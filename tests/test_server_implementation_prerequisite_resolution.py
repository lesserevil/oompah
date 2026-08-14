"""Owner API contract for exact implementation-prerequisite resolution."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from types import SimpleNamespace
import threading
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

import oompah.server as server_module
from oompah.implementation_prerequisite import (
    ImplementationPrerequisiteDeclaration,
    PrerequisiteContinuation,
    PrerequisiteKind,
    RecoveryTrigger,
    RecoveryTriggerKind,
    freeze_execution_profile_snapshot,
    new_record,
    new_resolution,
)
from oompah.models import AgentProfile, Issue
from oompah.server import AuthenticatedPrincipal, app
from oompah.task_transition_service import issue_authority_version


_HEAD = "b" * 40
_PROFILE_REVISION = "c" * 64


class _Tracker:
    def __init__(self, issue: Issue) -> None:
        self.issue = issue

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issue if identifier == self.issue.identifier else None

    @contextlib.contextmanager
    def owner_control_lock(self):
        yield


def _record(issue: Issue, trigger: RecoveryTrigger):
    kind = {
        RecoveryTriggerKind.TASK: PrerequisiteKind.DEPENDENCY,
        RecoveryTriggerKind.PROFILE_CAPABILITY: PrerequisiteKind.HARDWARE,
        RecoveryTriggerKind.OPERATOR: PrerequisiteKind.CREDENTIALS,
    }[trigger.kind]
    record = new_record(
        ImplementationPrerequisiteDeclaration(kind, "external-blocker", trigger),
        project_id="proj-1",
        task_id=issue.id,
        task_identifier=issue.identifier,
        source_run_id="run-1",
        source_assignment_id="assignment-1",
        source_generation="source-generation-1",
        source_focus="default",
        source_task_authority="a" * 64,
        source_head_sha=_HEAD,
        source_profile_revision=_PROFILE_REVISION,
        now=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    issue.implementation_prerequisite = record.to_dict()
    return record


def _issue(trigger: RecoveryTrigger) -> tuple[Issue, object]:
    issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Blocked implementation",
        description="Continue after one exact external prerequisite.",
        state="Needs Human",
        project_id="proj-1",
    )
    return issue, _record(issue, trigger)


def _body(issue: Issue, record, **overrides: str) -> dict[str, str]:
    return {
        "issue_key": issue.identifier,
        "record_id": record.record_id,
        "source_run_id": record.source_run_id,
        "source_assignment_id": record.source_assignment_id,
        "source_generation": record.source_generation,
        "task_authority": issue_authority_version(issue),
        "reason": "The named prerequisite is now satisfied.",
        **overrides,
    }


def _setup(monkeypatch, issue: Issue, *, profiles=(), active_jobs=()):
    tracker = _Tracker(issue)
    project = SimpleNamespace(
        id="proj-1",
        repo_url="https://github.com/owner/repo.git",
        access_token=None,
        status_actor_login="owner",
        tracker_owner=None,
        status_label_authorized_logins=[],
        default_branch="main",
    )
    project_store = MagicMock()
    project_store.get.side_effect = lambda project_id: (
        project if project_id == "proj-1" else None
    )
    project_store.project_write_lock.side_effect = lambda _project_id: contextlib.nullcontext()
    store = MagicMock()
    store.list_jobs.return_value = tuple(active_jobs)
    controller = SimpleNamespace(store=store)
    runtime = SimpleNamespace(
        project_bindings={
            "proj-1": SimpleNamespace(implementation_controller=controller)
        }
    )
    scheduled_job = SimpleNamespace(job_id="job-1", generation="workflow-generation-1")
    schedule = MagicMock(return_value=scheduled_job)
    lock = threading.Lock()
    snapshot = freeze_execution_profile_snapshot(profiles)
    orch = SimpleNamespace(
        project_store=project_store,
        workflow_runtime=runtime,
        _tracker_for_project=lambda project_id: tracker
        if project_id == "proj-1"
        else (_ for _ in ()).throw(KeyError(project_id)),
        _implementation_prerequisite_lock=lambda _project, _identifier: lock,
        _latest_execution_profile_authority=lambda: (snapshot, tuple(profiles)),
        _schedule_implementation_workflow_event=schedule,
        request_refresh=MagicMock(),
    )
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(
        server_module,
        "_authenticated_principal",
        lambda _request: AuthenticatedPrincipal("owner", "owner", "basic"),
    )
    monkeypatch.setattr(server_module, "is_project_owner", lambda *_args: True)
    return orch, tracker, schedule, store


def _post(body: dict[str, str]):
    return TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/projects/proj-1/tasks/TASK-1/implementation-prerequisite/resolve",
        json=body,
    )


def test_profile_capability_owner_resolution_schedules_exact_payload(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.PROFILE_CAPABILITY, "macos")
    issue, record = _issue(trigger)
    profile = AgentProfile(
        name="Mac Runner",
        command="codex",
        execution_capabilities=["macos"],
    )
    _orch, _tracker, schedule, _store = _setup(
        monkeypatch, issue, profiles=(profile,)
    )
    body = _body(issue, record)

    response = _post(body)

    assert response.status_code == 202, response.text
    assert response.json() == {
        "ok": True,
        "resolved": False,
        "replayed": False,
        "job_id": "job-1",
        "generation": "workflow-generation-1",
        "resume_status": "Open",
        "continuation": {
            "resume_status": "Open",
            "work_branch": None,
            "head_sha": _HEAD,
            "review_id": None,
            "review_head_sha": None,
            "target_branch": None,
            "pipeline_id": None,
            "pipeline_head_sha": None,
        },
    }
    kwargs = schedule.call_args.kwargs
    assert kwargs["expected_evidence_revision"] == body["task_authority"]
    assert kwargs["expected_head_sha"] == _HEAD
    assert kwargs["payload"] == {
        "record_id": record.record_id,
        "source_run_id": "run-1",
        "source_assignment_id": "assignment-1",
        "source_generation": "source-generation-1",
        "expected_task_authority": body["task_authority"],
        "actor": "owner",
        "reason": body["reason"],
        "trigger_evidence": {
            "kind": "profile-capability",
            "capability": "macos",
            "profile_name": "Mac Runner",
            "profile_revision": freeze_execution_profile_snapshot((profile,)).revision,
        },
        "continuation": response.json()["continuation"],
        "expected_status": "Needs Human",
    }


def test_owner_auth_and_exact_cas_fail_before_scheduling(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "rotate-credential")
    issue, record = _issue(trigger)
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)
    monkeypatch.setattr(server_module, "_authenticated_principal", lambda _request: None)

    unauthenticated = _post(
        _body(issue, record, operator_action="rotate-credential")
    )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "authentication"
    schedule.assert_not_called()

    monkeypatch.setattr(
        server_module,
        "_authenticated_principal",
        lambda _request: AuthenticatedPrincipal("owner", "owner", "basic"),
    )
    monkeypatch.setattr(server_module, "is_project_owner", lambda *_args: False)
    forbidden = _post(
        _body(issue, record, operator_action="rotate-credential")
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "owner_required"
    schedule.assert_not_called()

    monkeypatch.setattr(server_module, "is_project_owner", lambda *_args: True)
    stale = _body(issue, record, operator_action="rotate-credential")
    stale["source_run_id"] = "replacement-run"
    response = _post(stale)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_prerequisite"
    schedule.assert_not_called()


def test_malformed_request_is_rejected_before_task_or_workflow_lookup(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    orch, _tracker, schedule, _store = _setup(monkeypatch, issue)
    body = _body(issue, record, operator_action="runner-online")
    body["unexpected_status"] = "Open"

    response = _post(body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation"
    orch.project_store.get.assert_not_called()
    schedule.assert_not_called()


def test_operator_trigger_requires_exact_named_action(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "rotate-credential")
    issue, record = _issue(trigger)
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)

    response = _post(_body(issue, record, operator_action="different-action"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "operator_action_mismatch"
    schedule.assert_not_called()


def test_task_trigger_is_project_qualified_and_must_be_terminal(monkeypatch):
    trigger = RecoveryTrigger(
        RecoveryTriggerKind.TASK, "DEP-7", project_id="dependency-project"
    )
    issue, record = _issue(trigger)
    orch, _tracker, schedule, _store = _setup(monkeypatch, issue)
    dependency = Issue(
        id="DEP-7",
        identifier="DEP-7",
        title="Provision runner",
        description="Provision the required runner.",
        state="Open",
        project_id="dependency-project",
    )
    dependency_tracker = _Tracker(dependency)
    orch.project_store.get.side_effect = lambda project_id: SimpleNamespace(id=project_id)
    orch._tracker_for_project = lambda project_id: (
        dependency_tracker if project_id == "dependency-project" else _tracker
    )

    blocked = _post(_body(issue, record))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "trigger_task_not_terminal"
    schedule.assert_not_called()

    dependency.state = "Done"
    resolved = _post(_body(issue, record))
    assert resolved.status_code == 202, resolved.text
    assert schedule.call_args.kwargs["payload"]["trigger_evidence"] == {
        "kind": "task",
        "project_id": "dependency-project",
        "task_identifier": "DEP-7",
        "status": "Done",
        "task_authority": issue_authority_version(dependency),
    }


def test_equal_live_event_replays_and_conflicting_event_is_rejected(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "rotate-credential")
    issue, record = _issue(trigger)
    body = _body(issue, record, operator_action="rotate-credential")
    payload = {
        "record_id": record.record_id,
        "source_run_id": record.source_run_id,
        "source_assignment_id": record.source_assignment_id,
        "source_generation": record.source_generation,
        "expected_task_authority": body["task_authority"],
        "actor": "owner",
        "reason": body["reason"],
        "trigger_evidence": {"kind": "operator", "action": "rotate-credential"},
        "continuation": {
            "resume_status": "Open",
            "work_branch": None,
            "head_sha": _HEAD,
            "review_id": None,
            "review_head_sha": None,
            "target_branch": None,
            "pipeline_id": None,
            "pipeline_head_sha": None,
        },
        "expected_status": "Needs Human",
    }
    live = SimpleNamespace(
        action="prerequisite_resolution",
        payload=payload,
        expected_evidence_revision=body["task_authority"],
        expected_head_sha=_HEAD,
        job_id="live-job",
        generation="live-generation",
    )
    _orch, _tracker, schedule, store = _setup(
        monkeypatch, issue, active_jobs=(live,)
    )

    replay = _post(body)

    assert replay.status_code == 202, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["job_id"] == "live-job"
    schedule.assert_not_called()

    live.payload = {**payload, "reason": "conflicting reason"}
    conflict = _post(body)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "resolution_in_progress_conflict"
    assert store.list_jobs.call_count == 2


def test_review_continuation_and_pipeline_are_bound_to_live_exact_head(
    monkeypatch,
):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.work_branch = "TASK-1"
    issue.head_sha = _HEAD
    issue.review_number = "20"
    issue.review_head = _HEAD
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)
    provider = MagicMock()
    provider.get_review.return_value = SimpleNamespace(
        id="20",
        state="open",
        head_sha=_HEAD,
        source_branch="TASK-1",
        target_branch="main",
        pipeline_id="62564237",
        pipeline_head_sha=_HEAD,
    )
    monkeypatch.setattr(server_module, "detect_provider", lambda *_args, **_kwargs: provider)

    response = _post(
        _body(
            issue,
            record,
            operator_action="runner-online",
            pipeline_id="62564237",
        )
    )

    assert response.status_code == 202, response.text
    continuation = response.json()["continuation"]
    assert continuation["resume_status"] == "In Review"
    assert continuation["review_id"] == "20"
    assert continuation["review_head_sha"] == _HEAD
    assert continuation["target_branch"] == "main"
    assert continuation["pipeline_id"] == "62564237"
    assert continuation["pipeline_head_sha"] == _HEAD
    assert schedule.call_args.kwargs["expected_head_sha"] == _HEAD


def test_stale_pipeline_identity_is_rejected_before_scheduling(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.work_branch = "TASK-1"
    issue.head_sha = _HEAD
    issue.review_number = "20"
    issue.review_head = _HEAD
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)
    provider = MagicMock()
    provider.get_review.return_value = SimpleNamespace(
        id="20",
        state="open",
        head_sha=_HEAD,
        source_branch="TASK-1",
        target_branch="main",
        pipeline_id="replacement-pipeline",
        pipeline_head_sha=_HEAD,
    )
    monkeypatch.setattr(server_module, "detect_provider", lambda *_args, **_kwargs: provider)

    response = _post(
        _body(
            issue,
            record,
            operator_action="runner-online",
            pipeline_id="62564237",
        )
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_pipeline_evidence"
    schedule.assert_not_called()


def test_retargeted_review_is_rejected_before_scheduling(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.work_branch = "TASK-1"
    issue.target_branch = "main"
    issue.head_sha = _HEAD
    issue.review_number = "20"
    issue.review_head = _HEAD
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)
    provider = MagicMock()
    provider.get_review.return_value = SimpleNamespace(
        id="20",
        state="open",
        head_sha=_HEAD,
        source_branch="TASK-1",
        target_branch="release",
        pipeline_id=None,
        pipeline_head_sha=None,
    )
    monkeypatch.setattr(
        server_module,
        "detect_provider",
        lambda *_args, **_kwargs: provider,
    )

    response = _post(
        _body(issue, record, operator_action="runner-online")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_review_evidence"
    schedule.assert_not_called()


@pytest.mark.parametrize(
    "status",
    ["In Validation", "Done", "Merged", "Archived"],
)
def test_resolution_cannot_reopen_audit_or_terminal_status(
    monkeypatch,
    status,
):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.state = status
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)

    response = _post(
        _body(issue, record, operator_action="runner-online")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == (
        "resolution_source_status_rejected"
    )
    schedule.assert_not_called()


def test_cross_scope_durable_record_is_rejected(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    cross_scope = new_record(
        ImplementationPrerequisiteDeclaration(
            PrerequisiteKind.CREDENTIALS,
            "external-blocker",
            trigger,
        ),
        project_id="other-project",
        task_id=issue.id,
        task_identifier=issue.identifier,
        source_run_id=record.source_run_id,
        source_assignment_id=record.source_assignment_id,
        source_generation=record.source_generation,
        source_focus="default",
        source_task_authority="a" * 64,
        source_head_sha=_HEAD,
        source_profile_revision=_PROFILE_REVISION,
        now=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    issue.implementation_prerequisite = cross_scope.to_dict()
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)

    response = _post(_body(issue, cross_scope, operator_action="runner-online"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "prerequisite_scope_mismatch"
    schedule.assert_not_called()


def test_committed_resolution_replays_before_changed_task_authority(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    body = _body(issue, record, operator_action="runner-online")
    resolution = new_resolution(
        record,
        expected_task_authority=body["task_authority"],
        workflow_generation="committed-generation",
        actor="owner",
        reason=body["reason"],
        trigger_evidence={"kind": "operator", "action": "runner-online"},
        continuation=PrerequisiteContinuation(resume_status="Open"),
        now=datetime(2026, 8, 14, 1, tzinfo=timezone.utc),
    )
    issue.implementation_prerequisite_resolution = resolution.to_dict()
    issue.state = "Done"
    historical = SimpleNamespace(job_id="historical-job")
    _orch, _tracker, schedule, store = _setup(monkeypatch, issue)
    store.list_jobs.return_value = (historical,)

    response = _post(body)

    assert response.status_code == 200, response.text
    assert response.json()["resolved"] is True
    assert response.json()["replayed"] is True
    assert response.json()["job_id"] == "historical-job"
    assert response.json()["generation"] == "committed-generation"
    schedule.assert_not_called()


def test_accepted_submission_resumes_ready_to_integrate(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.integration = SimpleNamespace(
        state="ready", task_branch="TASK-1", head_sha=_HEAD
    )
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)

    response = _post(_body(issue, record, operator_action="runner-online"))

    assert response.status_code == 202, response.text
    assert response.json()["continuation"]["resume_status"] == "Ready to Integrate"
    assert response.json()["continuation"]["work_branch"] == "TASK-1"
    assert response.json()["continuation"]["head_sha"] == _HEAD
    assert schedule.call_args.kwargs["expected_head_sha"] == _HEAD


@pytest.mark.parametrize(
    ("status", "integration_state", "resume_status"),
    [
        ("Needs CI Fix", "blocked", "Needs CI Fix"),
        ("Needs Human", "needs_human", "Needs Human"),
    ],
)
def test_submission_state_outranks_stale_live_review(
    monkeypatch,
    status,
    integration_state,
    resume_status,
):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.state = status
    issue.work_branch = "TASK-1"
    issue.target_branch = "main"
    issue.head_sha = _HEAD
    issue.review_number = "20"
    issue.review_head = _HEAD
    issue.integration = SimpleNamespace(
        state=integration_state,
        task_branch="TASK-1",
        head_sha=_HEAD,
    )
    _orch, _tracker, _schedule, _store = _setup(monkeypatch, issue)
    detect = MagicMock()
    monkeypatch.setattr(server_module, "detect_provider", detect)

    response = _post(
        _body(issue, record, operator_action="runner-online")
    )

    assert response.status_code == 202, response.text
    continuation = response.json()["continuation"]
    assert continuation["resume_status"] == resume_status
    assert continuation["review_id"] is None
    assert continuation["target_branch"] is None
    detect.assert_not_called()


@pytest.mark.parametrize("status", ["Needs CI Fix", "Needs Rebase"])
def test_blocked_submission_preserves_its_exact_repair_status(
    monkeypatch,
    status,
):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.state = status
    issue.integration = SimpleNamespace(
        state="blocked",
        task_branch="TASK-1",
        head_sha=_HEAD,
    )
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)

    response = _post(
        _body(issue, record, operator_action="runner-online")
    )

    assert response.status_code == 202, response.text
    continuation = response.json()["continuation"]
    assert continuation["resume_status"] == status
    assert continuation["work_branch"] == "TASK-1"
    assert continuation["head_sha"] == _HEAD
    assert schedule.call_args.kwargs["payload"]["expected_status"] == status


def test_needs_human_submission_preserves_needs_human(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.integration = SimpleNamespace(
        state="needs_human",
        task_branch="TASK-1",
        head_sha=_HEAD,
    )
    _orch, _tracker, _schedule, _store = _setup(monkeypatch, issue)

    response = _post(
        _body(issue, record, operator_action="runner-online")
    )

    assert response.status_code == 202, response.text
    assert response.json()["continuation"]["resume_status"] == "Needs Human"


def test_integrated_submission_cannot_be_reopened(monkeypatch):
    trigger = RecoveryTrigger(RecoveryTriggerKind.OPERATOR, "runner-online")
    issue, record = _issue(trigger)
    issue.integration = SimpleNamespace(
        state="integrated",
        task_branch="TASK-1",
        head_sha=_HEAD,
    )
    _orch, _tracker, schedule, _store = _setup(monkeypatch, issue)

    response = _post(
        _body(issue, record, operator_action="runner-online")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "integration_already_integrated"
    schedule.assert_not_called()
