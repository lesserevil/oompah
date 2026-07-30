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


def test_orchestrator_terminal_audit_merge_preserves_unrelated_state(tmp_path):
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps({"future": {"keep": True}, "paused": True}),
        encoding="utf-8",
    )
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    orchestrator._terminal_audit_scopes = lambda: [("project-a", tracker)]

    orchestrator._run_terminal_audit_enforcement()

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["future"] == {"keep": True}
    assert persisted["paused"] is True
    assert persisted[SERVICE_STATE_KEY]["baseline_initialized"] is True


def test_new_orchestrator_recovers_after_operator_repairs_corrupt_state(tmp_path):
    state_path = tmp_path / "service_state.json"
    state_path.write_text("not-json", encoding="utf-8")
    damaged = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "damaged-workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    assert damaged._state_load_failed is True

    # A graceful restart after the operator restores a valid document creates
    # a new orchestrator with no process-local corruption marker.
    state_path.write_text("{}\n", encoding="utf-8")
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    restarted = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "restarted-workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    restarted._terminal_audit_scopes = lambda: [("project-a", tracker)]

    restarted._run_terminal_audit_enforcement()

    result = restarted._maintenance_status["terminal_audit_enforcement"]
    assert result["baseline_initialized"] is True
    assert result["quarantined"] is False
    assert result["errors"] == []


# Recovery tests for pending audit backlog
class TestAuditBacklogRecovery:
    """Test idempotent recovery of pending audit backlog."""

    def test_multi_request_audit_chain_deduplicates_on_recovery(self, tmp_path):
        """Multiple pending records in the same chain are deduplicated."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
        fingerprint_a = compute_evidence_fingerprint(
            requirements_text="requirements v1", project_id="project-a", task_id="TASK-1"
        )
        fingerprint_b = compute_evidence_fingerprint(
            requirements_text="requirements v2", project_id="project-a", task_id="TASK-1"
        )
        
        # Create two pending records in the chain (different fingerprints)
        attempt_1 = AuditAttempt(
            attempt_id="attempt-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_a,
            request_state=RequestState.PENDING,
        )
        attempt_2 = AuditAttempt(
            attempt_id="attempt-2",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_b,
            request_state=RequestState.PENDING,
        )
        
        record_1 = TerminalAuditRecord(
            audit_id="audit-1",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_a,
            request_state=RequestState.PENDING,
            attempts=[attempt_1],
        )
        record_2 = TerminalAuditRecord(
            audit_id="audit-2",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_b,
            request_state=RequestState.PENDING,
            attempts=[attempt_2],
        )
        
        tracker.metadata["TASK-1"] = {
            METADATA_KEY: TerminalAuditMetadata(pending_chain=[record_1, record_2]).to_dict()
        }

        enforcer = _enforcer(tmp_path)
        enforcer.initialize([("project-a", tracker)])
        
        # Both audits should be recovered
        assert len(enforcer.pending_audits) == 2
        audit_ids = {item.audit_id for item in enforcer.pending_audits}
        assert audit_ids == {"audit-1", "audit-2"}
        
        # Recovery is idempotent: repeated pass doesn't duplicate
        restarted = _enforcer(tmp_path)
        restarted.initialize([("project-a", tracker)])
        assert len(restarted.pending_audits) == 2
        assert {item.audit_id for item in restarted.pending_audits} == {"audit-1", "audit-2"}

    def test_stale_fingerprint_superseded_record_not_requeued(self, tmp_path):
        """Superseded records with old evidence are not requeued."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-b")])
        fingerprint_a = compute_evidence_fingerprint(
            requirements_text="requirements", project_id="project-a", task_id="TASK-1"
        )
        fingerprint_b = compute_evidence_fingerprint(
            requirements_text="requirements updated", project_id="project-a", task_id="TASK-1"
        )
        
        # First record is superseded (old evidence)
        record_old = TerminalAuditRecord(
            audit_id="audit-old",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_a,
            request_state=RequestState.SUPERSEDED,
            attempts=[],
        )
        
        # Second record is pending with new evidence
        attempt_new = AuditAttempt(
            attempt_id="attempt-new",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_b,
            request_state=RequestState.PENDING,
        )
        record_new = TerminalAuditRecord(
            audit_id="audit-new",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_b,
            request_state=RequestState.PENDING,
            attempts=[attempt_new],
        )
        
        tracker.metadata["TASK-1"] = {
            METADATA_KEY: TerminalAuditMetadata(pending_chain=[record_old, record_new]).to_dict()
        }

        enforcer = _enforcer(tmp_path)
        enforcer.initialize([("project-a", tracker)])
        
        # Only the new audit should be recovered
        assert len(enforcer.pending_audits) == 1
        assert enforcer.pending_audits[0].audit_id == "audit-new"

    def test_completed_audit_leaves_no_pending(self, tmp_path):
        """A task with only completed audits has zero pending audits."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
        fingerprint_a = compute_evidence_fingerprint(
            requirements_text="requirements", project_id="project-a", task_id="TASK-1"
        )
        
        # Record is already completed
        attempt_completed = AuditAttempt(
            attempt_id="attempt-done",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_a,
            request_state=RequestState.COMPLETED,
            verdict="pass",
        )
        record_done = TerminalAuditRecord(
            audit_id="audit-done",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint_a,
            request_state=RequestState.COMPLETED,
            attempts=[attempt_completed],
        )
        
        tracker.metadata["TASK-1"] = {
            METADATA_KEY: TerminalAuditMetadata(pending_chain=[record_done]).to_dict()
        }

        enforcer = _enforcer(tmp_path)
        enforcer.initialize([("project-a", tracker)])
        
        # Completed audits are not recovered as pending
        assert len(enforcer.pending_audits) == 0

    def test_restart_recovery_preserves_attempt_chain(self, tmp_path):
        """Restarting mid-recovery preserves all attempt history without duplication."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
        fingerprint = compute_evidence_fingerprint(
            requirements_text="requirements", project_id="project-a", task_id="TASK-1"
        )
        
        # Simulate a failed attempt that will be retried
        attempt_1 = AuditAttempt(
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
            request_state=RequestState.PENDING,
            attempts=[attempt_1],
        )
        
        tracker.metadata["TASK-1"] = {
            METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
        }

        # First recovery
        enforcer = _enforcer(tmp_path)
        enforcer.initialize([("project-a", tracker)])
        assert len(enforcer.pending_audits) == 1
        assert enforcer.pending_audits[0].attempt_ids == ["attempt-1"]

        # Simulate additional attempt after restart
        attempt_2 = AuditAttempt(
            attempt_id="attempt-2",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.IN_PROGRESS,
        )
        record_updated = TerminalAuditRecord(
            audit_id="audit-1",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            attempts=[attempt_1, attempt_2],
        )
        tracker.metadata["TASK-1"] = {
            METADATA_KEY: TerminalAuditMetadata(pending_chain=[record_updated]).to_dict()
        }

        # Second recovery after restart
        restarted = _enforcer(tmp_path)
        restarted.initialize([("project-a", tracker)])
        assert len(restarted.pending_audits) == 1
        assert restarted.pending_audits[0].attempt_ids == ["attempt-1", "attempt-2"]

    def test_repeated_recovery_pass_is_idempotent(self, tmp_path):
        """Multiple recovery passes don't change state or duplicate work."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
        fingerprint = compute_evidence_fingerprint(
            requirements_text="requirements", project_id="project-a", task_id="TASK-1"
        )
        
        attempt = AuditAttempt(
            attempt_id="attempt-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
        )
        record = TerminalAuditRecord(
            audit_id="audit-1",
            project_id="project-a",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            attempts=[attempt],
        )
        
        tracker.metadata["TASK-1"] = {
            METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
        }

        # First pass
        enforcer_1 = _enforcer(tmp_path)
        result_1 = enforcer_1.initialize([("project-a", tracker)])
        assert result_1["pending_audits"] == 1

        # Second pass (identical metadata)
        enforcer_2 = _enforcer(tmp_path)
        result_2 = enforcer_2.initialize([("project-a", tracker)])
        assert result_2["pending_audits"] == 1
        assert result_2["first_startup"] is False

        # Third pass (still identical)
        enforcer_3 = _enforcer(tmp_path)
        result_3 = enforcer_3.initialize([("project-a", tracker)])
        assert result_3["pending_audits"] == 1
        assert result_3["first_startup"] is False

        # All passes recover the same audit exactly once
        assert enforcer_1.pending_audits[0].audit_id == enforcer_2.pending_audits[0].audit_id
        assert enforcer_2.pending_audits[0].audit_id == enforcer_3.pending_audits[0].audit_id
