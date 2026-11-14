import os
import sys
from config.llm_factory import is_verbose
from foundry.constructor import build_and_verify_blueprint
from runtime.cleanup import archive_and_purge, create_isolated_session_dir
from runtime.factory import execute_blueprint


def run_autonomous_mission(user_mission: str) -> str:
    """
    Full lifecycle controller:
      1. Isolates CrewAI storage inside a temporary directory for this session.
      2. Mobilizes Layer 0 Construction Company to design & Brigadir-verify a BlueprintSpec.
      3. Executes the Task-Force (flat crew or multi-department layers).
      4. Saves Blueprint, Departments, Agents, and Custom Tools to `storage/`.
      5. Purges all live crews, dynamic modules, temp folders, and RAM.
    """
    verbose = is_verbose()
    session_dir = create_isolated_session_dir()
    os.environ["CREWAI_STORAGE_DIR"] = str(session_dir)

    approved_blueprint = None

    try:
        # Phase 1: Layer 0 Construction & Brigadir Inspection
        approved_blueprint = build_and_verify_blueprint(
            user_mission=user_mission,
            max_revisions=3,
        )

        # Phase 2: Task-Force Execution
        final_output = execute_blueprint(
            blueprint=approved_blueprint,
            user_mission=user_mission,
        )
        return final_output

    finally:
        # Phase 3 & 4: Archive to storage/ FIRST, then wipe active RAM & temp dirs
        archive_and_purge(
            blueprint=approved_blueprint,
            temp_session_dir=session_dir,
            verbose=verbose,
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mission = " ".join(sys.argv[1:]).strip()
    else:
        print("=== AUTONOMOUS MULTI-AGENT FOUNDRY ===")
        mission = input("Enter your task or complex mission: ").strip()

    if not mission:
        print("No mission provided. Exiting.")
        sys.exit(0)

    output = run_autonomous_mission(mission)
    print("\n" + "=" * 60)
    print("FINAL MISSION DELIVERABLE")
    print("=" * 60)
    print(output)
