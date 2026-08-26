"""Tests for shared scheduler-thread exception classification."""

from __future__ import annotations

from oompah.error_watcher import ErrorWatcher
from oompah.orchestrator_thread import (
    EXPECTED_SHUTDOWN_ERROR_CLASS,
    WORKFLOW_ROLLOUT_GATE_ERROR_CLASS,
    orchestrator_thread_error_fields,
)
from oompah.workflow_jobs import WorkflowRolloutGateError


def test_rollout_gate_rejection_has_distinct_error_watcher_class():
    message, extra = orchestrator_thread_error_fields(
        WorkflowRolloutGateError("review is not qualified")
    )

    assert message == "Workflow rollout gate rejected orchestrator startup"
    assert extra == {"error_class": WORKFLOW_ROLLOUT_GATE_ERROR_CLASS}


def test_unexpected_generic_scheduler_failure_keeps_crash_classification():
    message, extra = orchestrator_thread_error_fields(RuntimeError("boom"))

    assert message == "Orchestrator thread crashed"
    assert extra == {}


def test_expected_orchestrator_run_overlap_during_shutdown():
    message, extra = orchestrator_thread_error_fields(
        RuntimeError("orchestrator run overlap detected")
    )

    assert message == "Orchestrator run overlap detected (expected during shutdown)"
    assert extra == {"error_class": EXPECTED_SHUTDOWN_ERROR_CLASS}


def test_expected_restart_issue_conversion_incomplete():
    message, extra = orchestrator_thread_error_fields(
        RuntimeError("durable restart-issue conversion is incomplete")
    )

    assert message == "Durable restart-issue conversion incomplete (expected during shutdown)"
    assert extra == {"error_class": EXPECTED_SHUTDOWN_ERROR_CLASS}


def test_rollout_gate_fingerprint_is_distinct_and_shared_by_server_paths():
    watcher = object.__new__(ErrorWatcher)

    generic = watcher._fingerprint(
        "backend:__main__", "Orchestrator thread crashed"
    )
    uvicorn_rollout = watcher._fingerprint(
        "backend:__main__",
        "Workflow rollout gate rejected orchestrator startup",
        error_class=WORKFLOW_ROLLOUT_GATE_ERROR_CLASS,
    )
    granian_rollout = watcher._fingerprint(
        "backend:server",
        "Workflow rollout gate rejected orchestrator startup",
        error_class=WORKFLOW_ROLLOUT_GATE_ERROR_CLASS,
    )

    assert uvicorn_rollout != generic
    assert granian_rollout == uvicorn_rollout
