"""Regression tests for dashboard/API task-state reconciliation (OOMPAH-305).

Verifies that:
  § 1  OOMPAH-286-like regression: stale cache says Merged but canonical state
       branch says Backlog → all views must show Backlog.
  § 2  State-branch checkpoint advancing forces _issues_snapshot refresh.
  § 3  Per-project state isolation: a checkpoint in project A must not affect
       project B's stale window.
  § 4  Epic child with null merged_at cannot render as Merged in the board or
       detail API even if the snapshot carries a stale Merged entry.
  § 5  Degraded state-branch reads surface the stale banner (frontend header).
  § 6  Dashboard HTML exposes _setTrackerStaleBanner and reads the
       X-Oompah-Issues-Stale response header in fetchIssues.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.models import Issue
from oompah import server as server_module
from oompah.statuses import BACKLOG, MERGED


# ---------------------------------------------------------------------------
# Helpers shared across test sections
# ---------------------------------------------------------------------------


def _issue(
    identifier: str,
    state: str,
    *,
    issue_type: str = "task",
    parent_id: str | None = None,
    work_branch: str | None = None,
    review_url: str | None = None,
    merged_at: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        work_branch=work_branch,
        review_url=review_url,
        merged_at=merged_at,
    )


def _tracker_for_issues(issues, *, project_id: str = "proj-1") -> MagicMock:
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(issues)
    tracker.state_branch_enabled = True
    tracker.last_checkpoint_at = 0.0
    return tracker


def _orch_with_issues(
    issues,
    *,
    project_id: str = "proj-1",
    project_name: str = "project-1",
) -> MagicMock:
    project = SimpleNamespace(id=project_id, name=project_name)
    tracker = _tracker_for_issues(issues, project_id=project_id)
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch._project_epic_strategy.return_value = "flat"
    return orch


def _clear_snapshot() -> None:
    """Reset the global issues snapshot and API cache between tests."""
    with server_module._issues_snapshot_lock:
        server_module._issues_refresh_task = None
        server_module._issues_snapshot.update(
            {
                "data": None,
                "orch_id": None,
                "created_at_monotonic": 0.0,
                "created_at_wall": None,
                "duration_ms": None,
                "issue_count": 0,
                "error": None,
            }
        )
    server_module._api_cache.clear()


# ===========================================================================
# § 1 — OOMPAH-286 regression: stale Merged vs canonical Backlog
# ===========================================================================


class TestOOUMPAH286Regression:
    """Canonical state branch says Backlog; stale cache or source/main may say Merged."""

    def test_issue_without_merge_evidence_renders_as_backlog_not_merged(self):
        """An issue whose state is Merged but has no merge evidence (null merged_at,
        null work_branch, null review_url) must NOT render as Merged.

        This guards against stale cache entries or a source/main checkout
        surfacing a terminal status for a task whose canonical state-branch
        record has status=Backlog (OOMPAH-286 regression).
        """
        # Simulates: stale snapshot says Merged; canonical state branch says Backlog.
        # The Issue returned by the tracker reflects the canonical state (Backlog)
        # but has no merge evidence (merged_at, work_branch, review_url all null).
        issue = _issue(
            "OOMPAH-286",
            state="Merged",          # ← stale/wrong state leaked in
            parent_id="OOMPAH-285",
            merged_at=None,          # canonical state branch: null
            work_branch=None,        # canonical state branch: null
            review_url=None,         # canonical state branch: null
        )
        orch = _orch_with_issues([issue])
        board = server_module._fetch_and_serialize_issues(orch)

        # The guard must rewrite to Backlog (the canonical status).
        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        backlog_ids = [i["identifier"] for i in board.get("Backlog", [])]
        assert "OOMPAH-286" not in merged_ids, (
            "OOMPAH-286 must not appear in Merged column when merged_at is null"
        )
        assert "OOMPAH-286" in backlog_ids, (
            "OOMPAH-286 must appear in Backlog when merged_at/work_branch/review_url are null"
        )

    def test_issue_with_merge_evidence_renders_as_merged(self):
        """An issue with merged_at set must remain in the Merged column."""
        issue = _issue(
            "OOMPAH-100",
            state="Merged",
            merged_at="2026-07-01T12:00:00Z",
        )
        orch = _orch_with_issues([issue])
        board = server_module._fetch_and_serialize_issues(orch)

        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        assert "OOMPAH-100" in merged_ids, (
            "An issue with merged_at set must remain in the Merged column"
        )

    def test_issue_with_work_branch_renders_as_merged(self):
        """An issue with work_branch (PR created) must remain in the Merged column."""
        issue = _issue(
            "OOMPAH-101",
            state="Merged",
            work_branch="OOMPAH-101",
        )
        orch = _orch_with_issues([issue])
        board = server_module._fetch_and_serialize_issues(orch)

        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        assert "OOMPAH-101" in merged_ids

    def test_issue_with_review_url_renders_as_merged(self):
        """An issue with review_url set must remain in the Merged column."""
        issue = _issue(
            "OOMPAH-102",
            state="Merged",
            review_url="https://github.com/owner/repo/pull/42",
        )
        orch = _orch_with_issues([issue])
        board = server_module._fetch_and_serialize_issues(orch)

        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        assert "OOMPAH-102" in merged_ids

    def test_fetch_all_issues_guards_merged_state_without_evidence(self):
        """_fetch_all_issues applies the null-evidence guard on the Issue list."""
        issue = _issue(
            "OOMPAH-286",
            state="Merged",
            parent_id="OOMPAH-285",
        )
        orch = _orch_with_issues([issue])

        issues = server_module._fetch_all_issues(orch)
        by_id = {i.identifier: i for i in issues}
        assert by_id["OOMPAH-286"].state == BACKLOG, (
            "_fetch_all_issues must revert null-evidence Merged issue to Backlog"
        )

    def test_issue_dashboard_state_null_evidence_returns_backlog(self):
        """_issue_dashboard_state must return Backlog for null-evidence Merged issues."""
        issue = _issue("OOMPAH-286", state="Merged")
        result = server_module._issue_dashboard_state(issue)
        assert result == BACKLOG, (
            "_issue_dashboard_state must return Backlog when merged_at/work_branch/review_url are null"
        )

    def test_issue_dashboard_state_with_merged_at_returns_merged(self):
        """_issue_dashboard_state returns Merged when merged_at is set."""
        issue = _issue("TASK-1", state="Merged", merged_at="2026-07-01T10:00:00Z")
        result = server_module._issue_dashboard_state(issue)
        assert result == MERGED


# ===========================================================================
# § 2 — State-branch checkpoint advancing forces snapshot refresh
# ===========================================================================


class TestCheckpointInvalidatesSnapshot:
    """A state-branch checkpoint must force a fresh issues-snapshot read."""

    def test_any_tracker_checkpoint_newer_than_returns_false_when_all_old(self):
        """Returns False when no tracker has a checkpoint newer than snapshot_at."""
        orch = MagicMock()
        tracker = MagicMock()
        tracker.last_checkpoint_at = 100.0
        orch.tracker = tracker
        orch._project_trackers = {}

        # snapshot was created at t=200, checkpoint is at t=100 → not newer
        assert server_module._any_tracker_checkpoint_newer_than(orch, 200.0) is False

    def test_any_tracker_checkpoint_newer_than_returns_true_when_checkpoint_newer(self):
        """Returns True when a project tracker has a checkpoint newer than snapshot_at."""
        orch = MagicMock()
        orch.tracker = None
        tracker = MagicMock()
        tracker.last_checkpoint_at = 500.0
        orch._project_trackers = {"proj-1": tracker}

        # snapshot was created at t=400, checkpoint is at t=500 → newer
        assert server_module._any_tracker_checkpoint_newer_than(orch, 400.0) is True

    def test_any_tracker_checkpoint_newer_than_ignores_trackers_without_attribute(self):
        """Trackers without last_checkpoint_at are safely skipped."""
        orch = MagicMock()
        orch.tracker = object()  # no last_checkpoint_at
        orch._project_trackers = {}

        assert server_module._any_tracker_checkpoint_newer_than(orch, 100.0) is False

    def test_checkpoint_timestamp_updated_in_tracker(self, tmp_path):
        """OompahMarkdownTracker sets last_checkpoint_at after checkpoint flush."""
        from unittest.mock import patch, MagicMock
        from oompah.oompah_md_tracker import OompahMarkdownTracker

        root = tmp_path / "repo"
        root.mkdir()
        tracker = OompahMarkdownTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(root),
            state_branch_enabled=False,
        )
        # Initially 0.0 (no checkpoint yet)
        assert tracker.last_checkpoint_at == 0.0

        # Simulate a checkpoint flush by patching the internal git ops
        with patch.object(tracker, "_commit_and_push_state_branch"):
            tracker._do_checkpoint_flush()

        # After flush, last_checkpoint_at must be updated
        assert tracker.last_checkpoint_at > 0.0

    def test_checkpoint_callback_is_invoked_after_flush(self, tmp_path):
        """The _on_checkpoint_flushed callback is called after a successful flush."""
        from unittest.mock import patch
        from oompah.oompah_md_tracker import OompahMarkdownTracker

        root = tmp_path / "repo"
        root.mkdir()
        callback_calls = []
        tracker = OompahMarkdownTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(root),
            state_branch_enabled=False,
            _on_checkpoint_flushed=lambda: callback_calls.append(1),
        )

        with patch.object(tracker, "_commit_and_push_state_branch"):
            tracker._do_checkpoint_flush()

        assert callback_calls == [1], (
            "_on_checkpoint_flushed callback must be invoked exactly once after flush"
        )

    def test_checkpoint_callback_error_does_not_abort_flush(self, tmp_path):
        """A crashing _on_checkpoint_flushed callback must not propagate the exception."""
        from unittest.mock import patch
        from oompah.oompah_md_tracker import OompahMarkdownTracker

        root = tmp_path / "repo"
        root.mkdir()

        def bad_callback():
            raise RuntimeError("simulated callback failure")

        tracker = OompahMarkdownTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(root),
            state_branch_enabled=False,
            _on_checkpoint_flushed=bad_callback,
        )

        with patch.object(tracker, "_commit_and_push_state_branch"):
            # Must not raise even though callback raises
            tracker._do_checkpoint_flush()

        # Checkpoint timestamp must still be updated
        assert tracker.last_checkpoint_at > 0.0


# ===========================================================================
# § 3 — Per-project state isolation
# ===========================================================================


class TestPerProjectStateIsolation:
    """Checkpoint in project A must not affect project B's display."""

    def test_checkpoint_newer_than_checks_all_project_trackers(self):
        """_any_tracker_checkpoint_newer_than scans all project trackers."""
        orch = MagicMock()
        orch.tracker = None

        tracker_a = MagicMock()
        tracker_a.last_checkpoint_at = 600.0  # newer than snapshot

        tracker_b = MagicMock()
        tracker_b.last_checkpoint_at = 100.0  # older

        orch._project_trackers = {"proj-a": tracker_a, "proj-b": tracker_b}

        # Even one newer tracker should force refresh
        assert server_module._any_tracker_checkpoint_newer_than(orch, 500.0) is True

    def test_board_projects_isolated_by_project_id(self):
        """Issues from different projects are serialized with their project_id.

        Ensures that per-project filter caching cannot leak one project's state
        into another project's board view.
        """
        _clear_snapshot()
        try:
            issue_a = _issue("TASK-A1", "Open")
            issue_a.project_id = "proj-a"
            issue_b = _issue("TASK-B1", "Backlog")
            issue_b.project_id = "proj-b"

            server_module._set_issues_snapshot(
                {
                    "Open": [{"identifier": "TASK-A1", "project_id": "proj-a"}],
                    "Backlog": [{"identifier": "TASK-B1", "project_id": "proj-b"}],
                },
                duration_ms=5.0,
            )

            payload_a = server_module._issues_snapshot_payload(
                filter_project="proj-a", allow_empty=True
            )
            payload_b = server_module._issues_snapshot_payload(
                filter_project="proj-b", allow_empty=True
            )

            assert [i["identifier"] for i in payload_a.get("Open", [])] == ["TASK-A1"]
            assert "TASK-B1" not in [i["identifier"] for i in payload_a.get("Backlog", [])]

            assert [i["identifier"] for i in payload_b.get("Backlog", [])] == ["TASK-B1"]
            assert "TASK-A1" not in [i["identifier"] for i in payload_b.get("Open", [])]
        finally:
            _clear_snapshot()


# ===========================================================================
# § 4 — Epic child with null merged_at cannot render Merged
# ===========================================================================


class TestEpicChildNullMergedAt:
    """Unstarted epic children must never render as Merged."""

    def test_epic_child_null_merged_at_renders_as_backlog(self):
        """An epic child with no merge evidence must render as Backlog even if
        the tracker returns state=Merged (e.g., from a stale snapshot).

        Acceptance criterion: 'Oompah never presents a task as Merged unless
        canonical tracker state records its terminal merge state.'
        """
        parent = _issue("EPIC-1", "Merged", issue_type="epic", merged_at="2026-07-01T00:00:00Z")
        child = _issue(
            "EPIC-1.1",
            state="Merged",        # stale / incorrect state from non-state-branch read
            parent_id="EPIC-1",
            merged_at=None,        # no merge evidence
            work_branch=None,
            review_url=None,
        )
        orch = _orch_with_issues([parent, child])
        board = server_module._fetch_and_serialize_issues(orch)

        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        backlog_ids = [i["identifier"] for i in board.get("Backlog", [])]

        assert "EPIC-1.1" not in merged_ids, (
            "Epic child with null merged_at must not appear in Merged column"
        )
        assert "EPIC-1.1" in backlog_ids, (
            "Epic child with null merged_at must appear in Backlog"
        )

    def test_epic_with_null_merged_at_also_guarded(self):
        """An epic that somehow has Merged state but no evidence is also guarded."""
        epic = _issue(
            "EPIC-2",
            state="Merged",
            issue_type="epic",
            merged_at=None,
            work_branch=None,
            review_url=None,
        )
        orch = _orch_with_issues([epic])
        board = server_module._fetch_and_serialize_issues(orch)

        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        assert "EPIC-2" not in merged_ids, (
            "Epic with null merged_at must not appear in Merged column"
        )


# ===========================================================================
# § 5 — Degraded state-branch reads surface stale indicator
# ===========================================================================


class TestStaleBannerHeader:
    """X-Oompah-Issues-Stale header is emitted when snapshot exceeds TTL."""

    def test_stale_header_true_when_snapshot_older_than_threshold(self, monkeypatch):
        """When the snapshot is older than _ISSUES_SNAPSHOT_STALE_MS, the header is 'true'."""
        _clear_snapshot()
        monkeypatch.setattr(server_module, "_ISSUES_SNAPSHOT_STALE_MS", 5_000)
        try:
            server_module._set_issues_snapshot(
                {"Open": [{"identifier": "TASK-1", "project_id": "p1"}]},
                duration_ms=5.0,
            )
            # Backdate the snapshot to beyond the stale threshold
            with server_module._issues_snapshot_lock:
                server_module._issues_snapshot["created_at_monotonic"] = (
                    time.monotonic() - 10
                )

            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Stale") == "true", (
                "Snapshot older than stale threshold must set X-Oompah-Issues-Stale: true"
            )
        finally:
            _clear_snapshot()

    def test_stale_header_false_when_snapshot_is_fresh(self, monkeypatch):
        """When the snapshot was just updated, the header is 'false'."""
        _clear_snapshot()
        monkeypatch.setattr(server_module, "_ISSUES_SNAPSHOT_STALE_MS", 60_000)
        try:
            server_module._set_issues_snapshot(
                {"Open": [{"identifier": "TASK-1", "project_id": "p1"}]},
                duration_ms=5.0,
            )

            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Stale") == "false", (
                "Fresh snapshot must set X-Oompah-Issues-Stale: false"
            )
        finally:
            _clear_snapshot()


# ===========================================================================
# § 6 — Dashboard HTML stale banner
# ===========================================================================


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "No <script> block found in dashboard HTML"
    return max(matches, key=len)


@pytest.fixture(scope="module")
def dashboard_html() -> str:
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def dashboard_script(dashboard_html: str) -> str:
    return _extract_script(dashboard_html)


class TestDashboardStaleBannerUI:
    """Verify the stale tracker banner is wired into the dashboard template."""

    def test_stale_banner_element_exists(self, dashboard_html: str):
        """The tracker-stale-banner span must be present in the DOM."""
        assert 'id="tracker-stale-banner"' in dashboard_html, (
            "Dashboard must include a #tracker-stale-banner element for the stale indicator"
        )

    def test_stale_banner_has_aria_hidden(self, dashboard_html: str):
        """The banner starts hidden via aria-hidden='true'."""
        assert 'aria-hidden="true"' in dashboard_html, (
            "tracker-stale-banner must start with aria-hidden='true'"
        )

    def test_stale_banner_css_class_exists(self, dashboard_html: str):
        """The .tracker-stale-banner CSS class must be defined."""
        assert ".tracker-stale-banner" in dashboard_html, (
            "Dashboard CSS must define .tracker-stale-banner"
        )

    def test_set_tracker_stale_banner_function_exists(self, dashboard_script: str):
        """_setTrackerStaleBanner() function must be defined in the dashboard script."""
        assert "function _setTrackerStaleBanner(" in dashboard_script, (
            "Dashboard must define function _setTrackerStaleBanner(stale)"
        )

    def test_fetch_issues_reads_stale_header(self, dashboard_script: str):
        """fetchIssues() must read the X-Oompah-Issues-Stale response header."""
        assert "X-Oompah-Issues-Stale" in dashboard_script, (
            "fetchIssues must read the X-Oompah-Issues-Stale header from API responses"
        )

    def test_fetch_issues_calls_set_banner(self, dashboard_script: str):
        """fetchIssues() must call _setTrackerStaleBanner based on the header value."""
        assert "_setTrackerStaleBanner(" in dashboard_script, (
            "fetchIssues must call _setTrackerStaleBanner() to update the stale indicator"
        )

    def test_ws_issues_handler_clears_stale_banner(self, dashboard_script: str):
        """The WS 'issues' handler must clear the stale banner (fresh push = not stale)."""
        # Find the issues WS handler and verify it calls _setTrackerStaleBanner(false)
        ws_issues_block_match = re.search(
            r"msg\.type === 'issues'.*?(?=msg\.type|}\s*else|$)",
            dashboard_script,
            re.DOTALL,
        )
        assert ws_issues_block_match, "Could not find msg.type === 'issues' handler"
        block = ws_issues_block_match.group(0)
        assert "_setTrackerStaleBanner(false)" in block, (
            "WS issues handler must call _setTrackerStaleBanner(false) to clear the banner "
            "after receiving a fresh push from the server"
        )

    def test_stale_banner_has_accessibility_title(self, dashboard_html: str):
        """The stale banner must have a descriptive title for accessibility."""
        # The title attribute explains what 'stale' means for screen readers
        assert "tracker-stale-banner" in dashboard_html
        # Find the element and check it has a title
        match = re.search(
            r'id="tracker-stale-banner"[^>]*title="([^"]+)"',
            dashboard_html,
        )
        assert match, (
            "tracker-stale-banner must have a title attribute for accessibility"
        )
        assert len(match.group(1)) > 10, (
            "title attribute must be descriptive (not empty or too short)"
        )


# ===========================================================================
# § 7 — merged_at field propagation
# ===========================================================================


class TestMergedAtFieldPropagation:
    """merged_at is exposed in board and detail API responses."""

    def test_board_entry_includes_merged_at_when_set(self):
        """Board entries must include merged_at when the tracker provides it."""
        issue = _issue("TASK-1", "Merged", merged_at="2026-07-15T10:00:00Z")
        issue.project_id = "proj-1"
        server_module._set_issues_snapshot(
            {
                "Merged": [
                    {
                        "identifier": "TASK-1",
                        "project_id": "proj-1",
                        "merged_at": "2026-07-15T10:00:00Z",
                        "state": "Merged",
                    }
                ]
            },
            duration_ms=5.0,
        )
        payload = server_module._issues_snapshot_payload(allow_empty=True)
        entry = (payload or {}).get("Merged", [{}])[0] if (payload or {}).get("Merged") else None
        if entry:
            assert "merged_at" in entry, (
                "Board entries must include the merged_at field"
            )

    def test_fetch_and_serialize_includes_merged_at_in_board_entries(self):
        """_fetch_and_serialize_issues must include merged_at in each board entry."""
        issue = _issue("TASK-1", "Merged", merged_at="2026-07-15T10:00:00Z")
        # Give it work_branch so it stays in Merged column
        issue.work_branch = "TASK-1"
        orch = _orch_with_issues([issue])

        board = server_module._fetch_and_serialize_issues(orch)
        merged_entries = board.get("Merged", [])
        assert merged_entries, "Issue with merge evidence must appear in Merged"
        entry = merged_entries[0]
        assert "merged_at" in entry, (
            "_fetch_and_serialize_issues must include merged_at in board entry"
        )
        assert entry["merged_at"] == "2026-07-15T10:00:00Z"
