"""Policy Engine implementation — budget, tool whitelist, approval checks."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.models.policy import Policy, PolicyType
from agent_os.db.models.tool import Tool
from agent_os.policy.interface import PolicyEngineInterface
from agent_os.policy.schemas import PolicyCheckContext, PolicyDecision

logger = structlog.get_logger(__name__)


class PolicyEngine(PolicyEngineInterface):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(self, context: PolicyCheckContext) -> PolicyDecision:
        """
        执行策略判定，按优先级依次检查：
        1. 预算上限
        2. 工具白名单
        3. 高风险审批
        """
        policies = await self._load_policies(context.tenant_id)

        # DATA_BOUNDARY 类型暂未实现，提前告警（不阻断）
        from agent_os.db.models.policy import PolicyType
        if any(p.policy_type == PolicyType.DATA_BOUNDARY for p in policies):
            logger.warning("data_boundary_policy_unhandled", task_id=context.task_id)

        # 1. 预算检查
        budget_decision = self._check_budget(context, policies)
        if not budget_decision.allowed:
            logger.warning("policy_denied_budget", task_id=context.task_id, reason=budget_decision.reason)
            return budget_decision

        # 2. 工具白名单检查
        if context.tool_name:
            tool_decision = await self._check_tool_whitelist(context, policies)
            if not tool_decision.allowed:
                logger.warning("policy_denied_tool", task_id=context.task_id, tool=context.tool_name, reason=tool_decision.reason)
                return tool_decision

        # 3. 高风险审批检查
        approval_decision = self._check_approval(context, policies)

        budget_remaining = context.budget_usd - context.cumulative_cost_usd

        return PolicyDecision(
            allowed=True,
            requires_approval=approval_decision.requires_approval,
            budget_remaining=budget_remaining,
        )

    async def _load_policies(self, tenant_id: str) -> list[Policy]:
        """加载租户的策略配置，按优先级降序。"""
        stmt = (
            select(Policy)
            .where(Policy.tenant_id == tenant_id, Policy.enabled.is_(True))
            .order_by(Policy.priority.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    def _check_budget(self, context: PolicyCheckContext, policies: list[Policy]) -> PolicyDecision:
        """检查预算上限。"""
        budget_policies = [p for p in policies if p.policy_type == PolicyType.BUDGET]
        budget_limit = context.budget_usd

        for p in budget_policies:
            if "max_budget_usd" in p.rule_json:
                budget_limit = min(budget_limit, p.rule_json["max_budget_usd"])

        if context.cumulative_cost_usd >= budget_limit:
            return PolicyDecision(
                allowed=False,
                reason=f"预算已耗尽: ${context.cumulative_cost_usd:.4f} / ${budget_limit:.4f}",
                budget_remaining=0.0,
            )

        return PolicyDecision(
            allowed=True,
            budget_remaining=budget_limit - context.cumulative_cost_usd,
        )

    async def _check_tool_whitelist(
        self, context: PolicyCheckContext, policies: list[Policy]
    ) -> PolicyDecision:
        """检查工具是否在白名单中，并验证权限。"""
        # 查找工具注册信息
        stmt = select(Tool).where(Tool.tool_name == context.tool_name, Tool.enabled.is_(True))
        result = await self._session.execute(stmt)
        tool = result.scalar_one_or_none()

        if tool is None:
            return PolicyDecision(
                allowed=False,
                reason=f"工具未注册或已禁用: {context.tool_name}",
            )

        # 检查白名单策略
        whitelist_policies = [p for p in policies if p.policy_type == PolicyType.TOOL_WHITELIST]
        for p in whitelist_policies:
            allowed_tools = p.rule_json.get("tools", [])
            if allowed_tools and context.tool_name not in allowed_tools:
                return PolicyDecision(
                    allowed=False,
                    reason=f"工具不在白名单中: {context.tool_name}",
                )

        # 检查工具所需权限
        if tool.permissions:
            required = tool.permissions if isinstance(tool.permissions, list) else []
            # MVP: 简化权限检查，后续对接 RBAC
            if required and context.role == "anonymous":
                return PolicyDecision(
                    allowed=False,
                    reason=f"权限不足: 需要 {required}",
                )

        return PolicyDecision(allowed=True)

    def _check_approval(self, context: PolicyCheckContext, policies: list[Policy]) -> PolicyDecision:
        """检查是否需要人工审批。"""
        approval_policies = [p for p in policies if p.policy_type == PolicyType.APPROVAL]

        # 按风险等级判定
        if context.risk_level == "high":
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                reason="高风险操作需要人工确认",
            )

        # 检查策略中是否强制要求审批
        for p in approval_policies:
            risk_levels = p.rule_json.get("require_approval_risk_levels", [])
            if context.risk_level in risk_levels:
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="策略要求人工确认",
                )

        return PolicyDecision(allowed=True, requires_approval=False)
