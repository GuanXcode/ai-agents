"""Orchestrator schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_os.db.models.task import TaskStatus
from agent_os.db.models.task_step import ActionType, StepStatus


class StepInput(BaseModel):
    action_type: ActionType
    instruction: str = ""
    tool_name: str | None = None
    tool_args: dict | None = None
    context: dict | None = None


class StepOutput(BaseModel):
    step_id: str
    status: StepStatus
    result: dict | None = None
    error: str | None = None
    cost_tokens: int = 0
    cost_usd: float = 0.0


class ExecutionPlan(BaseModel):
    """LLM 生成的执行计划。"""
    steps: list[StepInput] = Field(default_factory=list)
    summary: str = ""


class TaskResult(BaseModel):
    """任务最终结果。"""
    task_id: str
    status: TaskStatus
    result_summary: str | None = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    error: str | None = None
