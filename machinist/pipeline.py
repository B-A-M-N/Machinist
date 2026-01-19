from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, List

from .artifacts import Artifacts
from .autofix import add_missing_imports, remove_unused_typing_imports
from .config import MachinistConfig
from .llm.base import LLMClient
from .llm_interface import LLMInterface
from .registry import ToolMetadata, ToolRegistry, ToolSpec
from .sandbox import SandboxPolicy
from .static_analysis import validate_code_ast, reconcile_spec_from_impl_ast
from .validation import Validation, validate_spec_against_template, validate_impl_against_template
from .validator import ValidationRunner, ValidationResult
from .parsing import extract_python_code, to_safe_module_name
from .test_skeleton import build_pytest_skeleton, reject_forbidden_test_patterns
from .templates import PseudoSpecTemplate, CompositionSpec
from .auto_tool_creator import AutoToolCreator # Import AutoToolCreator


class MachinistPipeline:
    def __init__(
        self,
        spec_llm: LLMClient,
        impl_llm: LLMClient,
        test_llm: LLMClient,
        fg_llm: LLMClient, # NEW: FunctionGemma LLM client
        embed_llm: LLMClient, # NEW: Embedding client (e.g. nomic-embed-text)
        registry: ToolRegistry,
        sandbox_policy: SandboxPolicy | None = None,
        config: MachinistConfig | None = None,
        validator: ValidationRunner | None = None,
    ) -> None:
        self.embed_llm = embed_llm
        self.llm_interface = LLMInterface(
            spec_llm=spec_llm,
            impl_llm=impl_llm,
            test_llm=test_llm,
            fg_llm=fg_llm, # NEW: Pass fg_llm to LLMInterface
            registry=registry,
        )
        self.registry = registry
        self.config = config or MachinistConfig()
        self.validator = validator or ValidationRunner(sandbox_policy or SandboxPolicy())
        self.artifacts = Artifacts(llm_interface=self.llm_interface, config=self.config)
        self.validation = Validation(
            llm_interface=self.llm_interface,
            validator=self.validator,
            config=self.config,
        )
        self.auto_tool_creator = AutoToolCreator(self, registry, self.llm_interface) # Initialize AutoToolCreator

    # ... existing methods ...

    def create_composite_tool(
        self,
        goal: str,
        available_tools: List[PseudoSpecTemplate],
        composition_spec: CompositionSpec | None = None,
        available_tool_ids_for_rules_str: str | None = None,
        stream: bool = True,
        on_token=None,
    ) -> ToolMetadata:
        """
        Creates a new, single tool by composing existing tools based on a goal.
        """
        return self.auto_tool_creator.create_tool_from_composition_spec(
            goal, available_tools, composition_spec, available_tool_ids_for_rules_str, stream, on_token
        )


    def _parse_signature_from_spec(self, spec: ToolSpec) -> ast.FunctionDef:
        src = spec.signature.strip()
        if not src.endswith(":"):
            src += ":"
        mod = ast.parse(src + "\n    pass\n")
        fn = next((n for n in mod.body if isinstance(n, ast.FunctionDef)), None)
        if fn is None:
            raise ValueError(f"Could not parse spec.signature: {spec.signature!r}")
        return fn

    def _normalize_arglist(self, fn: ast.FunctionDef) -> tuple[list[str], list[str]]:
        pos = [a.arg for a in fn.args.posonlyargs] + [a.arg for a in fn.args.args]
        kwonly = [a.arg for a in fn.args.kwonlyargs]
        return pos, kwonly

    def _validate_implementation_signature(self, spec: ToolSpec, code: str) -> None:
        try:
            impl_tree = ast.parse(code)
            impl_fn = next((n for n in impl_tree.body if isinstance(n, ast.FunctionDef)), None)
            if impl_fn is None:
                raise ValueError("No function definition found in implementation code.")

            if impl_fn.name != spec.name:
                raise ValueError(f"Implementation name '{impl_fn.name}' != spec name '{spec.name}'.")

            spec_fn = self._parse_signature_from_spec(spec)
            spec_pos, spec_kw = self._normalize_arglist(spec_fn)
            impl_pos, impl_kw = self._normalize_arglist(impl_fn)

            if spec_pos != impl_pos or spec_kw != impl_kw:
                raise ValueError(
                    f"Signature mismatch.\n"
                    f"Spec pos={spec_pos}, kwonly={spec_kw}\n"
                    f"Impl pos={impl_pos}, kwonly={impl_kw}"
                )
            
            spec_has_kwonly = bool(spec_fn.args.kwonlyargs)
            impl_has_kwonly = bool(impl_fn.args.kwonlyargs)
            if spec_has_kwonly != impl_has_kwonly:
                raise ValueError("kwonly mismatch: spec requires '*' keyword-only args but impl does not (or vice versa).")

        except Exception as e:
            raise ValueError(f"AST signature validation failed: {e}") from e

    def generate_spec(self, goal: str, *, stream: bool = True, on_token=None) -> ToolSpec:
        return self.llm_interface.generate_spec(goal, stream=stream, on_token=on_token)

    def generate_spec_from_template(self, goal: str, template: PseudoSpecTemplate, *, stream: bool = True, on_token=None) -> ToolSpec:
        spec = self.llm_interface.generate_spec_from_template(goal, template, stream=stream, on_token=on_token)
        validate_spec_against_template(spec, template)
        return spec

    def generate_composition_spec(self, goal: str, available_tools: List[PseudoSpecTemplate], *, stream: bool = True, on_token=None, available_tool_ids_for_rules_str: str | None = None) -> CompositionSpec:
        """Generates a CompositionSpec for a complex goal."""
        return self.llm_interface.generate_composition_spec(goal, available_tools, stream=stream, on_token=on_token, available_tool_ids_for_rules_str=available_tool_ids_for_rules_str)

    def generate_implementation(self, spec: ToolSpec, *, template: PseudoSpecTemplate | None = None, stream: bool = True, on_token=None, max_attempts: int = 3) -> Tuple[ToolSpec, str, bool]:
        error = None
        error_feedback = None
        for i in range(max_attempts):
            if error:
                print(f"Implementation generation failed (attempt {i+1}/{max_attempts}): {error}")
                error_feedback = f"\nYour previous attempt failed with the following error:\n{error}\nPlease fix the error and provide the corrected implementation."

            raw_code = self.llm_interface.generate_implementation(
                spec, stream=(stream and i==0), on_token=on_token, error_feedback=error_feedback
            )
            
            try:
                clean_code = extract_python_code(raw_code)
                if not clean_code.strip():
                    raise ValueError("Implementation output must be a single python code block (no JSON).")

                fixed_code = remove_unused_typing_imports(clean_code)
                fixed_code = add_missing_imports(fixed_code)
                
                ast_errors = validate_code_ast(fixed_code, spec.imports, is_test=False)
                if ast_errors:
                    raise ValueError(f"Static analysis of implementation failed: {', '.join(ast_errors)}")
                
                if template:
                    validate_impl_against_template(fixed_code, template)

                updated_spec, spec_changed = reconcile_spec_from_impl_ast(spec, fixed_code)
                self._validate_implementation_signature(updated_spec, fixed_code)
                return updated_spec, fixed_code, spec_changed

            except ValueError as e:
                error = e
        
        raise ValueError(f"Failed to generate a valid implementation after {max_attempts} attempts. Last error: {error}")

    def generate_tests(
        self, spec: ToolSpec, *, template: PseudoSpecTemplate | None = None, stream: bool = True, on_token=None, strict: bool = False
    ) -> str:
        safe_name = to_safe_module_name(spec.name)
        failure_excs = []
        if template:
            for fm in (template.base_failure_modes or []):
                exc = fm.get("exception")
                if isinstance(exc, str) and exc.strip():
                    failure_excs.append(exc.strip())
        else:
            for fm in (spec.failure_modes or []):
                exc = getattr(fm, "exception", None) if not isinstance(fm, dict) else fm.get("exception")
                if isinstance(exc, str) and exc.strip():
                    failure_excs.append(exc.strip())

        skeleton = build_pytest_skeleton(
            module_name=safe_name,
            func_name=spec.name,
            failure_exceptions=list(set(failure_excs)),
            needs_tmp_path=True,
            intent=template.intent if template else None, # Pass intent to skeleton builder
        )

        raw_tests = self.llm_interface.generate_tests(
            spec,
            stream=stream,
            on_token=on_token,
            strict=strict,
            safe_name=safe_name,
            test_skeleton=skeleton.code,
        )

        clean_tests = extract_python_code(raw_tests)

        # FIX: Add a hard guard that rejects curly-brace wrapped tests
        if clean_tests.lstrip().startswith("{") or clean_tests.rstrip().endswith("}"):
            raise ValueError("Generated test code is wrapped in curly braces, which is invalid.")

        if template and template.intent == "copy" and "assert not src.exists()" in clean_tests:
            raise ValueError("Semantic contradiction: Test for a copy tool asserts that the source file is deleted.")

        structural_errors = reject_forbidden_test_patterns(clean_tests)
        if structural_errors:
            raise ValueError("Static structural validation failed: " + ", ".join(structural_errors))

        required_import = f"from {safe_name} import {spec.name}"
        if required_import not in clean_tests:
            raise ValueError(f"Tests must contain the exact import: {required_import}")

        spec_fn = self._parse_signature_from_spec(spec)
        spec_pos, spec_kw = self._normalize_arglist(spec_fn)
        
        tree = ast.parse(clean_tests)
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == spec.name:
                calls.append(node)

        if not calls:
            raise ValueError(f"No calls to the function '{spec.name}' found in the generated tests.")

        for call in calls:
            if len(call.args) > len(spec_pos):
                 raise ValueError(
                    f"Test calls {spec.name} with {len(call.args)} positional args, but spec expects {len(spec_pos)}."
                )
            
            call_kw_names = {kw.arg for kw in call.keywords}
            allowed_kw_names = set(spec_pos + spec_kw)
            
            extra_kwargs = call_kw_names - allowed_kw_names
            if extra_kwargs:
                raise ValueError(
                    f"Test calls {spec.name} with unexpected keyword arguments: {extra_kwargs}"
                )

        fixed_tests = remove_unused_typing_imports(clean_tests)
        fixed_tests = add_missing_imports(fixed_tests)

        ast_errors = validate_code_ast(
            fixed_tests,
            spec.imports,
            is_test=True,
            module_under_test=safe_name,
        )
        if ast_errors:
            error_str = ", ".join(ast_errors)
            raise ValueError(f"Static analysis of tests failed: {error_str}")

        return fixed_tests

    def write_artifacts(self, spec: ToolSpec, code: str, tests: str) -> Tuple[Path, Path]:
        return self.artifacts.write_artifacts(spec, code, tests)

    def repair_and_validate(
        self,
        spec: ToolSpec,
        source_path: Path,
        tests_path: Path,
        initial_validation: ValidationResult,
        max_attempts: int = 3,
    ) -> Tuple[ValidationResult, str, str]:
        return self.validation.repair_and_validate(
            spec,
            source_path,
            tests_path,
            initial_validation,
            max_attempts,
        )

    def validate(
        self,
        source_path: Path,
        tests_path: Path,
        *, 
        stream: bool = True,
        on_output: callable | None = None,
        func_name: str | None = None,
    ) -> ValidationResult:
        return self.validation.validate(
            source_path,
            tests_path,
            stream=stream,
            on_output=on_output,
            func_name=func_name,
        )

    def promote(
        self,
        spec: ToolSpec,
        source_path: Path,
        tests_path: Path,
        validation: ValidationResult,
        template: PseudoSpecTemplate | None = None,
    ) -> ToolMetadata:
        source_code = source_path.read_text(encoding="utf-8")
        tool_id = self.registry.resolve_id(spec, source_code)
        results_path = tests_path.with_suffix(".results.json")
        results_path.write_text(self._serialize_results(validation), encoding="utf-8")

        meta = ToolMetadata(
            tool_id=tool_id,
            version="0.1.0",
            created_at=datetime.utcnow().isoformat(),
            spec=spec,
            source_path=source_path,
            tests_path=tests_path,
            test_results_path=results_path,
            dependencies={"python": ">=3.10"},
            security_policy="bwrap-no-net",
            capability_profile="no-network; scratch-only",
            model=self.llm_interface.impl_llm.model_name(),
            template_id=template.id if template else None,
        )
        self.registry.register(meta)
        return meta

    def _serialize_results(self, validation: ValidationResult) -> str:
        payload = {
            "lint_ok": validation.lint_ok,
            "tests_ok": validation.tests_ok,
            "coverage_ok": validation.coverage_ok,
            "commands": {
                name: {
                    "returncode": res.returncode,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                }
                for name, res in validation.command_results.items()
            },
        }
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)
