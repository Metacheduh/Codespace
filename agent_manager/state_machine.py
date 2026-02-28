"""
Deterministic job state machine.

Valid states:  pending  →  running  →  succeeded
                                    →  failed  →  pending  (retry)

Transitions are explicit and rule-based.  No LLM involvement.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# Allowed (from_state → to_state) transitions
_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PENDING: frozenset({JobState.RUNNING}),
    JobState.RUNNING: frozenset({JobState.SUCCEEDED, JobState.FAILED}),
    JobState.FAILED: frozenset({JobState.PENDING}),  # retry
    JobState.SUCCEEDED: frozenset(),  # terminal
}


class Transition(NamedTuple):
    from_state: JobState
    to_state: JobState
    reason: str


class InvalidTransitionError(Exception):
    """Raised when a state transition violates the state machine rules."""


def validate_transition(from_state: JobState, to_state: JobState) -> None:
    """Raise InvalidTransitionError if the transition is not allowed."""
    allowed = _TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        raise InvalidTransitionError(
            f"Transition {from_state.value!r} → {to_state.value!r} is not allowed. "
            f"Allowed from {from_state.value!r}: {sorted(s.value for s in allowed)}"
        )


def transition(from_state: JobState, to_state: JobState, reason: str) -> Transition:
    """Create a validated state transition."""
    validate_transition(from_state, to_state)
    return Transition(from_state=from_state, to_state=to_state, reason=reason)


def can_retry(state: JobState) -> bool:
    """Return True if the job is in a state that allows retrying (failed → pending)."""
    return state == JobState.FAILED
