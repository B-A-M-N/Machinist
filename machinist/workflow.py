from __future__ import annotations
from typing import Dict, Any, List
import os
import re
import json

from .templates import CompositionSpec
from .registry import ToolRegistry

class WorkflowEngine:
    """
    Executes a CompositionSpec (a multi-tool workflow).
    """
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self._execution_cache = {}

    def _hash_inputs(self, tool_id: str, inputs: Dict[str, Any]) -> str:
        # Sort keys to ensure stability. Convert values to string for simple hashing.
        try:
            s = json.dumps({k: str(v) for k,v in sorted(inputs.items())}, sort_keys=True)
        except:
            s = str(inputs)
        return f"{tool_id}:{s}"

    def _resolve_value(self, value: str, context: Dict[str, Any], item: Any = None) -> Any:
        """
        Resolves a value string like '$input.root_dir' or '$item' from the context.
        This is a very simple resolver and can be expanded.
        """
        if value == "$item" and item is not None:
            return item
        
        if value.startswith('$'):
            key = value[1:] # Remove '$'
            if '.' in key:
                # e.g., 'find.files'
                step_id, var_name = key.split('.', 1)
                if step_id in context and isinstance(context[step_id], dict):
                    return context[step_id].get(var_name)
                else:
                    raise ValueError(f"Could not resolve step '{step_id}' in context.")
            else:
                # e.g., 'root_dir'
                return context.get(key)
        
        # Handle simple literals (for now, just bools and strings)
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        # For now, assume it's a string literal if it's not a variable
        return value.strip('"').strip("'")


    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluates a simple condition string.
        Supports "$var", "$var == value", "$var != value".
        """
        if not condition:
            return True

        # Basic comparison parsing (very rudimentary)
        if "==" in condition:
            lhs, rhs = condition.split("==", 1)
            try:
                lhs_val = self._resolve_value(lhs.strip(), context)
                rhs_val = self._resolve_value(rhs.strip(), context)
                return str(lhs_val) == str(rhs_val)
            except: pass
        
        if "!=" in condition:
            lhs, rhs = condition.split("!=", 1)
            try:
                lhs_val = self._resolve_value(lhs.strip(), context)
                rhs_val = self._resolve_value(rhs.strip(), context)
                return str(lhs_val) != str(rhs_val)
            except: pass

        # Fallback: try to resolve as simple variable
        try:
            val = self._resolve_value(condition, context)
            return bool(val)
        except:
            pass # Not a simple variable
            
        print(f"Warning: Could not evaluate condition '{condition}', defaulting to False.")
        return False


    def _run_step_logic(self, step_id: str, tool_id: str, kwargs: Dict[str, Any]) -> Any:
        # 1. Check Nested Workflow
        nested_workflow = self.tool_registry.find_workflow_by_id(tool_id)
        if nested_workflow:
            print(f"    -> Entering nested workflow '{tool_id}'")
            # Recursive call
            # Note: nested workflow outputs context, but usually we want a specific output or the whole context?
            # CompositionSpec doesn't define a "return value" for the workflow itself, only context.
            # We'll assume the nested workflow returns its final context.
            # But a step expects a single result usually, or we map outputs.
            # For now, return the whole context.
            return self.execute(nested_workflow, kwargs)

        # 2. Find Tool
        concrete_tool_ids = self.tool_registry.find_by_template_id(tool_id)
        
        # Fallback: try to find by tool name directly
        if not concrete_tool_ids:
             all_tools = self.tool_registry.list_tools()
             concrete_tool_ids = [t.tool_id for t in all_tools if t.spec.name == tool_id]

        if not concrete_tool_ids:
            raise RuntimeError(f"Step '{step_id}': No registered tool found for template/name '{tool_id}'")
        
        tool_id_to_run = concrete_tool_ids[0]
        
        # 3. Check Cache
        meta = self.tool_registry.load(tool_id_to_run)
        # Check semantic tags (if available on spec) or deterministic flag
        is_pure = False
        if meta:
            spec = meta.spec
            is_pure = spec.deterministic or (hasattr(spec, 'semantic_tags') and ("pure" in spec.semantic_tags or "idempotent" in spec.semantic_tags))
        
        cache_key = self._hash_inputs(tool_id_to_run, kwargs)
        if is_pure and cache_key in self._execution_cache:
            print(f"    -> Cache Hit for {tool_id_to_run}")
            return self._execution_cache[cache_key]

        # 4. Execute
        executable_func = self.tool_registry.get_executable(tool_id_to_run)
        if not executable_func:
            raise RuntimeError(f"Step '{step_id}': Could not load executable for tool '{tool_id_to_run}'")
            
        print(f"    -> Calling {executable_func.__name__} with: {kwargs}")
        result = executable_func(**kwargs)
        
        if is_pure:
            self._execution_cache[cache_key] = result
            
        return result

    def execute(self, comp_spec: CompositionSpec, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the workflow defined by the CompositionSpec.
        """
        print(f"Executing workflow: {comp_spec.pipeline_id}")
        
        context: Dict[str, Any] = inputs.copy()
        
        for step in comp_spec.steps:
            print(f"  - Executing step: {step.id} (tool: {step.tool_id})")

            # Check Condition
            if step.if_condition:
                 if not self._evaluate_condition(step.if_condition, context):
                      print(f"    -> Skipping step '{step.id}' because condition '{step.if_condition}' is False.")
                      continue

            # Check for `foreach` loop
            if step.foreach:
                loop_collection = self._resolve_value(step.foreach, context)
                if not isinstance(loop_collection, list):
                    raise TypeError(f"Step '{step.id}': `foreach` value '{step.foreach}' did not resolve to a list.")
                
                step_outputs = []
                for item in loop_collection:
                    # Resolve parameters for this iteration
                    kwargs = {}
                    for param_name, binding in step.bind.items():
                        kwargs[param_name] = self._resolve_value(binding.value, context, item)

                    # Execute logic
                    try:
                        result = self._run_step_logic(step.id, step.tool_id, kwargs)
                        step_outputs.append(result)
                    except Exception as e:
                        print(f"      ERROR during execution of step '{step.id}' for item '{item}': {e}")
                        raise e 
                
                # Store the collected results
                if step.outputs:
                    output_name = next(iter(step.outputs.keys()))
                    context[step.id] = {output_name: step_outputs}
                    print(f"    -> Stored loop output '{step.id}.{output_name}'")

            else: # Single execution
                # Resolve parameters
                kwargs = {}
                for param_name, binding in step.bind.items():
                    kwargs[param_name] = self._resolve_value(binding.value, context)
                
                # Execute logic
                try:
                    result = self._run_step_logic(step.id, step.tool_id, kwargs)
                except Exception as e:
                    print(f"      ERROR during execution of step '{step.id}': {e}")
                    raise e

                # Store output
                if step.outputs:
                    output_name = next(iter(step.outputs.keys()))
                    context[step.id] = {output_name: result}
                    print(f"    -> Stored output '{step.id}.{output_name}'")

        print("Workflow execution finished.")
        return context