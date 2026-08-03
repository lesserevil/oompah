"""Regression coverage for direct-owner watchdog protection (OOMPAH-707)."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.models import Issue, Project, WorkflowDefinition
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectStore
from oompah.server import app


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
    orch._project_trackers[project.id] = tracker
    orch._fetch_all_in_progress_issues = MagicMock(return_value=[])
    return orch, tracker, _issue()


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
        }
    ]


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
    tracker.update_issue.assert_not_called()


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
