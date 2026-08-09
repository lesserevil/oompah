"""REST and cache contracts for the canonical task decision projection."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.http_auth import HtpasswdCredentials, VerificationError
from oompah.integration_queue import IntegrationQueueStore
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.work_decision import (
    PermittedAction,
    UnmetPrerequisite,
    WorkDecision,
)
from oompah.work_decision_projection import project_work_decision
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_reasons import AlertSeverity


def _issue() -> Issue:
    return Issue(
        id="id-1",
        identifier="TASK-1",
        title="Task",
        state="Open",
        project_id="project-a",
    )


def _projection(
    *,
    reason: str = "dispatch.eligible",
    secret_observation: str | None = None,
) -> dict:
    return project_work_decision(
        WorkDecision(
            project_id="project-a",
            task_id="TASK-1",
            status="Open",
            disposition=TaskDisposition.RUNNABLE,
            reason_code=reason,
            responsible_owner=WorkflowOwner.DISPATCHER,
            unmet_prerequisites=(
                (
                    UnmetPrerequisite(
                        "operator.action_required",
                        "TASK-1",
                        secret_observation,
                    ),
                )
                if secret_observation
                else ()
            ),
            evidence_revision=f"evidence-{reason}",
            next_reassessment_at="2026-08-06T05:00:00+00:00",
            permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
            action_required=False,
            alert_level=AlertSeverity.NONE,
        )
    )


def _decision(*, reason: str = "dispatch.eligible") -> WorkDecision:
    return WorkDecision(
        project_id="project-a",
        task_id="TASK-1",
        status="Open",
        disposition=TaskDisposition.RUNNABLE,
        reason_code=reason,
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision=f"evidence-{reason}",
        next_reassessment_at="2026-08-06T05:00:00+00:00",
        permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
    )


class _StubOrchestrator:
    def __init__(self, issue: Issue, decision: dict):
        self.tracker = MagicMock()
        self.tracker.fetch_issue_detail.return_value = issue
        self._decision = decision

    def _tracker_for_project(self, project_id: str):
        assert project_id == "project-a"
        return self.tracker

    def work_decision_projection(self, project_id, task_id, task=None):
        assert (project_id, task_id) == ("project-a", "TASK-1")
        return self._decision


def _credentials() -> HtpasswdCredentials:
    credentials = HtpasswdCredentials(enabled=True)

    def verify(username: str, password: str) -> None:
        if (username, password) != ("operator", "correct horse"):
            raise VerificationError("Invalid credentials")

    credentials.verifier = verify
    credentials.htpasswd_path = "/test/.htpasswd"
    return credentials


def _basic(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def test_work_decision_endpoint_is_authenticated_and_matches_ui_projection(
    monkeypatch,
) -> None:
    issue = _issue()
    decision = _projection()
    orch = _StubOrchestrator(issue, decision)
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(server_module, "_http_credentials", _credentials())

    client = TestClient(server_module.app, raise_server_exceptions=False)
    path = "/api/v1/projects/project-a/tasks/TASK-1/work-decision"
    assert client.get(path).status_code == 401
    response = client.get(
        path,
        headers={"Authorization": _basic("operator", "correct horse")},
    )

    assert response.status_code == 200
    assert response.json() == {"work_decision": decision}
    assert server_module._work_decision_for_task(
        orch, issue.project_id, issue.identifier, issue
    ) == decision


def test_work_decision_endpoint_never_serializes_secret_evidence(monkeypatch) -> None:
    secret = "Authorization: Bearer endpoint-super-secret"
    decision = _projection(secret_observation=secret)
    orch = _StubOrchestrator(_issue(), decision)
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(server_module, "_http_credentials", None)

    client = TestClient(server_module.app, raise_server_exceptions=False)
    response = client.get(
        "/api/v1/projects/project-a/tasks/TASK-1/work-decision"
    )

    assert response.status_code == 200
    rendered = response.text
    assert "endpoint-super-secret" not in rendered
    assert "Authorization:" not in rendered
    assert "Bearer " not in rendered
    assert "[REDACTED]" in rendered


def test_work_decision_endpoint_explains_bounded_scan_omission(monkeypatch) -> None:
    class _IncompleteOrchestrator(_StubOrchestrator):
        def work_decision_availability(self, _project_id, _task_id=None):
            return "incomplete"

    orch = _IncompleteOrchestrator(_issue(), None)
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(server_module, "_http_credentials", None)

    response = TestClient(
        server_module.app, raise_server_exceptions=False
    ).get("/api/v1/projects/project-a/tasks/TASK-1/work-decision")

    assert response.status_code == 503
    assert response.json()["availability"] == "incomplete"
    assert "current bounded workflow pass is incomplete" in response.json()[
        "error"
    ]["message"]


def test_detail_cache_invalidates_when_only_decision_revision_changes() -> None:
    issue = _issue()
    first = _projection(reason="dispatch.eligible")
    second = _projection(reason="implementation.recovery_scheduled")
    orch = _StubOrchestrator(issue, first)
    key = "detail:project-a:TASK-1:actor:"
    cached = {
        "identifier": "TASK-1",
        "project_id": "project-a",
        "work_decision": first,
        "work_decision_availability": "available",
    }
    server_module._api_cache.clear()
    with server_module._detail_cache_lock:
        server_module._detail_cache_generations.clear()

    try:
        server_module._detail_cache_set(
            key,
            cached,
            project_id="project-a",
            generation=None,
        )
        assert server_module._detail_cache_get(key, orch, "project-a") == cached

        orch._decision = second
        assert server_module._detail_cache_get(key, orch, "project-a") is None
        assert server_module._api_cache.get(key) is None
    finally:
        server_module._api_cache.clear()
        with server_module._detail_cache_lock:
            server_module._detail_cache_generations.clear()


def test_detail_cache_invalidates_when_only_task_availability_changes() -> None:
    class _AvailabilityOrchestrator(_StubOrchestrator):
        def __init__(self):
            super().__init__(_issue(), None)
            self.availability = "pending"

        def work_decision_availability(self, _project_id, _task_id=None):
            return self.availability

    orch = _AvailabilityOrchestrator()
    key = "detail:project-a:TASK-1:actor:"
    cached = {
        "identifier": "TASK-1",
        "project_id": "project-a",
        "state": "Open",
        "work_decision": None,
        "work_decision_availability": "pending",
    }
    server_module._api_cache.clear()
    with server_module._detail_cache_lock:
        server_module._detail_cache_generations.clear()
    try:
        server_module._detail_cache_set(
            key,
            cached,
            project_id="project-a",
            generation=None,
        )
        assert server_module._detail_cache_get(key, orch, "project-a") == cached

        orch.availability = "incomplete"
        assert server_module._detail_cache_get(key, orch, "project-a") is None
        assert server_module._api_cache.get(key) is None
    finally:
        server_module._api_cache.clear()
        with server_module._detail_cache_lock:
            server_module._detail_cache_generations.clear()


def test_legacy_two_argument_projection_method_returns_its_value() -> None:
    decision = _projection()

    class _LegacyOrchestrator:
        def work_decision_projection(self, project_id, task_id):
            return decision

    assert server_module._work_decision_for_task(
        _LegacyOrchestrator(), "project-a", "TASK-1", _issue()
    ) == decision


def test_board_serialization_carries_queue_state_and_canonical_decision(
    tmp_path,
) -> None:
    issue = _issue()
    decision = _projection(reason="implementation.recovery_scheduled")
    orchestrator = _StubOrchestrator(issue, decision)
    orchestrator.project_store = MagicMock()
    orchestrator.project_store.list_all.return_value = []
    orchestrator.coordination_store = None
    orchestrator._unmerged_review_branches = set()
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite3"))
    orchestrator.integration_queue = queue
    try:
        queue.enqueue(
            project_id="project-a",
            epic_id="EPIC-1",
            task_id="TASK-1",
            task_branch="task-1",
            head_sha="a" * 40,
        )

        board = server_module._serialize_issues(orchestrator, [issue])
        row = board["Open"][0]

        assert row["integration_queue"]["state"] == "ready"
        assert row["work_decision"] == decision
        assert row["work_decision"]["reason_code"] == (
            "implementation.recovery_scheduled"
        )
    finally:
        queue.close()


def test_retained_omitted_row_is_suppressed_from_board_detail_and_api(
    tmp_path,
    monkeypatch,
) -> None:
    config = ServiceConfig(workspace_root=str(tmp_path / "workspace"))
    config.workflow_engine_mode = "enforce"
    orch = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    issue = _issue()
    stale = _decision(reason="dispatch.eligible")
    assert orch._cache_work_decisions(
        [stale],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orch._work_decision_publication_epoch,
    )
    assert orch._cache_work_decisions(
        [],
        2,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orch._work_decision_publication_epoch,
        scan_complete=False,
    )
    assert ("project-a", "TASK-1") in orch._work_decisions

    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = [issue]
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_comments.return_value = []
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = []
    orch._tracker_for_project = MagicMock(return_value=tracker)
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(server_module, "_get_tracker", lambda *_args: tracker)
    monkeypatch.setattr(server_module, "_http_credentials", None)
    server_module._api_cache.clear()
    with server_module._detail_cache_lock:
        server_module._detail_cache_generations.clear()

    board_row = server_module._serialize_issues(orch, [issue])["Open"][0]
    detail = TestClient(
        server_module.app, raise_server_exceptions=False
    ).get("/api/v1/issues/TASK-1/detail?project_id=project-a")
    decision = TestClient(
        server_module.app, raise_server_exceptions=False
    ).get("/api/v1/projects/project-a/tasks/TASK-1/work-decision")

    assert board_row["work_decision"] is None
    assert board_row["work_decision_availability"] == "incomplete"
    assert detail.status_code == 200
    assert detail.json()["work_decision"] is None
    assert detail.json()["work_decision_availability"] == "incomplete"
    assert decision.status_code == 503
    assert decision.json()["availability"] == "incomplete"
    server_module._api_cache.clear()
    with server_module._detail_cache_lock:
        server_module._detail_cache_generations.clear()


def test_newer_board_issue_missing_from_source_projection_is_unavailable(tmp_path) -> None:
    config = ServiceConfig(workspace_root=str(tmp_path / "workspace"))
    config.workflow_engine_mode = "enforce"
    orch = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    old = _decision(reason="dispatch.eligible")
    orch._cache_work_decisions(
        [old],
        1,
        source="controller",
        live_keys={("project-a", "TASK-1")},
        publication_epoch=orch._work_decision_publication_epoch,
    )
    newer = Issue(
        id="id-new",
        identifier="TASK-NEW",
        title="Newer than projection",
        state="Open",
        project_id="project-a",
    )

    row = server_module._serialize_issues(orch, [newer])["Open"][0]

    assert row["work_decision"] is None
    assert row["work_decision_availability"] == "unavailable"


def test_disabled_legacy_board_issue_is_normalized_and_fail_closed(tmp_path) -> None:
    config = ServiceConfig(workspace_root=str(tmp_path / "workspace"))
    config.workflow_engine_mode = "off"
    orch = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    legacy = Issue(
        id="legacy-id",
        identifier="TASK-LEGACY",
        title="Legacy",
        state="Open",
        project_id=None,
    )

    row = server_module._serialize_issues(orch, [legacy])["Open"][0]

    assert row["work_decision"] is None
    assert row["work_decision_availability"] == "disabled"


def test_legacy_null_project_id_matches_canonical_legacy_projection(tmp_path) -> None:
    config = ServiceConfig(workspace_root=str(tmp_path / "workspace"))
    config.workflow_engine_mode = "shadow"
    orch = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    legacy = Issue(
        id="legacy-id",
        identifier="TASK-LEGACY",
        title="Legacy",
        state="Open",
        project_id=None,
    )
    decision = WorkDecision(
        project_id="legacy",
        task_id="TASK-LEGACY",
        status="Open",
        disposition=TaskDisposition.RUNNABLE,
        reason_code="dispatch.eligible",
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision="legacy-evidence",
        next_reassessment_at="2026-08-06T05:00:00+00:00",
        permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
    )
    orch._cache_work_decisions(
        [decision],
        1,
        source="shadow",
        live_keys={("legacy", "TASK-LEGACY")},
        publication_epoch=orch._work_decision_publication_epoch,
    )

    row = server_module._serialize_issues(orch, [legacy])["Open"][0]

    assert row["work_decision"]["task_id"] == "TASK-LEGACY"
    assert row["work_decision_availability"] == "available"


def test_done_cached_decision_matches_snapshot_and_public_api(
    tmp_path,
    monkeypatch,
) -> None:
    config = ServiceConfig(workspace_root=str(tmp_path / "workspace"))
    config.workflow_engine_mode = "enforce"
    orch = Orchestrator(
        config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    done = Issue(
        id="done-id",
        identifier="TASK-DONE",
        title="Done awaiting landing",
        state="Done",
        project_id="project-a",
    )
    decision = WorkDecision(
        project_id="project-a",
        task_id="TASK-DONE",
        status="Done",
        disposition=TaskDisposition.BLOCKED,
        reason_code="landing.waiting",
        responsible_owner=WorkflowOwner.ROLLUP,
        unmet_prerequisites=(
            UnmetPrerequisite("landing.not_landed", "task-branch->epic-parent"),
        ),
        evidence_revision="done-evidence",
        next_reassessment_at="2026-08-06T05:00:00+00:00",
        permitted_actions=(PermittedAction.REFRESH_LANDING,),
        action_required=False,
        alert_level=AlertSeverity.NONE,
    )
    orch._cache_work_decisions(
        [decision],
        1,
        source="controller",
        live_keys={("project-a", "TASK-DONE")},
        publication_epoch=orch._work_decision_publication_epoch,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = done
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(server_module, "_get_tracker", lambda *_args: tracker)
    monkeypatch.setattr(server_module, "_http_credentials", None)

    expected = orch.work_decision_projection("project-a", "TASK-DONE")
    snapshot = orch.get_snapshot()["work_decision_projection"]
    response = TestClient(
        server_module.app, raise_server_exceptions=False
    ).get("/api/v1/projects/project-a/tasks/TASK-DONE/work-decision")

    assert response.status_code == 200
    assert response.json() == {"work_decision": expected}
    assert snapshot["items"] == [expected]
    assert snapshot["availability"] == "ready"


def test_cold_restart_reports_failed_project_unavailable_through_api(
    tmp_path,
    monkeypatch,
) -> None:
    state_path = str(tmp_path / "service_state.json")
    first_config = ServiceConfig(workspace_root=str(tmp_path / "workspace-first"))
    first_config.workflow_engine_mode = "enforce"
    first = Orchestrator(
        first_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    first._cache_work_decisions(
        [],
        1,
        source="controller",
        live_keys=set(),
        failed_projects={"project-a"},
        publication_epoch=first._work_decision_publication_epoch,
    )

    restarted_config = ServiceConfig(
        workspace_root=str(tmp_path / "workspace-restarted")
    )
    restarted_config.workflow_engine_mode = "enforce"
    restarted = Orchestrator(
        restarted_config,
        str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    issue = Issue(
        id="id-1",
        identifier="TASK-1",
        title="Task",
        state="Open",
        project_id="project-a",
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: restarted)
    monkeypatch.setattr(server_module, "_get_tracker", lambda *_args: tracker)
    monkeypatch.setattr(server_module, "_http_credentials", None)

    response = TestClient(
        server_module.app, raise_server_exceptions=False
    ).get("/api/v1/projects/project-a/tasks/TASK-1/work-decision")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "decision_unavailable"
    assert response.json()["availability"] == "unavailable"
