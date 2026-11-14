from typing import List, Set, Tuple
from foundry.schemas import BlueprintSpec
from foundry.tool_inspector import resolve_tool_instance
from foundry.tool_smith import compile_and_verify_tool


def run_deterministic_audit(blueprint: BlueprintSpec) -> Tuple[bool, List[str]]:
    """
    Hard programmatic checklist executed by the Brigadir's engineering rules BEFORE
    LLM semantic inspection. Verifies custom tool compilation, tool existence,
    agent/task ID integrity, and inter-layer handoff contracts.
    """
    issues: List[str] = []

    # 1. Compile and AST-audit any newly synthesized custom tools
    compiled_custom_tools: Set[str] = set()
    for tool_spec in blueprint.custom_tools:
        ok, msg = compile_and_verify_tool(tool_spec)
        if not ok:
            issues.append(f"CustomTool '{tool_spec.tool_name}' failed verification: {msg}")
        else:
            compiled_custom_tools.add(tool_spec.tool_name)

    def _validate_scope(scope: str, agents: list, tasks: list) -> None:
        if not agents:
            issues.append(f"[{scope}] Must contain at least one agent.")
            return
        if not tasks:
            issues.append(f"[{scope}] Must contain at least one task.")
            return

        agent_ids = {a.agent_id for a in agents}
        if len(agent_ids) != len(agents):
            issues.append(f"[{scope}] Duplicate agent_id detected.")

        for agent in agents:
            for tool_name in agent.tools:
                if tool_name in compiled_custom_tools:
                    continue
                if resolve_tool_instance(tool_name) is None:
                    issues.append(
                        f"[{scope}] Agent '{agent.agent_id}' references unknown tool '{tool_name}'."
                    )

        task_ids = {t.task_id for t in tasks}
        if len(task_ids) != len(tasks):
            issues.append(f"[{scope}] Duplicate task_id detected.")

        for task in tasks:
            if task.assigned_agent_id not in agent_ids:
                issues.append(
                    f"[{scope}] Task '{task.task_id}' assigned to unknown agent '{task.assigned_agent_id}'."
                )
            for ctx_id in task.context_task_ids:
                if ctx_id not in task_ids:
                    issues.append(
                        f"[{scope}] Task '{task.task_id}' references unknown context_task_id '{ctx_id}'."
                    )
                if ctx_id == task.task_id:
                    issues.append(f"[{scope}] Task '{task.task_id}' cannot depend on itself.")

    # 2. Validate flat or layered topology
    if blueprint.architecture_mode == "flat":
        _validate_scope("flat_crew", blueprint.flat_agents, blueprint.flat_tasks)
    elif blueprint.architecture_mode == "layered":
        if not blueprint.departments:
            issues.append("[layered] Requires at least one Department layer.")
        else:
            for dept in sorted(blueprint.departments, key=lambda d: d.layer_order):
                _validate_scope(
                    f"Layer {dept.layer_order}: {dept.department_id}",
                    dept.agents,
                    dept.tasks,
                )
                if not dept.handoff_contract.strip():
                    issues.append(
                        f"[Layer {dept.layer_order}: {dept.department_id}] Missing handoff_contract."
                    )

    return len(issues) == 0, issues
