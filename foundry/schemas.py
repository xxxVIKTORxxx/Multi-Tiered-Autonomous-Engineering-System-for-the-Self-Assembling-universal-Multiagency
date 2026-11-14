from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class CustomToolSpec(BaseModel):
    """Schema for a dynamically synthesized Python BaseTool created by the Tool-Smith."""

    tool_name: str = Field(
        ...,
        description="Unique snake_case identifier for the custom tool (e.g., 'csv_column_filter').",
    )
    class_name: str = Field(
        ...,
        description="PascalCase Python class name inheriting from BaseTool (e.g., 'CsvColumnFilterTool').",
    )
    description: str = Field(
        ...,
        description="Clear explanation of what the tool does and when an agent should use it.",
    )
    python_code: str = Field(
        ...,
        description=(
            "Complete, valid Python module code defining the Pydantic input schema "
            "and a subclass of crewai.tools.BaseTool with a _run method."
        ),
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Keywords for indexing and retrieving this tool from storage.",
    )


class AgentSpec(BaseModel):
    """Schema for an individual Worker Agent."""

    agent_id: str = Field(
        ...,
        description="Unique snake_case ID for this agent within the crew (e.g., 'security_auditor').",
    )
    role: str = Field(..., description="The job title/role of the agent.")
    goal: str = Field(..., description="Specific objective the agent must achieve.")
    backstory: str = Field(
        ...,
        description="Detailed persona, domain expertise, and operational rules for the agent.",
    )
    tools: List[str] = Field(
        default_factory=list,
        description="List of tool names (either from crewai_tools or custom_tools) assigned to this agent.",
    )
    allow_delegation: bool = Field(
        default=False,
        description="Whether this agent can delegate sub-tasks to coworkers.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Domain tags so HR can reuse this agent in future projects.",
    )


class TaskSpec(BaseModel):
    """Schema for an actionable task assigned to a specific Agent."""

    task_id: str = Field(
        ...,
        description="Unique snake_case identifier for this task (e.g., 'extract_api_endpoints').",
    )
    description: str = Field(
        ...,
        description="Step-by-step instructions for what the agent must do.",
    )
    expected_output: str = Field(
        ...,
        description="Exact format, structure, and quality criteria of the completed work.",
    )
    assigned_agent_id: str = Field(
        ...,
        description="Must match an agent_id defined in the same crew or department.",
    )
    context_task_ids: List[str] = Field(
        default_factory=list,
        description="List of task_ids whose outputs must be passed as context into this task.",
    )


class DepartmentSpec(BaseModel):
    """
    Schema for a multi-agent Department (a modular 'Layer' in complex workflows).
    Each department acts as an encapsulated sub-crew with defined inputs and deliverables.
    """

    department_id: str = Field(
        ...,
        description="Unique snake_case ID (e.g., 'data_ingestion_dept').",
    )
    name: str = Field(..., description="Human-readable department name.")
    mission: str = Field(
        ...,
        description="High-level responsibility of this department layer in the overall pipeline.",
    )
    layer_order: int = Field(
        ...,
        ge=1,
        description="Execution order (1 = first layer, 2 = receives Layer 1 output, etc.).",
    )
    process_type: Literal["sequential", "hierarchical"] = Field(
        default="sequential",
        description="Coordination mode inside this department.",
    )
    agents: List[AgentSpec] = Field(
        ...,
        min_length=1,
        description="Specialists belonging to this department.",
    )
    tasks: List[TaskSpec] = Field(
        ...,
        min_length=1,
        description="Ordered internal tasks executed by this department's agents.",
    )
    handoff_contract: str = Field(
        ...,
        description="Strict description of the deliverable passed from this department to the next layer.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Domain tags for archiving and reusing this entire department.",
    )


class BlueprintSpec(BaseModel):
    """
    Master Blueprint produced by the Architect & approved by the Brigadir.
    Supports both 'flat' (simple tasks) and 'layered' (multi-department enterprise tasks).
    """

    blueprint_id: str = Field(
        ...,
        description="Unique snake_case identifier for this task-force blueprint.",
    )
    title: str = Field(..., description="Short title summarizing the task-force mission.")
    architecture_mode: Literal["flat", "layered"] = Field(
        ...,
        description=(
            "'flat' for simple tasks handled by a single small crew; "
            "'layered' for complex tasks decomposed into sequential Departments."
        ),
    )
    reasoning: str = Field(
        ...,
        description="Architect's justification for choosing flat vs. layered structure.",
    )
    custom_tools: List[CustomToolSpec] = Field(
        default_factory=list,
        description="Any new Python tools synthesized specifically for this blueprint.",
    )
    # Used when architecture_mode == 'flat'
    flat_process_type: Literal["sequential", "hierarchical"] = Field(
        default="sequential",
        description="Process type when running in 'flat' mode.",
    )
    flat_agents: List[AgentSpec] = Field(
        default_factory=list,
        description="Agents used when architecture_mode is 'flat'.",
    )
    flat_tasks: List[TaskSpec] = Field(
        default_factory=list,
        description="Tasks used when architecture_mode is 'flat'.",
    )
    # Used when architecture_mode == 'layered'
    departments: List[DepartmentSpec] = Field(
        default_factory=list,
        description="Ordered Department layers used when architecture_mode is 'layered'.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Searchable tags for archiving and future HR retrieval.",
    )


class InspectionReport(BaseModel):
    """Structured QA verdict issued by the Brigadir (Foreman) during construction."""

    approved: bool = Field(
        ...,
        description="True only if all agents, tools, tasks, and layer handoffs pass validation.",
    )
    issues: List[str] = Field(
        default_factory=list,
        description="Specific structural, prompt, or tool defects found during inspection.",
    )
    fix_instructions: str = Field(
        default="",
        description="Actionable instructions for the builders if approved is False.",
    )
