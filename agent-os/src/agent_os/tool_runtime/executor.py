"""Tool Runtime executor — validate and execute tool calls.

Policy authorization is handled by the Orchestrator before calling execute().
The executor is responsible for: lookup → arg validation → execution with timeout.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import structlog

from agent_os.tool_runtime.interface import ToolRuntimeInterface
from agent_os.tool_runtime.registry import ToolRegistry
from agent_os.tool_runtime.schemas import ToolCallRequest, ToolCallResult, ToolDefinition

logger = structlog.get_logger(__name__)


class ToolNotFoundError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class ValidationError(Exception):
    pass


class ToolRuntime(ToolRuntimeInterface):
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._executors: dict[str, Callable] = {}
        self._load_builtin_tools()

    def _load_builtin_tools(self) -> None:
        """加载内置工具的注册定义和执行函数。"""
        from agent_os.tool_runtime.tools import query_sales_db, read_document

        for module in [query_sales_db, read_document]:
            self._registry.register(module.DEFINITION)
            self._executors[module.DEFINITION.name] = module.execute

    def register(self, definition: ToolDefinition) -> None:
        self._registry.register(definition)

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._registry.get(name)

    async def execute(self, call: ToolCallRequest) -> ToolCallResult:
        """执行工具调用：查找 → 参数校验 → 执行（含超时）。"""
        # 1. 查找工具
        tool_def = self._registry.get(call.tool_name)
        if tool_def is None:
            raise ToolNotFoundError(f"工具未注册: {call.tool_name}")

        # 2. 参数校验
        self._validate_args(tool_def, call.args)

        # 3. 执行（含超时）
        start = time.monotonic()
        try:
            executor = self._executors.get(call.tool_name)
            if executor is None:
                raise ToolNotFoundError(f"工具执行器未注册: {call.tool_name}")

            result = await asyncio.wait_for(
                executor(call.args),
                timeout=tool_def.timeout_sec,
            )
            duration = int((time.monotonic() - start) * 1000)
            result.duration_ms = duration
            return result

        except asyncio.TimeoutError:
            duration = int((time.monotonic() - start) * 1000)
            logger.error("tool_timeout", tool_name=call.tool_name, timeout=tool_def.timeout_sec)
            return ToolCallResult(
                tool_name=call.tool_name,
                status="timeout",
                error=f"执行超时 ({tool_def.timeout_sec}s)",
                duration_ms=duration,
                risk_level=tool_def.risk_level,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            logger.error("tool_execution_error", tool_name=call.tool_name, error=str(e))
            return ToolCallResult(
                tool_name=call.tool_name,
                status="failed",
                error=str(e),
                duration_ms=duration,
                risk_level=tool_def.risk_level,
            )

    def _validate_args(self, tool_def: ToolDefinition, args: dict) -> None:
        """基于 JSON Schema 做简易参数校验。"""
        schema = tool_def.input_schema
        if not schema:
            return

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        missing = [r for r in required if r not in args]
        if missing:
            raise ValidationError(f"缺少必填参数: {missing}")

        for key in args:
            if key not in properties:
                raise ValidationError(f"未知参数: {key}")
