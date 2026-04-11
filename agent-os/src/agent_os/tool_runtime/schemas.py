"""Tool Runtime schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_os.db.models.tool_call import RiskLevel


class ToolCallRequest(BaseModel):
    """工具调用请求。"""
    tool_name: str
    args: dict = Field(default_factory=dict)
    task_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    role: str = ""
    budget_usd: float = float("inf")


class ToolCallResult(BaseModel):
    """工具调用结果。"""
    call_id: str = ""
    tool_name: str
    status: str  # succeeded | failed | timeout
    output: dict | None = None
    error: str | None = None
    risk_level: RiskLevel | None = None
    duration_ms: int = 0


class ToolDefinition(BaseModel):
    """工具注册定义。"""
    name: str
    description: str
    input_schema: dict
    output_schema: dict | None = None
    permissions: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    timeout_sec: int = 30
    max_retries: int = 1
