"""Memory Service interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.memory.schemas import Context, KnowledgeChunk
from agent_os.orchestrator.schemas import StepOutput


class MemoryServiceInterface(ABC):
    """记忆服务接口。"""

    @abstractmethod
    async def load_context(self, task_id: str, tenant_id: str, user_id: str, goal: str) -> Context:
        """加载任务上下文（短期记忆 + 用户偏好 + 关联知识）。"""

    @abstractmethod
    async def save_step_result(self, task_id: str, step_output: StepOutput) -> None:
        """持久化步骤结果到短期记忆。"""

    @abstractmethod
    async def archive_task(self, task_id: str) -> None:
        """任务结束后归档短期记忆，生成长期记忆摘要。"""

    @abstractmethod
    async def search_knowledge(self, query: str, top_k: int = 5) -> list[KnowledgeChunk]:
        """语义检索知识库。MVP 返回空列表，后续接入 pgvector。"""
