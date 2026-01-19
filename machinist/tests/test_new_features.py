import pytest
from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch

from machinist.registry import ToolRegistry, ToolMetadata, ToolSpec
from machinist.workflow import WorkflowEngine
from machinist.templates import CompositionSpec, CompositionStep, StepBinding
from machinist.sandbox import BwrapSandbox, SandboxPolicy

# --- Registry Search Tests ---

def mock_embedder(text: str):
    text = text.lower()
    if "search" in text or "find" in text:
        return [1.0, 0.0]
    if "copy" in text:
        return [0.0, 1.0]
    return [0.5, 0.5]

def test_registry_semantic_search(tmp_path):
    registry = ToolRegistry(tmp_path)
    
    # Register tools
    tools = [
        ("search_files", "Finds files matching a pattern."),
        ("copy_file", "Copies a file from src to dst."),
    ]
    for name, doc in tools:
        spec = ToolSpec(name=name, signature="...", docstring=doc, inputs={}, outputs={}, failure_modes=[], deterministic=True)
        meta = ToolMetadata(tool_id=name, version="1", created_at="", spec=spec, source_path=Path("."), tests_path=Path("."), test_results_path=Path("."), dependencies={}, security_policy="", capability_profile="", model="")
        registry.register(meta)

    # Test Keyword Search Fallback
    results_kw = registry.search_tools("Finds")
    assert len(results_kw) > 0
    assert results_kw[0].tool_id == "search_files"
    
    # Test Semantic Search
    results_sem = registry.search_tools("search something", embedder=mock_embedder)
    assert len(results_sem) > 0
    assert results_sem[0].tool_id == "search_files"
    
    results_copy = registry.search_tools("copy this", embedder=mock_embedder)
    assert results_copy[0].tool_id == "copy_file"


# --- Complex Workflow Tests ---

def test_workflow_conditional(tmp_path):
    registry = ToolRegistry(tmp_path)
    
    # Register a "print_msg" tool executable
    mock_tool = MagicMock(return_value="executed")
    registry._executable_cache["print_msg"] = mock_tool
    
    # Register dummy metadata
    meta = ToolMetadata(tool_id="print_msg", version="1", created_at="", spec=ToolSpec("print_msg", "", "", {}, {}, [], True), source_path=Path("."), tests_path=Path("."), test_results_path=Path("."), dependencies={}, security_policy="", capability_profile="", model="", template_id="print_msg_template")
    registry.register(meta)

    engine = WorkflowEngine(registry)
    
    # Workflow: Step 1 always runs, Step 2 runs if $do_it is True
    spec = CompositionSpec(
        pipeline_id="test_pipeline",
        description="Test Conditional",
        steps=[
            CompositionStep(id="step1", tool_id="print_msg_template", bind={"msg": StepBinding("'Hello'")}, outputs={"res": "str"}),
            CompositionStep(id="step2", tool_id="print_msg_template", bind={"msg": StepBinding("'Conditional'")}, if_condition="$do_it", outputs={"res": "str"})
        ]
    )
    
    # Case 1: do_it = False
    ctx_false = engine.execute(spec, {"do_it": False})
    assert "step1" in ctx_false
    assert "step2" not in ctx_false
    assert mock_tool.call_count == 1
    
    # Case 2: do_it = True
    mock_tool.reset_mock()
    ctx_true = engine.execute(spec, {"do_it": True})
    assert "step1" in ctx_true
    assert "step2" in ctx_true
    assert mock_tool.call_count == 2


# --- Advanced Sandboxing Tests ---

@patch("shutil.which")
@patch("subprocess.run")
def test_sandbox_resource_limits(mock_subprocess, mock_which):
    # Mock 'prlimit' and 'bwrap' existence
    mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["bwrap", "prlimit"] else None
    
    # Policy with limits
    policy = SandboxPolicy(memory_limit_mb=512, cpu_time_limit_sec=10)
    sandbox = BwrapSandbox(policy)
    
    # Run a dummy command
    sandbox.run(["echo", "hello"], workdir=Path("/tmp"))
    
    # Verify subprocess call arguments
    args, _ = mock_subprocess.call_args
    cmd_list = args[0]
    
    # Check for prlimit injection
    # Expected structure: bwrap ... -- prlimit --as=... --cpu=... echo hello
    assert "bwrap" in cmd_list[0]
    assert "prlimit" in cmd_list
    
    prlimit_idx = cmd_list.index("prlimit")
    
    # Verify Memory Limit (512MB = 536870912 bytes)
    expected_mem = 512 * 1024 * 1024
    assert f"--as={expected_mem}" in cmd_list[prlimit_idx+1] or f"--as={expected_mem}" in cmd_list[prlimit_idx+2]
    
    # Verify CPU Limit
    assert "--cpu=10" in cmd_list[prlimit_idx+1] or "--cpu=10" in cmd_list[prlimit_idx+2]