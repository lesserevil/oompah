"""Regression coverage for direct-owner watchdog protection (OOMPAH-707)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.implementation_workflow import (
    ImplementationAction,
    ImplementationWorkflowHandler,
)
from oompah.implementation_workflow_adapter import (
    OrchestratorImplementationEffects,
    ProductionImplementationWorkflowBackend,
)
from oompah.models import Issue, Project, RunningEntry, WorkflowDefinition
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore, RecoveryPublicationError
from oompah.server import app
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    TransitionOutcome,
    TransitionPhase,
    issue_authority_version,
)
from oompah.validation_resource_lease import (
    ValidationLeaseOwner,
    ValidationResourceLease,
)
from oompah.workflow_jobs import WorkflowJobSpec
from oompah.workflow_fact_model import FactDomain
from oompah.workflow_worker import DurableWorkflowWorker, WorkflowRunDisposition


def _project_store(tmp_path) -> tuple[ProjectStore, Project]:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(
        id="proj-1",
        name="example",
        repo_url="https://github.com/example/repo.git",
        repo_path=str(tmp_path / "repo"),
        branch="main",
        status_actor_login="alice",
    )
    store._projects[project.id] = project
    return store, project


def _issue(state: str = "In Progress") -> Issue:
    return Issue(
        id="task-1",
        identifier="OOMPAH-1",
        title="Direct owner work",
        description="A complete task description.",
        state=state,
        issue_type="task",
        labels=["human-only"],
        project_id="proj-1",
    )


def _orchestrator(tmp_path) -> tuple[Orchestrator, MagicMock, Issue]:
    store, project = _project_store(tmp_path)
    orch = Orchestrator(
        config=ServiceConfig(owner_claim_ttl_hours=48, duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker = MagicMock()
    issue = _issue()
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_issue_states_by_ids.return_value = [issue]
    tracker.update_issue.side_effect = lambda _identifier, **fields: setattr(
        issue, "state", fields["status"]
    )
    orch._project_trackers[project.id] = tracker
    orch._fetch_all_in_progress_issues = MagicMock(return_value=[])
    return orch, tracker, issue


def _committed_outcome(issue: Issue, status: str) -> TransitionOutcome:
    return TransitionOutcome(
        transition_id=f"transition-{status.lower().replace(' ', '-')}",
        project_id=str(issue.project_id),
        task_id=issue.identifier,
        disposition=TransitionDisposition.APPLIED,
        reason_code="test.committed",
        observed_status=status,
        observed_version=f"version-{status.lower().replace(' ', '-')}",
        requested_status=status,
        applied_status=status,
    )


def test_live_direct_owner_claim_survives_repeated_orphan_scans(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)

    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
    )
    for _ in range(5):
        orch._reset_orphaned_in_progress([issue])

    tracker.update_issue.assert_not_called()
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) == claim
    snapshot = orch.get_snapshot()["owner_claims"]
    assert snapshot == [
        {
            "claim_id": claim.claim_id,
            "issue_id": issue.id,
            "project_id": issue.project_id,
            "owner_login": "alice",
            "ownership_source": "direct_owner",
            "claimed_at": snapshot[0]["claimed_at"],
            "expires_at": snapshot[0]["expires_at"],
            "age_seconds": snapshot[0]["age_seconds"],
            "expires_in_seconds": snapshot[0]["expires_in_seconds"],
            "is_expired": False,
            "renewable": True,
            "retirement_pending": False,
        }
    ]


def test_owner_claim_ignores_same_tracker_id_owned_by_another_project(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    foreign_issue = Issue(
        id=issue.id,
        identifier=issue.identifier,
        title="Foreign task with a colliding tracker id",
        description="Another managed project owns this runtime.",
        state="In Progress",
        issue_type="task",
        project_id="proj-2",
    )
    orch.state.running[issue.id] = RunningEntry(
        worker_task=None,
        identifier=foreign_issue.identifier,
        issue=foreign_issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
    )

    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
    )

    assert claim.project_id == issue.project_id
    assert orch.state.running[issue.id].issue.project_id == "proj-2"


def test_owner_claim_is_restored_from_durable_service_state(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
    )

    restarted_store, _project = _project_store(tmp_path)
    restarted = Orchestrator(
        config=ServiceConfig(owner_claim_ttl_hours=48, duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=restarted_store,
        state_path=str(tmp_path / "service_state.json"),
    )

    restored = restarted._owner_claim_for_issue(issue.id, issue.project_id)
    assert restored is not None
    assert restored.claim_id == claim.claim_id
    assert restored.owner_login == "alice"


def test_owner_claim_retirement_marker_survives_restart(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-pending-across-restart",
    )
    assert orch.mark_owner_claim_retirement_pending(
        issue_id=issue.id,
        project_id=issue.project_id,
        expected_claim_id=claim.claim_id,
    )

    restarted_store, _project = _project_store(tmp_path)
    restarted = Orchestrator(
        config=ServiceConfig(
            owner_claim_ttl_hours=48,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=restarted_store,
        state_path=str(tmp_path / "service_state.json"),
    )

    restored = restarted._owner_claim_for_issue(issue.id, issue.project_id)
    assert restored is not None
    assert restored.claim_id == claim.claim_id
    assert restored.retirement_pending is True
    projection = restarted._owner_claim_snapshot(restored, now=time.time())
    assert projection["retirement_pending"] is True


def test_committed_status_transition_retires_exact_claim_durably(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-before-terminal-commit",
    )
    outcome = _committed_outcome(issue, "Done")
    transition_service = SimpleNamespace(
        execute=AsyncMock(return_value=outcome),
    )

    with (
        patch.object(
            orch,
            "_task_transition_service",
            return_value=transition_service,
        ),
        patch.object(orch, "_notify_state_only") as notify,
    ):
        committed = asyncio.run(
            orch._transition_issue_status_async(
                issue,
                "Done",
                project_id=issue.project_id,
                tracker=tracker,
                reason_code="test.owner_claim_terminal_commit",
            )
        )

    assert committed is outcome
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    state = json.loads((tmp_path / "service_state.json").read_text())
    assert state["owner_claims"] == {}
    notify.assert_called_once_with()
    transition_service.execute.assert_awaited_once()
    assert claim.claim_id == "claim-before-terminal-commit"


def test_status_transition_without_owner_claim_runtime_still_commits():
    orch = Orchestrator.__new__(Orchestrator)
    issue = _issue()
    tracker = MagicMock()
    outcome = _committed_outcome(issue, "Done")
    transition_service = SimpleNamespace(
        execute=AsyncMock(return_value=outcome),
    )

    with patch.object(
        orch,
        "_task_transition_service",
        return_value=transition_service,
    ):
        committed = asyncio.run(
            orch._transition_issue_status_async(
                issue,
                "Done",
                project_id=issue.project_id,
                tracker=tracker,
                reason_code="test.no_owner_claim_runtime",
            )
        )

    assert committed is outcome
    transition_service.execute.assert_awaited_once()


def test_committed_status_transition_preserves_aba_replacement_claim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    original = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-captured-before-commit",
    )
    outcome = _committed_outcome(issue, "Done")
    replacement: dict[str, object] = {}

    async def commit_after_replacement(_intent):
        replacement["claim"] = orch.grant_owner_claim(
            issue_id=issue.id,
            project_id=issue.project_id,
            owner_login="alice",
            claim_id="claim-installed-during-commit",
        )
        return outcome

    transition_service = SimpleNamespace(
        execute=AsyncMock(side_effect=commit_after_replacement),
    )
    with (
        patch.object(
            orch,
            "_task_transition_service",
            return_value=transition_service,
        ),
        patch.object(orch, "_notify_state_only") as notify,
    ):
        committed = asyncio.run(
            orch._transition_issue_status_async(
                issue,
                "Done",
                project_id=issue.project_id,
                tracker=tracker,
                reason_code="test.owner_claim_aba_commit",
            )
        )

    assert committed is outcome
    current = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert current is replacement["claim"]
    assert current.claim_id != original.claim_id
    state = json.loads((tmp_path / "service_state.json").read_text())
    persisted = next(iter(state["owner_claims"].values()))
    assert persisted["claim_id"] == "claim-installed-during-commit"
    notify.assert_not_called()


def test_enforce_status_commit_schedules_exact_direct_owner_revocation(tmp_path):
    from oompah.implementation_workflow import ImplementationAction

    orch, tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-revoked-after-commit",
    )
    outcome = _committed_outcome(issue, "Done")
    transition_service = SimpleNamespace(
        execute=AsyncMock(return_value=outcome),
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="revocation-job")
    )

    with (
        patch.object(
            orch,
            "_task_transition_service",
            return_value=transition_service,
        ),
        patch.object(orch, "_notify_state_only"),
    ):
        asyncio.run(
            orch._transition_issue_status_async(
                issue,
                "Done",
                project_id=issue.project_id,
                tracker=tracker,
                reason_code="test.owner_claim_enforce_commit",
            )
        )

    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["project_id"] == issue.project_id
    assert scheduled["identifier"] == issue.identifier
    assert scheduled["action"] is ImplementationAction.AUTHORITY_REVOCATION
    assert scheduled["payload"]["authority_kind"] == "direct_owner"
    assert scheduled["payload"]["claim_id"] == claim.claim_id
    assert scheduled["payload"]["owner_id"] == claim.owner_login
    assert scheduled["payload"]["expected_status"] == "Done"
    assert scheduled["expected_evidence_revision"] == outcome.observed_version
    pending = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert pending is not None
    assert pending.claim_id == claim.claim_id
    assert pending.retirement_pending is True


@pytest.mark.parametrize("committed_status", ["Done", "Open", "Needs Human"])
def test_failed_revocation_enqueue_is_repaired_by_live_reconciliation(
    tmp_path, committed_status
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = committed_status
    tracker.fetch_all_issues.return_value = [issue]
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-retried-after-enqueue-failure",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        side_effect=(
            RuntimeError("workflow store unavailable"),
            SimpleNamespace(job_id="reconciled-revocation"),
        )
    )

    with patch.object(orch, "_notify_state_only") as notify:
        initially_scheduled = asyncio.run(
            orch._retire_owner_claim_after_status_commit(
                issue=issue,
                project_id=issue.project_id,
                claim=claim,
                observed_status=issue.state,
                observed_version="postcommit-version",
            )
        )
        with patch.object(
            orch,
            "_has_active_owner_claim_revocation",
            return_value=False,
        ):
            reconciled = orch._reconcile_inactive_owner_claims()

    assert initially_scheduled is False
    assert reconciled == 1
    assert orch._schedule_implementation_workflow_event.call_count == 2
    repair = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert repair["payload"]["authority_kind"] == "direct_owner"
    assert repair["payload"]["claim_id"] == claim.claim_id
    assert repair["payload"]["reconciliation_nonce"]
    assert repair["expected_evidence_revision"]
    pending = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert pending is not None
    assert pending.claim_id == claim.claim_id
    assert pending.retirement_pending is True
    notify.assert_called_once_with()


def test_live_reconciliation_waits_for_active_exact_revocation(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "In Validation"
    tracker.fetch_all_issues.return_value = [issue]
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-with-active-revocation",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()

    with (
        patch.object(
            orch,
            "_has_active_owner_claim_revocation",
            return_value=True,
        ),
        patch.object(orch, "_notify_state_only") as notify,
    ):
        reconciled = orch._reconcile_inactive_owner_claims()

    assert reconciled == 0
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is claim
    orch._schedule_implementation_workflow_event.assert_not_called()
    notify.assert_not_called()


def test_live_reconciliation_preserves_unmarked_open_preclaim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    tracker.fetch_all_issues.return_value = [issue]
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="valid-open-preclaim",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()

    assert orch._reconcile_inactive_owner_claims() == 0
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is claim
    orch._schedule_implementation_workflow_event.assert_not_called()


def test_durable_validation_transition_retires_exact_captured_claim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    head = "a" * 40
    issue.state = "Ready to Integrate"
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch=issue.identifier,
        head_sha=head,
    )
    tracker.fetch_issue_detail.return_value = issue
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-submitted-to-ready",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="claim-revocation")
    )
    job = SimpleNamespace(
        action="validation_submission",
        project_id=issue.project_id,
        task_id=issue.identifier,
        expected_head_sha=head,
        payload={
            "owner_claim_id": claim.claim_id,
            "owner_login": claim.owner_login,
        },
    )

    assert orch._retire_owner_claim_after_validation_transition(job)

    pending = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert pending is not None
    assert pending.claim_id == claim.claim_id
    assert pending.retirement_pending is True
    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["action"].value == "authority_revocation"
    assert scheduled["payload"]["claim_id"] == claim.claim_id
    assert scheduled["payload"]["expected_status"] == "Ready to Integrate"
    assert scheduled["expected_head_sha"] == head
    authority_source = orch._workflow_shadow_sources(issue)[
        FactDomain.IMPLEMENTATION_AUTHORITY
    ]
    assert authority_source(issue) == {"lease_expires_at": None}


def test_production_validation_job_hands_standalone_owner_to_ready_workflow(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    head = "c" * 40
    issue.integration = IntegrationRecord(
        state="ready",
        mode="standalone",
        task_branch=issue.identifier,
        head_sha=head,
    )
    tracker.fetch_issue_detail.return_value = issue
    orch.project_store.remote_branch_head = MagicMock(return_value=head)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-production-validation",
    )
    orch.config.parallel_epic_children_enabled = False
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="exact-owner-revocation")
    )
    submission = orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            generation="production-validation-generation",
            action=ImplementationAction.VALIDATION_SUBMISSION.value,
            idempotency_key="production-validation-submission",
            payload={
                "expected_status": issue.state,
                "owner_claim_id": claim.claim_id,
                "owner_login": claim.owner_login,
                "head_sha": head,
                "work_branch": issue.identifier,
            },
            expected_evidence_revision=issue_authority_version(issue),
            expected_head_sha=head,
        )
    )
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    handler = ImplementationWorkflowHandler(
        ProductionImplementationWorkflowBackend(effects)
    )
    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={ImplementationAction.VALIDATION_SUBMISSION.value: handler},
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="production-validation-worker",
        retry_delay_seconds=0.01,
    )

    result = asyncio.run(worker.run_once())

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert orch.workflow_job_store.get(submission.job_id).state.value == "completed"
    assert issue.state == "Ready to Integrate"
    pending = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert pending is not None
    assert pending.claim_id == claim.claim_id
    assert pending.retirement_pending is True
    authority_source = orch._workflow_shadow_sources(issue)[
        FactDomain.IMPLEMENTATION_AUTHORITY
    ]
    assert authority_source(issue) == {"lease_expires_at": None}
    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["action"] is ImplementationAction.AUTHORITY_REVOCATION
    assert scheduled["payload"]["claim_id"] == claim.claim_id
    effects.receipts.close()


def test_validation_restart_replays_precommit_intent_and_retires_exact_claim(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    head = "f" * 40
    issue.integration = IntegrationRecord(
        state="ready",
        mode="standalone",
        task_branch=issue.identifier,
        head_sha=head,
    )
    tracker.fetch_issue_detail.return_value = issue
    orch.project_store.remote_branch_head = MagicMock(return_value=head)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-crash-after-ready-write",
    )
    orch.config.parallel_epic_children_enabled = False
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    submission = orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            generation="validation-crash-after-ready-write",
            action=ImplementationAction.VALIDATION_SUBMISSION.value,
            idempotency_key="validation-crash-after-ready-write",
            payload={
                "expected_status": issue.state,
                "owner_claim_id": claim.claim_id,
                "owner_login": claim.owner_login,
                "head_sha": head,
                "work_branch": issue.identifier,
            },
            expected_evidence_revision=issue_authority_version(issue),
            expected_head_sha=head,
        )
    )
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={
            ImplementationAction.VALIDATION_SUBMISSION.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="validation-precheckpoint-crash-worker",
        retry_delay_seconds=0.01,
    )

    def commit_ready_then_die(_identifier, **fields):
        issue.state = fields["status"]
        raise SystemExit("simulated death after Ready tracker commit")

    tracker.update_issue.side_effect = commit_ready_then_die
    with pytest.raises(SystemExit, match="after Ready tracker commit"):
        asyncio.run(worker.run_once())

    stranded = orch.workflow_job_store.get(submission.job_id)
    assert issue.state == "Ready to Integrate"
    # asyncio.run quarantines the still-owned worker while propagating this
    # artificial BaseException. A real process death leaves the persisted
    # transition_intent phase; both preserve the same checkpoint payload.
    assert stranded.phase == "quarantined"
    assert stranded.checkpoint["transition_intent"]["expected_status"] == (
        "In Progress"
    )
    assert "transition" not in stranded.checkpoint
    current = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert current is not None
    assert current.claim_id == claim.claim_id
    assert current.retirement_pending is False

    orch._close_owned_persistent_stores()
    restarted_store, project = _project_store(tmp_path)
    restarted = Orchestrator(
        config=ServiceConfig(
            owner_claim_ttl_hours=48,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=restarted_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker.reset_mock()
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_issue_states_by_ids.return_value = [issue]
    tracker.update_issue.side_effect = lambda _identifier, **fields: setattr(
        issue, "state", fields["status"]
    )
    restarted._project_trackers[project.id] = tracker
    restarted.config.parallel_epic_children_enabled = False
    restarted.workflow_runtime = SimpleNamespace(enforce=True)
    restarted._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="restarted-exact-owner-revocation")
    )
    # A full process restart makes the old transition owner unavailable. Move
    # only the journal clock beyond its bounded claim TTL to model that fact.
    restarted.task_transition_journal._clock = lambda: time.time() + 301
    assert restarted.workflow_job_store.recover_abandoned() == 1
    restarted_effects = OrchestratorImplementationEffects(
        restarted,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    restarted_worker = DurableWorkflowWorker(
        store=restarted.workflow_job_store,
        handlers={
            ImplementationAction.VALIDATION_SUBMISSION.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(restarted_effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): restarted._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="validation-precheckpoint-recovery-worker",
        retry_delay_seconds=0.01,
    )

    result = asyncio.run(restarted_worker.run_once())

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert restarted.workflow_job_store.get(submission.job_id).state.value == (
        "completed"
    )
    tracker.update_issue.assert_not_called()
    pending = restarted._owner_claim_for_issue(issue.id, issue.project_id)
    assert pending is not None
    assert pending.claim_id == claim.claim_id
    assert pending.retirement_pending is True
    scheduled = restarted._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["action"] is ImplementationAction.AUTHORITY_REVOCATION
    assert scheduled["payload"]["claim_id"] == claim.claim_id
    restarted._close_owned_persistent_stores()


def test_stale_production_validation_job_retains_direct_owner_claim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    accepted_head = "d" * 40
    issue.integration = IntegrationRecord(
        state="ready",
        mode="standalone",
        task_branch=issue.identifier,
        head_sha=accepted_head,
    )
    tracker.fetch_issue_detail.return_value = issue
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-stale-validation-keeps",
    )
    orch.config.parallel_epic_children_enabled = False
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()
    stale = orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            generation="stale-production-validation",
            action=ImplementationAction.VALIDATION_SUBMISSION.value,
            idempotency_key="stale-production-validation",
            payload={
                "expected_status": issue.state,
                "owner_claim_id": claim.claim_id,
                "owner_login": claim.owner_login,
                "head_sha": accepted_head,
            },
            expected_evidence_revision=issue_authority_version(issue),
            expected_head_sha=accepted_head,
        )
    )
    # A newer accepted head invalidates the queued submission before any
    # transition/finalizer authority is exercised.
    issue.integration = replace(issue.integration, head_sha="e" * 40)
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={
            ImplementationAction.VALIDATION_SUBMISSION.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="stale-production-validation-worker",
    )

    result = asyncio.run(worker.run_once())

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert orch.workflow_job_store.get(stale.job_id).state.value == "superseded"
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is claim
    assert claim.retirement_pending is False
    orch._schedule_implementation_workflow_event.assert_not_called()
    effects.receipts.close()


def test_stale_validation_transition_cannot_revoke_aba_owner_claim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    head = "b" * 40
    issue.state = "Ready to Integrate"
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch=issue.identifier,
        head_sha=head,
    )
    tracker.fetch_issue_detail.return_value = issue
    old_claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-submitted-before-aba",
    )
    assert orch.release_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        expected_claim_id=old_claim.claim_id,
    )
    replacement = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="bob",
        claim_id="claim-replacement-after-aba",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()
    stale_job = SimpleNamespace(
        action="validation_submission",
        project_id=issue.project_id,
        task_id=issue.identifier,
        expected_head_sha=head,
        payload={
            "owner_claim_id": old_claim.claim_id,
            "owner_login": old_claim.owner_login,
        },
    )

    assert not orch._retire_owner_claim_after_validation_transition(stale_job)
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is replacement
    orch._schedule_implementation_workflow_event.assert_not_called()


@pytest.mark.parametrize(
    ("state", "expected_head"),
    (("In Progress", "a" * 40), ("Ready to Integrate", "b" * 40)),
)
def test_validation_handoff_retains_claim_until_status_and_head_commit(
    tmp_path, state, expected_head
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = state
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch=issue.identifier,
        head_sha="a" * 40,
    )
    tracker.fetch_issue_detail.return_value = issue
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-before-validation-commit",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()
    job = SimpleNamespace(
        action="validation_submission",
        project_id=issue.project_id,
        task_id=issue.identifier,
        expected_head_sha=expected_head,
        payload={
            "owner_claim_id": claim.claim_id,
            "owner_login": claim.owner_login,
        },
    )

    assert not orch._retire_owner_claim_after_validation_transition(job)
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is claim
    assert claim.retirement_pending is False
    orch._schedule_implementation_workflow_event.assert_not_called()


def test_live_reconciliation_retires_marked_claim_after_return_to_in_progress(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    tracker.fetch_all_issues.return_value = [issue]
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="pending-claim-after-reopen",
    )
    assert orch.mark_owner_claim_retirement_pending(
        issue_id=issue.id,
        project_id=issue.project_id,
        expected_claim_id=claim.claim_id,
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="pending-in-progress-revocation")
    )

    with (
        patch.object(
            orch,
            "_has_active_owner_claim_revocation",
            return_value=False,
        ),
        patch.object(orch, "_notify_state_only"),
    ):
        reconciled = orch._reconcile_inactive_owner_claims()

    assert reconciled == 1
    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["payload"]["claim_id"] == claim.claim_id
    assert scheduled["payload"]["expected_status"] == "In Progress"


def test_restart_recovers_claim_retirement_from_committed_transition_journal(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-at-postcommit-crash-boundary",
    )

    with patch.object(
        orch,
        "_retire_owner_claim_after_status_commit",
        new=AsyncMock(side_effect=SystemExit("simulated process death")),
    ):
        with pytest.raises(SystemExit, match="simulated process death"):
            asyncio.run(
                orch._transition_issue_status_async(
                    issue,
                    "Open",
                    project_id=issue.project_id,
                    tracker=tracker,
                    reason_code="test.owner_claim_postcommit_crash",
                )
            )

    assert issue.state == "Open"
    stranded = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert stranded is not None
    assert stranded.claim_id == claim.claim_id
    assert stranded.retirement_pending is False

    restarted_store, project = _project_store(tmp_path)
    restarted = Orchestrator(
        config=ServiceConfig(
            owner_claim_ttl_hours=48,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=restarted_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker.fetch_all_issues.return_value = [issue]
    restarted._project_trackers[project.id] = tracker

    assert restarted._reconcile_inactive_owner_claims() == 1
    assert restarted._owner_claim_for_issue(issue.id, issue.project_id) is None
    persisted = json.loads((tmp_path / "service_state.json").read_text())
    assert persisted["owner_claims"] == {}


def test_transition_requested_before_new_claim_cannot_retire_that_claim(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    intent = orch._build_transition_intent(
        issue,
        "Open",
        project_id=issue.project_id,
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="test.owner_claim_request_order",
        originating_job="test-owner-claim-request-order",
        evidence_generation=None,
        exact_head=None,
        idempotency_key="test-owner-claim-request-order",
    )
    started = orch.task_transition_journal.begin(intent)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-created-after-transition-request",
    )
    outcome = TransitionOutcome(
        transition_id=started.transition_id,
        project_id=str(issue.project_id),
        task_id=issue.identifier,
        disposition=TransitionDisposition.APPLIED,
        reason_code="test.owner_claim_request_order",
        observed_status="Open",
        observed_version="postcommit-version",
        requested_status="Open",
        applied_status="Open",
    )
    orch.task_transition_journal.append(
        started.transition_id,
        TransitionPhase.APPLIED,
        outcome.reason_code,
        outcome,
    )

    assert not orch._claim_has_committed_retirement_transition(
        issue=issue,
        project_id=issue.project_id,
        claim=claim,
    )


def _commit_validation_submission_transition(
    orch, issue, *, captured_claim_id: str
):
    submission = orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            generation=f"validation-{captured_claim_id}",
            action="validation_submission",
            idempotency_key=f"validation:{captured_claim_id}",
            payload={"owner_claim_id": captured_claim_id},
        )
    )
    intent = orch._build_transition_intent(
        issue,
        "Ready to Integrate",
        project_id=issue.project_id,
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="implementation.validation_submission",
        originating_job=submission.job_id,
        evidence_generation=submission.generation,
        exact_head=None,
        idempotency_key=f"validation-transition:{captured_claim_id}",
    )
    started = orch.task_transition_journal.begin(intent)
    issue.state = "Ready to Integrate"
    outcome = TransitionOutcome(
        transition_id=started.transition_id,
        project_id=str(issue.project_id),
        task_id=issue.identifier,
        disposition=TransitionDisposition.APPLIED,
        reason_code="transition.applied",
        observed_status=issue.state,
        observed_version="ready-version",
        requested_status=issue.state,
        applied_status=issue.state,
    )
    orch.task_transition_journal.append(
        started.transition_id,
        TransitionPhase.APPLIED,
        outcome.reason_code,
        outcome,
    )
    return submission


def test_retirement_scan_handles_request_and_commit_order_interleaving(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    preclaim_intent = orch._build_transition_intent(
        issue,
        "Open",
        project_id=issue.project_id,
        actor="oompah",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="test.delayed_preclaim_transition",
        originating_job="delayed-preclaim-transition",
        evidence_generation=None,
        exact_head=None,
        idempotency_key="delayed-preclaim-transition",
    )
    preclaim = orch.task_transition_journal.begin(preclaim_intent)
    assert preclaim.claim_token is not None
    assert orch.task_transition_journal.release(
        str(issue.project_id), issue.identifier, preclaim.claim_token
    )
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-between-request-and-commit",
    )
    _commit_validation_submission_transition(
        orch,
        issue,
        captured_claim_id=claim.claim_id,
    )

    # Commit the older request after the valid validation transition. Journal
    # results are event-sequence ordered, so this older request is encountered
    # first even though its request timestamp predates the owner claim.
    delayed = TransitionOutcome(
        transition_id=preclaim.transition_id,
        project_id=str(issue.project_id),
        task_id=issue.identifier,
        disposition=TransitionDisposition.APPLIED,
        reason_code="test.delayed_preclaim_transition",
        observed_status="Open",
        observed_version="delayed-preclaim-version",
        requested_status="Open",
        applied_status="Open",
    )
    orch.task_transition_journal.append(
        preclaim.transition_id,
        TransitionPhase.APPLIED,
        delayed.reason_code,
        delayed,
    )

    assert orch._claim_has_committed_retirement_transition(
        issue=issue,
        project_id=issue.project_id,
        claim=claim,
    )


def test_postcommit_recovery_retires_exact_submitting_claim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-captured-by-submission",
    )
    _commit_validation_submission_transition(
        orch,
        issue,
        captured_claim_id=claim.claim_id,
    )
    tracker.fetch_all_issues.return_value = [issue]
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="recovered-exact-revocation")
    )

    with (
        patch.object(
            orch,
            "_has_active_owner_claim_revocation",
            return_value=False,
        ),
        patch.object(orch, "_notify_state_only"),
    ):
        assert orch._reconcile_inactive_owner_claims() == 1

    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["payload"]["claim_id"] == claim.claim_id


def test_postcommit_recovery_preserves_replacement_claim_from_aba(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    old_claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-captured-before-replacement",
    )
    assert orch.release_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        expected_claim_id=old_claim.claim_id,
    )
    replacement = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="bob",
        claim_id="claim-replacement-before-ready-commit",
    )
    _commit_validation_submission_transition(
        orch,
        issue,
        captured_claim_id=old_claim.claim_id,
    )
    tracker.fetch_all_issues.return_value = [issue]
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()

    assert orch._reconcile_inactive_owner_claims() == 0
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is replacement
    assert replacement.retirement_pending is False
    orch._schedule_implementation_workflow_event.assert_not_called()


def test_active_owner_claim_revocation_lookup_is_exact(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            generation="revocation-generation",
            action="authority_revocation",
            idempotency_key="owner-claim-revocation",
            payload={
                "authority_kind": "direct_owner",
                "claim_id": "claim-active-revocation",
            },
        )
    )

    assert orch._has_active_owner_claim_revocation(
        issue=issue,
        project_id=str(issue.project_id),
        claim_id="claim-active-revocation",
    )
    assert not orch._has_active_owner_claim_revocation(
        issue=issue,
        project_id=str(issue.project_id),
        claim_id="replacement-claim",
    )


def test_live_reconciliation_retries_after_tracker_refresh_recovers(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Done"
    tracker.fetch_all_issues.side_effect = (
        RuntimeError("terminal refresh unavailable"),
        [issue],
    )
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-after-refresh-recovery",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="refresh-recovery-revocation")
    )

    with (
        patch.object(
            orch,
            "_has_active_owner_claim_revocation",
            return_value=False,
        ),
        patch.object(orch, "_notify_state_only"),
    ):
        assert orch._reconcile_inactive_owner_claims() == 0
        assert orch._reconcile_inactive_owner_claims() == 1

    scheduled = orch._schedule_implementation_workflow_event.call_args.kwargs
    assert scheduled["payload"]["claim_id"] == claim.claim_id


def test_expired_owner_claim_is_pruned_during_restore(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    expired = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        ttl_hours=-1,
        claim_id="expired-before-restart",
    )
    assert expired.expires_at < time.time()

    restarted_store, _project = _project_store(tmp_path)
    restarted = Orchestrator(
        config=ServiceConfig(
            owner_claim_ttl_hours=48,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=restarted_store,
        state_path=str(tmp_path / "service_state.json"),
    )

    assert restarted.state.owner_claims == {}
    state = json.loads((tmp_path / "service_state.json").read_text())
    assert state["owner_claims"] == {}


def test_snapshot_prunes_expired_owner_claim_from_memory_and_disk(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        ttl_hours=-1,
        claim_id="expired-before-snapshot",
    )

    snapshot = orch.get_snapshot()

    assert snapshot["owner_claims"] == []
    assert orch.state.owner_claims == {}
    state = json.loads((tmp_path / "service_state.json").read_text())
    assert state["owner_claims"] == {}


def test_owner_claim_persistence_failures_roll_back_grant_and_release(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)

    with patch.object(orch, "_save_state", return_value=False):
        with pytest.raises(OSError, match="not durably persisted"):
            orch.grant_owner_claim(
                issue_id=issue.id,
                project_id=issue.project_id,
                owner_login="alice",
                claim_id="claim-that-never-commits",
            )
    assert orch.state.owner_claims == {}

    committed = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-before-release-failure",
    )
    state_before_release = json.loads(
        (tmp_path / "service_state.json").read_text()
    )
    with patch.object(orch, "_save_state", return_value=False):
        with pytest.raises(OSError, match="retirement marker"):
            orch.mark_owner_claim_retirement_pending(
                issue_id=issue.id,
                project_id=issue.project_id,
                expected_claim_id=committed.claim_id,
            )
    assert committed.retirement_pending is False
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is committed

    with patch.object(orch, "_save_state", return_value=False):
        with pytest.raises(OSError, match="release was not persisted"):
            orch.release_owner_claim(
                issue_id=issue.id,
                project_id=issue.project_id,
                expected_claim_id=committed.claim_id,
            )

    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is committed
    assert json.loads((tmp_path / "service_state.json").read_text()) == (
        state_before_release
    )


def test_expired_or_released_claim_returns_task_to_existing_recovery(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    expired = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        ttl_hours=-1,
    )

    orch._reset_orphaned_in_progress([issue])

    tracker.update_issue.assert_called_once_with(issue.identifier, status="Open")
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    state = json.loads((tmp_path / "service_state.json").read_text())
    assert state["owner_claims"] == {}
    assert expired.expires_at < time.time()

    tracker.reset_mock()
    issue.state = "In Progress"
    orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
    )
    assert orch.release_owner_claim(issue_id=issue.id, project_id=issue.project_id)
    orch._reset_orphaned_in_progress([issue])
    tracker.update_issue.assert_called_once_with(issue.identifier, status="Open")


def test_scheduler_orphan_behavior_is_unchanged_without_direct_claim(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)

    orch._reset_orphaned_in_progress([issue])

    tracker.update_issue.assert_called_once_with(issue.identifier, status="Open")
    assert orch.get_snapshot()["owner_claims"] == []


def test_owner_claim_and_watchdog_are_serialized_so_newer_owner_work_wins(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    watchdog_started = threading.Event()
    permit_watchdog_reset = threading.Event()
    updates: list[str] = []

    def update_issue(_identifier, *, status, **_kwargs):
        if status == "Open":
            watchdog_started.set()
            assert permit_watchdog_reset.wait(timeout=3)
        updates.append(status)

    tracker.update_issue.side_effect = update_issue
    watchdog = threading.Thread(
        target=orch._reset_orphaned_in_progress,
        args=([issue],),
    )
    watchdog.start()
    assert watchdog_started.wait(timeout=3)

    def claim_and_mark_direct_work():
        with orch.project_store.project_write_lock(issue.project_id):
            orch.grant_owner_claim(
                issue_id=issue.id,
                project_id=issue.project_id,
                owner_login="alice",
            )
            tracker.update_issue(issue.identifier, status="In Progress")

    owner = threading.Thread(target=claim_and_mark_direct_work)
    owner.start()
    permit_watchdog_reset.set()
    watchdog.join(timeout=3)
    owner.join(timeout=3)

    assert not watchdog.is_alive()
    assert not owner.is_alive()
    assert updates == ["Open", "In Progress"]
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None


def test_owner_claim_api_marks_direct_work_and_release_is_authorized(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    tracker.fetch_issue_detail.return_value = issue
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json={"actor_login": "alice", "ttl_hours": 24})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["active"] is True
        assert payload["ownership_source"] == "direct_owner"
        assert payload["owner_login"] == "alice"
        tracker.update_issue.assert_called_once_with(issue.identifier, status="In Progress")
        tracker.add_label.assert_not_called()
        tracker.remove_label.assert_not_called()

        observed = client.get(endpoint)
        assert observed.status_code == 200
        assert observed.json()["active"] is True

        released = client.request("DELETE", endpoint, json={"actor_login": "alice"})
        assert released.status_code == 200
        assert released.json() == {"released": True}
        assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None

        issue.state = "Done"
        rejected = client.post(endpoint, json={"actor_login": "alice"})
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "invalid_state"


def test_owner_claim_releases_request_lock_for_status_writer(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    tracker.fetch_issue_detail.return_value = issue
    project_lock = orch.project_store.project_write_lock(issue.project_id)
    writer_acquired: list[bool] = []

    def update_issue(_identifier, **fields):
        acquired = project_lock.acquire(timeout=0.5)
        writer_acquired.append(acquired)
        if acquired:
            try:
                issue.state = fields["status"]
            finally:
                project_lock.release()

    tracker.update_issue.side_effect = update_issue
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(
            endpoint,
            json={"actor_login": "alice", "ttl_hours": 24},
        )

    assert response.status_code == 200, response.text
    assert writer_acquired == [True]
    assert issue.state == "In Progress"
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None


def test_owner_claim_api_enforce_routes_claim_and_release_through_workflow(tmp_path):
    from oompah.implementation_workflow import ImplementationAction

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(
        enforce=True,
        health_snapshot=lambda: {},
        projections=lambda: (),
        liveness_controller=orch.workflow_controller,
    )
    orch._schedule_implementation_workflow_event = MagicMock(
        side_effect=(
            SimpleNamespace(job_id="claim-job", generation="claim-generation"),
            SimpleNamespace(job_id="release-job", generation="release-generation"),
        )
    )
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        claimed = client.post(endpoint, json={"actor_login": "alice"})
        assert claimed.status_code == 202, claimed.text
        claim_call = orch._schedule_implementation_workflow_event.call_args_list[
            0
        ].kwargs
        assert claim_call["action"] is ImplementationAction.DIRECT_OWNER_CLAIM
        assert claim_call["payload"]["owner_id"] == "alice"
        assert claim_call["payload"]["issue_id"] == issue.id
        tracker.update_issue.assert_not_called()

        external_claim = orch.grant_owner_claim(
            issue_id=issue.id,
            project_id=issue.project_id,
            owner_login="alice",
        )
        released = client.request(
            "DELETE", endpoint, json={"actor_login": "alice"}
        )
        retiring = client.get(endpoint)

    assert released.status_code == 202, released.text
    release_call = orch._schedule_implementation_workflow_event.call_args_list[
        1
    ].kwargs
    assert release_call["action"] is ImplementationAction.AUTHORITY_REVOCATION
    assert release_call["payload"]["claim_id"] == external_claim.claim_id
    pending = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert pending is not None
    assert pending.claim_id == external_claim.claim_id
    assert pending.retirement_pending is True
    assert retiring.status_code == 200
    assert retiring.json()["active"] is False
    assert retiring.json()["retirement_pending"] is True


def test_enforce_owner_claim_atomically_promotes_backlog_with_owner_authority(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Backlog"
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(enforce=True)

    def enqueue_owner_claim(**kwargs):
        payload = dict(kwargs["payload"])
        return orch.workflow_job_store.enqueue(
            WorkflowJobSpec(
                project_id=kwargs["project_id"],
                task_id=kwargs["identifier"],
                generation=f"direct-owner:{payload['claim_id']}",
                action=kwargs["action"].value,
                idempotency_key=f"owner-claim:{payload['claim_id']}",
                payload=payload,
                expected_evidence_revision=kwargs["expected_evidence_revision"],
                expected_head_sha=kwargs["expected_head_sha"],
                priority=kwargs["priority"],
            )
        )

    orch._schedule_implementation_workflow_event = MagicMock(
        side_effect=enqueue_owner_claim
    )
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        accepted = client.post(endpoint, json={"actor_login": "alice"})

    assert accepted.status_code == 202, accepted.text
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="backlog-owner-claim-worker",
    )

    result = asyncio.run(worker.run_once())

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert issue.state == "In Progress"
    claim = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert claim is not None
    assert claim.owner_login == "alice"
    durable = orch.workflow_job_store.get(result.job_id)
    transition_intent = durable.checkpoint["transition_intent"]
    assert transition_intent["expected_status"] == "Backlog"
    assert transition_intent["requested_status"] == "In Progress"
    assert transition_intent["actor"] == "alice"
    assert transition_intent["authority"] == "project_owner"
    assert transition_intent["evidence_generation"] == claim.claim_id
    effects.receipts.close()


@pytest.mark.parametrize(
    ("actor", "claim_id", "reason_code"),
    (
        ("mallory", "claim-live", "transition.owner_claim_actor_mismatch"),
        ("alice", "claim-invented", "transition.owner_claim_generation_mismatch"),
    ),
)
def test_backlog_commit_rejects_inexact_live_owner_authority(
    tmp_path,
    actor,
    claim_id,
    reason_code,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Backlog"
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    live = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-live",
    )
    intent = TransitionIntent(
        project_id=str(issue.project_id),
        task_id=issue.identifier,
        expected_status="Backlog",
        expected_version=issue_authority_version(issue),
        requested_status="In Progress",
        actor=actor,
        authority=TransitionAuthority.PROJECT_OWNER,
        reason_code="implementation.direct_owner_claim",
        idempotency_key=f"owner-claim-inexact:{actor}:{claim_id}",
        originating_job=f"owner-claim-job:{actor}:{claim_id}",
        evidence_generation=claim_id,
    )

    outcome = asyncio.run(
        orch._task_transition_service(issue.project_id, tracker).execute(intent)
    )

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == reason_code
    assert issue.state == "Backlog"
    tracker.update_issue.assert_not_called()
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is live


def test_enforce_owner_claim_release_after_intent_cannot_commit_backlog(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Backlog"
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(enforce=True)

    def enqueue_owner_claim(**kwargs):
        payload = dict(kwargs["payload"])
        return orch.workflow_job_store.enqueue(
            WorkflowJobSpec(
                project_id=kwargs["project_id"],
                task_id=kwargs["identifier"],
                generation=f"direct-owner:{payload['claim_id']}",
                action=kwargs["action"].value,
                idempotency_key=f"owner-claim:{payload['claim_id']}",
                payload=payload,
                expected_evidence_revision=kwargs["expected_evidence_revision"],
                expected_head_sha=kwargs["expected_head_sha"],
                priority=kwargs["priority"],
            )
        )

    orch._schedule_implementation_workflow_event = MagicMock(
        side_effect=enqueue_owner_claim
    )
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        accepted = client.post(endpoint, json={"actor_login": "alice"})

    assert accepted.status_code == 202, accepted.text
    job = orch.workflow_job_store.get(accepted.json()["job_id"])
    claim_id = job.payload["claim_id"]
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )

    def release_after_intent(phase, _job):
        if phase == "transition_intent":
            assert orch.release_owner_claim(
                issue_id=issue.id,
                project_id=issue.project_id,
                expected_claim_id=claim_id,
            )

    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="released-owner-claim-worker",
        phase_observer=release_after_intent,
    )

    result = asyncio.run(worker.run_once())

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert issue.state == "Backlog"
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    tracker.update_issue.assert_not_called()
    durable = orch.workflow_job_store.get(job.job_id)
    assert durable.state.value == "exhausted"
    assert durable.checkpoint["transition_compensation"]["claim_id"] == claim_id
    effects.receipts.close()


def test_enforce_owner_claim_delete_after_intent_cannot_commit_backlog(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Backlog"
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(
        enforce=True,
        health_snapshot=lambda: {},
        projections=lambda: (),
        liveness_controller=orch.workflow_controller,
    )

    def schedule_owner_workflow(**kwargs):
        if kwargs["action"] is ImplementationAction.AUTHORITY_REVOCATION:
            return SimpleNamespace(
                job_id="delete-retirement-job",
                generation="delete-retirement-generation",
            )
        payload = dict(kwargs["payload"])
        return orch.workflow_job_store.enqueue(
            WorkflowJobSpec(
                project_id=kwargs["project_id"],
                task_id=kwargs["identifier"],
                generation=f"direct-owner:{payload['claim_id']}",
                action=kwargs["action"].value,
                idempotency_key=f"owner-claim:{payload['claim_id']}",
                payload=payload,
                expected_evidence_revision=kwargs["expected_evidence_revision"],
                expected_head_sha=kwargs["expected_head_sha"],
                priority=kwargs["priority"],
            )
        )

    orch._schedule_implementation_workflow_event = MagicMock(
        side_effect=schedule_owner_workflow
    )
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        accepted = client.post(endpoint, json={"actor_login": "alice"})

    assert accepted.status_code == 202, accepted.text
    job = orch.workflow_job_store.get(accepted.json()["job_id"])
    claim_id = job.payload["claim_id"]
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )

    async def delete_after_intent(phase, _job):
        if phase != "transition_intent":
            return
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            response = await asyncio.to_thread(
                client.request,
                "DELETE",
                endpoint,
                json={"actor_login": "alice"},
            )
        assert response.status_code == 202, response.text
        retiring = orch._owner_claim_for_issue(issue.id, issue.project_id)
        assert retiring is not None
        assert retiring.claim_id == claim_id
        assert retiring.retirement_pending is True

    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="retiring-owner-claim-worker",
        phase_observer=delete_after_intent,
    )

    result = asyncio.run(worker.run_once())

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert issue.state == "Backlog"
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    tracker.update_issue.assert_not_called()
    durable = orch.workflow_job_store.get(job.job_id)
    assert durable.state.value == "exhausted"
    compensation = durable.checkpoint["transition_compensation"]
    assert compensation["claim_id"] == claim_id
    assert compensation["reason_code"] == "transition.owner_claim_retiring"
    revocation = orch._schedule_implementation_workflow_event.call_args_list[-1]
    assert revocation.kwargs["action"] is ImplementationAction.AUTHORITY_REVOCATION
    assert revocation.kwargs["payload"]["claim_id"] == claim_id
    effects.receipts.close()


def test_enforce_backlog_owner_claim_still_rejects_non_owner(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Backlog"
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        rejected = client.post(endpoint, json={"actor_login": "mallory"})

    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "owner_claim_unauthorized"
    orch._schedule_implementation_workflow_event.assert_not_called()
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None


@pytest.mark.parametrize("protected_status", ["In Validation", "Done"])
def test_enforce_owner_claim_keeps_protected_states_unclaimable(
    tmp_path,
    protected_status,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = protected_status
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock()
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        rejected = client.post(endpoint, json={"actor_login": "alice"})

    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "invalid_state"
    orch._schedule_implementation_workflow_event.assert_not_called()
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None


def test_backlog_owner_claim_restart_replays_exact_owner_transition(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Backlog"
    tracker.fetch_issue_detail.return_value = issue
    claim_id = "claim-crash-after-backlog-promotion"
    submission = orch.workflow_job_store.enqueue(
        WorkflowJobSpec(
            project_id=str(issue.project_id),
            task_id=issue.identifier,
            generation=f"direct-owner:{claim_id}",
            action=ImplementationAction.DIRECT_OWNER_CLAIM.value,
            idempotency_key=f"owner-claim:{claim_id}",
            payload={
                "owner_id": "alice",
                "claim_id": claim_id,
                "expected_status": "Backlog",
            },
            expected_evidence_revision=issue_authority_version(issue),
        )
    )
    effects = OrchestratorImplementationEffects(
        orch,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    worker = DurableWorkflowWorker(
        store=orch.workflow_job_store,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): orch._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="owner-claim-precheckpoint-crash-worker",
    )

    def commit_in_progress_then_die(_identifier, **fields):
        issue.state = fields["status"]
        raise SystemExit("simulated death after owner transition commit")

    tracker.update_issue.side_effect = commit_in_progress_then_die
    with pytest.raises(SystemExit, match="after owner transition commit"):
        asyncio.run(worker.run_once())

    stranded = orch.workflow_job_store.get(submission.job_id)
    assert issue.state == "In Progress"
    intent = stranded.checkpoint["transition_intent"]
    assert intent["actor"] == "alice"
    assert intent["authority"] == "project_owner"
    assert intent["evidence_generation"] == claim_id
    current = orch._owner_claim_for_issue(issue.id, issue.project_id)
    assert current is not None
    assert current.claim_id == claim_id

    orch._close_owned_persistent_stores()
    restarted_store, project = _project_store(tmp_path)
    restarted = Orchestrator(
        config=ServiceConfig(
            owner_claim_ttl_hours=48,
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=restarted_store,
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker.reset_mock()
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_issue_states_by_ids.return_value = [issue]
    tracker.update_issue.side_effect = lambda _identifier, **fields: setattr(
        issue, "state", fields["status"]
    )
    restarted._project_trackers[project.id] = tracker
    restarted.task_transition_journal._clock = lambda: time.time() + 301
    assert restarted.workflow_job_store.recover_abandoned() == 1
    restarted_effects = OrchestratorImplementationEffects(
        restarted,
        project_id=str(issue.project_id),
        tracker=tracker,
    )
    restarted_worker = DurableWorkflowWorker(
        store=restarted.workflow_job_store,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(restarted_effects)
                )
            )
        },
        transition_services={
            str(issue.project_id): restarted._task_transition_service(
                issue.project_id,
                tracker,
            )
        },
        worker_id="owner-claim-precheckpoint-recovery-worker",
    )

    result = asyncio.run(restarted_worker.run_once())

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert restarted.workflow_job_store.get(submission.job_id).state.value == (
        "completed"
    )
    tracker.update_issue.assert_not_called()
    restored = restarted._owner_claim_for_issue(issue.id, issue.project_id)
    assert restored is not None
    assert restored.claim_id == claim_id
    assert restored.owner_login == "alice"
    restarted._close_owned_persistent_stores()


def test_owner_claim_tracker_lookup_cannot_block_healthz(tmp_path):
    """Native tracker locks stay off the shared ASGI event loop."""

    orch, tracker, issue = _orchestrator(tmp_path)
    lookup_entered = threading.Event()
    release_lookup = threading.Event()

    def blocked_detail(_identifier):
        lookup_entered.set()
        assert release_lookup.wait(3), "tracker lookup rescue timed out"
        return issue

    tracker.fetch_issue_detail.side_effect = blocked_detail
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    rescue = threading.Timer(2, release_lookup.set)
    rescue.daemon = True

    async def scenario():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            owner_request = asyncio.create_task(client.get(endpoint))
            assert await asyncio.to_thread(lookup_entered.wait, 1)
            health = await asyncio.wait_for(client.get("/healthz"), 0.5)
            assert health.status_code == 200
            assert not release_lookup.is_set()
            release_lookup.set()
            owner_response = await asyncio.wait_for(owner_request, 1)
            assert owner_response.status_code == 200

    rescue.start()
    try:
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            asyncio.run(scenario())
    finally:
        release_lookup.set()
        rescue.cancel()


def test_owner_claim_job_store_wait_cannot_block_healthz(tmp_path):
    """Workflow publication locks stay off the shared ASGI event loop."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    schedule_entered = threading.Event()
    release_schedule = threading.Event()

    def blocked_schedule(**_kwargs):
        schedule_entered.set()
        assert release_schedule.wait(3), "workflow-store rescue timed out"
        return SimpleNamespace(
            job_id="claim-job",
            generation="claim-generation",
        )

    orch._schedule_implementation_workflow_event = blocked_schedule
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    rescue = threading.Timer(2, release_schedule.set)
    rescue.daemon = True

    async def scenario():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            owner_request = asyncio.create_task(
                client.post(endpoint, json={"actor_login": "alice"})
            )
            assert await asyncio.to_thread(schedule_entered.wait, 1)
            health = await asyncio.wait_for(client.get("/healthz"), 0.5)
            assert health.status_code == 200
            assert not release_schedule.is_set()
            release_schedule.set()
            owner_response = await asyncio.wait_for(owner_request, 1)
            assert owner_response.status_code == 202

    rescue.start()
    try:
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            asyncio.run(scenario())
    finally:
        release_schedule.set()
        rescue.cancel()


def test_owner_claim_admission_survives_saturated_ordinary_api_pool(tmp_path):
    """Ordinary tracker waits cannot queue lifecycle control behind them."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    tracker.fetch_issue_detail.return_value = issue
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(
            job_id="claim-job",
            generation="claim-generation",
        )
    )
    ordinary_release = threading.Event()
    ordinary_workers_entered = threading.Event()
    entered_lock = threading.Lock()
    entered_count = 0

    def block_ordinary_worker():
        nonlocal entered_count
        with entered_lock:
            entered_count += 1
            if entered_count == 4:
                ordinary_workers_entered.set()
        assert ordinary_release.wait(3), "ordinary API pool rescue timed out"

    ordinary_futures = [
        server_module._api_thread_pool.submit(block_ordinary_worker)
        for _ in range(4)
    ]
    assert ordinary_workers_entered.wait(1)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    rescue = threading.Timer(2, ordinary_release.set)
    rescue.daemon = True

    async def scenario():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            claim_request = asyncio.create_task(
                client.post(endpoint, json={"actor_login": "alice"})
            )
            health = await asyncio.wait_for(client.get("/healthz"), 0.5)
            claimed = await asyncio.wait_for(claim_request, 0.5)
            assert health.status_code == 200
            assert claimed.status_code == 202, claimed.text
            assert not ordinary_release.is_set(), (
                "owner claim completed only after ordinary API workers were released"
            )

    rescue.start()
    try:
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            asyncio.run(scenario())
    finally:
        ordinary_release.set()
        rescue.cancel()
        for future in ordinary_futures:
            future.result(timeout=1)


def test_enforce_retry_cleanup_does_not_supersede_direct_owner_revocation(tmp_path):
    from oompah.implementation_workflow import ImplementationAction

    orch, _tracker, issue = _orchestrator(tmp_path)
    claim = orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
        claim_id="claim-with-exact-revocation",
    )
    orch.workflow_runtime = SimpleNamespace(enforce=True)
    orch._schedule_implementation_workflow_event = MagicMock(
        return_value=SimpleNamespace(job_id="direct-owner-revocation")
    )
    with patch.object(orch, "_notify_state_only"):
        scheduled = asyncio.run(
            orch._retire_owner_claim_after_status_commit(
                issue=issue,
                project_id=issue.project_id,
                claim=claim,
                observed_status="Done",
                observed_version="postcommit-version",
            )
        )
    assert scheduled is True

    withdrawn = server_module._cancel_retry_for_authority_change(
        orch,
        issue,
        issue.identifier,
        issue.project_id,
        "Done",
        None,
    )

    assert withdrawn == set()
    assert orch._schedule_implementation_workflow_event.call_count == 2
    direct_revocation = orch._schedule_implementation_workflow_event.call_args_list[
        0
    ].kwargs
    assert direct_revocation["action"] is ImplementationAction.AUTHORITY_REVOCATION
    assert direct_revocation["payload"]["authority_kind"] == "direct_owner"
    assert direct_revocation["payload"]["claim_id"] == claim.claim_id
    scheduler_revocation = orch._schedule_implementation_workflow_event.call_args_list[
        1
    ].kwargs
    assert scheduler_revocation["action"] == "authority_revocation"
    assert scheduler_revocation["payload"]["authority_kind"] == "scheduler"


def test_absent_owner_claim_delete_cas_preserves_concurrent_replacement(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    lookup = orch._owner_claim_for_issue
    replacement: dict[str, object] = {}

    def absent_then_install_replacement(issue_id, project_id):
        replacement["claim"] = orch.grant_owner_claim(
            issue_id=issue_id,
            project_id=project_id,
            owner_login="alice",
            claim_id="replacement-after-absent-read",
        )
        return None

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(
            orch,
            "_owner_claim_for_issue",
            side_effect=absent_then_install_replacement,
        ),
        patch.object(
            server_module,
            "_publish_owner_claim_state",
            new=AsyncMock(),
        ),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.request(
            "DELETE",
            endpoint,
            json={"actor_login": "alice"},
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"released": False}
    assert lookup(issue.id, issue.project_id) is replacement["claim"]
    state = json.loads((tmp_path / "service_state.json").read_text())
    persisted = next(iter(state["owner_claims"].values()))
    assert persisted["claim_id"] == "replacement-after-absent-read"


def test_owner_claim_api_retires_scheduler_before_granting_direct_work(tmp_path):
    """A running scheduler generation cannot survive an owner takeover."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    running = MagicMock()
    running.issue = issue
    running.identifier = issue.identifier
    running.authority_generation = "generation-1"
    orch.state.running[issue.id] = running

    async def terminate(issue_id, *, cleanup_workspace):
        assert issue_id == issue.id
        assert cleanup_workspace is False
        assert issue.id in orch.state.running
        orch.state.running.pop(issue.id)
        return True

    orch._terminate_running = AsyncMock(side_effect=terminate)
    orch._schedule_running_termination = MagicMock()
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json={"actor_login": "alice"})

    assert response.status_code == 200, response.text
    tracker.add_label.assert_called_once_with(issue.identifier, "human-only")
    tracker.remove_label.assert_called_once_with(issue.identifier, "human-only")
    assert running.authority_revoked is True
    assert running.authority_revocation_reason == "direct owner claimed task"
    orch._terminate_running.assert_awaited_once_with(
        issue.id,
        cleanup_workspace=False,
    )
    orch._schedule_running_termination.assert_not_called()
    assert issue.id not in orch.state.running
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None
    # The scheduler already owned the task in In Progress; takeover preserves
    # that state without a dispatchable Open transition.
    tracker.update_issue.assert_not_called()


def test_owner_claim_completes_after_retryable_recovery_publication(tmp_path):
    """A retained checkpoint cannot leave owner takeover ownerless."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.labels = []
    issue.head_sha = "a" * 40
    tracker.fetch_issue_detail.return_value = issue

    def update_state(_identifier, *, status, **_kwargs):
        issue.state = status

    tracker.update_issue.side_effect = update_state
    running = MagicMock()
    running.issue = issue
    running.identifier = issue.identifier
    running.authority_generation = "generation-1"
    orch.state.running[issue.id] = running
    publication_error = RecoveryPublicationError(
        "local transfer interrupted",
        context={
            "snapshot_head": "a" * 40,
            "pending_ref": "refs/oompah/recovery-pending/OOMPAH-1",
        },
    )

    async def terminate(issue_id, *, cleanup_workspace):
        assert issue_id == issue.id
        assert cleanup_workspace is False
        orch.state.running.pop(issue.id)
        orch._route_retryable_recovery_publication(
            running,
            issue.id,
            issue.project_id,
            publication_error,
        )
        return True

    orch._terminate_running = AsyncMock(side_effect=terminate)
    orch._post_comment = MagicMock()
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json={"actor_login": "alice"})

    assert response.status_code == 200, response.text
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None
    assert issue.state == "In Progress"
    assert [call.kwargs["status"] for call in tracker.update_issue.call_args_list] == [
        "Open",
        "In Progress",
    ]
    tracker.mark_needs_human.assert_not_called()
    assert issue.id not in orch.state.running


def test_owner_claim_retries_real_standalone_pending_checkpoint(tmp_path):
    """The owner API can take over without losing a real unpublished commit."""

    store, project = _project_store(tmp_path)
    authority = Path(project.repo_path)
    authority.mkdir()

    def git(repo, *args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=check,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )

    git(authority, "init", "--initial-branch=main")
    git(authority, "config", "user.name", "Test")
    git(authority, "config", "user.email", "test@example.com")
    (authority / "base.txt").write_text("base\n", encoding="utf-8")
    git(authority, "add", "base.txt")
    git(authority, "commit", "-m", "base")
    issue = _issue()
    issue.labels = []
    issue.work_branch = issue.identifier
    checkout = Path(store.worktree_path_for(project.id, issue.identifier))
    checkout.parent.mkdir(parents=True)
    git(tmp_path, "clone", str(authority), str(checkout))
    git(checkout, "config", "user.name", "Test")
    git(checkout, "config", "user.email", "test@example.com")
    git(checkout, "switch", "-c", issue.identifier)
    (checkout / "owner.txt").write_text("owner state\n", encoding="utf-8")
    with patch(
        "oompah.projects._transfer_recovery_snapshot_objects",
        side_effect=ProjectError("first transfer interrupted"),
    ):
        with pytest.raises(RecoveryPublicationError) as interrupted:
            store.preserve_worktree_changes(
                project.id,
                issue.identifier,
                str(checkout),
                issue.identifier,
            )

    orch = Orchestrator(
        config=ServiceConfig(owner_claim_ttl_hours=48, duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "service_state.json"),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue

    def update_state(_identifier, *, status, **_kwargs):
        issue.state = status

    tracker.update_issue.side_effect = update_state
    orch._project_trackers[project.id] = tracker
    worker_task = MagicMock()
    worker_task.done.return_value = True
    entry = RunningEntry(
        worker_task=worker_task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        workspace_path=str(checkout),
    )
    orch.state.running[issue.id] = entry
    orch._fire_task_cost_record = MagicMock()
    orch._fire_telemetry_comment = MagicMock()
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json={"actor_login": "alice"})

    assert response.status_code == 200, response.text
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None
    assert issue.state == "In Progress"
    recovery_ref = str(interrupted.value.context["recovery_ref"])
    recovery_head = git(
        authority,
        "rev-parse",
        "--verify",
        f"{recovery_ref}^{{commit}}",
    ).stdout.strip()
    assert recovery_head == interrupted.value.context["snapshot_head"]
    assert issue.id not in orch.state.running


def test_restart_reconciles_checkpoint_after_tracker_reopen_failure(tmp_path):
    """Published Git evidence survives the tracker-write crash window."""

    authority = tmp_path / "authority"
    authority.mkdir()

    def git(repo, *args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=check,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )

    git(authority, "init", "--initial-branch=main")
    git(authority, "config", "user.name", "Test")
    git(authority, "config", "user.email", "test@example.com")
    (authority / "base.txt").write_text("base\n", encoding="utf-8")
    git(authority, "add", "base.txt")
    git(authority, "commit", "-m", "base")

    projects_path = tmp_path / "projects.json"
    worktrees_root = tmp_path / "worktrees"
    store = ProjectStore(
        path=str(projects_path),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(worktrees_root),
    )
    project = Project(
        id="proj-1",
        name="example",
        repo_url=str(authority),
        repo_path=str(authority),
        branch="main",
        default_branch="main",
    )
    store._projects[project.id] = project
    store._save()
    issue = _issue()
    issue.work_branch = issue.identifier
    checkout = Path(store.worktree_path_for(project.id, issue.identifier))
    checkout.parent.mkdir(parents=True)
    git(tmp_path, "clone", str(authority), str(checkout))
    git(checkout, "config", "user.name", "Test")
    git(checkout, "config", "user.email", "test@example.com")
    git(checkout, "switch", "-c", issue.identifier)
    (checkout / "retained.txt").write_text("retained\n", encoding="utf-8")

    with patch(
        "oompah.projects._transfer_recovery_snapshot_objects",
        side_effect=ProjectError("initial publication interruption"),
    ):
        with pytest.raises(RecoveryPublicationError):
            store.preserve_worktree_changes(
                project.id,
                issue.identifier,
                str(checkout),
                issue.identifier,
            )

    first_store = ProjectStore(
        path=str(projects_path),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(worktrees_root),
    )
    first = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=first_store,
        state_path=str(tmp_path / "first-state.json"),
    )
    unavailable_tracker = MagicMock()
    unavailable_tracker.fetch_issue_detail.return_value = issue
    unavailable_tracker.update_issue.side_effect = RuntimeError("tracker unavailable")
    first._project_trackers[project.id] = unavailable_tracker

    first_result = first._reconcile_pending_recovery_publications(discover=True)

    assert first_result["errors"], first_result
    assert (project.id, issue.identifier) in first._pending_recovery_publications
    recovery_ref = str(
        first._pending_recovery_publications[(project.id, issue.identifier)][
            "recovery_ref"
        ]
    )
    ref_result = git(
        authority,
        "rev-parse",
        "--verify",
        f"{recovery_ref}^{{commit}}",
        check=False,
    )
    assert ref_result.returncode == 0, (first_result, ref_result.stderr)

    second_store = ProjectStore(
        path=str(projects_path),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(worktrees_root),
    )
    second = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=second_store,
        state_path=str(tmp_path / "second-state.json"),
    )
    recovered_issue = _issue()
    recovered_issue.work_branch = recovered_issue.identifier
    recovered_tracker = MagicMock()
    recovered_tracker.fetch_issue_detail.return_value = recovered_issue

    def reopen(_identifier, *, status, **_kwargs):
        recovered_issue.state = status

    recovered_tracker.update_issue.side_effect = reopen
    second._project_trackers[project.id] = recovered_tracker
    second._post_comment = MagicMock()

    second_result = second._reconcile_pending_recovery_publications(discover=True)

    assert second_result["reopened"] == 1
    assert second_result["pending"] == 0
    recovered_tracker.update_issue.assert_called_once_with(
        recovered_issue.identifier,
        status="Open",
    )


def test_owner_claim_api_keeps_resistant_scheduler_runtime_visible(tmp_path):
    """Provider retirement failure cannot create a second owner."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    running = MagicMock()
    running.issue = issue
    running.identifier = issue.identifier
    running.authority_generation = "generation-1"
    orch.state.running[issue.id] = running
    orch._terminate_running = AsyncMock(return_value=False)
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json={"actor_login": "alice"})

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "owner_takeover_pending"
    assert orch.state.running[issue.id] is running
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    tracker.add_label.assert_called_once_with(issue.identifier, "human-only")
    tracker.remove_label.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_owner_claim_api_waits_for_claim_to_register_before_retirement(tmp_path):
    """A dispatch between selection and RunningEntry registration is fenced."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    orch.state.claimed.add(issue.id)
    running = MagicMock()
    running.issue = issue
    running.identifier = issue.identifier
    running.authority_generation = "generation-1"
    original_cancel = orch._cancel_retry_for_issue

    def cancel_then_register(**kwargs):
        result = original_cancel(**kwargs)

        def register_runtime():
            orch.state.claimed.discard(issue.id)
            orch.state.running[issue.id] = running

        registration = threading.Timer(0.01, register_runtime)
        registration.daemon = True
        registration.start()
        return result

    async def terminate(issue_id, *, cleanup_workspace):
        assert issue_id == issue.id
        assert cleanup_workspace is False
        assert orch.state.running[issue.id] is running
        orch.state.running.pop(issue.id)
        return True

    orch._cancel_retry_for_issue = MagicMock(side_effect=cancel_then_register)
    orch._terminate_running = AsyncMock(side_effect=terminate)
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json={"actor_login": "alice"})

    assert response.status_code == 200, response.text
    orch._terminate_running.assert_awaited_once_with(
        issue.id,
        cleanup_workspace=False,
    )
    assert issue.id not in orch.state.claimed
    assert issue.id not in orch.state.running
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None
    tracker.update_issue.assert_called_once_with(issue.identifier, status="In Progress")
    tracker.remove_label.assert_called_once_with(issue.identifier, "human-only")


@pytest.mark.timeout(20)
def test_owner_claim_retires_exact_advertised_legacy_provider_only(
    tmp_path,
    monkeypatch,
):
    """The health recovery request retires one exact orphan generation."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    lease_path = tmp_path / "legacy-recovery.sqlite3"
    orch.validation_resource_lease = ValidationResourceLease(
        lease_path,
        capacity=2,
        poll_seconds=0.01,
    )
    launcher = """
import os
import sys
import time
import types
from pathlib import Path
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease

lease = ValidationResourceLease(sys.argv[1], capacity=2, poll_seconds=0.01)
owner = ValidationLeaseOwner.worker(
    project_id='proj-1',
    task_id='OOMPAH-1',
    authority_generation=sys.argv[2],
)
handle = lease.acquire(owner)
handle.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=60)
Path(sys.argv[3]).write_text(str(os.getpid()), encoding='utf-8')
time.sleep(30)
"""
    flagged_ready = tmp_path / "flagged.ready"
    unrelated_ready = tmp_path / "unrelated.ready"
    flagged = subprocess.Popen(
        [
            sys.executable,
            "-c",
            launcher,
            str(lease_path),
            "generation-1",
            str(flagged_ready),
        ],
        start_new_session=True,
    )
    unrelated = subprocess.Popen(
        [
            sys.executable,
            "-c",
            launcher,
            str(lease_path),
            "generation-2",
            str(unrelated_ready),
        ],
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 3
        while (
            not flagged_ready.exists() or not unrelated_ready.exists()
        ) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert flagged_ready.exists() and unrelated_ready.exists()
        flagged_pid = int(flagged_ready.read_text(encoding="utf-8"))
        monkeypatch.setattr(
            "oompah.validation_resource_lease._legacy_provider_bootstrap_process",
            lambda pid, _ticks, _trusted, _parent: int(pid) == flagged_pid,
        )
        snapshot = orch.validation_resource_lease.status().to_dict()
        recovery = next(
            owner["recovery_request"]
            for owner in snapshot["owners"]
            if owner.get("process_role") == "legacy_provider_bootstrap"
        )
        body = {
            "actor_login": "alice",
            **recovery["body"],
        }
        client = TestClient(app, raise_server_exceptions=False)
        endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new=AsyncMock()),
        ):
            response = client.post(endpoint, json=body)

        assert response.status_code == 200, response.text
        assert flagged.wait(timeout=3) != 0
        assert unrelated.poll() is None
        remaining = orch.validation_resource_lease.status().to_dict()["owners"]
        assert [owner["authority_generation"] for owner in remaining] == [
            "generation-2"
        ]
        cancellation = orch.validation_resource_lease.cancellation_for(
            ValidationLeaseOwner.worker(
                project_id="proj-1",
                task_id="OOMPAH-1",
                authority_generation="generation-1",
            )
        )
        assert cancellation is not None
        assert cancellation["cancelled_by"] == "operator:alice"
        assert cancellation["reason"] == "direct owner takeover"
        assert orch._owner_claim_for_issue(issue.id, issue.project_id) is not None
        tracker.add_label.assert_called_once_with(issue.identifier, "human-only")
        tracker.remove_label.assert_called_once_with(issue.identifier, "human-only")
    finally:
        for process in (flagged, unrelated):
            if process.poll() is None:
                process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=3)


def test_owner_claim_stale_validation_generation_cannot_cancel_current_runtime(
    tmp_path,
):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    running = MagicMock()
    running.authority_generation = "current-generation"
    orch.state.running[issue.id] = running
    orch.validation_resource_lease.cancel_exact_owner_process = MagicMock()
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    body = {
        "actor_login": "alice",
        "expected_validation_owner": {
            "kind": "worker",
            "project_id": "proj-1",
            "task_id": "OOMPAH-1",
            "authority_generation": "stale-generation",
            "requester_pid": 101,
            "requester_start_ticks": 102,
            "child_pid": 103,
            "child_start_ticks": 104,
        },
    }

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json=body)

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == (
        "validation_owner_recovery_pending"
    )
    orch.validation_resource_lease.cancel_exact_owner_process.assert_not_called()
    assert orch.state.running[issue.id] is running
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    tracker.add_label.assert_called_once_with(issue.identifier, "human-only")
    tracker.remove_label.assert_not_called()


def test_legacy_recovery_waits_for_exact_durable_owner_row_to_retire(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    owner = ValidationLeaseOwner.worker(
        project_id="proj-1",
        task_id="OOMPAH-1",
        authority_generation="generation-1",
    )
    identity = {
        "requester_pid": 101,
        "requester_start_ticks": 102,
        "child_pid": 103,
        "child_start_ticks": 104,
    }
    durable_owner = {
        "kind": "worker",
        "project_id": "proj-1",
        "task_id": "OOMPAH-1",
        "authority_generation": "generation-1",
        **identity,
    }
    orch.validation_resource_lease.status = MagicMock(
        side_effect=[
            types.SimpleNamespace(
                owners=(
                    {
                        **durable_owner,
                        "process_role": "legacy_provider_bootstrap",
                    },
                )
            ),
            types.SimpleNamespace(owners=(durable_owner,)),
        ]
    )
    orch.validation_resource_lease.cancel_exact_owner_process = MagicMock(
        return_value=True
    )

    retired, error = server_module._retire_expected_legacy_validation_owner(
        orch,
        issue,
        owner,
        identity,
    )

    assert retired is False
    assert error == "the exact legacy validation owner has not retired yet"


def test_legacy_recovery_rejects_non_session_provider_pid(tmp_path):
    orch, _tracker, issue = _orchestrator(tmp_path)
    running = MagicMock()
    running.authority_generation = "generation-1"
    running.session.agent_pid = "901"
    orch.state.running[issue.id] = running
    orch.validation_resource_lease.cancel_exact_owner_process = MagicMock()
    owner = ValidationLeaseOwner.worker(
        project_id="proj-1",
        task_id="OOMPAH-1",
        authority_generation="generation-1",
    )
    identity = {
        "requester_pid": 101,
        "requester_start_ticks": 102,
        "child_pid": 902,
        "child_start_ticks": 104,
    }

    retired, error = server_module._retire_expected_legacy_validation_owner(
        orch,
        issue,
        owner,
        identity,
    )

    assert retired is False
    assert error == "the live provider process no longer matches the request"
    orch.validation_resource_lease.cancel_exact_owner_process.assert_not_called()


def test_owner_claim_same_generation_aba_replacement_fails_closed(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    issue.labels = []
    tracker.fetch_issue_detail.return_value = issue
    identity = {
        "requester_pid": 101,
        "requester_start_ticks": 102,
        "child_pid": 103,
        "child_start_ticks": 104,
    }
    orch.validation_resource_lease.status = MagicMock(
        return_value=types.SimpleNamespace(
            owners=(
                {
                    "kind": "worker",
                    "project_id": "proj-1",
                    "task_id": "OOMPAH-1",
                    "authority_generation": "generation-1",
                    "process_role": "legacy_provider_bootstrap",
                    **identity,
                },
            )
        )
    )
    # The exact transaction observes that the advertised row was replaced
    # after the health read but before cancellation authority was recorded.
    orch.validation_resource_lease.cancel_exact_owner_process = MagicMock(
        return_value=False
    )
    client = TestClient(app, raise_server_exceptions=False)
    endpoint = "/api/v1/projects/proj-1/tasks/OOMPAH-1/owner-claim"
    body = {
        "actor_login": "alice",
        "expected_validation_owner": {
            "kind": "worker",
            "project_id": "proj-1",
            "task_id": "OOMPAH-1",
            "authority_generation": "generation-1",
            **identity,
        },
    }

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(
            server_module,
            "_publish_owner_claim_state",
            new=AsyncMock(),
        ),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = client.post(endpoint, json=body)

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == (
        "validation_owner_recovery_pending"
    )
    assert orch._owner_claim_for_issue(issue.id, issue.project_id) is None
    tracker.add_label.assert_called_once_with(issue.identifier, "human-only")
    tracker.remove_label.assert_not_called()


def test_stale_dispatch_aborts_after_direct_owner_claim(tmp_path):
    """A candidate selected before takeover cannot start after the lease."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    issue.labels = []
    orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
    )

    assert orch._should_dispatch(issue) is False
    asyncio.run(orch._dispatch(issue, attempt=None))

    assert issue.id not in orch.state.claimed
    assert issue.id not in orch.state.running
    tracker.update_issue.assert_not_called()


def test_persisted_takeover_fence_blocks_retry_authority_install(tmp_path):
    """A completed owner takeover blocks the retry's final authority write."""

    orch, tracker, issue = _orchestrator(tmp_path)
    issue.state = "Open"
    issue.labels = []  # stale retry candidate captured before the takeover
    fenced = _issue(state="Open")
    # The temporary human-only label has already been removed, so this covers
    # the narrow race after a successful owner claim rather than merely the
    # in-progress label write.
    fenced.labels = []
    orch.grant_owner_claim(
        issue_id=issue.id,
        project_id=issue.project_id,
        owner_login="alice",
    )
    tracker.fetch_issue_detail.return_value = fenced

    authorized, current = orch._write_in_progress_if_scheduler_authorized(
        tracker,
        issue,
    )

    assert authorized is False
    assert current is fenced
    tracker.update_issue.assert_not_called()
    assert issue.id not in orch.state.running


def test_dashboard_owner_claim_badge_reads_state_snapshot():
    dashboard = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")

    assert "state.owner_claims" in dashboard
    assert "ownerClaimsByIssueKey" in dashboard
    assert "renderCardOwnerClaim" in dashboard
    assert "ownership_source" in dashboard or "Direct owner work" in dashboard


def test_owner_claim_ttl_is_environment_configured_and_bounded(monkeypatch):
    monkeypatch.setenv("OOMPAH_OWNER_CLAIM_TTL_HOURS", "12")

    config = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template=""))

    assert config.owner_claim_ttl_hours == 12
    assert ServiceConfig(owner_claim_ttl_hours=0).owner_claim_ttl_hours == 1
    assert "OOMPAH_OWNER_CLAIM_TTL_HOURS" in (
        Path(__file__).resolve().parents[1] / ".env.example"
    ).read_text(encoding="utf-8")
