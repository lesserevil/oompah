"""Tests for the stalled-task remediation watchdog (OOMPAH-398).

Covers:
- Module constants (ENV_VAR, DEFAULT_INTERVAL_SECONDS, STALLED_STATES).
- Config default and env-override parsing.
- is_stalled_status() helper for canonical and custom statuses.
- classify_stalled_task() for every classification outcome.
- Idempotency: tasks already actioned and unchanged are skipped.
- build_watchdog_comment() sentinel marker.
- run_watchdog_audit() with fake trackers: safe reopen, safe archive,
  and refusal when evidence is ambiguous or CI is still failing.
- Orchestrator integration: watchdog is coalesced, respects interval,
  and does not block normal dispatch.
"""

from __future__ import annotations

import asyncio
import os
import threading
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.statuses import (
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
)
from oompah.stalled_task_watchdog import (
    DEFAULT_INTERVAL_SECONDS,
    ENV_VAR,
    STALLED_STATES,
    WATCHDOG_COMMENT_MARKER,
    WatchdogAuditResult,
    StalledTaskDecision,
    build_watchdog_comment,
    classify_stalled_task,
    is_stalled_status,
    run_watchdog_audit,
)


# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------


class TestConstants:
    def test_env_var_name(self):
        assert ENV_VAR == "OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS"

    def test_default_interval_is_300(self):
        assert DEFAULT_INTERVAL_SECONDS == 300

    def test_stalled_states_contains_expected(self):
        assert NEEDS_HUMAN in STALLED_STATES
        assert NEEDS_CI_FIX in STALLED_STATES
        assert NEEDS_REBASE in STALLED_STATES
        assert NEEDS_ANSWER in STALLED_STATES


class TestConfigDefault:
    def test_service_config_default_is_300(self):
        cfg = ServiceConfig()
        assert cfg.stalled_task_watchdog_interval_seconds == 300

    def test_env_override_parsed(self):
        with patch.dict(os.environ, {ENV_VAR: "600"}):
            cfg = ServiceConfig.from_workflow(
                _make_workflow(),
            )
        assert cfg.stalled_task_watchdog_interval_seconds == 600

    def test_env_override_minimum_60(self):
        """Values below 60 are clamped to 60 (prevent runaway polling)."""
        cfg = ServiceConfig(stalled_task_watchdog_interval_seconds=0)
        assert cfg.stalled_task_watchdog_interval_seconds == 60

    def test_env_override_minimum_60_via_from_workflow(self):
        with patch.dict(os.environ, {ENV_VAR: "10"}):
            cfg = ServiceConfig.from_workflow(_make_workflow())
        assert cfg.stalled_task_watchdog_interval_seconds == 60


# ---------------------------------------------------------------------------
# is_stalled_status()
# ---------------------------------------------------------------------------


class TestIsStalledStatus:
    @pytest.mark.parametrize("status", [
        NEEDS_HUMAN, NEEDS_CI_FIX, NEEDS_REBASE, NEEDS_ANSWER,
        "Needs Human", "needs ci fix", "Needs Rebase",
    ])
    def test_canonical_stalled_statuses(self, status):
        assert is_stalled_status(status)

    @pytest.mark.parametrize("status", ["blocked", "Blocked", "stalled", "Stalled"])
    def test_custom_stalled_keywords(self, status):
        assert is_stalled_status(status)

    @pytest.mark.parametrize("status", ["Open", "In Progress", "Done", "Merged", None])
    def test_non_stalled_statuses(self, status):
        assert not is_stalled_status(status)


# ---------------------------------------------------------------------------
# classify_stalled_task()
# ---------------------------------------------------------------------------


class TestClassifyNeedsAnswer:
    def test_needs_answer_always_human_blocked(self):
        decision = classify_stalled_task("T-1", NEEDS_ANSWER, [])
        assert decision.classification == "human_blocked"
        assert decision.action == "none"

    def test_needs_answer_with_any_comments(self):
        comments = [_comment("oompah", "Some question?")]
        decision = classify_stalled_task("T-1", NEEDS_ANSWER, comments)
        assert decision.classification == "human_blocked"


class TestClassifyNeedsHuman:
    def test_no_comments_insufficient_evidence(self):
        decision = classify_stalled_task("T-2", NEEDS_HUMAN, [])
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_completion_comment_without_question_is_actionable(self):
        """An agent completion comment with no question → accidental stall → reopen."""
        comments = [
            _comment("oompah", "Agent completed successfully. Fixed the bug and pushed."),
        ]
        decision = classify_stalled_task("T-3", NEEDS_HUMAN, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_agent_done_comment_without_question_is_actionable(self):
        comments = [_comment("oompah", "Focus complete: implemented the feature and committed.")]
        decision = classify_stalled_task("T-4", NEEDS_HUMAN, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_comment_with_question_is_human_blocked(self):
        comments = [_comment("oompah", "I ran into an issue. Can you clarify the requirements?")]
        decision = classify_stalled_task("T-5", NEEDS_HUMAN, comments)
        assert decision.classification == "human_blocked"
        assert decision.action == "none"

    def test_focus_handoff_with_question_is_human_blocked(self):
        comments = [_comment("oompah", "Focus handoff: needs human approval to proceed.")]
        decision = classify_stalled_task("T-6", NEEDS_HUMAN, comments)
        assert decision.classification == "human_blocked"

    def test_blocking_dependency_is_human_blocked(self):
        comments = [_comment("oompah", "Blocked on human review of the security audit.")]
        decision = classify_stalled_task("T-7", NEEDS_HUMAN, comments)
        assert decision.classification == "human_blocked"

    def test_question_mark_at_end_of_last_comment_is_human_blocked(self):
        comments = [_comment("human_user", "Should we proceed with approach A or B?")]
        decision = classify_stalled_task("T-8", NEEDS_HUMAN, comments)
        assert decision.classification == "human_blocked"

    def test_task_id_and_project_id_in_decision(self):
        decision = classify_stalled_task(
            "OOMPAH-42", NEEDS_HUMAN, [], project_id="proj-abc", run_id=7
        )
        assert decision.task_id == "OOMPAH-42"
        assert decision.project_id == "proj-abc"
        assert decision.watchdog_run_id == 7

    def test_completion_followed_by_question_stays_human_blocked(self):
        """If an earlier completion comment is followed by a question, block."""
        comments = [
            _comment("oompah", "Implemented and committed."),
            _comment("human", "Wait — should we use the new API?"),
        ]
        decision = classify_stalled_task("T-9", NEEDS_HUMAN, comments)
        assert decision.classification == "human_blocked"

    def test_handoff_wording_alone_is_not_human_blocker(self):
        """A required focus handoff is not proof that a human decision remains."""
        comments = [_comment("oompah", "Focus handoff: needs human review of the branch.")]
        decision = classify_stalled_task("T-9a", NEEDS_HUMAN, comments)
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_merged_review_overrides_stale_handoff(self):
        comments = [
            _comment("oompah", "Focus handoff: needs human review after the audit."),
        ]
        decision = classify_stalled_task(
            "T-9b",
            NEEDS_HUMAN,
            comments,
            evidence={"review": {"number": "692", "state": "merged"}},
        )
        assert decision.classification == "actionable"
        assert decision.action == "reopen"
        assert "692" in decision.evidence

    def test_missing_audit_branch_with_canonical_ref_is_technical(self):
        decision = classify_stalled_task(
            "T-9c",
            NEEDS_HUMAN,
            [_comment("oompah", "Focus handoff: needs human review.")],
            evidence={"audit_branch": None, "canonical_ref": "main"},
        )
        assert decision.classification == "insufficient_evidence"
        assert "audit branch is missing" in decision.evidence

    def test_provider_failure_is_not_human_blocked(self):
        decision = classify_stalled_task(
            "T-9d",
            NEEDS_HUMAN,
            [_comment("oompah", "Focus handoff: needs human review.")],
            evidence={"provider": {"available": False, "error": "timeout"}},
        )
        assert decision.classification == "insufficient_evidence"
        assert "provider evidence failed" in decision.evidence

    def test_ambiguous_scm_state_fails_closed(self):
        decision = classify_stalled_task(
            "T-9e",
            NEEDS_HUMAN,
            [_comment("oompah", "Focus handoff: needs human review.")],
            evidence={"branch": {"scm_state": "ambiguous"}},
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_newer_completion_supersedes_older_question(self):
        comments = [
            _comment("oompah", "Should we use approach A?"),
            _comment("oompah", "Completed and pushed the implementation."),
        ]
        comments[0]["created_at"] = "2026-08-03T00:00:00Z"
        comments[1]["created_at"] = "2026-08-04T00:00:00Z"
        decision = classify_stalled_task("T-9f", NEEDS_HUMAN, comments)
        assert decision.classification == "actionable"

    def test_newer_question_remains_current_after_older_completion(self):
        comments = [
            _comment("oompah", "Completed and pushed the implementation."),
            _comment("human", "Should we use approach A?"),
        ]
        comments[0]["created_at"] = "2026-08-03T00:00:00Z"
        comments[1]["created_at"] = "2026-08-04T00:00:00Z"
        decision = classify_stalled_task("T-9g", NEEDS_HUMAN, comments)
        assert decision.classification == "human_blocked"


class TestClassifyNeedsCIFix:
    def test_no_evidence_insufficient(self):
        decision = classify_stalled_task("T-10", NEEDS_CI_FIX, [])
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_ci_passing_comment_is_actionable(self):
        comments = [_comment("oompah", "CI checks are now passing on this branch.")]
        decision = classify_stalled_task("T-11", NEEDS_CI_FIX, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_pr_merged_comment_is_actionable(self):
        comments = [_comment("github", "PR #42 has been merged into main.")]
        decision = classify_stalled_task("T-12", NEEDS_CI_FIX, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_tests_passing_comment_is_actionable(self):
        comments = [_comment("ci-bot", "All tests passed on push.")]
        decision = classify_stalled_task("T-13", NEEDS_CI_FIX, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_unrelated_comment_is_insufficient(self):
        comments = [_comment("human", "I updated the dependencies.")]
        decision = classify_stalled_task("T-14", NEEDS_CI_FIX, comments)
        assert decision.classification == "insufficient_evidence"

    def test_watchdog_comment_is_ignored_for_ci(self):
        """A prior watchdog comment should not trigger reopen on CI Fix."""
        comments = [
            _comment("oompah", f"{WATCHDOG_COMMENT_MARKER} previous action"),
        ]
        decision = classify_stalled_task("T-15", NEEDS_CI_FIX, comments)
        assert decision.classification == "insufficient_evidence"


class TestClassifyNeedsRebase:
    def test_no_evidence_insufficient(self):
        decision = classify_stalled_task("T-20", NEEDS_REBASE, [])
        assert decision.classification == "insufficient_evidence"

    def test_conflict_resolved_comment_is_actionable(self):
        comments = [_comment("oompah", "Rebase resolved, no more conflicts.")]
        decision = classify_stalled_task("T-21", NEEDS_REBASE, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_no_conflict_comment_is_actionable(self):
        comments = [_comment("oompah", "Branch is now clean — no conflict detected.")]
        decision = classify_stalled_task("T-22", NEEDS_REBASE, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_merged_pr_is_actionable(self):
        comments = [_comment("github", "PR closed and merged.")]
        decision = classify_stalled_task("T-23", NEEDS_REBASE, comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_irrelevant_comment_stays_insufficient(self):
        comments = [_comment("human", "I'll look at the conflict next week.")]
        decision = classify_stalled_task("T-24", NEEDS_REBASE, comments)
        assert decision.classification == "insufficient_evidence"


class TestClassifyCustomBlockedStalled:
    def test_blocked_status_no_evidence_is_human_blocked(self):
        decision = classify_stalled_task("T-30", "Blocked", [])
        assert decision.classification == "human_blocked"
        assert decision.action == "none"

    def test_stalled_status_no_evidence_is_human_blocked(self):
        decision = classify_stalled_task("T-31", "Stalled", [])
        assert decision.classification == "human_blocked"

    def test_resolution_signal_in_blocked_is_actionable(self):
        comments = [_comment("oompah", "PR #99 merged successfully.")]
        decision = classify_stalled_task("T-32", "Blocked", comments)
        assert decision.classification == "actionable"
        assert decision.action == "reopen"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_already_actioned_no_new_activity(self):
        """If the last comment is a watchdog sentinel and nothing has changed, skip."""
        comments = [
            _comment("oompah", f"{WATCHDOG_COMMENT_MARKER} prior action"),
        ]
        decision = classify_stalled_task("T-40", NEEDS_HUMAN, comments)
        assert decision.already_actioned is True
        assert decision.action == "none"

    def test_new_activity_after_watchdog_comment_triggers_reclassification(self):
        """New non-watchdog comment after the sentinel → re-classify."""
        comments = [
            _comment("oompah", f"{WATCHDOG_COMMENT_MARKER} prior action"),
            _comment("oompah", "Agent completed the task."),
        ]
        decision = classify_stalled_task("T-41", NEEDS_HUMAN, comments)
        assert decision.already_actioned is False
        # New completion comment → actionable
        assert decision.classification == "actionable"

    def test_watchdog_comment_not_last_triggers_reclassification(self):
        """If watchdog is not last, there was activity after it."""
        comments = [
            _comment("oompah", "Implemented and finished the feature."),
            _comment("oompah", f"{WATCHDOG_COMMENT_MARKER} prior action"),
            _comment("human", "Thanks for the implementation."),
        ]
        decision = classify_stalled_task("T-42", NEEDS_HUMAN, comments)
        assert decision.already_actioned is False


# ---------------------------------------------------------------------------
# build_watchdog_comment()
# ---------------------------------------------------------------------------


class TestBuildWatchdogComment:
    def test_contains_sentinel_marker(self):
        decision = StalledTaskDecision(
            task_id="T-1",
            project_id="proj",
            stalled_status=NEEDS_HUMAN,
            classification="actionable",
            action="reopen",
            evidence="Test evidence.",
            watchdog_run_id=3,
        )
        body = build_watchdog_comment(decision)
        assert WATCHDOG_COMMENT_MARKER in body

    def test_contains_run_id(self):
        decision = StalledTaskDecision(
            task_id="T-1",
            project_id="proj",
            stalled_status=NEEDS_HUMAN,
            classification="actionable",
            action="reopen",
            evidence="Evidence.",
            watchdog_run_id=7,
        )
        body = build_watchdog_comment(decision)
        assert "run #7" in body

    def test_contains_classification_and_action(self):
        decision = StalledTaskDecision(
            task_id="T-1",
            project_id=None,
            stalled_status=NEEDS_CI_FIX,
            classification="insufficient_evidence",
            action="none",
            evidence="Nothing to act on.",
            watchdog_run_id=1,
        )
        body = build_watchdog_comment(decision)
        assert "insufficient_evidence" in body
        assert "none" in body


# ---------------------------------------------------------------------------
# run_watchdog_audit() — fake tracker integration
# ---------------------------------------------------------------------------


def _make_issue(identifier: str, state: str) -> Issue:
    issue = MagicMock(spec=Issue)
    issue.identifier = identifier
    issue.state = state
    return issue


def _make_tracker(issues: list, comments_by_id: dict | None = None) -> MagicMock:
    tracker = MagicMock()
    tracker.fetch_issues_by_states.return_value = issues
    comments_by_id = comments_by_id or {}
    tracker.fetch_comments.side_effect = lambda iid: comments_by_id.get(iid, [])
    tracker.add_comment.return_value = {}
    tracker.update_issue.return_value = None
    tracker.archive_issue.return_value = None
    return tracker


class TestRunWatchdogAuditSafeReopen:
    def test_safe_reopen_accidental_needs_human(self):
        """A task with a completion comment (no question) in NEEDS_HUMAN → reopened."""
        issue = _make_issue("T-100", NEEDS_HUMAN)
        comments = [_comment("oompah", "Agent completed the task successfully. Pushed.")]
        tracker = _make_tracker([issue], {"T-100": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=1)

        assert result.tasks_audited == 1
        assert result.tasks_actionable == 1
        assert result.actions_taken == 1
        # Should have called update_issue with status=OPEN
        tracker.update_issue.assert_called_once_with("T-100", status=OPEN)
        # Should have posted a watchdog comment
        tracker.add_comment.assert_called_once()
        comment_body = tracker.add_comment.call_args[0][1]
        assert WATCHDOG_COMMENT_MARKER in comment_body

    def test_current_evidence_provider_overrides_handoff_comment(self):
        issue = _make_issue("T-100a", NEEDS_HUMAN)
        tracker = _make_tracker(
            [issue],
            {"T-100a": [_comment("oompah", "Focus handoff: needs human review.")]},
        )

        result = run_watchdog_audit(
            [(None, tracker)],
            run_id=13,
            evidence_provider=lambda _project_id, _issue, _tracker: {
                "review": {"number": "692", "state": "merged"}
            },
        )

        assert result.tasks_actionable == 1
        assert result.actions_taken == 1
        tracker.update_issue.assert_called_once_with("T-100a", status=OPEN)

    def test_safe_reopen_ci_fix_with_passing_comment(self):
        issue = _make_issue("T-101", NEEDS_CI_FIX)
        comments = [_comment("ci-bot", "All checks passed on the branch.")]
        tracker = _make_tracker([issue], {"T-101": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=2)

        assert result.tasks_actionable == 1
        assert result.actions_taken == 1
        tracker.update_issue.assert_called_once_with("T-101", status=OPEN)

    def test_safe_reopen_needs_rebase_resolved(self):
        issue = _make_issue("T-102", NEEDS_REBASE)
        comments = [_comment("oompah", "Conflict resolved — branch is clean.")]
        tracker = _make_tracker([issue], {"T-102": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=3)

        assert result.actions_taken == 1
        tracker.update_issue.assert_called_once_with("T-102", status=OPEN)


class TestRunWatchdogAuditRefusal:
    def test_refuses_when_question_pending_in_needs_human(self):
        """Human question present → stays human_blocked, no action."""
        issue = _make_issue("T-110", NEEDS_HUMAN)
        comments = [_comment("oompah", "Could you please review the architecture decision?")]
        tracker = _make_tracker([issue], {"T-110": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=4)

        assert result.tasks_human_blocked == 1
        assert result.actions_taken == 0
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    def test_refuses_when_ci_still_failing_no_comment_evidence(self):
        """No comment says CI passed → insufficient_evidence, no action."""
        issue = _make_issue("T-111", NEEDS_CI_FIX)
        comments = [_comment("human", "The lint errors need to be fixed manually.")]
        tracker = _make_tracker([issue], {"T-111": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=5)

        assert result.tasks_insufficient_evidence == 1
        assert result.actions_taken == 0
        tracker.update_issue.assert_not_called()

    def test_refuses_needs_answer_always(self):
        """NEEDS_ANSWER is always human_blocked, never acted on."""
        issue = _make_issue("T-112", NEEDS_ANSWER)
        comments = []
        tracker = _make_tracker([issue], {"T-112": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=6)

        assert result.tasks_human_blocked == 1
        assert result.actions_taken == 0

    def test_refuses_ambiguous_rebase_state(self):
        """No evidence of rebase resolution → insufficient_evidence."""
        issue = _make_issue("T-113", NEEDS_REBASE)
        comments = [_comment("human", "I'll try to rebase this next week.")]
        tracker = _make_tracker([issue], {"T-113": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=7)

        assert result.tasks_insufficient_evidence == 1
        assert result.actions_taken == 0


class TestRunWatchdogAuditIdempotency:
    def test_already_actioned_task_is_skipped(self):
        """If the last comment is a watchdog sentinel and nothing else changed, skip."""
        issue = _make_issue("T-120", NEEDS_HUMAN)
        comments = [_comment("oompah", f"{WATCHDOG_COMMENT_MARKER} prior audit")]
        tracker = _make_tracker([issue], {"T-120": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=8)

        assert result.actions_skipped == 1
        assert result.actions_taken == 0
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    def test_multiple_projects_independent(self):
        """Each project is audited independently; one action doesn't affect another."""
        issue_a = _make_issue("A-1", NEEDS_HUMAN)
        issue_b = _make_issue("B-1", NEEDS_CI_FIX)
        comments_a = [_comment("oompah", "Implementation complete, all done.")]
        comments_b = [_comment("human", "CI is still broken.")]
        tracker_a = _make_tracker([issue_a], {"A-1": comments_a})
        tracker_b = _make_tracker([issue_b], {"B-1": comments_b})

        result = run_watchdog_audit(
            [("proj-a", tracker_a), ("proj-b", tracker_b)],
            run_id=9,
        )

        assert result.tasks_audited == 2
        assert result.tasks_actionable == 1       # only A-1
        assert result.tasks_insufficient_evidence == 1  # B-1
        assert result.actions_taken == 1
        tracker_a.update_issue.assert_called_once_with("A-1", status=OPEN)
        tracker_b.update_issue.assert_not_called()

    def test_same_current_evidence_after_restart_is_idempotent(self):
        first = classify_stalled_task(
            "T-121", NEEDS_HUMAN, [], evidence={"review": {"state": "merged"}}, run_id=1
        )
        comments = [{"author": "oompah", "body": build_watchdog_comment(first)}]
        decision = classify_stalled_task(
            "T-121",
            NEEDS_HUMAN,
            comments,
            evidence={"review": {"state": "merged"}},
            run_id=2,
        )
        assert decision.already_actioned is True
        assert decision.action == "none"

    def test_new_current_evidence_after_restart_is_not_suppressed(self):
        old = StalledTaskDecision(
            task_id="T-122", project_id=None, stalled_status=NEEDS_HUMAN,
            classification="actionable", action="reopen", evidence="old evidence",
        )
        decision = classify_stalled_task(
            "T-122",
            NEEDS_HUMAN,
            [{"author": "oompah", "body": build_watchdog_comment(old)}],
            evidence={"review": {"number": "692", "state": "merged"}},
            run_id=3,
        )
        assert decision.already_actioned is False
        assert decision.classification == "actionable"
        assert "692" in decision.evidence


class TestRunWatchdogAuditTelemetry:
    def test_audit_result_to_dict(self):
        result = WatchdogAuditResult(
            run_id=5,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            duration_s=1.0,
            tasks_audited=3,
            tasks_actionable=1,
            tasks_human_blocked=1,
            tasks_insufficient_evidence=1,
            actions_taken=1,
        )
        d = result.to_dict()
        assert d["run_id"] == 5
        assert d["tasks_audited"] == 3
        assert d["actions_taken"] == 1
        assert "started_at" in d
        assert "finished_at" in d

    def test_maintenance_status_updated_after_run(self):
        issue = _make_issue("T-200", NEEDS_HUMAN)
        comments = []
        tracker = _make_tracker([issue], {"T-200": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=10)

        assert result.started_at
        assert result.finished_at
        assert result.duration_s >= 0.0

    def test_tracker_error_recorded_and_audit_continues(self):
        """If tracker.fetch_issues_by_states raises, the error is logged and audit continues."""
        bad_tracker = MagicMock()
        bad_tracker.fetch_issues_by_states.side_effect = RuntimeError("network error")

        good_issue = _make_issue("T-201", NEEDS_HUMAN)
        good_comments = [_comment("oompah", "Completed successfully.")]
        good_tracker = _make_tracker([good_issue], {"T-201": good_comments})

        result = run_watchdog_audit(
            [("bad-proj", bad_tracker), ("good-proj", good_tracker)],
            run_id=11,
        )

        assert len(result.errors) >= 1
        assert result.tasks_audited == 1  # only the good project's issue
        assert result.actions_taken == 1

    def test_dry_run_does_not_mutate_tracker(self):
        issue = _make_issue("T-202", NEEDS_HUMAN)
        comments = [_comment("oompah", "Done and dusted.")]
        tracker = _make_tracker([issue], {"T-202": comments})

        result = run_watchdog_audit([(None, tracker)], run_id=12, dry_run=True)

        assert result.actions_taken == 1  # counted
        tracker.update_issue.assert_not_called()  # not actually called
        tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# Orchestrator integration tests
# ---------------------------------------------------------------------------


def _make_workflow():
    """Return a minimal WorkflowDefinition for tests."""
    from oompah.models import WorkflowDefinition
    return WorkflowDefinition(config={}, prompt_template="test")


def _make_orchestrator(tmp_path, projects=None):
    from oompah.orchestrator import Orchestrator
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    project_store.epic_branch_name.side_effect = lambda eid: f"epic-{eid}"
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


class TestOrchestratorIntegration:
    def test_collects_current_review_ci_and_audit_evidence(self, tmp_path):
        project = MagicMock()
        project.id = "project-1"
        project.default_branch = "main"
        project.repo_url = "https://github.com/example/repo.git"
        project.access_token = None
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = Issue(
            id="T-300",
            identifier="T-300",
            title="stalled",
            state=NEEDS_HUMAN,
            work_branch="feature/T-300",
            review_number="692",
        )
        tracker = MagicMock()
        tracker.get_metadata.return_value = {
            "oompah.terminal_audit": {
                "pending_chain": [
                    {"target_branch": "main", "branch_key": "audit/T-300"}
                ]
            }
        }
        provider = MagicMock()
        provider.is_available.return_value = True
        provider.get_review.return_value = {"number": "692", "state": "merged"}
        provider.get_branch_head_sha.return_value = "a" * 40
        provider.get_branch_ci_status.return_value = "passed"

        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            evidence = orch._collect_stalled_watchdog_evidence(
                "project-1", issue, tracker
            )

        assert evidence["review"]["state"] == "merged"
        assert evidence["branch"]["canonical_ref"] == "main"
        assert evidence["ci"]["status"] == "passed"
        assert evidence["audit"]["pending_chain"]

    def test_scheduler_watchdog_wakes_once_after_clearing_stale_completed(
        self, tmp_path
    ):
        """Recovered tasks are considered immediately, with one batch wake-up."""
        orch = _make_orchestrator(tmp_path)
        first = _make_issue("T-190", OPEN)
        first.id = "issue-190"
        second = _make_issue("T-191", OPEN)
        second.id = "issue-191"
        orch._last_candidates = [first, second]
        orch.state.completed.update({first.id, second.id})

        with patch.object(orch, "request_refresh") as request_refresh:
            fixed = orch._watchdog_stale_completed()

        assert fixed == 2
        assert first.id not in orch.state.completed
        assert second.id not in orch.state.completed
        request_refresh.assert_called_once_with()

    def test_scheduler_watchdog_does_not_wake_without_recovery(self, tmp_path):
        """A no-op watchdog pass must not create periodic dispatch churn."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("T-192", OPEN)
        issue.id = "issue-192"
        orch._last_candidates = [issue]

        with patch.object(orch, "request_refresh") as request_refresh:
            fixed = orch._watchdog_stale_completed()

        assert fixed == 0
        request_refresh.assert_not_called()

    def test_scheduler_watchdog_preserves_terminal_completion(self, tmp_path):
        """Terminal tasks remain suppressed and do not wake dispatch."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("T-193", "Merged")
        issue.id = "issue-193"
        orch._last_candidates = [issue]
        orch.state.completed.add(issue.id)

        with patch.object(orch, "request_refresh") as request_refresh:
            fixed = orch._watchdog_stale_completed()

        assert fixed == 0
        assert issue.id in orch.state.completed
        request_refresh.assert_not_called()

    def test_stalled_watchdog_reopen_clears_suppression_and_wakes_once(
        self, tmp_path
    ):
        """Verified tracker reopens become selectable on the next dispatch pass."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        first = _make_issue("T-194", OPEN)
        first.id = "issue-194"
        second = _make_issue("T-195", OPEN)
        second.id = "issue-195"
        tracker.fetch_issue_detail.side_effect = [first, second]
        result = WatchdogAuditResult(
            decisions=[
                StalledTaskDecision(
                    task_id=first.identifier,
                    project_id=None,
                    stalled_status=NEEDS_HUMAN,
                    classification="actionable",
                    action="reopen",
                    evidence="completed without a human question",
                ),
                StalledTaskDecision(
                    task_id=second.identifier,
                    project_id=None,
                    stalled_status=NEEDS_CI_FIX,
                    classification="actionable",
                    action="reopen",
                    evidence="CI now passes",
                ),
            ]
        )
        orch.state.completed.update({first.id, second.id})
        orch.state.claimed.update({first.id, second.id})
        orch.state.claimed_issues[first.id] = first
        orch.state.claimed_issues[second.id] = second
        orch.state.reopen_counts[first.id] = 3
        orch.state.reopen_counts[second.id] = 3

        with patch.object(orch, "request_refresh") as request_refresh:
            recovered = orch._reconcile_stalled_watchdog_reopens(
                result, {None: tracker}
            )

        assert recovered == 2
        assert not ({first.id, second.id} & orch.state.completed)
        assert not ({first.id, second.id} & orch.state.claimed)
        assert first.id not in orch.state.claimed_issues
        assert second.id not in orch.state.claimed_issues
        assert first.id not in orch.state.reopen_counts
        assert second.id not in orch.state.reopen_counts
        request_refresh.assert_called_once_with()

    def test_stalled_watchdog_does_not_reconcile_unverified_reopen(self, tmp_path):
        """A failed or reverted tracker write cannot clear scheduler safeguards."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        issue = _make_issue("T-196", NEEDS_HUMAN)
        issue.id = "issue-196"
        tracker.fetch_issue_detail.return_value = issue
        result = WatchdogAuditResult(
            decisions=[
                StalledTaskDecision(
                    task_id=issue.identifier,
                    project_id=None,
                    stalled_status=NEEDS_HUMAN,
                    classification="actionable",
                    action="reopen",
                    evidence="completion evidence",
                )
            ]
        )
        orch.state.completed.add(issue.id)

        with patch.object(orch, "request_refresh") as request_refresh:
            recovered = orch._reconcile_stalled_watchdog_reopens(
                result, {None: tracker}
            )

        assert recovered == 0
        assert issue.id in orch.state.completed
        request_refresh.assert_not_called()

    def test_watchdog_coalesced_when_already_in_flight(self, tmp_path):
        """If watchdog is already in-flight, a second call is coalesced (skipped)."""
        orch = _make_orchestrator(tmp_path)
        state = orch._get_or_create_job_state("stalled_task_watchdog")
        state.in_flight = True

        orch._maybe_run_stalled_task_watchdog()

        # in_flight=True means it should be skipped
        assert state.skip_count >= 1
        assert state.run_count == 0

    def test_watchdog_respects_interval(self, tmp_path):
        """If the interval has not elapsed, a call is skipped."""
        import time
        orch = _make_orchestrator(tmp_path)
        # Set last run to now so the next_run is in the future
        now = time.monotonic()
        state = orch._get_or_create_job_state("stalled_task_watchdog")
        state.last_run_monotonic = now
        state.next_run_monotonic = now + 9999.0

        orch._maybe_run_stalled_task_watchdog()

        assert state.skip_count >= 1
        assert state.run_count == 0

    def test_watchdog_runs_when_interval_elapsed(self, tmp_path):
        """When interval has elapsed, the watchdog runs."""
        import time
        orch = _make_orchestrator(tmp_path)

        # Ensure tracker is available
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = []

        # Set last run far in the past
        state = orch._get_or_create_job_state("stalled_task_watchdog")
        state.last_run_monotonic = time.monotonic() - 9999.0
        state.next_run_monotonic = time.monotonic() - 1.0

        orch._maybe_run_stalled_task_watchdog()

        assert state.run_count == 1
        assert state.last_status in ("completed", "failed")

    def test_watchdog_uses_configured_interval(self, tmp_path):
        """The interval used by the watchdog comes from config."""
        orch = _make_orchestrator(tmp_path)
        orch.config.stalled_task_watchdog_interval_seconds = 3600

        with patch.object(orch, "_run_maintenance_job") as mock_rmj:
            orch._maybe_run_stalled_task_watchdog()

        mock_rmj.assert_called_once()
        _, kwargs = mock_rmj.call_args[0], mock_rmj.call_args[1]
        assert mock_rmj.call_args.kwargs.get("min_interval_s") == 3600.0 or \
               mock_rmj.call_args[1].get("min_interval_s") == 3600.0 or \
               3600.0 in mock_rmj.call_args.args

    def test_watchdog_maintenance_status_populated(self, tmp_path):
        """After a run, maintenance_status has stalled_task_watchdog key."""
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = []

        orch._do_stalled_task_watchdog()

        assert "stalled_task_watchdog" in orch._maintenance_status
        snapshot = orch._maintenance_status["stalled_task_watchdog"]
        assert "run_id" in snapshot
        assert "tasks_audited" in snapshot
        assert "actions_taken" in snapshot

    def test_watchdog_does_not_block_normal_dispatch(self, tmp_path):
        """_run_step5b_maintenance submits watchdog to thread pool (non-blocking)."""
        # Verify the watchdog is *called* inside _run_step5b_maintenance
        orch = _make_orchestrator(tmp_path)
        with patch.object(orch, "_maybe_run_stalled_task_watchdog") as mock_wdg, \
             patch.object(orch, "_maybe_heal_repos"), \
             patch.object(orch, "_maybe_cleanup_worktrees"), \
             patch.object(orch, "_auto_archive"), \
             patch.object(orch, "_maybe_open_deferred_done_reviews"), \
             patch.object(orch, "_maybe_run_merged_labels"), \
             patch.object(orch, "_maybe_run_release_pick_reconciliation"), \
             patch.object(orch, "_maybe_sync_github_issue_intake"):
            orch._run_step5b_maintenance()

        mock_wdg.assert_called_once()

    def test_watchdog_run_id_increments(self, tmp_path):
        """Each _do_stalled_task_watchdog call uses an incrementing run_id."""
        orch = _make_orchestrator(tmp_path)
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = []

        orch._do_stalled_task_watchdog()
        orch._do_stalled_task_watchdog()

        snap = orch._maintenance_status["stalled_task_watchdog"]
        assert snap["run_id"] == 2


# ---------------------------------------------------------------------------
# OOMPAH-818: Fence stalled-task reopen against exact failing gate evidence
# ---------------------------------------------------------------------------


_OOMPAH_814_HEAD = "254b131c713bece56500a72408f796c46bfee8d0"
_REPAIR_HEAD = "9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f"


def _blocked_gate_row(orch):
    orch.integration_queue.enqueue(
        project_id="project-1",
        epic_id="EPIC-1",
        task_id="OOMPAH-814",
        task_branch="OOMPAH-814",
        head_sha=_OOMPAH_814_HEAD,
    )
    claimed = orch.integration_queue.claim_next(
        project_id="project-1",
        epic_id="EPIC-1",
        lease_owner="gate-owner",
        dependency_map={"OOMPAH-814": ("dependency",)},
        satisfied={"dependency"},
    )
    assert claimed is not None
    assert orch.integration_queue.fail(
        "project-1",
        "OOMPAH-814",
        lease_owner="gate-owner",
        error="Combined-tree quality gate failed: 2 failures",
    )
    return orch.integration_queue.get("project-1", "OOMPAH-814")


def _oompah_814_evidence(
    *,
    ci_status: str = "passed",
    integration_state: str = "blocked",
    gate_status: str | None = "failed",
    gate_head: str = _OOMPAH_814_HEAD,
    branch_head: str | None = None,
    accepted_head: str | None = None,
    generation: str = "gen-authoritative-42",
) -> dict:
    """Build the deterministic OOMPAH-814-shaped evidence envelope."""
    ev: dict = {
        "integration": {
            "state": integration_state,
            "head_sha": accepted_head or _OOMPAH_814_HEAD,
            "task_branch": "OOMPAH-814",
        },
        "branch": {
            "canonical_ref": "main",
            "head_sha": branch_head or _OOMPAH_814_HEAD,
        },
        "ci": {"status": ci_status},
    }
    if gate_status is not None:
        ev["gate"] = {
            "head_sha": gate_head,
            "status": gate_status,
            "generation": generation,
        }
    return ev


class TestGateFailureFencesWatchdogReopen:
    """OOMPAH-818 acceptance: the OOMPAH-814 sequence cannot report passing."""

    def test_authoritative_gate_failure_dominates_passing_ci(self):
        """Gate failed at exact accepted head → watchdog must not reopen."""
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence=_oompah_814_evidence(),
            run_id=22,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"
        assert decision.evidence_head == _OOMPAH_814_HEAD
        assert decision.evidence_result in {"failed", "fail", "failure"}
        assert decision.evidence_generation == "gen-authoritative-42"
        assert "dominates" in decision.evidence.lower()

    def test_durable_gate_evidence_survives_orchestrator_restart(self, tmp_path):
        from oompah.integration import IntegrationRecord

        project = MagicMock()
        project.id = "project-1"
        project.default_branch = "main"
        project.repo_url = "https://github.com/example/repo.git"
        project.access_token = None
        first = _make_orchestrator(tmp_path, projects=[project])
        blocked = _blocked_gate_row(first)
        assert blocked is not None
        first.integration_queue.close()

        restarted = _make_orchestrator(tmp_path, projects=[project])
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_OOMPAH_814_HEAD,
            ),
        )

        restarted_row = restarted.integration_queue.get("project-1", "OOMPAH-814")
        assert restarted_row is not None
        assert restarted._retire_inactive_integration_rows(
            "project-1",
            [issue],
            [restarted_row],
        ) == 0

        snapshot = restarted._collect_stalled_watchdog_gate_snapshot(
            "project-1",
            issue,
        )

        assert snapshot["status"] == "failed"
        assert snapshot["head_sha"] == _OOMPAH_814_HEAD
        assert snapshot["generation"].startswith("integration-queue-v1:")

    def test_action_time_queue_cas_rejects_concurrent_gate_transition(self, tmp_path):
        from oompah.integration import IntegrationRecord

        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_OOMPAH_814_HEAD,
            ),
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        orch.integration_queue.enqueue(
            project_id="project-1",
            epic_id="EPIC-1",
            task_id="OOMPAH-814",
            task_branch="OOMPAH-814",
            head_sha=_REPAIR_HEAD,
        )
        executed = orch._execute_stalled_watchdog_reopen(
            "project-1",
            issue,
            tracker,
            decision,
            build_watchdog_comment(decision),
        )

        assert executed is False
        tracker.add_comment.assert_not_called()
        tracker.update_issue.assert_not_called()

    def test_action_time_queue_cas_applies_unchanged_generation(self, tmp_path):
        from oompah.integration import IntegrationRecord

        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_OOMPAH_814_HEAD,
            ),
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        with patch.object(
            orch,
            "_stalled_watchdog_branch_head",
            return_value=_REPAIR_HEAD,
        ):
            executed = orch._execute_stalled_watchdog_reopen(
                "project-1",
                issue,
                tracker,
                decision,
                build_watchdog_comment(decision),
            )

        assert executed is True
        tracker.add_comment.assert_called_once()
        tracker.update_issue.assert_called_once_with("OOMPAH-814", status=OPEN)

    def test_action_time_queue_cas_rejects_missing_tracker_integration(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=None,
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        with patch.object(
            orch,
            "_stalled_watchdog_branch_head",
            return_value=_REPAIR_HEAD,
        ):
            executed = orch._execute_stalled_watchdog_reopen(
                "project-1",
                issue,
                tracker,
                decision,
                build_watchdog_comment(decision),
            )

        assert executed is False
        tracker.add_comment.assert_not_called()
        tracker.update_issue.assert_not_called()

    @pytest.mark.parametrize(
        ("task_branch", "head_sha"),
        [
            (None, _OOMPAH_814_HEAD),
            ("OOMPAH-814", None),
        ],
    )
    def test_action_time_queue_cas_rejects_incomplete_tracker_integration(
        self,
        tmp_path,
        task_branch,
        head_sha,
    ):
        from oompah.integration import IntegrationRecord

        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch=task_branch,
                head_sha=head_sha,
            ),
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        with patch.object(
            orch,
            "_stalled_watchdog_branch_head",
            return_value=_REPAIR_HEAD,
        ):
            executed = orch._execute_stalled_watchdog_reopen(
                "project-1",
                issue,
                tracker,
                decision,
                build_watchdog_comment(decision),
            )

        assert executed is False
        tracker.add_comment.assert_not_called()
        tracker.update_issue.assert_not_called()

    def test_action_time_queue_cas_rejects_branch_rollback_to_failed_head(
        self,
        tmp_path,
    ):
        from oompah.integration import IntegrationRecord

        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_OOMPAH_814_HEAD,
            ),
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        with patch.object(
            orch,
            "_stalled_watchdog_branch_head",
            return_value=_OOMPAH_814_HEAD,
        ):
            executed = orch._execute_stalled_watchdog_reopen(
                "project-1",
                issue,
                tracker,
                decision,
                build_watchdog_comment(decision),
            )

        assert executed is False
        tracker.add_comment.assert_not_called()
        tracker.update_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_tracker_generation_change_waiting_on_shared_authority_fails_closed(
        self,
        tmp_path,
    ):
        from oompah.integration import IntegrationRecord

        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_OOMPAH_814_HEAD,
            ),
        )
        replacement = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="new generation",
            state="Ready to Integrate",
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_REPAIR_HEAD,
            ),
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        authority = orch.issue_transition_lock(issue.id)
        await authority.acquire()
        try:
            reopen = asyncio.create_task(
                orch._execute_stalled_watchdog_reopen_under_authority(
                    "project-1",
                    issue,
                    tracker,
                    decision,
                    build_watchdog_comment(decision),
                )
            )
            await asyncio.sleep(0)
            tracker.fetch_issue_detail.assert_not_called()
            tracker.fetch_issue_detail.return_value = replacement
        finally:
            authority.release()

        executed = await reopen
        assert executed is False
        tracker.add_comment.assert_not_called()
        tracker.update_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_tracker_generation_change_during_action_waits_for_authority(
        self,
        tmp_path,
    ):
        from oompah.integration import IntegrationRecord

        orch = _make_orchestrator(tmp_path)
        blocked = _blocked_gate_row(orch)
        assert blocked is not None
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
            integration=IntegrationRecord(
                state="ready",
                task_branch="OOMPAH-814",
                head_sha=_OOMPAH_814_HEAD,
            ),
        )
        tracker = MagicMock()
        fetch_entered = threading.Event()
        release_fetch = threading.Event()
        order: list[str] = []

        def fetch_current(_identifier):
            fetch_entered.set()
            assert release_fetch.wait(timeout=3)
            return issue

        tracker.fetch_issue_detail.side_effect = fetch_current
        tracker.update_issue.side_effect = lambda *_a, **_k: order.append(
            "watchdog-open"
        )
        decision = StalledTaskDecision(
            task_id=issue.identifier,
            project_id="project-1",
            stalled_status=NEEDS_CI_FIX,
            classification="actionable",
            action="reopen",
            evidence="repair CI passed on an advanced head",
            evidence_head=_REPAIR_HEAD,
            evidence_result="ci_passing_at_advanced_head",
            evidence_generation=(
                f"integration-queue-v1:{blocked.authority_generation()}"
            ),
        )

        with patch.object(
            orch,
            "_stalled_watchdog_branch_head",
            return_value=_REPAIR_HEAD,
        ):
            reopen = asyncio.create_task(
                orch._execute_stalled_watchdog_reopen_under_authority(
                    "project-1",
                    issue,
                    tracker,
                    decision,
                    build_watchdog_comment(decision),
                )
            )
            assert await asyncio.to_thread(fetch_entered.wait, 3)

            async def replace_tracker_generation():
                async with orch.issue_transition_lock(issue.id):
                    order.append("replacement-generation")

            replacement = asyncio.create_task(replace_tracker_generation())
            await asyncio.sleep(0)
            assert "replacement-generation" not in order
            release_fetch.set()
            executed = await reopen
            await replacement

        assert executed is True
        assert order == ["watchdog-open", "replacement-generation"]

    def test_gate_failure_immediately_before_watchdog_classification(self):
        """Gate completes with failures → next watchdog tick must not reopen."""
        # Simulate the exact interleaving reported in the incident: gate
        # completed with 2 failures, task moved to Needs CI Fix; the next
        # watchdog run must see the failing exact-head result and refuse.
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [
                _comment(
                    "oompah",
                    "Combined-tree quality gate failed: 2 test failures.",
                ),
            ],
            evidence=_oompah_814_evidence(),
            run_id=22,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_gate_failure_during_watchdog_classification(self):
        """Older pass evidence + newer fail → newer fail dominates."""
        # Older passing SCM CI check is still visible, but a newer
        # authoritative gate result at the same accepted head is failing.
        # The newer failing result must dominate.
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [_comment("ci-bot", "CI checks are green on this branch.")],
            evidence=_oompah_814_evidence(
                ci_status="passed",
                gate_status="failed",
            ),
            run_id=22,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.evidence_result in {"failed", "fail", "failure"}

    def test_pass_on_different_head_does_not_reopen_needs_ci_fix(self):
        """A passing gate on a stale head must not reopen the current head."""
        # Gate reports a passing result but at a DIFFERENT head from the
        # accepted head.  This must not become an actionable reopen.
        stale_pass_head = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": _OOMPAH_814_HEAD,
                    "task_branch": "OOMPAH-814",
                },
                "branch": {"head_sha": _OOMPAH_814_HEAD},
                "gate": {
                    "head_sha": stale_pass_head,
                    "status": "passed",
                    "generation": "gen-stale",
                },
                "ci": {"status": "passed"},
            },
            run_id=22,
        )
        # The gate result is on a different head, so the primary dominance
        # fence does not fire.  But the integration-state fence catches the
        # regression: branch head still equals accepted head, so no repair
        # has been pushed and we must not reopen.
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_gate_pass_at_exact_accepted_head_reopens_with_evidence(self):
        """A newer passing gate on the exact accepted head is safe to reopen."""
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence={
                "integration": {
                    "state": "ready",
                    "head_sha": _OOMPAH_814_HEAD,
                    "task_branch": "OOMPAH-814",
                },
                "branch": {"head_sha": _OOMPAH_814_HEAD},
                "gate": {
                    "head_sha": _OOMPAH_814_HEAD,
                    "status": "passed",
                    "generation": "gen-passed-777",
                },
            },
            run_id=22,
        )
        assert decision.classification == "actionable"
        assert decision.action == "reopen"
        assert decision.evidence_head == _OOMPAH_814_HEAD
        assert decision.evidence_result == "passed"
        assert decision.evidence_generation == "gen-passed-777"

    def test_pass_on_advanced_head_after_repair_can_reopen(self):
        """A repair push moves the branch past accepted head → safe to reopen."""
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence={
                "integration": {
                    "state": "ready",
                    "head_sha": _OOMPAH_814_HEAD,
                    "task_branch": "OOMPAH-814",
                },
                "branch": {"head_sha": _REPAIR_HEAD},
                "ci": {"status": "passed"},
            },
            run_id=23,
        )
        assert decision.classification == "actionable"
        assert decision.action == "reopen"
        assert decision.evidence_head == _REPAIR_HEAD

    def test_ci_passing_at_same_accepted_head_is_stale(self):
        """SCM CI passing at unchanged accepted head is stale evidence."""
        # This is the concrete OOMPAH-814 shape: the SCM (focused) CI shows
        # passing, but the branch head is unchanged from the accepted head
        # that the combined-tree gate failed on.
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": _OOMPAH_814_HEAD,
                    "task_branch": "OOMPAH-814",
                },
                "branch": {"head_sha": _OOMPAH_814_HEAD},
                "ci": {"status": "passed"},
            },
            run_id=22,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_duplicate_watchdog_runs_stay_idempotent(self):
        """Two consecutive runs against the same failing gate stay idempotent."""
        evidence = _oompah_814_evidence()
        first = classify_stalled_task(
            "OOMPAH-814", NEEDS_CI_FIX, [], evidence=evidence, run_id=22
        )
        assert first.classification == "insufficient_evidence"
        # Sentinel from first run is now in the comments — but the watchdog
        # never actually acted (action="none"), so it does not post a
        # sentinel and a second run must also refuse.
        second = classify_stalled_task(
            "OOMPAH-814", NEEDS_CI_FIX, [], evidence=evidence, run_id=23
        )
        assert second.classification == "insufficient_evidence"
        assert second.action == "none"
        # Same authoritative evidence surfaced in both decisions.
        assert first.evidence_head == second.evidence_head == _OOMPAH_814_HEAD
        assert first.evidence_generation == second.evidence_generation

    def test_restart_reconciliation_still_dominates(self):
        """After a service restart the persisted evidence still dominates."""
        # A prior watchdog sentinel exists.  In a naive rerun the idempotency
        # check would skip the task; but if a caller supplies fresh
        # authoritative evidence the failing exact-head result must still
        # dominate any softer reopen path.
        prior_decision = StalledTaskDecision(
            task_id="OOMPAH-814",
            project_id=None,
            stalled_status=NEEDS_CI_FIX,
            classification="insufficient_evidence",
            action="none",
            evidence="stale evidence",
        )
        comments = [{"author": "oompah", "body": build_watchdog_comment(prior_decision)}]
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            comments,
            evidence=_oompah_814_evidence(),
            run_id=24,
        )
        # Either the idempotency short-circuit fires (already_actioned) or
        # the fence re-runs and re-issues the same insufficient_evidence
        # verdict.  Neither can produce an actionable reopen.
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_needs_rebase_gate_failure_dominates(self):
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_REBASE,
            [],
            evidence=_oompah_814_evidence(gate_status="needs_rebase"),
            run_id=25,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"
        assert decision.evidence_result == "needs_rebase"

    def test_needs_rebase_ci_stale_at_accepted_head(self):
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_REBASE,
            [],
            evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": _OOMPAH_814_HEAD,
                    "task_branch": "OOMPAH-814",
                },
                "branch": {"head_sha": _OOMPAH_814_HEAD, "scm_state": "clean"},
                "ci": {"status": "passed"},
            },
            run_id=25,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_gate_result_exposed_in_watchdog_comment(self):
        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence=_oompah_814_evidence(),
            run_id=42,
        )
        body = build_watchdog_comment(decision)
        assert _OOMPAH_814_HEAD in body
        assert "Evidence head" in body
        assert "Evidence result" in body
        assert "Evidence generation" in body
        assert "gen-authoritative-42" in body

    def test_structured_event_exposes_gate_result(self):
        issue = _make_issue("OOMPAH-814", NEEDS_CI_FIX)
        tracker = _make_tracker([issue], {"OOMPAH-814": []})
        result = run_watchdog_audit(
            [(None, tracker)],
            run_id=22,
            evidence_provider=lambda *_a: _oompah_814_evidence(),
        )
        assert result.tasks_insufficient_evidence == 1
        assert result.actions_taken == 0
        snapshot = result.to_dict()
        assert snapshot["decisions"]
        decision = snapshot["decisions"][0]
        assert decision["evidence_head"] == _OOMPAH_814_HEAD
        assert decision["evidence_result"] in {"failed", "fail", "failure"}
        assert decision["evidence_generation"] == "gen-authoritative-42"

    def test_watchdog_audit_does_not_reopen_or_cancel_integration(self):
        """OOMPAH-818 acceptance: OOMPAH-814 sequence cannot reopen."""
        # This mirrors the exact sequence in the incident report — the task
        # is Needs CI Fix, integration record shows the failing accepted
        # head, and a passing focused/SCM CI check is visible.  The
        # watchdog must not reopen and must not cause the integration row
        # to be cancelled downstream.
        issue = _make_issue("OOMPAH-814", NEEDS_CI_FIX)
        tracker = _make_tracker([issue], {"OOMPAH-814": []})
        result = run_watchdog_audit(
            [(None, tracker)],
            run_id=22,
            evidence_provider=lambda *_a: _oompah_814_evidence(),
        )
        assert result.actions_taken == 0
        assert result.tasks_actionable == 0
        # No status change → no downstream integration-row cancellation.
        tracker.update_issue.assert_not_called()

    def test_older_pass_and_newer_fail_from_evidence_provider(self):
        """Deterministic interleaving: repeated audit with newer failing evidence."""
        issue = _make_issue("OOMPAH-814", NEEDS_CI_FIX)
        # First tick: only the older passing signal is available (gate not
        # yet complete).  Because integration record is blocked at the
        # accepted head and no advance has happened, the fence still holds.
        older_evidence = {
            "integration": {
                "state": "blocked",
                "head_sha": _OOMPAH_814_HEAD,
                "task_branch": "OOMPAH-814",
            },
            "branch": {"head_sha": _OOMPAH_814_HEAD},
            "ci": {"status": "passed"},
        }
        tracker = _make_tracker([issue], {"OOMPAH-814": []})
        first = run_watchdog_audit(
            [(None, tracker)],
            run_id=22,
            evidence_provider=lambda *_a: older_evidence,
        )
        assert first.actions_taken == 0
        # Second tick: the authoritative failing gate is now visible.  The
        # decision remains insufficient_evidence and now records the exact
        # failing head/result/generation for observability.
        tracker.reset_mock()
        # Ensure fetch_issues_by_states still returns the same issue.
        tracker.fetch_issues_by_states.return_value = [issue]
        tracker.fetch_comments.side_effect = lambda iid: []
        second = run_watchdog_audit(
            [(None, tracker)],
            run_id=23,
            evidence_provider=lambda *_a: _oompah_814_evidence(
                ci_status="passed",
                gate_status="failed",
            ),
        )
        assert second.actions_taken == 0
        decisions = second.decisions
        assert decisions and decisions[0].evidence_head == _OOMPAH_814_HEAD

    def test_orchestrator_evidence_carries_gate_and_integration(self, tmp_path):
        """The orchestrator collects integration record and gate outcome."""
        # Import here so the shared fixtures/helpers above stay stable.
        from oompah.integration import IntegrationRecord

        project = MagicMock()
        project.id = "project-1"
        project.default_branch = "main"
        project.repo_url = "https://github.com/example/repo.git"
        project.access_token = None
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="OOMPAH-814",
        )
        issue.integration = IntegrationRecord(
            state="ready",
            task_branch="OOMPAH-814",
            base_branch="epic-e",
            head_sha=_OOMPAH_814_HEAD,
            attempts=1,
            last_error="Combined-tree quality gate failed",
        )
        orch.integration_queue.enqueue(
            project_id="project-1",
            epic_id="EPIC-1",
            task_id="OOMPAH-814",
            task_branch="OOMPAH-814",
            head_sha=_OOMPAH_814_HEAD,
        )
        claimed = orch.integration_queue.claim_next(
            project_id="project-1",
            epic_id="EPIC-1",
            lease_owner="gate-owner",
            dependency_map={"OOMPAH-814": ("dependency",)},
            satisfied={"dependency"},
        )
        assert claimed is not None
        assert orch.integration_queue.fail(
            "project-1",
            "OOMPAH-814",
            lease_owner="gate-owner",
            error="Combined-tree quality gate failed: 2 failures",
        )
        tracker = MagicMock()
        tracker.get_metadata.return_value = {}
        provider = MagicMock()
        provider.is_available.return_value = True
        provider.get_review.return_value = None
        provider.find_pr_for_branch.return_value = None
        provider.get_branch_head_sha.return_value = _OOMPAH_814_HEAD
        provider.get_branch_ci_status.return_value = "passed"

        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            evidence = orch._collect_stalled_watchdog_evidence(
                "project-1", issue, tracker
            )
        assert evidence["integration"]["head_sha"] == _OOMPAH_814_HEAD
        assert evidence["integration"]["state"] == "ready"
        assert evidence["gate"]["head_sha"] == _OOMPAH_814_HEAD
        assert evidence["gate"]["status"] == "failed"
        assert evidence["gate"]["queue_state"] == "blocked"
        assert evidence["gate"]["generation"].startswith("integration-queue-v1:")

        decision = classify_stalled_task(
            "OOMPAH-814",
            NEEDS_CI_FIX,
            [],
            evidence=evidence,
            run_id=22,
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"
        assert decision.evidence_head == _OOMPAH_814_HEAD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comment(author: str, body: str) -> dict:
    """Build a minimal comment dict."""
    return {"author": author, "body": body}
