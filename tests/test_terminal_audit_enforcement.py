"""Startup persistence and recovery tests for terminal-audit enforcement."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import permutations
from types import SimpleNamespace

import pytest

from oompah.integration import IntegrationRecord
from oompah.models import Issue
from oompah.config import ServiceConfig
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import Orchestrator
from oompah.statuses import canonicalize_status
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_evidence_fingerprint,
    compute_integrated_evidence_fingerprint_variants,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_enforcement import (
    LEGACY_DONE_OVERRIDE_EQUIVALENCE_KEY,
    LEGACY_DONE_OVERRIDE_EQUIVALENCE_VERSION,
    LIFECYCLE_RECONCILIATION_CLASSIFIER_VERSION,
    LIFECYCLE_RECONCILIATION_VERSION,
    PendingAudit,
    SERVICE_STATE_KEY,
    TERMINAL_OVERRIDE_RECORDS_KEY,
    TERMINAL_RESULT_INTENTS_KEY,
    TerminalAuditEnforcement,
    TerminalAuditEnforcementState,
    _authority_key,
    get_recovery_snapshot,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)


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
        self.fail_status_updates = False
        self.fail_metadata_updates = False
        self.status_updates: list[tuple[str, str]] = []

    def fetch_all_issues_enriched(self):
        return list(self.issues)

    def get_metadata(self, identifier: str):
        return dict(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object):
        if self.fail_metadata_updates:
            raise RuntimeError("metadata write failed")
        self.set_calls += 1
        self.metadata.setdefault(identifier, {})[key] = value

    def update_issue(self, identifier: str, **kwargs):
        if self.fail_status_updates:
            raise RuntimeError("status write failed")
        for issue in self.issues:
            if issue.identifier == identifier and "status" in kwargs:
                self.status_updates.append((identifier, kwargs["status"]))
                issue.state = kwargs["status"]


class _OverrideRaceTracker(_Tracker):
    """Inject a concurrent override while the recovery updater reads current state."""

    def __init__(self, issues: list[Issue], injected_override: dict[str, object]):
        super().__init__(issues)
        self.injected_override = injected_override
        self.read_count = 0

    def get_metadata(self, identifier: str):
        self.read_count += 1
        if self.read_count == 2:
            current = TerminalAuditMetadata.from_dict(
                self.metadata[identifier][METADATA_KEY]
            )
            unknown = dict(current.unknown_fields)
            overrides = list(unknown.get(TERMINAL_OVERRIDE_RECORDS_KEY, []))
            overrides.append(self.injected_override)
            unknown[TERMINAL_OVERRIDE_RECORDS_KEY] = overrides
            self.metadata[identifier][METADATA_KEY] = TerminalAuditMetadata(
                pending_chain=current.pending_chain,
                attempt_history=current.attempt_history,
                unknown_fields=unknown,
            ).to_dict()
        return super().get_metadata(identifier)


class _SlowLifecycleTracker(_Tracker):
    """Block one status write so progress reads can race a migration safely."""

    def __init__(self, issues: list[Issue]):
        super().__init__(issues)
        self.started = threading.Event()
        self.release = threading.Event()

    def update_issue(self, identifier: str, **kwargs):
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release lifecycle write")
        return super().update_issue(identifier, **kwargs)


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


def _native_tracker(root) -> OompahMarkdownTracker:
    root.mkdir(parents=True, exist_ok=True)
    return OompahMarkdownTracker(
        active_states=["Open"],
        terminal_states=["Done"],
        cwd=str(root),
        default_branch="main",
        git_sync=False,
    )


def _native_integration(*, head_sha: str) -> IntegrationRecord:
    return IntegrationRecord(
        state="ready",
        task_branch="TASK-branch",
        base_branch="main",
        base_sha="b" * 40,
        head_sha=head_sha,
    )


def _pending_record(
    project_id: str,
    task_id: str,
    audit_id: str,
    *,
    request_state: RequestState = RequestState.PENDING,
) -> TerminalAuditRecord:
    fingerprint = compute_evidence_fingerprint(
        requirements_text="requirements",
        project_id=project_id,
        task_id=task_id,
    )
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=request_state,
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


def test_evidence_change_is_retained_as_invalidated_but_not_a_dispatch_queue_row(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    _enforcer(tmp_path).initialize([("project-a", tracker)])

    tracker.issues[0].evidence_fingerprint = "evidence-b"  # type: ignore[attr-defined]
    restarted = _enforcer(tmp_path)
    result = restarted.initialize([("project-a", tracker)])
    assert result["pending_audits"] == 0
    assert len(restarted.state.invalidated) == 1

    second = _enforcer(tmp_path)
    result = second.initialize([("project-a", tracker)])
    assert result["pending_audits"] == 0
    assert len(second.state.invalidated) == 1
    assert second.state.pending_audits == []


def test_terminal_to_nonterminal_to_terminal_is_not_grandfathered(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    _enforcer(tmp_path).initialize([("project-a", tracker)])

    tracker.issues[0].state = "Open"
    observed_nonterminal = _enforcer(tmp_path).initialize([("project-a", tracker)])
    assert observed_nonterminal["grandfathered"] == 0
    assert observed_nonterminal["pending_audits"] == 0

    tracker.issues[0].state = "Done"
    reentered = _enforcer(tmp_path).initialize([("project-a", tracker)])
    assert reentered["pending_audits"] == 0
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


def test_recovery_replaces_mixed_persisted_rows_with_live_metadata_per_project(tmp_path):
    """Only current In Validation metadata is retained as a launchable queue."""

    live = _pending_record("project-a", "TASK-1", "audit-live")
    stale_status = _pending_record("project-a", "TASK-2", "audit-archived")
    stale_revision = _pending_record("project-a", "TASK-3", "audit-revision")
    stale_evidence = _pending_record("project-a", "TASK-4", "audit-evidence")
    stale_missing = _pending_record("project-b", "TASK-1", "audit-missing")

    tracker_a = _Tracker(
        [
            _issue("TASK-1", "In Validation", "evidence-a"),
            _issue("TASK-2", "Archived", "evidence-a"),
            _issue("TASK-3", "In Validation", "evidence-a"),
            _issue("TASK-4", "In Validation", "evidence-a"),
        ]
    )
    tracker_a.issues[-1].description = "requirements updated"
    tracker_b = _Tracker([])
    tracker_a.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[live]).to_dict()
    }
    tracker_a.metadata["TASK-3"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[replace(stale_revision, request_state=RequestState.SUPERSEDED)]
        ).to_dict()
    }
    tracker_a.metadata["TASK-4"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[stale_evidence]).to_dict()
    }

    state = TerminalAuditEnforcementState(
        pending_audits=[
            PendingAudit.from_record(live),
            PendingAudit.from_record(stale_status),
            PendingAudit.from_record(stale_revision),
            PendingAudit.from_record(stale_evidence),
            PendingAudit.from_record(stale_missing),
        ]
    )
    (tmp_path / "service_state.json").write_text(
        json.dumps({SERVICE_STATE_KEY: state.to_dict()}), encoding="utf-8"
    )

    enforcer = _enforcer(tmp_path)
    recovered = enforcer.initialize(
        [("project-a", tracker_a), ("project-b", tracker_b)]
    )

    assert recovered["pending_audits"] == 1
    assert [(entry.project_id, entry.task_id, entry.audit_id) for entry in enforcer.pending_audits] == [
        ("project-a", "TASK-1", "audit-live")
    ]
    persisted = json.loads((tmp_path / "service_state.json").read_text())
    assert [entry["audit_id"] for entry in persisted[SERVICE_STATE_KEY]["pending_audits"]] == [
        "audit-live"
    ]

    repeated = _enforcer(tmp_path).initialize(
        [("project-a", tracker_a), ("project-b", tracker_b)]
    )
    assert repeated["pending_audits"] == 1
    assert repeated["scan_complete"] is True


def test_corrupt_service_state_fails_closed_and_is_observable(tmp_path, caplog):
    state_path = tmp_path / "service_state.json"
    state_path.write_text("not-json")
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a")])
    enforcer = _enforcer(tmp_path)

    with caplog.at_level(logging.ERROR, logger="oompah.terminal_audit_enforcement"):
        result = enforcer.initialize([("project-a", tracker)])

    assert result["quarantined"] is True
    assert result["pending_audits"] == 0
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
    assert result["pending_audits"] == 0
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
    assert enforcer.pending_audits == []
    assert len(enforcer.state.invalidated) == 1

    enforcer.mark_audit_passed("project-a", tracker.issues[0], "evidence-b")
    restarted = _enforcer(tmp_path)
    result = restarted.initialize([("project-a", tracker)])
    assert result["pending_audits"] == 0
    assert result["grandfathered"] == 1


def test_restart_finishes_override_retirement_after_status_write(tmp_path):
    """A crash between status and final metadata writes cannot requeue siblings."""
    tracker = _Tracker([_issue("TASK-1", "Done", "evidence-a", "project-a")])
    record = _pending_record("project-a", "TASK-1", "audit-pending")
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={
                "oompah.terminal_override_records": [
                    {
                        "version": 1,
                        "override_id": "override-crashed",
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "target_state": "Done",
                        "evidence_fingerprint": record.evidence_fingerprint.to_dict(),
                        "authorized_by": {
                            "version": 1,
                            "identity": "owner",
                        },
                        "reason": "restart recovery",
                        "applied": False,
                    }
                ]
            },
        ).to_dict()
    }

    enforcer = _enforcer(tmp_path)
    recovered = enforcer.recover_pending_audits([("project-a", tracker)])

    assert recovered == []
    stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    assert stored.pending_chain[0].request_state == RequestState.CANCELLED
    assert stored.unknown_fields["oompah.terminal_override_records"][0]["applied"] is True
    assert stored.unknown_fields["oompah.terminal_audit_retirements"][0]["applied"] is True


def test_legacy_incompatible_shared_merged_child_restores_done_without_canceling_unrelated_audit(
    tmp_path,
):
    """Legacy EXOCOMP-240-shaped state converges to its completed Done audit."""

    child = _issue("CHILD-1", "Merged", "evidence-a", "project-a")
    child.parent_id = "EPIC-1"
    done = _pending_record("project-a", "CHILD-1", "audit-done")
    done = replace(
        done,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="done-pass",
                target_state=TargetState.DONE,
                evidence_fingerprint=done.evidence_fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )
    merged = replace(
        done,
        audit_id="audit-merged-override",
        target_state=TargetState.MERGED,
        request_state=RequestState.COMPLETED,
    )
    unrelated = replace(
        done,
        audit_id="audit-unrelated-archive",
        target_state=TargetState.ARCHIVED,
        request_state=RequestState.PENDING,
        attempts=[],
    )
    override = {
        "version": 1,
        "override_id": "override-legacy-merged",
        "project_id": "project-a",
        "task_id": "CHILD-1",
        "target_state": TargetState.MERGED.value,
        "evidence_fingerprint": done.evidence_fingerprint.to_dict(),
        "authorized_by": {"version": 1, "identity": "owner"},
        "reason": "legacy emergency approval",
        "applied": True,
    }
    tracker = _Tracker([child])
    tracker.metadata[child.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[done, merged, unrelated],
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [override]},
        ).to_dict()
    }

    def conflict(_issue, target, _project):
        if target == TargetState.MERGED:
            return (
                "Cannot transition shared-epic child CHILD-1 to Merged: parent "
                "review must land on configured target branch main first."
            )
        return None

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=conflict,
    )
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []

    stored = TerminalAuditMetadata.from_dict(
        tracker.metadata[child.identifier][METADATA_KEY]
    )
    by_id = {record.audit_id: record for record in stored.pending_chain}
    assert child.state == "Done"
    assert by_id[done.audit_id].request_state == RequestState.COMPLETED
    assert by_id[merged.audit_id].request_state == RequestState.SUPERSEDED
    assert by_id[unrelated.audit_id].request_state == RequestState.PENDING
    repaired_override = stored.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY][0]
    assert repaired_override["lifecycle_reconciled"] is True
    assert repaired_override["reconciled_to"] == "Done"
    assert tracker.status_updates == [("CHILD-1", "Done")]


def _legacy_lifecycle_issue(tracker: _Tracker, identifier: str) -> None:
    issue = _issue(identifier, "Merged", "evidence-a", "project-a")
    issue.parent_id = "EPIC-1"
    done = replace(
        _pending_record("project-a", identifier, f"audit-done-{identifier}"),
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id=f"done-pass-{identifier}",
                target_state=TargetState.DONE,
                evidence_fingerprint=compute_issue_evidence_fingerprint(
                    issue, "project-a"
                ),
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )
    tracker.issues.append(issue)
    tracker.metadata[identifier] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[done]).to_dict()
    }


def _shared_epic_conflict(issue, target, _project):
    if target == TargetState.MERGED:
        return f"shared epic parent has not landed for {issue.identifier}"
    return None


def _completed_terminal_authority(
    issue: Issue,
    project_id: str,
    target_state: TargetState,
) -> TerminalAuditRecord:
    fingerprint = compute_issue_evidence_fingerprint(issue, project_id)
    return TerminalAuditRecord(
        audit_id=f"audit-{target_state.value.lower()}-{issue.identifier}",
        project_id=project_id,
        task_id=issue.identifier,
        target_state=target_state,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id=f"pass-{target_state.value.lower()}-{issue.identifier}",
                target_state=target_state,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )


def _applied_terminal_override(
    issue: Issue,
    project_id: str,
    target_state: TargetState,
) -> dict[str, object]:
    raw = OverrideRecord(
        override_id=f"override-{target_state.value.lower()}-{issue.identifier}",
        project_id=project_id,
        task_id=issue.identifier,
        target_state=target_state,
        evidence_fingerprint=compute_issue_evidence_fingerprint(issue, project_id),
        authorized_by=ContributorIdentity("owner", "api"),
        reason="authorized recovery",
    ).to_dict()
    raw["applied"] = True
    return raw


def _oompah_660_lifecycle_issue(
    project_id: str = "proj-14849f1b",
) -> Issue:
    issue = Issue(
        id="OOMPAH-660",
        identifier="OOMPAH-660",
        state="Merged",
        title="Rebase epic-OOMPAH-619 onto main",
        description=(
            "The epic branch `epic-OOMPAH-619` is stale: it has fallen behind "
            "`main`. Rebase the branch onto `origin/main`, resolve any conflicts, "
            "and force-push with `git push --force-with-lease`.\n\n"
            "This task was auto-filed because epic OOMPAH-619 was detected as "
            "stale. Do NOT create a new branch or PR — work directly on "
            "`epic-OOMPAH-619`."
        ),
        parent_id="OOMPAH-619",
        project_id=project_id,
        work_branch="epic-OOMPAH-619--task-OOMPAH-660",
    )
    issue.integration = IntegrationRecord(
        state="integrated",
        attempts=2,
        task_branch="epic-OOMPAH-619--task-OOMPAH-660",
        base_branch="epic-OOMPAH-619",
        base_sha="17658b95e32641e8cf2dbfff06f780c0f6b57916",
        head_sha="793bcc7969d39634dab560ed0a10b9dcad7a9716",
        integrated_sha="793bcc7969d39634dab560ed0a10b9dcad7a9716",
    )
    return issue


def _legacy_done_override(issue: Issue, project_id: str) -> dict[str, object]:
    variants = compute_integrated_evidence_fingerprint_variants(issue, project_id)
    assert variants is not None
    raw = OverrideRecord(
        override_id="override-6ca80332d3a5",
        project_id=project_id,
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=variants.legacy_work_branch,
        authorized_by=ContributorIdentity("lesserevil", "api"),
        reason="production owner override",
        created_at="2026-07-31T13:50:42.120929+00:00",
    ).to_dict()
    raw["applied"] = True
    return raw


def _v1_exhausted_lifecycle_state(
    identifiers: list[tuple[str, str]],
    started: datetime,
) -> dict[str, object]:
    return {
        SERVICE_STATE_KEY: TerminalAuditEnforcementState(
            lifecycle_reconciliation={
                "version": 1,
                "status": "degraded",
                "records": [
                    {
                        "project_id": project_id,
                        "task_id": task_id,
                        "status": "exhausted",
                        "attempts": 5,
                        "last_error": "lifecycle_repair_not_applied",
                        "conflict": "stale shared-epic conflict",
                        "failure_fingerprint": "0" * 64,
                        "exhausted_at": started.isoformat(),
                        "updated_at": started.isoformat(),
                    }
                    for project_id, task_id in identifiers
                ],
                "cursor": 0,
                "updated_at": started.isoformat(),
                "errors": [],
            }
        ).to_dict()
    }


def test_lifecycle_reconciliation_batches_are_durable_and_restart_safe(tmp_path):
    tracker = _Tracker([])
    for number in range(5):
        _legacy_lifecycle_issue(tracker, f"CHILD-{number}")
    state_path = tmp_path / "service_state.json"

    first = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    progress = first.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=2
    )
    assert progress["status"] == "migrating"
    assert progress["processed"] == 2
    assert progress["pending"] == 3
    assert len(tracker.status_updates) == 2

    # A fresh enforcement object resumes from the persisted row statuses.
    restarted = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=2
    )
    final = restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=2
    )
    assert final["status"] == "complete"
    assert final["processed"] == 5
    assert final["reconciled"] == 5
    assert final["pending"] == 0
    assert [identifier for identifier, _ in tracker.status_updates] == [
        f"CHILD-{number}" for number in range(5)
    ]

    # Duplicate recovery does not issue a second terminal mutation.
    duplicate = restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=10
    )
    assert duplicate["status"] == "complete"
    assert len(tracker.status_updates) == 5


def test_lifecycle_batch_scopes_native_issues_and_installs_complete_snapshot(
    tmp_path,
):
    tracker = _native_tracker(tmp_path / "native-repo")
    parent = tracker.create_issue(
        "Parent epic",
        issue_type="epic",
        initial_status="Merged",
    )
    child = tracker.create_issue(
        "Native child",
        parent=parent.identifier,
        initial_status="Merged",
    )
    observed: list[str] = []

    def validate(issue, target, project_id):
        assert target == TargetState.MERGED
        assert project_id == "project-native"
        assert issue.project_id == "project-native"
        snapshot = get_recovery_snapshot()
        assert snapshot is not None
        assert snapshot[issue.identifier] is issue
        assert all(item.project_id == "project-native" for item in snapshot.values())
        if issue.parent_id:
            assert snapshot[issue.parent_id].state == "Merged"
        observed.append(issue.identifier)
        return None

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=validate,
    )
    result = enforcer.reconcile_lifecycle_batch(
        [("project-native", tracker)], batch_size=2
    )

    assert result["status"] == "complete"
    assert result["processed"] == 2
    assert result["reconciled"] == 0
    assert set(observed) == {parent.identifier, child.identifier}
    assert tracker.fetch_issue_detail(child.identifier).project_id is None


def test_lifecycle_stale_merged_conflict_accepts_current_pass_archived(tmp_path):
    issue = _issue("ARCHIVED-1", "Archived", "evidence", "project-a")
    issue.parent_id = "EPIC-1"
    tracker = _Tracker([issue])
    archived = _completed_terminal_authority(
        issue, "project-a", TargetState.ARCHIVED
    )
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[archived]).to_dict()
    }
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps(
            _v1_exhausted_lifecycle_state(
                [("project-a", issue.identifier)], started
            )
        ),
        encoding="utf-8",
    )
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], max_attempts=1, now=started
    )

    assert result["status"] == "complete"
    assert result["processed"] == 1
    assert result["reconciled"] == 0
    assert result["action_required"] is False
    assert tracker.status_updates == []
    row = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert row["outcome"] == "not_needed"
    assert row["classifier_version"] == LIFECYCLE_RECONCILIATION_CLASSIFIER_VERSION


def test_lifecycle_revalidates_locked_snapshot_before_done_write(tmp_path):
    child = _issue("CHILD-RACE", "Merged", "evidence", "project-a")
    child.parent_id = "EPIC-RACE"
    parent = _issue("EPIC-RACE", "In Review", "parent", "project-a")
    parent.issue_type = "epic"
    tracker = _Tracker([child, parent])
    done_record = _completed_terminal_authority(
        child, "project-a", TargetState.DONE
    )
    tracker.metadata[child.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[done_record]
        ).to_dict()
    }
    tracker.metadata[parent.identifier] = {}

    class LandingLockStore(_LockStore):
        def project_write_lock(self, _project_id):
            class Lock:
                def __enter__(self):
                    parent.state = "Merged"
                    return self

                def __exit__(self, *_args):
                    return None

            return Lock()

    observed_parent_states: list[str] = []

    def validate(issue, _target, _project_id):
        snapshot = get_recovery_snapshot()
        assert snapshot is not None
        parent_state = canonicalize_status(snapshot[issue.parent_id].state)
        observed_parent_states.append(parent_state)
        if parent_state in {"Merged", "Archived"}:
            return None
        return "parent review has not landed"

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=LandingLockStore(),
        validate_terminal_transition=validate,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=1,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    assert observed_parent_states == ["In Review", "Merged"]
    assert result["status"] == "complete"
    assert result["reconciled"] == 0
    assert tracker.status_updates == []
    assert child.state == "Merged"


def test_lifecycle_locked_refetch_completes_concurrent_child_state_change(tmp_path):
    child = _issue("CHILD-STATE-RACE", "Merged", "evidence", "project-a")
    child.parent_id = "EPIC-STATE-RACE"
    parent = _issue("EPIC-STATE-RACE", "In Review", "parent", "project-a")
    parent.issue_type = "epic"
    tracker = _Tracker([child, parent])
    tracker.metadata[child.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[
                _completed_terminal_authority(
                    child, "project-a", TargetState.DONE
                )
            ]
        ).to_dict()
    }
    tracker.metadata[parent.identifier] = {}

    class StateChangeLockStore(_LockStore):
        def project_write_lock(self, _project_id):
            class Lock:
                def __enter__(self):
                    child.state = "Done"
                    return self

                def __exit__(self, *_args):
                    return None

            return Lock()

    def validate(_issue, _target, _project_id):
        return "parent review has not landed"

    state_path = tmp_path / "service_state.json"
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=StateChangeLockStore(),
        validate_terminal_transition=validate,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=1,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    assert result["status"] == "complete"
    assert result["reconciled"] == 0
    assert tracker.status_updates == []
    row = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert row["status"] == "completed"
    assert row["outcome"] == "state_changed"
    assert "conflict" not in row


def test_lifecycle_done_only_owner_override_repairs_once_but_normal_task_fails_closed(
    tmp_path,
):
    helper = _issue("HELPER-1", "Merged", "evidence", "project-a")
    helper.title = "Rebase epic-EPIC-1 onto main"
    helper.parent_id = "EPIC-1"
    normal = _issue("NORMAL-1", "Merged", "evidence", "project-a")
    normal.parent_id = "EPIC-1"
    tracker = _Tracker([helper, normal])
    for issue in (helper, normal):
        tracker.metadata[issue.identifier] = {
            METADATA_KEY: TerminalAuditMetadata(
                unknown_fields={
                    TERMINAL_OVERRIDE_RECORDS_KEY: [
                        _applied_terminal_override(
                            issue, "project-a", TargetState.DONE
                        )
                    ]
                }
            ).to_dict()
        }
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps(
            _v1_exhausted_lifecycle_state(
                [
                    ("project-a", helper.identifier),
                    ("project-a", normal.identifier),
                ],
                started,
            )
        ),
        encoding="utf-8",
    )
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        batch_size=2,
        max_attempts=1,
        now=started,
    )

    assert result["reconciled"] == 1
    assert result["exhausted"] == 1
    assert result["action_required"] is True
    assert tracker.status_updates == [(helper.identifier, "Done")]
    repeated = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        batch_size=2,
        max_attempts=1,
        now=started + timedelta(days=1),
    )
    assert repeated == result
    assert tracker.status_updates == [(helper.identifier, "Done")]


def test_lifecycle_legacy_equivalence_repairs_exact_production_oompah_660_once(
    tmp_path,
):
    project_id = "proj-14849f1b"
    issue = _oompah_660_lifecycle_issue(project_id)
    variants = compute_integrated_evidence_fingerprint_variants(issue, project_id)
    assert variants is not None
    assert variants.integrated.digest.startswith("ab40139d2035")
    assert variants.legacy_work_branch.digest.startswith("62954f9b5fdc")

    legacy_done = _legacy_done_override(issue, project_id)
    merged = OverrideRecord(
        override_id="override-d9ab44234a19",
        project_id=project_id,
        task_id=issue.identifier,
        target_state=TargetState.MERGED,
        evidence_fingerprint=variants.legacy_work_branch,
        authorized_by=ContributorIdentity("oompah-cli", "api"),
        reason="historical incompatible Merged override",
    ).to_dict()
    merged["applied"] = True
    foreign_merged = dict(merged)
    foreign_merged["override_id"] = "foreign-merged"
    foreign_merged["project_id"] = "project-b"
    state_path = tmp_path / "service_state.json"

    class IntentCheckingTracker(_Tracker):
        intent_seen = False

        def update_issue(self, identifier: str, **kwargs):
            persisted = json.loads(state_path.read_text(encoding="utf-8"))[
                SERVICE_STATE_KEY
            ]["lifecycle_reconciliation"]["records"][0]
            assert persisted[LEGACY_DONE_OVERRIDE_EQUIVALENCE_KEY]["version"] == (
                LEGACY_DONE_OVERRIDE_EQUIVALENCE_VERSION
            )
            self.intent_seen = True
            return super().update_issue(identifier, **kwargs)

    tracker = IntentCheckingTracker([issue])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [
                    legacy_done,
                    merged,
                    foreign_merged,
                ]
            }
        ).to_dict()
    }
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [(project_id, tracker)],
        max_attempts=1,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    assert result["status"] == "complete"
    assert result["reconciled"] == 1
    assert result["action_required"] is False
    assert tracker.intent_seen is True
    assert tracker.status_updates == [(issue.identifier, "Done")]
    lifecycle = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]
    row = lifecycle["records"][0]
    marker = row[LEGACY_DONE_OVERRIDE_EQUIVALENCE_KEY]
    assert row["status"] == "completed"
    assert row["outcome"] == "reconciled"
    assert marker["version"] == LEGACY_DONE_OVERRIDE_EQUIVALENCE_VERSION
    assert marker["legacy_evidence_fingerprint"] == variants.legacy_work_branch.digest
    assert marker["current_evidence_fingerprint"] == variants.integrated.digest

    stored = TerminalAuditMetadata.from_dict(
        tracker.metadata[issue.identifier][METADATA_KEY]
    )
    by_id = {
        raw["override_id"]: raw
        for raw in stored.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY]
    }
    assert "retired_reason" not in by_id[legacy_done["override_id"]]
    assert by_id[merged["override_id"]]["lifecycle_reconciled"] is True
    assert "retired_reason" not in by_id[foreign_merged["override_id"]]
    reconciliation = stored.unknown_fields["oompah.lifecycle_reconciliations"][0]
    assert reconciliation[LEGACY_DONE_OVERRIDE_EQUIVALENCE_KEY] == marker

    writes_before = tracker.set_calls
    repeated = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    ).reconcile_lifecycle_batch(
        [(project_id, tracker)],
        max_attempts=1,
        now=datetime(2026, 8, 6, tzinfo=timezone.utc),
    )
    assert repeated == result
    assert tracker.set_calls == writes_before
    assert tracker.status_updates == [(issue.identifier, "Done")]


def test_lifecycle_current_match_oompah_662_control_needs_no_equivalence(tmp_path):
    project_id = "proj-14849f1b"
    issue = _issue("OOMPAH-662", "Merged", "evidence", project_id)
    issue.title = "Rebase epic-OOMPAH-619 onto main"
    issue.parent_id = "OOMPAH-619"
    tracker = _Tracker([issue])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [
                    _applied_terminal_override(issue, project_id, TargetState.DONE)
                ]
            }
        ).to_dict()
    }
    state_path = tmp_path / "service_state.json"
    result = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    ).reconcile_lifecycle_batch(
        [(project_id, tracker)], max_attempts=1
    )

    assert result["reconciled"] == 1
    row = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert LEGACY_DONE_OVERRIDE_EQUIVALENCE_KEY not in row
    assert tracker.status_updates == [(issue.identifier, "Done")]


@pytest.mark.parametrize(
    "mutation",
    [
        "integrated_sha",
        "base_branch",
        "task_identity",
        "target",
        "authority",
        "application",
        "ordinary_task",
        "ci_fix",
        "merge_conflict",
        "retired",
        "missing_integration",
        "arbitrary_fingerprint",
    ],
)
def test_lifecycle_legacy_equivalence_one_field_drift_fails_closed(
    tmp_path,
    mutation,
):
    project_id = "proj-14849f1b"
    issue = _oompah_660_lifecycle_issue(project_id)
    override = _legacy_done_override(issue, project_id)
    if mutation == "integrated_sha":
        issue.integration = replace(issue.integration, integrated_sha="f" * 40)
    elif mutation == "base_branch":
        issue.integration = replace(issue.integration, base_branch="main")
    elif mutation == "task_identity":
        override["task_id"] = "OOMPAH-661"
    elif mutation == "target":
        override["target_state"] = TargetState.ARCHIVED.value
    elif mutation == "authority":
        override["authorized_by"] = {"version": 1, "identity": ""}
    elif mutation == "application":
        override["applied"] = False
    elif mutation == "ordinary_task":
        issue.title = "Implement an ordinary feature"
    elif mutation == "ci_fix":
        issue.labels = ["ci-fix"]
    elif mutation == "merge_conflict":
        issue.labels = ["merge-conflict"]
    elif mutation == "retired":
        override["retired_reason"] = "superseded_by_newer_override"
    elif mutation == "missing_integration":
        issue.integration = None
    elif mutation == "arbitrary_fingerprint":
        override["evidence_fingerprint"] = EvidenceFingerprint("0" * 64).to_dict()
        override["reason"] = "mentions the exact production SHA and migration"

    tracker = _Tracker([issue])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [override]}
        ).to_dict()
    }
    result = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    ).reconcile_lifecycle_batch(
        [(project_id, tracker)], max_attempts=1
    )

    assert result["reconciled"] == 0
    assert result["exhausted"] == 1
    assert tracker.status_updates == []


def test_lifecycle_legacy_equivalence_scm_outage_fails_closed(tmp_path):
    project_id = "proj-14849f1b"
    issue = _oompah_660_lifecycle_issue(project_id)
    tracker = _Tracker([issue])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [
                    _legacy_done_override(issue, project_id)
                ]
            }
        ).to_dict()
    }

    def unavailable(*_args):
        raise OSError("SCM unavailable")

    result = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=unavailable,
    ).reconcile_lifecycle_batch(
        [(project_id, tracker)], max_attempts=1
    )

    assert result["reconciled"] == 0
    assert result["exhausted"] == 1
    assert tracker.status_updates == []


def test_lifecycle_legacy_equivalence_recovers_post_write_metadata_failure(
    tmp_path,
):
    project_id = "proj-14849f1b"
    issue = _oompah_660_lifecycle_issue(project_id)
    tracker = _Tracker([issue])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [
                    _legacy_done_override(issue, project_id)
                ]
            }
        ).to_dict()
    }
    state_path = tmp_path / "service_state.json"
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    tracker.fail_metadata_updates = True
    first = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    ).reconcile_lifecycle_batch(
        [(project_id, tracker)], max_attempts=2, now=started
    )

    assert first["failed"] == 1
    assert tracker.status_updates == [(issue.identifier, "Done")]
    intent = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert intent[LEGACY_DONE_OVERRIDE_EQUIVALENCE_KEY]["version"] == 1

    tracker.fail_metadata_updates = False
    recovered = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    ).reconcile_lifecycle_batch(
        [(project_id, tracker)],
        max_attempts=2,
        now=started + timedelta(seconds=30),
    )

    assert recovered["status"] == "complete"
    assert recovered["reconciled"] == 1
    assert tracker.status_updates == [(issue.identifier, "Done")]


def test_lifecycle_legacy_equivalence_is_project_scoped(tmp_path):
    task_id = "OOMPAH-660"
    issue_a = _oompah_660_lifecycle_issue("project-a")
    issue_b = _oompah_660_lifecycle_issue("project-b")
    tracker_a = _Tracker([issue_a])
    tracker_b = _Tracker([issue_b])
    project_a_override = _legacy_done_override(issue_a, "project-a")
    tracker_a.metadata[task_id] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [project_a_override]
            }
        ).to_dict()
    }
    tracker_b.metadata[task_id] = deepcopy(tracker_a.metadata[task_id])

    result = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    ).reconcile_lifecycle_batch(
        [("project-a", tracker_a), ("project-b", tracker_b)],
        batch_size=2,
        max_attempts=1,
    )

    assert result["reconciled"] == 1
    assert result["exhausted"] == 1
    assert tracker_a.status_updates == [(task_id, "Done")]
    assert tracker_b.status_updates == []


@pytest.mark.parametrize(
    ("retirement_marker", "retirement_value"),
    [
        ("retired_reason", "superseded_by_newer_override"),
        ("retired_by_reconciliation", True),
        ("lifecycle_retired", True),
    ],
)
def test_lifecycle_retired_done_override_cannot_reauthorize_status_write(
    tmp_path,
    retirement_marker,
    retirement_value,
):
    helper = _issue("HELPER-RETIRED", "Merged", "evidence", "project-a")
    helper.title = "Rebase epic-EPIC-1 onto main"
    helper.parent_id = "EPIC-1"
    override = _applied_terminal_override(
        helper, "project-a", TargetState.DONE
    )
    override[retirement_marker] = retirement_value
    tracker = _Tracker([helper])
    tracker.metadata[helper.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [override]}
        ).to_dict()
    }
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps(
            _v1_exhausted_lifecycle_state(
                [("project-a", helper.identifier)], started
            )
        ),
        encoding="utf-8",
    )
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], max_attempts=1, now=started
    )

    assert result["exhausted"] == 1
    assert result["reconciled"] == 0
    assert tracker.status_updates == []
    assert helper.state == "Merged"


def test_lifecycle_fingerprint_reopens_for_changed_landing_fact_not_outage_or_restart(
    tmp_path,
):
    issue = _issue("NESTED-1", "Merged", "evidence", "project-a")
    issue.parent_id = "EPIC-1"
    parent = _issue("EPIC-1", "In Review", "parent", "project-a")
    parent.issue_type = "epic"
    tracker = _Tracker([issue, parent])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata().to_dict()
    }
    tracker.metadata[parent.identifier] = {
        METADATA_KEY: TerminalAuditMetadata().to_dict()
    }
    evidence = {"revision": "landing-v1", "landed": False, "outage": False}

    def validate(_issue, _target, _project):
        return None if evidence["landed"] else "target-relative review not landed"

    def landing(_issue, project_id, _snapshot):
        if evidence["outage"]:
            raise OSError("workflow fact store unavailable")
        return {
            "project_id": project_id,
            "source": "epic-NESTED-1",
            "target": "epic-EPIC-1",
            "evidence_revision": evidence["revision"],
        }

    state_path = tmp_path / "service_state.json"
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    first = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=validate,
        lifecycle_landing_evidence=landing,
    )
    exhausted = first.reconcile_lifecycle_batch(
        [("project-a", tracker)], max_attempts=1, now=started
    )
    assert exhausted["exhausted"] == 1

    evidence["outage"] = True
    restarted = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=validate,
        lifecycle_landing_evidence=landing,
    )
    unavailable = restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=1,
        now=started + timedelta(days=1),
    )
    assert unavailable == exhausted

    evidence.update({"outage": False, "landed": True, "revision": "landing-v2"})
    recovered = restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=1,
        now=started + timedelta(days=2),
    )
    assert recovered["status"] == "complete"
    assert recovered["action_required"] is False
    assert recovered["reconciled"] == 0


def test_lifecycle_v1_absent_reappearance_waits_for_authoritative_landing_evidence(
    tmp_path,
):
    project_id = "project-a"
    task_id = "CHILD-REAPPEARS-DURING-OUTAGE"
    tracker = _Tracker([])
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state_path = tmp_path / "service_state.json"
    raw_state = _v1_exhausted_lifecycle_state(
        [(project_id, task_id)], started
    )
    row = raw_state[SERVICE_STATE_KEY]["lifecycle_reconciliation"]["records"][0]
    row["last_error"] = "task_not_present_in_current_snapshot"
    state_path.write_text(json.dumps(raw_state), encoding="utf-8")
    evidence = {"available": False}

    def landing(_issue, scoped_project_id, _snapshot):
        if not evidence["available"]:
            raise OSError("SCM landing observation unavailable")
        return {
            "project_id": scoped_project_id,
            "source": "epic-PARENT",
            "target": "main",
            "observation": "landed",
            "facts": [],
        }

    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=lambda *_args: None,
        lifecycle_landing_evidence=landing,
    )

    initial = enforcer.reconcile_lifecycle_batch(
        [(project_id, tracker)], max_attempts=1, now=started
    )
    assert initial["exhausted"] == 1
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert persisted["attempts"] == 5
    assert persisted["migration_v1_rearm_pending"] is True

    issue = _issue(task_id, "Merged", "evidence", project_id)
    tracker.issues.append(issue)
    tracker.metadata[task_id] = {}
    unavailable = enforcer.reconcile_lifecycle_batch(
        [(project_id, tracker)],
        max_attempts=1,
        now=started + timedelta(hours=1),
    )
    assert unavailable == initial
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert persisted["status"] == "exhausted"
    assert persisted["attempts"] == 5
    assert persisted["migration_v1_rearm_pending"] is True
    assert tracker.status_updates == []

    evidence["available"] = True
    recovered = enforcer.reconcile_lifecycle_batch(
        [(project_id, tracker)],
        max_attempts=1,
        now=started + timedelta(hours=2),
    )
    assert recovered["status"] == "complete"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert persisted["status"] == "completed"
    assert persisted["attempts"] == 1
    assert "migration_v1_rearm_pending" not in persisted
    assert tracker.status_updates == []


def test_lifecycle_v1_rearm_survives_processing_outage_after_fingerprint(
    tmp_path,
):
    project_id = "project-a"
    helper = _issue("HELPER-OBSERVATION-RACE", "Merged", "evidence", project_id)
    helper.title = "Rebase epic-EPIC-1 onto main"
    helper.parent_id = "EPIC-1"
    tracker = _Tracker([helper])
    tracker.metadata[helper.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [
                    _applied_terminal_override(
                        helper,
                        project_id,
                        TargetState.DONE,
                    )
                ]
            }
        ).to_dict()
    }
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps(
            _v1_exhausted_lifecycle_state(
                [(project_id, helper.identifier)], started
            )
        ),
        encoding="utf-8",
    )
    validator_calls = 0

    def validate(_issue, _target, _project_id):
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls == 2:
            raise OSError("SCM unavailable after fingerprint observation")
        return "maintenance helpers are Done-only"

    def landing(_issue, scoped_project_id, _snapshot):
        return {
            "project_id": scoped_project_id,
            "source": "epic-EPIC-1",
            "target": "main",
            "observation": "not_landed",
            "facts": [],
        }

    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=validate,
        lifecycle_landing_evidence=landing,
    )

    unavailable = enforcer.reconcile_lifecycle_batch(
        [(project_id, tracker)], max_attempts=1, now=started
    )
    assert unavailable["exhausted"] == 1
    assert tracker.status_updates == []
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert persisted["attempts"] == 1
    assert persisted["retry_epochs"] == 1
    assert persisted["migration_v1_rearm_pending"] is True
    assert persisted["migration_v1_rearm_started"] is True

    recovered = enforcer.reconcile_lifecycle_batch(
        [(project_id, tracker)],
        max_attempts=1,
        now=started + timedelta(hours=1),
    )
    assert recovered["status"] == "complete"
    assert recovered["reconciled"] == 1
    assert tracker.status_updates == [(helper.identifier, "Done")]
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert persisted["retry_epochs"] == 1
    assert "migration_v1_rearm_pending" not in persisted
    assert "migration_v1_rearm_started" not in persisted


def test_lifecycle_landing_evidence_rejects_incomplete_fact_and_uses_exact_scm_route(
    monkeypatch,
):
    import oompah.orchestrator as orchestrator_module

    project = SimpleNamespace(
        id="project-a",
        repo_url="https://github.com/org/repo",
        default_branch="main",
        access_token=None,
    )
    root = _issue("ROOT", "In Review", "root", "project-a")
    root.issue_type = "epic"
    nested = _issue("NESTED", "In Review", "nested", "project-a")
    nested.issue_type = "epic"
    nested.parent_id = root.identifier
    child = _issue("CHILD", "Merged", "child", "project-a")
    child.parent_id = nested.identifier
    snapshot = {
        item.identifier: item
        for item in (root, nested, child)
    }
    landing = {
        "project_id": "project-a",
        "source": "epic-NESTED",
        "target": "epic-ROOT",
        "state": "landed",
        "durable": True,
        "evidence_revision": "landing-revision-1",
    }

    class Store:
        def landing_facts(self, *, project_id, task_id):
            assert project_id == "project-a"
            assert task_id == "NESTED"
            return (landing,)

    class StrictLandingFact:
        @classmethod
        def from_dict(cls, _raw):
            raise ValueError("landing proof requires kind")

    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.project_store = SimpleNamespace(get=lambda value: project)
    orchestrator.workflow_job_store = Store()
    orchestrator._epic_branch_for_issue = lambda issue: f"epic-{issue.identifier}"
    provider = SimpleNamespace(
        observe_branch_landing=lambda _repo, source, target: (
            source == "epic-NESTED" and target == "epic-ROOT"
        )
    )
    monkeypatch.setattr(
        orchestrator_module,
        "detect_provider",
        lambda *_args, **_kwargs: provider,
    )
    monkeypatch.setattr(
        orchestrator_module.importlib,
        "import_module",
        lambda _name: SimpleNamespace(LandingFact=StrictLandingFact),
    )

    nested_fact = Orchestrator._terminal_lifecycle_landing_evidence(
        orchestrator,
        nested,
        "project-a",
        snapshot,
    )
    child_fact = Orchestrator._terminal_lifecycle_landing_evidence(
        orchestrator,
        child,
        "project-a",
        snapshot,
    )

    assert nested_fact["source"] == child_fact["source"] == "epic-NESTED"
    assert nested_fact["target"] == child_fact["target"] == "epic-ROOT"
    assert nested_fact["observation"] == child_fact["observation"] == "landed"
    # The incomplete raw mapping has no LandingFact schema/proof/content hash,
    # so only the exact source/target SCM observation may authorize landing.
    assert nested_fact["facts"] == child_fact["facts"] == []


def test_lifecycle_forge_observation_requires_explicit_tristate_capability():
    orchestrator = Orchestrator.__new__(Orchestrator)

    class LegacyProvider:
        def list_merged_reviews(self, _slug):
            return []

        def find_pr_for_branch(self, _slug, _branch):
            return None

    class ObservingProvider:
        def __init__(self, observation):
            self.observation = observation

        def observe_branch_landing(self, _slug, _source, _target):
            return self.observation

    assert Orchestrator._epic_branch_landing_observation(
        orchestrator,
        LegacyProvider(),
        "org/repo",
        "epic-CHILD",
        "epic-PARENT",
    ) is None
    assert Orchestrator._epic_branch_landing_observation(
        orchestrator,
        ObservingProvider(False),
        "org/repo",
        "epic-CHILD",
        "epic-PARENT",
    ) is False
    assert Orchestrator._epic_branch_landing_observation(
        orchestrator,
        ObservingProvider(True),
        "org/repo",
        "epic-CHILD",
        "epic-PARENT",
    ) is True


def test_lifecycle_actual_orchestrator_propagates_scm_outage_without_status_write(
    tmp_path,
    monkeypatch,
):
    import httpx

    from oompah.scm import GitHubProvider

    project = SimpleNamespace(
        id="project-a",
        repo_url="https://github.com/org/repo",
        default_branch="main",
        access_token=None,
    )

    class ProjectStore(_LockStore):
        def get(self, project_id):
            return project if project_id == project.id else None

        @staticmethod
        def epic_branch_name(identifier):
            return f"epic-{identifier}"

    child = _issue("CHILD-OUTAGE", "Merged", "evidence", project.id)
    child.parent_id = "EPIC-OUTAGE"
    parent = _issue("EPIC-OUTAGE", "In Review", "parent", project.id)
    parent.issue_type = "epic"
    tracker = _Tracker([child, parent])
    tracker.metadata[child.identifier] = {}
    tracker.metadata[parent.identifier] = {}
    provider = GitHubProvider(access_token="test")

    def unavailable_api(*_args, **_kwargs):
        raise httpx.HTTPError("transport unavailable")

    provider._api = unavailable_api
    monkeypatch.setattr(
        "oompah.orchestrator.detect_provider",
        lambda *_args, **_kwargs: provider,
    )

    project_store = ProjectStore()
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.project_store = project_store
    orchestrator.workflow_job_store = SimpleNamespace()
    orchestrator._alerts = []
    validator = lambda issue, target, project_id: (
        Orchestrator._validate_terminal_transition(
            orchestrator,
            issue,
            target,
            project_id,
        )
    )
    landing = lambda issue, project_id, snapshot: (
        Orchestrator._terminal_lifecycle_landing_evidence(
            orchestrator,
            issue,
            project_id,
            snapshot,
        )
    )
    state_path = tmp_path / "service_state.json"
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=project_store,
        validate_terminal_transition=validator,
        lifecycle_landing_evidence=landing,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [(project.id, tracker)],
        max_attempts=1,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    assert result["exhausted"] == 1
    assert result["reconciled"] == 0
    assert tracker.status_updates == []
    assert child.state == "Merged"
    row = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]["records"][0]
    assert row["last_error"] == "lifecycle_validation_failed:OSError"


def test_lifecycle_v1_live_shaped_46_row_migration_converges_44_plus_2(
    tmp_path,
    monkeypatch,
):
    project_a = "project-a"
    project_b = "project-b"
    tracker_a = _Tracker([])
    tracker_b = _Tracker([])
    rows: list[tuple[str, str]] = []

    # Four stale Merged repair intents are superseded by exact current
    # PASS/Archived authority.
    for number in range(4):
        issue = _issue(f"ARCHIVED-{number}", "Archived", "evidence", project_a)
        issue.parent_id = "PARENT-A"
        tracker_a.issues.append(issue)
        tracker_a.metadata[issue.identifier] = {
            METADATA_KEY: TerminalAuditMetadata(
                pending_chain=[
                    _completed_terminal_authority(
                        issue, project_a, TargetState.ARCHIVED
                    )
                ]
            ).to_dict()
        }
        rows.append((project_a, issue.identifier))

    # Thirty-one children are valid from terminal parent facts in the complete
    # project snapshot, even when their native projection carries no project ID.
    terminal_parent = _issue("PARENT-A", "Archived", "parent", None)
    terminal_parent.issue_type = "epic"
    tracker_a.issues.append(terminal_parent)
    tracker_a.metadata[terminal_parent.identifier] = {}
    for number in range(31):
        issue = _issue(f"VALID-{number}", "Merged", "evidence", None)
        issue.parent_id = terminal_parent.identifier
        tracker_a.issues.append(issue)
        tracker_a.metadata[issue.identifier] = {}
        rows.append((project_a, issue.identifier))

    # Nine target-relative/nested landings remain valid before their parents
    # themselves reach a terminal state. Include two in another project to
    # prove aliases and landing facts cannot escape their source scope.
    for number in range(9):
        project_id = project_b if number >= 7 else project_a
        tracker = tracker_b if project_id == project_b else tracker_a
        parent_id = f"OPEN-PARENT-{project_id}-{number}"
        parent = _issue(parent_id, "In Review", "parent", None)
        parent.issue_type = "epic"
        issue = _issue(f"LANDED-{number}", "Merged", "evidence", None)
        issue.parent_id = parent.identifier
        tracker.issues.extend([parent, issue])
        tracker.metadata[parent.identifier] = {}
        tracker.metadata[issue.identifier] = {}
        rows.append((project_id, issue.identifier))

    # Only these structurally Done-only maintenance helpers require writes.
    for number in range(2):
        issue = _issue(f"REBASE-{number}", "Merged", "evidence", project_a)
        issue.title = "Rebase epic-MAINTENANCE onto main"
        issue.parent_id = "MAINTENANCE"
        tracker_a.issues.append(issue)
        tracker_a.metadata[issue.identifier] = {
            METADATA_KEY: TerminalAuditMetadata(
                unknown_fields={
                    TERMINAL_OVERRIDE_RECORDS_KEY: [
                        _applied_terminal_override(
                            issue, project_a, TargetState.DONE
                        )
                    ]
                }
            ).to_dict()
        }
        rows.append((project_a, issue.identifier))

    assert len(rows) == 46

    projects = {
        project_a: SimpleNamespace(
            id=project_a,
            repo_url="https://github.com/org/project-a",
            default_branch="main",
            access_token=None,
        ),
        project_b: SimpleNamespace(
            id=project_b,
            repo_url="https://github.com/org/project-b",
            default_branch="main",
            access_token=None,
        ),
    }

    class ProjectStore(_LockStore):
        def get(self, project_id):
            return projects.get(project_id)

        @staticmethod
        def epic_branch_name(identifier):
            return f"epic-{identifier}"

    class ExactLandingProvider:
        @staticmethod
        def observe_branch_landing(_repo, source, target):
            assert source.startswith("epic-")
            assert target == "main"
            return True

        @staticmethod
        def list_merged_reviews(_repo):
            return []

        @staticmethod
        def find_pr_for_branch(_repo, _branch):
            return None

    monkeypatch.setattr(
        "oompah.orchestrator.detect_provider",
        lambda *_args, **_kwargs: ExactLandingProvider(),
    )
    project_store = ProjectStore()
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.project_store = project_store
    orchestrator.workflow_job_store = SimpleNamespace()
    orchestrator._alerts = []

    def validate(issue, target, project_id):
        return Orchestrator._validate_terminal_transition(
            orchestrator,
            issue,
            target,
            project_id,
        )

    def landing(issue, project_id, snapshot):
        return Orchestrator._terminal_lifecycle_landing_evidence(
            orchestrator,
            issue,
            project_id,
            snapshot,
        )

    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps(_v1_exhausted_lifecycle_state(rows, started)),
        encoding="utf-8",
    )
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=project_store,
        validate_terminal_transition=validate,
        lifecycle_landing_evidence=landing,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [(project_a, tracker_a), (project_b, tracker_b)],
        batch_size=46,
        max_attempts=1,
        now=started,
    )

    assert result["status"] == "complete"
    assert result["processed"] == 46
    assert result["reconciled"] == 2
    assert result["failed"] == 0
    assert result["pending"] == 0
    assert result["exhausted"] == 0
    assert result["action_required"] is False
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY][
        "lifecycle_reconciliation"
    ]
    assert persisted["version"] == LIFECYCLE_RECONCILIATION_VERSION
    assert sum(row["outcome"] == "not_needed" for row in persisted["records"]) == 44
    assert sum(row["outcome"] == "reconciled" for row in persisted["records"]) == 2
    assert tracker_a.status_updates == [
        ("REBASE-0", "Done"),
        ("REBASE-1", "Done"),
    ]
    writes_before = tracker_a.set_calls + tracker_b.set_calls
    restarted = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=validate,
    )
    repeated = restarted.reconcile_lifecycle_batch(
        [(project_a, tracker_a), (project_b, tracker_b)],
        batch_size=46,
        max_attempts=1,
        now=started + timedelta(days=1),
    )
    assert repeated == result
    assert tracker_a.set_calls + tracker_b.set_calls == writes_before
    assert tracker_a.status_updates == [
        ("REBASE-0", "Done"),
        ("REBASE-1", "Done"),
    ]


def test_initialize_can_defer_lifecycle_reconciliation(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-DEFERRED")
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    result = enforcer.initialize(
        [("project-a", tracker)], defer_lifecycle_reconciliation=True
    )

    assert result["lifecycle_reconciliation"]["status"] == "idle"
    assert tracker.status_updates == []
    completed = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=1
    )
    assert completed["status"] == "complete"
    assert tracker.status_updates == [("CHILD-DEFERRED", "Done")]


def test_lifecycle_reconciliation_isolates_tracker_failures_and_retries(tmp_path):
    tracker = _Tracker([])
    for number in range(3):
        _legacy_lifecycle_issue(tracker, f"CHILD-{number}")
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    tracker.fail_status_updates = True
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    failed = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=3, now=started
    )
    assert failed["status"] == "degraded"
    assert failed["failed"] == 3
    assert all("lifecycle_repair_not_applied" in error for error in failed["errors"])
    assert tracker.status_updates == []

    tracker.fail_status_updates = False
    recovered = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        batch_size=3,
        now=started + timedelta(seconds=30),
    )
    assert recovered["status"] == "complete"
    assert recovered["reconciled"] == 3
    assert len(tracker.status_updates) == 3


def test_lifecycle_reconciliation_finishes_after_status_write_metadata_failure(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-METADATA")
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    tracker.fail_metadata_updates = True
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    failed = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=1, now=started
    )
    assert failed["status"] == "degraded"
    assert failed["failed"] == 1
    assert tracker.status_updates == [("CHILD-METADATA", "Done")]

    # The second pass sees Done and performs only the durable ledger/comment
    # half; it must not repeat the tracker status mutation.
    tracker.fail_metadata_updates = False
    recovered = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        batch_size=1,
        now=started + timedelta(seconds=30),
    )
    assert recovered["status"] == "complete"
    assert recovered["reconciled"] == 1
    assert tracker.status_updates == [("CHILD-METADATA", "Done")]


def test_lifecycle_progress_read_does_not_wait_for_slow_tracker_mutation(tmp_path):
    tracker = _SlowLifecycleTracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-SLOW")
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    worker = threading.Thread(
        target=enforcer.reconcile_lifecycle_batch,
        args=([("project-a", tracker)],),
        kwargs={"batch_size": 1},
    )
    worker.start()
    assert tracker.started.wait(timeout=2)
    started = time.monotonic()
    progress = enforcer.lifecycle_reconciliation_status()
    assert time.monotonic() - started < 0.2
    assert progress["status"] in {"migrating", "degraded"}
    tracker.release.set()
    worker.join(timeout=5)
    assert not worker.is_alive()


def test_lifecycle_legacy_hot_rows_exhaust_once_without_more_writes(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-HOT")
    tracker.issues[0].state = "Done"
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    persisted = {
        SERVICE_STATE_KEY: TerminalAuditEnforcementState(
            lifecycle_reconciliation={
                "version": 1,
                "status": "degraded",
                "records": [
                    {
                        "project_id": "project-a",
                        "task_id": "CHILD-HOT",
                        "status": "failed",
                        "attempts": 30_001,
                        "last_error": "lifecycle_metadata_not_finalized",
                        "conflict": "shared epic parent has not landed",
                        "updated_at": started.isoformat(),
                    }
                ],
                "cursor": 0,
                "updated_at": started.isoformat(),
                "errors": [],
            }
        ).to_dict()
    }
    writes: list[dict[str, object]] = []

    def load_state():
        return deepcopy(persisted)

    def save_state(update):
        writes.append(deepcopy(update))
        persisted.update(deepcopy(update))

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "unused.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        load_state=load_state,
        save_state=save_state,
        validate_terminal_transition=_shared_epic_conflict,
    )

    exhausted = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], now=started
    )
    assert exhausted["status"] == "degraded"
    assert exhausted["exhausted"] == 1
    assert exhausted["action_required"] is True
    assert exhausted["retry_pending"] == 0
    assert exhausted["next_retry_at"] is None
    assert len(writes) == 1

    unchanged = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], now=started + timedelta(days=1)
    )
    assert unchanged == exhausted
    assert len(writes) == 1
    assert tracker.status_updates == []


def test_lifecycle_pending_rows_are_not_starved_by_four_failed_rows(tmp_path):
    tracker = _Tracker([])
    for number in range(4):
        _legacy_lifecycle_issue(tracker, f"FAILED-{number}")
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    tracker.fail_metadata_updates = True
    failed = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=4, now=started
    )
    assert failed["failed"] == 4
    assert failed["retry_due"] == 0

    tracker.fail_metadata_updates = False
    _legacy_lifecycle_issue(tracker, "LATER-0")
    _legacy_lifecycle_issue(tracker, "LATER-1")
    progress = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        batch_size=2,
        now=started + timedelta(seconds=1),
    )

    assert progress["processed"] == 2
    assert progress["pending"] == 0
    assert progress["failed"] == 4
    assert tracker.status_updates[-2:] == [("LATER-0", "Done"), ("LATER-1", "Done")]


def test_lifecycle_retry_due_time_survives_restart_and_transient_recovers(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-RETRY")
    state_path = tmp_path / "service_state.json"
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    tracker.fail_status_updates = True
    first = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    failed = first.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        now=started,
        retry_backoff_seconds=10,
        retry_max_backoff_seconds=40,
    )
    assert failed["retry_pending"] == 1
    assert failed["next_retry_at"] == (started + timedelta(seconds=10)).isoformat()

    tracker.fail_status_updates = False
    restarted = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    not_due = restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        now=started + timedelta(seconds=9),
        retry_backoff_seconds=10,
        retry_max_backoff_seconds=40,
    )
    assert not_due["retry_due"] == 0
    assert tracker.status_updates == []

    recovered = restarted.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        now=started + timedelta(seconds=10),
        retry_backoff_seconds=10,
        retry_max_backoff_seconds=40,
    )
    assert recovered["status"] == "complete"
    assert recovered["reconciled"] == 1
    assert tracker.status_updates == [("CHILD-RETRY", "Done")]


def test_lifecycle_transient_scope_scan_outage_does_not_consume_retry(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-SCAN-OUTAGE")
    state_path = tmp_path / "service_state.json"
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    tracker.fail_status_updates = True
    first = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=2,
        retry_backoff_seconds=1,
        retry_max_backoff_seconds=2,
        now=started,
    )
    assert first["retry_pending"] == 1

    fetch_issues = tracker.fetch_all_issues_enriched

    def fail_scan():
        raise RuntimeError("transient project snapshot outage")

    tracker.fetch_all_issues_enriched = fail_scan
    during_outage = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=2,
        retry_backoff_seconds=1,
        retry_max_backoff_seconds=2,
        now=started + timedelta(seconds=1),
    )
    persisted = json.loads(state_path.read_text(encoding="utf-8"))[SERVICE_STATE_KEY]
    row = persisted["lifecycle_reconciliation"]["records"][0]
    assert during_outage["status"] == "degraded"
    assert during_outage["retry_pending"] == 1
    assert during_outage["exhausted"] == 0
    assert during_outage["action_required"] is False
    assert row["attempts"] == 1
    assert any(error.startswith("scan_failed:project-a") for error in during_outage["errors"])

    tracker.fetch_all_issues_enriched = fetch_issues
    tracker.fail_status_updates = False
    recovered = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=2,
        retry_backoff_seconds=1,
        retry_max_backoff_seconds=2,
        now=started + timedelta(seconds=2),
    )
    assert recovered["status"] == "complete"
    assert recovered["reconciled"] == 1
    assert tracker.status_updates == [("CHILD-SCAN-OUTAGE", "Done")]


def test_lifecycle_exhausted_absence_reopens_when_task_reappears(tmp_path):
    tracker = _Tracker([])
    state_path = tmp_path / "service_state.json"
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    state = TerminalAuditEnforcementState(
        lifecycle_reconciliation={
            "version": 1,
            "status": "migrating",
            "records": [
                {
                    "project_id": "project-a",
                    "task_id": "CHILD-REAPPEARS",
                    "status": "pending",
                    "attempts": 0,
                    "last_error": None,
                }
            ],
            "cursor": 0,
            "updated_at": started.isoformat(),
            "errors": [],
        }
    )
    state_path.write_text(
        json.dumps({SERVICE_STATE_KEY: state.to_dict()}), encoding="utf-8"
    )
    enforcer = TerminalAuditEnforcement(
        str(state_path),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )

    absent = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], max_attempts=1, now=started
    )
    assert absent["exhausted"] == 1
    assert absent["action_required"] is True

    _legacy_lifecycle_issue(tracker, "CHILD-REAPPEARS")
    recovered = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=1,
        now=started + timedelta(seconds=1),
    )
    assert recovered["status"] == "complete"
    assert recovered["action_required"] is False
    assert tracker.status_updates == [("CHILD-REAPPEARS", "Done")]


def test_lifecycle_exhaustion_reopens_after_relevant_operator_change(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-OPERATOR")
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=_shared_epic_conflict,
    )
    tracker.fail_status_updates = True
    enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=2,
        retry_backoff_seconds=1,
        retry_max_backoff_seconds=2,
        now=started,
    )
    exhausted = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=2,
        retry_backoff_seconds=1,
        retry_max_backoff_seconds=2,
        now=started + timedelta(seconds=1),
    )
    assert exhausted["exhausted"] == 1
    assert exhausted["action_required"] is True

    tracker.fail_status_updates = False
    tracker.issues[0].parent_id = "EPIC-REPAIRED"
    recovered = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        max_attempts=2,
        retry_backoff_seconds=1,
        retry_max_backoff_seconds=2,
        now=started + timedelta(seconds=2),
    )
    assert recovered["status"] == "complete"
    assert recovered["action_required"] is False
    assert tracker.status_updates == [("CHILD-OPERATOR", "Done")]


def test_lifecycle_non_external_failures_checkpoint_once_per_batch(tmp_path):
    tracker = _Tracker([])
    for number in range(4):
        _legacy_lifecycle_issue(tracker, f"VALIDATOR-{number}")
    persisted: dict[str, object] = {}
    writes: list[dict[str, object]] = []

    def load_state():
        return deepcopy(persisted)

    def save_state(update):
        writes.append(deepcopy(update))
        persisted.update(deepcopy(update))

    def broken_validator(*_args):
        raise RuntimeError("validator unavailable")

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "unused.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        load_state=load_state,
        save_state=save_state,
        validate_terminal_transition=broken_validator,
    )
    started = datetime(2026, 8, 5, tzinfo=timezone.utc)
    failed = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)], batch_size=4, now=started
    )
    assert failed["failed"] == 4
    assert len(writes) == 1

    enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        batch_size=4,
        now=started + timedelta(seconds=1),
    )
    assert len(writes) == 1


def test_lifecycle_external_effect_requires_successful_intent_checkpoint(tmp_path):
    tracker = _Tracker([])
    _legacy_lifecycle_issue(tracker, "CHILD-INTENT")
    save_attempts = 0

    def fail_save(_update):
        nonlocal save_attempts
        save_attempts += 1
        raise OSError("disk unavailable")

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "unused.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        load_state=lambda: {},
        save_state=fail_save,
        validate_terminal_transition=_shared_epic_conflict,
    )

    result = enforcer.reconcile_lifecycle_batch(
        [("project-a", tracker)],
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    assert result["failed"] == 1
    assert any("lifecycle_intent_persist_failed" in error for error in result["errors"])
    assert tracker.status_updates == []
    assert save_attempts == 2  # required intent attempt plus coalesced outcome attempt


def test_lifecycle_scheduler_uses_due_time_floor_and_coalesces_timer():
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    assert Orchestrator._terminal_lifecycle_schedule_delay(
        {"pending": 2}, now=now, floor_seconds=0.5
    ) == 0.5
    assert Orchestrator._terminal_lifecycle_schedule_delay(
        {
            "pending": 0,
            "retry_pending": 1,
            "next_retry_at": (now + timedelta(seconds=30)).isoformat(),
        },
        now=now,
        floor_seconds=1,
    ) == 30
    assert (
        Orchestrator._terminal_lifecycle_schedule_delay(
            {"pending": 0, "retry_pending": 0, "exhausted": 4},
            now=now,
            floor_seconds=1,
        )
        is None
    )

    class FakeFuture:
        def __init__(self):
            self._done = False
            self.callbacks = []

        def done(self):
            return self._done

        def add_done_callback(self, callback):
            self.callbacks.append(callback)

        def result(self):
            return None

        def complete(self):
            self._done = True
            for callback in list(self.callbacks):
                callback(self)

    class FakeTimer:
        def __init__(self, delay, callback):
            self.delay = delay
            self.callback = callback
            self._cancelled = False

        def cancelled(self):
            return self._cancelled

        def cancel(self):
            self._cancelled = True

    class FakeLoop:
        def __init__(self):
            self.futures = []
            self.timers = []

        def is_running(self):
            return True

        def run_in_executor(self, *_args):
            future = FakeFuture()
            self.futures.append(future)
            return future

        def call_later(self, delay, callback):
            timer = FakeTimer(delay, callback)
            self.timers.append(timer)
            return timer

    loop = FakeLoop()
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._stopping = False
    orchestrator._dispatch_loop = loop
    orchestrator._tick_pool = None
    orchestrator._terminal_lifecycle_future = None
    orchestrator._terminal_lifecycle_timer = None
    orchestrator._terminal_lifecycle_rediscovery_pending = False
    orchestrator._terminal_audit_enforcement = SimpleNamespace(
        lifecycle_reconciliation_status=lambda: {"pending": 1}
    )
    orchestrator.config = SimpleNamespace(
        terminal_lifecycle_reconciliation_scheduler_floor_seconds=2.0
    )

    orchestrator._schedule_terminal_lifecycle_reconciliation()
    orchestrator._schedule_terminal_lifecycle_reconciliation()
    assert len(loop.futures) == 1
    loop.futures[0].complete()
    assert len(loop.timers) == 1
    assert loop.timers[0].delay == 2.0

    orchestrator._schedule_terminal_lifecycle_reconciliation()
    assert len(loop.futures) == 1
    orchestrator._schedule_terminal_lifecycle_reconciliation(discover_new=True)
    assert len(loop.futures) == 2
    assert loop.timers[0].cancelled()


@pytest.mark.asyncio
async def test_lifecycle_discovery_event_during_active_scan_is_replayed():
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def run_batch():
        nonlocal calls
        with calls_lock:
            calls += 1
            call_number = calls
        if call_number == 1:
            first_started.set()
            assert release_first.wait(timeout=2)
        elif call_number == 2:
            second_started.set()

    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._stopping = False
    orchestrator._dispatch_loop = asyncio.get_running_loop()
    orchestrator._tick_pool = None
    orchestrator._terminal_lifecycle_future = None
    orchestrator._terminal_lifecycle_timer = None
    orchestrator._terminal_lifecycle_rediscovery_pending = False
    orchestrator._run_terminal_lifecycle_reconciliation_batch = run_batch
    orchestrator._terminal_audit_enforcement = SimpleNamespace(
        lifecycle_reconciliation_status=lambda: {
            "status": "degraded",
            "pending": 0,
            "retry_pending": 0,
            "exhausted": 4,
        }
    )
    orchestrator.config = SimpleNamespace(
        terminal_lifecycle_reconciliation_scheduler_floor_seconds=1.0
    )

    orchestrator._schedule_terminal_lifecycle_reconciliation(discover_new=True)
    assert await asyncio.to_thread(first_started.wait, 1)
    orchestrator._schedule_terminal_lifecycle_reconciliation(discover_new=True)
    orchestrator._schedule_terminal_lifecycle_reconciliation(discover_new=True)
    assert orchestrator._terminal_lifecycle_rediscovery_pending is True
    assert calls == 1

    release_first.set()
    assert await asyncio.to_thread(second_started.wait, 1)
    await asyncio.sleep(0)
    assert calls == 2
    assert orchestrator._terminal_lifecycle_rediscovery_pending is False
    assert orchestrator._terminal_lifecycle_timer is None


def test_lifecycle_worker_uses_configured_retry_policy():
    captured = {}

    def reconcile(scopes, **kwargs):
        captured["scopes"] = scopes
        captured.update(kwargs)
        return {"status": "degraded", "retry_pending": 1}

    enforcer = SimpleNamespace(reconcile_lifecycle_batch=reconcile, last_result={})
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.config = SimpleNamespace(
        terminal_lifecycle_reconciliation_batch_size=6,
        terminal_lifecycle_reconciliation_max_attempts=3,
        terminal_lifecycle_reconciliation_retry_backoff_seconds=7,
        terminal_lifecycle_reconciliation_max_backoff_seconds=70,
    )
    orchestrator._terminal_audit_enforcement = enforcer
    scopes = [("project-a", object())]
    orchestrator._terminal_audit_scopes = lambda: scopes
    orchestrator._maintenance_status = {}
    orchestrator._notify_state_only = lambda: None

    orchestrator._run_terminal_lifecycle_reconciliation_batch()

    assert captured["scopes"] == scopes
    assert captured["batch_size"] == 6
    assert captured["max_attempts"] == 3
    assert captured["retry_backoff_seconds"] == 7
    assert captured["retry_max_backoff_seconds"] == 70
    assert orchestrator._maintenance_status["terminal_lifecycle_reconciliation"] == {
        "status": "degraded",
        "retry_pending": 1,
    }


def test_terminal_audit_state_adapter_reports_failed_durable_write():
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._save_state = lambda **_updates: False

    with pytest.raises(OSError, match="not durably persisted"):
        orchestrator._save_state_for_terminal_audit({SERVICE_STATE_KEY: {}})


def test_recovery_applies_unapplied_override_while_still_in_validation(tmp_path):
    """An override intent must not deadlock when its status write was interrupted."""
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a", "project-a")])
    record = _pending_record("project-a", "TASK-1", "audit-pending")
    override = {
        "version": 1,
        "override_id": "override-crashed-before-status",
        "project_id": "project-a",
        "task_id": "TASK-1",
        "target_state": "Done",
        "evidence_fingerprint": record.evidence_fingerprint.to_dict(),
        "authorized_by": {"version": 1, "identity": "owner"},
        "reason": "restart recovery",
        "applied": False,
    }
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [override]},
        ).to_dict()
    }

    tracker.fail_status_updates = True
    enforcer = _enforcer(tmp_path)
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.issues[0].state == "In Validation"
    failed = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    assert failed.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY][0]["applied"] is False

    tracker.fail_status_updates = False
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.issues[0].state == "Done"
    assert tracker.status_updates == [("TASK-1", "Done")]
    recovered = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    assert recovered.pending_chain[0].request_state == RequestState.CANCELLED
    assert recovered.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY][0]["applied"] is True

    # Restart recovery is idempotent after both halves of the intent are durable.
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.status_updates == [("TASK-1", "Done")]


def test_recovery_retires_incompatible_merged_override_without_status_write(tmp_path):
    """Restart recovery must not replay a structurally impossible Merged override."""
    issue = _issue("CHILD-1", "In Validation", "evidence-a", "project-a")
    issue.parent_id = "EPIC-1"
    fingerprint = compute_issue_evidence_fingerprint(issue, "project-a")
    override = {
        "version": 1,
        "override_id": "override-incompatible-merged",
        "project_id": "project-a",
        "task_id": "CHILD-1",
        "target_state": TargetState.MERGED.value,
        "evidence_fingerprint": fingerprint.to_dict(),
        "authorized_by": {"version": 1, "identity": "owner"},
        "reason": "legacy recovery",
        "applied": False,
    }
    tracker = _Tracker([issue])
    tracker.metadata[issue.identifier] = {
        METADATA_KEY: TerminalAuditMetadata(
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [override]}
        ).to_dict()
    }

    def conflict(_issue, target, _project):
        if target == TargetState.MERGED:
            return (
                "Cannot transition shared-epic child CHILD-1 to Merged: parent "
                "review must land on configured target branch main first."
            )
        return None

    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service_state.json"),
        terminal_states=("Done",),
        project_store=_LockStore(),
        validate_terminal_transition=conflict,
    )
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []

    stored = TerminalAuditMetadata.from_dict(
        tracker.metadata[issue.identifier][METADATA_KEY]
    )
    repaired = stored.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY][0]
    assert issue.state == "In Validation"
    assert tracker.status_updates == []
    assert repaired["applied"] is True
    assert "parent review must land" in repaired["retired_reason"]


@pytest.mark.parametrize(
    ("concurrent_created_at", "concurrent_applied"),
    [
        ("2026-07-31T08:00:00Z", True),
        ("2026-07-31T10:00:00Z", False),
    ],
    ids=("older-retires", "newer-remains-authoritative"),
)
def test_override_recovery_classifies_concurrent_ledger_append(
    tmp_path,
    concurrent_created_at,
    concurrent_applied,
):
    """Finalization retires older appends and preserves only a newer authority."""
    record = _pending_record("project-a", "TASK-1", "audit-pending")
    first_override = {
        "version": 1,
        "override_id": "override-first",
        "project_id": "project-a",
        "task_id": "TASK-1",
        "target_state": "Done",
        "evidence_fingerprint": record.evidence_fingerprint.to_dict(),
        "authorized_by": {"version": 1, "identity": "owner"},
        "reason": "restart recovery",
        "created_at": "2026-07-31T09:00:00Z",
        "applied": False,
    }
    second_override = {
        **first_override,
        "override_id": "override-concurrent",
        "target_state": "Merged",
        "reason": "concurrent owner callback",
        "created_at": concurrent_created_at,
    }
    tracker = _OverrideRaceTracker(
        [_issue("TASK-1", "In Validation", "evidence-a", "project-a")],
        second_override,
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [first_override]},
        ).to_dict()
    }

    recovered = _enforcer(tmp_path).recover_pending_audits([("project-a", tracker)])
    assert recovered == []
    stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    overrides = stored.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY]
    assert [item["override_id"] for item in overrides] == [
        "override-first",
        "override-concurrent",
    ]
    assert overrides[0]["applied"] is True
    assert overrides[1]["applied"] is concurrent_applied
    assert tracker.status_updates == [("TASK-1", "Done")]

    if concurrent_applied:
        assert overrides[1]["retired_reason"] == "superseded_by_newer_override"
        assert _enforcer(tmp_path).recover_pending_audits(
            [("project-a", tracker)]
        ) == []
        assert tracker.status_updates == [("TASK-1", "Done")]
    else:
        assert "retired_reason" not in overrides[1]
        assert _enforcer(tmp_path).recover_pending_audits(
            [("project-a", tracker)]
        ) == []
        assert tracker.status_updates == [
            ("TASK-1", "Done"),
            ("TASK-1", "Merged"),
        ]
        finalized = TerminalAuditMetadata.from_dict(
            tracker.metadata["TASK-1"][METADATA_KEY]
        )
        assert finalized.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY][1][
            "applied"
        ] is True


def test_authority_key_uses_aware_time_then_stable_persisted_id():
    """Malformed/equal timestamps never fall back to input list position."""

    assert _authority_key("2026-07-31T10:00:00+02:00", ("intent-a",)) < (
        _authority_key("2026-07-31T09:00:00Z", ("intent-a",))
    )
    assert _authority_key("malformed", ("intent-a",)) < _authority_key(
        "malformed", ("intent-z",)
    )
    assert _authority_key("2026-07-31T09:00:00", ("intent-a",)) < _authority_key(
        None, ("intent-z",)
    )


@pytest.mark.parametrize("order", list(permutations(("a", "z"))))
@pytest.mark.parametrize(
    ("created_a", "created_z", "selected_id", "expected_status"),
    [
        (
            "2026-07-31T09:00:00Z",
            "2026-07-31T09:00:00Z",
            "override-z-done",
            "Done",
        ),
        ("malformed", None, "override-z-done", "Done"),
        (
            "2026-07-31T10:00:00Z",
            "2026-07-31T09:00:00Z",
            "override-a-merged",
            "Merged",
        ),
    ],
    ids=("equal", "malformed", "newest"),
)
def test_override_recovery_authority_is_permutation_invariant(
    tmp_path,
    order,
    created_a,
    created_z,
    selected_id,
    expected_status,
):
    """One override wins and every same-evidence sibling retires in one pass."""

    tracker = _Tracker([_issue("TASK-1", "In Validation", "ignored")])
    record = _pending_record("project-a", "TASK-1", "audit-pending")

    def _override(
        override_id: str,
        target: TargetState,
        created_at: object,
    ) -> dict[str, object]:
        raw = OverrideRecord(
            override_id=override_id,
            project_id="project-a",
            task_id="TASK-1",
            target_state=target,
            evidence_fingerprint=record.evidence_fingerprint,
            authorized_by=ContributorIdentity("owner", "oompah"),
            reason="restart recovery",
            created_at=created_at if isinstance(created_at, str) else None,
        ).to_dict()
        if created_at is None:
            raw.pop("created_at", None)
        raw["applied"] = False
        return raw

    candidates = {
        "a": _override("override-a-merged", TargetState.MERGED, created_a),
        "z": _override("override-z-done", TargetState.DONE, created_z),
    }
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={
                TERMINAL_OVERRIDE_RECORDS_KEY: [candidates[key] for key in order]
            },
        ).to_dict()
    }

    enforcer = _enforcer(tmp_path)
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.status_updates == [("TASK-1", expected_status)]

    stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    by_id = {
        item["override_id"]: item
        for item in stored.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY]
    }
    assert all(item["applied"] is True for item in by_id.values())
    loser_id = ({"override-a-merged", "override-z-done"} - {selected_id}).pop()
    assert by_id[loser_id]["retired_reason"] == "superseded_by_newer_override"
    assert "retired_reason" not in by_id[selected_id]

    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.status_updates == [("TASK-1", expected_status)]


@pytest.mark.parametrize("order", list(permutations(("a", "z"))))
@pytest.mark.parametrize(
    ("created_a", "created_z", "selected_audit", "expected_status"),
    [
        (
            "2026-07-31T09:00:00Z",
            "2026-07-31T09:00:00Z",
            "audit-z-done",
            "Done",
        ),
        ("malformed", None, "audit-z-done", "Done"),
        (
            "2026-07-31T10:00:00Z",
            "2026-07-31T09:00:00Z",
            "audit-a-merged",
            "Merged",
        ),
    ],
    ids=("equal", "malformed", "newest"),
)
def test_result_recovery_authority_is_permutation_invariant(
    tmp_path,
    order,
    created_a,
    created_z,
    selected_audit,
    expected_status,
):
    """Recovery performs only the deterministic winning terminal write."""

    tracker = _Tracker([_issue("TASK-1", "In Validation", "ignored")])
    done_record = _pending_record(
        "project-a",
        "TASK-1",
        "audit-z-done",
        request_state=RequestState.COMPLETED,
    )
    merged_record = replace(
        done_record,
        audit_id="audit-a-merged",
        target_state=TargetState.MERGED,
    )

    def _intent(
        record: TerminalAuditRecord,
        attempt_id: str,
        created_at: object,
    ) -> dict[str, object]:
        intent: dict[str, object] = {
            "project_id": "project-a",
            "task_id": "TASK-1",
            "audit_id": record.audit_id,
            "attempt_id": attempt_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
            "status": record.target_state.value,
            "audit_ids": [record.audit_id],
            "applied": False,
        }
        if created_at is not None:
            intent["created_at"] = created_at
        return intent

    intents = {
        "a": _intent(merged_record, "attempt-a", created_a),
        "z": _intent(done_record, "attempt-z", created_z),
    }
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[merged_record, done_record],
            unknown_fields={
                TERMINAL_RESULT_INTENTS_KEY: [intents[key] for key in order]
            },
        ).to_dict()
    }

    enforcer = _enforcer(tmp_path)
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.status_updates == [("TASK-1", expected_status)]

    stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    by_audit = {
        item["audit_id"]: item
        for item in stored.unknown_fields[TERMINAL_RESULT_INTENTS_KEY]
    }
    assert all(item["applied"] is True for item in by_audit.values())
    loser_audit = ({"audit-a-merged", "audit-z-done"} - {selected_audit}).pop()
    assert by_audit[loser_audit]["retired_reason"] == "superseded_by_newer_intent"
    assert by_audit[selected_audit]["retired_reason"] == "recovered_current_intent"
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.status_updates == [("TASK-1", expected_status)]


def test_restart_replays_unacknowledged_result_status_and_is_idempotent(tmp_path):
    """A PASS persisted before its tracker write is recovered exactly once."""
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
    record = _pending_record("project-a", "TASK-1", "audit-pass", request_state=RequestState.COMPLETED)
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={
                TERMINAL_RESULT_INTENTS_KEY: [
                    {
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "audit_id": record.audit_id,
                        "attempt_id": "attempt-pass",
                        "target_state": "Done",
                        "evidence_fingerprint": record.evidence_fingerprint.digest,
                        "status": "Done",
                        "audit_ids": [record.audit_id],
                        "applied": False,
                    }
                ]
            },
        ).to_dict()
    }

    tracker.fail_status_updates = True
    enforcer = _enforcer(tmp_path)
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    failed = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    assert failed.unknown_fields[TERMINAL_RESULT_INTENTS_KEY][0]["applied"] is False
    assert tracker.issues[0].state == "In Validation"

    tracker.fail_status_updates = False
    recovered = enforcer.recover_pending_audits([("project-a", tracker)])
    assert recovered == []
    assert tracker.issues[0].state == "Done"
    applied = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    assert applied.unknown_fields[TERMINAL_RESULT_INTENTS_KEY][0]["applied"] is True

    updates_before_replay = tracker.set_calls
    assert enforcer.recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.set_calls == updates_before_replay


def test_recovery_retires_result_intent_after_task_evidence_changes(tmp_path):
    """A completed result for an obsolete task revision must never be replayed."""
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
    record = _pending_record(
        "project-a", "TASK-1", "audit-pass", request_state=RequestState.COMPLETED
    )
    tracker.issues[0].description = "requirements updated"
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={
                TERMINAL_RESULT_INTENTS_KEY: [
                    {
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "audit_id": record.audit_id,
                        "attempt_id": "attempt-pass",
                        "target_state": "Done",
                        "evidence_fingerprint": record.evidence_fingerprint.digest,
                        "status": "Done",
                        "audit_ids": [record.audit_id],
                        "applied": False,
                    }
                ]
            },
        ).to_dict()
    }

    assert _enforcer(tmp_path).recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.issues[0].state == "In Validation"
    assert tracker.status_updates == []
    stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    intent = stored.unknown_fields[TERMINAL_RESULT_INTENTS_KEY][0]
    assert intent["applied"] is True
    assert intent["retired_reason"] == "current_evidence_mismatch"
    assert stored.pending_chain[0].request_state == RequestState.COMPLETED


def test_native_markdown_restart_replays_current_result_intent(tmp_path):
    """Fresh native adapters derive the same persisted revision fingerprint."""

    repo = tmp_path / "native-repo"
    tracker = _native_tracker(repo)
    issue = tracker.create_issue(
        "Native recovery",
        description="requirements",
        initial_status="In Validation",
    )
    tracker.set_metadata_field(
        issue.identifier,
        "oompah.integration",
        _native_integration(head_sha="a" * 40).to_dict(),
    )
    current = tracker.fetch_issue_detail(issue.identifier)
    assert current is not None
    fingerprint = compute_issue_evidence_fingerprint(current, "project-a")
    record = TerminalAuditRecord(
        audit_id="audit-native-pass",
        project_id="project-a",
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
    )
    intent = {
        "project_id": "project-a",
        "task_id": issue.identifier,
        "audit_id": record.audit_id,
        "attempt_id": "attempt-native-pass",
        "target_state": "Done",
        "evidence_fingerprint": fingerprint.digest,
        "status": "Done",
        "audit_ids": [record.audit_id],
        "applied": False,
        "created_at": "2026-07-31T09:00:00Z",
    }
    TerminalAuditMetadataStore(tracker, _LockStore(), "project-a").write(
        issue.identifier,
        TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={TERMINAL_RESULT_INTENTS_KEY: [intent]},
        ),
    )

    restarted = _native_tracker(repo)
    assert _enforcer(tmp_path / "restart").recover_pending_audits(
        [("project-a", restarted)]
    ) == []
    refreshed = restarted.fetch_issue_detail(issue.identifier)
    assert refreshed is not None
    assert refreshed.state == "Done"
    stored = TerminalAuditMetadata.from_dict(
        restarted.get_metadata(issue.identifier)[METADATA_KEY]
    )
    assert stored.unknown_fields[TERMINAL_RESULT_INTENTS_KEY][0]["applied"] is True


def test_native_markdown_source_revision_retires_stale_override_without_write(
    tmp_path,
):
    """A revised native source head cannot inherit an older owner override."""

    repo = tmp_path / "native-repo"
    tracker = _native_tracker(repo)
    issue = tracker.create_issue(
        "Native override recovery",
        description="requirements",
        initial_status="In Validation",
    )
    tracker.set_metadata_field(
        issue.identifier,
        "oompah.integration",
        _native_integration(head_sha="a" * 40).to_dict(),
    )
    audited = tracker.fetch_issue_detail(issue.identifier)
    assert audited is not None
    audited_fingerprint = compute_issue_evidence_fingerprint(audited, "project-a")
    record = TerminalAuditRecord(
        audit_id="audit-native-pending",
        project_id="project-a",
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=audited_fingerprint,
        request_state=RequestState.PENDING,
    )
    override = OverrideRecord(
        override_id="override-native-stale",
        project_id="project-a",
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=audited_fingerprint,
        authorized_by=ContributorIdentity("owner", "oompah"),
        reason="recover interrupted override",
        created_at="2026-07-31T09:00:00Z",
    ).to_dict()
    override["applied"] = False
    TerminalAuditMetadataStore(tracker, _LockStore(), "project-a").write(
        issue.identifier,
        TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={TERMINAL_OVERRIDE_RECORDS_KEY: [override]},
        ),
    )

    tracker.set_metadata_field(
        issue.identifier,
        "oompah.integration",
        _native_integration(head_sha="c" * 40).to_dict(),
    )
    restarted = _native_tracker(repo)
    revised = restarted.fetch_issue_detail(issue.identifier)
    assert revised is not None
    assert compute_issue_evidence_fingerprint(revised, "project-a") != audited_fingerprint

    assert _enforcer(tmp_path / "restart").recover_pending_audits(
        [("project-a", restarted)]
    ) == []
    refreshed = restarted.fetch_issue_detail(issue.identifier)
    assert refreshed is not None
    assert refreshed.state == "In Validation"
    assert not (
        repo / ".oompah" / "tasks" / "done" / f"{issue.identifier}.md"
    ).exists()
    stored = TerminalAuditMetadata.from_dict(
        restarted.get_metadata(issue.identifier)[METADATA_KEY]
    )
    retired = stored.unknown_fields[TERMINAL_OVERRIDE_RECORDS_KEY][0]
    assert retired["applied"] is True
    assert retired["retired_reason"] == "evidence_mismatch"
    assert stored.pending_chain[0].request_state == RequestState.PENDING


def test_recovery_selects_one_newest_current_result_intent(tmp_path):
    """Competing completed intents cannot replay multiple terminal statuses."""
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
    first = _pending_record(
        "project-a", "TASK-1", "audit-first", request_state=RequestState.COMPLETED
    )
    second = replace(first, audit_id="audit-second")
    def _intent(record: TerminalAuditRecord, attempt_id: str) -> dict[str, object]:
        return {
            "project_id": "project-a",
            "task_id": "TASK-1",
            "audit_id": record.audit_id,
            "attempt_id": attempt_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
            "status": "Done",
            "audit_ids": [record.audit_id],
            "applied": False,
        }

    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[first, second],
            unknown_fields={
                TERMINAL_RESULT_INTENTS_KEY: [
                    _intent(first, "attempt-first"),
                    _intent(second, "attempt-second"),
                ]
            },
        ).to_dict()
    }

    assert _enforcer(tmp_path).recover_pending_audits([("project-a", tracker)]) == []
    assert tracker.issues[0].state == "Done"
    assert tracker.status_updates == [("TASK-1", "Done")]
    stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
    intents = stored.unknown_fields[TERMINAL_RESULT_INTENTS_KEY]
    assert [intent["applied"] for intent in intents] == [True, True]
    assert intents[0]["retired_reason"] == "superseded_by_newer_intent"
    assert intents[1]["retired_reason"] == "recovered_current_intent"


def test_recovery_rebuilds_finalization_failure_counts_without_accumulating(tmp_path):
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
    tracker.fail_status_updates = True
    record = _pending_record(
        "project-a", "TASK-1", "audit-pass", request_state=RequestState.COMPLETED
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(
            pending_chain=[record],
            unknown_fields={
                TERMINAL_RESULT_INTENTS_KEY: [
                    {
                        "project_id": "project-a",
                        "task_id": "TASK-1",
                        "audit_id": record.audit_id,
                        "attempt_id": "attempt-pass",
                        "target_state": record.target_state.value,
                        "evidence_fingerprint": record.evidence_fingerprint.digest,
                        "status": "Done",
                        "audit_ids": [record.audit_id],
                        "applied": False,
                    }
                ]
            },
        ).to_dict()
    }
    enforcer = _enforcer(tmp_path)

    enforcer.recover_pending_audits([("project-a", tracker)])
    assert enforcer.finalization_failure_counts == {"project-a": 1}

    enforcer.recover_pending_audits([("project-a", tracker)])
    assert enforcer.finalization_failure_counts == {"project-a": 1}


def test_dispatch_cas_does_not_resurrect_completed_audit(tmp_path):
    """A stale dispatch snapshot cannot overwrite a PASS completion."""
    tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a", "project-a")])
    completed = _pending_record(
        "project-a", "TASK-1", "audit-pass", request_state=RequestState.COMPLETED
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[completed]).to_dict()
    }
    stale = replace(completed, request_state=RequestState.IN_PROGRESS)
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    try:
        store = TerminalAuditMetadataStore(tracker, orchestrator.project_store, "project-a")
        assert orchestrator._audit_update_record(store, tracker.issues[0], stale) is False
        stored = TerminalAuditMetadata.from_dict(tracker.metadata["TASK-1"][METADATA_KEY])
        assert stored.pending_chain[0].request_state == RequestState.COMPLETED
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


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


def test_orchestrator_recovery_converges_live_queue_metrics_and_health(tmp_path):
    """A recovery scan cannot rehydrate a terminal or superseded audit row."""

    live = _pending_record("project-a", "TASK-1", "audit-live")
    stale_terminal = _pending_record("project-a", "TASK-2", "audit-terminal")
    tracker = _Tracker(
        [
            _issue("TASK-1", "In Validation", "evidence-a"),
            _issue("TASK-2", "Done", "evidence-a"),
        ]
    )
    tracker.metadata["TASK-1"] = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[live]).to_dict()
    }
    state_path = tmp_path / "service_state.json"
    state_path.write_text(
        json.dumps(
            {
                SERVICE_STATE_KEY: TerminalAuditEnforcementState(
                    pending_audits=[
                        PendingAudit.from_record(live),
                        PendingAudit.from_record(stale_terminal),
                    ]
                ).to_dict()
            }
        ),
        encoding="utf-8",
    )
    orchestrator = Orchestrator(
        ServiceConfig(workspace_root=str(tmp_path / "workspace")),
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(state_path),
    )
    try:
        orchestrator._terminal_audit_scopes = lambda: [("project-a", tracker)]
        # Simulate the stale running gauge that a prior process left behind.
        orchestrator._terminal_audit_metrics.record_running(
            "project-a", "TASK-2", "audit-terminal"
        )

        orchestrator._run_terminal_audit_enforcement()
        first = orchestrator.get_snapshot()

        assert first["terminal_audit_enforcement"]["pending_audits"] == 1
        assert first["terminal_audit"]["queued"] == 1
        assert first["terminal_audit"]["running"] == 0
        assert first["terminal_audit"]["oldest_queue_task_id"] == "TASK-1"
        assert first["terminal_audit_health"]["pending_count"] == 1
        assert first["terminal_audit_health"]["in_progress_count"] == 0

        orchestrator._run_terminal_audit_enforcement()
        second = orchestrator.get_snapshot()
        assert second["terminal_audit"]["queued_total"] == 1
        assert second["terminal_audit"]["stale_discarded"] == 0
        assert second["terminal_audit_health"]["pending_count"] == 1
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


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

    def test_multi_request_audit_chain_recovers_only_current_revision(self, tmp_path):
        """Only the pending record for the current native evidence is actionable."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-a")])
        tracker.issues[0].description = "requirements v2"
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
        
        assert [item.audit_id for item in enforcer.pending_audits] == ["audit-2"]
        
        # Recovery is idempotent: repeated pass doesn't duplicate
        restarted = _enforcer(tmp_path)
        restarted.initialize([("project-a", tracker)])
        assert [item.audit_id for item in restarted.pending_audits] == ["audit-2"]

    def test_stale_fingerprint_superseded_record_not_requeued(self, tmp_path):
        """Superseded records with old evidence are not requeued."""
        tracker = _Tracker([_issue("TASK-1", "In Validation", "evidence-b")])
        tracker.issues[0].description = "requirements updated"
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
