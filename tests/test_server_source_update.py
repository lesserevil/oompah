"""Tests for source-reference set/clear in PATCH /api/v1/issues/{identifier}.

Covers:
  - _strip_source_header: removes "Triggered by: X" prefix from description
  - PATCH source_task_id: sets "Triggered by: X" on a task without a source
  - PATCH source_task_id: replaces existing "Triggered by: X" header
  - PATCH clear_source=True: removes "Triggered by: X" from description
  - PATCH clear_source=True: no-op when description has no source header
  - PATCH source_task_id="": validation error (empty source not allowed)
  - PATCH source_task_id + description: description wins, source fields ignored
  - Server persists update through tracker.update_issue() (backend persistence)
  - Missing project/task identifier → 404 (existing behavior unchanged)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app, _strip_source_header
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Unit tests for _strip_source_header helper
# ---------------------------------------------------------------------------


class TestStripSourceHeader:
    def test_removes_triggered_by_prefix_with_body(self):
        desc = "Triggered by: TASK-42\n\nThe rest of the description."
        assert _strip_source_header(desc) == "The rest of the description."

    def test_removes_triggered_by_only_no_body(self):
        desc = "Triggered by: TASK-42"
        assert _strip_source_header(desc) == ""

    def test_removes_trailing_newline_after_header(self):
        desc = "Triggered by: TASK-42\n\n"
        assert _strip_source_header(desc) == ""

    def test_strips_leading_blank_lines_between_header_and_body(self):
        desc = "Triggered by: TASK-42\n\n\n\nBody text."
        assert _strip_source_header(desc) == "Body text."

    def test_no_header_returns_unchanged(self):
        desc = "Normal description without a source header."
        assert _strip_source_header(desc) == desc

    def test_empty_string_returns_empty(self):
        assert _strip_source_header("") == ""

    def test_does_not_remove_triggered_by_mid_description(self):
        """Only removes from the very start of the description."""
        desc = "Some intro.\n\nTriggered by: TASK-42\n\nMore text."
        assert _strip_source_header(desc) == desc

    def test_multiword_source_identifier_stripped_correctly(self):
        desc = "Triggered by: owner/repo#99\n\nBody."
        assert _strip_source_header(desc) == "Body."

    def test_idempotent_on_already_stripped_description(self):
        desc = "Just a plain description."
        assert _strip_source_header(desc) == desc


# ---------------------------------------------------------------------------
# Helpers for server integration tests
# ---------------------------------------------------------------------------


def _make_issue(
    identifier: str = "TASK-1",
    description: str = "",
    issue_type: str = "task",
    state: str = "open",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test task",
        state=state,
        issue_type=issue_type,
        description=description,
    )


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    mock_tracker = MagicMock()
    mock_tracker.update_issue = MagicMock()
    mock_tracker.close_issue = MagicMock()
    mock_tracker.mark_needs_human = MagicMock()
    mock_tracker.fetch_issue_detail = MagicMock()
    mock_tracker.fetch_children = MagicMock(return_value=[])

    mock_project = MagicMock()
    mock_project.id = project_id

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.list_all = MagicMock(return_value=[mock_project])
    mock_orch.config.tracker_terminal_states = ["closed"]
    mock_orch.state.running = {}
    mock_orch.state.retry_attempts = {}
    mock_orch.state.claimed = set()
    mock_orch.state.completed = set()

    return mock_orch, mock_tracker


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# PATCH /api/v1/issues/{identifier} — source_task_id (set/replace)
# ---------------------------------------------------------------------------


class TestPatchSetSource:
    """Server-side tests for setting the source reference via PATCH."""

    def test_set_source_on_task_without_existing_source(self, client):
        """PATCH with source_task_id on a task without a source adds the header."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Original description.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "source_task_id": "TASK-42",
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        mock_tracker.update_issue.assert_called_once()
        _id, kwargs = mock_tracker.update_issue.call_args.args[0], mock_tracker.update_issue.call_args.kwargs
        new_desc = kwargs.get("description", "")
        assert new_desc.startswith("Triggered by: TASK-42")
        assert "Original description." in new_desc

    def test_set_source_on_task_with_no_description(self, client):
        """PATCH with source_task_id on an empty-description task sets just the header."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "source_task_id": "TASK-99",
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        mock_tracker.update_issue.assert_called_once()
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        assert new_desc == "Triggered by: TASK-99"

    def test_replace_existing_source_header(self, client):
        """PATCH with a different source_task_id replaces the old 'Triggered by:' header."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Triggered by: OLD-SOURCE\n\nBody text.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "source_task_id": "NEW-SOURCE",
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        assert "NEW-SOURCE" in new_desc
        assert "OLD-SOURCE" not in new_desc
        assert "Body text." in new_desc

    def test_empty_source_task_id_returns_400(self, client):
        """PATCH with an empty source_task_id string must return 400."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Some description.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "source_task_id": "   ",  # whitespace only
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 400
        err = resp.json()["error"]
        assert err["code"] == "validation"
        assert "source_task_id" in err["message"].lower()
        mock_tracker.update_issue.assert_not_called()

    def test_description_wins_over_source_task_id(self, client):
        """When both description and source_task_id are provided, description wins."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Original.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "description": "Explicit description.",
                    "source_task_id": "TASK-99",
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        # Explicit description takes precedence; source_task_id is ignored.
        assert new_desc == "Explicit description."
        assert "TASK-99" not in new_desc


# ---------------------------------------------------------------------------
# PATCH /api/v1/issues/{identifier} — clear_source (remove)
# ---------------------------------------------------------------------------


class TestPatchClearSource:
    """Server-side tests for removing the source reference via PATCH."""

    def test_clear_source_removes_triggered_by_header(self, client):
        """PATCH with clear_source=True strips the 'Triggered by:' header."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Triggered by: TASK-42\n\nBody text.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "clear_source": True,
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        assert "Triggered by" not in new_desc
        assert "Body text." in new_desc

    def test_clear_source_noop_when_no_source_header(self, client):
        """clear_source=True on a task without a source is a clean no-op."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Plain description, no source.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "clear_source": True,
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        assert new_desc == "Plain description, no source."

    def test_clear_source_on_empty_description(self, client):
        """clear_source=True on an empty description leaves description empty."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "clear_source": True,
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        assert new_desc == ""

    def test_clear_source_only_no_status_change(self, client):
        """clear_source=True without status/title/priority only updates description."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Triggered by: TASK-42\n\nBody.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "clear_source": True,
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        mock_tracker.update_issue.assert_called_once()
        call_kwargs = mock_tracker.update_issue.call_args.kwargs
        # Only description should be in the update_fields, not status/title.
        assert "status" not in call_kwargs
        assert "title" not in call_kwargs
        assert "description" in call_kwargs

    def test_description_wins_over_clear_source(self, client):
        """When both description and clear_source are provided, description wins."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="TASK-1",
            description="Triggered by: TASK-42\n\nBody.",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-1",
                json={
                    "description": "My explicit description with Triggered by still here.",
                    "clear_source": True,
                    "project_id": "proj-1",
                },
            )

        assert resp.status_code == 200
        new_desc = mock_tracker.update_issue.call_args.kwargs.get("description", "")
        # explicit description wins
        assert new_desc == "My explicit description with Triggered by still here."


# ---------------------------------------------------------------------------
# Missing task / missing project → existing 404 behavior is unchanged
# ---------------------------------------------------------------------------


class TestPatchSourceMissingTask:
    """Confirm that missing task/project returns 404, not 500."""

    def test_missing_identifier_returns_404(self, client):
        """set-source on an unknown identifier returns 404."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = None

        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.patch(
                "/api/v1/issues/NONEXISTENT",
                json={
                    "source_task_id": "TASK-42",
                    # no project_id → searches all projects; returns none
                },
            )

        # Falls back to _find_tracker_for_issue; not found → 404.
        assert resp.status_code == 404
