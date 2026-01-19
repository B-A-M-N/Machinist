from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any

# from machinist.pipeline import MachinistPipeline # Removed to break circular dependency
from machinist.registry import ToolRegistry, ToolMetadata, ToolSpec
from machinist.templates import CompositionSpec, PseudoSpecTemplate
from machinist.prompts.auto_tool_creator_prompts import CREATE_COMPOSITE_TOOL_PROMPT
from machinist.llm.base import DEFAULT_SYSTEM_PROMPT, render_prompt
from machinist.llm_interface import LLMInterface
from machinist.parsing import extract_python_code
from machinist.static_analysis import reconcile_spec_from_impl_ast

# Forward declaration for MachinistPipeline to resolve type hinting without circular import
if False: # Only for type checking
    from machinist.pipeline import MachinistPipeline


class AutoToolCreator:
    # Define aliases for common LLM hallucinations or preferred naming
    ALIASES = {
        r"fs\.(\w+)\.v\d+": r"\1",  # e.g., fs.search_files.v1 -> search_files
        r"filesystem\.(\w+)": r"\1", # e.g., filesystem.copy -> copy
    }

    def __init__(self, pipeline: "MachinistPipeline", registry: ToolRegistry, llm_interface: LLMInterface):
        self.pipeline = pipeline
        self.registry = registry
        self.llm_interface = llm_interface

    def _resolve_tool_id_alias(self, tool_id: str) -> str:
        """Resolves tool_id aliases to their canonical form."""
        for pattern, replacement in self.ALIASES.items():
            match = re.fullmatch(pattern, tool_id)
            if match:
                return match.expand(replacement)
        return tool_id

    def create_tool_from_composition_spec(
        self,
        goal: str,
        available_tools: List[PseudoSpecTemplate],
        composition_spec: CompositionSpec | None = None,
        available_tool_ids_for_rules_str: str | None = None,
        stream: bool = True,
        on_token=None,
    ) -> ToolMetadata:
        
        if composition_spec is None:
            print(f"Generating CompositionSpec for goal: {goal}")
            composition_spec = self.pipeline.generate_composition_spec(
                goal, available_tools, stream=stream, on_token=on_token,
                available_tool_ids_for_rules_str=available_tool_ids_for_rules_str
            )
            print(f"Generated CompositionSpec: {composition_spec.pipeline_id}")

        # 1. Gather source code of component tools
        component_tools_source_map: Dict[str, str] = {}
        for step in composition_spec.steps:
            # Resolve alias before looking up in registry
            canonical_tool_id = self._resolve_tool_id_alias(step.tool_id)
            step.tool_id = canonical_tool_id # Update the tool_id in the step
            
            concrete_tool_ids = self.registry.find_by_template_id(step.tool_id)
            if not concrete_tool_ids:
                raise RuntimeError(f"Could not find concrete tool for template ID: {step.tool_id} (original: {step.tool_id})")
            
            # For now, just take the first concrete tool found
            tool_id_to_use = concrete_tool_ids[0]
            metadata = self.registry.load(tool_id_to_use)
            if not metadata:
                raise RuntimeError(f"Could not load metadata for tool ID: {tool_id_to_use}")
            
            source_path = metadata.source_path
            if not source_path.exists():
                raise FileNotFoundError(f"Source file for tool {tool_id_to_use} not found at {source_path}")
            
            component_tools_source_map[step.tool_id] = source_path.read_text(encoding="utf-8")

        component_tools_source = "\n\n".join(component_tools_source_map.values())

        # 2. Generate implementation of the composite tool
        print(f"Generating implementation for composite tool '{composition_spec.pipeline_id}'")
        raw_composite_code = self.llm_interface.impl_llm.stream_complete(
            DEFAULT_SYSTEM_PROMPT,
            render_prompt(
                CREATE_COMPOSITE_TOOL_PROMPT,
                composition_spec_json=composition_spec.to_json(),
                component_tools_source=component_tools_source,
            ),
            temperature=0.1,
            max_tokens=4000,
            on_token=on_token,
        )
        composite_code = extract_python_code(raw_composite_code)
        
        if not composite_code.strip():
            raise ValueError("LLM returned empty or invalid code for composite tool implementation.")

        # 3. Generate ToolSpec for the new composite tool based on its implementation
        # We need to create a temporary spec based on the composition spec's inputs
        # Then reconcile it with the generated code.
        temp_spec_inputs = {name: {"type": "Any", "description": f"Input {name}"} for name in composition_spec.inputs.keys()}
        temp_spec = ToolSpec(
            name=composition_spec.pipeline_id.replace('.', '_'), # Make it a valid Python identifier
            signature=f"def {composition_spec.pipeline_id.replace('.', '_')}({', '.join(composition_spec.inputs.keys())}):",
            docstring=composition_spec.description,
            inputs=temp_spec_inputs,
            outputs={"result": {"type": "Any", "description": "The result of the composite operation"}},
            failure_modes="",
            deterministic=False, # Composite tools might not be deterministic
            imports=[]
        )

        print(f"Reconciling ToolSpec for composite tool '{temp_spec.name}'")
        updated_spec, _ = reconcile_spec_from_impl_ast(temp_spec, composite_code)
        
        # 4. Generate tests for the composite tool
        print(f"Generating tests for composite tool '{updated_spec.name}'")
        composite_tests = self.pipeline.generate_tests(updated_spec, stream=stream, on_token=on_token)

        # 5. Write artifacts and promote
        source_path, tests_path = self.pipeline.write_artifacts(updated_spec, composite_code, composite_tests)

        print(f"Validating composite tool '{updated_spec.name}'")
        validation_result = self.pipeline.validate(source_path, tests_path, func_name=updated_spec.name, stream=stream)

        if not validation_result.lint_ok or not validation_result.tests_ok:
            print(f"Validation failed for composite tool '{updated_spec.name}'. Attempting repair...")
            repaired_validation, repaired_code, repaired_tests = self.pipeline.repair_and_validate(
                updated_spec, source_path, tests_path, validation_result
            )
            if repaired_validation.lint_ok and repaired_validation.tests_ok:
                print(f"Composite tool '{updated_spec.name}' repaired successfully.")
                # Overwrite with repaired code and tests
                source_path.write_text(repaired_code, encoding="utf-8")
                tests_path.write_text(repaired_tests, encoding="utf-8")
                validation_result = repaired_validation
            else:
                raise RuntimeError(f"Composite tool '{updated_spec.name}' could not be repaired.")
        
        print(f"Promoting composite tool '{updated_spec.name}' to registry.")
        tool_metadata = self.pipeline.promote(updated_spec, source_path, tests_path, validation_result, template=None)
        
        print(f"Successfully created and promoted composite tool: {tool_metadata.tool_id}")
        return tool_metadata
