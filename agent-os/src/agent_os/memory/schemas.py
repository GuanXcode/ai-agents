"""Memory Service schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Context(BaseModel):
    """任务执行上下文。"""
    task_id: str
    tenant_id: str
    user_id: str
    goal: str
    short_term: list[dict] = Field(default_factory=list)  # 最近 N 轮对话
    user_preferences: dict = Field(default_factory=dict)   # 用户偏好
    knowledge: list[dict] = Field(default_factory=list)    # 关联知识片段


class KnowledgeChunk(BaseModel):
    """知识片段。"""
    chunk_id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    score: float = 0.0  # 检索相关度
