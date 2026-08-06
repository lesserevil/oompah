"""Full-stack replay of the systemic workflow incident corpus.

These tests intentionally compose the real native tracker, Git fact collector,
pure evaluator, durable scheduler/ledger, resumable worker, transition journal,
and structured UI projection.  The only scenario-specific adapter supplies
immutable external observations that are unavailable in a local replay (for
example a forge audit result); lifecycle, queue, and Git mutations stay behind
their production boundaries.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import oompah.server as server_module
from oompah.task_transition_service import (
    TaskTransitionService,
    TransitionAuthority,
    TransitionIntent,
    TransitionJournal,
    issue_authority_version,
)
from oompah.work_decision import evaluate_task
from oompah.workflow_contract import IN_VALIDATION
from oompah.workflow_facts import (
    FactDomain,
    GitLandingCollector,
    LandingRequest,
    WorkflowFactCollector,
)
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore
from oompah.workflow_scheduler import WorkflowJobScheduler
from oompah.workflow_shadow import LegacyWorkflowProjection, WorkflowShadowEvaluator
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowJobContext,
    WorkflowRunDisposition,
)
from tests.fixtures_workflow_incidents import (
    INCIDENTS,
    IncidentScenario,
    GitReplay,
    NativeTrackerReplay,
    materialize_git,
    materialize_native_tracker,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
PROJECT_ID = "historical-incidents"


class _FactTracker:
    """Read adapter exposing persisted incident metadata to the collector."""

    def __init__(self, tracker: Any) -> None:
        self._tracker = tracker

    def fetch_issue_detail(self, identifier: str):
        issue = self._tracker.fetch_issue_detail(identifier)
        if issue is None:
            return None
        metadata = self._tracker.get_metadata(identifier)
        integration = metadata.get("oompah.integration")
        if isinstance(integration, dict):
            return replace(issue, integration=dict(integration))
        return issue

    def fetch_children(self, identifier: str):
        return self._tracker.fetch_children(identifier)


def _task_key(scenario: IncidentScenario) -> str:
    return {
        "OOMPAH-562": "child",
        "OOMPAH-731": "maintenance",
        "OOMPAH-732": "standalone",
        "OOMPAH-739": "child",
        "OOMPAH-748": "child",
        "OOMPAH-749": "live",
        "OOMPAH-751": "sender",
    }[scenario.source_task_id]


def _landing_requests(scenario: IncidentScenario, git: GitReplay | None):
    if git is None:
        return ()
    if scenario.source_task_id == "OOMPAH-739":
        return (
            LandingRequest(
                "epic-child",
                "main",
                revision=git.commits["child-head"],
            ),
            LandingRequest(
                "epic-parent",
                "main",
                revision=git.commits["parent-head"],
            ),
        )
    if scenario.source_task_id == "OOMPAH-748":
        return (
            LandingRequest(
                "epic-child",
                "epic-parent",
                revision=git.commits["child-head"],
            ),
        )
    return ()


def _seed_authoritative_integration(
    scenario: IncidentScenario,
    replay: NativeTrackerReplay,
    git: GitReplay | None,
) -> None:
    """Persist only source facts needed by the real tracker collector."""

    key = _task_key(scenario)
    identifier = replay.identifiers[key]
    current = replay.tracker.get_metadata(identifier).get("oompah.integration")
    integration = dict(current or {})
    before = scenario.before
    if scenario.source_task_id == "OOMPAH-562":
        integration["required_base_missing"] = ["dependency"]
    elif scenario.source_task_id == "OOMPAH-731":
        integration["maintenance_publication_proven"] = True
    elif scenario.source_task_id == "OOMPAH-732":
        integration["mode"] = "standalone"
    elif scenario.source_task_id == "OOMPAH-749":
        integration["live_claim_precedes_history"] = True
    else:
        return
    if git is not None and scenario.source_task_id == "OOMPAH-731":
        integration["published_epic_head"] = before["published_epic_head"]
    replay.tracker.set_metadata_field(identifier, "oompah.integration", integration)


def _collector(
    scenario: IncidentScenario,
    replay: NativeTrackerReplay,
    git: GitReplay | None,
) -> WorkflowFactCollector:
    def terminal_audit(_issue: Any) -> dict[str, Any]:
        return {"phase": "none"}

    def review_ci(_issue: Any) -> dict[str, Any]:
        return {"state": "open", "ci": "passed"}

    def implementation_authority(_issue: Any) -> dict[str, Any]:
        return {"lease_expires_at": "2099-01-01T00:00:00Z"}

    def retry_budget(_issue: Any) -> dict[str, Any]:
        return {"remaining": 5}

    def config(_issue: Any) -> dict[str, Any]:
        if scenario.source_task_id == "OOMPAH-751":
            return {"coordination_policy_denied": True}
        return {}

    return WorkflowFactCollector(
        project_id=PROJECT_ID,
        tracker=_FactTracker(replay.tracker),
        sources={
            FactDomain.TERMINAL_AUDIT: terminal_audit,
            FactDomain.REVIEW_CI: review_ci,
            FactDomain.IMPLEMENTATION_AUTHORITY: implementation_authority,
            FactDomain.RETRY_BUDGET: retry_budget,
            FactDomain.CONFIG: config,
        },
        landing_collector=(
            GitLandingCollector(git.path, project_id=PROJECT_ID, clock=lambda: NOW)
            if git is not None
            else None
        ),
        clock=lambda: NOW,
    )


def _ui_projection(decision):
    """Build the same structured fields consumed by the dashboard projection."""

    return LegacyWorkflowProjection(
        "ui",
        status=decision.status,
        disposition=decision.disposition,
        owner=decision.responsible_owner,
        reason_code=decision.reason_code,
        permitted_actions=decision.permitted_actions,
        recommended_status=decision.recommended_status,
    )


class _IncidentHandler:
    domain = WorkflowActionDomain.TRACKER

    def __init__(
        self,
        scenario: IncidentScenario,
        replay: NativeTrackerReplay,
        collector: WorkflowFactCollector,
        task_id: str,
        landing_requests: tuple[LandingRequest, ...],
    ) -> None:
        self.scenario = scenario
        self.replay = replay
        self.collector = collector
        self.task_id = task_id
        self.landing_requests = landing_requests

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        facts = self.collector.collect(
            self.task_id,
            landing_requests=self.landing_requests,
        )
        return RevalidationResult(
            context.job.generation,
            evidence_revision=facts.facts_version,
        )

    async def inspect(self, _context: WorkflowJobContext) -> EffectObservation:
        return EffectObservation(False)

    async def apply(self, context: WorkflowJobContext) -> EffectResult:
        return EffectResult(
            {
                "task_id": self.task_id,
                "action": context.job.action,
                "reason_code": self.scenario.expected.reason_code,
            }
        )

    async def verify(
        self, _context: WorkflowJobContext, effect: EffectResult
    ) -> VerificationResult:
        return VerificationResult(True, effect.receipt)

    async def build_transition(
        self, context: WorkflowJobContext, _verification: VerificationResult
    ) -> TransitionIntent | None:
        # OOMPAH-731 is the direct-maintenance path whose durable audit job
        # must move the native task into validation. Other incidents either
        # retain a terminal state or complete a non-lifecycle effect.
        if self.scenario.source_task_id != "OOMPAH-731":
            return None
        issue = self.replay.tracker.fetch_issue_detail(self.task_id)
        assert issue is not None
        return TransitionIntent(
            project_id=PROJECT_ID,
            task_id=self.task_id,
            expected_status=issue.state,
            expected_version=issue_authority_version(issue),
            requested_status=IN_VALIDATION,
            actor="workflow-worker",
            authority=TransitionAuthority.WORKER,
            reason_code=self.scenario.expected.reason_code,
            idempotency_key=f"{context.job.idempotency_key}:status",
            originating_job=context.job.job_id,
        )


def _run_incident(scenario: IncidentScenario, root: Path, monkeypatch) -> None:
    native = materialize_native_tracker(root, scenario)
    git = materialize_git(root, scenario) if scenario.git is not None else None
    _seed_authoritative_integration(scenario, native, git)
    task_id = native.identifiers[_task_key(scenario)]
    collector = _collector(scenario, native, git)
    requests = tuple(_landing_requests(scenario, git))
    issue = native.tracker.fetch_issue_detail(task_id)
    assert issue is not None
    facts = collector.collect(task_id, landing_requests=requests)
    decision = evaluate_task(issue, facts, now=NOW)
    expected = scenario.expected

    assert decision.reason_code == expected.reason_code
    assert decision.disposition is expected.disposition
    assert decision.responsible_owner is expected.owner
    assert decision.durable_jobs == tuple(sorted(expected.durable_jobs))

    # The UI projection is structured data, not a prose/log parser. The shadow
    # registry is the same redacted projection endpoint used by the dashboard.
    shadow = WorkflowShadowEvaluator(mode="enforce")
    ui = _ui_projection(decision)
    compared = shadow.evaluate(
        issue,
        facts,
        (ui,),
        snapshot_generation=1,
        now=NOW,
    )
    assert compared.state.value == "aligned"
    diagnostic = shadow.diagnostic(PROJECT_ID, task_id)
    assert diagnostic is not None
    assert diagnostic["decision"]["reason_code"] == decision.reason_code
    assert diagnostic["legacy"][0]["reason_code"] == decision.reason_code
    monkeypatch.setattr(
        server_module,
        "_orchestrator",
        SimpleNamespace(workflow_shadow=shadow),
    )
    response = asyncio.run(
        server_module.api_workflow_diagnostic(PROJECT_ID, task_id)
    )
    api_diagnostic = json.loads(response.body)
    assert api_diagnostic["diagnostic"]["decision"]["reason_code"] == (
        decision.reason_code
    )

    job_store_path = root / "workflow-jobs.sqlite3"
    transition_path = root / "transitions.sqlite3"
    store = WorkflowJobStore(str(job_store_path))
    journal = TransitionJournal(str(transition_path))
    service = TaskTransitionService(
        project_id=PROJECT_ID,
        tracker=native.tracker,
        journal=journal,
    )
    handler = _IncidentHandler(scenario, native, collector, task_id, requests)
    handlers = {action: handler for action in decision.durable_jobs}
    worker = DurableWorkflowWorker(
        store=store,
        handlers=handlers or {"noop": handler},
        transition_services={PROJECT_ID: service},
        worker_id="workflow-worker",
        heartbeat_seconds=1,
    )
    scheduler = WorkflowJobScheduler(store=store, worker=worker)
    reconciliation = scheduler.reconcile((decision,))
    assert reconciliation.jobs_created == len(expected.durable_jobs)

    # Duplicate event delivery replays the existing schedule cursor instead of
    # creating a second external effect or queue row.
    duplicate = scheduler.reconcile(
        (decision,), snapshot_generation=reconciliation.snapshot_generation
    )
    assert duplicate.jobs_created == 0
    assert duplicate.jobs_replayed == len(expected.durable_jobs)
    assert len(store.list_jobs()) == len(expected.durable_jobs)

    if expected.durable_jobs:
        crashed = store.claim_next(lease_owner="crashed-worker", lease_seconds=60)
        assert crashed is not None
        store.close()

        restarted_store = WorkflowJobStore(str(job_store_path))
        try:
            assert restarted_store.recover_abandoned(lease_owner="crashed-worker") == 1
            restarted_journal = TransitionJournal(str(transition_path))
            restarted_service = TaskTransitionService(
                project_id=PROJECT_ID,
                tracker=native.tracker,
                journal=restarted_journal,
            )
            restarted_handler = _IncidentHandler(
                scenario, native, collector, task_id, requests
            )
            restarted_worker = DurableWorkflowWorker(
                store=restarted_store,
                handlers={action: restarted_handler for action in expected.durable_jobs},
                transition_services={PROJECT_ID: restarted_service},
                worker_id="restarted-worker",
                heartbeat_seconds=1,
            )
            while True:
                result = asyncio.run(restarted_worker.run_once())
                if result.disposition is WorkflowRunDisposition.IDLE:
                    break
                assert result.disposition is WorkflowRunDisposition.COMPLETED
            assert all(
                job.state is WorkflowJobState.COMPLETED
                for job in restarted_store.list_jobs()
            )
        finally:
            restarted_store.close()
    else:
        store.close()
        reopened = WorkflowJobStore(str(job_store_path))
        try:
            assert reopened.list_jobs() == ()
        finally:
            reopened.close()

    if scenario.git is not None and git is not None:
        for ref in scenario.git.refs:
            assert git.ref_exists(ref.name) is ref.present
        for assertion in scenario.git.assertions:
            assert git.is_ancestor(assertion.ancestor, assertion.descendant) is (
                assertion.expected
            )

    if scenario.source_task_id == "OOMPAH-731":
        final_issue = native.tracker.fetch_issue_detail(task_id)
        assert final_issue is not None
        assert final_issue.state == IN_VALIDATION
    elif scenario.source_task_id == "OOMPAH-739":
        # Durable positive landing facts preserve terminal state even after
        # the source refs have disappeared.
        final_issue = native.tracker.fetch_issue_detail(task_id)
        assert final_issue is not None
        assert final_issue.state == "Merged"


@pytest.mark.parametrize("scenario", INCIDENTS, ids=lambda item: item.source_task_id)
def test_every_historical_incident_replays_through_the_full_stack(
    tmp_path, scenario, monkeypatch
):
    _run_incident(scenario, tmp_path / scenario.source_task_id, monkeypatch)
