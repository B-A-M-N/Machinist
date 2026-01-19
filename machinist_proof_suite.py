#!/usr/bin/env python3
"""
Machinist Proof Suite
=====================
This script provides an extensive, end-to-end verification of the Machinist framework.
It demonstrates and proves the functionality of:
1. Atomic Tool Generation (Mode 1)
2. Semantic Registry Search (Mode 6)
3. Workflow Generation & Execution (Mode 2)
4. Complex Logic (Conditionals)
5. Sandboxed Safety (Resource Limits)

Usage:
    python3 machinist_proof_suite.py
"""

import subprocess
import sys
import shutil
import json
import time
from pathlib import Path

# Configuration
REGISTRY_DIR = "proof_registry"
CLI_CMD = [sys.executable, "-m", "machinist.cli", "--registry", REGISTRY_DIR]

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}\n{title}\n{'='*80}{Colors.ENDC}")

def print_step(msg):
    print(f"{Colors.OKBLUE}>> {msg}{Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.OKGREEN}✔ PASS: {msg}{Colors.ENDC}")

def print_fail(msg):
    print(f"{Colors.FAIL}✘ FAIL: {msg}{Colors.ENDC}")
    sys.exit(1)

def clean_env():
    if Path(REGISTRY_DIR).exists():
        shutil.rmtree(REGISTRY_DIR)
    Path(REGISTRY_DIR).mkdir()
    # Cleanup test files
    for p in Path(".").glob("proof_*.txt"):
        p.unlink()
    if Path("conditional_out.txt").exists(): Path("conditional_out.txt").unlink()
    if Path("trigger.txt").exists(): Path("trigger.txt").unlink()

def run_cli(args, input_data=None, desc=""):
    print_step(f"Running: machinist {' '.join(args)}")
    
    proc = subprocess.run(
        CLI_CMD + args,
        input=input_data,
        capture_output=True,
        text=True
    )
    
    if proc.returncode != 0:
        print(f"{Colors.FAIL}STDERR:\n{proc.stderr}{Colors.ENDC}")
        print_fail(f"Command failed: {desc}")
    
    return proc.stdout

# --- TESTS ---

def proof_tool_generation():
    print_header("PROOF 1: ATOMIC TOOL GENERATION")
    
    # 1. Generate 'reverse_string'
    goal = "create a function that reverses a given string"
    out = run_cli(
        ["--mode", "1", "--goal", goal, "--promote"],
        desc="Generate 'reverse_string'"
    )
    
    if "Promoted tool" in out:
        print_success("Tool generated and promoted.")
    else:
        print(out)
        print_fail("Tool generation failed or was not promoted.")

    # 2. Verify it exists in registry
    tools = [t for t in Path(REGISTRY_DIR).iterdir() if t.is_dir() and t.name != "cached_specs"]
    if not tools:
        print_fail("Registry is empty.")
    print_success(f"Registry populated with: {[t.name for t in tools]}")

def proof_semantic_search():
    print_header("PROOF 2: SEMANTIC REGISTRY SEARCH")
    
    # Search for "flip text backwards" -> should find "reverse_string"
    out = run_cli(
        ["--mode", "6", "--goal", "flip text backwards"],
        desc="Search for 'flip text backwards'"
    )
    
    if "reverse" in out.lower() or "string" in out.lower():
        print_success("Semantic search successfully linked query to tool logic.")
    else:
        print(out)
        print_fail("Semantic search failed to find relevant tool.")

def proof_workflow_execution():
    print_header("PROOF 3: WORKFLOW GENERATION & EXECUTION")
    
    # 1. Generate 'write_file' tool
    print_step("Generating dependency: write_file tool...")
    goal_write = "create a tool named write_file that takes 'file_path' and 'content' and writes the content to the file"
    out = run_cli(
        ["--mode", "1", "--goal", goal_write, "--promote"],
        desc="Generate 'write_file'"
    )
    if "Promoted tool" not in out:
        print_fail("Failed to generate required 'write_file' tool.")

    # 2. Identify tool names dynamically
    tools = [t for t in Path(REGISTRY_DIR).iterdir() if t.is_dir() and t.name != "cached_specs"]
    tool_names = []
    for t_dir in tools:
        meta = json.loads((t_dir / "metadata.json").read_text())
        tool_names.append(meta['spec']['name'])
    
    reverse_tool = next((n for n in tool_names if "reverse" in n), "reverse_string")
    write_tool = next((n for n in tool_names if "write" in n), "write_file")
    
    # 3. Run Workflow
    goal = f"Use tool '{reverse_tool}' to reverse input 'text'. Then use tool '{write_tool}' to write the result to input 'path'."
    inputs = json.dumps({"text": "Machinist", "path": "proof_output.txt"})
    
    print_step(f"Running workflow using tools: {reverse_tool} -> {write_tool}")
    out = run_cli(
        ["--mode", "2", "--goal", goal, "--inputs", inputs],
        desc="Run Reverse+Write Workflow"
    )
    
    # 4. Verify Output
    expected_file = Path("proof_output.txt")
    if expected_file.exists():
        content = expected_file.read_text().strip()
        if "tsinihcaM" in content:
            print_success(f"Workflow executed correctly. Content: '{content}'")
        else:
            print_fail(f"File content wrong. Expected 'tsinihcaM', got '{content}'")
    else:
        print(out)
        print_fail("Output file 'proof_output.txt' was not created.")

def proof_conditional_logic():
    print_header("PROOF 4: COMPLEX CONDITIONAL LOGIC")
    
    # 1. Generate 'file_exists' tool
    print_step("Generating dependency: file_exists tool...")
    goal_exists = "check if a file exists and return a boolean"
    out = run_cli(
        ["--mode", "1", "--goal", goal_exists, "--promote"],
        desc="Generate 'file_exists'"
    )
    
    # 2. Run Conditional Scenario
    goal = "if 'trigger.txt' exists, write 'triggered' to 'conditional_out.txt'"
    
    # Scenario A: trigger.txt MISSING
    print_step("Scenario A: Trigger file missing (Should skip write)")
    run_cli(["--mode", "2", "--goal", goal], desc="Run Conditional Workflow (False)")
    if Path("conditional_out.txt").exists():
        print_fail("Workflow executed write step when it should have skipped!")
    else:
        print_success("Condition FALSE handled correctly (Write skipped).")
        
    # Scenario B: trigger.txt PRESENT
    print_step("Scenario B: Trigger file present (Should execute write)")
    Path("trigger.txt").write_text("exists")
    run_cli(["--mode", "2", "--goal", goal], desc="Run Conditional Workflow (True)")
    if Path("conditional_out.txt").exists():
        print_success("Condition TRUE handled correctly (Write executed).")
    else:
        print_fail("Workflow failed to execute write step when condition was true.")

def proof_sandboxing():
    print_header("PROOF 5: ADVANCED SANDBOXING (RESOURCE LIMITS)")
    
    from machinist.sandbox import BwrapSandbox, SandboxPolicy
    
    print_step("Running memory-bomb (100MB) with 20MB limit inside sandbox...")
    policy = SandboxPolicy(memory_limit_mb=20)
    sandbox = BwrapSandbox(policy)
    cmd = [sys.executable, "-c", "x = 'a' * (100 * 1024 * 1024); print('Allocated')"]
    
    res = sandbox.run(cmd, workdir=Path("/tmp"))
    
    if res.returncode != 0:
        print_success(f"Sandbox correctly killed memory-bomb (Exit Code: {res.returncode})")
    else:
        print_fail("Process survived memory limit! Resource isolation failed.")

def main():
    start_all = time.time()
    try:
        clean_env()
        proof_tool_generation()
        proof_semantic_search()
        proof_workflow_execution()
        proof_conditional_logic()
        proof_sandboxing()
        
        print_header("ALL PROOFS PASSED SUCCESSFULLY")
        print(f"Total Proof Duration: {time.time() - start_all:.2f}s")
    except Exception as e:
        print_fail(f"Exception during proof: {e}")
    finally:
        # Final cleanup of registry
        if Path(REGISTRY_DIR).exists():
            shutil.rmtree(REGISTRY_DIR)
        for p in ["proof_output.txt", "trigger.txt", "conditional_out.txt"]:
            if Path(p).exists(): Path(p).unlink()

if __name__ == "__main__":
    main()