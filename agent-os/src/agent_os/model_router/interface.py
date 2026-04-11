"""Model Router interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.model_router.schemas import ModelRequest, ModelResponse
from agent_os.orchestrator.schemas import StepInput


class ModelRouterInterface(ABC):
    """模型路由接口。"""

    @abstractmethod
    async def route(self, step: StepInput, context: dict | None = None) -> ModelResponse:
        """
        按步骤类型路由到合适的模型。

        Args:
            step: 当前步骤（含 action_type, instruction）
            context: 会话上下文

        Returns:
            ModelResponse

        Raises:
            ModelUnavailableError: 首选和 fallback 模型均不可用
        """
