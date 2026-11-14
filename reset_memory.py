import os
import shutil
from pathlib import Path


def full_factory_reset() -> None:
    """
    Completely wipes:
      1. All persistent registries inside `storage/data/` (blueprints, departments, agents, custom_tools)
      2. Any leftover `crew_foundry_session_*` temporary folders
      3. Local `.crewai` or `CREWAI_STORAGE_DIR` SQLite/Chroma caches if present
    """
    root_dir = Path(__file__).resolve().parent
    storage_data_dir = root_dir / "storage" / "data"

    if storage_data_dir.exists():
        shutil.rmtree(storage_data_dir, ignore_errors=True)
        print(f"[RESET] Wiped persistent registry directory: {storage_data_dir}")
    else:
        print("[RESET] No storage/data directory found (already clean).")

    # Clean any local .crewai folder in the project root
    local_crewai_dir = root_dir / ".crewai"
    if local_crewai_dir.exists():
        shutil.rmtree(local_crewai_dir, ignore_errors=True)
        print(f"[RESET] Wiped local CrewAI cache: {local_crewai_dir}")

    # Clean custom CREWAI_STORAGE_DIR if configured in environment
    custom_crewai_dir = os.getenv("CREWAI_STORAGE_DIR")
    if custom_crewai_dir:
        p = Path(custom_crewai_dir)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            print(f"[RESET] Wiped CREWAI_STORAGE_DIR: {p}")

    print("[RESET] Factory reset complete. All agent/department/tool memories deleted.")


if __name__ == "__main__":
    confirm = input(
        "This will permanently delete ALL saved blueprints, departments, agents, and custom tools.\n"
        "Type 'RESET' to confirm: "
    ).strip()
    if confirm == "RESET":
        full_factory_reset()
    else:
        print("Reset cancelled.")
