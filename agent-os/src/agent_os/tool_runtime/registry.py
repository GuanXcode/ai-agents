"""Tool registry — in-memory tool registration and lookup."""

from __future__ import annotations

import structlog

from agent_os.tool_runtime.schemas import ToolDefinition

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """工具注册表：内存存储工具定义。启动时从 DB 加载，运行时动态注册。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition
        logger.info("tool_registered", tool_name=definition.name)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def unregister(self, name: str) -> None:
        if name in self._tools:
            del self._tools[name]
            logger.info("tool_unregistered", tool_name=name)
