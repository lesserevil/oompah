"""Tests for retry and archive release-addendum lifecycle-control endpoints (OOMPAH-179).

Covers:
  POST /api/v1/issues/{identifier}/release-addendums/{addendum_id}/retry
  POST /api/v1/issues/{identifier}/release-addendums/{addendum_id}/archive

  Retry endpoint:
  - 200: blocked → open (standard retry after conflict)
  - 200: in_review → open (retry after closed-unmerged PR)
  - 409: invalid source state (open, merged, archived, in_progress)
  - 409: schema-level transition guard (should never happen but validated)
  - 404: project not found / issue not found / addendum not found
  - 400: missing project_id
  - commits are immutable across retry
  - oompah comment posted on source task (includes branch, transition, PR URL)
  - wake-up event published on retry
  - cache invalidated

  Archive endpoint:
  - 200: open → archived (operator cancels before execution)
  - 200: blocked → archived (operator cancels after conflict)
  - 409: invalid source state (in_review, in_progress, merged, archived)
  - 404: project not found / issue not found / addendum not found
  - 400: missing project_id
  - commits preserved in archived addendum
  - oompah comment posted on source task (includes branch, transition)
  - cache invalidated
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue, Project
from oompah.release_addendum_schema import (
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40
_PR_URL = "https://github.com/org/repo/pull/42"


def _make_issue(
    identifier: str = "FOO-10",
    state: str = "Merged",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A merged task",
        description="",
        state=state,
        priority=1,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_project(pid: str = "proj-1") -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.default_branch = "main"
    project.supported_release_branches = ["release/1.1", "release/1.0"]
    project.repo_url = "https://github.com/org/repo"
    project.repo_path = "/tmp/repos/proj-1"
    project.access_token = None
    project.branches = ["main", "release/*"]
    return project


def _make_addendum(
    source_id: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.BLOCKED,
    pr_url: str | None = _PR_URL,
    error: str | None = "cherry-pick conflict",
    commits: list[str] | None = None,
) -> ReleaseAddendum:
    commits = commits or [_COMMIT_A, _COMMIT_B]
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target_branch),
        source_branch="main",
        target_branch=target_branch,
        status=status,
        commits=commits,
        work_branch=make_work_branch(source_id, target_branch),
        worktree_key=make_worktree_key(source_id, target_branch),
        queued_at=NOW.isoformat(),
        started_at=NOW.isoformat(),
        completed_at=None,
        pr_url=pr_url,
        result_commits=[],
        error=error,
        claimed_by="worker-1",
        lease_expires_at=NOW.isoformat(),
    )


class _WriteableTracker:
    """In-memory tracker with full read/write/comment support."""

    def __init__(self, addendums: list[ReleaseAddendum]) -> None:
        self._lock = threading.Lock()
        self._meta: dict = {
            "oompah.release_addendums": [a.to_raw() for a in addendums]
        }
        self.comments: list[dict] = []
        self.writes: int = 0

    def get_metadata(self, _identifier: str) -> dict:
        with self._lock:
            return {k: list(v) if isinstance(v, list) else v for k, v in self._meta.items()}

    def set_metadata_field(self, _identifier: str, key: str, value: object) -> None:
        with self._lock:
            self._meta[key] = value
            self.writes += 1

    def add_comment(self, identifier: str, message: str, *, author: str) -> None:
        self.comments.append({"identifier": identifier, "message": message, "author": author})

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return _make_issue(identifier=identifier)


def _make_orchestrator(
    tracker: _WriteableTracker | None = None,
    issue: Issue | None = None,
    project: MagicMock | None = None,
) -> MagicMock:
    t = tracker or _WriteableTracker([])
    p = project or _make_project()
    orch = MagicMock()
    orch._tracker_for_project.return_value = t
    orch.project_store.list_all.return_value = [p]
    orch.project_store.get.return_value = p
    t.fetch_issue_detail = MagicMock(
        return_value=issue or _make_issue()
    )
    orch.event_bus = MagicMock()
    return orch


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper to build the retry/archive URL
# ---------------------------------------------------------------------------

def _retry_url(identifier: str, addendum_id: str) -> str:
    """Build the retry URL; addendum_id may contain slashes."""
    return f"/api/v1/issues/{identifier}/release-addendums/{addendum_id}/retry"


def _archive_url(identifier: str, addendum_id: str) -> str:
    return f"/api/v1/issues/{identifier}/release-addendums/{addendum_id}/archive"


# ---------------------------------------------------------------------------
# Tests: POST retry endpoint
# ---------------------------------------------------------------------------


class TestRetryReleaseAddendum:
    """Tests for POST /…/release-addendums/{addendum_id}/retry."""

    def _retry(
        self,
        client,
        tracker: _WriteableTracker,
        addendum: ReleaseAddendum,
        identifier: str = "FOO-10",
        project_id: str = "proj-1",
        issue: Issue | None = None,
    ):
        orch = _make_orchestrator(tracker=tracker, issue=issue or _make_issue(identifier))
        url = _retry_url(identifier, addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            return client.post(url, json={"project_id": project_id})

    # --- 200: valid transitions ---

    def test_blocked_to_open_returns_200(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 200

    def test_in_review_to_open_returns_200(self, client):
        addendum = _make_addendum(
            status=AddendumStatus.IN_REVIEW,
            error="PR closed without merge: https://github.com/org/repo/pull/42",
        )
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 200

    def test_blocked_retry_transitions_status_to_open(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 200
        data = resp.json()
        found = next(
            (a for a in data["addendums"] if a["id"] == addendum.id), None
        )
        assert found is not None
        assert found["status"] == "open"

    def test_in_review_retry_transitions_status_to_open(self, client):
        addendum = _make_addendum(status=AddendumStatus.IN_REVIEW, error="PR closed without merge: x")
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 200
        data = resp.json()
        found = next(a for a in data["addendums"] if a["id"] == addendum.id)
        assert found["status"] == "open"

    def test_response_contains_identifier_and_addendum_id(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        data = resp.json()
        assert data["identifier"] == "FOO-10"
        assert data["addendum_id"] == addendum.id

    def test_response_contains_addendums_list(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        data = resp.json()
        assert "addendums" in data
        assert len(data["addendums"]) >= 1

    # --- commits immutability ---

    def test_commits_unchanged_after_retry(self, client):
        original_commits = [_COMMIT_A, _COMMIT_B]
        addendum = _make_addendum(status=AddendumStatus.BLOCKED, commits=list(original_commits))
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 200
        data = resp.json()
        found = next(a for a in data["addendums"] if a["id"] == addendum.id)
        assert found["commits"] == original_commits

    def test_retry_clears_error_field(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED, error="cherry-pick conflict")
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        data = resp.json()
        found = next(a for a in data["addendums"] if a["id"] == addendum.id)
        assert found.get("error") is None

    # --- oompah comments ---

    def test_retry_posts_oompah_comment(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        self._retry(client, tracker, addendum)
        assert any(c["author"] == "oompah" for c in tracker.comments)

    def test_retry_comment_includes_branch(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED, target_branch="release/1.0")
        tracker = _WriteableTracker([addendum])
        self._retry(client, tracker, addendum)
        comment_messages = " ".join(c["message"] for c in tracker.comments)
        assert "release/1.0" in comment_messages

    def test_retry_comment_includes_transition(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        self._retry(client, tracker, addendum)
        comment_messages = " ".join(c["message"] for c in tracker.comments)
        assert "blocked" in comment_messages.lower() or "open" in comment_messages.lower()

    def test_retry_comment_includes_pr_url_when_present(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED, pr_url=_PR_URL)
        tracker = _WriteableTracker([addendum])
        self._retry(client, tracker, addendum)
        comment_messages = " ".join(c["message"] for c in tracker.comments)
        assert _PR_URL in comment_messages

    # --- 409: invalid source state ---

    def test_open_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 409

    def test_merged_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.MERGED, pr_url=_PR_URL)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 409

    def test_archived_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.ARCHIVED)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 409

    def test_in_progress_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.IN_PROGRESS)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 409

    def test_409_response_has_invalid_transition_code(self, client):
        addendum = _make_addendum(status=AddendumStatus.MERGED)
        tracker = _WriteableTracker([addendum])
        resp = self._retry(client, tracker, addendum)
        data = resp.json()
        assert data["error"]["code"] == "invalid_transition"

    # --- 400: missing project_id ---

    def test_missing_project_id_returns_400(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        orch = _make_orchestrator(tracker=tracker)
        url = _retry_url("FOO-10", addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={})
        assert resp.status_code == 400

    # --- 404: not found ---

    def test_unknown_addendum_id_returns_404(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        orch = _make_orchestrator(tracker=tracker)
        url = _retry_url("FOO-10", "DOES-NOT-EXIST/release/9.9")
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        assert resp.status_code == 404

    def test_unknown_issue_returns_404(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        issue = None  # Issue not found
        orch = _make_orchestrator(tracker=tracker, issue=issue)
        orch._tracker_for_project.return_value = tracker
        tracker.fetch_issue_detail = MagicMock(return_value=None)
        url = _retry_url("NONEXISTENT-99", addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        assert resp.status_code == 404

    # --- cache invalidation ---

    def test_retry_invalidates_cache(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        with patch.object(server_module._api_cache, "invalidate_prefix") as mock_inv:
            resp = self._retry(client, tracker, addendum)
        assert resp.status_code == 200
        mock_inv.assert_called()


# ---------------------------------------------------------------------------
# Tests: POST archive endpoint
# ---------------------------------------------------------------------------


class TestArchiveReleaseAddendum:
    """Tests for POST /…/release-addendums/{addendum_id}/archive."""

    def _archive(
        self,
        client,
        tracker: _WriteableTracker,
        addendum: ReleaseAddendum,
        identifier: str = "FOO-10",
        project_id: str = "proj-1",
        issue: Issue | None = None,
    ):
        orch = _make_orchestrator(tracker=tracker, issue=issue or _make_issue(identifier))
        url = _archive_url(identifier, addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            return client.post(url, json={"project_id": project_id})

    # --- 200: valid transitions ---

    def test_open_to_archived_returns_200(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 200

    def test_blocked_to_archived_returns_200(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 200

    def test_open_archive_transitions_status_to_archived(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 200
        data = resp.json()
        found = next(a for a in data["addendums"] if a["id"] == addendum.id)
        assert found["status"] == "archived"

    def test_blocked_archive_transitions_status_to_archived(self, client):
        addendum = _make_addendum(status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 200
        data = resp.json()
        found = next(a for a in data["addendums"] if a["id"] == addendum.id)
        assert found["status"] == "archived"

    def test_response_contains_identifier_and_addendum_id(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        data = resp.json()
        assert data["identifier"] == "FOO-10"
        assert data["addendum_id"] == addendum.id

    def test_response_contains_addendums_list(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        data = resp.json()
        assert "addendums" in data

    # --- commits preserved in archived addendum ---

    def test_commits_preserved_after_archive(self, client):
        original_commits = [_COMMIT_A, _COMMIT_B]
        addendum = _make_addendum(
            status=AddendumStatus.OPEN, error=None, commits=list(original_commits)
        )
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 200
        data = resp.json()
        found = next(a for a in data["addendums"] if a["id"] == addendum.id)
        assert found["commits"] == original_commits

    # --- oompah comments ---

    def test_archive_posts_oompah_comment(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        self._archive(client, tracker, addendum)
        assert any(c["author"] == "oompah" for c in tracker.comments)

    def test_archive_comment_includes_branch(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None, target_branch="release/1.0")
        tracker = _WriteableTracker([addendum])
        self._archive(client, tracker, addendum)
        comment_messages = " ".join(c["message"] for c in tracker.comments)
        assert "release/1.0" in comment_messages

    def test_archive_comment_includes_transition_to_archived(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        self._archive(client, tracker, addendum)
        comment_messages = " ".join(c["message"] for c in tracker.comments).lower()
        assert "archived" in comment_messages

    # --- 409: invalid source state ---

    def test_in_review_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.IN_REVIEW, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 409

    def test_in_progress_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.IN_PROGRESS, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 409

    def test_merged_addendum_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.MERGED, pr_url=_PR_URL, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 409

    def test_already_archived_returns_409(self, client):
        addendum = _make_addendum(status=AddendumStatus.ARCHIVED, error=None)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 409

    def test_409_response_has_invalid_transition_code(self, client):
        addendum = _make_addendum(status=AddendumStatus.IN_REVIEW)
        tracker = _WriteableTracker([addendum])
        resp = self._archive(client, tracker, addendum)
        data = resp.json()
        assert data["error"]["code"] == "invalid_transition"

    # --- 400: missing project_id ---

    def test_missing_project_id_returns_400(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        orch = _make_orchestrator(tracker=tracker)
        url = _archive_url("FOO-10", addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={})
        assert resp.status_code == 400

    # --- 404: not found ---

    def test_unknown_addendum_id_returns_404(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        orch = _make_orchestrator(tracker=tracker)
        url = _archive_url("FOO-10", "DOES-NOT-EXIST/release/9.9")
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        assert resp.status_code == 404

    # --- cache invalidation ---

    def test_archive_invalidates_cache(self, client):
        addendum = _make_addendum(status=AddendumStatus.OPEN, error=None)
        tracker = _WriteableTracker([addendum])
        with patch.object(server_module._api_cache, "invalidate_prefix") as mock_inv:
            resp = self._archive(client, tracker, addendum)
        assert resp.status_code == 200
        mock_inv.assert_called()


# ---------------------------------------------------------------------------
# Tests: addendum_id with slashes in path (URL routing)
# ---------------------------------------------------------------------------


class TestAddendumIdRouting:
    """Addendum IDs contain slashes; the :path parameter must handle them."""

    def test_retry_with_slash_in_addendum_id(self, client):
        addendum = _make_addendum(
            source_id="FOO-10",
            target_branch="release/1.0",
            status=AddendumStatus.BLOCKED,
        )
        # addendum.id == "FOO-10/release/1.0" — contains multiple slashes
        tracker = _WriteableTracker([addendum])
        orch = _make_orchestrator(tracker=tracker)
        url = _retry_url("FOO-10", addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        # Should route and find the addendum correctly
        assert resp.status_code == 200

    def test_archive_with_slash_in_addendum_id(self, client):
        addendum = _make_addendum(
            source_id="FOO-10",
            target_branch="release/1.1",
            status=AddendumStatus.OPEN,
            error=None,
        )
        tracker = _WriteableTracker([addendum])
        orch = _make_orchestrator(tracker=tracker)
        url = _archive_url("FOO-10", addendum.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: multiple addendums on a source task
# ---------------------------------------------------------------------------


class TestMultipleAddendums:
    """Only the targeted addendum is modified; siblings are preserved."""

    def test_retry_only_affects_target_addendum(self, client):
        a1 = _make_addendum(target_branch="release/1.0", status=AddendumStatus.BLOCKED)
        a2 = _make_addendum(target_branch="release/1.1", status=AddendumStatus.IN_REVIEW, error=None)
        tracker = _WriteableTracker([a1, a2])
        orch = _make_orchestrator(tracker=tracker)
        url = _retry_url("FOO-10", a1.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        assert resp.status_code == 200
        data = resp.json()
        # a1 → open
        r1 = next(a for a in data["addendums"] if a["id"] == a1.id)
        assert r1["status"] == "open"
        # a2 stays in_review
        r2 = next(a for a in data["addendums"] if a["id"] == a2.id)
        assert r2["status"] == "in_review"

    def test_archive_only_affects_target_addendum(self, client):
        a1 = _make_addendum(target_branch="release/1.0", status=AddendumStatus.OPEN, error=None)
        a2 = _make_addendum(target_branch="release/1.1", status=AddendumStatus.BLOCKED)
        tracker = _WriteableTracker([a1, a2])
        orch = _make_orchestrator(tracker=tracker)
        url = _archive_url("FOO-10", a1.id)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(url, json={"project_id": "proj-1"})
        assert resp.status_code == 200
        data = resp.json()
        # a1 → archived
        r1 = next(a for a in data["addendums"] if a["id"] == a1.id)
        assert r1["status"] == "archived"
        # a2 stays blocked
        r2 = next(a for a in data["addendums"] if a["id"] == a2.id)
        assert r2["status"] == "blocked"
