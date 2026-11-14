import json
from pathlib import Path
from typing import Dict, List, Optional
from foundry.schemas import DepartmentSpec

STORAGE_ROOT = Path(__file__).resolve().parent / "data"
DEPTS_DIR = STORAGE_ROOT / "departments"
INDEX_FILE = DEPTS_DIR / "index.json"


def _ensure_dirs() -> None:
    DEPTS_DIR.mkdir(parents=True, exist_ok=True)
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


def save_department(spec: DepartmentSpec) -> None:
    """Archives a multi-agent Department layer into persistent storage."""
    _ensure_dirs()
    index = _load_index()
    index[spec.department_id] = spec.model_dump()
    _save_index(index)


def get_department(department_id: str) -> Optional[DepartmentSpec]:
    """Retrieves a DepartmentSpec by its unique department_id."""
    index = _load_index()
    data = index.get(department_id)
    if not data:
        return None
    return DepartmentSpec(**data)


def list_departments() -> List[DepartmentSpec]:
    """Returns all archived DepartmentSpecs."""
    index = _load_index()
    return [DepartmentSpec(**item) for item in index.values()]


def search_departments(keywords: List[str]) -> List[DepartmentSpec]:
    """Finds stored departments matching any keyword in name, mission, or tags."""
    if not keywords:
        return list_departments()

    lowered = [k.lower() for k in keywords]
    matches: List[DepartmentSpec] = []
    for dept in list_departments():
        haystack = (
            f"{dept.department_id} {dept.name} {dept.mission} {' '.join(dept.tags)}"
        ).lower()
        if any(kw in haystack for kw in lowered):
            matches.append(dept)
    return matches
