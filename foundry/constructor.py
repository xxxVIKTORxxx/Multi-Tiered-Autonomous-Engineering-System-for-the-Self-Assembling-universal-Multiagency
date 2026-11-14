import gc
from crewai import Crew, Process, Task
from config.llm_factory import get_llm, get_max_rpm, is_verbose
from foundry.auditor import run_deterministic_audit
from foundry.construction_team import instantiate_layer0_agents
from foundry.schemas import BlueprintSpec, InspectionReport
from foundry.tool_inspector import get_full_toolbox_catalog
from storage.blueprints import get_registry_digest


def build_and_verify_blueprint(
    user_mission: str, max_revisions: int = 3
) -> BlueprintSpec:
    """
    Mobilizes Layer 0 (The Construction Company) from persistent core builders,
    designs and QA-audits the BlueprintSpec (flat or layered departments), and
    immediately dissolves Layer 0 from RAM once the Brigadir signs off.
    """
    verbose = is_verbose()
    max_rpm = get_max_rpm()

    architect_llm = get_llm(temperature=0.15)
    reviewer_llm = get_llm(temperature=0.1)

    registry_digest = get_registry_digest()
    toolbox_catalog = get_full_toolbox_catalog()

    # Load Layer 0 Construction Department specialists
    layer0 = instantiate_layer0_agents(architect_llm, reviewer_llm, verbose)
    architect = layer0["core_chief_architect"]
    hr = layer0["core_hr_specialist"]
    quartermaster = layer0["core_tool_quartermaster"]
    prompt_eng = layer0["core_prompt_engineer"]
    brigadir = layer0["core_brigadir"]

    revision_feedback = ""
    approved_blueprint: BlueprintSpec | None = None

    try:
        for attempt in range(1, max_revisions + 1):
            if verbose:
                print(f"\n[LAYER 0: FOUNDRY] === Construction Cycle {attempt}/{max_revisions} ===")

            feedback_note = (
                f"\n\n=== BRIGADIR REJECTION FEEDBACK (MUST FIX) ===\n{revision_feedback}"
                if revision_feedback
                else ""
            )

            # Step 1: Chief Architect Topology Plan
            t_arch = Task(
                description=(
                    f"Analyze the user mission:\n\"{user_mission}\"\n\n"
                    f"Review existing organizational assets:\n{registry_digest}\n\n"
                    f"Choose:\n"
                    f"- 'flat' mode: Single small crew (1-3 agents) for direct, single-stage tasks.\n"
                    f"- 'layered' mode: Sequential Department Layers (Layer 1, Layer 2, ...) for "
                    f"complex multi-stage missions, specifying each layer's mission and handoff contract."
                    f"{feedback_note}"
                ),
                expected_output=(
                    "Architectural topology plan specifying 'flat' vs 'layered', exact layers, "
                    "objectives, and inter-layer handoff contracts."
                ),
                agent=architect,
            )

            # Step 2: HR Staffing & Archive Lookup
            t_hr = Task(
                description=(
                    f"Staff every layer (or flat crew) from the Architect's plan using the "
                    f"archived assets below first:\n\n{registry_digest}\n\n"
                    f"Reuse matching archived Departments or Agents whenever suitable; define new "
                    f"specialists with unique snake_case `agent_id`s only for uncovered roles."
                ),
                expected_output="Complete staffing roster per layer noting reused vs. new assets.",
                agent=hr,
                context=[t_arch],
            )

            # Step 3: Tool Quartermaster & Custom Tool Synthesis
            t_tools = Task(
                description=(
                    f"Equip each agent_id using the toolbox catalog below:\n\n{toolbox_catalog}\n\n"
                    f"Assign exact tool names from the catalog OR design a new `CustomToolSpec` "
                    f"with complete Python code subclassing `crewai.tools.BaseTool` (`name`, "
                    f"`description`, `args_schema`, and `_run`). Avoid forbidden imports "
                    f"(`subprocess`, `shutil`, `ctypes`, `pickle`) or `os.system`/`eval`/`exec`."
                ),
                expected_output="Exact tool assignments per agent_id and any CustomToolSpec code.",
                agent=quartermaster,
                context=[t_arch, t_hr],
            )

            # Step 4: Prompt Engineer Blueprint Compilation
            t_assemble = Task(
                description=(
                    f"Compile the complete `BlueprintSpec` JSON for:\n\"{user_mission}\"\n\n"
                    f"Rules:\n"
                    f"- Populate `flat_agents` + `flat_tasks` if 'flat', OR ordered `departments` if 'layered'.\n"
                    f"- Every `assigned_agent_id` must exist in that same crew/department.\n"
                    f"- Every `context_task_ids` entry must reference a preceding `task_id` in that scope.\n"
                    f"- Write clear `backstory` prompts and strict `expected_output` criteria."
                    f"{feedback_note}"
                ),
                expected_output="A strictly valid BlueprintSpec object.",
                agent=prompt_eng,
                context=[t_arch, t_hr, t_tools],
                output_pydantic=BlueprintSpec,
            )

            build_crew = Crew(
                agents=[architect, hr, quartermaster, prompt_eng],
                tasks=[t_arch, t_hr, t_tools, t_assemble],
                process=Process.sequential,
                max_rpm=max_rpm,
                verbose=verbose,
            )

            build_out = build_crew.kickoff()
            candidate_bp: BlueprintSpec | None = getattr(build_out, "pydantic", None)

            del build_crew
            gc.collect()

            if candidate_bp is None:
                revision_feedback = "Failed to parse valid BlueprintSpec JSON."
                continue

            # Stage 1 Audit: Deterministic Code, ID, & Tool Verification
            det_ok, det_issues = run_deterministic_audit(candidate_bp)
            if not det_ok:
                revision_feedback = "Deterministic Audit Failed:\n- " + "\n- ".join(det_issues)
                if verbose:
                    print(f"[BRIGADIR] Deterministic rejection:\n{revision_feedback}")
                continue

            # Stage 2 Audit: Brigadir Architectural & Layer Handoff Inspection
            t_inspect = Task(
                description=(
                    f"Audit this BlueprintSpec for mission:\n\"{user_mission}\"\n\n"
                    f"BLUEPRINT:\n{candidate_bp.model_dump_json(indent=2)}\n\n"
                    f"Verify topology fit ('flat' vs 'layered'), agent roles/tools, task clarity, "
                    f"and inter-layer `handoff_contract` compatibility. Approve ONLY if production-ready."
                ),
                expected_output="An InspectionReport with approval status and any fix instructions.",
                agent=brigadir,
                output_pydantic=InspectionReport,
            )

            qa_crew = Crew(
                agents=[brigadir],
                tasks=[t_inspect],
                process=Process.sequential,
                max_rpm=max_rpm,
                verbose=verbose,
            )

            qa_out = qa_crew.kickoff()
            report: InspectionReport | None = getattr(qa_out, "pydantic", None)

            del qa_crew
            gc.collect()

            if report and report.approved:
                if verbose:
                    print(f"[BRIGADIR] Blueprint '{candidate_bp.blueprint_id}' APPROVED.")
                approved_blueprint = candidate_bp
                break

            revision_feedback = (
                "Brigadir QA Issues:\n- "
                + "\n- ".join(report.issues)
                + f"\nFix Instructions: {report.fix_instructions}"
                if report
                else "Brigadir failed to return a valid InspectionReport."
            )
            if verbose:
                print(f"[BRIGADIR] QA rejection:\n{revision_feedback}")

        if approved_blueprint is None:
            raise RuntimeError(
                f"Layer 0 Foundry failed after {max_revisions} cycles:\n{revision_feedback}"
            )

        return approved_blueprint

    finally:
        # Dissolve Layer 0 builders from RAM before Task-Force execution begins
        layer0.clear()
        del architect, hr, quartermaster, prompt_eng, brigadir, layer0
        gc.collect()
