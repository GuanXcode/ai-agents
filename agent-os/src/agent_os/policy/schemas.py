"""Policy Engine schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PolicyDecision(BaseModel):
    """策略判定结果。"""
    allowed: bool
    reason: str = ""
    requires_approval: bool = False
    budget_remaining: float = 0.0


class PolicyCheckContext(BaseModel):
    """策略检查上下文。"""
    task_id: str
    tenant_id: str
    user_id: str
    role: str
    cumulative_cost_usd: float
    budget_usd: float
    tool_name: str | None = None
    risk_level: str | None = None
