from __future__ import annotations
import ast
from typing import List, Set, Tuple
from .registry import ToolSpec

class ReconcileVisitor(ast.NodeVisitor):
    def __init__(self):
        self.raised_exceptions = set()
        self.imports = set()

    def visit_Raise(self, node):
        if isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name):
                self.raised_exceptions.add(node.exc.func.id)
        elif isinstance(node.exc, ast.Name):
            self.raised_exceptions.add(node.exc.id)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module.split('.')[0])
        self.generic_visit(node)

def reconcile_spec_from_impl_ast(spec: ToolSpec, code: str) -> Tuple[ToolSpec, bool]:
    tree = ast.parse(code)
    visitor = ReconcileVisitor()
    visitor.visit(tree)

    changed = False
    
    # Reconcile imports
    spec_imports = set(spec.imports)
    new_imports = visitor.imports - spec_imports
    if new_imports:
        spec.imports.extend(list(new_imports))
        changed = True

    # Reconcile exceptions
    spec_exceptions = {fm.get("exception") for fm in spec.failure_modes}
    new_exceptions = visitor.raised_exceptions - spec_exceptions
    
    allowed_new_exceptions = {"ValueError", "TypeError", "FileExistsError", "PermissionError", "OSError"}
    
    for exc in new_exceptions:
        if exc in allowed_new_exceptions:
            spec.failure_modes.append({"exception": exc, "reason": "Inferred from implementation."})
            changed = True
        else:
            print(f"Warning: Implementation raises a non-allowed exception: {exc}")

    return spec, changed


class CodeVisitor(ast.NodeVisitor):
    """
    An AST visitor that collects defined names and used names (variables),
    while being aware of scopes and ignoring type annotations.
    """

    def __init__(self):
        # Initialize with Python's built-in functions
        self.defined_names: Set[str] = set(dir(__import__("builtins")))
        self.used_names: Set[str] = set()
        # Stack to keep track of names defined in the current scope
        self._scope_stack: List[Set[str]] = [self.defined_names]

    def _is_defined(self, name: str) -> bool:
        """Check if a name is defined in any of the current scopes."""
        for scope in reversed(self._scope_stack):
            if name in scope:
                return True
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # The function name itself is defined in the outer scope
        self._scope_stack[-1].add(node.name)
        
        # Start a new scope for the function's body
        function_scope = set()

        # Arguments are defined in this new scope
        for arg in node.args.args:
            function_scope.add(arg.arg)
        if node.args.vararg:
            function_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            function_scope.add(node.args.kwarg.arg)

        # Push the new scope onto the stack
        self._scope_stack.append(function_scope)

        # Visit the function body, but DO NOT visit arg annotations
        for item in node.body:
            self.visit(item)
            
        # Pop the function's scope
        self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        self._scope_stack[-1].add(node.name)
        # Process decorators and base classes in the current scope
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        
        # Everything inside the class is in a new scope
        class_scope = set()
        self._scope_stack.append(class_scope)
        for item in node.body:
            self.visit(item)
        self._scope_stack.pop()

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            # If a name is loaded, check if it's been defined in any scope
            if not self._is_defined(node.id):
                self.used_names.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            # If a name is stored/deleted, it's now defined in the current scope
            self._scope_stack[-1].add(node.id)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._scope_stack[-1].add(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            self._scope_stack[-1].add(alias.asname or alias.name)

    def visit_Global(self, node: ast.Global):
        # Add global names to the current scope
        for name in node.names:
            self._scope_stack[-1].add(name)

    def visit_Nonlocal(self, node: ast.Nonlocal):
        # Add nonlocal names to the current scope
        for name in node.names:
            self._scope_stack[-1].add(name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self._scope_stack[-1].add(node.name)
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        for item in node.items:
            if item.optional_vars:
                self.visit(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        for item in node.items:
            if item.optional_vars:
                self.visit(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    # This method is key to NOT treating type hints as used variables
    def visit_AnnAssign(self, node: ast.AnnAssign):
        # Visit the value that is being assigned, but NOT the annotation
        if node.value:
            self.visit(node.value)
        # The target itself is a definition, so visit it to add to defined_names
        self.visit(node.target)

    def _visit_comp(self, node):
        # Create a new scope for the comprehension
        comp_scope = set()
        self._scope_stack.append(comp_scope)
        
        # Visit generators first to define variables (e.g. 'for i in ...')
        for generator in node.generators:
            self.visit(generator)
            
        # Visit the element/key/value expression which uses the variables
        if hasattr(node, 'elt'):
            self.visit(node.elt)
        elif hasattr(node, 'key'):
            self.visit(node.key)
            self.visit(node.value)
            
        self._scope_stack.pop()

    def visit_ListComp(self, node): self._visit_comp(node)
    def visit_SetComp(self, node): self._visit_comp(node)
    def visit_GeneratorExp(self, node): self._visit_comp(node)
    def visit_DictComp(self, node): self._visit_comp(node)


def validate_code_ast(
    code: str,
    declared_imports: List[str],
    *,
    is_test: bool = False,
    module_under_test: str | None = None,
) -> List[str]:
    """
    Performs static analysis on a string of Python code to find common errors
    that LLMs make, like using modules without importing them or hallucinating functions.
    """
    errors = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        errors.append(f"SyntaxError during static analysis: {e}")
        return errors

    # 1. Check if the code's imports are a subset of the declared imports + allowlist
    actual_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                actual_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                actual_imports.add(node.module.split('.')[0])
    
    if is_test:
        allowed_imports = {"pytest", "pathlib", "unittest", "os", "re", "sys", "io", "subprocess"}
        if module_under_test:
            allowed_imports.add(module_under_test)
    else:
        allowed_imports = set(declared_imports)
        allowed_imports.add("typing") # Always allow typing for implementation

    undeclared = actual_imports - allowed_imports
    if undeclared:
        errors.append(
            f"The code imports modules that were not in the declaration allowlist: {sorted(list(undeclared))}."
        )

    # 2. Check for undefined names (potential NameErrors)
    visitor = CodeVisitor()
    visitor.visit(tree)
    
    undefined_names = visitor.used_names
    
    # Filter out names that are actually modules from allowed imports
    truly_undefined = {
        name for name in undefined_names 
        if name not in allowed_imports and name not in declared_imports
    }
    
    if truly_undefined:
        errors.append(
            f"The code appears to use undefined names: {sorted(list(truly_undefined))}. "
            "This may be due to a hallucinated function or a missing import."
        )

    return errors
