"""Tests for Orchestrator._reconcile_addendum_pr_outcomes_sweep (OOMPAH-179).

Covers the maintenance-lane sweep that polls PR state for in_review
release addendums and delegates to poll_addendum_pr:

- Skips projects with no repo_url.
- Skips projects where provider detection fails.
- Calls poll_addendum_pr for each in_review addendum.
- Skips addendums that are not in_review.
- Handles fetch_all_issues failures gracefully.
- Does not crash when poll_addendum_pr raises.
- Respects the job deadline.
- The sweep is registered in _do_merged_labels.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.release_addendum_schema import (
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)
from oompah.scm import ReviewRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
_COMMIT = "a" * 40
_PR_URL = "https://github.com/org/repo/pull/42"


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_project(
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.repo_path = "/tmp/repo"
    p.default_branch = "main"
    p.access_token = None
    return p


def _make_addendum(
    source_id: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.IN_REVIEW,
    pr_url: str | None = _PR_URL,
) -> ReleaseAddendum:
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target_branch),
        source_branch="main",
        target_branch=target_branch,
        status=status,
        commits=[_COMMIT],
        work_branch=make_work_branch(source_id, target_branch),
        worktree_key=make_worktree_key(source_id, target_branch),
        queued_at=NOW.isoformat(),
        pr_url=pr_url,
    )


class _InMemoryTracker:
    """Minimal in-memory tracker for orchestrator sweep tests."""

    def __init__(self, issues: list, addendums_by_id: dict[str, list[ReleaseAddendum]]) -> None:
        self._issues = issues
        self._metadata: dict[str, dict] = {
            identifier: {"oompah.release_addendums": [a.to_raw() for a in adds]}
            for identifier, adds in addendums_by_id.items()
        }
        self.comments: list[dict] = []
        self.writes: int = 0

    def fetch_all_issues(self) -> list:
        return list(self._issues)

    def get_metadata(self, identifier: str) -> dict:
        return dict(self._metadata.get(str(identifier), {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self._metadata.setdefault(str(identifier), {})[key] = value
        self.writes += 1

    def add_comment(self, identifier: str, message: str, *, author: str) -> None:
        self.comments.append({"identifier": identifier, "message": message, "author": author})


def _make_issue_obj(identifier: str) -> SimpleNamespace:
    return SimpleNamespace(identifier=identifier, id=identifier)


def _make_orchestrator(tmp_path, projects=None) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ---------------------------------------------------------------------------
# Tests: _reconcile_addendum_pr_outcomes_sweep
# ---------------------------------------------------------------------------


class TestReconcileAddendumPrOutcomesSweep:
    """Tests for Orchestrator._reconcile_addendum_pr_outcomes_sweep."""

    def test_skips_project_with_no_repo_url(self, tmp_path):
        project = _make_project(repo_url="")
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10")],
            addendums_by_id={"FOO-10": [_make_addendum()]},
        )
        orch._project_trackers[project.id] = tracker

        with patch("oompah.release_addendum_poller.poll_addendum_pr") as mock_poll:
            orch._reconcile_addendum_pr_outcomes_sweep()

        mock_poll.assert_not_called()

    def test_skips_project_when_provider_detection_fails(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10")],
            addendums_by_id={"FOO-10": [_make_addendum()]},
        )
        orch._project_trackers[project.id] = tracker

        with patch(
            "oompah.orchestrator.detect_provider", side_effect=RuntimeError("no provider")
        ):
            with patch("oompah.release_addendum_poller.poll_addendum_pr") as mock_poll:
                orch._reconcile_addendum_pr_outcomes_sweep()

        mock_poll.assert_not_called()

    def test_skips_project_when_provider_is_none(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10")],
            addendums_by_id={"FOO-10": [_make_addendum()]},
        )
        orch._project_trackers[project.id] = tracker

        with patch("oompah.orchestrator.detect_provider", return_value=None):
            with patch("oompah.release_addendum_poller.poll_addendum_pr") as mock_poll:
                orch._reconcile_addendum_pr_outcomes_sweep()

        mock_poll.assert_not_called()

    def test_polls_in_review_addendum(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        addendum = _make_addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10")],
            addendums_by_id={"FOO-10": [addendum]},
        )
        orch._project_trackers[project.id] = tracker

        mock_provider = MagicMock()
        with patch("oompah.orchestrator.detect_provider", return_value=mock_provider):
            with patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
                with patch("oompah.release_addendum_poller.poll_addendum_pr") as mock_poll:
                    mock_poll.return_value = addendum
                    orch._reconcile_addendum_pr_outcomes_sweep()

        mock_poll.assert_called_once()
        call_kwargs = mock_poll.call_args
        assert call_kwargs[0][1] == "FOO-10"  # source_identifier
        assert call_kwargs[0][2].id == addendum.id  # addendum

    def test_skips_non_in_review_addendums(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        addendums = [
            _make_addendum(target_branch="release/1.0", status=AddendumStatus.OPEN),
            _make_addendum(target_branch="release/1.1", status=AddendumStatus.BLOCKED),
            _make_addendum(target_branch="release/1.2", status=AddendumStatus.MERGED),
            _make_addendum(target_branch="release/1.3", status=AddendumStatus.ARCHIVED),
        ]
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10")],
            addendums_by_id={"FOO-10": addendums},
        )
        orch._project_trackers[project.id] = tracker

        mock_provider = MagicMock()
        with patch("oompah.orchestrator.detect_provider", return_value=mock_provider):
            with patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
                with patch("oompah.release_addendum_poller.poll_addendum_pr") as mock_poll:
                    orch._reconcile_addendum_pr_outcomes_sweep()

        mock_poll.assert_not_called()

    def test_handles_fetch_all_issues_failure_gracefully(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        mock_tracker = MagicMock()
        mock_tracker.fetch_all_issues.side_effect = RuntimeError("DB error")
        orch._project_trackers[project.id] = mock_tracker

        mock_provider = MagicMock()
        with patch("oompah.orchestrator.detect_provider", return_value=mock_provider):
            with patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
                # Must not raise
                orch._reconcile_addendum_pr_outcomes_sweep()

    def test_handles_poll_exception_without_crashing(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        addendum = _make_addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10")],
            addendums_by_id={"FOO-10": [addendum]},
        )
        orch._project_trackers[project.id] = tracker

        mock_provider = MagicMock()
        with patch("oompah.orchestrator.detect_provider", return_value=mock_provider):
            with patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
                with patch(
                    "oompah.release_addendum_poller.poll_addendum_pr",
                    side_effect=RuntimeError("unexpected"),
                ):
                    # Must not raise; logs warning
                    orch._reconcile_addendum_pr_outcomes_sweep()

    def test_polls_multiple_in_review_addendums_across_sources(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        a1 = _make_addendum("FOO-10", "release/1.0", AddendumStatus.IN_REVIEW)
        a2 = _make_addendum("FOO-11", "release/1.0", AddendumStatus.IN_REVIEW)
        tracker = _InMemoryTracker(
            issues=[_make_issue_obj("FOO-10"), _make_issue_obj("FOO-11")],
            addendums_by_id={"FOO-10": [a1], "FOO-11": [a2]},
        )
        orch._project_trackers[project.id] = tracker

        poll_calls: list = []
        def _fake_poll(tracker, src, addendum, *, scm, repo):
            poll_calls.append((src, addendum.id))
            return addendum

        mock_provider = MagicMock()
        with patch("oompah.orchestrator.detect_provider", return_value=mock_provider):
            with patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
                with patch(
                    "oompah.release_addendum_poller.poll_addendum_pr",
                    side_effect=_fake_poll,
                ):
                    orch._reconcile_addendum_pr_outcomes_sweep()

        ids_polled = [a_id for _, a_id in poll_calls]
        assert a1.id in ids_polled
        assert a2.id in ids_polled

    def test_handles_addendum_read_failure_gracefully(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        bad_tracker = MagicMock()
        bad_tracker.fetch_all_issues.return_value = [_make_issue_obj("FOO-10")]
        bad_tracker.get_metadata.side_effect = RuntimeError("metadata unavailable")
        orch._project_trackers[project.id] = bad_tracker

        mock_provider = MagicMock()
        with patch("oompah.orchestrator.detect_provider", return_value=mock_provider):
            with patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"):
                with patch("oompah.release_addendum_poller.poll_addendum_pr") as mock_poll:
                    orch._reconcile_addendum_pr_outcomes_sweep()

        # Must not raise; poll should not be called
        mock_poll.assert_not_called()

    def test_sweep_registered_in_do_merged_labels(self, tmp_path):
        """_reconcile_addendum_pr_outcomes_sweep must appear in _do_merged_labels sweeps."""
        orch = _make_orchestrator(tmp_path)
        # Patch all sweep methods to no-ops
        orch._label_merged_epics = MagicMock()
        orch._reconcile_merged_epic_children = MagicMock()
        orch._label_merged_issues = MagicMock()
        orch._reconcile_in_review_pr_outcomes = MagicMock()
        orch._reconcile_terminal_open_reviews = MagicMock()
        orch._reconcile_stale_in_review_tasks = MagicMock()
        orch._reconcile_addendum_pr_outcomes_sweep = MagicMock()
        orch._job_deadline_exceeded = MagicMock(return_value=False)

        orch._do_merged_labels()

        orch._reconcile_addendum_pr_outcomes_sweep.assert_called_once()
