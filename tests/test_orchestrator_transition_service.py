"""Contract coverage for the orchestrator's single status-writer boundary."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator, TaskTransitionNotApplied
from oompah.task_transition_service import TransitionDisposition, TransitionPhase


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
