"""State machine transition tests."""

from agent_os.db.models.task import TaskStatus
from agent_os.orchestrator.state_machine import can_transition


class TestStateMachine:
    def test_pending_to_planning(self):
        assert can_transition(TaskStatus.PENDING, TaskStatus.PLANNING)

    def test_planning_to_waiting_human(self):
        assert can_transition(TaskStatus.PLANNING, TaskStatus.WAITING_HUMAN)

    def test_planning_to_failed(self):
        assert can_transition(TaskStatus.PLANNING, TaskStatus.FAILED)

    def test_waiting_human_to_running(self):
        assert can_transition(TaskStatus.WAITING_HUMAN, TaskStatus.RUNNING)

    def test_waiting_human_to_canceled(self):
        assert can_transition(TaskStatus.WAITING_HUMAN, TaskStatus.CANCELED)

    def test_running_to_retrying(self):
        assert can_transition(TaskStatus.RUNNING, TaskStatus.RETRYING)

    def test_running_to_succeeded(self):
        assert can_transition(TaskStatus.RUNNING, TaskStatus.SUCCEEDED)

    def test_running_to_timeout(self):
        assert can_transition(TaskStatus.RUNNING, TaskStatus.TIMEOUT)

    def test_retrying_to_failed(self):
        assert can_transition(TaskStatus.RETRYING, TaskStatus.FAILED)

    def test_terminal_states_have_no_transitions(self):
        assert not can_transition(TaskStatus.SUCCEEDED, TaskStatus.RUNNING)
        assert not can_transition(TaskStatus.FAILED, TaskStatus.RUNNING)
        assert not can_transition(TaskStatus.CANCELED, TaskStatus.RUNNING)

    def test_invalid_transition(self):
        assert not can_transition(TaskStatus.PENDING, TaskStatus.SUCCEEDED)
