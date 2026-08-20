"""Contract coverage for the orchestrator's single status-writer boundary."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator, TaskTransitionNotApplied
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionDisposition,
    TransitionPhase,
)


class _StatefulTracker:
    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.updates: list[tuple[str, str]] = []

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        if identifier not in {self.issue.id, self.issue.identifier}:
            return None
        return deepcopy(self.issue)

    def fetch_issue_states_by_ids(self, identifiers: list[str]) -> list[Issue]:
        issue = self.fetch_issue_detail(identifiers[0])
        return [issue] if issue is not None else []

    def update_issue(self, identifier: str, *, status: str) -> None:
        self.updates.append((identifier, status))
        self.issue.state = status


def _issue(state: str = "Open") -> Issue:
    return Issue(
        id="task-1",
        identifier="OOMPAH-TEST",
        title="Transition boundary test",
        description="Exercise the durable orchestrator status writer.",
        state=state,
        issue_type="task",
    )


def _orchestrator(tmp_path, tracker: _StatefulTracker) -> Orchestrator:
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "state.json"),
    )
    orchestrator.tracker = tracker
    return orchestrator


def test_orchestrator_has_no_direct_status_writer_bypass() -> None:
    path = Path(__file__).parents[1] / "oompah" / "orchestrator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "update_issue":
            if any(keyword.arg == "status" for keyword in node.keywords):
                violations.append(node.lineno)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "to_thread"
            and node.args
            and isinstance(node.args[0], ast.Attribute)
            and node.args[0].attr == "update_issue"
            and any(keyword.arg == "status" for keyword in node.keywords)
        ):
            violations.append(node.lineno)
    assert violations == []


def test_migrated_call_sites_carry_reason_and_all_lifecycle_families() -> None:
    source = (Path(__file__).parents[1] / "oompah" / "orchestrator.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    missing_reason: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {
            "_transition_issue_status",
            "_transition_issue_status_async",
            "_transition_identifier_status",
            "_transition_identifier_status_async",
        }:
            continue
        if not any(keyword.arg == "reason_code" for keyword in node.keywords):
            missing_reason.append(node.lineno)
    assert missing_reason == []
    for family in (
        "dispatch.",
        "worker.",
        "retry.",
        "integration.",
        "review.",
        "rollup.",
        "duplicate.",
        "watchdog.",
        "restart.",
        "handoff.",
        "maintenance.",
        "quality_gate.",
    ):
        assert f'"{family}' in source


def test_nonterminal_transition_is_journalled_applied_and_verified(tmp_path) -> None:
    tracker = _StatefulTracker(_issue())
    orchestrator = _orchestrator(tmp_path, tracker)

    outcome = orchestrator._transition_issue_status(
        tracker.fetch_issue_detail("OOMPAH-TEST"),
        "Needs Human",
        tracker=tracker,
        reason_code="watchdog.test_action_required",
    )

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("OOMPAH-TEST", "Needs Human")]
    assert [
        event.phase
        for event in orchestrator.task_transition_journal.events(outcome.transition_id)
    ] == [
        TransitionPhase.REQUESTED,
        TransitionPhase.APPLYING,
        TransitionPhase.APPLIED,
    ]


def test_leaving_validation_fences_and_resolves_terminal_audit_generation(
    tmp_path,
) -> None:
    tracker = _StatefulTracker(_issue("In Validation"))
    orchestrator = _orchestrator(tmp_path, tracker)
    enforcement = orchestrator._terminal_audit_enforcement

    with (
        patch.object(
            enforcement,
            "prepare_status_departure",
            return_value="audit-departure-test",
        ) as prepare,
        patch.object(
            enforcement,
            "resolve_status_departure",
            return_value=True,
        ) as resolve_departure,
    ):
        outcome = orchestrator._transition_issue_status(
            tracker.fetch_issue_detail("OOMPAH-TEST"),
            "Needs Human",
            tracker=tracker,
            reason_code="watchdog.test_validation_departure",
        )

    assert outcome.disposition is TransitionDisposition.APPLIED
    prepare.assert_called_once()
    assert prepare.call_args.args[1].state == "In Validation"
    assert prepare.call_args.args[3] == "Needs Human"
    resolve_departure.assert_called_once()
    assert resolve_departure.call_args.args[-1] == "audit-departure-test"
    assert tracker.issue.state == "Needs Human"


def test_maintenance_departure_uses_same_terminal_audit_fence(tmp_path) -> None:
    tracker = _StatefulTracker(_issue("In Validation"))
    orchestrator = _orchestrator(tmp_path, tracker)
    enforcement = orchestrator._terminal_audit_enforcement
    issue = tracker.fetch_issue_detail("OOMPAH-TEST")
    assert issue is not None

    with (
        patch.object(
            enforcement,
            "prepare_status_departure",
            return_value="audit-departure-maintenance",
        ) as prepare,
        patch.object(
            enforcement,
            "resolve_status_departure",
            return_value=True,
        ) as resolve_departure,
    ):
        outcome = orchestrator._request_task_status_transition_from_maintenance(
            project_id="legacy",
            tracker=tracker,
            issue=issue,
            requested_status="Needs Human",
            actor="watchdog",
            authority=TransitionAuthority.WATCHDOG,
            reason_code="watchdog.test_maintenance_departure",
            idempotency_key="watchdog-test-maintenance-departure",
            originating_job="watchdog-test",
        )

    assert outcome.disposition is TransitionDisposition.APPLIED
    prepare.assert_called_once()
    assert prepare.call_args.args[1].state == "In Validation"
    assert prepare.call_args.args[3] == "Needs Human"
    resolve_departure.assert_called_once()
    assert resolve_departure.call_args.args[-1] == "audit-departure-maintenance"
    assert tracker.issue.state == "Needs Human"


def test_stale_observation_cannot_overwrite_newer_status(tmp_path) -> None:
    tracker = _StatefulTracker(_issue())
    orchestrator = _orchestrator(tmp_path, tracker)
    stale = tracker.fetch_issue_detail("OOMPAH-TEST")
    assert stale is not None
    tracker.issue.state = "Needs Human"

    with pytest.raises(TaskTransitionNotApplied) as raised:
        orchestrator._transition_issue_status(
            stale,
            "In Progress",
            tracker=tracker,
            reason_code="dispatch.test_stale_observation",
            evidence_generation="generation-1",
        )

    assert raised.value.outcome.reason_code == "transition.stale_status"
    assert tracker.issue.state == "Needs Human"
    assert tracker.updates == []


def test_needs_human_transition_emits_diagnostic(tmp_path, caplog) -> None:
    tracker = _StatefulTracker(_issue())
    orchestrator = _orchestrator(tmp_path, tracker)

    with caplog.at_level("WARNING", logger="oompah.orchestrator"):
        outcome = orchestrator._transition_issue_status(
            tracker.fetch_issue_detail("OOMPAH-TEST"),
            "Needs Human",
            tracker=tracker,
            actor="external-actor",
            authority=TransitionAuthority.WATCHDOG,
            reason_code="watchdog.test_needs_human_diagnostic",
            originating_job="diagnostic-job",
            idempotency_key="diagnostic-key",
        )

    assert outcome.disposition is TransitionDisposition.APPLIED
    diagnostics = [
        record.getMessage()
        for record in caplog.records
        if "NEEDS_HUMAN transition diagnostic" in record.getMessage()
    ]
    assert len(diagnostics) == 1
    message = diagnostics[0]
    assert "task=OOMPAH-TEST" in message
    assert "actor=external-actor" in message
    assert "reason_code=watchdog.test_needs_human_diagnostic" in message
    assert "originating_job=diagnostic-job" in message
    assert "caller_stack:" in message


def test_non_needs_human_transition_has_no_diagnostic(tmp_path, caplog) -> None:
    tracker = _StatefulTracker(_issue())
    orchestrator = _orchestrator(tmp_path, tracker)

    with caplog.at_level("WARNING", logger="oompah.orchestrator"):
        orchestrator._transition_issue_status(
            tracker.fetch_issue_detail("OOMPAH-TEST"),
            "In Progress",
            tracker=tracker,
            reason_code="dispatch.test_no_diagnostic",
            evidence_generation="generation-1",
        )

    assert not [
        record
        for record in caplog.records
        if "NEEDS_HUMAN transition diagnostic" in record.getMessage()
    ]
