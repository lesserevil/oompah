"""Tests for oversized intake issue epic proposal generation (#284)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from oompah.epic_proposal import (
    EPIC_PROPOSAL_METADATA_KEY,
    apply_epic_proposal,
    ensure_epic_proposal,
    generate_epic_proposal,
)
from oompah.intake_schema import (
    DecompositionStatus,
    parse_intake_metadata,
    intake_to_raw,
)
from oompah.issue_validator import ScopeClassification, validate_issue
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.statuses import BACKLOG, DECOMPOSED, PROPOSED


def _oversized_description() -> str:
    return """
## Problem
The intake workflow needs a multi-phase overhaul that validates quality,
handles generated proposal approval, and decomposes oversized work before it
reaches the backlog.

## Desired Behavior
Oompah should keep broad requests in Proposed while it produces an actionable
epic and child-task breakdown for the requestor to approve.

## Acceptance Criteria
- Oversized proposed issues receive a concrete epic and child-task proposal.
- Approved decomposition creates child issues linked under the generated epic.
- Re-running intake reuses the existing child tasks for the same proposal.
- Generated tasks preserve the original requestor and source issue context.
""".strip()


def _source_issue(**overrides) -> Issue:
    defaults = {
        "id": "example-org/oompah#500",
        "identifier": "example-org/oompah#500",
        "title": "Build multi-phase intake decomposition workflow",
        "description": _oversized_description(),
        "priority": 0,
        "state": PROPOSED,
        "issue_type": "task",
        "labels": [],
        "url": "https://github.com/example-org/oompah/issues/500",
    }
    defaults.update(overrides)
    return Issue(**defaults)


class FakeTracker:
    def __init__(self, issues: list[Issue] | None = None):
        self.issues = {issue.identifier: issue for issue in (issues or [])}
        self.metadata: dict[str, dict[str, object]] = {}
        self.comments: list[tuple[str, str, str]] = []
        self.parent_links: list[tuple[str, str]] = []
        self.create_calls: list[dict[str, object]] = []
        self.update_calls: list[tuple[str, dict[str, object]]] = []
        self._next = 900

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return dict(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self.metadata.setdefault(identifier, {})[key] = value

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        self.comments.append((identifier, text, author))
        return {"author": author, "text": text}

    def create_issue(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
        initial_status: str | None = None,
        labels: list[str] | None = None,
        parent: str | None = None,
    ) -> Issue:
        identifier = f"example-org/oompah#{self._next}"
        self._next += 1
        issue = Issue(
            id=identifier,
            identifier=identifier,
            title=title,
            description=description,
            priority=priority,
            state=initial_status or "Backlog",
            issue_type=issue_type,
            labels=list(labels or []),
            parent_id=parent,
        )
        self.issues[identifier] = issue
        self.create_calls.append(
            {
                "identifier": identifier,
                "title": title,
                "issue_type": issue_type,
                "initial_status": initial_status,
                "parent": parent,
            }
        )
        return issue

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues.get(identifier)

    def update_issue(self, identifier: str, **fields: object) -> None:
        self.update_calls.append((identifier, dict(fields)))
        issue = self.issues[identifier]
        if "title" in fields:
            issue.title = str(fields["title"])
        if "description" in fields:
            issue.description = str(fields["description"])
        if "status" in fields:
            issue.state = str(fields["status"])

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        self.parent_links.append((child_id, parent_id))
        self.issues[child_id].parent_id = parent_id

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        return [issue for issue in self.issues.values() if issue.state in state_names]


def test_generate_epic_proposal_from_oversized_validator_result():
    source = _source_issue()
    validation = validate_issue(
        title=source.title,
        description=source.description,
        issue_type=source.issue_type,
        labels=source.labels,
    )

    assert validation.scope == ScopeClassification.EPIC_NEEDED

    proposal = generate_epic_proposal(
        source,
        validation_result=validation,
        requestor="alice",
    )

    assert proposal.epic_title.startswith("Epic:")
    assert len(proposal.fingerprint) == 64
    assert len(proposal.children) >= 3
    assert any("child" in child.title.lower() for child in proposal.children)
    assert all("example-org/oompah#500" in child.description for child in proposal.children)
    assert all("@alice" in child.description for child in proposal.children)


def test_ensure_epic_proposal_posts_once_and_records_intake_metadata():
    source = _source_issue()
    tracker = FakeTracker([source])

    first = ensure_epic_proposal(tracker, source, requestor="alice")
    second = ensure_epic_proposal(tracker, source, requestor="alice")

    assert first is not None
    assert second is not None
    assert first.created is True
    assert first.comment_posted is True
    assert second.duplicate_suppressed is True
    assert len(tracker.comments) == 1

    stored = tracker.metadata[source.identifier][EPIC_PROPOSAL_METADATA_KEY]
    assert isinstance(stored, dict)
    assert stored["fingerprint"] == first.proposal.fingerprint

    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    assert readiness.scope.value == "needs_decomposition"
    assert readiness.decomposition_status == DecompositionStatus.PROPOSED
    assert readiness.proposal_fingerprint == first.proposal.fingerprint


def test_ensure_epic_proposal_skips_existing_epic_children():
    source = _source_issue(parent_id="example-org/oompah#400")
    tracker = FakeTracker([source])

    result = ensure_epic_proposal(tracker, source, requestor="alice")

    assert result is None
    assert tracker.comments == []
    assert source.identifier not in tracker.metadata


def test_apply_accepted_proposal_creates_proposed_epic_and_linked_children():
    source = _source_issue()
    tracker = FakeTracker([source])
    ensured = ensure_epic_proposal(tracker, source, requestor="alice")
    assert ensured is not None

    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    readiness.decomposition_status = DecompositionStatus.ACCEPTED
    tracker.set_metadata_field(source.identifier, "oompah.intake", intake_to_raw(readiness))

    result = apply_epic_proposal(tracker, source)

    assert result.skipped_reason is None
    assert result.created_epic is True
    assert result.created_child_count == len(ensured.proposal.children)
    assert tracker.issues[source.identifier].state == DECOMPOSED
    assert result.epic_identifier is not None

    epic = tracker.issues[result.epic_identifier]
    assert epic.issue_type == "epic"
    assert epic.state == PROPOSED

    assert len(result.child_identifiers) == len(ensured.proposal.children)
    assert tracker.parent_links == [
        (child_id, result.epic_identifier)
        for child_id in result.child_identifiers
    ]
    for child_id in result.child_identifiers:
        child = tracker.issues[child_id]
        assert child.state == PROPOSED
        assert child.parent_id == result.epic_identifier
        assert "Source issue: example-org/oompah#500" in (child.description or "")
        assert "@alice" in (child.description or "")


def test_apply_same_proposal_does_not_duplicate_child_tasks():
    source = _source_issue()
    tracker = FakeTracker([source])
    ensure_epic_proposal(tracker, source, requestor="alice")
    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    readiness.decomposition_status = DecompositionStatus.ACCEPTED
    tracker.set_metadata_field(source.identifier, "oompah.intake", intake_to_raw(readiness))

    first = apply_epic_proposal(tracker, source)
    create_count = len(tracker.create_calls)
    second = apply_epic_proposal(tracker, source)

    assert first.created_child_count > 0
    assert second.duplicate_suppressed is True
    assert len(tracker.create_calls) == create_count
    assert second.child_identifiers == first.child_identifiers


def test_apply_changed_proposal_updates_existing_epic_and_children():
    source = _source_issue()
    tracker = FakeTracker([source])
    ensure_epic_proposal(tracker, source, requestor="alice")
    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    readiness.decomposition_status = DecompositionStatus.ACCEPTED
    tracker.set_metadata_field(source.identifier, "oompah.intake", intake_to_raw(readiness))
    first = apply_epic_proposal(tracker, source)
    create_count = len(tracker.create_calls)

    raw = dict(tracker.metadata[source.identifier][EPIC_PROPOSAL_METADATA_KEY])
    raw["fingerprint"] = "f" * 64
    raw["applied_fingerprint"] = first.proposal.fingerprint
    raw["epic_title"] = "Epic: Updated decomposition"
    raw["children"] = [
        {**child, "title": f"Updated {idx}"}
        for idx, child in enumerate(raw["children"], start=1)
    ]
    tracker.set_metadata_field(source.identifier, EPIC_PROPOSAL_METADATA_KEY, raw)
    readiness.proposal_fingerprint = "f" * 64
    tracker.set_metadata_field(source.identifier, "oompah.intake", intake_to_raw(readiness))

    updated = apply_epic_proposal(tracker, source)

    assert updated.created_epic is False
    assert updated.updated_child_count == len(first.child_identifiers)
    assert len(tracker.create_calls) == create_count
    assert tracker.issues[first.epic_identifier].title == "Epic: Updated decomposition"
    assert all(tracker.issues[child_id].title.startswith("Updated") for child_id in first.child_identifiers)


def test_orchestrator_processes_oversized_proposed_issues():
    source = _source_issue()
    tracker = FakeTracker([source])
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = []
    orch.tracker = tracker

    processed = orch._process_epic_proposals()

    assert processed == [source]
    assert len(tracker.comments) == 1
    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    assert readiness.decomposition_status == DecompositionStatus.PROPOSED
    assert orch._last_epic_proposal_metrics["processed_count"] == 1
    assert orch._last_epic_proposal_metrics["created_count"] == 1


def test_orchestrator_records_validation_guidance_for_small_proposed_bug():
    source = _source_issue(
        title="Detect stopped dispatch loop",
        description="""
## Problem
The HTTP server can stay alive while the orchestrator dispatch loop stops
ticking, so new open issues never dispatch.

## Expected Behavior
Oompah should detect the stale dispatch loop and recover or alert clearly.

## Acceptance Criteria
- The stale loop condition is detected.
- A regression test covers recovery from the stale loop condition.
""".strip(),
        issue_type="bug",
        requestor_login="alice",
    )
    tracker = FakeTracker([source])
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = []
    orch.tracker = tracker

    processed = orch._process_epic_proposals()

    assert processed == [source]
    assert tracker.comments == []

    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    assert set(readiness.missing_fields) == {
        "actual_behavior",
        "reproduction_steps",
    }
    assert readiness.last_validator_result is not None
    assert readiness.last_validator_result.value == "fail"
    assert orch._last_epic_proposal_metrics["processed_count"] == 1
    assert orch._last_epic_proposal_metrics["created_count"] == 0
    assert orch._last_epic_proposal_metrics["comment_posted_count"] == 0
    assert orch._last_epic_proposal_metrics["promoted_count"] == 0


def test_orchestrator_promotes_valid_small_proposed_issue_without_comment():
    source = _source_issue(
        title="Add managed-project issue template refresh workflow",
        description="""
## Problem
Oompah-managed projects need a first-class way to keep GitHub issue templates
aligned with the current canonical templates shipped by oompah.

## Desired Behavior
Oompah should expose a project-level workflow that lets an operator inspect
and update a managed project's issue templates to the latest canonical
oompah templates.

## Acceptance Criteria
- Each GitHub-Issues-backed managed project can report whether its issue
  templates match the latest canonical oompah templates.
- Applying updates writes the canonical templates without touching unrelated
  files.
""".strip(),
        issue_type="feature",
        requestor_login="alice",
    )
    tracker = FakeTracker([source])
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = []
    orch.tracker = tracker

    processed = orch._process_epic_proposals()

    assert processed == [source]
    assert tracker.issues[source.identifier].state == BACKLOG
    assert tracker.comments == []

    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    assert readiness.is_ready is True
    assert readiness.requestor_approved is False
    assert orch._last_epic_proposal_metrics["processed_count"] == 1
    assert orch._last_epic_proposal_metrics["created_count"] == 0
    assert orch._last_epic_proposal_metrics["comment_posted_count"] == 0
    assert orch._last_epic_proposal_metrics["promoted_count"] == 1


def test_orchestrator_respects_project_intake_auto_promote_false():
    source = _source_issue(
        title="Add managed-project issue template refresh workflow",
        description="""
## Problem
Oompah-managed projects need a first-class way to keep GitHub issue templates
aligned with the current canonical templates shipped by oompah.

## Desired Behavior
Oompah should expose a project-level workflow that lets an operator inspect
and update a managed project's issue templates to the latest canonical
oompah templates.

## Acceptance Criteria
- Each GitHub-Issues-backed managed project can report whether its issue
  templates match the latest canonical oompah templates.
- Applying updates writes the canonical templates without touching unrelated
  files.
""".strip(),
        issue_type="feature",
        requestor_login="alice",
        project_id="proj",
    )
    tracker = FakeTracker([source])
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = []
    orch.project_store.get.return_value = SimpleNamespace(intake_auto_promote=False)
    orch.tracker = tracker
    orch._tracker_for_project = MagicMock(return_value=tracker)

    processed = orch._process_epic_proposals()

    assert processed == [source]
    assert tracker.issues[source.identifier].state == PROPOSED
    assert tracker.comments == []

    readiness = parse_intake_metadata(tracker.metadata[source.identifier]["oompah.intake"])
    assert readiness.is_ready is True
    assert orch._last_epic_proposal_metrics["processed_count"] == 1
    assert orch._last_epic_proposal_metrics["promoted_count"] == 0
