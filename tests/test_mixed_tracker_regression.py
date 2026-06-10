"""Regression tests for mixed Backlog/GitHub tracker scenarios (TASK-459.7).

Covers:
  1. Mixed board — Backlog + GitHub issues appear together without identifier collision.
  2. Identifier collision prevention — bare numbers in different trackers get distinct
     display_identifiers (AC #1).
  3. Project filtering — filter_project only returns issues from the requested project.
  4. Detail panel — both tracker kinds return correct tracker identity fields (AC #2).
  5. Comments — GET and POST for both tracker kinds (AC #2).
  6. Labels — POST label for both tracker kinds (AC #2).
  7. Create flows — POST create routes to the correct tracker based on project (AC #2).
  8. Status updates — PATCH for both tracker kinds (AC #2).
  9. Cache invalidation — status update, comment, and label operations each invalidate
     the ``issues:all`` cache entry.
  10. Tracker identity display — board entries always contain all tracker fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.server import app


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _dt() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _backlog_issue(
    identifier: str = "TASK-1",
    project_id: str = "proj-backlog",
    is_legacy: bool = False,
) -> Issue:
    """Minimal Backlog-backed issue."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Backlog issue {identifier}",
        state="open",
        priority=2,
        issue_type="task",
        labels=[],
        created_at=_dt(),
        updated_at=_dt(),
        project_id=project_id,
        is_legacy=is_legacy,
    )


def _github_issue(
    identifier: str = "acme/tasks#1",
    issue_number: str = "1",
    project_id: str = "proj-github",
) -> Issue:
    """Minimal GitHub-backed issue with full tracker identity."""
    return Issue(
        id=f"GH_{issue_number}",
        identifier=identifier,
        title=f"GitHub issue #{issue_number}",
        state="open",
        priority=1,
        issue_type="task",
        labels=["area:api"],
        created_at=_dt(),
        updated_at=_dt(),
        tracker_kind="github_issues",
        tracker_owner="acme",
        tracker_repo="tasks",
        issue_number=issue_number,
        display_identifier=f"tasks#{issue_number}",
        provider_url=f"https://github.com/acme/tasks/issues/{issue_number}",
        managed_repo="acme/code",
        target_branch="main",
        work_branch=f"oompah/code/gh-{issue_number}",
        is_legacy=False,
        project_id=project_id,
    )


def _project(pid: str, name: str, tracker_kind: str = "backlog") -> MagicMock:
    p = MagicMock(spec=Project)
    p.id = pid
    p.name = name
    p.tracker_kind = tracker_kind
    p.repo_url = "https://example.invalid/repo.git"
    p.repo_path = "/tmp/fake"
    return p


def _make_tracker(issues: list[Issue]) -> MagicMock:
    t = MagicMock()
    t.fetch_all_issues.return_value = list(issues)
    t.fetch_issue_detail = MagicMock(
        side_effect=lambda ident: next(
            (i for i in issues if i.identifier == ident or i.id == ident), None
        )
    )
    t.fetch_comments.return_value = []
    t.fetch_children.return_value = []
    t.update_issue = MagicMock()
    t.add_label = MagicMock()
    t.remove_label = MagicMock()
    t.add_comment = MagicMock(return_value={"id": "c1", "text": "test"})
    t.create_issue = MagicMock(side_effect=lambda **kw: _backlog_issue())
    return t


def _make_mixed_orch(
    backlog_issues: list[Issue],
    github_issues: list[Issue],
    backlog_pid: str = "proj-backlog",
    github_pid: str = "proj-github",
    backlog_name: str = "myproject",
    github_name: str = "mygh",
) -> MagicMock:
    """Orchestrator with two projects: one Backlog, one GitHub."""
    proj_backlog = _project(backlog_pid, backlog_name, "backlog")
    proj_github = _project(github_pid, github_name, "github_issues")

    tracker_backlog = _make_tracker(backlog_issues)
    tracker_github = _make_tracker(github_issues)

    orch = MagicMock()
    orch.project_store.list_all.return_value = [proj_backlog, proj_github]
    orch._unmerged_review_branches = set()

    def _tracker_for(pid):
        if pid == backlog_pid:
            return tracker_backlog
        if pid == github_pid:
            return tracker_github
        raise KeyError(f"Unknown project {pid!r}")

    orch._tracker_for_project.side_effect = _tracker_for
    orch.tracker = tracker_backlog  # legacy fallback
    orch.config.tracker_terminal_states = ["Done"]
    orch.state.running = {}
    orch.state.retry_attempts = {}
    return orch


@pytest.fixture(autouse=True)
def clear_api_cache():
    server_module._api_cache.clear()
    yield
    server_module._api_cache.clear()


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Mixed board — Backlog + GitHub issues together
# ---------------------------------------------------------------------------


class TestMixedBoard:
    """Board contains issues from both tracker kinds without corruption."""

    def test_board_contains_both_backlog_and_github_issues(self):
        bl = _backlog_issue("TASK-10", "proj-backlog")
        gh = _github_issue("acme/tasks#10", "10", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        open_ids = {e["identifier"] for e in data.get("Open", [])}
        assert "TASK-10" in open_ids
        assert "acme/tasks#10" in open_ids

    def test_board_total_count_is_sum_of_both_projects(self):
        bl_issues = [_backlog_issue(f"TASK-{i}", "proj-backlog") for i in range(3)]
        gh_issues = [_github_issue(f"acme/tasks#{i}", str(i), "proj-github") for i in range(2)]
        orch = _make_mixed_orch(bl_issues, gh_issues)

        data = server_module._fetch_and_serialize_issues(orch)
        total = sum(len(v) for v in data.values() if isinstance(v, list))
        assert total == 5

    def test_project_ids_are_stamped_on_all_entries(self):
        bl = _backlog_issue("TASK-1", "proj-backlog")
        gh = _github_issue("acme/tasks#1", "1", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        all_entries = [e for v in data.values() for e in v]
        project_ids = {e["project_id"] for e in all_entries}
        assert "proj-backlog" in project_ids
        assert "proj-github" in project_ids

    def test_tracker_kind_stamped_correctly_on_each_entry(self):
        bl = _backlog_issue("TASK-5", "proj-backlog")
        gh = _github_issue("acme/tasks#5", "5", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        all_entries = {e["identifier"]: e for v in data.values() for e in v}

        assert all_entries["TASK-5"]["tracker_kind"] is None
        assert all_entries["acme/tasks#5"]["tracker_kind"] == "github_issues"

    def test_all_entries_have_full_tracker_key_set(self):
        required_keys = {
            "tracker_kind", "tracker_owner", "tracker_repo", "issue_number",
            "url", "managed_repo", "target_branch", "work_branch", "is_legacy",
        }
        bl = _backlog_issue("TASK-7", "proj-backlog")
        gh = _github_issue("acme/tasks#7", "7", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        for state, entries in data.items():
            for entry in entries:
                missing = required_keys - entry.keys()
                assert not missing, f"Entry {entry['identifier']!r} missing keys: {missing}"


# ---------------------------------------------------------------------------
# 2. Identifier collision prevention — AC #1
# ---------------------------------------------------------------------------


class TestIdentifierCollisionPrevention:
    """Mixed board data cannot collide on bare task numbers (AC #1)."""

    def test_backlog_and_github_with_same_bare_number_have_distinct_display_identifiers(self):
        """TASK-1 and GitHub #1 must not share a display_identifier."""
        bl = _backlog_issue("TASK-1", "proj-backlog")
        gh = _github_issue("acme/tasks#1", "1", "proj-github")
        orch = _make_mixed_orch([bl], [gh], backlog_name="myproject")

        data = server_module._fetch_and_serialize_issues(orch)
        all_entries = {e["identifier"]: e for v in data.values() for e in v}

        bl_di = all_entries["TASK-1"]["display_identifier"]
        gh_di = all_entries["acme/tasks#1"]["display_identifier"]

        assert bl_di != gh_di, (
            f"Identifier collision: both display as {bl_di!r}"
        )

    def test_backlog_display_identifier_uses_project_name(self):
        """Backlog issue TASK-42 in 'myproject' displays as 'myproject-42'."""
        bl = _backlog_issue("TASK-42", "proj-backlog")
        orch = _make_mixed_orch([bl], [], backlog_name="myproject")

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["display_identifier"] == "myproject-42"

    def test_github_display_identifier_uses_tracker_short_form(self):
        """GitHub issue with display_identifier='tasks#7' uses that verbatim."""
        gh = _github_issue("acme/tasks#7", "7", "proj-github")
        orch = _make_mixed_orch([], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["display_identifier"] == "tasks#7"

    def test_multiple_backlog_issues_all_unique_display_identifiers(self):
        """TASK-1, TASK-2, TASK-3 are all distinct after formatting."""
        issues = [_backlog_issue(f"TASK-{i}", "proj-backlog") for i in range(1, 4)]
        orch = _make_mixed_orch(issues, [], backlog_name="proj")

        data = server_module._fetch_and_serialize_issues(orch)
        display_ids = [e["display_identifier"] for v in data.values() for e in v]
        assert len(display_ids) == len(set(display_ids)), "Duplicate display identifiers"

    def test_multiple_github_issues_all_unique_display_identifiers(self):
        """GitHub issues #1, #2, #3 each get a unique display_identifier."""
        issues = [_github_issue(f"acme/tasks#{i}", str(i), "proj-github") for i in range(1, 4)]
        orch = _make_mixed_orch([], issues)

        data = server_module._fetch_and_serialize_issues(orch)
        display_ids = [e["display_identifier"] for v in data.values() for e in v]
        assert len(display_ids) == len(set(display_ids)), "Duplicate display identifiers"

    def test_legacy_backlog_issue_is_distinct_from_github_issue_same_number(self):
        """Legacy Backlog issue and GitHub issue with same number stay distinct."""
        bl = _backlog_issue("TASK-99", "proj-backlog", is_legacy=True)
        gh = _github_issue("acme/tasks#99", "99", "proj-github")
        orch = _make_mixed_orch([bl], [gh], backlog_name="legacyproject")

        data = server_module._fetch_and_serialize_issues(orch)
        all_entries = {e["identifier"]: e for v in data.values() for e in v}

        bl_di = all_entries["TASK-99"]["display_identifier"]
        gh_di = all_entries["acme/tasks#99"]["display_identifier"]
        assert bl_di != gh_di
        assert all_entries["TASK-99"]["is_legacy"] is True
        assert all_entries["acme/tasks#99"]["is_legacy"] is False


# ---------------------------------------------------------------------------
# 3. Project filtering — mixed tracker set
# ---------------------------------------------------------------------------


class TestProjectFiltering:
    """Filtering to a specific project excludes the other tracker's issues."""

    def test_filter_to_backlog_project_excludes_github_issues(self):
        bl = _backlog_issue("TASK-1", "proj-backlog")
        gh = _github_issue("acme/tasks#1", "1", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        # Populate the cache with full board
        full = server_module._fetch_and_serialize_issues(orch)
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot["data"] = full
            server_module._issues_snapshot["orch_id"] = id(orch)

        payload = server_module._issues_snapshot_payload(
            filter_project="proj-backlog", allow_empty=True, orch=orch
        )
        all_entries = [e for v in payload.values() if isinstance(v, list) for e in v]
        pids = {e["project_id"] for e in all_entries}
        assert "proj-backlog" in pids
        assert "proj-github" not in pids

    def test_filter_to_github_project_excludes_backlog_issues(self):
        bl = _backlog_issue("TASK-1", "proj-backlog")
        gh = _github_issue("acme/tasks#1", "1", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        full = server_module._fetch_and_serialize_issues(orch)
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot["data"] = full
            server_module._issues_snapshot["orch_id"] = id(orch)

        payload = server_module._issues_snapshot_payload(
            filter_project="proj-github", allow_empty=True, orch=orch
        )
        all_entries = [e for v in payload.values() if isinstance(v, list) for e in v]
        pids = {e["project_id"] for e in all_entries}
        assert "proj-github" in pids
        assert "proj-backlog" not in pids

    def test_no_filter_returns_both_projects(self):
        bl = _backlog_issue("TASK-1", "proj-backlog")
        gh = _github_issue("acme/tasks#1", "1", "proj-github")
        orch = _make_mixed_orch([bl], [gh])

        full = server_module._fetch_and_serialize_issues(orch)
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot["data"] = full
            server_module._issues_snapshot["orch_id"] = id(orch)

        payload = server_module._issues_snapshot_payload(
            filter_project=None, allow_empty=True, orch=orch
        )
        all_entries = [e for v in payload.values() if isinstance(v, list) for e in v]
        pids = {e["project_id"] for e in all_entries}
        assert "proj-backlog" in pids
        assert "proj-github" in pids


# ---------------------------------------------------------------------------
# 4. Detail panel — both tracker kinds (AC #2)
# ---------------------------------------------------------------------------


class TestDetailPanelMixedTrackers:
    """GET /api/v1/issues/{id}/detail returns correct tracker identity for both kinds."""

    def test_backlog_issue_detail_has_null_tracker_kind(self, client):
        bl = _backlog_issue("TASK-1", "proj-backlog")
        tracker = _make_tracker([bl])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-1/detail",
                params={"project_id": "proj-backlog"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tracker_kind"] is None
        assert body["tracker_owner"] is None
        assert body["is_legacy"] is False

    def test_github_issue_detail_has_populated_tracker_kind(self, client):
        gh = _github_issue("acme/tasks#5", "5", "proj-github")
        tracker = _make_tracker([gh])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-github", "mygh", "github_issues")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/GH_5/detail",
                params={"project_id": "proj-github"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tracker_kind"] == "github_issues"
        assert body["tracker_owner"] == "acme"
        assert body["tracker_repo"] == "tasks"
        assert body["issue_number"] == "5"
        assert body["is_legacy"] is False

    def test_legacy_backlog_issue_detail_has_is_legacy_true(self, client):
        bl = _backlog_issue("TASK-OLD-1", "proj-backlog", is_legacy=True)
        tracker = _make_tracker([bl])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-OLD-1/detail",
                params={"project_id": "proj-backlog"},
            )

        assert resp.status_code == 200
        assert resp.json()["is_legacy"] is True

    def test_detail_has_all_tracker_identity_keys(self, client):
        required_keys = {
            "tracker_kind", "tracker_owner", "tracker_repo", "issue_number",
            "url", "managed_repo", "target_branch", "work_branch", "is_legacy",
        }
        for issue, pid, pname in [
            (_backlog_issue("TASK-11", "proj-backlog"), "proj-backlog", "myproject"),
            (_github_issue("acme/tasks#11", "11", "proj-github"), "proj-github", "mygh"),
        ]:
            tracker = _make_tracker([issue])
            orch = MagicMock()
            orch.project_store.list_all.return_value = [_project(pid, pname)]
            orch._tracker_for_project.return_value = tracker
            orch.tracker = tracker

            route_id = issue.id
            with patch.object(server_module, "_get_orchestrator", return_value=orch):
                resp = client.get(
                    f"/api/v1/issues/{route_id}/detail",
                    params={"project_id": pid},
                )

            assert resp.status_code == 200, f"{issue.identifier}: {resp.text}"
            body = resp.json()
            missing = required_keys - body.keys()
            assert not missing, f"{issue.identifier} missing detail keys: {missing}"


# ---------------------------------------------------------------------------
# 5. Comments — both tracker kinds (AC #2)
# ---------------------------------------------------------------------------


class TestCommentsMixedTrackers:
    """GET and POST /api/v1/issues/{id}/comments work for both tracker kinds."""

    def test_get_comments_for_backlog_issue(self, client):
        bl = _backlog_issue("TASK-20", "proj-backlog")
        tracker = _make_tracker([bl])
        tracker.fetch_comments.return_value = [{"id": "c1", "text": "hello"}]
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-20/comments",
                params={"project_id": "proj-backlog"},
            )

        assert resp.status_code == 200
        assert resp.json() == [{"id": "c1", "text": "hello"}]
        tracker.fetch_comments.assert_called_with("TASK-20")

    def test_get_comments_for_github_issue(self, client):
        gh = _github_issue("acme/tasks#20", "20", "proj-github")
        tracker = _make_tracker([gh])
        tracker.fetch_comments.return_value = [{"id": "gc1", "text": "github comment"}]
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-github", "mygh", "github_issues")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/GH_20/comments",
                params={"project_id": "proj-github"},
            )

        assert resp.status_code == 200
        assert resp.json() == [{"id": "gc1", "text": "github comment"}]

    def test_post_comment_to_backlog_issue(self, client):
        bl = _backlog_issue("TASK-30", "proj-backlog")
        tracker = _make_tracker([bl])
        tracker.add_comment.return_value = {"id": "new-c", "text": "hi"}
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker
        orch.request_refresh = MagicMock()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-30/comments",
                json={"text": "hi", "project_id": "proj-backlog"},
            )

        assert resp.status_code == 201
        tracker.add_comment.assert_called_once()

    def test_post_comment_to_github_issue_calls_github_tracker(self, client):
        gh = _github_issue("acme/tasks#30", "30", "proj-github")
        tracker = _make_tracker([gh])
        tracker.add_comment.return_value = {"id": "gh-c2", "text": "nice"}
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-github", "mygh", "github_issues")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker
        orch.request_refresh = MagicMock()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/GH_30/comments",
                json={
                    "text": "nice",
                    "project_id": "proj-github",
                    "issue_key": "acme/tasks#30",
                },
            )

        assert resp.status_code == 201
        tracker.add_comment.assert_called_once()

    def test_post_comment_backlog_not_github_tracker(self, client):
        """Comment posted to a Backlog project must NOT touch the GitHub tracker."""
        bl = _backlog_issue("TASK-40", "proj-backlog")
        gh = _github_issue("acme/tasks#40", "40", "proj-github")
        bl_tracker = _make_tracker([bl])
        gh_tracker = _make_tracker([gh])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [
            _project("proj-backlog", "myproject"),
            _project("proj-github", "mygh", "github_issues"),
        ]

        def _tracker_for(pid):
            return bl_tracker if pid == "proj-backlog" else gh_tracker

        orch._tracker_for_project.side_effect = _tracker_for
        orch.tracker = bl_tracker
        orch.request_refresh = MagicMock()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues/TASK-40/comments",
                json={"text": "test", "project_id": "proj-backlog"},
            )

        bl_tracker.add_comment.assert_called_once()
        gh_tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Labels — both tracker kinds (AC #2)
# ---------------------------------------------------------------------------


class TestLabelsMixedTrackers:
    """POST /api/v1/issues/{id}/labels adds label on the correct tracker."""

    def test_add_label_to_backlog_issue(self, client):
        bl = _backlog_issue("TASK-50", "proj-backlog")
        tracker = _make_tracker([bl])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-50/labels",
                json={"label": "needs:frontend", "project_id": "proj-backlog"},
            )

        assert resp.status_code == 201
        tracker.add_label.assert_called_once_with("TASK-50", "needs:frontend")

    def test_add_label_to_github_issue(self, client):
        gh = _github_issue("acme/tasks#50", "50", "proj-github")
        tracker = _make_tracker([gh])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-github", "mygh", "github_issues")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/GH_50/labels",
                json={
                    "label": "area:api",
                    "project_id": "proj-github",
                    "issue_key": "acme/tasks#50",
                },
            )

        assert resp.status_code == 201
        tracker.add_label.assert_called_once()

    def test_add_label_backlog_not_github_tracker(self, client):
        """Adding label to Backlog issue must NOT call the GitHub tracker."""
        bl = _backlog_issue("TASK-60", "proj-backlog")
        gh = _github_issue("acme/tasks#60", "60", "proj-github")
        bl_tracker = _make_tracker([bl])
        gh_tracker = _make_tracker([gh])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [
            _project("proj-backlog", "myproject"),
            _project("proj-github", "mygh", "github_issues"),
        ]

        def _tracker_for(pid):
            return bl_tracker if pid == "proj-backlog" else gh_tracker

        orch._tracker_for_project.side_effect = _tracker_for
        orch.tracker = bl_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues/TASK-60/labels",
                json={"label": "area:core", "project_id": "proj-backlog"},
            )

        bl_tracker.add_label.assert_called_once()
        gh_tracker.add_label.assert_not_called()


# ---------------------------------------------------------------------------
# 7. Create flows — routes to correct tracker (AC #2)
# ---------------------------------------------------------------------------


class TestCreateFlowsMixedTrackers:
    """POST /api/v1/issues routes to the correct tracker based on project_id."""

    def test_create_for_backlog_project_calls_backlog_tracker(self, client):
        created = _backlog_issue("TASK-70", "proj-backlog")
        bl_tracker = MagicMock()
        bl_tracker.create_issue.return_value = created
        bl_tracker.add_label = MagicMock()
        gh_tracker = MagicMock()
        orch = MagicMock()
        orch.project_store.list_all.return_value = [
            _project("proj-backlog", "myproject"),
            _project("proj-github", "mygh", "github_issues"),
        ]
        proj_mock = MagicMock()
        proj_mock.id = "proj-backlog"
        proj_mock.repo_path = "/tmp/fake"
        orch.project_store.get.return_value = proj_mock
        orch._tracker_for_project.return_value = bl_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "New backlog task", "project_id": "proj-backlog"},
            )

        assert resp.status_code == 201
        bl_tracker.create_issue.assert_called_once()

    def test_create_for_github_project_calls_github_tracker(self, client):
        created = _github_issue("acme/tasks#70", "70", "proj-github")
        gh_tracker = MagicMock()
        gh_tracker.create_issue.return_value = created
        gh_tracker.add_label = MagicMock()
        orch = MagicMock()
        orch.project_store.list_all.return_value = [
            _project("proj-github", "mygh", "github_issues"),
        ]
        proj_mock = MagicMock()
        proj_mock.id = "proj-github"
        proj_mock.repo_path = "/tmp/fake"
        orch.project_store.get.return_value = proj_mock
        orch._tracker_for_project.return_value = gh_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "New GitHub task", "project_id": "proj-github"},
            )

        assert resp.status_code == 201
        gh_tracker.create_issue.assert_called_once()

    def test_create_backlog_response_has_null_tracker_kind(self, client):
        """Creating on a Backlog project returns tracker_kind=null."""
        created = _backlog_issue("TASK-71", "proj-backlog")
        bl_tracker = MagicMock()
        bl_tracker.create_issue.return_value = created
        bl_tracker.add_label = MagicMock()
        orch = MagicMock()
        proj_mock = MagicMock()
        proj_mock.id = "proj-backlog"
        proj_mock.repo_path = "/tmp/fake"
        orch.project_store.get.return_value = proj_mock
        orch._tracker_for_project.return_value = bl_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "BL task", "project_id": "proj-backlog"},
            )

        assert resp.status_code == 201
        assert resp.json()["issue"]["tracker_kind"] is None

    def test_create_github_response_has_tracker_kind_github_issues(self, client):
        """Creating on a GitHub project returns tracker_kind='github_issues'."""
        created = _github_issue("acme/tasks#72", "72", "proj-github")
        gh_tracker = MagicMock()
        gh_tracker.create_issue.return_value = created
        gh_tracker.add_label = MagicMock()
        orch = MagicMock()
        proj_mock = MagicMock()
        proj_mock.id = "proj-github"
        proj_mock.repo_path = "/tmp/fake"
        orch.project_store.get.return_value = proj_mock
        orch._tracker_for_project.return_value = gh_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "GH task", "project_id": "proj-github"},
            )

        assert resp.status_code == 201
        assert resp.json()["issue"]["tracker_kind"] == "github_issues"


# ---------------------------------------------------------------------------
# 8. Status updates — both tracker kinds (AC #2)
# ---------------------------------------------------------------------------


class TestStatusUpdatesMixedTrackers:
    """PATCH /api/v1/issues/{id} works for both Backlog and GitHub issues."""

    def _make_update_orch(self, issue: Issue) -> MagicMock:
        tracker = _make_tracker([issue])
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.config.tracker_terminal_states = ["Done"]
        orch.state.running = {}
        orch.state.retry_attempts = {}
        return orch, tracker

    def test_update_status_backlog_issue(self, client):
        bl = _backlog_issue("TASK-80", "proj-backlog")
        orch, tracker = self._make_update_orch(bl)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-80",
                json={"project_id": "proj-backlog", "status": "In Progress"},
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once()
        call_kwargs = tracker.update_issue.call_args[1]
        assert call_kwargs.get("status") == "In Progress"

    def test_update_status_github_issue(self, client):
        gh = _github_issue("acme/tasks#80", "80", "proj-github")
        orch, tracker = self._make_update_orch(gh)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/GH_80",
                json={
                    "project_id": "proj-github",
                    "status": "Done",
                    "issue_key": "acme/tasks#80",
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once()

    def test_update_priority_backlog_issue(self, client):
        bl = _backlog_issue("TASK-81", "proj-backlog")
        orch, tracker = self._make_update_orch(bl)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/TASK-81",
                json={"project_id": "proj-backlog", "priority": 1},
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once()
        call_kwargs = tracker.update_issue.call_args[1]
        # The server converts priority to str before forwarding to the tracker.
        assert str(call_kwargs.get("priority")) == "1"

    def test_update_priority_github_issue(self, client):
        gh = _github_issue("acme/tasks#81", "81", "proj-github")
        orch, tracker = self._make_update_orch(gh)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/GH_81",
                json={
                    "project_id": "proj-github",
                    "priority": 2,
                    "issue_key": "acme/tasks#81",
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once()


# ---------------------------------------------------------------------------
# 9. Cache invalidation after mutations
# ---------------------------------------------------------------------------


class TestCacheInvalidationMixedTrackers:
    """Status update, comment, and label operations each invalidate issues:all."""

    def test_status_update_invalidates_issues_all_cache(self, client):
        bl = _backlog_issue("TASK-90", "proj-backlog")
        tracker = _make_tracker([bl])
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.config.tracker_terminal_states = ["Done"]
        orch.state.running = {}
        orch.state.retry_attempts = {}

        # Seed the cache
        server_module._api_cache.set("issues:all", {"Open": []}, ttl_ms=60_000)
        assert server_module._api_cache.get("issues:all") is not None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.patch(
                "/api/v1/issues/TASK-90",
                json={"project_id": "proj-backlog", "status": "In Progress"},
            )

        assert server_module._api_cache.get("issues:all") is None, (
            "issues:all cache should be invalidated after status update"
        )

    def test_comment_post_invalidates_issues_all_cache(self, client):
        bl = _backlog_issue("TASK-91", "proj-backlog")
        tracker = _make_tracker([bl])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker
        orch.request_refresh = MagicMock()

        server_module._api_cache.set("issues:all", {"Open": []}, ttl_ms=60_000)
        assert server_module._api_cache.get("issues:all") is not None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues/TASK-91/comments",
                json={"text": "test comment", "project_id": "proj-backlog"},
            )

        assert server_module._api_cache.get("issues:all") is None, (
            "issues:all cache should be invalidated after comment post"
        )

    def test_label_add_invalidates_issues_all_cache(self, client):
        bl = _backlog_issue("TASK-92", "proj-backlog")
        tracker = _make_tracker([bl])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-backlog", "myproject")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        server_module._api_cache.set("issues:all", {"Open": []}, ttl_ms=60_000)
        assert server_module._api_cache.get("issues:all") is not None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues/TASK-92/labels",
                json={"label": "area:test", "project_id": "proj-backlog"},
            )

        assert server_module._api_cache.get("issues:all") is None, (
            "issues:all cache should be invalidated after label add"
        )

    def test_github_status_update_invalidates_issues_all_cache(self, client):
        gh = _github_issue("acme/tasks#92", "92", "proj-github")
        tracker = _make_tracker([gh])
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.config.tracker_terminal_states = ["Done"]
        orch.state.running = {}
        orch.state.retry_attempts = {}

        server_module._api_cache.set("issues:all", {"Open": []}, ttl_ms=60_000)
        assert server_module._api_cache.get("issues:all") is not None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.patch(
                "/api/v1/issues/GH_92",
                json={
                    "project_id": "proj-github",
                    "status": "Done",
                    "issue_key": "acme/tasks#92",
                },
            )

        assert server_module._api_cache.get("issues:all") is None, (
            "issues:all cache should be invalidated after GitHub issue status update"
        )

    def test_github_label_add_invalidates_issues_all_cache(self, client):
        gh = _github_issue("acme/tasks#93", "93", "proj-github")
        tracker = _make_tracker([gh])
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_project("proj-github", "mygh", "github_issues")]
        orch._tracker_for_project.return_value = tracker
        orch.tracker = tracker

        server_module._api_cache.set("issues:all", {"Open": []}, ttl_ms=60_000)
        assert server_module._api_cache.get("issues:all") is not None

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            client.post(
                "/api/v1/issues/GH_93/labels",
                json={
                    "label": "area:gh",
                    "project_id": "proj-github",
                    "issue_key": "acme/tasks#93",
                },
            )

        assert server_module._api_cache.get("issues:all") is None, (
            "issues:all cache should be invalidated after GitHub issue label add"
        )


# ---------------------------------------------------------------------------
# 10. Tracker identity display — board entries (AC #2)
# ---------------------------------------------------------------------------


class TestTrackerIdentityDisplayBoard:
    """Board entries always expose tracker identity fields correctly."""

    def test_backlog_issue_url_is_none_when_not_set(self):
        bl = _backlog_issue("TASK-100", "proj-backlog")
        orch = _make_mixed_orch([bl], [])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["url"] is None

    def test_backlog_issue_url_uses_provider_url_when_set(self):
        bl = _backlog_issue("TASK-101", "proj-backlog")
        bl.provider_url = "https://backlog.example.com/TASK-101"
        orch = _make_mixed_orch([bl], [])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["url"] == "https://backlog.example.com/TASK-101"

    def test_github_issue_url_uses_provider_url(self):
        gh = _github_issue("acme/tasks#101", "101", "proj-github")
        orch = _make_mixed_orch([], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["url"] == "https://github.com/acme/tasks/issues/101"

    def test_backlog_is_legacy_false_by_default(self):
        bl = _backlog_issue("TASK-102", "proj-backlog")
        orch = _make_mixed_orch([bl], [])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["is_legacy"] is False

    def test_legacy_backlog_is_legacy_true(self):
        bl = _backlog_issue("TASK-103", "proj-backlog", is_legacy=True)
        orch = _make_mixed_orch([bl], [])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["is_legacy"] is True

    def test_github_issue_has_full_tracker_owner_repo(self):
        gh = _github_issue("acme/tasks#104", "104", "proj-github")
        orch = _make_mixed_orch([], [gh])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]
        assert entry["tracker_owner"] == "acme"
        assert entry["tracker_repo"] == "tasks"
        assert entry["issue_number"] == "104"
        assert entry["managed_repo"] == "acme/code"
        assert entry["target_branch"] == "main"

    def test_mixed_board_entries_are_sortable_by_priority(self):
        """Mixed board entries are sorted by priority (no KeyError on None tracker fields)."""
        bl_low = _backlog_issue("TASK-200", "proj-backlog")
        bl_low.priority = 3
        gh_high = _github_issue("acme/tasks#200", "200", "proj-github")
        gh_high.priority = 1
        orch = _make_mixed_orch([bl_low], [gh_high])

        data = server_module._fetch_and_serialize_issues(orch)
        open_entries = data.get("Open", [])
        assert len(open_entries) == 2
        # Priority 1 (highest) should come first
        assert open_entries[0]["priority"] == 1
        assert open_entries[1]["priority"] == 3
