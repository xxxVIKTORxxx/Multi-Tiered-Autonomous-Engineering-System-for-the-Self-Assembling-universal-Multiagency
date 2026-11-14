import json
from pathlib import Path
from typing import Dict, List, Optional
from foundry.schemas import AgentSpec

STORAGE_ROOT = Path(__file__).resolve().parent / "data"
AGENTS_DIR = STORAGE_ROOT / "agents"
INDEX_FILE = AGENTS_DIR / "index.json"


def _ensure_dirs() -> None:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
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


def save_agent(spec: AgentSpec) -> None:
    """Archives an AgentSpec into persistent storage for future reuse by HR."""
    _ensure_dirs()
    index = _load_index()
    index[spec.agent_id] = spec.model_dump()
    _save_index(index)


def get_agent(agent_id: str) -> Optional[AgentSpec]:
    """Retrieves an AgentSpec by its unique ID."""
    index = _load_index()
    data = index.get(agent_id)
    if not data:
        return None
    return AgentSpec(**data)


def list_agents() -> List[AgentSpec]:
    """Returns all archived AgentSpecs."""
    index = _load_index()
    return [AgentSpec(**item) for item in index.values()]


def search_agents(keywords: List[str]) -> List[AgentSpec]:
    """Finds stored agents matching any of the given keywords in role, goal, or tags."""
    if not keywords:
        return list_agents()

    lowered = [k.lower() for k in keywords]
    matches: List[AgentSpec] = []
    for agent in list_agents():
        haystack = (
            f"{agent.agent_id} {agent.role} {agent.goal} {' '.join(agent.tags)}"
        ).lower()
        if any(kw in haystack for kw in lowered):
            matches.append(agent)
    return matches
