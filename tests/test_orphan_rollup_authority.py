"""Production-shaped orphan-recovery/epic-rollup authority regressions."""

from __future__ import annotations

import asyncio
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.epic_workflow import (
    EpicAction,
    EpicFactCollector,
    EpicWorkflowController,
    EpicWorkflowHandler,
    ProductionEpicWorkflowBackend,
)
from oompah.integration import IntegrationRecord
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_PROGRESS, OPEN, READY_TO_INTEGRATE
from oompah.workflow_worker import DurableWorkflowWorker, WorkflowRunDisposition


@dataclass
class _Write:
    identifier: str
    before: str
    after: str


class _AtomicTracker:
    """Small stateful tracker with the same fresh-read contract as production."""

    def __init__(self, issues: list[Issue]) -> None:
        self._lock = threading.RLock()
        self._issues = {issue.identifier: copy.deepcopy(issue) for issue in issues}
        self.writes: list[_Write] = []

    def invalidate_read_cache(self) -> None:
        return None

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        with self._lock:
            issue = self._issues.get(identifier)
            return copy.deepcopy(issue) if issue is not None else None

    def fetch_children(self, epic_id: str) -> list[Issue]:
        with self._lock:
            return [
                copy.deepcopy(issue)
                for issue in self._issues.values()
                if str(issue.parent_id or "") == str(epic_id)
            ]

    def update_issue(self, identifier: str, **fields: str) -> None:
        with self._lock:
            issue = self._issues[identifier]
            before = issue.state
            if "status" in fields:
                issue.state = fields["status"]
            self.writes.append(_Write(identifier, before, issue.state))

    def replace(self, issue: Issue) -> None:
        with self._lock:
            self._issues[issue.identifier] = copy.deepcopy(issue)


@pytest.fixture
def harness(tmp_path):
    project = MagicMock()
    project.id = "proj-oompah"
    project.name = "oompah"
    project.default_branch = "main"
    project.branch = "main"
    project.paused = False
    project.require_epic_for_tasks = False
    project_lock = threading.RLock()
    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.return_value = project
    project_store.project_write_lock.return_value = project_lock
    project_store.epic_branch_name.side_effect = lambda identifier: (
        f"epic-{identifier}"
    )
    orchestrator = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    try:
        yield orchestrator
    finally:
        orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)
        orchestrator.integration_queue.close()
        orchestrator.coordination_store.close()
        orchestrator.review_capacity_store.close()
        orchestrator.workflow_job_store.close()
        orchestrator.task_transition_journal.close()


def _issue(
    identifier: str,
    *,
    state: str,
    issue_type: str = "task",
    parent_id: str | None = None,
    integration: IntegrationRecord | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description=f"Production-shaped {identifier} fixture",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id="proj-oompah",
        priority=1,
        labels=[],
        integration=integration,
    )


def _accepted_parent(*, state: str = OPEN, head: str = "a" * 40) -> Issue:
    return _issue(
        "OOMPAH-795",
        state=state,
        issue_type="epic",
        integration=IntegrationRecord(
            state="ready",
            mode="queue",
            task_branch="OOMPAH-795",
            base_branch="main",
            base_sha="0" * 40,
            head_sha=head,
        ),
    )


def _install_tracker(orchestrator: Orchestrator, tracker: _AtomicTracker) -> None:
    orchestrator._project_trackers["proj-oompah"] = tracker
    orchestrator._fetch_all_in_progress_issues = lambda: [
        issue
        for identifier in tuple(tracker._issues)
        if (issue := tracker.fetch_issue_detail(identifier)) is not None
        and issue.state == IN_PROGRESS
    ]
    orchestrator._post_event = MagicMock()


def test_o795_rollup_and_orphan_ticks_converge_without_false_activity(
    harness: Orchestrator,
) -> None:
    parent = _accepted_parent()
    child = _issue(
        "OOMPAH-859",
        state=READY_TO_INTEGRATE,
        parent_id=parent.id,
    )
    leaf = _issue("OOMPAH-LEAF", state=IN_PROGRESS)
    tracker = _AtomicTracker([parent, child, leaf])
    _install_tracker(harness, tracker)

    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="proj-oompah",
            tracker=tracker,
        ),
        store=harness.workflow_job_store,
    )
    _batch, scheduled = controller.reconcile([parent])
    assert scheduled.jobs_created == 1
    job = harness.workflow_job_store.list_jobs(limit=1)[0]
    assert job.action == EpicAction.CHILD_LANDING_VERIFICATION.value

    transition_service = MagicMock()
    transition_service.execute = MagicMock()
    worker = DurableWorkflowWorker(
        store=harness.workflow_job_store,
        handlers={
            job.action: EpicWorkflowHandler(
                ProductionEpicWorkflowBackend(
                    controller=controller,
                    tracker=tracker,
                    effects=MagicMock(),
                )
            )
        },
        transition_services={"proj-oompah": transition_service},
        worker_id="epic-rollup-owner",
    )

    result = asyncio.run(worker.run_once())

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    transition_service.execute.assert_not_called()

    current_parent = tracker.fetch_issue_detail(parent.identifier)
    assert current_parent is not None
    assert current_parent.state == OPEN
    parent_writes = [
        write.after for write in tracker.writes if write.identifier == parent.id
    ]
    assert parent_writes == []
    assert parent.id not in harness._orphan_reset_counts
    assert harness.state.running == {}
    assert tracker.fetch_issue_detail(leaf.identifier).state == IN_PROGRESS


def test_rollup_rejects_newer_parent_child_generation_and_direct_owner(
    harness: Orchestrator,
) -> None:
    parent = _accepted_parent()
    child = _issue("OOMPAH-859", state=IN_PROGRESS, parent_id=parent.id)
    tracker = _AtomicTracker([parent, child])
    _install_tracker(harness, tracker)
    decision_started = threading.Event()
    release_decision = threading.Event()
    original_effective_state = harness._epic_child_effective_state

    def pause_after_lineage_observation(epic: Issue, observed_child: Issue) -> str:
        decision_started.set()
        assert release_decision.wait(timeout=5)
        return original_effective_state(epic, observed_child)

    harness._epic_child_effective_state = pause_after_lineage_observation
    with ThreadPoolExecutor(max_workers=1) as pool:
        transition = pool.submit(harness._reconcile_epic_rollup_statuses, [parent])
        assert decision_started.wait(timeout=5)
        tracker.replace(_accepted_parent(head="b" * 40))
        release_decision.set()
        assert transition.result(timeout=10) == 0

    assert tracker.fetch_issue_detail(parent.identifier).state == OPEN
    assert tracker.writes == []

    current = tracker.fetch_issue_detail(parent.identifier)
    assert current is not None
    harness.grant_owner_claim(
        issue_id=current.id,
        project_id=current.project_id,
        owner_login="operator",
    )
    assert harness._reconcile_epic_rollup_statuses([current]) == 0
    assert tracker.fetch_issue_detail(parent.identifier).state == OPEN
    assert tracker.writes == []
