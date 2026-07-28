"""Startup persistence and recovery tests for terminal-audit enforcement."""

from __future__ import annotations

import json
import logging

from oompah.models import Issue
from oompah.config import ServiceConfig
from oompah.orchestrator import Orchestrator
from oompah.terminal_audit import (
    AuditAttempt,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    compute_evidence_fingerprint,
)
from oompah.terminal_audit_enforcement import (
    SERVICE_STATE_KEY,
    TerminalAuditEnforcement,
)
from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata


class _LockStore:
    class _Lock:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def project_write_lock(self, _project_id):
        return self._Lock()


class _Tracker:
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        self.metadata: dict[str, dict[str, object]] = {}
        self.set_calls = 0

    def fetch_all_issues_enriched(self):
        return list(self.issues)

    def get_metadata(self, identifier: str):
        return dict(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object):
        self.set_calls += 1
        self.metadata.setdefault(identifier, {})[key] = value


def _issue(identifier: str, state: str, evidence: str, project: str | None = None) -> Issue:
    issue = Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="requirements",
        state=state,
        project_id=project,
    )
    # Adapters may expose a precomputed evidence fingerprint.  The
    # enforcement layer accepts this useful narrow contract without requiring
    # every tracker to duplicate the domain fingerprint calculation.
    issue.evidence_fingerprint = evidence  # type: ignore[attr-defined]
    return issue


def _enforcer(tmp_path, *, terminal_states=("Done",)):
    return TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=terminal_states,
        project_store=_LockStore(),
    )


def test_first_startup_snapshots_existing_terminal_tasks_and_second_reuses_it(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    enforcer = _enforcer(tmp_path)

    first = enforcer.initialize([("project-a", tracker)])
    assert first["first_startup"] is True
    assert first["pending_audits"] == 0
    assert len(enforcer.state.grandfathered) == 1

    persisted = json.loads((tmp_path / "service_state.json").read_text())
    record = persisted[SERVICE_STATE_KEY]
    assert record["version"] == 1
    assert record["grandfathered"][0]["project_id"] == "project-a"
    assert record["grandfathered"][0]["task_id"] == "TASK-1"
    assert record["grandfathered"][0]["terminal_state"] == "Done"

    second = _enforcer(tmp_path).initialize([("project-a", tracker)])
    assert second["first_startup"] is False
    assert second["pending_audits"] == 0
    assert second["grandfathered"] == 1


def test_evidence_change_requires_one_fresh_audit_and_deduplicates_restart(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    _enforcer(tmp_path).initialize([("project-a", tracker)])

    tracker.issues[0].evidence_fingerprint = "evidence-b"  # type: ignore[attr-defined]
    restarted = _enforcer(tmp_path)
    result = restarted.initialize([("project-a", tracker)])
    assert result["pending_audits"] == 1
    first_audit_id = restarted.pending_audits[0].audit_id

    second = _enforcer(tmp_path)
    result = second.initialize([("project-a", tracker)])
    assert result["pending_audits"] == 1
    assert len({entry.audit_id for entry in second.pending_audits}) == 1
    assert second.state.pending_audits[0].audit_id == first_audit_id


def test_terminal_to_nonterminal_to_terminal_is_not_grandfathered(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    _enforcer(tmp_path).initialize([("project-a", tracker)])

    tracker.issues[0].state = "Open"
    observed_nonterminal = _enforcer(tmp_path).initialize([("project-a", tracker)])
    assert observed_nonterminal["grandfathered"] == 0
    assert observed_nonterminal["pending_audits"] == 0

    tracker.issues[0].state = "Done"
    reentered = _enforcer(tmp_path).initialize([("project-a", tracker)])
    assert reentered["pending_audits"] == 1
    assert reentered["grandfathered"] == 0


def test_pending_validation_metadata_recovers_without_writing_or_duplicating_attempts(
    tmp_path,
):
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
    fingerprint = compute_evidence_fingerprint(
        requirements_text="requirements",
        project_id="project-a",
        task_id="TASK-1",
    )
    attempt = AuditAttempt(
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
    }

    enforcer = _enforcer(tmp_path)
    enforcer.initialize([("project-a", tracker)])
    assert [(item.audit_id, item.attempt_ids) for item in enforcer.pending_audits] == [
        ("audit-1", ["attempt-1"])
    ]
    assert tracker.set_calls == 0

    restarted = _enforcer(tmp_path)
    restarted.initialize([("project-a", tracker)])
    assert [(item.audit_id, item.attempt_ids) for item in restarted.pending_audits] == [
        ("audit-1", ["attempt-1"])
    ]
    assert tracker.set_calls == 0


def test_corrupt_service_state_fails_closed_and_is_observable(tmp_path, caplog):
    state_path = tmp_path / "service_state.json"
    state_path.write_text("not-json")
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    enforcer = _enforcer(tmp_path)

    with caplog.at_level(logging.ERROR, logger="oompah.terminal_audit_enforcement"):
        result = enforcer.initialize([("project-a", tracker)])

    assert result["quarantined"] is True
    assert result["pending_audits"] == 1
    assert "service_state_corrupt" in result["errors"]
    assert any("service_state_corrupt" in record.message for record in caplog.records)
    assert state_path.read_text() == "not-json"


def test_corrupt_enforcement_entry_is_replaced_with_quarantine_record(tmp_path, caplog):
    state_path = tmp_path / "service_state.json"
    state_path.write_text(json.dumps({SERVICE_STATE_KEY: {"version": 999}}))
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])

    with caplog.at_level(logging.ERROR, logger="oompah.terminal_audit_enforcement"):
        result = _enforcer(tmp_path).initialize([("project-a", tracker)])

    assert result["quarantined"] is True
    assert result["pending_audits"] == 1
    persisted = json.loads(state_path.read_text())[SERVICE_STATE_KEY]
    assert persisted["version"] == 1
    assert persisted["quarantined"] is True
    assert any("terminal_audit_enforcement_corrupt" in record.message for record in caplog.records)


def test_legacy_service_state_without_enforcement_is_initialized(tmp_path):
    state_path = tmp_path / "service_state.json"
    state_path.write_text(json.dumps({"paused": True, "future": {"keep": True}}))
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])

    result = _enforcer(tmp_path).initialize([("project-a", tracker)])
    persisted = json.loads(state_path.read_text())
    assert result["first_startup"] is True
    assert persisted["paused"] is True
    assert persisted["future"] == {"keep": True}
    assert SERVICE_STATE_KEY in persisted


def test_overlapping_task_ids_are_scoped_by_project(tmp_path):
    tracker_a = _Tracker([_issue("TASK-1", "Done", "same")])
    tracker_b = _Tracker([_issue("TASK-1", "Done", "same")])
    enforcer = _enforcer(tmp_path)
    result = enforcer.initialize([("project-a", tracker_a), ("project-b", tracker_b)])
    assert result["grandfathered"] == 2
    assert {entry.project_id for entry in enforcer.state.grandfathered} == {
        "project-a",
        "project-b",
    }


def test_malformed_validation_metadata_is_quarantined_and_observable(tmp_path, caplog):
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
    tracker.metadata["TASK-1"] = {METADATA_KEY: {"version": 999}}

    with caplog.at_level(logging.ERROR, logger="oompah.terminal_audit_enforcement"):
        result = _enforcer(tmp_path).initialize([("project-a", tracker)])

    assert result["pending_audits"] == 0
    assert any("metadata_quarantined" in record.message for record in caplog.records)
    assert tracker.metadata["TASK-1"][METADATA_KEY]["quarantine"]


def test_mark_audit_passed_reestablishes_grandfather_baseline(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    _enforcer(tmp_path).initialize([("project-a", tracker)])
    tracker.issues[0].evidence_fingerprint = "evidence-b"  # type: ignore[attr-defined]
    enforcer = _enforcer(tmp_path)
    enforcer.initialize([("project-a", tracker)])
    assert len(enforcer.pending_audits) == 1

    enforcer.mark_audit_passed("project-a", tracker.issues[0], "evidence-b")
    restarted = _enforcer(tmp_path)
    result = restarted.initialize([("project-a", tracker)])
    assert result["pending_audits"] == 0
    assert result["grandfathered"] == 1


def test_orchestrator_runs_enforcement_before_dispatch_startup(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    orchestrator._terminal_audit_scopes = lambda: [("project-a", tracker)]

    orchestrator._run_terminal_audit_enforcement()

    state = json.loads((tmp_path / "service_state.json").read_text())
    assert state[SERVICE_STATE_KEY]["grandfathered"][0]["task_id"] == "TASK-1"
    assert orchestrator._maintenance_status["terminal_audit_enforcement"][
        "baseline_initialized"
    ] is True
