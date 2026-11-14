import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from crewai.tools import BaseTool
from foundry.schemas import CustomToolSpec

STORAGE_ROOT = Path(__file__).resolve().parent / "data"
TOOLS_DIR = STORAGE_ROOT / "custom_tools"
INDEX_FILE = TOOLS_DIR / "index.json"


def _ensure_dirs() -> None:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text("{}", encoding="utf-8")


def _load_index() -> Dict[str, dict]:
    _ensure_dirs()
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_index(index_data: Dict[str, dict]) -> None:
    _ensure_dirs()
    INDEX_FILE.write_text(json.dumps(index_data, indent=2), encoding="utf-8")


def save_custom_tool(spec: CustomToolSpec) -> Path:
    """Persists a verified CustomToolSpec's Python code and metadata to storage."""
    _ensure_dirs()
    code_path = TOOLS_DIR / f"{spec.tool_name}.py"
    code_path.write_text(spec.python_code, encoding="utf-8")

    index = _load_index()
    index[spec.tool_name] = {
        "tool_name": spec.tool_name,
        "class_name": spec.class_name,
        "description": spec.description,
        "tags": spec.tags,
        "file_path": str(code_path),
    }
    _save_index(index)
    return code_path


def list_custom_tools() -> List[dict]:
    """Returns metadata summaries of all stored custom tools for HR & Tool-Smith lookup."""
    index = _load_index()
    return list(index.values())


def get_custom_tool_spec(tool_name: str) -> Optional[CustomToolSpec]:
    """Retrieves full CustomToolSpec (including Python code) from storage by tool_name."""
    index = _load_index()
    meta = index.get(tool_name)
    if not meta:
        return None

    code_path = Path(meta["file_path"])
    if not code_path.exists():
        return None

    return CustomToolSpec(
        tool_name=meta["tool_name"],
        class_name=meta["class_name"],
        description=meta["description"],
        python_code=code_path.read_text(encoding="utf-8"),
        tags=meta.get("tags", []),
    )


def instantiate_custom_tool(tool_name: str) -> Optional[BaseTool]:
    """
    Dynamically imports a stored custom tool module and returns an instance of its BaseTool class.
    Registers module under 'dynamic_custom_tools.<tool_name>' for clean teardown later.
    """
    index = _load_index()
    meta = index.get(tool_name)
    if not meta:
        return None

    code_path = Path(meta["file_path"])
    if not code_path.exists():
        return None

    module_name = f"dynamic_custom_tools.{tool_name}"
    spec = importlib.util.spec_from_file_location(module_name, str(code_path))
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    tool_cls = getattr(module, meta["class_name"], None)
    if tool_cls is None:
        return None

    return tool_cls()
