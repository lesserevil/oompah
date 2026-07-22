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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
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


# ---------------------------------------------------------------------------
# Server-side: api_update_issue must log WARNING not ERROR for fetch failures
# ---------------------------------------------------------------------------


class TestUpdateIssueApiStateBranchFetchError:
    """PATCH /api/v1/issues/{identifier} must not trigger error_watcher on fetch failure."""

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
