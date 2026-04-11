"""Base LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.model_router.schemas import ModelRequest, ModelResponse


class LLMProvider(ABC):
    """LLM 提供商适配器基类。"""

    @abstractmethod
    async def complete(self, request: ModelRequest) -> ModelResponse:
        """调用模型，返回响应。"""

    @abstractmethod
    def name(self) -> str:
        """返回 provider 名称。"""
