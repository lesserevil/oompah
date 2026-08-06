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
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.models import Issue, Project, RunningEntry, WorkflowDefinition
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore, RecoveryPublicationError
from oompah.server import app
from oompah.validation_resource_lease import (
    ValidationLeaseOwner,
    ValidationResourceLease,
)


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
        loop = asyncio.get_running_loop()

        def register_runtime():
            orch.state.claimed.discard(issue.id)
            orch.state.running[issue.id] = running

        loop.call_later(0.01, register_runtime)
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
