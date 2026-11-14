import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from foundry.schemas import BlueprintSpec
from storage.agents import list_agents, save_agent
from storage.custom_tools import list_custom_tools, save_custom_tool
from storage.departments import list_departments, save_department

STORAGE_ROOT = Path(__file__).resolve().parent / "data"
BLUEPRINTS_DIR = STORAGE_ROOT / "blueprints"
INDEX_FILE = BLUEPRINTS_DIR / "index.json"


def _ensure_dirs() -> None:
    BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
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


def save_blueprint(blueprint: BlueprintSpec) -> Path:
    """
    Saves the full BlueprintSpec to disk AND registers all nested custom tools,
    agents, and departments into their respective registries before cleanup.
    """
    _ensure_dirs()

    # 1. Persist any custom tools
    for tool_spec in blueprint.custom_tools:
        save_custom_tool(tool_spec)

    # 2. Persist flat agents OR layered departments & their internal agents
    if blueprint.architecture_mode == "flat":
        for agent_spec in blueprint.flat_agents:
            save_agent(agent_spec)
    else:
        for dept_spec in blueprint.departments:
            save_department(dept_spec)
            for agent_spec in dept_spec.agents:
                save_agent(agent_spec)

    # 3. Persist the full blueprint JSON
    bp_file = BLUEPRINTS_DIR / f"{blueprint.blueprint_id}.json"
    bp_file.write_text(blueprint.model_dump_json(indent=2), encoding="utf-8")

    # 4. Update index metadata
    index = _load_index()
    index[blueprint.blueprint_id] = {
        "blueprint_id": blueprint.blueprint_id,
        "title": blueprint.title,
        "architecture_mode": blueprint.architecture_mode,
        "tags": blueprint.tags,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "file_path": str(bp_file),
    }
    _save_index(index)
    return bp_file


def get_blueprint(blueprint_id: str) -> Optional[BlueprintSpec]:
    """Loads a full BlueprintSpec by blueprint_id."""
    index = _load_index()
    meta = index.get(blueprint_id)
    if not meta:
        return None

    bp_file = Path(meta["file_path"])
    if not bp_file.exists():
        return None

    return BlueprintSpec.model_validate_json(bp_file.read_text(encoding="utf-8"))


def list_blueprints() -> List[dict]:
    """Returns metadata summaries for all archived Blueprints."""
    index = _load_index()
    return list(index.values())


def get_registry_digest() -> str:
    """
    Generates a concise text catalog of all existing Blueprints, Departments,
    Agents, and Custom Tools for injection into the Construction Crew's context.
    """
    bps = list_blueprints()
    depts = list_departments()
    agents = list_agents()
    tools = list_custom_tools()

    lines = ["=== ARCHIVED ENGINEERING ASSETS (REUSE BEFORE REBUILDING) ==="]

    lines.append("\n[1. Existing Task-Force Blueprints]")
    if bps:
        for b in bps:
            lines.append(
                f"- {b['blueprint_id']} ({b['architecture_mode']}): {b['title']} | tags={b.get('tags', [])}"
            )
    else:
        lines.append("- None yet.")

    lines.append("\n[2. Existing Multi-Agent Departments (Layers)]")
    if depts:
        for d in depts:
            agent_ids = [a.agent_id for a in d.agents]
            lines.append(
                f"- {d.department_id} ('{d.name}'): {d.mission} | agents={agent_ids} | tags={d.tags}"
            )
    else:
        lines.append("- None yet.")

    lines.append("\n[3. Existing Specialist Agents]")
    if agents:
        for a in agents:
            lines.append(
                f"- {a.agent_id} (Role: {a.role}): {a.goal} | tools={a.tools} | tags={a.tags}"
            )
    else:
        lines.append("- None yet.")

    lines.append("\n[4. Existing Custom Python Tools]")
    if tools:
        for t in tools:
            lines.append(
                f"- {t['tool_name']} ({t['class_name']}): {t['description']} | tags={t.get('tags', [])}"
            )
    else:
        lines.append("- None yet.")

    return "\n".join(lines)
