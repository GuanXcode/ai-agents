"""Policy Engine interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.policy.schemas import PolicyCheckContext, PolicyDecision


class PolicyEngineInterface(ABC):
    """策略引擎接口。"""

    @abstractmethod
    async def check(self, context: PolicyCheckContext) -> PolicyDecision:
        """
        执行策略判定。

        Args:
            context: 策略检查上下文（含累计成本、角色、租户、工具名等）

        Returns:
            PolicyDecision（是否允许、是否需要人工确认、剩余预算）
        """
