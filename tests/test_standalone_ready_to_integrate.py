"""Standalone Ready-to-Integrate delivery reconciliation coverage."""

from __future__ import annotations

import asyncio
import copy
import threading
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.providers import ProviderStore
from oompah.scm import ReviewRequest, SCMProvider
from oompah.statuses import IN_REVIEW, IN_VALIDATION, MERGED, READY_TO_INTEGRATE
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    Verdict,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadataStore
from oompah.terminal_transition_coordinator import AuditResult


def _issue(
    identifier: str,
    *,
    branch: str | None = None,
    parent_id: str | None = None,
    issue_type: str = "task",
) -> Issue:
    return Issue(
        id=f"id-{identifier}",
        identifier=identifier,
        title=f"Title for {identifier}",
        description=f"Description for {identifier}",
        state=READY_TO_INTEGRATE,
        parent_id=parent_id,
        issue_type=issue_type,
        work_branch=branch or identifier,
    )


def _review(
    identifier: str,
    *,
    state: str = "open",
    review_id: str = "42",
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"{identifier}: review",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="oompah",
        state=state,
        source_branch=identifier,
        target_branch="trunk",
        created_at="2026-07-30T00:00:00+00:00",
        updated_at="2026-07-30T00:00:00+00:00",
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
    provider.find_pr_for_branch.side_effect = [None, created]
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
    assert not _delivery_alerts(orch)


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
    provider.find_pr_for_branch.side_effect = [None, created]
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
        orch._reconcile_standalone_ready_to_integrate_tasks()

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
