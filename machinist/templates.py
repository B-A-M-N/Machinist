from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Literal, Union

# Avoid circular import by importing inside functions or using TYPE_CHECKING if used only for types.
# But here we need to instantiate it. 
# It seems registry does not import templates, so we are safe.
from .registry import ToolSpec

SideEffect = Literal["filesystem_read", "filesystem_write", "filesystem_delete", "network", "process"]
SemanticTag = Literal["pure", "idempotent", "safe_to_retry"]

@dataclass
class ParamSkeleton:
    name: str
    type: str
    description: str
    must_exist: bool = False
    must_not_exist: bool = False
    must_be: Literal["file", "directory"] | None = None

@dataclass
class PseudoSpecTemplate:
    """
    A template for guiding an LLM to generate a full, valid ToolSpec.
    It provides the core intent, constraints, and structure.
    """
    id: str
    intent: str
    description: str
    keywords: List[str]
    
    # Enhanced metadata for composition
    typed_outputs: Dict[str, str] = field(default_factory=dict) # e.g., {"files": "list[path]"}
    side_effects: List[SideEffect] = field(default_factory=list) # Existing, but now central for composition logic
    semantic_tags: List[SemanticTag] = field(default_factory=list) # e.g., ["pure", "idempotent"]
    
    # Function signature constraints
    param_skeletons: List[ParamSkeleton] = field(default_factory=list)
    return_type: str | None = None

    # Implementation constraints
    forbidden_verbs: List[str] = field(default_factory=list)
    required_verbs: List[str] = field(default_factory=list)
    allowed_imports: List[str] = field(default_factory=list)
    denied_imports: List[str] = field(default_factory=list)

    # Test generation constraints
    base_failure_modes: List[Dict[str, Any]] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list) # e.g., "src_exists: false", "dst_exists: true"

    @classmethod
    def from_tool_spec(cls, tool_spec: Any) -> PseudoSpecTemplate:
        """
        Converts a ToolSpec into a PseudoSpecTemplate.
        """
        param_skeletons = []
        # Attempt to parse signature to get parameter names and types more accurately
        try:
            from machinist.parsing import parse_signature
            sig_params = parse_signature(tool_spec.signature)
            for param_name, param_type in sig_params.items():
                param_skeletons.append(ParamSkeleton(
                    name=param_name,
                    type=param_type, # Use parsed type
                    description=tool_spec.inputs.get(param_name, "") # Get description from inputs
                ))
        except Exception:
            # Fallback if signature parsing fails or ToolSpec doesn't have a parseable signature
            for param_name, description in tool_spec.inputs.items():
                param_skeletons.append(ParamSkeleton(name=param_name, type="str", description=description)) # Default to str

        return cls(
            id=tool_spec.name,
            intent=tool_spec.name,
            description=tool_spec.docstring,
            keywords=[], # Keywords are not in ToolSpec
            typed_outputs=tool_spec.outputs,
            side_effects=[], # Side effects are not in ToolSpec
            semantic_tags=[], # Semantic tags are not in ToolSpec
            param_skeletons=param_skeletons,
            return_type="str" if tool_spec.outputs else "None", # Basic inference
            forbidden_verbs=[], # Not in ToolSpec
            required_verbs=[], # Not in ToolSpec
            allowed_imports=tool_spec.imports, # Use imports from ToolSpec
            denied_imports=[], # Not in ToolSpec
            base_failure_modes=tool_spec.failure_modes, # Use failure modes from ToolSpec
            postconditions=[], # Not in ToolSpec
        )



def to_ollama_tool_schema(template: PseudoSpecTemplate) -> Dict[str, Any]:
    """
    Converts a PseudoSpecTemplate into the JSON schema format expected by Ollama's tool-calling API.
    """
    properties = {}
    required = []
    
    # Simple type mapping from Python types to JSON schema types
    type_map = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
    }

    for param in template.param_skeletons:
        # For now, we assume params are required unless they have a default value in a real signature.
        # ParamSkeleton doesn't track defaults yet, so we'll treat them all as required.
        required.append(param.name)
        properties[param.name] = {
            "type": type_map.get(param.type, "string"), # Default to string if type is unknown
            "description": param.description
        }

    return {
        "type": "function",
        "function": {
            "name": template.intent, # Use the intent as the function name for the LLM
            "description": template.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }
    }


# --- Composition Pseudo-Specs ---

@dataclass
class StepBinding:
    # A single binding, value can be a direct input, or reference to another step's output
    value: str # e.g., "$root_dir", "join($dst_dir, basename($item))"

@dataclass
class CompositionStep:
    id: str
    tool_id: str # References a PseudoSpecTemplate.id or a registered ToolSpec.name
    bind: Dict[str, StepBinding] = field(default_factory=dict) # Param name to StepBinding
    foreach: str | None = None # e.g., "$find.files"
    if_condition: str | None = None # e.g., "$file_exists" or "$count > 5"
    outputs: Dict[str, str] = field(default_factory=dict) # Name output for later steps, e.g., {"files": "list[path]"}
    # The 'then' part is a bit tricky for a simple dataclass, might be another CompositionStep
    # For now, let's keep it simple and assume 'then' means direct execution of another tool.
    # It might be a recursive definition of CompositionStep or just a direct tool call.
    # Let's use a simple tool_id reference for 'then' for now.
    then_tool_id: str | None = None
    then_bind: Dict[str, StepBinding] = field(default_factory=dict)

@dataclass
class FailurePolicy:
    on_step: str # Step ID
    action: Literal["stop", "continue", "retry"]

@dataclass
class CompositionSpec:
    """
    A pseudo-spec for guiding an LLM to generate or execute a multi-tool workflow.
    """
    pipeline_id: str
    description: str
    inputs: Dict[str, str] = field(default_factory=dict) # Global pipeline inputs, e.g., {"root_dir": "path"}
    steps: List[CompositionStep] = field(default_factory=list)
    global_postconditions: List[str] = field(default_factory=list)
    failure_policy: List[FailurePolicy] = field(default_factory=list)
    semantic_tags: List[SemanticTag] = field(default_factory=list)


# --- Template Registry ---

TEMPLATE_REGISTRY: Dict[str, PseudoSpecTemplate] = {}
COMPOSITION_REGISTRY: Dict[str, CompositionSpec] = {} # New registry for composition specs

def register_template(template: PseudoSpecTemplate):
    TEMPLATE_REGISTRY[template.id] = template

def register_composition_spec(comp_spec: CompositionSpec):
    COMPOSITION_REGISTRY[comp_spec.pipeline_id] = comp_spec


# --- Filesystem Templates ---

# Updated templates with new fields
register_template(PseudoSpecTemplate(
    id="fs.copy.v1",
    intent="copy",
    description="A tool that copies a file from a source to a destination.",
    keywords=["copy", "duplicate", "clone"],
    typed_outputs={}, # No specific return value to type
    side_effects=["filesystem_read", "filesystem_write"],
    semantic_tags=["idempotent"],
    param_skeletons=[
        ParamSkeleton(name="src_path", type="str", description="The path to the source file.", must_exist=True, must_be="file"),
        ParamSkeleton(name="dst_path", type="str", description="The path to the destination file.", must_not_exist=True),
    ],
    return_type="None",
    allowed_imports=["os", "shutil"],
    denied_imports=["subprocess"],
    forbidden_verbs=["move", "rename", "delete", "unlink", "remove"],
    required_verbs=["copy", "duplicate", "clone"],
    base_failure_modes=[
        {"exception": "FileNotFoundError", "reason": "The source file does not exist."},
        {"exception": "FileExistsError", "reason": "The destination file already exists."},
    ],
    postconditions=["src_exists: true", "dst_exists: true"],
))

register_template(PseudoSpecTemplate(
    id="fs.move.v1",
    intent="move",
    description="A tool that moves or renames a file.",
    keywords=["move", "rename"],
    typed_outputs={},
    side_effects=["filesystem_read", "filesystem_write", "filesystem_delete"],
    semantic_tags=[], # Not idempotent
    param_skeletons=[
        ParamSkeleton(name="src_path", type="str", description="The path to the source file.", must_exist=True, must_be="file"),
        ParamSkeleton(name="dst_path", type="str", description="The path to the destination.", must_not_exist=True),
    ],
    return_type="None",
    allowed_imports=["os", "shutil"],
    denied_imports=["subprocess"],
    forbidden_verbs=["copy", "duplicate", "delete", "unlink", "remove"],
    required_verbs=["move", "rename"],
    base_failure_modes=[
        {"exception": "FileNotFoundError", "reason": "The source file does not exist."},
        {"exception": "FileExistsError", "reason": "The destination file already exists."},
    ],
    postconditions=["src_exists: false", "dst_exists: true"],
))

register_template(PseudoSpecTemplate(
    id="fs.delete.v1",
    intent="delete",
    description="A tool that deletes a file.",
    keywords=["delete", "remove", "unlink"],
    typed_outputs={},
    side_effects=["filesystem_delete"],
    semantic_tags=["idempotent"], # Deleting a non-existent file can still be considered idempotent
    param_skeletons=[
        ParamSkeleton(name="path", type="str", description="The path to the file to delete.", must_exist=True, must_be="file"),
    ],
    return_type="None",
    allowed_imports=["os"],
    denied_imports=["subprocess", "shutil"],
    forbidden_verbs=["copy", "move", "rename"],
    required_verbs=["delete", "remove", "unlink"],
    base_failure_modes=[
        {"exception": "FileNotFoundError", "reason": "The file does not exist."},
        {"exception": "IsADirectoryError", "reason": "The path points to a directory, not a file to be deleted."},
    ],
    postconditions=["path_exists: false"],
))

register_template(PseudoSpecTemplate(
    id="fs.read.v1",
    intent="read",
    description="A tool that reads the content of a file.",
    keywords=["read", "get content", "open file"],
    typed_outputs={"content": "str"},
    side_effects=["filesystem_read"],
    semantic_tags=["pure", "idempotent"],
    param_skeletons=[
        ParamSkeleton(name="path", type="str", description="The path of the file to read.", must_exist=True, must_be="file"),
    ],
    return_type="str",
    allowed_imports=["os"],
    denied_imports=["subprocess", "shutil"],
    forbidden_verbs=[],
    required_verbs=["read", "open"],
    base_failure_modes=[
        {"exception": "FileNotFoundError", "reason": "The file does not exist."},
        {"exception": "IsADirectoryError", "reason": "The path points to a directory, not a file."},
    ],
    postconditions=["content_is_string: true"],
))

register_template(PseudoSpecTemplate(
    id="fs.search_files.v1",
    intent="search_files",
    description="A tool that searches for files matching a glob pattern.",
    keywords=["find", "search", "locate", "glob"],
    typed_outputs={"found_paths": "list[path]"},
    side_effects=["filesystem_read"],
    semantic_tags=["pure", "idempotent"],
    param_skeletons=[
        ParamSkeleton(name="root_dir", type="str", description="The directory to start the search from.", must_exist=True, must_be="directory"),
        ParamSkeleton(name="pattern", type="str", description="The glob pattern to match filenames against (e.g., '*.txt')."),
        ParamSkeleton(name="recursive", type="bool", description="If True, searches directories recursively.", must_exist=False),
    ],
    return_type="list[str]",
    allowed_imports=["os", "fnmatch", "glob"],
    denied_imports=["subprocess"],
    forbidden_verbs=[],
    required_verbs=["walk", "listdir", "glob", "fnmatch"],
    base_failure_modes=[
        {"exception": "FileNotFoundError", "reason": "The root directory does not exist."},
        {"exception": "NotADirectoryError", "reason": "The root path is not a directory."},
    ],
    postconditions=["return_is_list_of_strings: true"],
))

# --- Text Manipulation Templates ---

register_template(PseudoSpecTemplate(
    id="text.insert_line.v1",
    intent="insert_line",
    description="A tool that ensures a string has a specific line, often a newline.",
    keywords=["insert line", "add newline", "ensure newline"],
    typed_outputs={"text_with_newline": "str"},
    side_effects=[],
    semantic_tags=["pure", "idempotent"],
    param_skeletons=[
        ParamSkeleton(name="text", type="str", description="The input string."),
    ],
    return_type="str",
    allowed_imports=[],
    denied_imports=["os", "shutil"],
    forbidden_verbs=[],
    required_verbs=[],
    base_failure_modes=[
        {"exception": "TypeError", "reason": "The input is not a string."},
    ],
    postconditions=["return_is_string: true"],
))

register_template(PseudoSpecTemplate(
    id="fs.write.v1",
    intent="write",
    description="A tool that writes or overwrites content to a specific file path.",
    keywords=["edit", "write", "modify", "update file", "overwrite"],
    typed_outputs={},
    side_effects=["filesystem_write"],
    semantic_tags=[], # Not idempotent if content is different
    param_skeletons=[
        ParamSkeleton(name="file_path", type="str", description="The path to the file to be written.", must_exist=True, must_be="file"),
        ParamSkeleton(name="content", type="str", description="The new content to write to the file."),
    ],
    return_type="None",
    allowed_imports=["os"],
    denied_imports=["subprocess", "shutil"],
    forbidden_verbs=["copy", "move", "rename", "delete"],
    required_verbs=["write", "open"],
    base_failure_modes=[
        {"exception": "FileNotFoundError", "reason": "The file does not exist at the specified path."},
        {"exception": "IsADirectoryError", "reason": "The specified path is a directory, not a file."},
        {"exception": "PermissionError", "reason": "The user does not have permission to write to the file."},
    ],
    postconditions=["file_content_is_updated: true"],
))

# --- Example Composition Spec ---
register_composition_spec(CompositionSpec(
    pipeline_id="fs.find_and_copy_and_normalize_text.v1",
    description="Finds files, copies them to a destination, and ensures they end with a newline.",
    inputs={
        "root_dir": "path",
        "pattern": "glob",
        "dst_dir": "path"
    },
    steps=[
        CompositionStep(
            id="find",
            tool_id="fs.search_files.v1",
            bind={
                "root_dir": StepBinding(value="$root_dir"),
                "pattern": StepBinding(value="$pattern"),
                "recursive": StepBinding(value="true")
            },
            outputs={"files": "list[path]"}
        ),
        CompositionStep(
            id="copy_and_normalize",
            tool_id="fs.copy.v1", # The 'foreach' implies we need a way to wrap single-tool operations
            foreach="$find.files",
            bind={
                "src_path": StepBinding(value="$item"),
                "dst_path": StepBinding(value="join($dst_dir, basename($item))")
            },
            then_tool_id="text.insert_line.v1", # This might need to be more complex
            then_bind={
                "text": StepBinding(value="read_file($copy_and_normalize.dst_path)")
            }
            # This "then" structure is an oversimplification. Needs to be a list of steps or a proper sub-pipeline.
            # Will refine the CompositionStep definition if the LLM needs to generate complex 'then' blocks.
        )
        # The user's example had a 'normalize' step that read, inserted newline, and wrote.
        # This current data structure can't directly express the 'read_file(...); insert_newline(...); write_file(...)' sequence cleanly within one step's 'then'.
        # For now, I'll simplify the 'then' to just another tool_id for the first iteration.
        # If the LLM generates something complex, I'll refine `CompositionStep` to support sub-steps or a `workflow_id` for nested workflows.
    ],
    global_postconditions=[
        "all_files_in_dst_end_with_newline: true"
    ],
    failure_policy=[
        FailurePolicy(on_step="copy_and_normalize", action="stop")
    ],
    semantic_tags=[]
))



def select_template(goal: str) -> PseudoSpecTemplate | None:
    """
    Selects the most appropriate PseudoSpecTemplate based on the goal's keywords.
    """
    goal_lower = goal.lower()
    for template in TEMPLATE_REGISTRY.values():
        if any(keyword in goal_lower for keyword in template.keywords):
            return template
    return None

def select_composition_spec(goal: str) -> CompositionSpec | None:
    """
    Selects a CompositionSpec based on the goal's intent.
    This will likely evolve to be more sophisticated (e.g., embedding similarity).
    For now, a simple keyword match for specific known pipelines.
    """
    goal_lower = goal.lower()
    for comp_spec in COMPOSITION_REGISTRY.values():
        # This is a very simplistic matching. Needs to be improved significantly.
        if comp_spec.pipeline_id in goal_lower or comp_spec.description.lower() in goal_lower:
            return comp_spec
    return None


def spec_from_fg_skeleton(skeleton: Dict[str, Any]) -> ToolSpec:
    """
    Converts a tool_spec skeleton from FunctionGemma into a proper ToolSpec object.
    """
    name = skeleton.get("name", "unnamed_tool")
    # Sanitize name to be a valid python identifier
    name = name.replace(".", "_").replace("-", "_")
    
    description = skeleton.get("description", "")
    
    # Build signature and inputs
    params = skeleton.get("parameters", {}).get("properties", {})
    required_params = skeleton.get("parameters", {}).get("required", [])
    
    param_list = []
    inputs = {}
    for param_name, param_details in params.items():
        # A simple mapping from JSON schema type to Python type hint
        type_map = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
        }
        py_type = type_map.get(param_details.get("type"), "Any")
        param_list.append(f"{param_name}: {py_type}")
        inputs[param_name] = param_details.get("description", "")

    # Build return type
    returns_info = skeleton.get("returns", {})
    return_type_str = type_map.get(returns_info.get("type"), "None")
    
    signature = f"def {name}({', '.join(param_list)}) -> {return_type_str}:"
    
    # Build outputs
    outputs = {"return_value": returns_info.get("description", "")} if return_type_str != "None" else {}

    # For now, imports and failure modes will be empty, as FunctionGemma doesn't propose these.
    # The `reconcile_spec_from_impl_ast` step will have to add them later.
    return ToolSpec(
        name=name,
        signature=signature,
        docstring=description, # The top-level description serves as the docstring
        imports=[],
        inputs=inputs,
        outputs=outputs,
        failure_modes=[],
        deterministic=True # Default to True, side-effect analysis will correct this later
    )