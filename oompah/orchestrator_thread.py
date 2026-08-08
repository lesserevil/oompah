"""Shared exception classification for the scheduler's dedicated thread."""

from __future__ import annotations

from oompah.workflow_jobs import WorkflowRolloutGateError


WORKFLOW_ROLLOUT_GATE_ERROR_CLASS = "workflow_rollout_gate_rejected"


def orchestrator_thread_error_fields(
    error: BaseException,
) -> tuple[str, dict[str, str]]:
    """Return stable log fields without changing the caller's source module."""

    if isinstance(error, WorkflowRolloutGateError):
        return (
            "Workflow rollout gate rejected orchestrator startup",
            {"error_class": WORKFLOW_ROLLOUT_GATE_ERROR_CLASS},
        )
    return "Orchestrator thread crashed", {}
