"""Tests for the YOLO-loop block watchdog (oompah-zlz_2-jg4).

Covers each detector (D1–D4) and the orchestrator integration:
* Action history records every attempt with the right outcome/error.
* D1 escalates after N consecutive identical failures.
* D2 logs a starvation warning when reviews_considered < total_reviews
  for ≥3 consecutive ticks.
* D3 detects task-PR coherence breaks (closed recovery task, PR still
  failing) and resets the orphan-recovery cache.
* D4 switches strategy from auto-merge to direct merge after 3
  consecutive "PR already mergeable" failures, then escalates via D1.
* Idempotency: same pattern doesn't re-file every tick. When the PR
  resolves, the cache clears and a future recurrence can re-file.
"""

from __future__ import annotations

from collections import deque
from unittest.mock import ANY, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest
from oompah.statuses import NEEDS_HUMAN
from oompah.yolo_watchdog import (
    CoverageRecord,
    D1_RECURRENCE_THRESHOLD,
    D4_ALREADY_MERGEABLE_THRESHOLD,
    YoloActionRecord,
    count_consecutive_already_mergeable,
    detect_d1_recurrent_failures,
    detect_d2_loop_coverage,
    detect_d3_task_pr_coherence,
    detect_d4_already_mergeable,
    is_already_mergeable_error,
    run_all_detectors,
)


def _make_review(
    review_id: str,
    source_branch: str = "feat-branch",
    target_branch: str = "main",
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
        target_branch=target_branch,
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
    p.default_branch = "main"
    p.epic_strategy = "flat"
    p.require_epic_for_tasks = False
    return p


def _make_orchestrator(tmp_path, projects=None):
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    project_store.epic_branch_name.side_effect = lambda epic_id: f"epic-{epic_id}"
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


def _make_issue(
    identifier: str,
    issue_type: str = "task",
    parent_id: str | None = None,
    project_id: str = "proj-1",
    state: str = "open",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="body",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
    )


# ---------------------------------------------------------------------------
# Pure-function detector tests
# ---------------------------------------------------------------------------


class TestIsAlreadyMergeableError:
    def test_matches_already_mergeable(self):
        assert is_already_mergeable_error("Pull request is already mergeable")

    def test_matches_clean_status(self):
        assert is_already_mergeable_error(
            "Pull request is in clean status. Auto-merge can't apply."
        )

    def test_case_insensitive(self):
        assert is_already_mergeable_error("ALREADY MERGEABLE")

    def test_empty_returns_false(self):
        assert not is_already_mergeable_error("")
        assert not is_already_mergeable_error(None)  # type: ignore[arg-type]

    def test_unrelated_error(self):
        assert not is_already_mergeable_error("network error: 503")


class TestCountConsecutiveAlreadyMergeable:
    def test_no_history(self):
        assert count_consecutive_already_mergeable([], "p", "1") == 0

    def test_unrelated_pr_ignored(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="2", action_type="enqueue",
                outcome="failure", error_msg="already mergeable",
                tick=1, timestamp=0,
            ),
        ]
        assert count_consecutive_already_mergeable(history, "p", "1") == 0

    def test_other_action_type_ignored(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="merge",
                outcome="failure", error_msg="already mergeable",
                tick=1, timestamp=0,
            ),
        ]
        assert count_consecutive_already_mergeable(history, "p", "1") == 0

    def test_break_on_success(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="already mergeable",
                tick=1, timestamp=0,
            ),
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="success", error_msg="",
                tick=2, timestamp=0,
            ),
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="already mergeable",
                tick=3, timestamp=0,
            ),
        ]
        assert count_consecutive_already_mergeable(history, "p", "1") == 1

    def test_break_on_other_error(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="already mergeable",
                tick=1, timestamp=0,
            ),
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="rate limit",
                tick=2, timestamp=0,
            ),
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="already mergeable",
                tick=3, timestamp=0,
            ),
        ]
        assert count_consecutive_already_mergeable(history, "p", "1") == 1


class TestDetectD1:
    """D1 fires when the same (project, review, action) has ≥5 trailing failures."""

    def _fail_n(self, n: int, project_id="p", review_id="1", action_type="enqueue"):
        return [
            YoloActionRecord(
                project_id=project_id, review_id=review_id,
                action_type=action_type,
                outcome="failure", error_msg="boom",
                tick=i + 1, timestamp=0,
            )
            for i in range(n)
        ]

    def test_below_threshold_no_pattern(self):
        history = self._fail_n(D1_RECURRENCE_THRESHOLD - 1)
        assert detect_d1_recurrent_failures(history) == []

    def test_at_threshold_fires(self):
        history = self._fail_n(D1_RECURRENCE_THRESHOLD)
        patterns = detect_d1_recurrent_failures(history)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.detector == "d1"
        assert p.severity == "p0"
        assert p.project_id == "p"
        assert p.review_id == "1"
        assert "needs-human" in p.labels
        assert "yolo-watchdog" in p.labels
        assert "boom" in p.body

    def test_success_breaks_run(self):
        history = self._fail_n(3) + [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="success", error_msg="", tick=4, timestamp=0,
            ),
        ] + self._fail_n(2)
        # New tail run is only 2 failures — well below threshold.
        # Note: the second batch starts with tick=1 again from _fail_n,
        # so we must rebuild with ascending ticks.
        history = (
            self._fail_n(3)
            + [YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="success", error_msg="", tick=4, timestamp=0,
            )]
            + [YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="boom",
                tick=5, timestamp=0,
            ),
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="boom",
                tick=6, timestamp=0,
            )]
        )
        assert detect_d1_recurrent_failures(history) == []

    def test_per_action_isolation(self):
        # Different action types have independent runs.
        history = (
            self._fail_n(D1_RECURRENCE_THRESHOLD, action_type="enqueue")
            + self._fail_n(2, action_type="merge")
        )
        patterns = detect_d1_recurrent_failures(history)
        keys = {p.pattern_key for p in patterns}
        assert keys == {"d1:p:1:enqueue"}

    def test_per_review_isolation(self):
        history = (
            self._fail_n(D1_RECURRENCE_THRESHOLD, review_id="1")
            + self._fail_n(2, review_id="2")
        )
        patterns = detect_d1_recurrent_failures(history)
        keys = {p.pattern_key for p in patterns}
        assert keys == {"d1:p:1:enqueue"}

    def test_project_lookup_used_for_title(self):
        history = self._fail_n(D1_RECURRENCE_THRESHOLD)
        patterns = detect_d1_recurrent_failures(
            history, project_lookup={"p": "myproj"},
        )
        assert "myproj" in patterns[0].title


class TestDetectD2:
    def test_below_threshold_no_pattern(self):
        coverage = [
            CoverageRecord(tick=1, project_id="p", considered=2, total=3, actions=1, missing_review_ids=["3"]),
            CoverageRecord(tick=2, project_id="p", considered=2, total=3, actions=1, missing_review_ids=["3"]),
        ]
        assert detect_d2_loop_coverage(coverage) == []

    def test_three_starved_ticks_fires(self):
        coverage = [
            CoverageRecord(tick=1, project_id="p", considered=2, total=3, actions=1, missing_review_ids=["3"]),
            CoverageRecord(tick=2, project_id="p", considered=1, total=3, actions=0, missing_review_ids=["2", "3"]),
            CoverageRecord(tick=3, project_id="p", considered=2, total=3, actions=1, missing_review_ids=["3"]),
        ]
        patterns = detect_d2_loop_coverage(coverage)
        assert len(patterns) == 1
        assert patterns[0].detector == "d2"
        assert patterns[0].severity == "warning"
        assert "2/3" in patterns[0].title or "considered=2" in patterns[0].body

    def test_full_coverage_breaks_run(self):
        coverage = [
            CoverageRecord(tick=1, project_id="p", considered=2, total=3, actions=1, missing_review_ids=["3"]),
            CoverageRecord(tick=2, project_id="p", considered=3, total=3, actions=1, missing_review_ids=[]),
            CoverageRecord(tick=3, project_id="p", considered=2, total=3, actions=1, missing_review_ids=["3"]),
        ]
        # only the most recent run is 1 tick — below threshold.
        assert detect_d2_loop_coverage(coverage) == []

    def test_per_project_isolation(self):
        coverage = [
            CoverageRecord(tick=1, project_id="a", considered=2, total=3, actions=0, missing_review_ids=["3"]),
            CoverageRecord(tick=2, project_id="a", considered=2, total=3, actions=0, missing_review_ids=["3"]),
            CoverageRecord(tick=3, project_id="a", considered=2, total=3, actions=0, missing_review_ids=["3"]),
            CoverageRecord(tick=1, project_id="b", considered=3, total=3, actions=1, missing_review_ids=[]),
            CoverageRecord(tick=2, project_id="b", considered=3, total=3, actions=1, missing_review_ids=[]),
            CoverageRecord(tick=3, project_id="b", considered=3, total=3, actions=1, missing_review_ids=[]),
        ]
        patterns = detect_d2_loop_coverage(coverage)
        assert len(patterns) == 1
        assert patterns[0].project_id == "a"


class TestDetectD3:
    def test_no_incoherent_no_patterns(self):
        assert detect_d3_task_pr_coherence(incoherent_prs=[]) == []

    def test_incoherent_emits_pattern(self):
        incoherent = [{
            "project_id": "p",
            "review_id": "5",
            "kind": "merge-conflict",
            "source_branch": "feat",
            "reason": "recovery task closed",
        }]
        patterns = detect_d3_task_pr_coherence(incoherent_prs=incoherent)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.detector == "d3"
        assert p.severity == "p0"
        assert p.project_id == "p"
        assert p.review_id == "5"
        assert "merge-conflict" in p.body
        assert "feat" in p.body
        assert "needs-human" in p.labels


class TestDetectD4:
    def _enqueue_already_mergeable(self, count: int, start_tick: int = 1, project="p", review="1"):
        return [
            YoloActionRecord(
                project_id=project, review_id=review, action_type="enqueue",
                outcome="failure", error_msg="Pull request is already mergeable",
                tick=start_tick + i, timestamp=0,
            )
            for i in range(count)
        ]

    def _merge_fallback_failure(self, count: int, start_tick: int = 100, project="p", review="1"):
        return [
            YoloActionRecord(
                project_id=project, review_id=review,
                action_type="merge_after_already_mergeable",
                outcome="failure", error_msg="Pull request is already mergeable",
                tick=start_tick + i, timestamp=0,
            )
            for i in range(count)
        ]

    def test_no_history_no_patterns(self):
        assert detect_d4_already_mergeable([]) == []

    def test_threshold_alone_no_pattern(self):
        # ≥3 enqueue 'already mergeable' failures alone is NOT enough — D4 only
        # fires once the direct-merge fallback has also failed.
        history = self._enqueue_already_mergeable(D4_ALREADY_MERGEABLE_THRESHOLD)
        assert detect_d4_already_mergeable(history) == []

    def test_threshold_plus_fallback_failure_fires(self):
        history = (
            self._enqueue_already_mergeable(D4_ALREADY_MERGEABLE_THRESHOLD)
            + self._merge_fallback_failure(1)
        )
        patterns = detect_d4_already_mergeable(history)
        assert len(patterns) == 1
        assert patterns[0].detector == "d4"
        assert patterns[0].severity == "p0"

    def test_does_not_fire_for_unrelated_error(self):
        history = [
            YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="rate limit",
                tick=i + 1, timestamp=0,
            )
            for i in range(D4_ALREADY_MERGEABLE_THRESHOLD)
        ]
        history += self._merge_fallback_failure(1)
        assert detect_d4_already_mergeable(history) == []


class TestRunAllDetectors:
    def test_returns_d1_and_d4_simultaneously(self):
        # Same PR has 5 enqueue 'already mergeable' failures plus a fallback failure.
        history = []
        for tick in range(1, 6):
            history.append(YoloActionRecord(
                project_id="p", review_id="1", action_type="enqueue",
                outcome="failure", error_msg="Pull request is already mergeable",
                tick=tick, timestamp=0,
            ))
        history.append(YoloActionRecord(
            project_id="p", review_id="1",
            action_type="merge_after_already_mergeable",
            outcome="failure", error_msg="Pull request is already mergeable",
            tick=6, timestamp=0,
        ))
        patterns = run_all_detectors(history=history)
        keys = {p.pattern_key for p in patterns}
        assert "d1:p:1:enqueue" in keys
        assert "d4:p:1" in keys


# ---------------------------------------------------------------------------
# Orchestrator integration tests
# ---------------------------------------------------------------------------


class TestOrchestratorActionHistoryRecording:
    """Verify _record_yolo_action is wired into _yolo_review_actions_sync."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_successful_merge_recorded(self, mock_slug, mock_detect, tmp_path):
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("1", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        assert len(orch._yolo_action_history) == 1
        record = orch._yolo_action_history[0]
        assert record.project_id == project.id
        assert record.review_id == "1"
        assert record.action_type == "merge"
        assert record.outcome == "success"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_failed_merge_recorded_with_error(self, mock_slug, mock_detect, tmp_path):
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (False, "merge failed: connection reset")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("1", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        record = orch._yolo_action_history[0]
        assert record.outcome == "failure"
        assert "connection reset" in record.error_msg

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_conflict_dispatch_recorded(self, mock_slug, mock_detect, tmp_path):
        project = _make_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("1", has_conflicts=True)]}

        orch._yolo_review_actions_sync()

        records = list(orch._yolo_action_history)
        assert any(r.action_type == "notify_conflict" for r in records)


class TestYoloEpicStrategyGate:
    """YOLO must honor per-project epic merge strategy before acting."""

    def _install_tracker(self, orch, project, child=None, parent=None):
        tracker = MagicMock()

        def fetch_detail(identifier):
            if child is not None and identifier == child.identifier:
                return child
            if parent is not None and identifier == parent.identifier:
                return parent
            return None

        tracker.fetch_issue_detail.side_effect = fetch_detail
        orch._project_trackers[project.id] = tracker
        return tracker

    @pytest.mark.parametrize(
        "review_kwargs",
        [
            {"ci_status": "passed"},
            {"has_conflicts": True},
            {"ci_status": "failed"},
        ],
    )
    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_shared_child_pr_is_closed_before_any_yolo_action(
        self, mock_slug, mock_detect, tmp_path, review_kwargs,
    ):
        project = _make_project()
        project.epic_strategy = "shared"
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        provider.enable_auto_merge.return_value = (True, "enqueued")
        provider.close_review.return_value = (True, "closed")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._yolo_retry_ci = MagicMock()
        tracker = self._install_tracker(
            orch,
            project,
            child=_make_issue("TASK-472.4", parent_id="TASK-472"),
            parent=_make_issue("TASK-472", issue_type="epic"),
        )
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "249",
                    source_branch="TASK-472.4",
                    target_branch="main",
                    **review_kwargs,
                )
            ],
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()
        provider.close_review.assert_called_once_with(
            "org/repo",
            "249",
            comment=ANY,
        )
        orch._yolo_notify_conflict.assert_not_called()
        orch._yolo_retry_ci.assert_not_called()
        tracker.add_comment.assert_called_once()
        comment_args = tracker.add_comment.call_args.args
        assert comment_args[0] == "TASK-472.4"
        assert "Closed stale child PR #249" in comment_args[1]
        records = list(orch._yolo_action_history)
        assert len(records) == 1
        assert records[0].action_type == "close_invalid_review"
        assert records[0].outcome == "success"
        assert "shared epic workflow" in records[0].error_msg

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_require_epic_parent_closes_standalone_task_pr(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        project.epic_strategy = "shared"
        project.require_epic_for_tasks = True
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        provider.enable_auto_merge.return_value = (True, "enqueued")
        provider.close_review.return_value = (True, "closed")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = self._install_tracker(
            orch,
            project,
            child=_make_issue("TASK-733", parent_id=None, state="In Review"),
        )
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "224",
                    source_branch="TASK-733",
                    target_branch="main",
                    ci_status="passed",
                )
            ],
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()
        provider.close_review.assert_called_once_with(
            "org/repo",
            "224",
            comment=ANY,
        )
        tracker.update_issue.assert_called_once_with(
            "TASK-733",
            status=NEEDS_HUMAN,
        )
        tracker.add_comment.assert_called_once()
        comment_args = tracker.add_comment.call_args.args
        assert comment_args[0] == "TASK-733"
        assert "Closed stale standalone PR #224" in comment_args[1]
        records = list(orch._yolo_action_history)
        assert len(records) == 1
        assert records[0].action_type == "close_invalid_review"
        assert records[0].outcome == "success"
        assert "requires epic-owned tasks" in records[0].error_msg
        assert "TASK-733" in records[0].error_msg

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_shared_child_pr_targeting_epic_branch_is_closed(
        self, mock_slug, mock_detect, tmp_path,
    ):
        """Per-child task PRs targeting the epic branch are also closed.

        In shared mode children commit directly to the epic branch — there are
        no valid per-child task PRs, even when they happen to target the epic
        branch instead of main.  Only a PR whose source_branch IS the epic
        branch itself (an epic rollup PR) is allowed through.
        """
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        provider.close_review.return_value = (True, "closed")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        self._install_tracker(
            orch,
            project,
            child=_make_issue("TASK-472.4", parent_id="TASK-472"),
            parent=_make_issue("TASK-472", issue_type="epic"),
        )
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "249",
                    source_branch="TASK-472.4",
                    target_branch="epic-TASK-472",
                    ci_status="passed",
                )
            ],
        }

        orch._yolo_review_actions_sync()

        # The per-child PR is closed, not merged — work must land via the
        # epic rollup PR (epic-TASK-472 → main), not a per-child PR.
        provider.merge_review.assert_not_called()
        provider.close_review.assert_called_once()
        records = list(orch._yolo_action_history)
        assert len(records) == 1
        assert records[0].action_type == "close_invalid_review"
        assert "shared epic workflow" in records[0].error_msg

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_shared_nested_epic_branch_can_merge(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        project.epic_strategy = "shared"
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        self._install_tracker(
            orch,
            project,
            child=_make_issue("TASK-472.9", issue_type="epic", parent_id="TASK-472"),
            parent=_make_issue("TASK-472", issue_type="epic"),
        )
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "260",
                    source_branch="epic-TASK-472.9",
                    target_branch="epic-TASK-472",
                    ci_status="passed",
                )
            ],
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with("org/repo", "260")
        records = list(orch._yolo_action_history)
        assert len(records) == 1
        assert records[0].action_type == "merge"
        assert records[0].outcome == "success"


class TestOrchestratorD1Watchdog:
    """D1 — recurring identical failure → P0 task."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_five_failed_merges_files_p0(self, mock_slug, mock_detect, tmp_path):
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (False, "GitHub server error")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        new_issue = MagicMock(identifier="watchdog-001")
        mock_tracker.create_issue.return_value = new_issue
        mock_tracker.fetch_issue_detail.return_value = None

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        for _ in range(D1_RECURRENCE_THRESHOLD):
            orch._yolo_review_actions_sync()

        # Watchdog should have filed a P0 task.
        create_calls = mock_tracker.create_issue.call_args_list
        watchdog_calls = [
            c for c in create_calls
            if c.kwargs.get("priority") == 0
            and "needs-human" in (c.kwargs.get("labels") or [])
        ]
        assert len(watchdog_calls) == 1, f"Expected 1 watchdog task, got: {create_calls}"
        kw = watchdog_calls[0].kwargs
        assert "42" in kw["title"]
        assert "merge" in kw["title"]

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_idempotent_no_refile_on_subsequent_failures(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (False, "boom")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        new_issue = MagicMock(identifier="watchdog-001")
        mock_tracker.create_issue.return_value = new_issue

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        for _ in range(D1_RECURRENCE_THRESHOLD + 5):
            orch._yolo_review_actions_sync()

        # Only one watchdog task — idempotent.
        create_calls = mock_tracker.create_issue.call_args_list
        watchdog_calls = [
            c for c in create_calls
            if c.kwargs.get("priority") == 0
            and "needs-human" in (c.kwargs.get("labels") or [])
        ]
        assert len(watchdog_calls) == 1

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pr_resolves_clears_cache_for_recurrence(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        provider = MagicMock()
        # Five fails, then a success, then five more fails — should fire
        # twice because the success clears the cache.
        provider.merge_review.return_value = (False, "boom")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        mock_tracker.create_issue.side_effect = [
            MagicMock(identifier="watchdog-001"),
            MagicMock(identifier="watchdog-002"),
        ]

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        for _ in range(D1_RECURRENCE_THRESHOLD):
            orch._yolo_review_actions_sync()

        # Now succeed — clears cache.
        provider.merge_review.return_value = (True, "merged")
        orch._yolo_review_actions_sync()

        # Now fail 5 more times — should re-fire.
        provider.merge_review.return_value = (False, "boom")
        for _ in range(D1_RECURRENCE_THRESHOLD):
            orch._yolo_review_actions_sync()

        watchdog_calls = [
            c for c in mock_tracker.create_issue.call_args_list
            if c.kwargs.get("priority") == 0
            and "needs-human" in (c.kwargs.get("labels") or [])
        ]
        assert len(watchdog_calls) == 2


class TestOrchestratorD2Watchdog:
    """D2 — coverage starvation logged as WARNING."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_starvation_logs_warning(self, mock_slug, mock_detect, tmp_path, caplog):
        """A project with 3 PRs where only 1 gets considered for 3 ticks → WARN."""
        import logging
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        # 3 PRs all CI passed: only the first will be acted on per tick
        # (serialization break), so considered=1, total=3 every tick.
        # That triggers D2 after 3 ticks.
        # Note: serialization 'break' exits after one merge action so
        # subsequent reviews are NOT iterated.
        orch._reviews_cache = {
            project.id: [
                _make_review("1", ci_status="passed"),
                _make_review("2", ci_status="passed"),
                _make_review("3", ci_status="passed"),
            ],
        }

        with caplog.at_level(logging.WARNING):
            for _ in range(3):
                orch._yolo_review_actions_sync()

        warning_messages = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING and "YOLO watchdog D2" in r.message
        ]
        assert any("starvation" in m.lower() for m in warning_messages), \
            f"Expected D2 starvation warning, got: {warning_messages}"


class TestOrchestratorD3Watchdog:
    """D3 — task-PR coherence."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_closed_recovery_task_resets_cache_and_files_watchdog(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        # A previously-filed orphan-recovery task that is now closed.
        closed_task = Issue(
            id="rec-001", identifier="rec-001",
            title="merge conflict on PR #7",
            description="recovery", state="closed", labels=["merge-conflict"],
        )
        # Also, the task that fetch_issue_detail returns for the BRANCH
        # name (in _yolo_notify_conflict) — also closed.
        task_for_branch = Issue(
            id="feat-7", identifier="feat-7",
            title="feature 7", description="x",
            state="closed", labels=[],
        )

        mock_tracker = MagicMock()
        def fetch_detail(arg):
            if arg == "rec-001":
                return closed_task
            if arg == "feat-7":
                return task_for_branch
            return None
        mock_tracker.fetch_issue_detail.side_effect = fetch_detail
        mock_tracker.create_issue.return_value = MagicMock(identifier="watchdog-001")

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        # Pre-seed orphan-recovery cache as if we'd filed it before.
        orch._yolo_orphan_recovery_tasks[(project.id, "7", "merge-conflict")] = "rec-001"
        orch._reviews_cache = {
            project.id: [_make_review("7", source_branch="feat-7", has_conflicts=True)],
        }

        orch._yolo_review_actions_sync()

        # Cache should have been reset for the (project, 7, merge-conflict) key.
        assert (project.id, "7", "merge-conflict") not in orch._yolo_orphan_recovery_tasks
        # And a watchdog task should have been filed.
        watchdog_calls = [
            c for c in mock_tracker.create_issue.call_args_list
            if c.kwargs.get("priority") == 0
            and "needs-human" in (c.kwargs.get("labels") or [])
        ]
        assert len(watchdog_calls) == 1
        assert "coherence" in watchdog_calls[0].kwargs["title"].lower()


class TestOrchestratorD4Watchdog:
    """D4 — already-mergeable strategy switch."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_three_already_mergeable_switches_to_direct_merge(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        project.merge_queue_enabled = True
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False, "Pull request is already mergeable",
        )
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("9", ci_status="passed")]}

        # Run 3 ticks of "already mergeable" failure — switch should engage.
        for _ in range(D4_ALREADY_MERGEABLE_THRESHOLD):
            orch._yolo_review_actions_sync()

        assert (project.id, "9") in orch._yolo_already_mergeable_switched

        # Next tick should call merge_review (direct merge), not enable_auto_merge.
        provider.enable_auto_merge.reset_mock()
        provider.merge_review.reset_mock()
        # Make merge_review succeed this time.
        provider.merge_review.return_value = (True, "merged")
        orch._yolo_review_actions_sync()

        assert provider.enable_auto_merge.call_count == 0
        assert provider.merge_review.call_count == 1
        # Successful direct merge clears the switch.
        assert (project.id, "9") not in orch._yolo_already_mergeable_switched

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_fallback_also_fails_escalates_via_d1(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        project.merge_queue_enabled = True
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False, "Pull request is already mergeable",
        )
        provider.merge_review.return_value = (
            False, "Pull request is already mergeable",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        mock_tracker.create_issue.return_value = MagicMock(identifier="watchdog-001")

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._reviews_cache = {project.id: [_make_review("9", ci_status="passed")]}

        # Run enough ticks to hit D1 (5 enqueue failures) AND have direct
        # merge fallback also fail.
        for _ in range(D1_RECURRENCE_THRESHOLD + 1):
            orch._yolo_review_actions_sync()

        watchdog_calls = [
            c for c in mock_tracker.create_issue.call_args_list
            if c.kwargs.get("priority") == 0
            and "needs-human" in (c.kwargs.get("labels") or [])
        ]
        assert len(watchdog_calls) >= 1
        # At least one should be D4 OR D1 — either is acceptable
        # provided the operator gets escalation.
        all_titles = " ".join(c.kwargs["title"] for c in watchdog_calls)
        assert "9" in all_titles  # PR id present


class TestOrchestratorWatchdogStatePruning:
    """Watchdog cache must clear for PRs that leave the cache."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pr_removed_from_cache_clears_filed_task_state(
        self, mock_slug, mock_detect, tmp_path,
    ):
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (False, "boom")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        mock_tracker.create_issue.return_value = MagicMock(identifier="watchdog-001")

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        for _ in range(D1_RECURRENCE_THRESHOLD):
            orch._yolo_review_actions_sync()

        # The watchdog cache should have a D1 entry for project/42.
        assert any(
            k.startswith(f"d1:{project.id}:42:")
            for k in orch._yolo_watchdog_filed
        )

        # Now PR 42 disappears (merged/closed).
        orch._reviews_cache = {project.id: []}
        orch._yolo_review_actions_sync()

        assert not any(
            k.startswith(f"d1:{project.id}:42:")
            for k in orch._yolo_watchdog_filed
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_d4_switch_cleared_when_pr_leaves_cache(
        self, mock_slug, mock_detect, tmp_path,
    ):
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

        for _ in range(D4_ALREADY_MERGEABLE_THRESHOLD):
            orch._yolo_review_actions_sync()
        assert (project.id, "9") in orch._yolo_already_mergeable_switched

        # PR closes / disappears.
        orch._reviews_cache = {project.id: []}
        orch._yolo_review_actions_sync()

        assert (project.id, "9") not in orch._yolo_already_mergeable_switched


class TestOrchestratorCoverageLogging:
    """The 'YOLO iteration: considered N/M' line is emitted every tick."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_iteration_line_emitted(self, mock_slug, mock_detect, tmp_path, caplog):
        import logging
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", ci_status="passed"),
                _make_review("2", ci_status="passed"),
            ],
        }

        with caplog.at_level(logging.INFO):
            orch._yolo_review_actions_sync()

        iteration_lines = [
            r.message for r in caplog.records
            if "YOLO iteration:" in r.message
        ]
        assert len(iteration_lines) == 1
        assert "considered=1/2" in iteration_lines[0]
        assert "actions=1" in iteration_lines[0]


class TestWatchdogFilingLogLevel:
    """Regression for oompah-zlz_2-8vc.

    The watchdog's "filed P0 task" log line must NOT be at ERROR level,
    or else error_watcher's _TaskLoggingHandler will auto-file a duplicate
    meta-task in the oompah project every time the watchdog escalates a
    legitimate stuck PR. The notification belongs in the target project's
    task (already filed by _file_watchdog_task); the oompah orchestrator
    log line should stay at WARNING.
    """

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_filed_p0_task_logged_at_warning_not_error(
        self, mock_slug, mock_detect, tmp_path, caplog,
    ):
        import logging
        project = _make_project()
        provider = MagicMock()
        provider.merge_review.return_value = (False, "GitHub server error")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        mock_tracker = MagicMock()
        new_issue = MagicMock(identifier="watchdog-001")
        mock_tracker.create_issue.return_value = new_issue
        mock_tracker.fetch_issue_detail.return_value = None

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._project_trackers[project.id] = mock_tracker
        orch._reviews_cache = {
            project.id: [_make_review("42", ci_status="passed")],
        }

        # Drive D1 to threshold so the watchdog files a P0 task.
        with caplog.at_level(logging.DEBUG, logger="oompah.orchestrator"):
            for _ in range(D1_RECURRENCE_THRESHOLD):
                orch._yolo_review_actions_sync()

        # The watchdog should have filed exactly one P0 task.
        watchdog_calls = [
            c for c in mock_tracker.create_issue.call_args_list
            if c.kwargs.get("priority") == 0
            and "needs-human" in (c.kwargs.get("labels") or [])
        ]
        assert len(watchdog_calls) == 1, (
            f"Expected 1 watchdog task, got: {mock_tracker.create_issue.call_args_list}"
        )

        # The "filed P0 task" log line must be at WARNING, NOT ERROR.
        filing_records = [
            r for r in caplog.records
            if "YOLO watchdog: filed P0 task" in r.message
        ]
        assert len(filing_records) == 1, (
            f"Expected 1 filing log line, got {len(filing_records)}: "
            f"{[r.message for r in filing_records]}"
        )
        rec = filing_records[0]
        assert rec.levelno == logging.WARNING, (
            f"Expected 'YOLO watchdog: filed P0 task' to be logged at "
            f"WARNING (not ERROR — error_watcher would auto-file a "
            f"duplicate meta-task in oompah), got level={rec.levelname}"
        )
        # And explicitly: no records at ERROR or above for this filing.
        error_records = [
            r for r in caplog.records
            if r.levelno >= logging.ERROR
            and "YOLO watchdog: filed P0 task" in r.message
        ]
        assert error_records == [], (
            f"Watchdog filing log must not be ERROR+: {[r.message for r in error_records]}"
        )
