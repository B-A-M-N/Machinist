from __future__ import annotations

import argparse
import subprocess
import sys
import re
import json
import os # Import the os module
from pathlib import Path
from textwrap import indent
from dataclasses import asdict

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import MachinistConfig
from .llm import OllamaClient, OllamaAPIClient, FallbackOllamaClient
from .pipeline import MachinistPipeline
from .registry import ToolRegistry
from .sandbox import SandboxPolicy
from .parsing import to_safe_module_name
from . import standard_tools
from .templates import select_template, TEMPLATE_REGISTRY, PseudoSpecTemplate, spec_from_fg_skeleton
from .extractor import spec_from_existing_function, specs_from_directory, comp_spec_from_existing_script
from .workflow import WorkflowEngine
from .prompts.autonomous_tool_creation_prompts import GENERATE_AUTONOMOUS_GOAL_PROMPT
from .llm.base import render_prompt

DEFAULT_MODELS = ["rnj-1:8b-cloud", "phi4-mini", "llama3.2", "qwen3:4b", "qwen2.5-coder:3b"]
CONSOLE = Console()

# --- UI Components ---

def show_splash() -> None:
    SPLASH_ART = r"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠀⠀⠀⢠⣶⣶⣶⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢀⣴⣾⣿⣷⣄⢀⣸⣿⣿⣿⣿⣄⠀⣴⣿⣿⣶⣄⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠇⠀⠀⠀⠀⠀
⠀⠀⢀⣴⣦⣤⣠⣾⣿⣿⣿⠟⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣀⣤⣤⡄⠀
⠀⠀⣾⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⢙⣿⣿⣿⣿⣿⡿⠋⢹⣿⣿⣿⣿⣿⣿⣿⡆
⠀⠀⠉⠻⣿⣿⣿⡿⠁⠀⠀⠀⣴⣿⣿⣿⣿⣿⣿⠃⠀⠻⠿⠃⣿⣿⣿⣿⠋⠀
⣡⣀⣀⣼⣿⣿⣿⡇⠀⠀⣠⡟⠉⠙⢿⣿⣿⡿⠉⠀⢀⣨⣤⣴⣿⣿⣿⣿⣀⣀
⢸⣿⣿⣿⣿⣿⣿⣷⣠⣾⣿⣿⣦⡄⣠⡿⠃⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠁⠀⣠⡾⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⠀⠀⢙⣿⣿⣿⣿⣿⠿⠿⠟⠁⠀⣠⣾⣧⡀⠀⠈⠻⣿⣿⣿⣿⣿⣿⡏⠀⠀
⠀⠀⣵⣿⣿⣿⣿⣿⠁⣾⡀⠀⢠⣾⣿⣿⣿⣿⣦⡀⠀⠈⢻⣿⣿⣿⣿⣿⣶⡀
⠀⠀⢻⣿⣿⣿⣿⣿⣼⣿⡟⠀⣼⣿⣿⣿⣿⣿⣿⣿⣦⣤⣾⣿⣿⣿⣿⣿⣿⠃
⠀⠀⠀⠙⠉⠁⠈⣻⣿⣿⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠋⠀⠉⠙⠁⠀
⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⡿⢿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠙⠻⢿⠏⠀⠀⢸⣿⣿⣿⣿⠀⠀⠘⠿⠿⠛⠁⠀⠀⠀⠀⠀
"""
    title = Text("Welcome to Machinist: Your LLM-Tooling Foundry", style="bold cyan")
    art = Text(SPLASH_ART, style="bold blue")
    CONSOLE.print(Panel.fit(art, title=title, border_style="cyan"))

def _print_block(title: str, content: str, max_lines: int = 20) -> None:
    content = content.strip()
    lines = content.splitlines()
    if len(lines) > max_lines:
        content = "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines) - max_lines} more lines)"
    CONSOLE.print(Panel.fit(indent(content, "  "), title=title, border_style="cyan"), markup=False)

def _confirm(message: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    resp = input(f"{message} {suffix} ").strip().lower()
    if not resp:
        return default
    return resp in ("y", "yes")

def _pick_main_mode() -> str:
    CONSOLE.print("\nSelect an operating mode:", style="bold yellow")
    modes = {
        "1": "Generate Single Tool",
        "2": "Generate & Run Workflow",
        "3": "Extract Spec from File or Directory",
        "4": "Extract Composition Spec from Script",
        "5": "Autonomous Tool Creation",
        "6": "Search Registry",
        "q": "Quit"
    }
    for key, desc in modes.items():
        CONSOLE.print(f"  {key}) {desc}")
    
    while True:
        choice = input("Mode: ").strip().lower()
        if choice in modes:
            return modes[choice]
        if choice == 'exit':
            return "Quit"
        print("Invalid choice, please try again.")

def handle_search_registry(pipeline: MachinistPipeline, registry: ToolRegistry, args: argparse.Namespace):
    if hasattr(args, 'goal') and args.goal:
        query = args.goal
    else:
        query = input("\nEnter search query: ").strip()
    
    if not query:
        return

    print(f"\nSearching for: '{query}'...")
    # Use the embedder from the pipeline
    embedder = pipeline.embed_llm.embeddings if pipeline and hasattr(pipeline.embed_llm, 'embeddings') else None
    results = registry.search_tools(query, embedder=embedder)

    if not results:
        print("No matching tools found.")
        return

    print(f"\nFound {len(results)} matching tools:")
    for i, tool in enumerate(results):
        CONSOLE.print(f"  {i+1}) [bold cyan]{tool.spec.name}[/bold cyan] (ID: {tool.tool_id})")
        print(f"     Description: {tool.spec.docstring.splitlines()[0]}")

# --- Mode Handlers ---

def handle_generate_single_tool(pipeline: MachinistPipeline, registry: ToolRegistry, args: argparse.Namespace):
    if hasattr(args, 'goal') and args.goal:
        goal = args.goal
    else:
        goal = input("\nEnter tool goal: ").strip()
        
    if not goal:
        return

    # --- NEW: Tool-Gap Analysis with FunctionGemma ---
    print("\nAnalyzing goal with FunctionGemma...")
    decision = pipeline.llm_interface.propose_tool_or_spec_skeleton(goal, list(TEMPLATE_REGISTRY.values()))
    
    template = None
    spec = None

    if decision.get("decision") == "use_existing":
        template_id = decision.get("template_id")
        template = TEMPLATE_REGISTRY.get(template_id)
        if not template:
            print(f"Warning: FunctionGemma selected a non-existent template '{template_id}'. Falling back.")
        else:
            print(f"FunctionGemma recommends using template: '{template.id}'")

    elif decision.get("decision") == "create_new":
        print("FunctionGemma recommends creating a new tool.")
        new_spec_skeleton = decision.get("tool_spec")
        if new_spec_skeleton:
            print("Generating ToolSpec from FunctionGemma skeleton...")
            spec = spec_from_fg_skeleton(new_spec_skeleton)
            # The new spec is not associated with a template yet.
            template = None 
        else:
            print("Warning: FunctionGemma recommended a new tool but did not provide a spec. Falling back.")
            template = select_template(goal) # Fallback to keyword search

    elif decision.get("decision") == "create_composition":
        print("FunctionGemma recommends a multi-step workflow for this goal.")
        print("Please use the 'Generate & Run Workflow' mode for this task.")
        return # End this mode
    
    else: # Fallback for error or unknown decision
        print("Tool-gap analysis was inconclusive. Falling back to keyword search.")
        template = select_template(goal)

    # --- Spec Generation ---
    print("\n[1/4] Generating spec...")
    if spec: # Spec was already created from a new skeleton
        pass
    elif template:
        print(f"Using pseudo-spec template '{template.id}' to guide LLM...")
        spec = pipeline.generate_spec_from_template(goal, template, stream=True, on_token=lambda t: print(t, end="", flush=True))
    else:
        print("No template found, using general LLM...")
        spec = pipeline.generate_spec(goal, stream=True, on_token=lambda t: print(t, end="", flush=True))
    
    if not spec:
        print("Failed to generate a spec. Aborting.")
        return

    print()
    _print_block("Spec", spec.to_json())

    # --- Implementation, Testing, Promotion (same as before) ---
    # ...
    # ... (rest of the logic from the original function)
    # ...
    print("\n[2/4] Generating implementation...")
    spec, code, spec_changed = pipeline.generate_implementation(spec, template=template, stream=True, on_token=lambda t: print(t, end="", flush=True))
    print()
    _print_block("Implementation", code)

    print("\n[3/4] Generating tests...")
    tests = pipeline.generate_tests(spec, template=template, stream=True, on_token=lambda t: print(t, end="", flush=True))
    print()
    _print_block("Tests", tests)

    source_path, tests_path = pipeline.write_artifacts(spec, code, tests)

    print("\n[4/4] Running validation...")
    validation = pipeline.validate(source_path, tests_path, stream=True, on_output=lambda name, chunk: print(chunk, end="", flush=True), func_name=spec.name)
    if not validation.is_ok():
        print("\nValidation failed; attempting repair...")
        validation, _, _ = pipeline.repair_and_validate(spec, source_path, tests_path, validation)
        if not validation.is_ok():
            print("Validation failed after repair attempts.")
            return

    interactive = args.mode is None

    if (interactive and _confirm("Promote tool to registry?")) or (not interactive and getattr(args, 'promote', False)):
        meta = pipeline.promote(spec, source_path, tests_path, validation, template=template)
        print(f"Promoted tool {spec.name} -> {meta.tool_id}")
    elif not interactive:
        print("\nNon-interactive mode: skipping promotion to registry.")


def handle_run_workflow(pipeline: MachinistPipeline, registry: ToolRegistry, args: argparse.Namespace):
    if hasattr(args, 'goal') and args.goal:
        goal = args.goal
    else:
        goal = input("\nEnter workflow goal: ").strip()

    if not goal:
        return
        
    print("\n[1/3] Generating composition spec...")
    # Gather templates from registry + built-ins
    registered_tools = registry.list_tools()
    registered_templates = [PseudoSpecTemplate.from_tool_spec(t.spec) for t in registered_tools]
    all_templates = list(TEMPLATE_REGISTRY.values()) + registered_templates
    
    # Also pass the tool IDs for rules to prevent hallucination
    # Note: PseudoSpecTemplate.from_tool_spec sets id=spec.name
    available_tool_ids = [t.id for t in all_templates]
    ids_str = ", ".join(f'"{tid}"' for tid in available_tool_ids)

    comp_spec = pipeline.generate_composition_spec(goal, all_templates, available_tool_ids_for_rules_str=ids_str)
    _print_block("Composition Spec", json.dumps(asdict(comp_spec), indent=2, default=str))

    print("\n[2/3] Preparing workflow engine...")
    engine = WorkflowEngine(registry)
    
    workflow_inputs = {}
    
    # Pre-fill from --inputs arg if provided
    if args.inputs:
        try:
            workflow_inputs.update(json.loads(args.inputs))
        except Exception as e:
            print(f"Warning: Failed to parse --inputs JSON: {e}")

    if comp_spec.inputs:
        # Only ask for missing inputs
        for name, type_hint in comp_spec.inputs.items():
            if name in workflow_inputs:
                continue
                
            if args.mode is not None:
                 print(f"Non-interactive mode: Missing input '{name}' ({type_hint}). Workflow may fail.")
            else:
                value = input(f"  {name} ({type_hint}): ")
                workflow_inputs[name] = value

    print("\n[3/3] Executing workflow...")
    try:
        final_context = engine.execute(comp_spec, workflow_inputs)
        print("\n--- Workflow Finished ---")
        _print_block("Final Workflow Context", json.dumps(final_context, indent=2, default=str))
    except Exception as e:
        print(f"\n--- Workflow Failed ---")
        CONSOLE.print(f"Error during execution: {e}", style="bold red")

def handle_extract_spec(registry: ToolRegistry):
    target_path_str = input("\nEnter path to file or directory to extract from: ").strip()
    if not target_path_str:
        return
        
    expanded_path_str = os.path.expanduser(target_path_str)
    target_path = Path(expanded_path_str)

    if not target_path.exists():
        print(f"Error: Path does not exist: {target_path_str}") # Show original path in error
        return

    if target_path.is_dir():
        print(f"Extracting all specs from directory '{target_path_str}'...")
        specs = specs_from_directory(expanded_path_str, registry)
        if not specs:
            print("No tool functions found or extracted.")
            return
        
        for i, spec in enumerate(specs):
            _print_block(f"Extracted Spec {i+1}/{len(specs)} for {spec.name}", spec.to_json())

    elif target_path.is_file():
        func_name = input("Enter function name to extract from file: ").strip()
        if not func_name:
            return
        
        print(f"Extracting spec for '{func_name}' from '{target_path_str}'...")
        spec = spec_from_existing_function(expanded_path_str, func_name, registry)
        
        if spec:
            _print_block(f"Extracted Spec for {func_name}", spec.to_json())
        else:
            print("Spec extraction failed.")
    else:
        print(f"Error: Path is not a file or a directory: {target_path}")


def handle_extract_composition_spec(registry: ToolRegistry):
    script_path_str = input("\nEnter path to script to extract Composition Spec from: ").strip()
    if not script_path_str:
        return
    
    script_path = Path(script_path_str)
    if not script_path.is_file():
        print(f"Error: Path is not a file or does not exist: {script_path}")
        return
    
    print(f"Extracting Composition Spec from script '{script_path_str}'...")
    comp_spec = comp_spec_from_existing_script(script_path_str, registry)

    if comp_spec:
        _print_block(f"Extracted Composition Spec from {script_path.name}", json.dumps(asdict(comp_spec), indent=2, default=str))
    else:
        print("Composition Spec extraction failed.")


def handle_autonomous_tool_creation(pipeline: MachinistPipeline, registry: ToolRegistry, args: argparse.Namespace):
    print("\n--- Autonomous Tool Creation ---")
    
    while True:
        if not _confirm("Start a new autonomous tool creation iteration?", default=True):
            break

        print("\n[1/4] Getting existing tools...")
        existing_tools = registry.list_tools()
        if not existing_tools:
            print("No existing tools found in the registry. Please add some tools first.")
            return

        print("--- Registered Tools ---")
        canonical_tool_ids = []
        for tool in existing_tools:
            print(f"- ID: {tool.tool_id}, Name: {tool.spec.name}")
            canonical_tool_ids.append(tool.tool_id)
        print("------------------------")

        # Prepare existing tools JSON for goal generation prompt
        existing_tools_json = json.dumps([asdict(t.spec) for t in existing_tools], indent=2)

        # Extract actual tool IDs for CompositionSpec generation prompt rules
        available_tool_ids_for_rules = canonical_tool_ids
        available_tool_ids_for_rules_str = ", ".join(f'"{tid}"' for tid in available_tool_ids_for_rules)


        print("\n[2/4] Generating a new tool goal...")
        goal_prompt = render_prompt(GENERATE_AUTONOMOUS_GOAL_PROMPT, existing_tools_json=existing_tools_json)
        new_goal = pipeline.llm_interface.spec_llm.complete(
            "You are an expert system architect.", goal_prompt
        ).strip()

        print(f"Generated Goal: {new_goal}")



        try:
            print("\n[3/4] Creating the composite tool...")
            templates = [PseudoSpecTemplate.from_tool_spec(t.spec) for t in existing_tools]
            pipeline.create_composite_tool(new_goal, templates, available_tool_ids_for_rules_str=available_tool_ids_for_rules_str, stream=True, on_token=lambda t: print(t, end="", flush=True))


            print("\n[4/4] Autonomous tool creation iteration finished.")
        except Exception as e:
            print(f"\n--- Autonomous Tool Creation Failed ---")
            CONSOLE.print(f"Error during tool creation: {e}", style="bold red")


# --- Main Application Logic ---

def main(argv: list[str] | None = None) -> int:
    show_splash()
    parser = argparse.ArgumentParser(description="Machinist: Your LLM-Tooling Foundry")
    parser.add_argument("--model", default="rnj-1:8b-cloud", help="Ollama model name for non-interactive runs.")
    parser.add_argument("--registry", default="registry", help="Registry directory.")
    parser.add_argument("--mode", help="Mode to run (1-6).")
    parser.add_argument("--goal", help="Goal or query for the selected mode.")
    parser.add_argument("--inputs", help="JSON string of inputs for workflows.")
    parser.add_argument("--promote", action="store_true", help="Automatically promote tool to registry in non-interactive mode.")
    args = parser.parse_args(argv)

    registry = ToolRegistry(Path(args.registry))
    pipeline = None

    # Helper to map numeric mode to string
    mode_map = {
        "1": "Generate Single Tool",
        "2": "Generate & Run Workflow",
        "3": "Extract Spec from File or Directory",
        "4": "Extract Composition Spec from Script",
        "5": "Autonomous Tool Creation",
        "6": "Search Registry"
    }

    interactive = args.mode is None

    while True:
        if interactive:
            mode = _pick_main_mode()
        else:
            mode = mode_map.get(args.mode)
            if not mode:
                print(f"Invalid mode: {args.mode}")
                return 1

        if mode == "Quit":
            return 0
        
        if pipeline is None and mode in ["Generate Single Tool", "Generate & Run Workflow", "Autonomous Tool Creation", "Search Registry"]:
            print("Initializing LLM clients...")
            spec_llm = OllamaClient(args.model)
            impl_llm = OllamaClient(args.model)
            test_llm = OllamaClient(args.model)
            fg_llm = OllamaAPIClient("functiongemma")
            embed_llm = OllamaAPIClient("nomic-embed-text")

            pipeline = MachinistPipeline(
                spec_llm=spec_llm,
                impl_llm=impl_llm,
                test_llm=test_llm,
                fg_llm=fg_llm,
                embed_llm=embed_llm,
                registry=registry,
                sandbox_policy=SandboxPolicy(),
            )

        if mode == "Generate Single Tool":
            handle_generate_single_tool(pipeline, registry, args)
        elif mode == "Generate & Run Workflow":
            handle_run_workflow(pipeline, registry, args)
        elif mode == "Extract Spec from File or Directory":
            handle_extract_spec(registry)
        elif mode == "Extract Composition Spec from Script":
            handle_extract_composition_spec(registry)
        elif mode == "Autonomous Tool Creation":
            handle_autonomous_tool_creation(pipeline, registry, args)
        elif mode == "Search Registry":
            handle_search_registry(pipeline, registry, args)
        
        if not interactive:
            break

        print("\n" + "="*50 + "\n")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())