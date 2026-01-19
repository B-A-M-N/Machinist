from __future__ import annotations

import ast
import json
import re
import textwrap
from typing import Any, Dict, Optional, Tuple

import regex


def strip_code_fences(text: str) -> str:
    """
    Strip Markdown code fences while preserving the inner code. If no fences are
    present, return the text unchanged.
    """
    # This regex will find all content inside ```...``` blocks.
    # It handles optional language names after the opening fence.
    pattern = r"```(?:\w+\n)?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        # Join all found code blocks, stripping leading/trailing whitespace from each.
        return "\n".join(match.strip() for match in matches)
    # If no fences are found, return the original text.
    return text


def extract_brace_block(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def literal_eval_safe(text: str) -> Any | None:
    try:
        return ast.literal_eval(text)
    except Exception:
        return None


def json_coerce(raw: str) -> Dict[str, Any]:
    """
    Strictly parse a single JSON object from a fenced block.
    Allows ```json, ```python, or just ``` fences.
    """
    print(f"--- RAW_INPUT_TO_JSON_COERCE ---\n{raw}\n---------------------------------")

    # Regex to find a JSON block inside triple backticks, with an optional language identifier
    _JSON_FENCE_RE = re.compile(r"```(?:\w+)?\s*(\{[\s\S]*?\})\s*```", re.DOTALL)
    matches = _JSON_FENCE_RE.findall(raw)

    if len(matches) == 0:
        # Fallback: try to find a JSON object without fences if it looks valid
        try:
             # Try to extract just the first JSON-like block if fences are missing
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                 potential_json = raw[start : end + 1]
                 # Verify it's valid JSON before accepting it
                 json.loads(potential_json)
                 matches = [potential_json]
        except:
             pass

    if len(matches) != 1:
        # One last desperate attempt: if there are multiple blocks, pick the largest one that parses
        if len(matches) > 1:
            best_match = None
            max_len = -1
            for m in matches:
                try:
                    json.loads(m)
                    if len(m) > max_len:
                        max_len = len(m)
                        best_match = m
                except:
                    continue
            if best_match:
                matches = [best_match]
        
        if len(matches) != 1:
             raise ValueError(f"Expected exactly 1 JSON block, found {len(matches)}.")
    
    json_string = matches[0]

    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in fenced block: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object/dict.")

    print(f"--- CANDIDATE ---\n{json.dumps(data, indent=2)}\n-----------------")
    return data


def extract_code_block(text: str, label: str = "code") -> str | None:
    """
    Extract a fenced code block.
    - Prefer an explicitly labelled fence (```<label>).
    - For tests, if no label is present, prefer a fence that contains a pytest-style test function.
    - Otherwise fall back to the first fenced block.
    """
    # First try to find a labelled block.
    pattern = rf"```{{label}}\n?([^`]*)"
    m = regex.search(pattern, text, flags=regex.DOTALL | regex.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Collect all fenced blocks.
    blocks = [m.group(1).strip() for m in regex.finditer(r"```(?:\w+)?\n?(.*?)```", text, flags=regex.DOTALL)]
    if not blocks:
        return None

    # For tests, prefer a block that actually looks like tests.
    if label.lower() == "tests":
        for block in blocks:
            if "def test_" in block:
                return block

    # Otherwise return the first block.
    return blocks[0]


def coerce_code_tests(raw: str) -> Tuple[str | None, str | None]:
    data = json_coerce(raw)
    code = data.get("code")
    tests = data.get("tests")
    return _coerce_to_str(code), _coerce_to_str(tests)


def _coerce_to_str(obj: Any) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        parts = [v for v in obj.values() if isinstance(v, str)]
        if parts:
            return "\n".join(parts)
    if isinstance(obj, list):
        parts = [str(x) for x in obj]
        return "\n".join(parts)
    return str(obj)

def parse_json_safely(raw: str) -> Dict:
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        fence = "```"
        # Remove opening fence line
        text = "\n".join(text.splitlines()[1:])
        # Drop trailing fence if present
        if text.rstrip().endswith(fence):
            text = "\n".join(text.splitlines()[:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first/last brace block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        # Fallback: try Python literal eval and normalize
        try:
            literal = ast.literal_eval(text)
            return normalize_literal(literal)
        except Exception:
            raise ValueError(f"Failed to parse JSON from LLM output:\n{raw}")

def normalize_literal(obj):
    if isinstance(obj, dict):
        return {k: normalize_literal(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize_literal(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, type):
        return obj.__name__
    return str(obj)

def strip_code_blocks(text: str) -> str:
    """
    Strip Markdown code fences while preserving the inner code. If no fences are
    present, or if the content within them is empty, return the original text.
    """
    # This regex will find all content inside ```...``` blocks.
    # It handles optional language names after the opening fence.
    pattern = r"```(?:\w+\n)?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        result = "\n".join(match.strip() for match in matches)
        if result:
            return result

    pattern = r"\s*\[PYTHON\](.*?)[\[\/\\]PYTHON]"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        result = "\n".join(match.strip() for match in matches)
        if result:
            return result
    # If no fences are found, or if the content inside is empty, return original text.
    return text

def coerce_code_str(obj) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        parts = [v for v in obj.values() if isinstance(v, str)]
        if parts:
            return "\n".join(parts)
    return str(obj)

def normalize_snippet(raw: Optional[str]) -> str:
    if raw is None:
        return ""
    stripped = strip_code_blocks(raw)
    if stripped is None:
        stripped = raw
    return textwrap.dedent(stripped).strip()

def extract_python_code(text: str) -> str:
    """
    Extracts Python code from a string that might include markdown fences
    and conversational text. It prioritizes fenced code blocks.
    Handles double-fencing artifacts.
    """
    # Find all fenced code blocks
    # We use a greedy match for the content to handle nested backticks if possible, 
    # but non-greedy is safer for multiple blocks.
    # Let's try to find standard blocks first.
    pattern = r"```(?:python\w*)?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    
    if len(matches) == 0:
         # If no markdown fences are found, assume the text might be a mix of
        # a preamble and code.
        lines = text.strip().split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            # A line is considered code if it starts with a common Python keyword
            # or is indented. This is a heuristic.
            is_code_like = line.strip().startswith(('import ', 'from ', 'def ', '@', 'class ')) or (in_code and (line.startswith(' ') or line.strip() == ''))
            
            if is_code_like and not in_code:
                # Start of a code block
                in_code = True
            
            if in_code:
                code_lines.append(line)
                
        if code_lines:
            return '\n'.join(code_lines).strip()
        
        # If all else fails, return the original text, as it might just be code.
        return text.strip()

    # We have matches.
    candidate = matches[0].strip()
    
    # Check for double fencing (e.g. the content itself starts with ```python)
    if candidate.startswith("```"):
        return extract_python_code(candidate)

    # If multiple blocks, some might be explanations or separate files.
    # We prefer the one that looks like code (has imports or defs).
    best_candidate = candidate
    if len(matches) > 1:
        # Heuristic: pick the longest block that looks like python
        max_score = -1
        for m in matches:
            cleaned = m.strip()
            score = 0
            if "import " in cleaned: score += 1
            if "def " in cleaned: score += 2
            if "class " in cleaned: score += 2
            if len(cleaned) > 50: score += 1
            
            if score > max_score:
                max_score = score
                best_candidate = cleaned
    
    return best_candidate

def extract_json_block(text: str) -> str:
    """
    Extracts a JSON object string from a given text by finding the first '{' and last '}'.
    Raises ValueError if no valid JSON object is found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return text[start:end+1]

def extract_json_safely(text: str) -> Dict[str, Any]:
    """
    Attempts to extract and parse a JSON object from text, even if messy.
    """
    # 1. Try code fences first
    try:
        return json_coerce(text)
    except Exception:
        pass

    # 2. Try simple brace extraction
    try:
        block = extract_json_block(text)
        return json.loads(block)
    except Exception as e:
        raise ValueError(f"Failed to extract valid JSON: {e}") from e


def to_safe_module_name(name: str) -> str:
    """
    Convert a string to a safe, snake_case module name.
    """
    return re.sub(r"\W|^(?=\d)", "_", name).lower()


def parse_signature(signature: str) -> Dict[str, str]:
    """
    Parses a function signature string and returns a dictionary of parameter names to their type hints.
    """
    params = {}
    try:
        # Prepend 'def dummy' and append 'pass' to make it a valid function definition for AST parsing
        tree = ast.parse(f"def dummy({signature.strip().lstrip('def ').split('(', 1)[1].rsplit(')', 1)[0]}): pass")
        func_def = next((node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)), None)

        if func_def and func_def.args:
            for arg in func_def.args.args:
                param_name = arg.arg
                param_type = ast.unparse(arg.annotation) if arg.annotation else "Any"
                params[param_name] = param_type
            for arg in func_def.args.kwonlyargs:
                param_name = arg.arg
                param_type = ast.unparse(arg.annotation) if arg.annotation else "Any"
                params[param_name] = param_type
        return params
    except Exception:
        # Fallback for simpler parsing if AST fails
        param_pattern = re.compile(r"(\w+)(?::\s*([\w\.]+))?")
        match = re.search(r"\((.*?)\)", signature)
        if match:
            args_str = match.group(1)
            for arg_match in param_pattern.finditer(args_str):
                param_name = arg_match.group(1)
                param_type = arg_match.group(2) if arg_match.group(2) else "Any"
                params[param_name] = param_type
        return params

