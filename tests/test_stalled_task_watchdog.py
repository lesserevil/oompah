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

import os
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

    def test_collects_integration_record_for_internal_gate_authority(self, tmp_path):
        """OOMPAH-806: the integration record must be exposed as evidence."""
        project = MagicMock()
        project.id = "project-1"
        project.default_branch = "main"
        project.repo_url = "https://github.com/example/repo.git"
        project.access_token = None
        orch = _make_orchestrator(tmp_path, projects=[project])
        issue = Issue(
            id="T-806",
            identifier="T-806",
            title="stalled",
            state=NEEDS_CI_FIX,
            work_branch="feature/T-806",
        )
        tracker = MagicMock()
        tracker.get_metadata.return_value = {
            "oompah.integration": {
                "state": "blocked",
                "head_sha": "ef5e8c30e" + "0" * 31,
                "last_error": "combined-tree gate failed",
                "task_branch": "feature/T-806",
            },
        }
        provider = MagicMock()
        provider.is_available.return_value = True
        provider.get_review.return_value = None
        provider.get_branch_head_sha.return_value = "ef5e8c30e" + "0" * 31
        provider.get_branch_ci_status.return_value = "passed"

        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            evidence = orch._collect_stalled_watchdog_evidence(
                "project-1", issue, tracker
            )

        assert "integration" in evidence
        assert evidence["integration"]["state"] == "blocked"
        assert evidence["integration"]["head_sha"] == "ef5e8c30e" + "0" * 31

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
# OOMPAH-806: internal gate authority precedence over external forge CI
# ---------------------------------------------------------------------------


class TestInternalGateAuthorityPrecedence:
    """OOMPAH-806: external CI must not override a blocked internal gate.

    The live reproduction on OOMPAH-793 was: an exact-head combined-tree
    integration gate failed at head ef5e8c30e; the integration row moved to
    ``blocked`` and the tracker task moved to ``Needs CI Fix``.  Minutes later
    the watchdog observed unrelated passing external commit CI, reopened the
    task to ``Open``, and the integration reconciler cancelled the blocked
    row because tracker state was no longer ``Ready to Integrate``.  The
    watchdog must instead refuse to act while the internal record is blocked
    at the same head.
    """

    def test_blocked_gate_at_same_head_refuses_reopen_on_passing_external_ci(self):
        """External CI green cannot override an authoritative blocked gate."""
        decision = classify_stalled_task(
            "T-806-1",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "ef5e8c30e" + "0" * 31,
                    "last_error": "combined-tree gate failed",
                },
                "branch": {"head_sha": "ef5e8c30e" + "0" * 31},
                "ci": {"status": "success"},
            },
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"
        assert "blocked" in decision.evidence.lower()

    def test_blocked_gate_at_same_head_refuses_reopen_on_ci_passing_comment(self):
        """Prose 'CI passing' comment cannot override authoritative blocked gate."""
        comments = [_comment("ci-bot", "All checks passed on the branch.")]
        decision = classify_stalled_task(
            "T-806-2",
            NEEDS_CI_FIX,
            comments,
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
            },
        )
        assert decision.classification == "insufficient_evidence"
        assert decision.action == "none"

    def test_newer_pushed_head_allows_reopen_on_passing_ci(self):
        """A newer branch head is authoritative repair evidence."""
        decision = classify_stalled_task(
            "T-806-3",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "branch": {"head_sha": "b" * 40},
                "ci": {"status": "success"},
            },
        )
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_blocked_needs_rebase_refuses_external_ci_reopen(self):
        decision = classify_stalled_task(
            "T-806-4",
            NEEDS_REBASE,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "branch": {"head_sha": "a" * 40, "exists": True},
                "ci": {"status": "green"},
            },
        )
        assert decision.classification == "insufficient_evidence"

    def test_blocked_gate_unknown_branch_head_still_refuses(self):
        """When branch head is unknown, keep the blocked verdict authoritative."""
        decision = classify_stalled_task(
            "T-806-5",
            NEEDS_CI_FIX,
            [_comment("bot", "CI is now passing.")],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
            },
        )
        assert decision.classification == "insufficient_evidence"

    def test_merged_review_still_overrides_blocked_record(self):
        """Merged review evidence is authoritative repair evidence."""
        decision = classify_stalled_task(
            "T-806-6",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "review": {"state": "merged"},
            },
        )
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_audit_verdict_pass_still_overrides_blocked_record(self):
        decision = classify_stalled_task(
            "T-806-7",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "audit": {"verdict": "pass"},
            },
        )
        assert decision.classification == "actionable"

    def test_ready_integration_state_does_not_trigger_precedence(self):
        """Only ``blocked`` state activates internal-authority precedence."""
        decision = classify_stalled_task(
            "T-806-8",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {"state": "ready", "head_sha": "a" * 40},
                "ci": {"status": "success"},
            },
        )
        assert decision.classification == "actionable"
        assert decision.action == "reopen"

    def test_unrelated_task_ci_cannot_influence_this_task(self):
        """Watchdog only reads per-task evidence; unrelated CI is irrelevant."""
        # An unrelated task's CI status can only reach this task's classifier
        # via the current_evidence pathway.  When the evidence for THIS task
        # says ``blocked`` at the current head, the classifier refuses
        # regardless of what any other task looks like.
        decision = classify_stalled_task(
            "T-806-9",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "branch": {"head_sha": "a" * 40},
                "ci": {"status": "success"},
            },
        )
        assert decision.classification == "insufficient_evidence"

    def test_restart_preserves_precedence_same_evidence(self):
        """A restart re-reads evidence; blocked at same head still refuses."""
        # First run: watchdog posts sentinel comment.
        first = classify_stalled_task(
            "T-806-10",
            NEEDS_CI_FIX,
            [],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "branch": {"head_sha": "a" * 40},
                "ci": {"status": "success"},
            },
            run_id=1,
        )
        assert first.classification == "insufficient_evidence"
        # Sentinel comment then persists after restart.
        sentinel = _comment("oompah", f"{WATCHDOG_COMMENT_MARKER} run #1\n\n"
                            f"**Evidence:** {first.evidence}")
        # Second run with identical evidence: idempotent, still refuses.
        second = classify_stalled_task(
            "T-806-10",
            NEEDS_CI_FIX,
            [sentinel],
            current_evidence={
                "integration": {
                    "state": "blocked",
                    "head_sha": "a" * 40,
                },
                "branch": {"head_sha": "a" * 40},
                "ci": {"status": "success"},
            },
            run_id=2,
        )
        assert second.classification == "insufficient_evidence"

    def test_run_watchdog_audit_does_not_reopen_blocked_gate(self):
        """End-to-end: watchdog does not call update_issue when blocked."""
        issue = _make_issue("T-806-e2e", NEEDS_CI_FIX)
        tracker = _make_tracker(
            [issue],
            {"T-806-e2e": [_comment("bot", "CI is now passing on the branch.")]},
        )

        result = run_watchdog_audit(
            [(None, tracker)],
            run_id=42,
            evidence_by_task={
                "T-806-e2e": {
                    "integration": {
                        "state": "blocked",
                        "head_sha": "a" * 40,
                        "last_error": "combined-tree gate failed at ef5e8c30e",
                    },
                    "branch": {"head_sha": "a" * 40},
                    "ci": {"status": "success"},
                }
            },
        )
        assert result.actions_taken == 0
        assert result.tasks_insufficient_evidence == 1
        tracker.update_issue.assert_not_called()

    def test_newer_head_allows_reopen_via_run_watchdog_audit_once(self):
        """A newer branch head permits exactly one reopen even with blocked history."""
        issue = _make_issue("T-806-repair", NEEDS_CI_FIX)
        tracker = _make_tracker([issue])

        result = run_watchdog_audit(
            [(None, tracker)],
            run_id=51,
            evidence_by_task={
                "T-806-repair": {
                    "integration": {
                        "state": "blocked",
                        "head_sha": "a" * 40,
                    },
                    "branch": {"head_sha": "b" * 40},
                    "ci": {"status": "success"},
                }
            },
        )
        assert result.actions_taken == 1
        tracker.update_issue.assert_called_once_with(
            "T-806-repair", status=OPEN
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comment(author: str, body: str) -> dict:
    """Build a minimal comment dict."""
    return {"author": author, "body": body}
