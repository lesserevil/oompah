"""Behavioural dashboard contracts for the canonical WorkDecision view."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    LandingFact,
    LandingState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)


def _dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html"
    ).read_text(encoding="utf-8")


def _extract_function(name: str) -> str:
    source = _dashboard()
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"dashboard function {name} was not found"
    depth = 0
    for index in range(match.start(), len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"dashboard function {name} was not terminated")


def _run_javascript(functions: tuple[str, ...], body: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for dashboard behaviour tests")
    source = "\n".join(_extract_function(name) for name in functions)
    completed = subprocess.run(
        [node, "-e", source + "\n" + body],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


_FAKE_DOCUMENT = r"""
const document = {
  activeElement: null,
  createElement: function() {
    let encoded = '';
    const editElement = {
      dataset: {}, style: {}, textContent: '',
      addEventListener: function() {}, blur: function() {},
    };
    return {
      className: '', draggable: false, dataset: {}, style: {},
      classList: {add: function() {}, remove: function() {}},
      addEventListener: function() {},
      querySelector: function(selector) {
        return selector === '.card-title' || selector === '.card-desc'
          ? editElement : null;
      },
      set textContent(value) {
        encoded = String(value)
          .replace(/&/g, '&amp;').replace(/</g, '&lt;')
          .replace(/>/g, '&gt;').replace(/\"/g, '&quot;')
          .replace(/'/g, '&#39;');
      },
      get innerHTML() { return encoded; },
      set innerHTML(value) { encoded = String(value); },
    };
  },
};
"""


def _done_facts(issue: Issue) -> WorkflowFacts:
    observed_at = datetime(2026, 8, 6, tzinfo=timezone.utc).isoformat()
    observations = {
        domain: FactObservation.missing(
            domain, observed_at=observed_at, source="dashboard-e2e"
        )
        for domain in REQUIRED_FACT_DOMAINS
    }
    observations.update(
        {
            FactDomain.TASK: FactObservation.known(
                FactDomain.TASK,
                {
                    "identifier": issue.identifier,
                    "project_id": issue.project_id,
                    "status": issue.state,
                    "issue_type": issue.issue_type,
                    "parent_id": issue.parent_id,
                },
                observed_at=observed_at,
                source="dashboard-e2e",
            ),
            FactDomain.DEPENDENCIES: FactObservation.known(
                FactDomain.DEPENDENCIES,
                {"finish": [], "hard_start": []},
                observed_at=observed_at,
                source="dashboard-e2e",
            ),
            FactDomain.CONTAINMENT: FactObservation.known(
                FactDomain.CONTAINMENT,
                {"parent_id": issue.parent_id, "children": []},
                observed_at=observed_at,
                source="dashboard-e2e",
            ),
            FactDomain.RETRY_BUDGET: FactObservation.known(
                FactDomain.RETRY_BUDGET,
                {"remaining": 3},
                observed_at=observed_at,
                source="dashboard-e2e",
            ),
            FactDomain.CONFIG: FactObservation.known(
                FactDomain.CONFIG,
                {"version": 1},
                observed_at=observed_at,
                source="dashboard-e2e",
            ),
        }
    )
    landing = LandingFact(
        "task-branch",
        "epic-parent",
        "a" * 40,
        {"kind": LandingState.NOT_LANDED.value},
        observed_at,
        str(issue.project_id),
        state=LandingState.NOT_LANDED,
        durable=False,
        error_code=None,
    )
    observations[FactDomain.LANDING] = FactObservation.known(
        FactDomain.LANDING,
        {"evidence_revisions": [landing.evidence_revision]},
        observed_at=observed_at,
        source="dashboard-e2e",
    )
    return WorkflowFacts(
        str(issue.project_id),
        issue.identifier,
        observed_at,
        observations,
        landings=(landing,),
    )


def test_state_projection_revises_board_rows_by_project_and_removes_stale_values() -> None:
    result = _run_javascript(
        ("workDecisionTaskKey", "applyWorkDecisionProjectionToData"),
        r"""
const data = {
  Open: [
    {project_id: 'project-a', identifier: 'TASK-1', work_decision: {decision_revision: 'old-a'}},
    {project_id: 'project-b', identifier: 'TASK-1', work_decision: {decision_revision: 'old-b'}},
    {project_id: 'project-a', identifier: 'TASK-2', work_decision: {decision_revision: 'terminal'}},
  ],
};
const projection = {items: [
  {project_id: 'project-a', task_id: 'TASK-1', decision_revision: 'new-a', reason_text: 'A'},
  {project_id: 'project-b', task_id: 'TASK-1', decision_revision: 'new-b', reason_text: 'B'},
]};
const firstChanged = applyWorkDecisionProjectionToData(data, projection);
const secondChanged = applyWorkDecisionProjectionToData(data, projection);
console.log(JSON.stringify({
  firstChanged, secondChanged,
  reasons: data.Open.map(issue => issue.work_decision && issue.work_decision.reason_text),
  hasRemovedDecision: Object.prototype.hasOwnProperty.call(data.Open[2], 'work_decision'),
}));
""",
    )

    assert result == {
        "firstChanged": True,
        "secondChanged": False,
        "reasons": ["A", "B", None],
        "hasRemovedDecision": False,
    }


def test_bounded_scan_omission_removes_stale_decision_and_renders_pending_state() -> None:
    result = _run_javascript(
        (
            "workDecisionTaskKey",
            "applyWorkDecisionProjectionToData",
            "esc",
            "renderWorkDecisionSummary",
            "renderWorkDecisionAvailability",
            "renderIntegrationSummary",
            "createCard",
        ),
        _FAKE_DOCUMENT
        + r"""
const data = {Open: [{
  project_id: 'project-a', identifier: 'TASK-OMITTED', state: 'Open',
  title: 'Omitted task', description: '', priority: 2,
  work_decision: {decision_revision: 'stale', reason_text: 'Ready'},
  work_decision_availability: 'available',
}]};
const projection = {
  source: 'controller', availability: 'incomplete', items: [],
  incomplete_projects: ['project-a'],
  incomplete_tasks: [{project_id: 'project-a', task_id: 'TASK-OMITTED'}],
};
function columnKeyForStatus(value) { return value; }
function getEpicById() { return null; }
function renderCardOwnerClaim() { return ''; }
function getTypeIcon() { return 'T'; }
function issueDisplayIdentifier(issue) { return issue.identifier; }
function renderCardIntakeSummary() { return ''; }
function renderDuplicateScreeningSummary() { return ''; }
function renderCardTerminalAuditSummary() { return ''; }
function renderCardAttachments() { return ''; }
const changed = applyWorkDecisionProjectionToData(data, projection);
const issue = data.Open[0];
const html = createCard(issue).innerHTML;
console.log(JSON.stringify({
  changed, availability: issue.work_decision_availability,
  hasDecision: Object.prototype.hasOwnProperty.call(issue, 'work_decision'), html,
}));
""",
    )

    assert result["changed"] is True
    assert result["availability"] == "incomplete"
    assert result["hasDecision"] is False
    assert "pending a bounded rotating or reconciliation pass" in result["html"]
    assert "Ready" not in result["html"]


def test_projection_overlay_fails_closed_for_new_omissions_disabled_and_legacy() -> None:
    result = _run_javascript(
        ("workDecisionTaskKey", "applyWorkDecisionProjectionToData"),
        r"""
const sourceBearing = {source: 'controller', availability: 'ready', items: []};
const newerIssues = {Open: [{
  project_id: 'project-a', identifier: 'TASK-NEW', state: 'Open',
  work_decision_availability: 'available',
}]};
applyWorkDecisionProjectionToData(newerIssues, sourceBearing);

const disabledIssues = {Open: [{
  project_id: 'project-a', identifier: 'TASK-OFF', state: 'Open',
  work_decision: {decision_revision: 'stale'},
}]};
applyWorkDecisionProjectionToData(
  disabledIssues,
  {source: null, availability: 'disabled', items: []}
);

const legacyIssues = {Open: [{
  project_id: null, identifier: 'TASK-LEGACY', state: 'Open',
}]};
applyWorkDecisionProjectionToData(legacyIssues, {
  source: 'shadow', availability: 'ready',
  items: [{
    project_id: 'legacy', task_id: 'TASK-LEGACY',
    decision_revision: 'legacy-v1',
  }],
});

const legacyUnavailable = {Open: [{
  project_id: '', identifier: 'TASK-MISSING', state: 'Open',
}]};
applyWorkDecisionProjectionToData(legacyUnavailable, {
  source: 'controller', availability: 'partial', items: [],
  unavailable_projects: [null],
});
console.log(JSON.stringify({
  newerAvailability: newerIssues.Open[0].work_decision_availability,
  disabledAvailability: disabledIssues.Open[0].work_decision_availability,
  disabledHasDecision: Object.prototype.hasOwnProperty.call(
    disabledIssues.Open[0], 'work_decision'
  ),
  legacyRevision: legacyIssues.Open[0].work_decision.decision_revision,
  legacyAvailability: legacyIssues.Open[0].work_decision_availability,
  legacyMissingAvailability: legacyUnavailable.Open[0].work_decision_availability,
}));
""",
    )

    assert result == {
        "newerAvailability": "unavailable",
        "disabledAvailability": "disabled",
        "disabledHasDecision": False,
        "legacyRevision": "legacy-v1",
        "legacyAvailability": "available",
        "legacyMissingAvailability": "unavailable",
    }


def test_done_row_receives_and_renders_canonical_decision() -> None:
    result = _run_javascript(
        (
            "workDecisionTaskKey",
            "applyWorkDecisionProjectionToData",
            "esc",
            "renderWorkDecisionSummary",
            "renderWorkDecisionAvailability",
            "renderIntegrationSummary",
            "createCard",
        ),
        _FAKE_DOCUMENT
        + r"""
const data = {Done: [{
  project_id: 'project-a', identifier: 'TASK-DONE', state: 'Done',
  title: 'Done task', description: 'Awaiting landing', priority: 2,
}]};
const decision = {
  project_id: 'project-a', task_id: 'TASK-DONE', status: 'Done',
  decision_revision: 'done-v1', reason_code: 'landing.waiting',
  reason_text: 'Waiting for landing', owner: 'rollup',
  disposition: 'blocked', prerequisites: [], action_required: false,
};
function columnKeyForStatus(value) { return value; }
function renderCardOwnerClaim() { return ''; }
function getTypeIcon() { return 'T'; }
function issueDisplayIdentifier(issue) { return issue.identifier; }
function renderCardIntakeSummary() { return ''; }
function renderDuplicateScreeningSummary() { return ''; }
function renderCardTerminalAuditSummary() { return ''; }
function renderCardAttachments() { return ''; }
const changed = applyWorkDecisionProjectionToData(data, {items: [decision]});
const html = createCard(data.Done[0]).innerHTML;
console.log(JSON.stringify({
  changed,
  status: data.Done[0].work_decision.status,
  revision: data.Done[0].work_decision.decision_revision,
  html,
}));
""",
    )

    assert result["changed"] is True
    assert result["status"] == "Done"
    assert result["revision"] == "done-v1"
    assert "Waiting for landing" in result["html"]
    assert "rollup" in result["html"]


def test_real_controller_done_decision_reaches_snapshot_api_board_and_dashboard(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ServiceConfig(workspace_root=str(tmp_path / "workspace"))
    config.workflow_engine_mode = "enforce"
    orchestrator = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    done = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done awaiting landing",
        description="Awaiting the epic branch landing",
        state="Done",
        priority=2,
        project_id="project-a",
        parent_id="EPIC-1",
        target_branch="epic-parent",
    )
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = [done]
    tracker.fetch_issue_detail.return_value = done
    project = SimpleNamespace(
        id="project-a",
        to_safe_dict=lambda: {"id": "project-a"},
    )
    orchestrator.project_store = MagicMock()
    orchestrator.project_store.list_all.return_value = [project]
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._collect_universal_workflow_facts = MagicMock(
        return_value=_done_facts(done)
    )
    orchestrator.workflow_controller._clock = lambda: datetime(
        2026, 8, 6, tzinfo=timezone.utc
    )
    orchestrator._notify_observers = MagicMock()

    sweep = orchestrator._run_workflow_controller_sweep()
    snapshot = orchestrator.get_snapshot()["work_decision_projection"]
    board = server_module._serialize_issues(orchestrator, [done])
    row = board["Done"][0]

    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orchestrator)
    monkeypatch.setattr(server_module, "_get_tracker", lambda *_args: tracker)
    monkeypatch.setattr(server_module, "_http_credentials", None)
    response = TestClient(
        server_module.app, raise_server_exceptions=False
    ).get("/api/v1/projects/project-a/tasks/TASK-DONE/work-decision")

    rendered = _run_javascript(
        (
            "esc",
            "renderWorkDecisionSummary",
            "renderWorkDecisionAvailability",
            "renderIntegrationSummary",
            "createCard",
        ),
        _FAKE_DOCUMENT
        + "\nconst issue = "
        + json.dumps(row)
        + r""";
function columnKeyForStatus(value) { return value; }
function getEpicById() { return null; }
function renderCardOwnerClaim() { return ''; }
function getTypeIcon() { return 'T'; }
function issueDisplayIdentifier(issue) { return issue.identifier; }
function renderCardIntakeSummary() { return ''; }
function renderDuplicateScreeningSummary() { return ''; }
function renderCardTerminalAuditSummary() { return ''; }
function renderCardAttachments() { return ''; }
const html = createCard(issue).innerHTML;
console.log(JSON.stringify({html}));
""",
    )

    assert sweep["evaluated"] == 1
    assert sweep["truncated"] is False
    assert snapshot["availability"] == "ready"
    assert snapshot["complete"] is True
    assert snapshot["items"] == [row["work_decision"]]
    assert row["work_decision_availability"] == "available"
    assert response.status_code == 200
    assert response.json() == {"work_decision": row["work_decision"]}
    assert row["work_decision"]["status"] == "Done"
    assert row["work_decision"]["reason_code"] == "landing.waiting"
    assert "Completed work is waiting for target-branch landing or rollup" in rendered[
        "html"
    ]
    assert "rollup" in rendered["html"]


def test_queue_rendering_uses_decision_reason_owner_and_action_not_legacy_heuristics() -> None:
    result = _run_javascript(
        ("esc", "renderIntegrationSummary"),
        _FAKE_DOCUMENT
        + r"""
const html = renderIntegrationSummary(
  null,
  {state: 'retry_wait', wait_reason: '<legacy wait>', last_error: 'legacy error',
   repair_action: 'legacy repair', attempts: 2},
  {reason_text: '<canonical reason>', owner: 'integrator', recovery_action: 'retry safely'}
);
console.log(JSON.stringify({html}));
""",
    )
    html = result["html"]
    assert "legacy wait" not in html
    assert "legacy error" not in html
    assert "legacy repair" not in html
    assert "&lt;canonical reason&gt;" in html
    assert "integrator" in html
    assert "retry safely" in html


def test_compact_decision_renderer_is_accessible_and_escapes_values() -> None:
    result = _run_javascript(
        ("esc", "renderWorkDecisionSummary"),
        _FAKE_DOCUMENT
        + r"""
const html = renderWorkDecisionSummary({
  reason_text: '<script>bad()</script>', owner: 'operator" onclick="bad()',
  disposition: 'action_required', recovery_action: '<repair>',
  prerequisites: [{subject: '<credential>'}], action_required: true,
}, true);
console.log(JSON.stringify({html}));
""",
    )
    html = result["html"]
    assert 'class="work-decision-chip"' in html
    assert 'role="note"' in html
    assert "work-decision-summary" not in html
    assert "<script>" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "&lt;repair&gt;" in html
    assert "&lt;credential&gt;" in html
    assert 'onclick="bad()' not in html


def test_task_card_uses_compact_decision_without_spurious_integration_row() -> None:
    result = _run_javascript(
        (
            "esc",
            "renderWorkDecisionSummary",
            "renderWorkDecisionAvailability",
            "renderIntegrationSummary",
            "createCard",
        ),
        _FAKE_DOCUMENT
        + r"""
function columnKeyForStatus(value) { return value; }
function renderCardOwnerClaim() { return ''; }
function getTypeIcon() { return 'T'; }
function issueDisplayIdentifier(issue) { return issue.identifier; }
function renderCardIntakeSummary() { return ''; }
function renderDuplicateScreeningSummary() { return ''; }
function renderCardTerminalAuditSummary() { return ''; }
function renderCardAttachments() { return ''; }
const card = createCard({
  identifier: 'TASK-1', project_id: 'project-a', state: 'Open',
  title: 'Task', description: 'Description', priority: 2,
  work_decision: {
    reason_text: 'Waiting for capacity', owner: 'dispatcher',
    disposition: 'retry_scheduled', prerequisites: [],
  },
});
console.log(JSON.stringify({html: card.innerHTML}));
""",
    )
    html = result["html"]
    assert 'class="work-decision-chip"' in html
    assert "work-decision-summary" not in html
    assert "Integration:" not in html


def test_duplicate_identifiers_have_project_scoped_card_dom_cache_entries() -> None:
    result = _run_javascript(
        ("workDecisionTaskKey", "getOrCreateCard"),
        r"""
const _cardElementCache = new Map();
let created = 0;
function issueFingerprint(issue) {
  return JSON.stringify({project_id: issue.project_id, identifier: issue.identifier,
    title: issue.title});
}
function createCard(issue) {
  created += 1;
  return {projectId: issue.project_id, serial: created};
}
const a = {project_id: 'project-a', identifier: 'TASK-1', title: 'A'};
const b = {project_id: 'project-b', identifier: 'TASK-1', title: 'B'};
const firstA = getOrCreateCard(a);
const firstB = getOrCreateCard(b);
const secondA = getOrCreateCard(a);
console.log(JSON.stringify({
  created,
  distinctProjects: firstA !== firstB,
  reusedWithinProject: firstA === secondA,
  keys: Array.from(_cardElementCache.keys()).sort(),
}));
""",
    )

    assert result == {
        "created": 2,
        "distinctProjects": True,
        "reusedWithinProject": True,
        "keys": ["project-a::TASK-1", "project-b::TASK-1"],
    }


def test_duplicate_identifier_detail_refresh_keeps_open_project_identity() -> None:
    result = _run_javascript(
        ("refreshOpenDetailPanel",),
        r"""
let _openDetailIdentifier = 'TASK-1';
let _openDetailProjectId = 'project-b';
let _detailRefreshTimer = null;
const calls = [];
const panel = {classList: {contains: value => value === 'open'}};
const document = {
  activeElement: null,
  getElementById: id => id === 'detail-panel' ? panel : null,
};
function clearTimeout() {}
function setTimeout(callback) { callback(); return 1; }
function openDetailPanel(identifier, projectId) { calls.push([identifier, projectId]); }
refreshOpenDetailPanel();
console.log(JSON.stringify({calls}));
""",
    )

    assert result == {"calls": [["TASK-1", "project-b"]]}


def test_open_detail_identity_rejects_same_identifier_from_other_project() -> None:
    result = _run_javascript(
        ("workDecisionTaskKey", "openDetailIdentityMatches"),
        r"""
let _openDetailIdentifier = 'TASK-1';
let _openDetailProjectId = 'project-b';
console.log(JSON.stringify({
  sameProject: openDetailIdentityMatches('TASK-1', 'project-b'),
  otherProject: openDetailIdentityMatches('TASK-1', 'project-a'),
}));
""",
    )

    assert result == {"sameProject": True, "otherProject": False}
