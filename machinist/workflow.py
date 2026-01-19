from __future__ import annotations
from typing import Dict, Any, List
import os
import re

from .templates import CompositionSpec
from .registry import ToolRegistry

class WorkflowEngine:
    """
    Executes a CompositionSpec (a multi-tool workflow).
    """
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

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

            # 1. Find a concrete, executable tool for the step's abstract tool_id
            concrete_tool_ids = self.tool_registry.find_by_template_id(step.tool_id)
            
            # Fallback: try to find by tool name directly
            if not concrete_tool_ids:
                 all_tools = self.tool_registry.list_tools()
                 concrete_tool_ids = [t.tool_id for t in all_tools if t.spec.name == step.tool_id]

            if not concrete_tool_ids:
                raise RuntimeError(f"Step '{step.id}': No registered tool found for template/name '{step.tool_id}'")
            
            # For now, just use the first one found
            tool_id_to_run = concrete_tool_ids[0]
            executable_func = self.tool_registry.get_executable(tool_id_to_run)
            if not executable_func:
                raise RuntimeError(f"Step '{step.id}': Could not load executable for tool '{tool_id_to_run}'")

            # 2. Check for `foreach` loop
            if step.foreach:
                loop_collection = self._resolve_value(step.foreach, context)
                if not isinstance(loop_collection, list):
                    raise TypeError(f"Step '{step.id}': `foreach` value '{step.foreach}' did not resolve to a list.")
                
                step_outputs = []
                for item in loop_collection:
                    # 3. Resolve parameters for this iteration
                    kwargs = {}
                    for param_name, binding in step.bind.items():
                        kwargs[param_name] = self._resolve_value(binding.value, context, item)

                    # 4. Execute the tool
                    try:
                        print(f"    -> Calling {executable_func.__name__} with: {kwargs}")
                        result = executable_func(**kwargs)
                        step_outputs.append(result)
                    except Exception as e:
                        print(f"      ERROR during execution of step '{step.id}' for item '{item}': {e}")
                        # TODO: Implement failure policy
                        raise e # For now, fail fast
                
                # 5. Store the collected results of the loop
                if step.outputs:
                    output_name = next(iter(step.outputs.keys()))
                    context[step.id] = {output_name: step_outputs}
                    print(f"    -> Stored loop output '{step.id}.{output_name}'")

            else: # No `foreach`, single execution
                # 3. Resolve parameters
                kwargs = {}
                for param_name, binding in step.bind.items():
                    kwargs[param_name] = self._resolve_value(binding.value, context)
                
                # 4. Execute the tool
                try:
                    print(f"    -> Calling {executable_func.__name__} with: {kwargs}")
                    result = executable_func(**kwargs)
                except Exception as e:
                    print(f"      ERROR during execution of step '{step.id}': {e}")
                    # TODO: Implement failure policy
                    raise e

                # 5. Store output
                if step.outputs:
                    output_name = next(iter(step.outputs.keys()))
                    context[step.id] = {output_name: result}
                    print(f"    -> Stored output '{step.id}.{output_name}'")

        print("Workflow execution finished.")
        return context