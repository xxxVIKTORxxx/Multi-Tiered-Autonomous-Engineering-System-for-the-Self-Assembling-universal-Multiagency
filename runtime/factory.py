import gc
from typing import Dict, List
from crewai import Agent, Crew, Process, Task
from config.llm_factory import get_llm, get_max_rpm, is_verbose
from foundry.schemas import AgentSpec, BlueprintSpec, DepartmentSpec, TaskSpec
from foundry.tool_inspector import resolve_tools_for_agent


def _build_live_agents(
    agent_specs: List[AgentSpec], worker_llm, verbose: bool
) -> Dict[str, Agent]:
    """Instantiates CrewAI Agent objects and binds resolved built-in/custom tools."""
    live_agents: Dict[str, Agent] = {}

    for spec in agent_specs:
        tools, unresolved = resolve_tools_for_agent(spec.tools)
        if unresolved and verbose:
            print(
                f"[RUNTIME WARNING] Agent '{spec.agent_id}' skipped unresolved tools: {unresolved}"
            )

        live_agents[spec.agent_id] = Agent(
            role=spec.role,
            goal=spec.goal,
            backstory=spec.backstory,
            tools=tools,
            llm=worker_llm,
            verbose=verbose,
            allow_delegation=spec.allow_delegation,
        )

    return live_agents


def _build_live_tasks(
    task_specs: List[TaskSpec],
    live_agents: Dict[str, Agent],
    prior_layer_context: str = "",
) -> List[Task]:
    """Instantiates CrewAI Task objects, wiring internal context dependencies and prior layer outputs."""
    task_map: Dict[str, Task] = {}
    ordered_tasks: List[Task] = []

    for spec in task_specs:
        agent = live_agents[spec.assigned_agent_id]
        context_tasks = [
            task_map[cid] for cid in spec.context_task_ids if cid in task_map
        ]

        description = spec.description
        if prior_layer_context and not context_tasks:
            description = (
                f"{spec.description}\n\n"
                f"=== INPUT DELIVERABLE FROM PREVIOUS DEPARTMENT LAYER ===\n"
                f"{prior_layer_context}"
            )

        live_task = Task(
            description=description,
            expected_output=spec.expected_output,
            agent=agent,
            context=context_tasks if context_tasks else None,
        )
        task_map[spec.task_id] = live_task
        ordered_tasks.append(live_task)

    return ordered_tasks


def _execute_department_layer(
    dept: DepartmentSpec,
    prior_output: str,
    worker_llm,
    manager_llm,
    max_rpm: int,
    verbose: bool,
) -> str:
    """Executes a single Department layer as an isolated sub-crew and cleans its RAM immediately."""
    if verbose:
        print(
            f"\n[RUNTIME] >>> Mobilizing Layer {dept.layer_order}: {dept.name} ({dept.department_id}) <<<"
        )

    live_agents = _build_live_agents(dept.agents, worker_llm, verbose)
    live_tasks = _build_live_tasks(dept.tasks, live_agents, prior_layer_context=prior_output)

    process = (
        Process.hierarchical
        if dept.process_type == "hierarchical"
        else Process.sequential
    )

    crew_kwargs = {
        "agents": list(live_agents.values()),
        "tasks": live_tasks,
        "process": process,
        "memory": False,
        "max_rpm": max_rpm,
        "verbose": verbose,
    }
    if process == Process.hierarchical:
        crew_kwargs["manager_llm"] = manager_llm

    dept_crew = Crew(**crew_kwargs)
    try:
        result = dept_crew.kickoff()
        return getattr(result, "raw", str(result))
    finally:
        live_agents.clear()
        live_tasks.clear()
        del dept_crew, live_agents, live_tasks
        gc.collect()


def execute_blueprint(blueprint: BlueprintSpec, user_mission: str) -> str:
    """
    Executes an approved BlueprintSpec in either 'flat' mode (single crew)
    or 'layered' mode (sequential multi-department pipeline).
    """
    verbose = is_verbose()
    max_rpm = get_max_rpm()
    worker_llm = get_llm(temperature=0.25)
    manager_llm = get_llm(temperature=0.1)

    if verbose:
        print(
            f"\n[RUNTIME] Launching Task-Force '{blueprint.title}' "
            f"[Mode: {blueprint.architecture_mode.upper()}]"
        )

    # --- MODE A: FLAT SINGLE-LAYER CREW ---
    if blueprint.architecture_mode == "flat":
        live_agents = _build_live_agents(blueprint.flat_agents, worker_llm, verbose)
        live_tasks = _build_live_tasks(
            blueprint.flat_tasks, live_agents, prior_layer_context=f"Mission: {user_mission}"
        )

        process = (
            Process.hierarchical
            if blueprint.flat_process_type == "hierarchical"
            else Process.sequential
        )
        crew_kwargs = {
            "agents": list(live_agents.values()),
            "tasks": live_tasks,
            "process": process,
            "memory": False,
            "max_rpm": max_rpm,
            "verbose": verbose,
        }
        if process == Process.hierarchical:
            crew_kwargs["manager_llm"] = manager_llm

        flat_crew = Crew(**crew_kwargs)
        try:
            result = flat_crew.kickoff()
            return getattr(result, "raw", str(result))
        finally:
            live_agents.clear()
            live_tasks.clear()
            del flat_crew, live_agents, live_tasks
            gc.collect()

    # --- MODE B: LAYERED MULTI-DEPARTMENT PIPELINE ---
    sorted_departments = sorted(blueprint.departments, key=lambda d: d.layer_order)
    current_handoff = f"Initial User Mission:\n{user_mission}"

    for dept in sorted_departments:
        layer_output = _execute_department_layer(
            dept=dept,
            prior_output=current_handoff,
            worker_llm=worker_llm,
            manager_llm=manager_llm,
            max_rpm=max_rpm,
            verbose=verbose,
        )
        current_handoff = (
            f"Deliverable from Layer {dept.layer_order} ({dept.name}):\n"
            f"Expected Contract: {dept.handoff_contract}\n\n"
            f"{layer_output}"
        )

    return current_handoff
