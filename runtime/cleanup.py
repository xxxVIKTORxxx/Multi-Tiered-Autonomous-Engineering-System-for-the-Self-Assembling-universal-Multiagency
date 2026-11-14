import gc
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional
from foundry.schemas import BlueprintSpec
from storage.blueprints import save_blueprint


def archive_and_purge(
    blueprint: Optional[BlueprintSpec],
    temp_session_dir: Optional[Path] = None,
    verbose: bool = True,
) -> None:
    """
    1. Saves the Task-Force Blueprint (plus all nested Departments, Agents, and Custom Tools)
       into persistent storage BEFORE teardown.
    2. Unloads dynamically imported custom tool modules from `sys.modules`.
    3. Deletes any ephemeral session directories and runs full garbage collection.
    """
    # Step 1: Persist to storage registries
    if blueprint is not None:
        saved_path = save_blueprint(blueprint)
        if verbose:
            print(f"[ARCHIVE] Saved Task-Force Blueprint & assets to: {saved_path}")

    # Step 2: Unload dynamically imported custom tools from Python runtime memory
    dynamic_modules = [
        mod_name
        for mod_name in list(sys.modules.keys())
        if mod_name.startswith("dynamic_custom_tools.")
        or mod_name.startswith("_sandbox_tool_")
    ]
    for mod_name in dynamic_modules:
        sys.modules.pop(mod_name, None)

    if verbose and dynamic_modules:
        print(f"[CLEANUP] Unloaded {len(dynamic_modules)} dynamic tool module(s) from RAM.")

    # Step 3: Remove isolated session temp folder if provided
    if temp_session_dir and temp_session_dir.exists():
        shutil.rmtree(temp_session_dir, ignore_errors=True)
        if verbose:
            print(f"[CLEANUP] Purged ephemeral session cache: {temp_session_dir}")

    # Step 4: Force Python garbage collection
    gc.collect()
    if verbose:
        print("[CLEANUP] System memory restored to clean baseline.")


def create_isolated_session_dir() -> Path:
    """Creates a temporary workspace directory for isolated execution."""
    return Path(tempfile.mkdtemp(prefix="crew_foundry_session_"))
