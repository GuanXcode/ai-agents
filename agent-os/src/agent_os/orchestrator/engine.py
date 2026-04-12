"""Orchestrator Engine — task lifecycle management and step execution loop."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.config import OrchestratorSettings
from agent_os.db.models.audit_log import AuditLog
from agent_os.db.models.cost_record import CostRecord
from agent_os.db.models.task import Task, TaskStatus
from agent_os.db.models.task_step import ActionType, StepStatus, TaskStep
from agent_os.gateway.schemas import TaskEnvelope
from agent_os.memory.interface import MemoryServiceInterface
from agent_os.model_router.interface import ModelRouterInterface
from agent_os.model_router.router import ModelUnavailableError
from agent_os.observability import metrics
from agent_os.orchestrator.interface import OrchestratorInterface
from agent_os.orchestrator.schemas import (
    ExecutionPlan,
    StepInput,
    StepOutput,
    TaskResult,
)
from agent_os.orchestrator.state_machine import can_transition
from agent_os.policy.interface import PolicyEngineInterface
from agent_os.policy.schemas import PolicyCheckContext
from agent_os.tool_runtime.interface import ToolRuntimeInterface
from agent_os.tool_runtime.schemas import ToolCallRequest

logger = structlog.get_logger(__name__)


class Orchestrator(OrchestratorInterface):
    def __init__(
        self,
        settings: OrchestratorSettings,
        model_router: ModelRouterInterface,
        tool_runtime: ToolRuntimeInterface,
        memory: MemoryServiceInterface,
        policy: PolicyEngineInterface,
        session: AsyncSession,
    ) -> None:
        self._settings = settings
        self._model_router = model_router
        self._tool_runtime = tool_runtime
        self._memory = memory
        self._policy = policy
        self._session = session

    async def submit_task(self, envelope: TaskEnvelope) -> str:
        """提交任务：创建 Task 记录，生成执行计划。"""
        task_id = uuid.uuid4()

        task = Task(
            task_id=task_id,
            tenant_id=envelope.tenant_id,
            user_id=envelope.user_id,
            status=TaskStatus.PENDING,
            goal=envelope.goal,
            constraints={
                "budget_usd": envelope.constraints.budget_usd,
                "deadline_sec": envelope.constraints.deadline_sec,
            },
            max_retries=self._settings.default_max_retries,
            timeout_sec=envelope.constraints.deadline_sec,
        )
        self._session.add(task)

        # 生成执行计划
        await self._transition_task(task, TaskStatus.PLANNING)

        plan = await self._generate_plan(envelope.goal, envelope.context_refs)

        # 保存计划到 task 和 task_steps
        task.plan = {"steps": [s.model_dump() for s in plan.steps], "summary": plan.summary}

        for i, step_input in enumerate(plan.steps):
            step = TaskStep(
                step_id=uuid.uuid4(),
                task_id=task_id,
                step_order=i,
                action_type=step_input.action_type,
                input=step_input.model_dump(),
                status=StepStatus.PENDING,
            )
            self._session.add(step)

        await self._transition_task(task, TaskStatus.WAITING_HUMAN)
        await self._session.commit()

        metrics.task_total.add(1, {"tenant_id": envelope.tenant_id})

        logger.info(
            "task_submitted",
            task_id=str(task_id),
            tenant_id=envelope.tenant_id,
            step_count=len(plan.steps),
        )
        return str(task_id)

    async def approve_plan(self, task_id: str) -> TaskResult:
        """批准计划，开始执行步骤。"""
        task = await self._get_task(task_id)
        if task is None:
            return TaskResult(task_id=task_id, status=TaskStatus.FAILED, error="任务不存在")

        await self._transition_task(task, TaskStatus.RUNNING)
        await self._session.commit()

        # 异步执行（MVP 中直接 await）
        result = await self._execute_steps(task)

        return result

    async def reject_plan(self, task_id: str, reason: str) -> None:
        """拒绝计划，标记取消。"""
        task = await self._get_task(task_id)
        if task is None:
            return

        await self._transition_task(task, TaskStatus.CANCELED)
        task.error_message = reason
        await self._session.commit()

        await self._audit_log(task_id, "task_canceled", detail={"reason": reason})
        logger.info("task_rejected", task_id=task_id, reason=reason)

    async def approve_step(self, task_id: str, step_id: str) -> None:
        """批准高风险步骤。MVP: 标记步骤为可执行。"""
        stmt = (
            update(TaskStep)
            .where(
                TaskStep.step_id == uuid.UUID(step_id),
                TaskStep.task_id == uuid.UUID(task_id),
            )
            .values(status=StepStatus.PENDING)
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.info("step_approved", task_id=task_id, step_id=step_id)

    async def get_task_status(self, task_id: str) -> TaskResult:
        """查询任务状态。"""
        task = await self._get_task(task_id)
        if task is None:
            return TaskResult(task_id=task_id, status=TaskStatus.FAILED, error="任务不存在")

        return TaskResult(
            task_id=str(task.task_id),
            status=task.status,
            result_summary=task.result_summary,
            total_cost_usd=float(task.cumulative_cost_usd),
            total_tokens=task.cumulative_tokens,
            error=task.error_message,
        )

    # ── 内部方法 ──

    async def _generate_plan(self, goal: str, context_refs: list[str]) -> ExecutionPlan:
        """调用 LLM 生成执行计划。"""
        plan_step = StepInput(
            action_type=ActionType.PLAN,
            instruction=(
                f"请为以下目标生成执行计划：\n{goal}\n\n"
                "输出格式：每行一个步骤，格式为 action_type: instruction\n"
                "action_type 可选: plan, reason, tool_call, human_gate\n"
                "如果是 tool_call，需注明 tool_name 和 tool_args。"
            ),
            context={"context_refs": context_refs},
        )

        try:
            response = await self._model_router.route(plan_step)
            return self._parse_plan(response.output)
        except ModelUnavailableError:
            logger.warning("plan_generation_failed_using_default")
            # Fallback: 简单两步计划
            return ExecutionPlan(
                steps=[
                    StepInput(action_type=ActionType.REASON, instruction=f"分析并完成目标: {goal}"),
                ],
                summary=f"简单计划: {goal}",
            )

    def _parse_plan(self, llm_output: str) -> ExecutionPlan:
        """解析 LLM 输出为 ExecutionPlan。MVP 使用简单格式解析。"""
        steps: list[StepInput] = []
        lines = [l.strip() for l in llm_output.strip().split("\n") if l.strip()]

        for line in lines:
            if ":" not in line:
                continue
            parts = line.split(":", 1)
            action_str = parts[0].strip().lower()
            instruction = parts[1].strip() if len(parts) > 1 else ""

            action_map = {
                "plan": ActionType.PLAN,
                "reason": ActionType.REASON,
                "tool_call": ActionType.TOOL_CALL,
                "human_gate": ActionType.HUMAN_GATE,
            }
            action_type = action_map.get(action_str, ActionType.REASON)

            step = StepInput(action_type=action_type, instruction=instruction)

            # 解析 tool_call 的工具名
            if action_type == ActionType.TOOL_CALL and "tool_name=" in instruction:
                try:
                    for segment in instruction.split(","):
                        kv = segment.strip().split("=", 1)
                        if kv[0].strip() == "tool_name":
                            step.tool_name = kv[1].strip()
                        elif kv[0].strip() == "tool_args":
                            step.tool_args = json.loads(kv[1].strip())
                except Exception:
                    pass

            steps.append(step)

        if not steps:
            steps.append(StepInput(action_type=ActionType.REASON, instruction=llm_output[:500]))

        return ExecutionPlan(steps=steps, summary=llm_output[:200])

    async def _execute_steps(self, task: Task) -> TaskResult:
        """执行任务的所有步骤。"""
        constraints = task.constraints or {}
        budget_usd = constraints.get("budget_usd", self._settings.default_budget_usd)

        # 加载上下文
        context = await self._memory.load_context(
            task_id=str(task.task_id),
            tenant_id=task.tenant_id,
            user_id=task.user_id,
            goal=task.goal,
        )
        context = await self._memory.compress_context(context, self._model_router)

        # 加载步骤
        stmt = (
            select(TaskStep)
            .where(TaskStep.task_id == task.task_id)
            .order_by(TaskStep.step_order)
        )
        result = await self._session.execute(stmt)
        steps = list(result.scalars().all())

        for step in steps:
            # 检查总超时
            if step.status == StepStatus.SUCCEEDED:
                continue  # 跳过已完成步骤（幂等）

            # 策略检查（含工具风险等级）
            tool_name = step.input.get("tool_name") if step.input else None
            risk_level: str | None = None
            if tool_name:
                tool_def = self._tool_runtime.get_tool(tool_name)
                if tool_def and tool_def.risk_level:
                    risk_level = tool_def.risk_level.value

            policy_ctx = PolicyCheckContext(
                task_id=str(task.task_id),
                tenant_id=task.tenant_id,
                user_id=task.user_id,
                role="executor",
                cumulative_cost_usd=float(task.cumulative_cost_usd),
                budget_usd=budget_usd,
                tool_name=tool_name,
                risk_level=risk_level,
            )
            decision = await self._policy.check(policy_ctx)
            if not decision.allowed:
                task.error_message = f"策略拒绝: {decision.reason}"
                await self._transition_task(task, TaskStatus.FAILED)
                await self._session.commit()
                return self._build_result(task)

            # 高风险步骤需人工确认
            if decision.requires_approval or step.action_type == ActionType.HUMAN_GATE:
                await self._transition_task(task, TaskStatus.WAITING_HUMAN)
                step.status = StepStatus.WAITING_APPROVAL
                await self._session.commit()
                await self._audit_log(
                    str(task.task_id),
                    "step_waiting_approval",
                    detail={"step_id": str(step.step_id), "step_order": step.step_order},
                )
                # MVP: 自动批准（生产环境应等待外部回调）
                await self.approve_step(str(task.task_id), str(step.step_id))
                await self._transition_task(task, TaskStatus.RUNNING)

            # 执行步骤
            step_output = await self._execute_step(task, step, context)

            # 持久化步骤结果
            await self._memory.save_step_result(str(task.task_id), step_output)

            # 将新结果追加到上下文并检查是否需要压缩
            context.short_term.append({
                "step_id": str(step_output.step_id),
                "action_type": step.action_type.value if step.action_type else "unknown",
                "output": step_output.result,
            })
            context = await self._memory.compress_context(context, self._model_router)

            # 更新任务累计成本
            task.cumulative_cost_usd = float(task.cumulative_cost_usd) + step_output.cost_usd
            task.cumulative_tokens = task.cumulative_tokens + step_output.cost_tokens

            # 记录成本
            await self._record_cost(task, step, step_output)

            # 处理失败
            if step_output.status == StepStatus.FAILED:
                if step.retry_count < task.max_retries:
                    step.retry_count += 1
                    step.status = StepStatus.PENDING
                    await self._transition_task(task, TaskStatus.RETRYING)
                    await self._session.commit()
                    logger.info("step_retrying", task_id=str(task.task_id), step_id=str(step.step_id), retry=step.retry_count)

                    await self._transition_task(task, TaskStatus.RUNNING)
                    # 重试
                    retry_output = await self._execute_step(task, step, context)
                    await self._memory.save_step_result(str(task.task_id), retry_output)
                    task.cumulative_cost_usd = float(task.cumulative_cost_usd) + retry_output.cost_usd
                    task.cumulative_tokens = task.cumulative_tokens + retry_output.cost_tokens

                    if retry_output.status == StepStatus.FAILED:
                        task.error_message = f"步骤 {step.step_order} 重试失败: {retry_output.error}"
                        await self._transition_task(task, TaskStatus.FAILED)
                        await self._session.commit()
                        metrics.task_failed.add(1, {"tenant_id": task.tenant_id})
                        return self._build_result(task)
                else:
                    task.error_message = f"步骤 {step.step_order} 失败: {step_output.error}"
                    await self._transition_task(task, TaskStatus.FAILED)
                    await self._session.commit()
                    metrics.task_failed.add(1, {"tenant_id": task.tenant_id})
                    return self._build_result(task)

            await self._session.commit()

        # 全部步骤完成
        task.result_summary = f"任务完成，共 {len(steps)} 个步骤"
        await self._transition_task(task, TaskStatus.SUCCEEDED)
        await self._memory.archive_task(str(task.task_id))
        await self._session.commit()

        metrics.task_success.add(1, {"tenant_id": task.tenant_id})
        logger.info("task_succeeded", task_id=str(task.task_id), cost=float(task.cumulative_cost_usd))
        return self._build_result(task)

    async def _execute_step(self, task: Task, step: TaskStep, context) -> StepOutput:
        """执行单个步骤。"""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now(timezone.utc)
        await self._session.commit()

        input_data = step.input or {}
        instruction = input_data.get("instruction", "")
        action_type = step.action_type

        try:
            if action_type == ActionType.TOOL_CALL:
                result = await self._execute_tool_step(task, step, input_data)
            else:
                # plan / reason / human_gate → LLM 推理
                result = await self._execute_reason_step(task, step, instruction, context)

            step.status = result.status  # 以实际执行结果为准，不无条件覆盖
            return result

        except Exception as e:
            logger.error("step_execution_error", task_id=str(task.task_id), step_id=str(step.step_id), error=str(e))
            step.status = StepStatus.FAILED
            return StepOutput(
                step_id=str(step.step_id),
                status=StepStatus.FAILED,
                error=str(e),
            )

    async def _execute_reason_step(
        self, task: Task, step: TaskStep, instruction: str, context
    ) -> StepOutput:
        """调用模型执行推理步骤。"""
        step_input = StepInput(
            action_type=step.action_type,
            instruction=instruction,
            context={"system_prompt": "", "history": [h for h in context.short_term[-5:]]},
        )
        response = await self._model_router.route(step_input, context={"goal": task.goal})

        return StepOutput(
            step_id=str(step.step_id),
            status=StepStatus.SUCCEEDED,
            result={"output": response.output},
            cost_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
        )

    async def _execute_tool_step(
        self, task: Task, step: TaskStep, input_data: dict
    ) -> StepOutput:
        """执行工具调用步骤。"""
        constraints = task.constraints or {}
        tool_call = ToolCallRequest(
            tool_name=input_data.get("tool_name", ""),
            args=input_data.get("tool_args", {}),
            task_id=str(task.task_id),
            tenant_id=task.tenant_id,
            user_id=task.user_id,
            role="executor",
            budget_usd=constraints.get("budget_usd", self._settings.default_budget_usd),
        )
        tool_result = await self._tool_runtime.execute(tool_call)

        status = StepStatus.SUCCEEDED if tool_result.status == "succeeded" else StepStatus.FAILED
        return StepOutput(
            step_id=str(step.step_id),
            status=status,
            result=tool_result.output,
            error=tool_result.error,
        )

    async def _get_task(self, task_id: str) -> Task | None:
        stmt = select(Task).where(Task.task_id == uuid.UUID(task_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _transition_task(self, task: Task, target: TaskStatus) -> None:
        if not can_transition(task.status, target):
            raise ValueError(f"非法状态转换: {task.status.value} -> {target.value}")
        old_status = task.status
        task.status = target
        task.updated_at = datetime.now(timezone.utc)
        logger.info("task_status_changed", task_id=str(task.task_id), from_status=old_status.value, to_status=target.value)

    def _build_result(self, task: Task) -> TaskResult:
        return TaskResult(
            task_id=str(task.task_id),
            status=task.status,
            result_summary=task.result_summary,
            total_cost_usd=float(task.cumulative_cost_usd),
            total_tokens=task.cumulative_tokens,
            error=task.error_message,
        )

    async def _record_cost(self, task: Task, step: TaskStep, output: StepOutput) -> None:
        """记录步骤成本。"""
        record = CostRecord(
            record_id=uuid.uuid4(),
            task_id=task.task_id,
            step_id=step.step_id,
            model_name=step.model_name,
            total_tokens=output.cost_tokens,
            cost_usd=output.cost_usd,
        )
        self._session.add(record)
        metrics.model_cost.record(output.cost_usd, {"task_id": str(task.task_id)})

    async def _audit_log(self, task_id: str, event_type: str, detail: dict | None = None) -> None:
        """记录审计日志。"""
        log = AuditLog(
            log_id=uuid.uuid4(),
            task_id=uuid.UUID(task_id),
            event_type=event_type,
            detail=detail,
        )
        self._session.add(log)
        await self._session.commit()
