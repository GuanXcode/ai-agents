"""Tool Runtime interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.tool_runtime.schemas import ToolCallRequest, ToolCallResult, ToolDefinition


class ToolRuntimeInterface(ABC):
    """工具运行时接口。"""

    @abstractmethod
    async def execute(self, call: ToolCallRequest) -> ToolCallResult:
        """
        执行工具调用。

        Args:
            call: 工具调用请求

        Returns:
            ToolCallResult

        Raises:
            ToolNotFoundError: 工具未注册
            ValidationError: 参数校验失败
            超时时返回 ToolCallResult(status="timeout") 而非抛出异常
        """

    @abstractmethod
    def register(self, definition: ToolDefinition) -> None:
        """注册工具。"""

    @abstractmethod
    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取工具定义。"""
