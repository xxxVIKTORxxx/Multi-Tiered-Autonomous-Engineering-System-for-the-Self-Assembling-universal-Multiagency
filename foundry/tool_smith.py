import ast
import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple
from crewai.tools import BaseTool
from foundry.schemas import CustomToolSpec
from storage.custom_tools import save_custom_tool

# Dangerous modules and built-in calls blocked during AST security audit
FORBIDDEN_IMPORTS = {
    "subprocess",
    "shutil",
    "pty",
    "ctypes",
    "pickle",
    "marshal",
    "telnetlib",
    "ftplib",
}

FORBIDDEN_OS_ATTRS = {
    "system",
    "popen",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "execv",
    "execve",
    "remove",
    "unlink",
    "rmdir",
}

FORBIDDEN_BUILTINS = {"eval", "exec", "compile", "__import__"}


def audit_tool_code(spec: CustomToolSpec) -> Tuple[bool, List[str]]:
    """
    Performs static AST analysis on CustomToolSpec.python_code to verify:
      1. Valid Python syntax
      2. No dangerous imports or shell-execution primitives
      3. Presence of the target BaseTool subclass and a `_run` method
    """
    errors: List[str] = []

    try:
        tree = ast.parse(spec.python_code)
    except SyntaxError as exc:
        return False, [f"SyntaxError on line {exc.lineno}: {exc.msg}"]

    found_target_class = False
    found_run_method = False

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg in FORBIDDEN_IMPORTS:
                    errors.append(f"Forbidden import detected: '{alias.name}'")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in FORBIDDEN_IMPORTS:
                    errors.append(f"Forbidden import-from detected: '{node.module}'")

        # Check dangerous builtins (eval, exec, __import__)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
                errors.append(f"Forbidden builtin call detected: '{node.func.id}()'")
            elif isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in FORBIDDEN_OS_ATTRS
                ):
                    errors.append(f"Forbidden OS call detected: 'os.{node.func.attr}()'")

        # Check target class definition
        elif isinstance(node, ast.ClassDef) and node.name == spec.class_name:
            found_target_class = True
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_run":
                    found_run_method = True

    if not found_target_class:
        errors.append(f"Class '{spec.class_name}' not found in python_code.")
    elif not found_run_method:
        errors.append(f"Class '{spec.class_name}' is missing required '_run' method.")

    return len(errors) == 0, errors


def compile_and_verify_tool(spec: CustomToolSpec) -> Tuple[bool, str]:
    """
    Audits, test-compiles, and instantiates a CustomToolSpec in an isolated temp file.
    If valid, persists it into `storage/custom_tools` and cleans up the temp file.
    """
    is_safe, audit_errors = audit_tool_code(spec)
    if not is_safe:
        return False, "AST Security/Structure Audit Failed:\n- " + "\n- ".join(audit_errors)

    temp_module_name = f"_sandbox_tool_{spec.tool_name}"
    tmp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(spec.python_code)
            tmp_path = Path(tmp_file.name)

        module_spec = importlib.util.spec_from_file_location(temp_module_name, str(tmp_path))
        if module_spec is None or module_spec.loader is None:
            return False, "Could not create Python module spec from custom tool code."

        module = importlib.util.module_from_spec(module_spec)
        sys.modules[temp_module_name] = module
        module_spec.loader.exec_module(module)

        tool_cls = getattr(module, spec.class_name, None)
        if tool_cls is None or not issubclass(tool_cls, BaseTool):
            return False, f"'{spec.class_name}' does not inherit from crewai.tools.BaseTool."

        # Test instantiation to catch Pydantic field/schema errors early
        instance = tool_cls()
        if not getattr(instance, "name", None) or not getattr(instance, "description", None):
            return False, f"Tool instance '{spec.class_name}' must define 'name' and 'description'."

        # Persist to permanent storage registry
        save_custom_tool(spec)
        return True, f"Tool '{spec.tool_name}' ({spec.class_name}) verified and registered."

    except Exception as exc:
        return False, f"Runtime compilation/instantiation error: {type(exc).__name__}: {exc}"

    finally:
        sys.modules.pop(temp_module_name, None)
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
