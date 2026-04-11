"""Orchestrator interface — abstract contract for the orchestration engine."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.gateway.schemas import TaskEnvelope
from agent_os.orchestrator.schemas import TaskResult


class OrchestratorInterface(ABC):
    """编排引擎接口。"""

    @abstractmethod
    async def submit_task(self, envelope: TaskEnvelope) -> str:
        """提交任务，返回 task_id。"""

    @abstractmethod
    async def approve_plan(self, task_id: str) -> TaskResult:
        """人工批准执行计划，开始执行。"""

    @abstractmethod
    async def reject_plan(self, task_id: str, reason: str) -> None:
        """人工拒绝执行计划，任务标记为 CANCELED。"""

    @abstractmethod
    async def approve_step(self, task_id: str, step_id: str) -> None:
        """人工批准高风险步骤。"""

    @abstractmethod
    async def get_task_status(self, task_id: str) -> TaskResult:
        """查询任务状态。"""
