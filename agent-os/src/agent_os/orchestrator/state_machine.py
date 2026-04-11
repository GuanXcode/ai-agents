"""Task state machine — defines valid transitions."""

from __future__ import annotations

from agent_os.db.models.task import TaskStatus

# 合法状态转换表
TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.PLANNING},
    TaskStatus.PLANNING: {TaskStatus.WAITING_HUMAN, TaskStatus.FAILED},
    TaskStatus.WAITING_HUMAN: {TaskStatus.RUNNING, TaskStatus.CANCELED},
    TaskStatus.RUNNING: {TaskStatus.WAITING_HUMAN, TaskStatus.SUCCEEDED, TaskStatus.RETRYING, TaskStatus.TIMEOUT},
    TaskStatus.RETRYING: {TaskStatus.RUNNING, TaskStatus.FAILED},
    TaskStatus.TIMEOUT: {TaskStatus.FAILED},
    # 终态
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELED: set(),
}


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in TRANSITIONS.get(current, set())
