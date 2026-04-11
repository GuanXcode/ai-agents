"""Dependency injection — wire all modules together."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from agent_os.config import load_settings
from agent_os.memory.service import MemoryService
from agent_os.model_router.router import ModelRouter
from agent_os.orchestrator.engine import Orchestrator
from agent_os.orchestrator.interface import OrchestratorInterface
from agent_os.policy.engine import PolicyEngine
from agent_os.tool_runtime.executor import ToolRuntime
from agent_os.tool_runtime.registry import ToolRegistry


@lru_cache(maxsize=1)
def _get_settings():
    return load_settings()


def get_orchestrator(request: Request) -> OrchestratorInterface:
    """FastAPI 依赖：获取 Orchestrator 实例。"""
    settings = _get_settings()
    session = request.state.db_session

    memory = MemoryService(settings.memory, session)
    policy = PolicyEngine(session)
    registry = ToolRegistry()
    tool_runtime = ToolRuntime(registry)
    model_router = ModelRouter(settings.model_router)

    return Orchestrator(
        settings=settings.orchestrator,
        model_router=model_router,
        tool_runtime=tool_runtime,
        memory=memory,
        policy=policy,
        session=session,
    )
