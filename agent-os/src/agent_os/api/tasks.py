"""Task API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from agent_os.api.deps import get_orchestrator
from agent_os.gateway.schemas import TaskConstraints, TaskEnvelope, TaskRequest
from agent_os.orchestrator.interface import OrchestratorInterface
from agent_os.orchestrator.schemas import TaskResult

router = APIRouter(tags=["tasks"])


@router.post("/tasks", response_model=dict, status_code=201)
async def submit_task(
    body: TaskRequest,
    request: Request,
    orchestrator: OrchestratorInterface = Depends(get_orchestrator),
) -> dict:
    """提交新任务。"""
    envelope = TaskEnvelope(
        tenant_id=request.state.tenant_id,
        user_id=request.state.user_id,
        goal=body.goal,
        constraints=body.constraints,
        context_refs=body.context_refs,
    )
    task_id = await orchestrator.submit_task(envelope)
    return {"task_id": task_id, "status": "PENDING"}


@router.get("/tasks/{task_id}", response_model=TaskResult)
async def get_task_status(
    task_id: str,
    orchestrator: OrchestratorInterface = Depends(get_orchestrator),
) -> TaskResult:
    """查询任务状态。"""
    return await orchestrator.get_task_status(task_id)


@router.post("/tasks/{task_id}/approve", response_model=TaskResult)
async def approve_plan(
    task_id: str,
    orchestrator: OrchestratorInterface = Depends(get_orchestrator),
) -> TaskResult:
    """批准执行计划。"""
    return await orchestrator.approve_plan(task_id)


@router.post("/tasks/{task_id}/reject", status_code=200)
async def reject_plan(
    task_id: str,
    reason: str = "",
    orchestrator: OrchestratorInterface = Depends(get_orchestrator),
) -> dict:
    """拒绝执行计划。"""
    await orchestrator.reject_plan(task_id, reason)
    return {"task_id": task_id, "status": "CANCELED"}


@router.post("/tasks/{task_id}/steps/{step_id}/approve", status_code=200)
async def approve_step(
    task_id: str,
    step_id: str,
    orchestrator: OrchestratorInterface = Depends(get_orchestrator),
) -> dict:
    """批准高风险步骤。"""
    await orchestrator.approve_step(task_id, step_id)
    return {"task_id": task_id, "step_id": step_id, "status": "APPROVED"}
