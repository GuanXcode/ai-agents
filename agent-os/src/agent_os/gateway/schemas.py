"""Gateway schemas — request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskConstraints(BaseModel):
    budget_usd: float = Field(default=2.0, ge=0)
    deadline_sec: int = Field(default=120, ge=10)


class TaskRequest(BaseModel):
    """客户端提交的任务请求。"""
    goal: str = Field(..., min_length=1, max_length=2000)
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    context_refs: list[str] = Field(default_factory=list)


class TaskEnvelope(BaseModel):
    """Gateway 标准化后的内部任务对象。task_id 由 Orchestrator 生成。"""
    tenant_id: str
    user_id: str
    goal: str
    constraints: TaskConstraints
    context_refs: list[str]
