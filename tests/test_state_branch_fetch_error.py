"""Regression tests for OOMPAH-345: StateBranchFetchError must not trigger error_watcher.

When git fetch fails while syncing the state branch during an issue update,
the server must log at WARNING (not ERROR) so that error_watcher does not
auto-file a new bug task, creating a feedback loop.

Root cause: _sync_state_branch_from_remote() in oompah_md_tracker.py raised
a generic TrackerError on git fetch failure.  The Update issue API handler
in server.py caught Exception and logged at ERROR, which error_watcher
picked up and filed as OOMPAH-345.

Fix: raise StateBranchFetchError (a TrackerError subclass) so the server can
catch it separately and log at WARNING instead.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.orchestrator import TaskTransitionNotApplied
from oompah.server import app
from oompah.task_transition_service import (
    TransitionDisposition,
    TransitionOutcome,
)
from oompah.tracker import StateBranchFetchError, TrackerError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(
    project_id: str = "proj-test",
    raise_on_update: Exception | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Build a minimal mock Orchestrator with a stub tracker."""
    mock_tracker = MagicMock()
    if raise_on_update is not None:
        mock_tracker.update_issue = MagicMock(side_effect=raise_on_update)
    else:
        mock_tracker.update_issue = MagicMock()

    mock_tracker.fetch_issue_detail = MagicMock(
        return_value=MagicMock(
            id="OOMPAH-1",
            identifier="OOMPAH-1",
            title="Test issue",
            state="open",
            issue_type="task",
            labels=[],
            priority=None,
        )
    )

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.name = "Test Project"

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    if raise_on_update is not None:
        failed_outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id=project_id,
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.RETRYABLE,
            reason_code="transition.tracker_write_failed",
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
            retryable=True,
            details={"error_type": type(raise_on_update).__name__},
        )
        mock_orch._transition_issue_status = MagicMock(
            side_effect=TaskTransitionNotApplied(failed_outcome)
        )
    else:
        mock_orch._transition_issue_status = MagicMock()
    mock_orch.config = MagicMock()
    mock_orch.config.tracker_terminal_states = []
    mock_orch.state = MagicMock()
    mock_orch.state.running = {}
    mock_orch.state.retry_attempts = {}
    mock_orch.project_store = MagicMock()
    mock_orch.project_store.get = MagicMock(return_value=mock_project)

    return mock_orch, mock_tracker


@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestStateBranchFetchErrorHierarchy:
    """StateBranchFetchError class and alias must satisfy the hierarchy contract."""

    def test_is_tracker_error_subclass(self):
        """StateBranchFetchError must be a TrackerError subclass for back-compat."""
        from oompah.tracker import StateBranchFetchError, TrackerError

        assert issubclass(StateBranchFetchError, TrackerError)

    def test_alias_resolves_correctly(self):
        """TrackerStateBranchFetchError alias must resolve to StateBranchFetchError."""
        from oompah.tracker import StateBranchFetchError, TrackerStateBranchFetchError

        assert TrackerStateBranchFetchError is StateBranchFetchError

    def test_instantiation_with_message(self):
        """StateBranchFetchError must carry the error message through."""
        exc = StateBranchFetchError("fetch failed: network unreachable")
        assert "fetch failed" in str(exc)

    def test_caught_as_tracker_error(self):
        """StateBranchFetchError instances must be caught by except TrackerError."""
        with pytest.raises(TrackerError):
            raise StateBranchFetchError("transient network error")

    def test_distinct_from_state_branch_missing_error(self):
        """StateBranchFetchError must be a distinct type from StateBranchMissingError."""
        from oompah.tracker import StateBranchFetchError, StateBranchMissingError

        assert StateBranchFetchError is not StateBranchMissingError
        assert not issubclass(StateBranchFetchError, StateBranchMissingError)
        assert not issubclass(StateBranchMissingError, StateBranchFetchError)


# ---------------------------------------------------------------------------
# Orchestrator error classification
# ---------------------------------------------------------------------------


class TestErrorClassForStateBranchFetchError:
    """_error_class_for_tracker_exc must classify StateBranchFetchError correctly."""

    def test_classified_as_tracker_state_branch_fetch(self):
        """StateBranchFetchError maps to 'tracker_state_branch_fetch' class.

        This ensures error_watcher dedup groups all fetch failures under one
        class rather than treating them as generic 'tracker_failed' failures.
        """
        from oompah.orchestrator import _error_class_for_tracker_exc

        exc = StateBranchFetchError("git fetch origin failed")
        assert _error_class_for_tracker_exc(exc) == "tracker_state_branch_fetch"

    def test_distinct_from_state_branch_missing_class(self):
        """StateBranchFetchError and StateBranchMissingError must map to different classes."""
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.tracker import StateBranchMissingError

        fetch_class = _error_class_for_tracker_exc(StateBranchFetchError("x"))
        missing_class = _error_class_for_tracker_exc(StateBranchMissingError("x"))
        assert fetch_class != missing_class

    def test_distinct_from_generic_tracker_failed(self):
        """StateBranchFetchError must not map to the generic 'tracker_failed' class."""
        from oompah.orchestrator import _error_class_for_tracker_exc

        exc = StateBranchFetchError("x")
        assert _error_class_for_tracker_exc(exc) != "tracker_failed"


class TestDurableTransitionErrorClassification:
    @pytest.mark.parametrize(
        "reason_code",
        [
            "transition.tracker_read_failed",
            "transition.tracker_write_failed",
        ],
    )
    def test_recovers_redacted_tracker_type_for_transport_failures(
        self,
        reason_code: str,
    ) -> None:
        outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.RETRYABLE,
            reason_code=reason_code,
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
            retryable=True,
            details={"error_type": StateBranchFetchError.__name__},
        )

        assert server_module._transition_tracker_error_type(
            TaskTransitionNotApplied(outcome)
        ) == StateBranchFetchError.__name__

    def test_does_not_reclassify_nontransport_transition_rejection(self) -> None:
        outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code="transition.head_mismatch",
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
            details={"error_type": StateBranchFetchError.__name__},
        )

        assert (
            server_module._transition_tracker_error_type(
                TaskTransitionNotApplied(outcome)
            )
            is None
        )

    @pytest.mark.parametrize(
        "reason_code",
        ["transition.owner_active", "transition.recovery_required"],
    )
    def test_classifies_expected_transition_waiting(
        self,
        reason_code: str,
    ) -> None:
        outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.WAITING,
            reason_code=reason_code,
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
            retryable=True,
        )

        assert (
            server_module._transition_waiting_reason(
                TaskTransitionNotApplied(outcome)
            )
            == reason_code
        )

    @pytest.mark.parametrize(
        "reason_code",
        [
            "transition.illegal_edge",
            "transition.generation_required",
            "transition.head_mismatch",
        ],
    )
    def test_classifies_expected_transition_rejection(
        self,
        reason_code: str,
    ) -> None:
        outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code=reason_code,
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
        )

        assert (
            server_module._transition_rejected_reason(
                TaskTransitionNotApplied(outcome)
            )
            == reason_code
        )

    @pytest.mark.parametrize(
        "reason_code",
        ["transition.terminal_rejected", "transition.future_operational_failure"],
    )
    def test_does_not_classify_operational_rejection_as_expected_policy(
        self,
        reason_code: str,
    ) -> None:
        outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code=reason_code,
            observed_status="Open",
            observed_version=None,
            requested_status="Done",
        )

        assert (
            server_module._transition_rejected_reason(
                TaskTransitionNotApplied(outcome)
            )
            is None
        )

    def test_classifies_direct_validation_as_expected_policy(self) -> None:
        outcome = TransitionOutcome(
            transition_id="transition-1",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code="transition.audit_staging_required",
            observed_status="In Progress",
            observed_version=None,
            requested_status="In Validation",
        )

        assert server_module._transition_rejected_reason(
            TaskTransitionNotApplied(outcome)
        ) == "transition.audit_staging_required"


# ---------------------------------------------------------------------------
# Server-side: api_update_issue must log WARNING not ERROR for fetch failures
# ---------------------------------------------------------------------------


class TestUpdateIssueApiStateBranchFetchError:
    """PATCH /api/v1/issues/{identifier} must not trigger error_watcher on fetch failure."""

    @pytest.mark.parametrize(
        "reason_code",
        ["transition.owner_active", "transition.recovery_required"],
    )
    def test_transition_waiting_returns_conflict_without_error_log(
        self,
        client,
        caplog,
        reason_code: str,
    ) -> None:
        orch, _tracker = _make_mock_orchestrator()
        outcome = TransitionOutcome(
            transition_id="transition-waiting",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.WAITING,
            reason_code=reason_code,
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
            retryable=True,
        )
        orch._transition_issue_status.side_effect = TaskTransitionNotApplied(outcome)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            caplog.at_level(logging.WARNING, logger="oompah.server"),
        ):
            response = client.patch(
                "/api/v1/issues/OOMPAH-1",
                json={"status": "In Progress", "project_id": "proj-test"},
            )

        assert response.status_code == 409
        assert response.json()["error"]["reason"] == reason_code
        assert not [
            record
            for record in caplog.records
            if record.name == "oompah.server" and record.levelno >= logging.ERROR
        ]

    @pytest.mark.parametrize(
        "reason_code",
        [
            "transition.direct_owner_claim_authority_required",
            "transition.generation_required",
            "transition.head_mismatch",
            "transition.illegal_edge",
            "transition.owner_claim_authority_unavailable",
            "transition.project_owner_authority_required",
            "transition.validation_submission_authority_required",
        ],
    )
    def test_transition_rejection_returns_conflict_without_warning_or_error(
        self,
        client,
        caplog,
        reason_code: str,
    ) -> None:
        orch, _tracker = _make_mock_orchestrator()
        outcome = TransitionOutcome(
            transition_id="transition-rejected",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code=reason_code,
            observed_status="Open",
            observed_version=None,
            requested_status="In Progress",
        )
        orch._transition_issue_status.side_effect = TaskTransitionNotApplied(outcome)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            caplog.at_level(logging.INFO, logger="oompah.server"),
        ):
            response = client.patch(
                "/api/v1/issues/OOMPAH-1",
                json={"status": "In Progress", "project_id": "proj-test"},
            )

        assert response.status_code == 409
        assert response.json()["error"] == {
            "code": "transition_rejected",
            "message": (
                f"OOMPAH-1: In Progress was not applied "
                f"(rejected: {reason_code})"
            ),
            "reason": reason_code,
        }
        assert [
            record
            for record in caplog.records
            if record.name == "oompah.server"
            and record.levelno == logging.INFO
            and "rejected by durable transition" in record.message
        ]
        assert not [
            record
            for record in caplog.records
            if record.name == "oompah.server" and record.levelno >= logging.WARNING
        ]

    @pytest.mark.parametrize("enforce", [False, True], ids=["legacy", "enforce"])
    def test_direct_validation_rejection_is_actionable_and_atomic(
        self,
        client,
        caplog,
        enforce,
    ) -> None:
        orch, tracker = _make_mock_orchestrator()
        orch.workflow_runtime = SimpleNamespace(enforce=enforce)
        tracker.fetch_issue_detail.return_value.state = "In Progress"
        outcome = TransitionOutcome(
            transition_id="transition-audit-staging-required",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code="transition.audit_staging_required",
            observed_status="In Progress",
            observed_version=None,
            requested_status="In Validation",
        )
        orch._transition_issue_status.side_effect = TaskTransitionNotApplied(outcome)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(
                server_module,
                "_cancel_retry_for_authority_change",
                wraps=server_module._cancel_retry_for_authority_change,
            ) as cancel_authority,
            caplog.at_level(logging.INFO, logger="oompah.server"),
        ):
            response = client.patch(
                "/api/v1/issues/OOMPAH-1",
                json={
                    "status": "In Validation",
                    "title": "must not commit",
                    "project_id": "proj-test",
                },
            )

        assert response.status_code == 409
        assert response.json()["error"] == {
            "code": "transition_rejected",
            "message": (
                "In Validation is owned by the terminal-audit coordinator and "
                "cannot be set directly. Request Done, Merged, or Archived "
                "instead (or use `oompah task submit` for completed work) so "
                "Oompah stages the audit atomically."
            ),
            "reason": "transition.audit_staging_required",
        }
        tracker.update_issue.assert_not_called()
        cancel_authority.assert_not_called()
        orch._transition_issue_status.assert_not_called()
        orch._cancel_retry_for_issue.assert_not_called()
        orch._schedule_implementation_workflow_event.assert_not_called()
        assert not [
            record
            for record in caplog.records
            if record.name == "oompah.server" and record.levelno >= logging.WARNING
        ]

    def test_operational_terminal_rejection_remains_server_error(
        self,
        client,
        caplog,
    ) -> None:
        orch, _tracker = _make_mock_orchestrator()
        outcome = TransitionOutcome(
            transition_id="transition-terminal-failed",
            project_id="proj-test",
            task_id="OOMPAH-1",
            disposition=TransitionDisposition.REJECTED,
            reason_code="transition.terminal_rejected",
            observed_status="Open",
            observed_version=None,
            requested_status="Done",
            details={"detail": "terminal evidence was unavailable"},
        )
        orch._transition_issue_status.side_effect = TaskTransitionNotApplied(outcome)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            caplog.at_level(logging.ERROR, logger="oompah.server"),
        ):
            response = client.patch(
                "/api/v1/issues/OOMPAH-1",
                json={"status": "In Progress", "project_id": "proj-test"},
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "update_failed"
        assert [
            record
            for record in caplog.records
            if record.name == "oompah.server"
            and record.levelno >= logging.ERROR
            and "update issue api error" in record.message.lower()
        ]

    def test_state_branch_fetch_error_returns_503(self, client, caplog):
        """A StateBranchFetchError during update returns 503, not 500."""
        fetch_exc = StateBranchFetchError(
            "Cannot sync state branch 'oompah/state/proj-abc': "
            "git fetch origin 'oompah/state/proj-abc' failed: network unreachable. "
            "Remediation: verify network access and remote URL."
        )
        mock_orch, mock_tracker = _make_mock_orchestrator(raise_on_update=fetch_exc)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            caplog.at_level(logging.WARNING, logger="oompah"),
        ):
            resp = client.patch(
                "/api/v1/issues/OOMPAH-1",
                json={"status": "In Progress", "project_id": "proj-test"},
            )

        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "state_branch_fetch_failed"

    def test_state_branch_fetch_error_logs_warning_not_error(self, client, caplog):
        """A StateBranchFetchError during update must be logged at WARNING, not ERROR.

        This is the core regression: if this logs at ERROR, error_watcher
        files a new bug task, creating the OOMPAH-345 feedback loop.
        """
        fetch_exc = StateBranchFetchError(
            "Cannot sync state branch 'oompah/state/proj-abc': "
            "git fetch origin 'oompah/state/proj-abc' failed: connection timeout. "
            "Remediation: verify network access and remote URL."
        )
        mock_orch, mock_tracker = _make_mock_orchestrator(raise_on_update=fetch_exc)

        error_records: list[logging.LogRecord] = []
        warning_records: list[logging.LogRecord] = []

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            with caplog.at_level(logging.WARNING, logger="oompah"):
                client.patch(
                    "/api/v1/issues/OOMPAH-1",
                    json={"status": "In Progress", "project_id": "proj-test"},
                )
                for record in caplog.records:
                    if "state_branch" in record.message.lower() or "sync" in record.message.lower() or "fetch" in record.message.lower():
                        if record.levelno >= logging.ERROR:
                            error_records.append(record)
                        elif record.levelno == logging.WARNING:
                            warning_records.append(record)

        assert not error_records, (
            "StateBranchFetchError must NOT be logged at ERROR — "
            "that triggers error_watcher. Got ERROR records: "
            + str([r.message for r in error_records])
        )
        assert warning_records, (
            "StateBranchFetchError must be logged at WARNING. "
            "No WARNING records found mentioning fetch/sync."
        )

    def test_generic_tracker_error_still_logs_error(self, client, caplog):
        """A generic TrackerError must still be logged at ERROR (no regression)."""
        generic_exc = TrackerError("Something unexpected went wrong")
        mock_orch, mock_tracker = _make_mock_orchestrator(raise_on_update=generic_exc)

        error_records: list[logging.LogRecord] = []

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            with caplog.at_level(logging.WARNING, logger="oompah"):
                client.patch(
                    "/api/v1/issues/OOMPAH-1",
                    json={"status": "In Progress", "project_id": "proj-test"},
                )
                for record in caplog.records:
                    if "update issue api error" in record.message.lower():
                        if record.levelno >= logging.ERROR:
                            error_records.append(record)

        assert error_records, (
            "Generic TrackerError must still be logged at ERROR so error_watcher "
            "catches real failures."
        )

    def test_generic_exception_still_returns_500(self, client):
        """A non-TrackerError exception must still return 500 (no regression)."""
        generic_exc = RuntimeError("unexpected failure")
        mock_orch, mock_tracker = _make_mock_orchestrator(raise_on_update=generic_exc)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/OOMPAH-1",
                json={"status": "In Progress", "project_id": "proj-test"},
            )

        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["code"] == "update_failed"
