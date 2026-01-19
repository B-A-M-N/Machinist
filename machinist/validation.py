from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import re
from typing import Dict, Tuple

from .config import MachinistConfig
from .autofix import add_missing_imports
from .llm import DEFAULT_SYSTEM_PROMPT
from .llm_interface import LLMInterface
from .parsing import extract_python_code
from .registry import ToolSpec
from .validator import ValidationResult, ValidationRunner


from .templates import PseudoSpecTemplate
from .registry import ToolSpec
import ast

def validate_spec_against_template(spec: ToolSpec, template: PseudoSpecTemplate):
    """
    Validates a generated ToolSpec against a PseudoSpecTemplate.
    Raises ValueError if a constraint is violated.
    """
    # Validate imports
    if not set(spec.imports).issubset(set(template.allowed_imports)):
        extra_imports = set(spec.imports) - set(template.allowed_imports)
        raise ValueError(f"Spec validation failed: Imports {extra_imports} are not allowed by the template.")

    # Validate failure modes
    required_exceptions = {fm['exception'] for fm in template.base_failure_modes}
    spec_exceptions = {fm['exception'] for fm in spec.failure_modes}
    if not required_exceptions.issubset(spec_exceptions):
        missing_exceptions = required_exceptions - spec_exceptions
        print(f"Warning: Spec validation check: Missing suggested failure modes for exceptions {missing_exceptions}. Continuing anyway.")

    # Validate signature parameters
    spec_params = set(spec.inputs.keys())
    template_params = {p.name for p in template.param_skeletons}
    if spec_params != template_params:
        print(f"Warning: Spec validation check: Input parameters {spec_params} do not match template parameters {template_params}. Continuing anyway.")

    # Validate forbidden verbs in docstring
    for verb in template.forbidden_verbs:
        if verb in spec.docstring.lower():
            raise ValueError(f"Spec validation failed: Docstring contains forbidden verb '{verb}'.")

def validate_impl_against_template(code: str, template: PseudoSpecTemplate):
    """
    Validates a generated implementation against a PseudoSpecTemplate using AST.
    Raises ValueError if a constraint is violated.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Implementation has a syntax error: {e}")

    for node in ast.walk(tree):
        # Check for denied imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in template.denied_imports:
                    raise ValueError(f"Implementation validation failed: Denied import '{alias.name}' found.")
        elif isinstance(node, ast.ImportFrom):
            if node.module in template.denied_imports:
                raise ValueError(f"Implementation validation failed: Denied import from '{node.module}' found.")

        # Check for forbidden function calls (basic check)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in template.forbidden_verbs:
                raise ValueError(f"Implementation validation failed: Forbidden function call '{node.func.id}' found.")
        # Check for forbidden attribute calls (e.g., os.remove)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in template.forbidden_verbs:
                # This is a simple check; a more robust check would verify the object `node.func.value` refers to.
                raise ValueError(f"Implementation validation failed: Forbidden function call '{node.func.attr}' found.")

class Validation:
    # ... (the rest of the original Validation class)

    def __init__(
        self,
        llm_interface: LLMInterface,
        validator: ValidationRunner,
        config: MachinistConfig,
    ):
        self.llm_interface = llm_interface
        self.validator = validator
        self.config = config

    def _extract_file_block(self, text: str, filename: str) -> tuple[str | None, tuple[int, int] | None]:
        """
        Extract a labeled file block:
          ---filename---
          ```<anything>
          ...code...
          ```
        Returns (code, (start,end) span of match) or (None, None)
        """
        marker = re.escape(filename)
        pat = re.compile(
            rf"---{marker}---\s*```[a-zA-Z0-9_\-\s]*\n(.*?)\n```",
            re.DOTALL,
        )
        m = pat.search(text)
        if not m:
            return None, None
        return m.group(1).strip(), m.span()

    def repair_and_validate(
        self,
        spec: ToolSpec,
        source_path: Path,
        tests_path: Path,
        initial_validation: ValidationResult,
        max_attempts: int = 3,
    ) -> Tuple[ValidationResult, str, str]:
        """
        If validation failed, ask the LLM to repair code/tests using an advanced, tiered strategy.
        Returns (final_validation, final_code, final_tests).
        """
        current_validation = initial_validation
        
        for attempt in range(1, max_attempts + 1):
            if current_validation.is_ok():
                print("\nAll validation issues appear to be fixed.")
                break

            print(f"\n--- Repair Attempt {attempt}/{max_attempts} ---")
            error_summary = self._summarize_errors(current_validation)
            extra_instructions = ""

            # Add a high-level instruction based on the failure type
            impl_only_repair = False
            if not current_validation.tests_ok and current_validation.lint_ok:
                impl_only_repair = True
                extra_instructions = (
                    "**REPAIR STRATEGY: IMPLEMENTATION-ONLY**\n"
                    "The tests are failing due to a logic error in the implementation.\n"
                    "You MUST NOT modify the test file.\n"
                    f"Provide a patch ONLY for the implementation file: `{source_path.name}`."
                )
            elif not current_validation.lint_ok:
                extra_instructions = (
                    "A syntax error was detected. You MUST fix the syntax error in the relevant file(s)."
                )
            elif not current_validation.tests_ok:
                extra_instructions = (
                    "Tests are failing. Analyze the test failures and correct the implementation or tests as needed."
                )
            elif not current_validation.coverage_ok:
                extra_instructions = (
                    "Code coverage is too low. Please add new tests or modify existing ones to cover more code paths."
                )

            # Build prompt: in impl-only mode, DO NOT include test file or format block for it
            if impl_only_repair:
                repair_prompt = self._build_impl_only_repair_prompt(spec, source_path, error_summary, extra_instructions)
            else:
                repair_prompt = self._build_general_repair_prompt(spec, source_path, tests_path, error_summary, extra_instructions)
            
            print(f"Asking model to generate fixes (attempt {attempt})...")
            
            # Choose which model to use for repair
            if not current_validation.tests_ok or not current_validation.coverage_ok:
                client = self.llm_interface.test_llm
            else:
                client = self.llm_interface.impl_llm

            llm_response = client.complete(
                DEFAULT_SYSTEM_PROMPT,
                repair_prompt,
                temperature=0.3,
                max_tokens=4000,
            )

            # Extract blocks
            new_code_impl, impl_span = self._extract_file_block(llm_response, source_path.name)
            new_code_tests, tests_span = self._extract_file_block(llm_response, tests_path.name)

            # Enforce "ONLY blocks" policy: nothing else allowed besides whitespace
            leftover = llm_response
            spans = [s for s in [impl_span, tests_span] if s]
            for start, end in sorted(spans, reverse=True):
                leftover = leftover[:start] + leftover[end:]
            if leftover.strip():
                print("Model output contained extra text outside code blocks. Rejecting response and retrying.")
                continue

            if not new_code_impl and not new_code_tests:
                print("Model returned no valid, labeled code blocks. Rejecting response and retrying.")
                continue

            if new_code_impl:
                fixed_impl = add_missing_imports(new_code_impl)
                source_path.write_text(fixed_impl, encoding="utf-8")
                print(f"Applied new implementation to {source_path.name}")

            if impl_only_repair and new_code_tests:
                print("Ignoring test file patch in implementation-only repair mode.")
            elif new_code_tests:
                # DO NOT autofix imports in tests here; too risky
                fixed_tests = new_code_tests

                # Hard guard: preserve import contract
                required_import = f"from {source_path.stem} import {spec.name}"
                if required_import not in fixed_tests:
                    print(f"Rejected patched tests: missing required import line: {required_import!r}")
                    continue

                tests_path.write_text(fixed_tests, encoding="utf-8")
                print(f"Applied new tests to {tests_path.name}")
            
            # Re-run validation
            print("\nRe-running validation on the patched code...")
            current_validation = self.validate(
                source_path, tests_path, stream=True,
                on_output=lambda name, chunk: print(chunk, end="", flush=True), func_name=spec.name
            )

            if not current_validation.is_ok() and attempt == max_attempts:
                print("\nValidation failed after all repair attempts.")


        final_code = source_path.read_text(encoding="utf-8")
        final_tests = tests_path.read_text(encoding="utf-8")
        return current_validation, final_code, final_tests

    def validate(
        self,
        source_path: Path,
        tests_path: Path,
        *,
        stream: bool = True,
        on_output: callable | None = None,
        func_name: str | None = None,
    ) -> ValidationResult:
        preflight_ok, preflight_results = self._preflight([source_path, tests_path])
        if not preflight_ok:
            return ValidationResult(
                lint_ok=False,
                tests_ok=False,
                coverage_ok=False,
                command_results=preflight_results,
            )

        result = self.validator.run(
            source_path,
            tests_path,
            coverage_threshold=self.config.coverage_threshold,
            stream=stream,
            on_output=on_output,
        )

        cov_res = result.command_results.get("coverage")
        if cov_res and ("module-not-imported" in cov_res.stderr or "No data was collected" in cov_res.stderr or cov_res.returncode != 0):
            result.coverage_ok = False
        return result

    def _summarize_errors(self, validation: ValidationResult) -> str:
        error_summary = []
        for name, result in validation.command_results.items():
            if result.returncode != 0:
                stdout = (result.stdout or "").strip()
                stderr = (result.stderr or "").strip()
                if stdout:
                    error_summary.append(f"""--- {name} stdout ---
{stdout}""")
                if stderr:
                    error_summary.append(f"""--- {name} stderr ---
{stderr}""")
        return "\n".join(error_summary)

    def _build_general_repair_prompt(self, spec: ToolSpec, source_path: Path, tests_path: Path, error_summary: str, extra_instructions: str = "") -> str:
        source_code = source_path.read_text()
        test_code = tests_path.read_text()
        
        instructions = (
            "You are a code repair agent. Your task is to fix the failing code based on the provided error summary.\n"
            "You MUST respond with ONLY the corrected code in the specified format.\n"
            "Do NOT include any text, explanation, or commentary before, after, or between the code blocks.\n"
            "If you do not need to change a file, do NOT include a block for it.\n\n"
            "The response format is:\n"
            f"---{source_path.name}---\n"
            "```python\n"
            "<full source code of the file, with corrections>\n"
            "```\n\n"
            f"---{tests_path.name}---\n"
            "```python\n"
            "<full source code of the test file, with corrections>\n"
            "```"
        )
        if extra_instructions:
            instructions += f"\n\nSpecific guidance:\n{extra_instructions}\n"

        return f"""{instructions}

Tool Specification (Goal):
```json
{spec.to_json()}
```

Current Implementation Code ({source_path.name}):
```python
{source_code}
```

Current Test Code ({tests_path.name}):
```python
{test_code}
```

Validation Error Summary:
```
{error_summary}
```

Please provide the corrected code for the necessary file(s) in the specified format.
"""

    def _build_impl_only_repair_prompt(self, spec: ToolSpec, source_path: Path, error_summary: str, extra_instructions: str = "") -> str:
        source_code = source_path.read_text()
        instructions = (
            "You are a code repair agent. Fix the failing implementation based on the error summary.\n"
            "You MUST respond with ONLY the corrected code in the specified format.\n"
            "Do NOT include any text before/after the code block.\n\n"
            "Response format:\n"
            f"---{source_path.name}---\n"
            "```python\n"
            "<full source code of the file, with corrections>\n"
            "```"
        )
        if extra_instructions:
            instructions += f"\n\nSpecific guidance:\n{extra_instructions}\n"

        return f"""{instructions}

Tool Specification (Goal):
```json
{spec.to_json()}
```

Current Implementation Code ({source_path.name}):
```python
{source_code}
```

Validation Error Summary:
```
{error_summary}
```
"""

    def _preflight(self, paths: list[Path]) -> Tuple[bool, Dict[str, subprocess.CompletedProcess]]:
        """
        Run host-side py_compile and black formatting before sandboxed validation.
        """
        results: Dict[str, subprocess.CompletedProcess] = {}
        black_cmd = [sys.executable, "-m", "black", "--quiet", *[str(p) for p in paths]]
        res = subprocess.run(black_cmd, capture_output=True, text=True)
        results["black"] = res
        if res.returncode != 0: return False, results
        for p in paths:
            cmd = [sys.executable, "-m", "py_compile", str(p)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            results[f"py_compile:{p.name}"] = res
            if res.returncode != 0: return False, results
        return True, results