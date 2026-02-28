"""Tests for the deterministic job state machine."""

import pytest

from agent_manager.state_machine import (
    InvalidTransitionError,
    JobState,
    can_retry,
    transition,
    validate_transition,
)


class TestValidTransitions:
    def test_pending_to_running(self):
        t = transition(JobState.PENDING, JobState.RUNNING, reason="start")
        assert t.from_state == JobState.PENDING
        assert t.to_state == JobState.RUNNING

    def test_running_to_succeeded(self):
        t = transition(JobState.RUNNING, JobState.SUCCEEDED, reason="done")
        assert t.to_state == JobState.SUCCEEDED

    def test_running_to_failed(self):
        t = transition(JobState.RUNNING, JobState.FAILED, reason="error")
        assert t.to_state == JobState.FAILED

    def test_failed_to_pending_retry(self):
        t = transition(JobState.FAILED, JobState.PENDING, reason="retry")
        assert t.to_state == JobState.PENDING


class TestInvalidTransitions:
    def test_pending_to_succeeded(self):
        with pytest.raises(InvalidTransitionError):
            transition(JobState.PENDING, JobState.SUCCEEDED, reason="skip")

    def test_pending_to_failed(self):
        with pytest.raises(InvalidTransitionError):
            transition(JobState.PENDING, JobState.FAILED, reason="skip")

    def test_succeeded_to_running(self):
        with pytest.raises(InvalidTransitionError):
            transition(JobState.SUCCEEDED, JobState.RUNNING, reason="re-run")

    def test_succeeded_to_pending(self):
        with pytest.raises(InvalidTransitionError):
            transition(JobState.SUCCEEDED, JobState.PENDING, reason="reset")

    def test_failed_to_succeeded(self):
        with pytest.raises(InvalidTransitionError):
            transition(JobState.FAILED, JobState.SUCCEEDED, reason="magic")


class TestCanRetry:
    def test_failed_can_retry(self):
        assert can_retry(JobState.FAILED) is True

    def test_succeeded_cannot_retry(self):
        assert can_retry(JobState.SUCCEEDED) is False

    def test_running_cannot_retry(self):
        assert can_retry(JobState.RUNNING) is False

    def test_pending_cannot_retry(self):
        assert can_retry(JobState.PENDING) is False
