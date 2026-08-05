"""Standalone Ready-to-Integrate delivery reconciliation coverage."""

from __future__ import annotations

import asyncio
import copy
import threading
import time
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.models import BlockerRef, Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import BranchQualityGate, QualityGateOwner
from oompah.providers import ProviderStore
from oompah.scm import ReviewRequest, SCMProvider
from oompah.statuses import (
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    OPEN,
    READY_TO_INTEGRATE,
)
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    Verdict,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadataStore
from oompah.terminal_transition_coordinator import AuditResult, TransitionResult


def _issue(
    identifier: str,
    *,
    branch: str | None = None,
    parent_id: str | None = None,
    issue_type: str = "task",
    priority: int | None = None,
    submitted_at: str | None = None,
) -> Issue:
    issue = Issue(
        id=f"id-{identifier}",
        identifier=identifier,
        title=f"Title for {identifier}",
        description=f"Description for {identifier}",
        state=READY_TO_INTEGRATE,
        parent_id=parent_id,
        issue_type=issue_type,
        priority=priority,
        work_branch=branch or identifier,
    )
    if submitted_at is not None:
        issue.integration = IntegrationRecord(
            state="ready",
            task_branch=branch or identifier,
            submitted_at=submitted_at,
        )
    return issue


def _review(
    identifier: str,
    *,
    state: str = "open",
    review_id: str = "42",
    head_sha: str = "abc123",
    source_branch: str | None = None,
    target_branch: str = "trunk",
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"{identifier}: review",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="oompah",
        state=state,
        source_branch=source_branch or identifier,
        target_branch=target_branch,
        created_at="2026-07-30T00:00:00+00:00",
        updated_at="2026-07-30T00:00:00+00:00",
        head_sha=head_sha,
    )


def _close_orchestrator(orch: Orchestrator) -> None:
    orch.integration_queue.close()
    orch.coordination_store.close()
    orch.review_capacity_store.close()
    orch._tick_pool.shutdown(wait=True, cancel_futures=True)
    orch._refresh_pool.shutdown(wait=True, cancel_futures=True)


class _MemoryTracker:
    """Stateful tracker double for the real terminal coordinator integration."""

    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.metadata: dict[str, dict[str, Any]] = {}
        self.update_calls: list[tuple[str, dict[str, Any]]] = []
        self.comment_calls: list[tuple[str, str, str]] = []

    def fetch_issues_by_states(self, states: list[str]) -> list[Issue]:
        return [self.issue] if self.issue.state in states else []

    def fetch_all_issues(self) -> list[Issue]:
        return [self.issue]

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        assert identifier == self.issue.identifier
        return self.issue

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        assert identifier == self.issue.identifier
        self.update_calls.append((identifier, dict(kwargs)))
        if "status" in kwargs:
            self.issue.state = str(kwargs["status"])

    def add_comment(
        self,
        identifier: str,
        text: str,
        author: str = "oompah",
    ) -> dict[str, str]:
        assert identifier == self.issue.identifier
        self.comment_calls.append((identifier, text, author))
        return {"id": str(len(self.comment_calls)), "text": text}


def _make_orchestrator(
    tmp_path,
    *,
    project: Project,
    tracker: mock.MagicMock,
    provider_store: ProviderStore | None = None,
    state_name: str = "service-state.json",
) -> Orchestrator:
    project_store = mock.MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = (
        lambda project_id: project if str(project_id) == project.id else None
    )
    project_lock = threading.RLock()
    project_store.project_write_lock.return_value = project_lock
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        provider_store=provider_store,
        project_store=project_store,
        state_path=str(tmp_path / state_name),
    )
    orch._project_trackers[project.id] = tracker
    return orch


@pytest.fixture
def harness(tmp_path, monkeypatch):
    project = Project(
        id="proj-1",
        name="Test Project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="trunk",
    )
    tracker = mock.MagicMock()
    tracker.fetch_issues_by_states.return_value = []
    tracker.fetch_all_issues.side_effect = lambda: list(
        tracker.fetch_issues_by_states.return_value
    )
    tracker.fetch_issue_detail.side_effect = lambda identifier: next(
        (
            issue
            for issue in tracker.fetch_issues_by_states.return_value
            if issue.identifier == identifier
        ),
        None,
    )
    provider = mock.MagicMock(spec=SCMProvider)
    provider.get_branch_head_sha.return_value = "abc123"
    provider.find_pr_for_branch.return_value = None
    provider.create_review.return_value = _review("TASK-1")
    provider_store = ProviderStore(str(tmp_path / "providers.json"))
    orch = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker,
        provider_store=provider_store,
    )
    detect = mock.MagicMock(return_value=provider)
    monkeypatch.setattr("oompah.orchestrator.detect_provider", detect)
    gate = mock.MagicMock(return_value=True)
    monkeypatch.setattr(orch, "_review_quality_gate_passes", gate)
    yield orch, project, tracker, provider, detect, gate
    _close_orchestrator(orch)


def _delivery_alerts(orch: Orchestrator) -> list[dict[str, str]]:
    return [
        alert
        for alert in orch._alerts
        if str(alert.get("source", "")).startswith("standalone_ready_delivery:")
    ]


def _set_all_issues(tracker: mock.MagicMock, issues: list[Issue]) -> None:
    """Replace the harness's Ready-derived graph with an explicit snapshot."""

    tracker.fetch_all_issues.side_effect = None
    tracker.fetch_all_issues.return_value = issues


def test_standalone_gate_does_not_hold_shared_queue_driver(harness):
    """A long standalone gate must not delay shared-epic queue recovery."""
    orch, _project, _tracker, _provider, _detect, _gate = harness
    orch.config.parallel_epic_children_enabled = True

    standalone_started = threading.Event()
    release_standalone = threading.Event()
    shared_queue_started = threading.Event()

    def blocked_standalone_reconciliation() -> None:
        standalone_started.set()
        assert release_standalone.wait(timeout=5)

    orch._reconcile_standalone_ready_to_integrate_tasks = (
        blocked_standalone_reconciliation
    )
    orch._sync_ready_integration_submissions = mock.MagicMock()
    orch.project_store.list_all.side_effect = (
        lambda: (shared_queue_started.set() or [])
    )
    orch._handle_reconcile = mock.AsyncMock()
    orch._handle_review_check = mock.AsyncMock()
    orch._handle_dispatch_needed = mock.AsyncMock(return_value={})
    orch._handle_yolo_review = mock.AsyncMock(return_value=0.0)
    orch._notify_observers = mock.MagicMock()
    orch._maybe_run_watchdog = mock.MagicMock()
    orch._recover_release_addendum_leases = mock.MagicMock(return_value=0)
    orch._run_step5b_maintenance = mock.MagicMock()
    orch._run_step5c_epic_maintenance = mock.MagicMock()

    async def _run() -> None:
        with mock.patch(
            "oompah.orchestrator.validate_dispatch_config",
            return_value=[],
        ):
            await orch._tick()
            await asyncio.wait_for(
                asyncio.to_thread(standalone_started.wait),
                timeout=1,
            )
            await asyncio.wait_for(
                asyncio.to_thread(shared_queue_started.wait),
                timeout=1,
            )
            release_standalone.set()
            await asyncio.gather(
                orch._standalone_delivery_future,
                orch._integration_future,
            )

    asyncio.run(_run())


def test_ready_to_open_reconciliation_revokes_delivery_and_clears_alert(harness):
    """A rejected standalone task cannot retain an old gate generation."""
    orch, project, tracker, _provider, _detect, _gate = harness
    task = _issue("TASK-REOPEN", branch="feature/reopen")
    tracker.fetch_issues_by_states.return_value = [task]

    orch._reconcile_standalone_ready_to_integrate_tasks()
    authority = orch._standalone_delivery_authorities[
        (project.id, task.identifier)
    ]
    orch._alerts.append(
        {
            "level": "warning",
            "source": f"standalone_ready_delivery:{project.id}:{task.identifier}",
            "message": "stale delivery alert",
        }
    )

    # The replacement worker owns the reopened task.  Its non-Ready status
    # is absent from the Ready query, so the authority reconciliation must
    # inspect the claimed task directly and fence the old generation.
    task.state = OPEN
    with mock.patch.object(
        orch._branch_quality_gate,
        "cancel_owner",
    ) as cancel_owner:
        orch._reconcile_standalone_ready_to_integrate_tasks()

    cancel_owner.assert_called_once_with(
        QualityGateOwner(
            project_id=authority.project_id,
            task_id=authority.task_id,
            head_sha=authority.head_sha or "",
            authority_generation=authority.generation,
        )
    )
    assert (project.id, task.identifier) not in orch._standalone_delivery_authorities
    assert not _delivery_alerts(orch)


def test_benign_tracker_timestamp_change_keeps_exact_head_authority(harness):
    """Concurrent tracker bookkeeping must not cancel delivery authority."""
    orch, project, tracker, _provider, _detect, _gate = harness
    task = _issue("TASK-REVISION", branch="feature/revision")
    tracker.fetch_issues_by_states.return_value = [task]

    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    assert orch._set_standalone_delivery_head(
        authority,
        task.work_branch or "",
        "abc123",
        lambda: "abc123",
    )

    def concurrent_refresh() -> Issue:
        def update_timestamp() -> None:
            task.updated_at = datetime.now(timezone.utc)

        updater = threading.Thread(target=update_timestamp)
        updater.start()
        updater.join(timeout=5)
        refreshed = copy.copy(task)
        refreshed.updated_at = datetime.now(timezone.utc)
        return refreshed

    tracker.fetch_issue_detail.side_effect = concurrent_refresh
    refreshed = concurrent_refresh()
    assert orch._standalone_delivery_evidence_revision(refreshed) == (
        authority.evidence_revision
    )
    tracker.fetch_issue_detail.side_effect = lambda _identifier: refreshed
    assert orch._standalone_delivery_authorized(authority, tracker)
    assert (
        orch._standalone_delivery_authorities[(project.id, task.identifier)]
        is authority
    )


def test_legacy_quality_gate_facade_uses_generation_fallback(harness):
    """Older gate facades remain usable without broadening new gates."""
    orch, project, tracker, _provider, _detect, _gate = harness
    task = _issue("TASK-LEGACY", branch="feature/legacy")
    tracker.fetch_issues_by_states.return_value = [task]
    orch._reconcile_standalone_ready_to_integrate_tasks()
    authority = orch._standalone_delivery_authorities[
        (project.id, task.identifier)
    ]

    class LegacyGate:
        def __init__(self):
            self.generations: list[str] = []

        def cancel_generation(self, generation: str) -> int:
            self.generations.append(generation)
            return 1

    legacy = LegacyGate()
    orch._branch_quality_gate = legacy

    assert orch._cancel_standalone_delivery_gate(authority) == 1
    assert legacy.generations == [authority.generation]


def test_mocked_exact_quality_gate_facade_does_not_fall_back(harness):
    """A spec'd new facade receives structured ownership, not a generation."""
    orch, project, tracker, _provider, _detect, _gate = harness
    task = _issue("TASK-MOCKED-OWNER", branch="feature/mocked-owner")
    tracker.fetch_issues_by_states.return_value = [task]
    orch._reconcile_standalone_ready_to_integrate_tasks()
    authority = orch._standalone_delivery_authorities[
        (project.id, task.identifier)
    ]
    exact = mock.MagicMock(spec=BranchQualityGate)
    exact.cancel_owner.return_value = 1
    orch._branch_quality_gate = exact

    assert orch._cancel_standalone_delivery_gate(authority) == 1
    exact.cancel_owner.assert_called_once()
    exact.cancel_generation.assert_not_called()


def test_real_orchestrator_provider_store_and_project_create_review(harness):
    """Real collaborators catch calls to nonexistent ProviderStore/Project APIs."""
    orch, project, tracker, provider, detect, gate = harness
    task = _issue("TASK-1", branch="feature/task-1")
    tracker.fetch_issues_by_states.return_value = [task]
    provider.create_review.return_value = _review(
        "feature/task-1",
        review_id="101",
    )

    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert isinstance(orch.provider_store, ProviderStore)
    assert isinstance(project, Project)
    detect.assert_called_once_with(
        project.repo_url,
        access_token=project.access_token,
    )
    provider.get_branch_head_sha.assert_any_call(
        "org/repo",
        "feature/task-1",
    )
    gate.assert_called_once_with(
        project,
        task,
        "feature/task-1",
        "trunk",
    )
    provider.create_review.assert_called_once_with(
        "org/repo",
        "TASK-1: Title for TASK-1",
        "feature/task-1",
        target_branch="trunk",
        description="Description for TASK-1",
    )
    tracker.update_issue.assert_called_once_with("TASK-1", status=IN_REVIEW)
    assert not _delivery_alerts(orch)


def test_standalone_delivery_selects_priority_then_submitted_fifo(harness):
    """A newer Ready arrival cannot overtake an older equal-priority row."""

    orch, project, tracker, provider, _detect, gate = harness
    project.max_in_flight_prs = 3
    low_old = _issue(
        "TASK-LOW-OLD",
        priority=3,
        submitted_at="2026-08-01T00:00:00Z",
    )
    high_new = _issue(
        "TASK-HIGH-NEW",
        priority=1,
        submitted_at="2026-08-01T03:00:00Z",
    )
    high_old = _issue(
        "TASK-HIGH-OLD",
        priority=1,
        submitted_at="2026-08-01T02:00:00Z",
    )
    provider.list_open_reviews.return_value = []
    provider.create_review.side_effect = [
        _review("TASK-HIGH-OLD", review_id="priority-1"),
        _review("TASK-HIGH-NEW", review_id="priority-2"),
    ]
    tracker.fetch_issues_by_states.return_value = [low_old, high_new, high_old]

    orch._reconcile_standalone_ready_to_integrate_tasks()
    tracker.fetch_issues_by_states.return_value = [low_old, high_new]
    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert gate.call_args_list == [
        mock.call(project, high_old, "TASK-HIGH-OLD", "trunk"),
        mock.call(project, high_new, "TASK-HIGH-NEW", "trunk"),
    ]
    assert provider.create_review.call_args_list[0].args[1].startswith(
        "TASK-HIGH-OLD:"
    )
    assert provider.create_review.call_args_list[1].args[1].startswith(
        "TASK-HIGH-NEW:"
    )


def test_invalid_old_candidate_falls_through_without_claiming_later_rows(harness):
    """An invalid oldest row does not block the next ordered candidate."""

    orch, project, tracker, provider, _detect, gate = harness
    project.max_in_flight_prs = 3
    invalid = _issue(
        "TASK-INVALID-OLD",
        submitted_at="2026-08-01T00:00:00Z",
    )
    valid = _issue(
        "TASK-VALID-NEXT",
        submitted_at="2026-08-01T01:00:00Z",
    )
    unselected = _issue(
        "TASK-UNSELECTED",
        submitted_at="2026-08-01T02:00:00Z",
    )
    provider.get_branch_head_sha.side_effect = (
        lambda _repo, branch: None
        if branch == invalid.work_branch
        else "abc123"
    )
    provider.list_open_reviews.return_value = []
    provider.create_review.return_value = _review(
        "TASK-VALID-NEXT",
        review_id="fallback-1",
    )
    tracker.fetch_issues_by_states.return_value = [invalid, valid, unselected]

    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert gate.call_args_list == [
        mock.call(project, valid, "TASK-VALID-NEXT", "trunk"),
    ]
    assert provider.create_review.call_count == 1
    assert (project.id, invalid.identifier) in orch._standalone_delivery_authorities
    assert (project.id, valid.identifier) in orch._standalone_delivery_authorities
    assert (project.id, unselected.identifier) not in orch._standalone_delivery_authorities
    assert "not present on the remote" in next(
        alert["message"]
        for alert in _delivery_alerts(orch)
        if invalid.identifier in alert["message"]
    )


def test_dependency_blocked_candidate_does_not_claim_or_block_next(harness):
    """A finish-order wait is excluded before the next candidate is claimed."""

    orch, project, tracker, provider, _detect, gate = harness
    blocked = _issue(
        "TASK-BLOCKED-OLD",
        submitted_at="2026-08-01T00:00:00Z",
    )
    blocker = _issue("TASK-BLOCKER")
    blocker.state = OPEN
    blocked.blocked_by = [
        BlockerRef(id=blocker.id, identifier=blocker.identifier)
    ]
    next_task = _issue(
        "TASK-NEXT",
        submitted_at="2026-08-01T01:00:00Z",
    )
    provider.list_open_reviews.return_value = []
    provider.create_review.return_value = _review("TASK-NEXT", review_id="next-1")
    tracker.fetch_issues_by_states.return_value = [blocked, next_task]
    _set_all_issues(tracker, [blocked, blocker, next_task])

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once_with(project, next_task, "TASK-NEXT", "trunk")
    assert (project.id, blocked.identifier) not in orch._standalone_delivery_authorities
    assert provider.create_review.call_count == 1
    assert blocker.identifier in _delivery_alerts(orch)[0]["message"]


def test_unfinished_finish_dependency_defers_gate_and_review_idempotently(harness):
    """A direct Ready task waits without consuming a gate or CI-fix retry."""

    orch, project, tracker, provider, detect, gate = harness
    task = _issue("TASK-WAIT")
    blocker = _issue("TASK-UPSTREAM")
    blocker.state = OPEN
    task.blocked_by = [BlockerRef(id=blocker.id, identifier=blocker.identifier)]
    tracker.fetch_issues_by_states.return_value = [task]
    _set_all_issues(tracker, [task, blocker])

    orch._reconcile_standalone_ready_to_integrate_tasks()
    orch._reconcile_standalone_ready_to_integrate_tasks()

    detect.assert_not_called()
    provider.get_branch_head_sha.assert_not_called()
    provider.create_review.assert_not_called()
    gate.assert_not_called()
    tracker.update_issue.assert_not_called()
    assert task.state == READY_TO_INTEGRATE
    alerts = _delivery_alerts(orch)
    assert len(alerts) == 1
    assert alerts[0]["level"] == "info"
    assert blocker.identifier in alerts[0]["message"]


def test_unfinished_finish_dependency_stays_deferred_after_restart(
    tmp_path,
    monkeypatch,
):
    """Restart recovery preserves a dependency wait instead of spending a gate."""

    project = Project(
        id="proj-wait-restart",
        name="Restart Wait",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="trunk",
    )
    task = _issue("TASK-WAIT-RESTART")
    blocker = _issue("TASK-WAIT-UPSTREAM")
    blocker.state = OPEN
    task.blocked_by = [BlockerRef(id=blocker.id, identifier=blocker.identifier)]
    tracker = mock.MagicMock()
    tracker.fetch_issues_by_states.return_value = [task]
    tracker.fetch_all_issues.return_value = [task, blocker]
    tracker.fetch_issue_detail.side_effect = lambda identifier: next(
        (
            issue
            for issue in (task, blocker)
            if identifier in {issue.id, issue.identifier}
        ),
        None,
    )
    provider = mock.MagicMock(spec=SCMProvider)
    provider.get_branch_head_sha.return_value = "wait-head"
    detect = mock.MagicMock(return_value=provider)
    monkeypatch.setattr("oompah.orchestrator.detect_provider", detect)

    orch_one = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker,
        provider_store=ProviderStore(str(tmp_path / "providers-one.json")),
        state_name="state-one.json",
    )
    orch_two = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker,
        provider_store=ProviderStore(str(tmp_path / "providers-two.json")),
        state_name="state-two.json",
    )
    gate_one = mock.MagicMock(return_value=True)
    gate_two = mock.MagicMock(return_value=True)
    monkeypatch.setattr(orch_one, "_review_quality_gate_passes", gate_one)
    monkeypatch.setattr(orch_two, "_review_quality_gate_passes", gate_two)

    try:
        orch_one._reconcile_standalone_ready_to_integrate_tasks()
        orch_two._reconcile_standalone_ready_to_integrate_tasks()

        detect.assert_not_called()
        provider.create_review.assert_not_called()
        gate_one.assert_not_called()
        gate_two.assert_not_called()
        assert len(_delivery_alerts(orch_one)) == 1
        assert len(_delivery_alerts(orch_two)) == 1
    finally:
        _close_orchestrator(orch_one)
        _close_orchestrator(orch_two)


def test_terminal_audit_satisfied_dependency_releases_one_gate(harness):
    """A terminal dependency resumes the submitted head through normal delivery."""

    orch, project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-RELEASE")
    blocker = _issue("TASK-AUDITED")
    blocker.state = MERGED
    task.blocked_by = [BlockerRef(id=blocker.id, identifier=blocker.identifier)]
    tracker.fetch_issues_by_states.return_value = [task]
    _set_all_issues(tracker, [task, blocker])
    provider.create_review.return_value = _review("TASK-RELEASE", review_id="906")

    orch._reconcile_standalone_ready_to_integrate_tasks()
    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once_with(project, task, "TASK-RELEASE", "trunk")
    provider.create_review.assert_called_once()
    tracker.update_issue.assert_called_once_with("TASK-RELEASE", status=IN_REVIEW)
    assert _delivery_alerts(orch)[0]["level"] == "info"
    assert "waiting for review capacity" in _delivery_alerts(orch)[0]["message"]


def test_inherited_finish_dependency_defers_then_releases_delivery(harness):
    """A non-epic parent contributes the same finish-order barrier."""

    orch, project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-INHERITED", parent_id="PARENT")
    parent = _issue("PARENT", issue_type="task")
    parent.state = OPEN
    blocker = _issue("TASK-PARENT-UPSTREAM")
    blocker.state = OPEN
    parent.blocked_by = [BlockerRef(id=blocker.id, identifier=blocker.identifier)]
    tracker.fetch_issues_by_states.return_value = [task]
    _set_all_issues(tracker, [task, parent, blocker])
    provider.create_review.return_value = _review("TASK-INHERITED", review_id="907")

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_not_called()
    provider.create_review.assert_not_called()
    assert blocker.identifier in _delivery_alerts(orch)[0]["message"]

    blocker.state = MERGED
    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once_with(project, task, "TASK-INHERITED", "trunk")
    provider.create_review.assert_called_once()


def test_dependency_regression_fences_stale_delivery_before_review(harness):
    """A dependency reopening cannot let a previously-authorized gate create a PR."""

    orch, _project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-REGRESSION")
    blocker = _issue("TASK-REGRESSION-UPSTREAM")
    blocker.state = MERGED
    task.blocked_by = [BlockerRef(id=blocker.id, identifier=blocker.identifier)]
    tracker.fetch_issues_by_states.return_value = [task]
    _set_all_issues(tracker, [task, blocker])

    def regress_dependency(*_args):
        blocker.state = OPEN
        return True

    gate.side_effect = regress_dependency
    with mock.patch.object(
        orch._branch_quality_gate,
        "cancel_owner",
    ) as cancel_owner:
        orch._reconcile_standalone_ready_to_integrate_tasks()

        provider.create_review.assert_not_called()
        tracker.update_issue.assert_not_called()
        cancel_owner.assert_called_once()

    orch._reconcile_standalone_ready_to_integrate_tasks()
    gate.assert_called_once()
    assert len(_delivery_alerts(orch)) == 1
    assert _delivery_alerts(orch)[0]["level"] == "info"


def test_finish_dependency_resolution_is_isolated_per_project(harness):
    """Same-named dependencies in another project cannot release this task."""

    orch, project_one, tracker_one, provider, _detect, gate = harness
    project_two = Project(
        id="proj-2",
        name="Other Project",
        repo_url="https://github.com/org/other.git",
        repo_path=project_one.repo_path,
        default_branch="trunk",
    )
    task_one = _issue("TASK-PROJECT-ONE")
    blocker_one = _issue("SHARED-UPSTREAM")
    blocker_one.state = OPEN
    task_one.blocked_by = [
        BlockerRef(id=blocker_one.id, identifier=blocker_one.identifier)
    ]
    tracker_one.fetch_issues_by_states.return_value = [task_one]
    _set_all_issues(tracker_one, [task_one, blocker_one])

    task_two = _issue("TASK-PROJECT-TWO")
    blocker_two = _issue("SHARED-UPSTREAM")
    blocker_two.state = MERGED
    task_two.blocked_by = [
        BlockerRef(id=blocker_two.id, identifier=blocker_two.identifier)
    ]
    tracker_two = mock.MagicMock()
    tracker_two.fetch_issues_by_states.return_value = [task_two]
    tracker_two.fetch_all_issues.return_value = [task_two, blocker_two]
    tracker_two.fetch_issue_detail.side_effect = lambda identifier: next(
        (
            issue
            for issue in (task_two, blocker_two)
            if identifier in {issue.id, issue.identifier}
        ),
        None,
    )
    orch.project_store.list_all.return_value = [project_one, project_two]
    orch.project_store.get.side_effect = (
        lambda project_id: {
            project_one.id: project_one,
            project_two.id: project_two,
        }.get(str(project_id))
    )
    orch._project_trackers[project_two.id] = tracker_two
    provider.create_review.return_value = _review("TASK-PROJECT-TWO", review_id="908")

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once_with(project_two, task_two, "TASK-PROJECT-TWO", "trunk")
    provider.create_review.assert_called_once()
    tracker_one.update_issue.assert_not_called()
    assert len(_delivery_alerts(orch)) == 1
    assert task_one.identifier in _delivery_alerts(orch)[0]["message"]


def test_missing_remote_branch_raises_actionable_alert(harness):
    orch, _project, tracker, provider, _detect, gate = harness
    tracker.fetch_issues_by_states.return_value = [_issue("TASK-2")]
    provider.get_branch_head_sha.return_value = None

    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    gate.assert_not_called()
    assert "not present on the remote" in _delivery_alerts(orch)[0]["message"]


def test_existing_open_review_is_reused_idempotently(harness):
    orch, _project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-3")
    tracker.fetch_issues_by_states.return_value = [task]
    provider.find_pr_for_branch.return_value = _review(
        "TASK-3",
        review_id="99",
    )

    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.create_review.assert_not_called()
    gate.assert_not_called()
    tracker.update_issue.assert_called_once_with("TASK-3", status=IN_REVIEW)
    assert [
        call.args[:3]
        for call in tracker.set_metadata_field.call_args_list
    ] == [
        ("TASK-3", "oompah.review_url", "https://github.com/org/repo/pull/99"),
        ("TASK-3", "oompah.review_number", "99"),
        ("TASK-3", "oompah.work_branch", "TASK-3"),
        ("TASK-3", "oompah.target_branch", "trunk"),
        ("TASK-3", "oompah.review_head", "abc123"),
    ]


def test_existing_closed_review_is_replaced_after_gate(harness):
    orch, project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-4")
    tracker.fetch_issues_by_states.return_value = [task]
    provider.find_pr_for_branch.return_value = _review(
        "TASK-4",
        state="closed",
        review_id="17",
    )
    replacement = _review("TASK-4", review_id="18")
    provider.create_review.return_value = replacement

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once_with(project, task, "TASK-4", "trunk")
    provider.create_review.assert_called_once()
    tracker.update_issue.assert_called_once_with("TASK-4", status=IN_REVIEW)


def test_stale_merged_reconciliation_releases_persisted_review_capacity(
    tmp_path,
):
    project = Project(
        id="proj-stale-merge",
        name="Stale Merge Project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="trunk",
    )
    tracker = mock.MagicMock()
    orch = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker,
        provider_store=ProviderStore(str(tmp_path / "providers.json")),
    )
    issue = _issue("TASK-STALE-MERGED", branch="feature/stale-merged")
    issue.project_id = project.id
    reservation = orch.review_capacity_store.adopt(
        project_id=project.id,
        task_id=issue.identifier,
        source_branch=issue.work_branch,
        target_branch=project.default_branch,
        review_id="701",
        reservation_id="reservation-701",
    )
    orch._request_merged_via_coordinator = mock.MagicMock(
        return_value=mock.MagicMock(success=True),
    )

    try:
        orch._mark_stale_in_review_merged(
            tracker,
            issue,
            issue.work_branch,
        )
        assert reservation.review_id == "701"
        assert orch.review_capacity_store.count(project.id, []) == 0
    finally:
        _close_orchestrator(orch)


def test_existing_integration_queue_row_prevents_competing_review(harness):
    orch, project, tracker, provider, detect, gate = harness
    task = _issue("TASK-5")
    tracker.fetch_issues_by_states.return_value = [task]
    orch.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id=task.identifier,
        task_branch=task.work_branch or task.identifier,
        head_sha="abc123",
        priority=task.priority,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )

    orch._reconcile_standalone_ready_to_integrate_tasks()

    detect.assert_not_called()
    provider.get_branch_head_sha.assert_not_called()
    provider.create_review.assert_not_called()
    gate.assert_not_called()
    assert not _delivery_alerts(orch)


def test_duplicate_ticks_do_not_create_duplicate_reviews(harness):
    orch, _project, tracker, provider, _detect, _gate = harness
    task = _issue("TASK-6")
    tracker.fetch_issues_by_states.return_value = [task]
    created = _review("TASK-6", review_id="50")
    # Each delivery mutation performs a final forge CAS under task ownership.
    provider.find_pr_for_branch.side_effect = [None, None, created, created]
    provider.create_review.return_value = created

    orch._reconcile_standalone_ready_to_integrate_tasks()
    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.create_review.assert_called_once()


def test_same_sweep_reserves_review_capacity_without_false_alert(harness):
    orch, project, tracker, provider, _detect, gate = harness
    project.max_in_flight_prs = 1
    first = _issue("TASK-CAPACITY-1")
    second = _issue("TASK-CAPACITY-2")
    tracker.fetch_issues_by_states.return_value = [first, second]
    provider.find_pr_for_branch.return_value = None
    provider.create_review.return_value = _review(
        "TASK-CAPACITY-1",
        review_id="61",
    )
    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.create_review.assert_called_once()
    gate.assert_called_once_with(
        project,
        first,
        "TASK-CAPACITY-1",
        "trunk",
    )
    tracker.update_issue.assert_called_once_with(
        "TASK-CAPACITY-1",
        status=IN_REVIEW,
    )
    assert not _delivery_alerts(orch)


def test_later_sweep_stale_cache_cannot_create_second_review(harness):
    """A stale cache after the first PR still observes durable capacity."""
    orch, project, tracker, provider, _detect, gate = harness
    project.max_in_flight_prs = 1
    first = _issue("TASK-STale-FIRST")
    second = _issue("TASK-STale-SECOND")
    created = _review(first.work_branch or first.identifier, review_id="601")
    provider.find_pr_for_branch.return_value = None
    provider.list_open_reviews.return_value = []
    provider.create_review.return_value = created

    tracker.fetch_issues_by_states.return_value = [first]
    orch._reconcile_standalone_ready_to_integrate_tasks()
    assert provider.create_review.call_count == 1

    # The cache is stale/empty and the forge listing still lags creation.
    orch._reviews_cache = {project.id: []}
    tracker.fetch_issues_by_states.return_value = [second]
    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert provider.create_review.call_count == 1
    assert gate.call_count == 1
    assert _delivery_alerts(orch)[0]["level"] == "info"
    assert "waiting for review capacity" in _delivery_alerts(orch)[0]["message"]


def test_concurrent_ready_sweeps_share_one_durable_slot(harness):
    orch, project, tracker, provider, _detect, gate = harness
    project.max_in_flight_prs = 1
    tracker.fetch_issues_by_states.return_value = [
        _issue("TASK-CONCURRENT-1"),
        _issue("TASK-CONCURRENT-2"),
    ]
    provider.find_pr_for_branch.return_value = None
    provider.list_open_reviews.return_value = []
    provider.create_review.return_value = _review(
        "TASK-CONCURRENT-1",
        review_id="602",
    )

    workers = [
        threading.Thread(
            target=orch._reconcile_standalone_ready_to_integrate_tasks,
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert provider.create_review.call_count == 1
    assert not _delivery_alerts(orch)


def test_service_restart_rediscovers_existing_review_without_duplicate(
    tmp_path,
    monkeypatch,
):
    project = Project(
        id="proj-restart",
        name="Restart Project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="trunk",
    )
    provider_store = ProviderStore(str(tmp_path / "providers.json"))
    provider = mock.MagicMock(spec=SCMProvider)
    provider.get_branch_head_sha.return_value = "restart-sha"
    created = _review("TASK-7", review_id="77")
    created.head_sha = "restart-sha"
    # The first process performs lookup + final pre-create CAS; the restarted
    # process performs lookup + final open-review adoption CAS.
    provider.find_pr_for_branch.side_effect = [None, None, created, created]
    provider.create_review.return_value = created
    monkeypatch.setattr("oompah.orchestrator.detect_provider", lambda *_a, **_k: provider)

    tracker_one = mock.MagicMock()
    task_one = _issue("TASK-7")
    tracker_one.fetch_issues_by_states.return_value = [task_one]
    tracker_one.fetch_issue_detail.return_value = task_one
    orch_one = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker_one,
        provider_store=provider_store,
    )
    with mock.patch.object(
        orch_one,
        "_review_quality_gate_passes",
        return_value=True,
    ):
        orch_one._reconcile_standalone_ready_to_integrate_tasks()
    _close_orchestrator(orch_one)

    tracker_two = mock.MagicMock()
    task_two = _issue("TASK-7")
    tracker_two.fetch_issues_by_states.return_value = [task_two]
    tracker_two.fetch_issue_detail.return_value = task_two
    orch_two = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker_two,
        provider_store=ProviderStore(str(tmp_path / "providers.json")),
    )
    try:
        with mock.patch.object(
            orch_two,
            "_review_quality_gate_passes",
            return_value=True,
        ) as restarted_gate:
            orch_two._reconcile_standalone_ready_to_integrate_tasks()
        provider.create_review.assert_called_once()
        restarted_gate.assert_not_called()
        tracker_two.update_issue.assert_called_once_with(
            "TASK-7",
            status=IN_REVIEW,
        )
    finally:
        _close_orchestrator(orch_two)


def test_gate_failure_blocks_review_and_ready_retry_can_succeed(harness):
    orch, project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-8")
    tracker.fetch_issues_by_states.return_value = [task]
    provider.find_pr_for_branch.return_value = None
    provider.create_review.return_value = _review("TASK-8", review_id="88")
    gate.side_effect = [False, True]

    orch._reconcile_standalone_ready_to_integrate_tasks()
    provider.create_review.assert_not_called()
    assert "quality gate did not pass" in _delivery_alerts(orch)[0]["message"]

    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert gate.call_args_list == [
        mock.call(project, task, "TASK-8", "trunk"),
        mock.call(project, task, "TASK-8", "trunk"),
    ]
    provider.create_review.assert_called_once()
    tracker.update_issue.assert_called_once_with("TASK-8", status=IN_REVIEW)
    assert not _delivery_alerts(orch)


def test_owner_override_during_failed_gate_cancels_stale_delivery(harness):
    """A terminal owner override wins over a gate failure already in flight."""

    orch, project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-OVERRIDE-FAIL", branch="feature/override-fail")
    tracker.fetch_issues_by_states.return_value = [task]
    project.status_label_authorized_logins = ["owner"]
    tracker.fetch_issue_detail.return_value = task
    tracker.get_metadata.return_value = {}
    tracker.update_issue.side_effect = (
        lambda _identifier, **fields: setattr(task, "state", fields["status"])
        if "status" in fields
        else None
    )

    def override_then_fail(*_args):
        result = asyncio.run(
            orch.terminal_transition_coordinator.override_transition(
                current_issue=task,
                requested_target=TargetState.MERGED,
                authorized_actor=ContributorIdentity("owner", "test"),
                project_id=project.id,
                evidence_fingerprint=EvidenceFingerprint.from_evidence(
                    requirements_text=task.description or "",
                    project_id=project.id,
                    task_id=task.identifier,
                ),
                reason="Verified branch already matches the target.",
                project=project,
            )
        )
        assert result.success is True
        return False

    gate.side_effect = override_then_fail

    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert task.state == MERGED
    assert [call.kwargs.get("status") for call in tracker.update_issue.call_args_list] == [
        MERGED
    ]
    provider.create_review.assert_not_called()
    assert not _delivery_alerts(orch)


def test_owner_override_during_passing_gate_cancels_review_creation(harness):
    """A successful stale gate cannot create a review after terminal ownership."""

    orch, project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-OVERRIDE-PASS", branch="feature/override-pass")
    tracker.fetch_issues_by_states.return_value = [task]
    project.status_label_authorized_logins = ["owner"]
    tracker.fetch_issue_detail.return_value = task
    tracker.get_metadata.return_value = {}
    tracker.update_issue.side_effect = (
        lambda _identifier, **fields: setattr(task, "state", fields["status"])
        if "status" in fields
        else None
    )

    def override_then_pass(*_args):
        result = asyncio.run(
            orch.terminal_transition_coordinator.override_transition(
                current_issue=task,
                requested_target=TargetState.MERGED,
                authorized_actor=ContributorIdentity("owner", "test"),
                project_id=project.id,
                evidence_fingerprint=EvidenceFingerprint.from_evidence(
                    requirements_text=task.description or "",
                    project_id=project.id,
                    task_id=task.identifier,
                ),
                reason="Verified branch already matches the target.",
                project=project,
            )
        )
        assert result.success is True
        return True

    gate.side_effect = override_then_pass

    orch._reconcile_standalone_ready_to_integrate_tasks()
    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert task.state == MERGED
    assert [call.kwargs.get("status") for call in tracker.update_issue.call_args_list] == [
        MERGED
    ]
    provider.create_review.assert_not_called()
    assert not _delivery_alerts(orch)


def test_changed_remote_head_cancels_stale_gate_result(harness):
    """A force-push during the gate cannot create a review for the old head."""

    orch, _project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-HEAD-RACE", branch="feature/head-race")
    tracker.fetch_issues_by_states.return_value = [task]
    tracker.fetch_issue_detail.return_value = task
    provider.get_branch_head_sha.side_effect = ["head-before", "head-after"]
    gate.return_value = True

    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    assert task.state == READY_TO_INTEGRATE
    assert not _delivery_alerts(orch)


def test_remote_head_must_match_accepted_submission_before_gate(harness):
    """A newer remote tip cannot replace the exact head accepted by submit."""
    orch, _project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-SUBMITTED-HEAD", branch="feature/submitted-head")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch="feature/submitted-head",
        head_sha="a" * 40,
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = "b" * 40

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_not_called()
    provider.find_pr_for_branch.assert_not_called()
    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    alerts = _delivery_alerts(orch)
    assert len(alerts) == 1
    assert "advanced from accepted submitted head" in alerts[0]["message"]


def test_oompah_818_old_merged_review_cannot_terminalize_new_submission(harness):
    """A reused branch's historical merged PR cannot own its newer accepted head."""

    orch, project, tracker, provider, _detect, gate = harness
    old_head = "f1270e41dd9b91e689094ba4007c6922d1a7aab8"
    new_head = "e3140b65f4958a4b7f89a1fc414bb53e88215dc4"
    task = _issue("OOMPAH-818", branch="OOMPAH-818")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch="OOMPAH-818",
        head_sha=new_head,
        submitted_at="2026-08-05T02:58:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = new_head
    provider.find_pr_for_branch.return_value = _review(
        "OOMPAH-818",
        state="merged",
        review_id="716",
        head_sha=old_head,
    )
    provider.list_open_reviews.return_value = []
    provider.create_review.return_value = _review(
        "OOMPAH-818",
        review_id="717",
        head_sha=new_head,
    )
    orch._request_merged_via_coordinator = mock.MagicMock()

    orch._reconcile_standalone_ready_to_integrate_tasks()

    orch._request_merged_via_coordinator.assert_not_called()
    assert orch.integration_queue.get(project.id, task.identifier) is None
    gate.assert_called_once_with(project, task, "OOMPAH-818", "trunk")
    provider.create_review.assert_called_once()
    tracker.update_issue.assert_called_once_with(task.identifier, status=IN_REVIEW)
    tracker.add_comment.assert_called_once()
    assert "historical evidence" in tracker.add_comment.call_args.args[1]
    assert not _delivery_alerts(orch)


def test_non_exact_open_review_defers_without_creating_competitor(harness):
    """An open review for an older head must block duplicate PR creation."""

    orch, _project, tracker, provider, _detect, gate = harness
    new_head = "b" * 40
    task = _issue("TASK-OPEN-OLD", branch="feature/open-old")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=new_head,
        submitted_at="2026-08-05T03:00:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = new_head
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="open",
        review_id="700",
        head_sha="a" * 40,
    )

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_not_called()
    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()
    assert "cannot be proven" in _delivery_alerts(orch)[0]["message"]


def test_merged_review_without_head_fails_closed_on_containment_error(harness):
    """Ambiguous legacy merge evidence cannot terminalize or create a new PR."""

    orch, project, tracker, provider, _detect, gate = harness
    accepted_head = "c" * 40
    task = _issue("TASK-LEGACY-UNKNOWN", branch="feature/legacy-unknown")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:01:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="merged",
        review_id="701",
        head_sha="",
    )
    orch._request_merged_via_coordinator = mock.MagicMock()

    with (
        mock.patch.object(
            orch,
            "_get_branch_head_sha",
            return_value=accepted_head,
        ),
        mock.patch.object(
            orch,
            "_count_review_branch_ahead",
            return_value=(0, [], "target ref unavailable"),
        ),
    ):
        orch._reconcile_standalone_ready_to_integrate_tasks()

    orch._request_merged_via_coordinator.assert_not_called()
    gate.assert_not_called()
    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()
    alert = _delivery_alerts(orch)[0]["message"]
    assert "target containment could not be verified" in alert


def test_historical_review_release_cannot_retire_newer_branch_reservation(harness):
    """A stale review identity cannot release capacity owned by a newer review."""

    orch, project, tracker, provider, _detect, gate = harness
    project.max_in_flight_prs = 1
    new_head = "d" * 40
    task = _issue("TASK-RESERVATION-RACE", branch="feature/reservation-race")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=new_head,
        submitted_at="2026-08-05T03:02:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = new_head
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="merged",
        review_id="old-716",
        head_sha="a" * 40,
    )
    provider.list_open_reviews.return_value = []
    orch.review_capacity_store.adopt(
        project_id=project.id,
        task_id=task.identifier,
        source_branch=task.work_branch or "",
        target_branch=project.default_branch,
        review_id="new-717",
        reservation_id="reservation-new-717",
    )

    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert [
        reservation.review_id
        for reservation in orch.review_capacity_store.active(project.id)
    ] == ["new-717"]
    gate.assert_not_called()
    provider.create_review.assert_not_called()


def test_resubmit_generation_change_after_review_lookup_fences_terminal_staging(
    harness,
):
    """A same-head resubmit revokes a stale lookup before coordinator mutation."""

    orch, _project, tracker, provider, _detect, gate = harness
    accepted_head = "e" * 40
    task = _issue("TASK-RESUBMIT-RACE", branch="feature/resubmit-race")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:03:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    exact_merged = _review(
        task.work_branch or "",
        state="merged",
        review_id="702",
        head_sha=accepted_head,
    )

    def resubmit_during_lookup(*_args):
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha=accepted_head,
            submitted_at="2026-08-05T03:04:00+00:00",
        )
        return exact_merged

    provider.find_pr_for_branch.side_effect = resubmit_during_lookup
    orch._request_merged_via_coordinator = mock.MagicMock()

    orch._reconcile_standalone_ready_to_integrate_tasks()

    orch._request_merged_via_coordinator.assert_not_called()
    gate.assert_not_called()
    provider.create_review.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    assert task.state == READY_TO_INTEGRATE


def test_resubmit_waiting_on_transition_lock_revokes_final_staging_cas(harness):
    """The final CAS observes a submit generation that won task ownership first."""

    orch, project, tracker, provider, _detect, _gate = harness
    accepted_head = "f" * 40
    task = _issue("TASK-FINAL-CAS", branch="feature/final-cas")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:05:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    assert orch._set_standalone_delivery_head(
        authority,
        task.work_branch or "",
        accepted_head,
        lambda: accepted_head,
    )
    orch.request_terminal_transition = mock.AsyncMock()

    async def race() -> tuple[bool, object | None]:
        lock = orch.issue_transition_lock(task.id)
        await lock.acquire()
        staging = asyncio.create_task(
            orch._request_standalone_merged_with_authority_async(
                authority,
                tracker,
                provider=provider,
                repo_slug="org/repo",
                work_branch=task.work_branch or "",
                target_branch=project.default_branch,
                review_number="703",
                review_url="https://github.com/org/repo/pull/703",
                review_head=accepted_head,
            )
        )
        await asyncio.sleep(0)
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha=accepted_head,
            submitted_at="2026-08-05T03:06:00+00:00",
        )
        lock.release()
        return await asyncio.wait_for(staging, timeout=2)

    staged, transition = asyncio.run(race())

    assert staged is False
    assert transition is None
    orch.request_terminal_transition.assert_not_awaited()


def test_two_loop_submit_wins_before_exact_review_metadata_or_audit(harness):
    """Cross-loop submit ownership fences every stale exact-review mutation."""

    orch, project, tracker, provider, _detect, _gate = harness
    old_head = "1" * 40
    task = _issue("TASK-TWO-LOOP", branch="feature/two-loop")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=old_head,
        submitted_at="2026-08-05T03:07:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    assert orch._set_standalone_delivery_head(
        authority,
        task.work_branch or "",
        old_head,
        lambda: old_head,
    )
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="merged",
        review_id="704",
        head_sha=old_head,
    )
    orch.request_terminal_transition = mock.AsyncMock()
    submit_written = threading.Event()
    release_submit = threading.Event()
    staging_results: list[tuple[bool, object | None]] = []

    def submit_loop() -> None:
        async def submit() -> None:
            async with orch.issue_transition_lock(task.id):
                task.integration = IntegrationRecord(
                    state="ready",
                    task_branch=task.work_branch,
                    head_sha="2" * 40,
                    submitted_at="2026-08-05T03:08:00+00:00",
                )
                submit_written.set()
                await asyncio.to_thread(release_submit.wait, 2)

        asyncio.run(submit())

    def delivery_loop() -> None:
        staging_results.append(
            asyncio.run(
                orch._request_standalone_merged_with_authority_async(
                    authority,
                    tracker,
                    provider=provider,
                    repo_slug="org/repo",
                    work_branch=task.work_branch or "",
                    target_branch=project.default_branch,
                    review_number="704",
                    review_url="https://github.com/org/repo/pull/704",
                    review_head=old_head,
                )
            )
        )

    submit_worker = threading.Thread(target=submit_loop)
    delivery_worker = threading.Thread(target=delivery_loop)
    submit_worker.start()
    assert submit_written.wait(timeout=2)
    delivery_worker.start()
    assert delivery_worker.is_alive()
    release_submit.set()
    submit_worker.join(timeout=3)
    delivery_worker.join(timeout=3)

    assert not submit_worker.is_alive()
    assert not delivery_worker.is_alive()
    assert staging_results == [(False, None)]
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    orch.request_terminal_transition.assert_not_awaited()


def test_new_submit_fences_old_webhook_snapshot_after_lock_wait(harness):
    """A webhook fetched before submit cannot stage the newer task generation."""

    orch, project, tracker, _provider, _detect, _gate = harness
    old_head = "b" * 40
    task = _issue("TASK-WEBHOOK-FENCE", branch="feature/webhook-fence")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=old_head,
        submitted_at="2026-08-05T03:11:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    webhook_snapshot = copy.deepcopy(task)
    webhook_snapshot.project_id = project.id
    orch.request_terminal_transition = mock.AsyncMock()

    async def race():
        lock = orch.issue_transition_lock(task.id)
        await lock.acquire()
        request = asyncio.create_task(
            orch.request_terminal_transition_owned(
                current_issue=webhook_snapshot,
                requested_target=TargetState.MERGED,
                trigger_identity=ContributorIdentity("webhook", "forge"),
                project_id=project.id,
            )
        )
        await asyncio.sleep(0)
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha="c" * 40,
            submitted_at="2026-08-05T03:12:00+00:00",
        )
        lock.release()
        return await asyncio.wait_for(request, timeout=2)

    result = asyncio.run(race())

    assert result.success is False
    assert "generation changed" in (result.reason or "")
    orch.request_terminal_transition.assert_not_awaited()


def test_owned_webhook_refresh_preserves_intentional_state_override(harness):
    """Fresh evidence is used without restoring an already-visible terminal label."""

    orch, project, tracker, _provider, _detect, _gate = harness
    task = _issue("TASK-WEBHOOK-STATE", branch="feature/webhook-state")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha="d" * 40,
        submitted_at="2026-08-05T03:13:00+00:00",
    )
    task.state = MERGED
    tracker.fetch_issues_by_states.return_value = [task]
    webhook_snapshot = copy.deepcopy(task)
    webhook_snapshot.state = IN_REVIEW
    webhook_snapshot.project_id = project.id
    orch.request_terminal_transition = mock.AsyncMock(
        return_value=mock.MagicMock(success=True)
    )

    result = asyncio.run(
        orch.request_terminal_transition_owned(
            current_issue=webhook_snapshot,
            requested_target=TargetState.MERGED,
            trigger_identity=ContributorIdentity("webhook", "forge"),
            project_id=project.id,
        )
    )

    assert result.success is True
    staged_issue = orch.request_terminal_transition.await_args.kwargs["current_issue"]
    assert staged_issue is not task
    assert staged_issue.state == IN_REVIEW
    assert staged_issue.integration.head_sha == "d" * 40


def test_submit_wins_before_open_webhook_adoption(harness):
    """A delayed open webhook cannot overwrite a newer accepted submission."""

    from oompah.server import _mark_task_in_review_from_webhook
    from oompah.webhooks import WebhookEvent

    orch, project, tracker, provider, _detect, _gate = harness
    old_head = "e" * 40
    task = _issue("TASK-OPEN-WEBHOOK", branch="feature/open-webhook")
    task.target_branch = project.default_branch
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        base_branch=project.default_branch,
        head_sha=old_head,
        submitted_at="2026-08-05T03:14:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    observed = copy.deepcopy(task)
    resolved = threading.Event()
    orch._resolve_task_for_branch = mock.MagicMock(
        side_effect=lambda *_args, **_kwargs: resolved.set() or observed
    )
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="open",
        review_id="711",
        head_sha=old_head,
    )
    event = WebhookEvent(
        provider="github",
        event_type="pull_request",
        action="opened",
        repo_slug="org/repo",
        review_id="711",
        source_branch=task.work_branch or "",
        target_branch=project.default_branch,
        review_head=old_head,
    )
    errors: list[BaseException] = []

    def deliver_webhook() -> None:
        try:
            with mock.patch("oompah.server.detect_provider", return_value=provider):
                _mark_task_in_review_from_webhook(orch, event, project)
        except BaseException as exc:  # noqa: BLE001 - surface thread failure
            errors.append(exc)

    worker = threading.Thread(target=deliver_webhook)
    lock = orch.issue_transition_lock(task.id)
    with lock.sync():
        worker.start()
        assert resolved.wait(timeout=2)
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            base_branch=project.default_branch,
            head_sha="f" * 40,
            submitted_at="2026-08-05T03:15:00+00:00",
        )
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert errors == []
    provider.find_pr_for_branch.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    assert task.state == READY_TO_INTEGRATE
    assert task.integration.head_sha == "f" * 40


def test_exact_open_webhook_persists_metadata_before_in_review(harness):
    """The production owned webhook path accepts one exact review generation."""

    orch, project, tracker, provider, _detect, _gate = harness
    accepted_head = "0" * 40
    task = _issue("TASK-OPEN-WEBHOOK-EXACT", branch="feature/open-webhook-exact")
    task.target_branch = project.default_branch
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        base_branch=project.default_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:16:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    observed = copy.deepcopy(task)
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="open",
        review_id="715",
        head_sha=accepted_head,
    )
    metadata_attributes = {
        "oompah.review_url": "review_url",
        "oompah.review_number": "review_number",
        "oompah.work_branch": "work_branch",
        "oompah.target_branch": "target_branch",
        "oompah.review_head": "review_head",
    }

    def persist_metadata(_identifier, key, value) -> None:
        setattr(task, metadata_attributes[key], value)

    def persist_status(_identifier, **fields) -> None:
        task.state = fields["status"]

    tracker.set_metadata_field.side_effect = persist_metadata
    tracker.update_issue.side_effect = persist_status
    review_url = "https://github.com/org/repo/pull/715"

    adopted, reason = orch.adopt_open_review_from_webhook(
        observed_issue=observed,
        project=project,
        tracker=tracker,
        provider=provider,
        repo_slug="org/repo",
        review_id="715",
        review_url=review_url,
        source_branch=task.work_branch or "",
        target_branch=project.default_branch,
        review_head=accepted_head,
    )

    assert adopted is True
    assert reason == ""
    assert task.review_number == "715"
    assert task.review_url == review_url
    assert task.review_head == accepted_head
    assert task.state == IN_REVIEW
    tracker.update_issue.assert_called_once_with(task.identifier, status=IN_REVIEW)


def test_submit_wins_before_historical_review_cleanup(harness):
    """History comments and clears cannot cross a newer submit generation."""

    orch, _project, tracker, provider, _detect, gate = harness
    accepted_head = "7" * 40
    task = _issue("TASK-HISTORY-OWNED", branch="feature/history-owned")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:12:00+00:00",
    )
    task.review_number = "old-708"
    task.review_url = "https://github.com/org/repo/pull/708"
    task.review_head = "6" * 40
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    initial_lookup = threading.Event()
    provider.find_pr_for_branch.side_effect = lambda *_args: (
        initial_lookup.set()
        or _review(
            task.work_branch or "",
            state="merged",
            review_id="old-708",
            head_sha="6" * 40,
        )
    )
    errors: list[BaseException] = []

    def reconcile() -> None:
        try:
            orch._reconcile_standalone_ready_to_integrate_tasks()
        except BaseException as exc:  # noqa: BLE001 - surface thread failure
            errors.append(exc)

    worker = threading.Thread(target=reconcile)
    lock = orch.issue_transition_lock(task.id)
    with lock.sync():
        worker.start()
        assert initial_lookup.wait(timeout=2)
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha=accepted_head,
            submitted_at="2026-08-05T03:13:00+00:00",
        )
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert errors == []
    tracker.add_comment.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    gate.assert_not_called()


def test_submit_wins_before_open_review_adoption(harness):
    """Open-review metadata and In Review cannot cross a newer submit."""

    orch, _project, tracker, provider, _detect, gate = harness
    accepted_head = "8" * 40
    task = _issue("TASK-OPEN-OWNED", branch="feature/open-owned")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:14:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    exact_open = _review(
        task.work_branch or "",
        state="open",
        review_id="709",
        head_sha=accepted_head,
    )
    initial_lookup = threading.Event()
    provider.find_pr_for_branch.side_effect = lambda *_args: (
        initial_lookup.set() or exact_open
    )
    errors: list[BaseException] = []

    def reconcile() -> None:
        try:
            orch._reconcile_standalone_ready_to_integrate_tasks()
        except BaseException as exc:  # noqa: BLE001 - surface thread failure
            errors.append(exc)

    worker = threading.Thread(target=reconcile)
    lock = orch.issue_transition_lock(task.id)
    with lock.sync():
        worker.start()
        assert initial_lookup.wait(timeout=2)
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha=accepted_head,
            submitted_at="2026-08-05T03:15:00+00:00",
        )
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert errors == []
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    gate.assert_not_called()


def test_submit_wins_after_gate_before_review_create(harness):
    """The gate stays unlocked, but final create is fenced by submit ownership."""

    orch, _project, tracker, provider, _detect, gate = harness
    accepted_head = "9" * 40
    task = _issue("TASK-CREATE-OWNED", branch="feature/create-owned")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:16:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    provider.find_pr_for_branch.return_value = None
    gate_complete = threading.Event()
    gate.side_effect = lambda *_args: gate_complete.set() or True
    errors: list[BaseException] = []

    def reconcile() -> None:
        try:
            orch._reconcile_standalone_ready_to_integrate_tasks()
        except BaseException as exc:  # noqa: BLE001 - surface thread failure
            errors.append(exc)

    worker = threading.Thread(target=reconcile)
    lock = orch.issue_transition_lock(task.id)
    with lock.sync():
        worker.start()
        assert gate_complete.wait(timeout=2)
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha=accepted_head,
            submitted_at="2026-08-05T03:17:00+00:00",
        )
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert errors == []
    provider.create_review.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_review_appearing_after_gate_prevents_duplicate_create(harness):
    """A final forge observation detects a review created by another worker."""

    orch, _project, tracker, provider, _detect, gate = harness
    accepted_head = "a" * 40
    task = _issue("TASK-CREATE-CAS", branch="feature/create-cas")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:18:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    appeared = _review(
        task.work_branch or "",
        state="open",
        review_id="710",
        head_sha=accepted_head,
    )
    provider.find_pr_for_branch.side_effect = [None, appeared]

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once()
    provider.create_review.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_metadata_refresh_never_adopts_concurrent_integration_generation(harness):
    """A post-CAS integration write revokes authority instead of refreshing it."""

    orch, project, tracker, _provider, _detect, _gate = harness
    task = _issue("TASK-NO-ADOPT", branch="feature/no-adopt")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha="3" * 40,
        submitted_at="2026-08-05T03:09:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    assert orch._set_standalone_delivery_head(
        authority,
        task.work_branch or "",
        "3" * 40,
        lambda: "3" * 40,
    )

    def generation_changes_during_write(*_args) -> None:
        task.integration = IntegrationRecord(
            state="ready",
            task_branch=task.work_branch,
            head_sha="4" * 40,
            submitted_at="2026-08-05T03:10:00+00:00",
        )

    tracker.set_metadata_field.side_effect = generation_changes_during_write

    mutated = orch._standalone_delivery_mutation(
        authority,
        tracker,
        lambda: tracker.set_metadata_field(
            task.identifier,
            "oompah.review_number",
            "705",
        ),
    )

    assert mutated is False
    assert authority.revoked is True
    assert authority.evidence_revision[-6] == "3" * 40
    assert (project.id, task.identifier) not in orch._standalone_delivery_authorities


def test_open_review_metadata_failure_cannot_advance_status(harness):
    """Every authority-owned review field is required before In Review."""

    orch, _project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-OPEN-METADATA", branch="feature/open-metadata")
    tracker.fetch_issues_by_states.return_value = [task]
    exact_open = _review(
        task.work_branch or "",
        state="open",
        review_id="713",
        head_sha="abc123",
    )
    provider.find_pr_for_branch.return_value = exact_open

    def fail_review_head(_identifier, key, _value) -> None:
        if key == "oompah.review_head":
            raise RuntimeError("review head persistence failed")

    tracker.set_metadata_field.side_effect = fail_review_head

    orch._reconcile_standalone_ready_to_integrate_tasks()

    tracker.update_issue.assert_not_called()
    gate.assert_not_called()


def test_created_review_metadata_failure_cannot_advance_status(harness):
    """A created review remains Ready when exact metadata persistence fails."""

    orch, _project, tracker, provider, _detect, gate = harness
    task = _issue("TASK-CREATE-METADATA", branch="feature/create-metadata")
    tracker.fetch_issues_by_states.return_value = [task]
    provider.find_pr_for_branch.return_value = None
    provider.create_review.return_value = _review(
        task.work_branch or "",
        state="open",
        review_id="714",
        head_sha="abc123",
    )

    def fail_review_head(_identifier, key, _value) -> None:
        if key == "oompah.review_head":
            raise RuntimeError("review head persistence failed")

    tracker.set_metadata_field.side_effect = fail_review_head

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_called_once()
    provider.create_review.assert_called_once()
    tracker.update_issue.assert_not_called()


def test_final_review_revalidation_rejects_state_change_before_metadata(harness):
    """A review that is no longer exact-Merged cannot reach tracker or audit writes."""

    orch, _project, tracker, provider, _detect, gate = harness
    accepted_head = "5" * 40
    task = _issue("TASK-REVIEW-CAS", branch="feature/review-cas")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:11:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    provider.find_pr_for_branch.side_effect = [
        _review(
            task.work_branch or "",
            state="merged",
            review_id="706",
            head_sha=accepted_head,
        ),
        _review(
            task.work_branch or "",
            state="open",
            review_id="706",
            head_sha=accepted_head,
        ),
    ]
    orch.request_terminal_transition = mock.AsyncMock()

    orch._reconcile_standalone_ready_to_integrate_tasks()

    assert provider.find_pr_for_branch.call_count == 2
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    orch.request_terminal_transition.assert_not_awaited()
    gate.assert_not_called()


def test_stopped_dispatch_loop_bridge_fails_bounded_without_leaking_coroutine(
    harness,
):
    """A loop shutdown race returns for retry instead of blocking maintenance."""

    orch, project, tracker, provider, _detect, _gate = harness
    task = _issue("TASK-LOOP-STOP", branch="feature/loop-stop")
    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    stopped_loop = mock.MagicMock()
    stopped_loop.is_running.return_value = True
    orch._dispatch_loop = stopped_loop

    with (
        mock.patch.object(orch, "_running_loop", return_value=None),
        mock.patch(
            "oompah.orchestrator.asyncio.run_coroutine_threadsafe",
            side_effect=RuntimeError("loop stopped"),
        ),
    ):
        started = time.monotonic()
        result = orch._request_standalone_merged_with_authority(
            authority,
            tracker,
            provider=provider,
            repo_slug="org/repo",
            work_branch=task.work_branch or "",
            target_branch=project.default_branch,
            review_number="707",
            review_url="https://github.com/org/repo/pull/707",
            review_head="6" * 40,
        )

    assert result == (False, None)
    assert time.monotonic() - started < 1


def test_bridge_timeout_retains_task_ownership_until_inner_operation_exits(harness):
    """A timed-out bridge cannot orphan coordinator work outside the task lock."""

    orch, project, tracker, provider, _detect, _gate = harness
    accepted_head = "1" * 40
    task = _issue("TASK-BRIDGE-OWNER", branch="feature/bridge-owner")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:16:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.get_branch_head_sha.return_value = accepted_head
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="merged",
        review_id="712",
        head_sha=accepted_head,
    )
    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    assert orch._set_standalone_delivery_head(
        authority,
        task.work_branch or "",
        accepted_head,
        lambda: accepted_head,
    )

    coordinator_started = threading.Event()
    release_coordinator = threading.Event()

    async def blocked_coordinator(**_kwargs):
        coordinator_started.set()
        await asyncio.to_thread(release_coordinator.wait)
        return TransitionResult(success=True)

    orch.request_terminal_transition = mock.AsyncMock(side_effect=blocked_coordinator)
    dispatch_loop = asyncio.new_event_loop()
    loop_started = threading.Event()

    def run_dispatch_loop() -> None:
        asyncio.set_event_loop(dispatch_loop)
        dispatch_loop.call_soon(loop_started.set)
        dispatch_loop.run_forever()
        dispatch_loop.close()

    loop_worker = threading.Thread(target=run_dispatch_loop)
    orch._dispatch_loop = dispatch_loop
    loop_worker.start()
    assert loop_started.wait(timeout=2)

    submit_acquired = threading.Event()

    def submit() -> None:
        async def own_task() -> None:
            async with orch.issue_transition_lock(task.id):
                submit_acquired.set()

        asyncio.run(own_task())

    submit_worker = threading.Thread(target=submit)
    try:
        with mock.patch(
            "oompah.orchestrator._STANDALONE_TERMINAL_BRIDGE_TIMEOUT_SECONDS",
            0.05,
        ):
            started = time.monotonic()
            result = orch._request_standalone_merged_with_authority(
                authority,
                tracker,
                provider=provider,
                repo_slug="org/repo",
                work_branch=task.work_branch or "",
                target_branch=project.default_branch,
                review_number="712",
                review_url="https://github.com/org/repo/pull/712",
                review_head=accepted_head,
            )
        assert result == (False, None)
        assert time.monotonic() - started < 1
        assert coordinator_started.wait(timeout=2)

        submit_worker.start()
        assert not submit_acquired.wait(timeout=0.1)

        release_coordinator.set()
        assert submit_acquired.wait(timeout=2)
        submit_worker.join(timeout=2)
        assert not submit_worker.is_alive()
    finally:
        release_coordinator.set()
        if submit_worker.is_alive():
            submit_worker.join(timeout=2)
        dispatch_loop.call_soon_threadsafe(dispatch_loop.stop)
        loop_worker.join(timeout=2)
        orch._dispatch_loop = None

    assert not loop_worker.is_alive()
    orch.request_terminal_transition.assert_awaited_once()


def test_cancelled_bridge_keeps_inner_task_ownership_until_coordinator_exits(harness):
    """Cancelling the outer await cannot expose in-flight terminal side effects."""

    orch, project, tracker, provider, _detect, _gate = harness
    accepted_head = "2" * 40
    task = _issue("TASK-BRIDGE-CANCEL", branch="feature/bridge-cancel")
    task.integration = IntegrationRecord(
        state="ready",
        task_branch=task.work_branch,
        head_sha=accepted_head,
        submitted_at="2026-08-05T03:17:00+00:00",
    )
    tracker.fetch_issues_by_states.return_value = [task]
    provider.find_pr_for_branch.return_value = _review(
        task.work_branch or "",
        state="merged",
        review_id="716",
        head_sha=accepted_head,
    )
    authority = orch._claim_standalone_delivery_authority(project, task)
    assert authority is not None
    assert orch._set_standalone_delivery_head(
        authority,
        task.work_branch or "",
        accepted_head,
        lambda: accepted_head,
    )
    coordinator_started = threading.Event()
    release_coordinator = threading.Event()

    async def blocked_coordinator(**_kwargs):
        coordinator_started.set()
        await asyncio.to_thread(release_coordinator.wait)
        return TransitionResult(success=True)

    orch.request_terminal_transition = mock.AsyncMock(side_effect=blocked_coordinator)

    async def race() -> None:
        outer = asyncio.create_task(
            orch._request_standalone_merged_with_authority_async(
                authority,
                tracker,
                provider=provider,
                repo_slug="org/repo",
                work_branch=task.work_branch or "",
                target_branch=project.default_branch,
                review_number="716",
                review_url="https://github.com/org/repo/pull/716",
                review_head=accepted_head,
            )
        )
        assert await asyncio.to_thread(coordinator_started.wait, 2)
        outer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await outer

        submit_acquired = asyncio.Event()

        async def submit() -> None:
            async with orch.issue_transition_lock(task.id):
                submit_acquired.set()

        submit_task = asyncio.create_task(submit())
        await asyncio.sleep(0.05)
        assert not submit_acquired.is_set()
        release_coordinator.set()
        await asyncio.wait_for(submit_task, timeout=2)

    try:
        asyncio.run(race())
    finally:
        release_coordinator.set()

    orch.request_terminal_transition.assert_awaited_once()


def test_restart_stale_ready_snapshot_cannot_mutate_terminal_task(harness):
    """Fresh task evidence fences a stale Ready record recovered after restart."""

    orch, _project, tracker, provider, _detect, gate = harness
    stale_ready = _issue("TASK-RESTART-STALE", branch="feature/restart-stale")
    terminal_current = copy.deepcopy(stale_ready)
    terminal_current.state = MERGED
    tracker.fetch_issues_by_states.return_value = [stale_ready]
    tracker.fetch_issue_detail.side_effect = None
    tracker.fetch_issue_detail.return_value = terminal_current

    orch._reconcile_standalone_ready_to_integrate_tasks()

    gate.assert_not_called()
    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    assert not _delivery_alerts(orch)


def test_merged_review_completes_real_done_and_merged_audits(
    tmp_path,
    monkeypatch,
):
    project = Project(
        id="proj-audit",
        name="Audit Project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="trunk",
    )
    task = _issue("TASK-9")
    tracker = _MemoryTracker(task)
    provider = mock.MagicMock(spec=SCMProvider)
    provider.get_branch_head_sha.return_value = "merged-sha"
    provider.find_pr_for_branch.return_value = _review(
        "TASK-9",
        state="merged",
        review_id="90",
        head_sha="merged-sha",
    )
    monkeypatch.setattr(
        "oompah.orchestrator.detect_provider",
        lambda *_args, **_kwargs: provider,
    )
    orch = _make_orchestrator(
        tmp_path,
        project=project,
        tracker=tracker,
        provider_store=ProviderStore(str(tmp_path / "providers.json")),
    )
    store = TerminalAuditMetadataStore(
        tracker,
        orch.project_store,
        project.id,
    )

    try:
        errors: list[BaseException] = []

        def reconcile() -> None:
            try:
                orch._reconcile_standalone_ready_to_integrate_tasks()
            except BaseException as exc:  # noqa: BLE001 - surface thread failure
                errors.append(exc)

        worker = threading.Thread(target=reconcile)
        worker.start()
        worker.join(timeout=3)

        assert not worker.is_alive(), "standalone terminal staging deadlocked"
        assert errors == []

        provider.create_review.assert_not_called()
        assert task.review_number == "90"
        assert task.review_url == "https://github.com/org/repo/pull/90"
        assert task.state == IN_VALIDATION

        document = store.read(task.identifier)
        assert [record.target_state for record in document.pending_chain] == [
            TargetState.DONE,
            TargetState.MERGED,
        ]
        assert all(
            record.request_state == RequestState.PENDING
            for record in document.pending_chain
        )

        for target_state, expected_status in (
            (TargetState.DONE, IN_VALIDATION),
            (TargetState.MERGED, MERGED),
        ):
            record = next(
                item
                for item in store.read(task.identifier).pending_chain
                if item.target_state == target_state
            )
            outcome = asyncio.run(
                orch.terminal_transition_coordinator.apply_audit_result(
                    task,
                    AuditResult(
                        audit_id=record.audit_id,
                        target_state=record.target_state,
                        evidence_fingerprint=record.evidence_fingerprint,
                        verdict=Verdict.PASS,
                        message="Delivery and acceptance evidence verified.",
                        attempt_id=f"attempt-{target_state.value}",
                        auditor=ContributorIdentity("auditor", "test"),
                    ),
                    project.id,
                )
            )
            assert outcome.success is True
            assert outcome.applied_status == expected_status

        assert task.state == MERGED
        assert all(
            record.request_state == RequestState.COMPLETED
            for record in store.read(task.identifier).pending_chain
        )
        assert not _delivery_alerts(orch)
    finally:
        _close_orchestrator(orch)


def test_unsupported_repository_alerts_without_crashing(harness):
    orch, project, tracker, provider, detect, gate = harness
    project.repo_url = "ssh://example.invalid/org/repo"
    tracker.fetch_issues_by_states.return_value = [_issue("TASK-10")]
    detect.return_value = None

    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.create_review.assert_not_called()
    tracker.update_issue.assert_not_called()
    gate.assert_not_called()
    assert "no supported forge provider" in _delivery_alerts(orch)[0]["message"]


def test_epic_children_and_top_level_epics_are_excluded(harness):
    orch, _project, tracker, provider, _detect, _gate = harness
    tracker.fetch_issues_by_states.return_value = [
        _issue("TASK-CHILD", parent_id="EPIC-1"),
        _issue("EPIC-1", issue_type="epic"),
    ]

    orch._reconcile_standalone_ready_to_integrate_tasks()

    provider.get_branch_head_sha.assert_not_called()
    provider.create_review.assert_not_called()


def test_review_creation_failure_remains_visible_for_retry(harness):
    orch, _project, tracker, provider, _detect, _gate = harness
    tracker.fetch_issues_by_states.return_value = [_issue("TASK-11")]
    provider.create_review.side_effect = RuntimeError("forge unavailable")

    orch._reconcile_standalone_ready_to_integrate_tasks()

    tracker.update_issue.assert_not_called()
    assert "forge unavailable" in _delivery_alerts(orch)[0]["message"]
