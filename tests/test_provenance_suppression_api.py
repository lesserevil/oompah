"""Owner API contracts for terminal provenance suppression (OOMPAH-871)."""

from __future__ import annotations

import base64
import contextlib
import copy
from typing import Generator
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.http_auth import HtpasswdCredentials, VerificationError
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectStore
from oompah.provenance_suppression import PROVENANCE_SUPPRESSION_KEY
from oompah.provenance_suppression import (
    ProvenanceControlBusyError,
    ProvenanceGuardedTracker,
)
from oompah.server import app
from oompah.terminal_audit_metadata import METADATA_KEY


def _basic(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


@contextlib.contextmanager
def _server_auth() -> Generator[None, None, None]:
    credentials = HtpasswdCredentials(enabled=True)

    def verifier(username: str, password: str) -> None:
        if {"alice": "alicepw", "mallory": "mallorypw"}.get(username) == password:
            return
        raise VerificationError("Invalid credentials")

    credentials.verifier = verifier
    prior_credentials = server_module._http_credentials
    prior_map = server_module._actor_map
    server_module._http_credentials = credentials
    server_module._actor_map = None
    try:
        yield
    finally:
        server_module._http_credentials = prior_credentials
        server_module._actor_map = prior_map


class _Tracker:
    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.metadata: dict[str, object] = {}
        self.update_calls: list[tuple[str, dict[str, object]]] = []

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issue if identifier == self.issue.identifier else None

    def get_metadata(self, _identifier: str) -> dict[str, object]:
        return copy.deepcopy(self.metadata)

    def set_metadata_field(self, _identifier: str, key: str, value: object) -> None:
        self.metadata[key] = copy.deepcopy(value)

    def update_issue(self, identifier: str, **fields: object) -> None:
        assert identifier == self.issue.identifier
        self.update_calls.append((identifier, dict(fields)))
        if "status" in fields:
            self.issue.state = str(fields["status"])


def _orchestrator(tmp_path, state: str = "Merged") -> tuple[Orchestrator, _Tracker, Issue]:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(
        id="proj-1",
        name="example",
        repo_url="https://github.com/owner/repo.git",
        repo_path=str(tmp_path / "repo"),
        branch="main",
        status_actor_login="alice",
    )
    store._projects[project.id] = project
    issue = Issue(
        id="owner/repo#1",
        identifier="owner/repo#1",
        title="Terminal task",
        description="Complete task description.",
        state=state,
        project_id=project.id,
    )
    tracker = _Tracker(issue)
    orch = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._project_trackers[project.id] = ProvenanceGuardedTracker(
        tracker,
        store,
        project.id,
    )  # type: ignore[assignment]
    return orch, tracker, issue


def _endpoint(action: str) -> str:
    return f"/api/v1/projects/proj-1/tasks/1/terminal-provenance/{action}"


def _request(client: TestClient, action: str, **body: object):
    payload = {"issue_key": "owner/repo#1", "reason": "owner decision", **body}
    return client.post(
        _endpoint(action),
        json=payload,
        headers={"Authorization": _basic("alice", "alicepw")},
    )


def test_authenticated_owner_retains_terminal_task_as_provenance_only(tmp_path):
    orch, tracker, _issue = _orchestrator(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        response = _request(client, "retain")

    assert response.status_code == 200, response.text
    assert response.json()["suppressed"] is True
    assert response.json()["owner_login"] == "alice"
    marker = tracker.metadata[METADATA_KEY][PROVENANCE_SUPPRESSION_KEY]  # type: ignore[index]
    assert marker["actor"]["identity"] == "alice"  # type: ignore[index]
    assert tracker.update_calls == []


def test_provenance_control_busy_is_structured_and_never_mutates(tmp_path):
    orch, tracker, _issue = _orchestrator(tmp_path)
    guarded = orch._project_trackers["proj-1"]
    assert isinstance(guarded, ProvenanceGuardedTracker)
    broadcast = AsyncMock()

    @contextlib.contextmanager
    def busy_control_lock():
        raise ProvenanceControlBusyError("project authority busy")
        yield  # pragma: no cover - contextmanager shape only

    guarded.owner_control_lock = busy_control_lock  # type: ignore[method-assign]
    client = TestClient(app, raise_server_exceptions=False)
    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=broadcast),
    ):
        response = _request(client, "retain")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "control_busy",
        "message": response.json()["error"]["message"],
        "retryable": True,
    }
    assert tracker.metadata == {}
    assert tracker.update_calls == []
    broadcast.assert_not_awaited()


def test_retain_task_authority_busy_is_structured_and_never_mutates(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    orch.config.terminal_control_lock_timeout_seconds = 0.05
    broadcast = AsyncMock()
    client = TestClient(app, raise_server_exceptions=False)

    with (
        orch.issue_transition_lock(issue.id).sync(),
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=broadcast),
    ):
        response = _request(client, "retain")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "control_busy",
        "message": response.json()["error"]["message"],
        "retryable": True,
        "issue_id": issue.id,
        "timeout_seconds": 0.2,
    }
    assert "retry the exact request" in response.json()["error"]["message"]
    assert tracker.metadata == {}
    assert tracker.update_calls == []
    broadcast.assert_not_awaited()


def test_new_revision_control_busy_preserves_retained_marker_and_status(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    guarded = orch._project_trackers["proj-1"]
    client = TestClient(app, raise_server_exceptions=False)
    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        retained = _request(client, "retain")
    assert retained.status_code == 200
    retained_metadata = copy.deepcopy(tracker.metadata)
    tracker.update_calls.clear()
    broadcast = AsyncMock()

    @contextlib.contextmanager
    def busy_control_lock():
        raise ProvenanceControlBusyError("project authority busy")
        yield  # pragma: no cover - contextmanager shape only

    guarded.owner_control_lock = busy_control_lock  # type: ignore[method-assign]
    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=broadcast),
    ):
        response = _request(client, "new-revision")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "control_busy"
    assert response.json()["error"]["retryable"] is True
    assert tracker.metadata == retained_metadata
    assert tracker.update_calls == []
    assert issue.state == "Merged"
    broadcast.assert_not_awaited()


def test_new_revision_task_authority_busy_preserves_marker_and_status(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    orch.config.terminal_control_lock_timeout_seconds = 0.05
    client = TestClient(app, raise_server_exceptions=False)
    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        retained = _request(client, "retain")
    assert retained.status_code == 200
    retained_metadata = copy.deepcopy(tracker.metadata)
    tracker.update_calls.clear()
    broadcast = AsyncMock()

    with (
        orch.issue_transition_lock(issue.id).sync(),
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=broadcast),
    ):
        response = _request(client, "new-revision")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "control_busy",
        "message": response.json()["error"]["message"],
        "retryable": True,
        "issue_id": issue.id,
        "timeout_seconds": 0.2,
    }
    assert "retry the exact request" in response.json()["error"]["message"]
    assert tracker.metadata == retained_metadata
    assert tracker.update_calls == []
    assert issue.state == "Merged"
    broadcast.assert_not_awaited()


def test_terminal_provenance_rejects_nonowner_actor_mismatch_and_missing_reason(tmp_path):
    orch, tracker, _issue = _orchestrator(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
    ):
        nonowner = client.post(
            _endpoint("retain"),
            json={"issue_key": "owner/repo#1", "reason": "no authority"},
            headers={"Authorization": _basic("mallory", "mallorypw")},
        )
        mismatch = client.post(
            _endpoint("retain"),
            json={
                "issue_key": "owner/repo#1",
                "reason": "spoof attempt",
                "actor_login": "mallory",
            },
            headers={"Authorization": _basic("alice", "alicepw")},
        )
        missing_reason = client.post(
            _endpoint("retain"),
            json={"issue_key": "owner/repo#1"},
            headers={"Authorization": _basic("alice", "alicepw")},
        )

    assert nonowner.status_code == 403
    assert nonowner.json()["error"]["code"] == "owner_required"
    assert mismatch.status_code == 403
    assert mismatch.json()["error"]["code"] == "actor_mismatch"
    assert missing_reason.status_code == 400
    assert tracker.metadata == {}


def test_terminal_provenance_rejects_unknown_and_nonterminal_tasks(tmp_path):
    orch, tracker, _issue = _orchestrator(tmp_path, state="Open")
    client = TestClient(app, raise_server_exceptions=False)

    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
    ):
        nonterminal = _request(client, "retain")
        unknown = client.post(
            _endpoint("retain"),
            json={"issue_key": "owner/repo#404", "reason": "not present"},
            headers={"Authorization": _basic("alice", "alicepw")},
        )

    assert nonterminal.status_code == 409
    assert nonterminal.json()["error"]["code"] == "invalid_state"
    assert unknown.status_code == 404
    assert tracker.metadata == {}


def test_retain_refetches_terminal_state_under_transition_lock(tmp_path):
    orch, tracker, issue = _orchestrator(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    original_fetch = tracker.fetch_issue_detail
    fetch_count = 0

    def _fetch(identifier: str) -> Issue | None:
        nonlocal fetch_count
        fetch_count += 1
        current = original_fetch(identifier)
        if fetch_count >= 2 and current is not None:
            current.state = "Open"
        return current

    tracker.fetch_issue_detail = _fetch  # type: ignore[method-assign]
    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
    ):
        response = _request(client, "retain")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    assert issue.state == "Open"
    assert tracker.metadata == {}


def test_new_revision_opens_raw_tracker_before_clearing_suppression_and_retries(tmp_path):
    orch, raw_tracker, issue = _orchestrator(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        retained = _request(client, "retain")
        assert retained.status_code == 200, retained.text
        guarded = orch._project_trackers["proj-1"]
        assert isinstance(guarded, ProvenanceGuardedTracker)
        assert not hasattr(guarded, "wrapped_tracker")

        with patch(
            "oompah.provenance_suppression.authorize_new_revision",
            side_effect=RuntimeError("metadata write interrupted"),
        ):
            partial = _request(client, "new-revision")
        marker_after_partial = copy.deepcopy(
            raw_tracker.metadata[METADATA_KEY][PROVENANCE_SUPPRESSION_KEY]  # type: ignore[index]
        )
        completed = _request(client, "new-revision")

    assert partial.status_code == 503
    assert "metadata write interrupted" not in partial.text
    assert issue.state == "Open"
    assert marker_after_partial["suppressed"] is True  # type: ignore[index]
    assert completed.status_code == 200, completed.text
    assert completed.json()["suppressed"] is False
    assert completed.json()["authority_generation"] == 1
    assert raw_tracker.update_calls == [("owner/repo#1", {"status": "Open"})]


def test_retain_never_exposes_malformed_nested_actor_payload(tmp_path, caplog):
    orch, raw_tracker, _issue = _orchestrator(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    with (
        _server_auth(),
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        retained = _request(client, "retain")
        assert retained.status_code == 200, retained.text
        marker = raw_tracker.metadata[METADATA_KEY][PROVENANCE_SUPPRESSION_KEY]  # type: ignore[index]
        marker["actor"]["version"] = "secret-value-must-not-escape"  # type: ignore[index]

        caplog.clear()
        response = _request(client, "retain")

    assert response.status_code == 409
    assert "secret-value-must-not-escape" not in response.text
    assert "secret-value-must-not-escape" not in caplog.text
