"""Model Router schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelRequest(BaseModel):
    """模型调用请求。"""
    action_type: str
    system_prompt: str = ""
    user_message: str
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)


class ModelResponse(BaseModel):
    """模型调用响应。"""
    output: str
    model_name: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
