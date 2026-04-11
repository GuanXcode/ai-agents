"""Memory Service implementation — SQL-backed short-term and long-term memory."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.config import MemorySettings
from agent_os.memory.interface import MemoryServiceInterface
from agent_os.memory.schemas import Context, KnowledgeChunk
from agent_os.orchestrator.schemas import StepOutput

logger = structlog.get_logger(__name__)


class MemoryService(MemoryServiceInterface):
    def __init__(self, settings: MemorySettings, session: AsyncSession) -> None:
        self._settings = settings
        self._session = session

    async def load_context(
        self,
        task_id: str,
        tenant_id: str,
        user_id: str,
        goal: str,
    ) -> Context:
        """加载任务上下文：短期记忆 + 用户偏好。"""
        from agent_os.db.models.task_step import TaskStep

        short_term: list[dict] = []

        # 加载当前任务的步骤输出作为短期上下文
        stmt = (
            select(TaskStep)
            .where(
                TaskStep.task_id == uuid.UUID(task_id),
                TaskStep.output.isnot(None),
            )
            .order_by(TaskStep.created_at.desc())
            .limit(self._settings.short_term.max_rounds)
        )
        result = await self._session.execute(stmt)
        steps = result.scalars().all()
        for step in steps:
            if step.output:
                short_term.append({
                    "step_id": str(step.step_id),
                    "action_type": step.action_type.value if step.action_type else None,
                    "output": step.output,
                })

        # 加载用户偏好（MVP: 简单 KV 存储）
        user_prefs = await self._load_user_preferences(user_id, tenant_id)

        return Context(
            task_id=task_id,
            tenant_id=tenant_id,
            user_id=user_id,
            goal=goal,
            short_term=short_term[-self._settings.short_term.max_rounds:],
            user_preferences=user_prefs,
            knowledge=[],
        )

    async def save_step_result(self, task_id: str, step_output: StepOutput) -> None:
        """持久化步骤结果。短期记忆通过 task_steps 表自动持久化。"""
        from agent_os.db.models.task_step import TaskStep

        stmt = (
            update(TaskStep)
            .where(TaskStep.step_id == uuid.UUID(step_output.step_id))
            .values(
                output=step_output.result,
                status=step_output.status.value,
                cost_tokens=step_output.cost_tokens,
                cost_usd=step_output.cost_usd,
                error_message=step_output.error,
                ended_at=datetime.utcnow(),
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.info(
            "step_result_saved",
            task_id=task_id,
            step_id=step_output.step_id,
            status=step_output.status.value,
        )

    async def archive_task(self, task_id: str) -> None:
        """任务归档：将关键步骤摘要存为用户偏好。"""
        from agent_os.db.models.task_step import TaskStep

        stmt = (
            select(TaskStep)
            .where(TaskStep.task_id == uuid.UUID(task_id))
            .order_by(TaskStep.step_order)
        )
        result = await self._session.execute(stmt)
        steps = result.scalars().all()

        summaries = []
        for step in steps:
            if step.output and step.action_type:
                summaries.append({
                    "type": step.action_type.value,
                    "summary": json.dumps(step.output, ensure_ascii=False)[:200],
                })

        if summaries:
            logger.info(
                "task_archived",
                task_id=task_id,
                step_count=len(summaries),
            )
            # TODO: 将 summaries 持久化为长期记忆（写入 user_preferences 或独立的 memory 表）

    async def search_knowledge(self, query: str, top_k: int = 5) -> list[KnowledgeChunk]:
        """语义检索知识库。MVP 返回空列表，后续接入 pgvector。"""
        return []

    async def _load_user_preferences(self, user_id: str, tenant_id: str) -> dict:
        # TODO: 从 user_preferences 表或 Redis 加载用户偏好 KV
        return {}
