"""Regression tests for oompah-zlz_2-w9m — YOLO watchdog detectors D1/D3/D4.

These tests cover the explicit acceptance criteria from the issue, with
emphasis on the live miss that motivated the bug:

* The trickle PR #56 / trickle-iq1 scenario (D3): an open PR with
  has_conflicts=True and a PINNED orphan-recovery cache entry pointing
  at a closed task → reset cache + refile within 2 ticks.
* D1 diagnostic-context body assertions (latest error + structured fields).
* D3 negative cases (open recovery task → no fire; missing cache → no fire).
* D3 ci-fix kind parity (D3 also covers ci_status='failed').
* D3 with disappeared task (fetch_issue_detail returns None).
* D4 strategy-switch granularity (sub-threshold non-switch, multi-project
  isolation).
* Multi-project state pruning isolation.
* run_all_detectors interaction (D1+D3 same-PR ordering, empty input,
  D2-only path).

Companion to tests/test_yolo_watchdog.py — original 40-test suite from
oompah-zlz_2-jg4. Splitting these into a separate file makes the
regression set easy to bisect.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest
from oompah.yolo_watchdog import (
    CoverageRecord,
    D1_RECURRENCE_THRESHOLD,
    D4_ALREADY_MERGEABLE_THRESHOLD,
    YoloActionRecord,
    detect_d1_recurrent_failures,
    run_all_detectors,
)


# ---------------------------------------------------------------------------
# Local fixtures — duplicated from tests/test_yolo_watchdog.py so this file
# is self-contained and reorderable.
# ---------------------------------------------------------------------------


def _make_review(
    review_id: str,
    source_branch: str = "feat-branch",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    draft: bool = False,
    auto_merge_enabled: bool = False,
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch="main",
        created_at="2025-01-01",
        updated_at="2025-01-02",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        draft=draft,
        auto_merge_enabled=auto_merge_enabled,
    )


def _make_project(project_id: str = "proj-1", repo_url: str = "https://github.com/org/repo"):
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.merge_queue_enabled = False
    p.paused = False
    p.yolo = True
    p.access_token = None
    return p


def _make_orchestrator(tmp_path, projects=None):
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ---------------------------------------------------------------------------
# Live trickle-iq1 fixture (D3 acceptance criterion).
# ---------------------------------------------------------------------------


class TestTrickleIq1TwoTickRefile:
    """Reproduces the exact scenario from the bug report.

    Live miss timeline (2026-05-08):
      * Trickle PR #56 has has_conflicts=True for hours.
      * Orphan-recovery cache pinned (project, '56', 'merge-conflict')
        at trickle-iq1, which the operator closed without resolving.
      * No new task was filed automatically; operator had to manually
        re-file a P0 merge-conflict task.

    D3 acceptance criterion (verbatim):
      "an open PR with has_conflicts=True AND no current open
       merge-conflict task AND a PINNED entry in the orphan-recovery
       cache → reset the cache entry, allow the next tick to refile via
       the existing 975 path. Tested fixture: simulate the trickle-iq1
       scenario and assert the watchdog re-files within 2 ticks."

    Verifies:
      Tick 1: D3 detects the incoherence, resets the cache, files a
              P0 watchdog task.
      Tick 2: _file_orphan_recovery_task is reached (cache empty), and
              a fresh merge-conflict orphan-recovery task is filed.
    """

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_two_tick_refile_for_trickle_iq1_scenario(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project(project_id="proj-trickle")
        provider = MagicMock()
        provider.get_review.return_value = _make_review(
            "56", source_branch="epic/callback-auth", has_conflicts=True,
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "NVIDIA-Omniverse/trickle"

        # Pre-existing orphan-recovery task, but operator closed it.
        closed_recovery = Issue(
            id="trickle-iq1", identifier="trickle-iq1",
            title="merge conflict on PR #56 (epic/callback-auth)",
            description="recovery", state="closed", labels=["merge-conflict"],
        )

        mock_tracker = MagicMock()

        # Track every issue we file. Two tasks should land:
        #  (1) the D3 watchdog P0 task (tick 1)
        #  (2) the fresh orphan-recovery task (tick 2 via 975 path)
        filed_issues = []

        # Branch lookup returns None — the operator's closed task does
        # NOT match the branch name (its identifier is trickle-iq1; the
        # PR's branch is epic/callback-auth). For the closed task, we
        # return the closed Issue. For any freshly-filed task in tick
        # 2, return an OPEN Issue so D3 doesn't re-fire on subsequent
        # ticks.
        def fetch_detail(arg):
            if arg == "trickle-iq1":
                return closed_recovery
            for nid, kw in filed_issues:
                if arg == nid:
                    return Issue(
                        id=nid, identifier=nid,
                        title=kw.get("title", ""),
                        description="recovery", state="open",
                        labels=list(kw.get("labels") or []),
                    )
            return None
        mock_tracker.fetch_issue_detail.side_effect = fetch_detail

        def create_issue(**kwargs):
            new_id = f"trickle-new-{len(filed_issues) + 1}"
            issue = MagicMock(identifier=new_id)
            filed_issues.append((new_id, kwargs))
            return issue
        mock_tracker.create_issue.side_effect = create_issue

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        # Pre-seed the orphan-recovery cache exactly as it was on
        # 2026-05-08 — pinned at trickle-iq1.
        orch._yolo_orphan_recovery_tasks[
            (project.id, "56", "merge-conflict")
        ] = "trickle-iq1"
        orch._reviews_cache = {
            project.id: [_make_review(
                "56", source_branch="epic/callback-auth", has_conflicts=True,
            )],
        }

        # ---- Tick 1: D3 detects, resets cache, files watchdog task.
        orch._yolo_review_actions_sync()
        assert (project.id, "56", "merge-conflict") not in orch._yolo_orphan_recovery_tasks, (
            "Tick 1 must reset the orphan-recovery cache entry"
        )
        d3_calls_t1 = [
            (nid, kw) for (nid, kw) in filed_issues
            if kw.get("priority") == 0 and "yolo-watchdog" in (kw.get("labels") or [])
        ]
        assert len(d3_calls_t1) == 1, (
            f"Tick 1 must file exactly one D3 watchdog task, got: {filed_issues}"
        )
        assert "coherence" in d3_calls_t1[0][1]["title"].lower()
        # Watchdog body should reference both the PR and the closed
        # task so the operator has full context without log diving.
        body = d3_calls_t1[0][1]["description"]
        assert "56" in body
        assert "merge-conflict" in body

        # ---- Tick 2: cache empty → 975 path refiles a fresh
        # merge-conflict orphan-recovery task.
        orch._yolo_review_actions_sync()
        # The fresh recovery task has priority=0 but is filed via
        # _file_orphan_recovery_task, NOT the watchdog. It should NOT
        # carry the yolo-watchdog label and the title should match the
        # 975 path's template.
        recovery_calls = [
            (nid, kw) for (nid, kw) in filed_issues
            if kw.get("priority") == 0
            and "yolo-watchdog" not in (kw.get("labels") or [])
            and "merge conflict on PR #56" in kw.get("title", "")
        ]
        assert len(recovery_calls) == 1, (
            f"Tick 2 must refile exactly one orphan-recovery task via the "
            f"975 path. All filed: {filed_issues}"
        )
        # And the cache should now point at the new orphan-recovery
        # task (so a third tick wouldn't double-file).
        new_cache_entry = orch._yolo_orphan_recovery_tasks.get(
            (project.id, "56", "merge-conflict")
        )
        assert new_cache_entry is not None, (
            "Tick 2 must repopulate the orphan-recovery cache with the new task id"
        )
        assert new_cache_entry == recovery_calls[0][0]


# ---------------------------------------------------------------------------
# Additional D3 coverage — negatives, ci-fix parity, disappeared task.
# ---------------------------------------------------------------------------


class TestOrchestratorD3NegativeCases:
    """D3 must NOT fire for the well-functioning orphan-recovery flow."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_d3_does_not_fire_when_recovery_task_still_open(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """Cached recovery task is OPEN → operator/agent is on it → no D3."""
        project = _make_project()
        provider = MagicMock()
        provider.get_review.return_value = _make_review(
            "7", source_branch="feat-7", has_conflicts=True,
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        open_recovery = Issue(
            id="rec-001", identifier="rec-001",
            title="merge conflict on PR #7",
            description="recovery", state="open", labels=["merge-conflict"],
        )
        mock_tracker = MagicMock()
        def fetch_detail(arg):
            if arg == "rec-001":
                return open_recovery
            return None
        mock_tracker.fetch_issue_detail.side_effect = fetch_detail
        mock_tracker.create_issue.return_value = MagicMock(identifier="should-not-fire")

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._yolo_orphan_recovery_tasks[
            (project.id, "7", "merge-conflict")
        ] = "rec-001"
        orch._reviews_cache = {
            project.id: [_make_review(
                "7", source_branch="feat-7", has_conflicts=True,
            )],
        }

        orch._yolo_review_actions_sync()

        # Cache should remain pinned at rec-001 — no incoherence.
        assert orch._yolo_orphan_recovery_tasks.get(
            (project.id, "7", "merge-conflict")
        ) == "rec-001"
        # No D3 watchdog task.
        watchdog_calls = [
            c for c in mock_tracker.create_issue.call_args_list
            if "yolo-watchdog" in (c.kwargs.get("labels") or [])
        ]
        assert watchdog_calls == []

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_d3_does_not_fire_without_orphan_recovery_cache_entry(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """A conflicting PR with NO cache entry isn't D3's concern.

        D3 only escalates when the orphan-recovery cache claims a task
        was filed but it's actually closed. A first-time conflict with
        no cache entry is the standard 975 path — D3 must stay silent
        and let the orphan-recovery filer act.

        Note: in tick 1, the 975 path itself fires (creating an orphan-
        recovery task). The mock returns that fresh task as OPEN when
        D3's end-of-tick check looks it up, so D3 stays silent.
        """
        project = _make_project()
        provider = MagicMock()
        provider.get_review.return_value = _make_review(
            "7", source_branch="feat-7", has_conflicts=True,
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        filed_issues: list[tuple[str, dict]] = []

        mock_tracker = MagicMock()

        def fetch_detail(arg):
            # Return None for the branch lookup (no task matches).
            # Return an OPEN Issue for any freshly-filed orphan-recovery
            # task so D3 sees a healthy cache entry.
            for nid, kw in filed_issues:
                if arg == nid:
                    return Issue(
                        id=nid, identifier=nid,
                        title=kw.get("title", ""),
                        description="recovery", state="open",
                        labels=list(kw.get("labels") or []),
                    )
            return None
        mock_tracker.fetch_issue_detail.side_effect = fetch_detail

        def create_issue(**kwargs):
            new_id = f"new-{len(filed_issues) + 1}"
            filed_issues.append((new_id, kwargs))
            return MagicMock(identifier=new_id)
        mock_tracker.create_issue.side_effect = create_issue

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        # Cache empty.
        orch._reviews_cache = {
            project.id: [_make_review(
                "7", source_branch="feat-7", has_conflicts=True,
            )],
        }

        orch._yolo_review_actions_sync()

        # An orphan-recovery task may be filed (975 path) but NOT a D3
        # watchdog task.
        d3_calls = [
            (nid, kw) for (nid, kw) in filed_issues
            if "yolo-watchdog" in (kw.get("labels") or [])
        ]
        assert d3_calls == [], f"Did not expect any D3 tasks, got: {d3_calls}"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_d3_fires_when_recovery_task_has_disappeared(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """Cache pins at an id that no longer exists → reset and refile.

        If somebody hard-deletes the recovery task (via tracker admin
        action or DB cleanup), fetch_issue_detail returns None for it.
        The cache is stale — D3 must reset it so the next tick refiles.
        """
        project = _make_project()
        provider = MagicMock()
        provider.get_review.return_value = _make_review(
            "7", source_branch="feat-7", has_conflicts=True,
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        filed_issues: list[tuple[str, dict]] = []
        mock_tracker = MagicMock()

        def fetch_detail(arg):
            # rec-deleted-001 has been hard-deleted, so no record.
            # Branch lookup also returns None.
            # New tasks filed in this tick (tick 1's D3 watchdog task +
            # any orphan-recovery refile) come back as OPEN.
            for nid, kw in filed_issues:
                if arg == nid:
                    return Issue(
                        id=nid, identifier=nid,
                        title=kw.get("title", ""),
                        description="recovery", state="open",
                        labels=list(kw.get("labels") or []),
                    )
            return None
        mock_tracker.fetch_issue_detail.side_effect = fetch_detail

        def create_issue(**kwargs):
            new_id = f"watchdog-{len(filed_issues) + 1}"
            filed_issues.append((new_id, kwargs))
            return MagicMock(identifier=new_id)
        mock_tracker.create_issue.side_effect = create_issue

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._yolo_orphan_recovery_tasks[
            (project.id, "7", "merge-conflict")
        ] = "rec-deleted-001"
        orch._reviews_cache = {
            project.id: [_make_review(
                "7", source_branch="feat-7", has_conflicts=True,
            )],
        }

        orch._yolo_review_actions_sync()

        # And a D3 watchdog task — body should mention the task id and
        # the disappearance.
        d3_calls = [
            (nid, kw) for (nid, kw) in filed_issues
            if "yolo-watchdog" in (kw.get("labels") or [])
        ]
        assert len(d3_calls) == 1, f"Expected 1 D3 task, got: {filed_issues}"
        body = d3_calls[0][1]["description"]
        assert "rec-deleted-001" in body or "no longer exists" in body

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_d3_fires_for_ci_fix_kind(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """D3 spec covers both has_conflicts AND ci_status='failed'.

        A PR with failing CI and a stale ci-fix orphan-recovery cache
        entry should trigger the same D3 reset+escalate path.
        """
        project = _make_project()
        provider = MagicMock()
        provider.get_review.return_value = _make_review(
            "8", source_branch="feat-8", ci_status="failed",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        closed_recovery = Issue(
            id="rec-ci-001", identifier="rec-ci-001",
            title="fix CI on PR #8 (feat-8)",
            description="recovery", state="closed", labels=["ci-fix"],
        )

        filed_issues: list[tuple[str, dict]] = []
        mock_tracker = MagicMock()

        def fetch_detail(arg):
            if arg == "rec-ci-001":
                return closed_recovery
            for nid, kw in filed_issues:
                if arg == nid:
                    return Issue(
                        id=nid, identifier=nid,
                        title=kw.get("title", ""),
                        description="recovery", state="open",
                        labels=list(kw.get("labels") or []),
                    )
            return None
        mock_tracker.fetch_issue_detail.side_effect = fetch_detail

        def create_issue(**kwargs):
            new_id = f"watchdog-ci-{len(filed_issues) + 1}"
            filed_issues.append((new_id, kwargs))
            return MagicMock(identifier=new_id)
        mock_tracker.create_issue.side_effect = create_issue

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._yolo_orphan_recovery_tasks[
            (project.id, "8", "ci-fix")
        ] = "rec-ci-001"
        orch._reviews_cache = {
            project.id: [_make_review(
                "8", source_branch="feat-8", ci_status="failed",
            )],
        }

        orch._yolo_review_actions_sync()

        # Cache reset, watchdog task filed.
        # NOTE: cache may have been re-populated within the same tick
        # by _yolo_retry_ci's 975 path. What matters is that the
        # original "rec-ci-001" entry was reset (and a fresh recovery
        # task may or may not have been filed in tick 1 depending on
        # the loop ordering).
        # The key assertion: a D3 watchdog task was filed for ci-fix.
        d3_calls = [
            (nid, kw) for (nid, kw) in filed_issues
            if "yolo-watchdog" in (kw.get("labels") or [])
        ]
        assert len(d3_calls) == 1
        # Body should reference ci-fix as the kind.
        body = d3_calls[0][1]["description"]
        assert "ci-fix" in body
        # And the cache must NOT still point at the closed rec-ci-001.
        current = orch._yolo_orphan_recovery_tasks.get(
            (project.id, "8", "ci-fix")
        )
        assert current != "rec-ci-001", (
            "Closed recovery task must have been evicted from the cache"
        )


# ---------------------------------------------------------------------------
# D1 diagnostic-context coverage.
# ---------------------------------------------------------------------------


class TestD1DiagnosticContext:
    """D1 acceptance criterion: task body must contain diagnostic context.

    Verbatim from issue:
      "D1: a recurring (PR, action, failure) tuple ≥5 ticks → P0 task
       filed once with diagnostic context (latest error, action history)."
    """

    def test_body_contains_latest_error_and_count(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="42", action_type="enqueue",
                outcome="failure", error_msg="rate limit exceeded",
                tick=i + 1, timestamp=0,
            )
            for i in range(D1_RECURRENCE_THRESHOLD - 1)
        ]
        # Last error is more specific.
        history.append(YoloActionRecord(
            project_id="p", review_id="42", action_type="enqueue",
            outcome="failure",
            error_msg="GitHub GraphQL: required check 'lint' has not run",
            tick=D1_RECURRENCE_THRESHOLD, timestamp=0,
        ))
        patterns = detect_d1_recurrent_failures(history)
        assert len(patterns) == 1
        body = patterns[0].body
        # Latest error must be present (most recent failure context).
        assert "required check 'lint' has not run" in body
        # Count must be present.
        assert str(D1_RECURRENCE_THRESHOLD) in body
        # Diagnostic structured fields must be present (for grepability).
        assert "project_id:" in body
        assert "review_id:" in body
        assert "action_type:" in body
        assert "consecutive_failures:" in body

    def test_body_handles_empty_error_messages(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="merge",
                outcome="failure", error_msg="",
                tick=i + 1, timestamp=0,
            )
            for i in range(D1_RECURRENCE_THRESHOLD)
        ]
        patterns = detect_d1_recurrent_failures(history)
        assert len(patterns) == 1
        # Body must not crash and must give the operator a placeholder
        # when there's no error message.
        assert "no error message captured" in patterns[0].body


# ---------------------------------------------------------------------------
# D4 strategy-switch granularity.
# ---------------------------------------------------------------------------


class TestD4StrategySwitchGranularity:
    """D4 must switch only at threshold and only for the right PR."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_no_switch_below_threshold(self, mock_slug, mock_detect, tmp_path):
        """D4 must not engage at 1 or 2 already-mergeable failures."""
        project = _make_project()
        project.merge_queue_enabled = True
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False, "Pull request is already mergeable",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("9", ci_status="passed")]}

        # Run threshold - 1 ticks. No switch yet.
        for _ in range(D4_ALREADY_MERGEABLE_THRESHOLD - 1):
            orch._yolo_review_actions_sync()

        assert (project.id, "9") not in orch._yolo_already_mergeable_switched
        # Every tick should have called enable_auto_merge (NOT
        # merge_review).
        assert provider.enable_auto_merge.call_count == D4_ALREADY_MERGEABLE_THRESHOLD - 1
        assert provider.merge_review.call_count == 0

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_already_mergeable_failures_dont_trigger_d4_for_other_projects(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """Multi-project: project A's stuck PR doesn't poison project B."""
        project_a = _make_project(project_id="proj-a", repo_url="https://github.com/org/a")
        project_a.merge_queue_enabled = True
        project_b = _make_project(project_id="proj-b", repo_url="https://github.com/org/b")
        project_b.merge_queue_enabled = True

        # Both projects share a provider mock for simplicity.
        provider = MagicMock()
        # A's PR returns "already mergeable", B's PR succeeds.
        def enable_auto_merge(slug, review_id):
            if "/a" in slug:
                return False, "Pull request is already mergeable"
            return True, ""
        provider.enable_auto_merge.side_effect = enable_auto_merge
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.side_effect = lambda url: url.replace("https://github.com/", "")

        orch = _make_orchestrator(tmp_path, projects=[project_a, project_b])
        orch._reviews_cache = {
            project_a.id: [_make_review("9", ci_status="passed")],
            project_b.id: [_make_review("9", ci_status="passed")],
        }

        for _ in range(D4_ALREADY_MERGEABLE_THRESHOLD):
            orch._yolo_review_actions_sync()

        # A's PR #9 switched to direct merge. B's PR #9 (same id, different
        # project) is unaffected.
        assert (project_a.id, "9") in orch._yolo_already_mergeable_switched
        assert (project_b.id, "9") not in orch._yolo_already_mergeable_switched


# ---------------------------------------------------------------------------
# Cross-cutting: state pruning isolation between projects.
# ---------------------------------------------------------------------------


class TestWatchdogStatePruningMultiProject:
    """When one project's cache changes, only that project's state is pruned."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pruning_one_project_leaves_other_untouched(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project_a = _make_project(project_id="proj-a", repo_url="https://github.com/org/a")
        project_b = _make_project(project_id="proj-b", repo_url="https://github.com/org/b")

        provider = MagicMock()
        provider.merge_review.return_value = (False, "boom")
        mock_detect.return_value = provider
        mock_slug.side_effect = lambda url: url.replace("https://github.com/", "")

        mock_tracker_a = MagicMock()
        mock_tracker_a.create_issue.return_value = MagicMock(identifier="wd-a-001")
        mock_tracker_b = MagicMock()
        mock_tracker_b.create_issue.return_value = MagicMock(identifier="wd-b-001")

        orch = _make_orchestrator(tmp_path, projects=[project_a, project_b])
        orch._project_trackers[project_a.id] = mock_tracker_a
        orch._project_trackers[project_b.id] = mock_tracker_b
        orch._reviews_cache = {
            project_a.id: [_make_review("11", ci_status="passed")],
            project_b.id: [_make_review("22", ci_status="passed")],
        }

        # Run enough ticks to file D1 watchdog tasks on both projects.
        for _ in range(D1_RECURRENCE_THRESHOLD):
            orch._yolo_review_actions_sync()

        # Both should be filed.
        assert any(k.startswith(f"d1:{project_a.id}:11:") for k in orch._yolo_watchdog_filed)
        assert any(k.startswith(f"d1:{project_b.id}:22:") for k in orch._yolo_watchdog_filed)

        # PR #11 in project A disappears (merged). PR #22 in B still
        # present.
        orch._reviews_cache = {
            project_a.id: [],
            project_b.id: [_make_review("22", ci_status="passed")],
        }
        orch._yolo_review_actions_sync()

        assert not any(k.startswith(f"d1:{project_a.id}:11:") for k in orch._yolo_watchdog_filed)
        # Project B still has its filed-task state — its PR didn't
        # leave the cache.
        assert any(k.startswith(f"d1:{project_b.id}:22:") for k in orch._yolo_watchdog_filed)


# ---------------------------------------------------------------------------
# Combined detector behavior — making sure detectors don't step on each other.
# ---------------------------------------------------------------------------


class TestRunAllDetectorsInteraction:
    """Verify run_all_detectors emits each pattern exactly once per fire."""

    def test_d3_does_not_clobber_d1_for_same_pr(self):
        """Same PR: 5 enqueue failures (D1) + a D3 incoherence (cache stale)."""
        history = [
            YoloActionRecord(
                project_id="p", review_id="56", action_type="enqueue",
                outcome="failure", error_msg="boom",
                tick=i + 1, timestamp=0,
            )
            for i in range(D1_RECURRENCE_THRESHOLD)
        ]
        incoherent = [{
            "project_id": "p",
            "review_id": "56",
            "kind": "merge-conflict",
            "source_branch": "epic/callback-auth",
            "reason": "recovery task trickle-iq1 is closed",
        }]
        patterns = run_all_detectors(history=history, incoherent_prs=incoherent)
        keys = {p.pattern_key for p in patterns}
        assert "d1:p:56:enqueue" in keys
        assert "d3:p:56:merge-conflict" in keys
        # Ordering: D1 must come before D3 (per run_all_detectors docstring).
        d1_idx = next(i for i, pat in enumerate(patterns) if pat.detector == "d1")
        d3_idx = next(i for i, pat in enumerate(patterns) if pat.detector == "d3")
        assert d1_idx < d3_idx

    def test_no_history_no_coverage_no_incoherent_emits_nothing(self):
        assert run_all_detectors(history=[]) == []

    def test_only_coverage_emits_d2_only(self):
        coverage = [
            CoverageRecord(tick=i, project_id="p", considered=1, total=3, actions=0,
                           missing_review_ids=["2", "3"])
            for i in range(1, 4)
        ]
        patterns = run_all_detectors(history=[], coverage_history=coverage)
        assert len(patterns) == 1
        assert patterns[0].detector == "d2"

    def test_d4_below_d1_threshold_no_patterns(self):
        """run_all_detectors: 3 'already mergeable' enqueue failures alone
        (without any direct-merge fallback failure) produce no patterns —
        D1 hasn't reached threshold (5) and D4 needs ≥1 fallback failure.
        """
        history = [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="Pull request is already mergeable",
                tick=i + 1, timestamp=0,
            )
            for i in range(D4_ALREADY_MERGEABLE_THRESHOLD)
        ]
        patterns = run_all_detectors(history=history)
        # D1 hasn't reached threshold (5), D4 has no fallback failure → no patterns.
        assert patterns == []
