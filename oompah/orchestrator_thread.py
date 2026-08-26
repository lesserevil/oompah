"""Shared exception classification for the scheduler's dedicated thread."""

from __future__ import annotations

from oompah.workflow_jobs import WorkflowRolloutGateError


WORKFLOW_ROLLOUT_GATE_ERROR_CLASS = "workflow_rollout_gate_rejected"
EXPECTED_SHUTDOWN_ERROR_CLASS = "expected_shutdown"


def orchestrator_thread_error_fields(
    error: BaseException,
) -> tuple[str, dict[str, str]]:
    """Return stable log fields without changing the caller's source module.
    
    Classifies exceptions to distinguish between:
    - Expected failures (graceful shutdown, known handled errors)
    - Unexpected crashes (actual bugs that need investigation)
    
    The log level in the caller should match the error class:
    - expected_shutdown: INFO (not an error, just shutdown)
    - workflow_rollout_gate_rejected: WARNING (validation failure, not a crash)
    - Other: ERROR (unexpected crash needing investigation)
    """

    if isinstance(error, WorkflowRolloutGateError):
        return (
            "Workflow rollout gate rejected orchestrator startup",
            {"error_class": WORKFLOW_ROLLOUT_GATE_ERROR_CLASS},
        )
    
    # RuntimeError for orchestrator run overlap or incomplete restart conversion
    # during shutdown is expected and should not trigger error_watcher
    if isinstance(error, RuntimeError):
        msg = str(error)
        if "orchestrator run overlap detected" in msg:
            return (
                "Orchestrator run overlap detected (expected during shutdown)",
                {"error_class": EXPECTED_SHUTDOWN_ERROR_CLASS},
            )
        if "durable restart-issue conversion is incomplete" in msg:
            return (
                "Durable restart-issue conversion incomplete (expected during shutdown)",
                {"error_class": EXPECTED_SHUTDOWN_ERROR_CLASS},
            )
    
    return "Orchestrator thread crashed", {}
