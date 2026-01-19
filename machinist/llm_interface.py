from __future__ import annotations

import re
import ast
import json
import traceback # Import traceback
from dataclasses import asdict
from typing import Dict, List, Tuple, Any, Optional

from .llm.base import DEFAULT_SYSTEM_PROMPT, LLMClient, render_prompt
from .parsing import json_coerce, extract_json_block, extract_json_safely # Import extract_json_safely
from .prompts.spec_prompts import SPEC_PROMPT, SPEC_PROMPT_FROM_TEMPLATE
from .prompts.impl_prompts import IMPLEMENT_PROMPT
from .prompts.test_prompts import TEST_PROMPT
from .prompts.composition_prompts import COMPOSITION_SPEC_PROMPT
from .prompts.function_gemma_prompts import TOOL_GAP_ANALYSIS_PROMPT
from .registry import ToolSpec, ToolRegistry
from .templates import PseudoSpecTemplate, CompositionSpec, CompositionStep, StepBinding, FailurePolicy


class LLMInterface:
    def __init__(self, spec_llm: LLMClient, impl_llm: LLMClient, test_llm: LLMClient, fg_llm: LLMClient, registry: ToolRegistry):
        self.spec_llm = spec_llm
        self.impl_llm = impl_llm
        self.test_llm = test_llm
        self.fg_llm = fg_llm # Store FunctionGemma client
        self.registry = registry # Store registry instance

    def select_template_with_functiongemma(self, goal: str, templates: List[PseudoSpecTemplate]) -> Optional[Tuple[PseudoSpecTemplate, Dict[str, Any]]]:
        """
        Uses FunctionGemma to select the best tool and extract arguments from a user goal.
        """
        if not hasattr(self.fg_llm, "chat_with_tools"):
            print("Warning: FunctionGemma client does not support tool calling. Skipping.")
            return None

        ollama_tools = [to_ollama_tool_schema(t) for t in templates]
        
        messages = [{"role": "user", "content": goal}]

        try:
            print("Calling FunctionGemma for tool selection...")
            response = self.fg_llm.chat_with_tools(messages=messages, tools=ollama_tools)
            
            tool_calls = response.get("message", {}).get("tool_calls")
            if not tool_calls:
                print("FunctionGemma did not select a tool.")
                return None

            # For now, just use the first tool call
            tool_call = tool_calls[0]
            tool_name = tool_call.get("function", {}).get("name")
            tool_args = tool_call.get("function", {}).get("arguments")

            if not tool_name or not isinstance(tool_args, dict):
                print("Invalid tool_call format from FunctionGemma.")
                return None

            # Find the original PseudoSpecTemplate that matches the selected tool name (intent)
            for template in templates:
                if template.intent == tool_name:
                    print(f"FunctionGemma selected tool: {template.id} with args: {tool_args}")
                    return template, tool_args
            
            print(f"FunctionGemma selected tool '{tool_name}' which is not in the provided templates.")
            return None

        except Exception as e:
            print(f"Error during FunctionGemma tool selection: {e}")
            return None

    def propose_tool_or_spec_skeleton(self, goal: str, templates: List[PseudoSpecTemplate]) -> Dict[str, Any]:
        """
        Uses FunctionGemma (or the intelligence model) to analyze the goal and propose 
        using an existing template, creating a composition, or creating a new tool skeleton.
        """
        # Prepare the tool index for the prompt
        tool_index = {}
        for t in templates:
            tool_index[t.id] = t.description
        
        tool_index_json = json.dumps(tool_index, indent=2)

        prompt = render_prompt(
            TOOL_GAP_ANALYSIS_PROMPT, 
            goal=goal, 
            tool_index_json=tool_index_json
        )

        try:
            print("Asking LLM to analyze tool gap...")
            # Use spec_llm (rnj-1:8b-cloud) instead of fg_llm for better reasoning
            raw_response = self.spec_llm.complete(DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.1, max_tokens=1500)
            
            # Use the new robust extraction
            decision_data = extract_json_safely(raw_response)
            return decision_data

        except Exception as e:
            print(f"Error during tool gap analysis: {e}")
            if 'raw_response' in locals():
                print(f"RAW LLM RESPONSE: {repr(raw_response)}")
            # Fallback to a safe default that triggers keyword search in the caller
            return {"decision": "error", "reason": str(e)}


    def generate_spec(
        self,
        goal: str, *, 
        stream: bool = True, 
        on_token=None, 
        max_attempts: int = 3
    ) -> ToolSpec:
        prompt = f"{SPEC_PROMPT}\nGoal: {goal}"
        error = None
        data = None
        for i in range(max_attempts):
            if error:
                prompt = f"""FORMAT VIOLATION. You must return the TOOL SPEC as a single JSON object.\nYour previous attempt failed with the following error: {error}\nThe original goal for the tool was: '{goal}'\nProvide the correct and complete JSON object now.\n"""
            raw = self.spec_llm.stream_complete(
                DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=1000, on_token=on_token
            ) if (stream and i == 0) else self.spec_llm.complete(
                DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=1000
            )

            try:
                data = self._coerce_spec(raw)
                # Cache the generated spec
                spec_obj = ToolSpec(**data)
                cache_id = self.registry.cache_spec(spec_obj, {"goal": goal})
                print(f"Cached generated spec with ID: {cache_id}")
                return spec_obj
            except ValueError as e:
                error = e
                print(f"Spec generation failed (attempt {i+1}/{max_attempts}): {e}")
                data = None

        if not data:
            raise ValueError(
                f"Failed to generate a valid spec after {max_attempts} attempts. Last error: {error}"
            )
        # This part should be unreachable if data is None, but kept for type hints
        return ToolSpec(**data)


    def generate_spec_from_template(
        self,
        goal: str,
        template: PseudoSpecTemplate,
        *,
        stream: bool = True,
        on_token=None,
        max_attempts: int = 3,
    ) -> ToolSpec:
        template_json = json.dumps(asdict(template), indent=2)
        prompt = render_prompt(
            SPEC_PROMPT_FROM_TEMPLATE, template_json=template_json, goal=goal
        )

        error = None
        data = None
        for i in range(max_attempts):
            if error:
                prompt = f"""FORMAT VIOLATION. Your previous attempt failed.\nYou MUST follow the constraints from the template and the goal.\nYour previous attempt failed with the following error: {error}\nYou must return ONLY the `ToolSpec` JSON object in a markdown code fence.\n"""
            raw = self.spec_llm.stream_complete(
                DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.1, max_tokens=1000, on_token=on_token
            ) if (stream and i == 0) else self.spec_llm.complete(
                DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.1, max_tokens=1000
            )

            try:
                data = self._coerce_spec(raw)
                # Cache the generated spec
                spec_obj = ToolSpec(**data)
                cache_id = self.registry.cache_spec(spec_obj, {"goal": goal, "template_id": template.id})
                print(f"Cached generated spec from template with ID: {cache_id}")
                return spec_obj
            except ValueError as e:
                error = e
                print(f"Spec generation from template failed (attempt {i+1}/{max_attempts}): {e}")
                data = None

        if not data:
            raise ValueError(
                f"Failed to generate valid spec from template after {max_attempts} attempts. Last error: {error}"
            )
        # This part should be unreachable if data is None, but kept for type hints
        return ToolSpec(**data)
        
    def generate_composition_spec(self, goal: str, available_tools: List[PseudoSpecTemplate], *, stream: bool = True, on_token=None, max_attempts: int = 3, available_tool_ids_for_rules_str: str | None = None) -> CompositionSpec:
        available_tools_json = json.dumps([asdict(t) for t in available_tools], indent=2)
        
        prompt_args = {
            "available_tools_json": available_tools_json,
            "goal": goal
        }
        if available_tool_ids_for_rules_str:
            prompt_args["available_tool_ids_for_rules"] = available_tool_ids_for_rules_str

        prompt = render_prompt(COMPOSITION_SPEC_PROMPT, **prompt_args)
        
        error = None
        data = None
        raw_output_for_repair = None
        
        for i in range(max_attempts):
            current_prompt = prompt
            if error:
                # Repair prompt: provide feedback to the LLM
                current_prompt = f"""You previously produced an invalid CompositionSpec.
Please correct the following error and return ONLY the corrected JSON object.

ERROR: {error}
INVALID OUTPUT: {raw_output_for_repair or "N/A"}

{prompt}
"""
            
            raw = self.spec_llm.stream_complete(DEFAULT_SYSTEM_PROMPT, current_prompt, temperature=0.1, max_tokens=2000, on_token=on_token) if (stream and i==0) else self.spec_llm.complete(DEFAULT_SYSTEM_PROMPT, current_prompt, temperature=0.1, max_tokens=2000)

            # --- Robustness fixes begin here ---
            print(f"--- RAW LLM RESPONSE (CompositionSpec) ---\n{repr(raw)}\n--- END ---") # Log raw response
            raw_output_for_repair = raw # Store for potential repair prompt

            if not raw:
                error = RuntimeError("CompositionSpec generation returned no content from LLM.")
                continue
            if not isinstance(raw, str):
                error = RuntimeError(f"LLM returned non-string: {type(raw)} -> {raw}")
                continue

            spec_text = raw.strip()
            if not spec_text:
                error = RuntimeError("LLM returned empty string for CompositionSpec generation.")
                continue

            try:
                raw_json = extract_json_block(spec_text)
                data = json.loads(raw_json)
            except (ValueError, json.JSONDecodeError) as e:
                error = e
                print(f"CompositionSpec JSON extraction/parsing failed (attempt {i+1}/{max_attempts}): {e}")
                data = None
                continue # Try again

            try:
                # Normalize nullable fields with defaults
                data["inputs"] = data.get("inputs") or {}
                data["steps"] = data.get("steps") or []
                data["global_postconditions"] = data.get("global_postconditions") or []
                data["failure_policy"] = data.get("failure_policy") or []
                data["semantic_tags"] = data.get("semantic_tags") or []

                # Type checks for iterables
                if not isinstance(data["steps"], list):
                    raise ValueError(f"CompositionSpec.steps must be list, got {type(data['steps'])}.")
                if not isinstance(data["inputs"], dict):
                    raise ValueError(f"CompositionSpec.inputs must be dict, got {type(data['inputs'])}.")
                if not isinstance(data["global_postconditions"], list):
                    raise ValueError(f"CompositionSpec.global_postconditions must be list, got {type(data['global_postconditions'])}.")
                if not isinstance(data["failure_policy"], list):
                    raise ValueError(f"CompositionSpec.failure_policy must be list, got {type(data['failure_policy'])}.")
                if not isinstance(data["semantic_tags"], list):
                    raise ValueError(f"CompositionSpec.semantic_tags must be list, got {type(data['semantic_tags'])}.")

                # Re-hydrate into dataclasses for type safety and cache
                required_top_keys = ["pipeline_id", "description"]
                if not all(k in data for k in required_top_keys):
                    raise ValueError(f"Generated CompositionSpec is missing required top-level keys: {', '.join(k for k in required_top_keys if k not in data)}.")
                
                steps = [CompositionStep(
                    id=s.get('id', f"step_{idx}"), # Provide default ID
                    tool_id=s['tool_id'],
                    bind={k: StepBinding(v) for k, v in s.get('bind', {}).items()},
                    foreach=s.get('foreach'),
                    outputs=s.get('outputs', {}),
                    then_tool_id=s.get('then_tool_id'),
                    then_bind={k: StepBinding(v) for k, v in s.get('then_bind', {}).items()}
                ) for idx, s in enumerate(data['steps'])]

                policies = [FailurePolicy(**p) for p in data['failure_policy']]

                comp_spec_obj = CompositionSpec(
                    pipeline_id=data['pipeline_id'],
                    description=data['description'],
                    inputs=data['inputs'],
                    steps=steps,
                    global_postconditions=data['global_postconditions'],
                    failure_policy=policies,
                    semantic_tags=data['semantic_tags']
                )
                
                cache_id = self.registry.cache_spec(comp_spec_obj, {"goal": goal, "available_tools_count": len(available_tools)})
                print(f"Cached generated CompositionSpec with ID: {cache_id}")
                return comp_spec_obj

            except Exception as e:
                error = e
                print("CompositionSpec generation exception:")
                traceback.print_exc() # Print full traceback
                print(f"CompositionSpec generation failed (attempt {i+1}/{max_attempts}): {e!r}") # Use !r for detailed error
                data = None
                continue # Try again

        raise ValueError(f"Failed to generate a valid CompositionSpec after {max_attempts} attempts. Last error type: {type(error).__name__ if error else 'None'} Last error: {error!r}")

    def generate_implementation(
        self,
        spec: ToolSpec,
        *,
        stream: bool = True,
        on_token=None,
        error_feedback: str | None = None,
    ) -> str:
        prompt = render_prompt(
            IMPLEMENT_PROMPT,
            contract_json=spec.to_json(),
            func_name=spec.name
        )
        if error_feedback:
            prompt += f"\n{error_feedback}"
        return self.impl_llm.stream_complete(
            DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.0, max_tokens=2000, on_token=on_token
        ) if stream else self.impl_llm.complete(
            DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.0, max_tokens=2000
        )

    def generate_tests(
        self,
        spec: ToolSpec,
        *,
        stream: bool = True,
        on_token=None,
        strict: bool = False,
        safe_name: str,
        test_skeleton: str,
    ) -> str:
        prompt = render_prompt(
            TEST_PROMPT,
            contract_json=spec.to_json(),
            test_skeleton=test_skeleton,
            required_import=f"from {safe_name} import {spec.name}",
        )
        return self.test_llm.stream_complete(
            DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=1200, on_token=on_token
        ) if stream else self.test_llm.complete(
            DEFAULT_SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=1200
        )

    def _coerce_spec(self, raw: str) -> Dict:
        data = json_coerce(raw)
        if not isinstance(data, dict):
            raise ValueError("Spec coercion failed: output is not a dict")

        if data and all(isinstance(v, dict) for v in data.values()) and len(data) == 1:
            data = next(iter(data.values()))
        if "strict_json" in data and isinstance(data["strict_json"], dict):
            data = {**data, **data["strict_json"]}

        required_keys = ["name", "signature", "docstring", "imports", "inputs", "outputs", "failure_modes", "deterministic"]
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Spec missing required key: {key}")

        if not isinstance(data["name"], str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", data["name"]):
            raise ValueError(f"Generated tool name '{data['name']}' is not a valid Python identifier.")

        try:
            sig_tree = ast.parse(data["signature"].strip() + " pass")
            func_def = next((n for n in ast.walk(sig_tree) if isinstance(n, ast.FunctionDef)), None)
            if not func_def:
                raise ValueError("Signature is not a valid function definition.")
            sig_params = {arg.arg for arg in func_def.args.args}
            if sig_params != set(data["inputs"].keys()):
                raise ValueError(f"Signature parameters {sig_params} do not match input keys {set(data['inputs'].keys())}.")
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Spec coherence check failed: {e}")

        return data