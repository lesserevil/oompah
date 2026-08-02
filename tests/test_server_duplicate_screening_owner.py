"""Authorization and request-contract tests for owner duplicate recovery."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.duplicate_screening import (
    inconclusive_record,
    new_claim_record,
)
from oompah.models import Issue
from oompah.server import AuthenticatedPrincipal, app


def _issue() -> Issue:
    return Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Unique task",
        description="Detailed implementation scope.",
        state="Needs Human",
        issue_type="task",
        project_id="proj-1",
    )


def _setup_owner_endpoint(monkeypatch, *, actor: str, is_owner: bool):
    issue = _issue()
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    project = SimpleNamespace(
        status_actor_login="owner",
        tracker_owner=None,
        status_label_authorized_logins=[],
    )
    orch = MagicMock()
    orch._get_project_by_id.return_value = project
    orch._owner_resolve_duplicate_screening.return_value = True

    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
    monkeypatch.setattr(
        server_module,
        "_get_tracker_for_issue_or_project",
        lambda _orch, _identifier, _project_id: (tracker, "proj-1"),
    )
    monkeypatch.setattr(
        server_module,
        "_authenticated_principal",
        lambda _request: AuthenticatedPrincipal(actor, actor, "basic"),
    )
    monkeypatch.setattr("oompah.transition_gate.is_project_owner", lambda *_: is_owner)
    return orch, tracker


def test_owner_resolution_requires_authenticated_principal(monkeypatch):
    monkeypatch.setattr(server_module, "_get_orchestrator", MagicMock)
    monkeypatch.setattr(server_module, "_authenticated_principal", lambda _request: None)

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/issues/TASK-1/duplicate-screening/owner-resolution",
        json={"verdict": "no_duplicate", "reason": "Reviewed the corpus."},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication"


def test_non_owner_cannot_apply_owner_resolution(monkeypatch):
    orch, _tracker = _setup_owner_endpoint(
        monkeypatch,
        actor="not-owner",
        is_owner=False,
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/issues/TASK-1/duplicate-screening/owner-resolution",
        json={"verdict": "no_duplicate", "reason": "No duplicate found."},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    orch._owner_resolve_duplicate_screening.assert_not_called()


def test_authenticated_owner_resolution_passes_revision_and_returns_rearm_state(
    monkeypatch,
):
    orch, _tracker = _setup_owner_endpoint(
        monkeypatch,
        actor="owner",
        is_owner=True,
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/issues/TASK-1/duplicate-screening/owner-resolution",
        json={
            "verdict": "no_duplicate",
            "reason": "Reviewed all active peer tasks.",
            "task_fingerprint": "fingerprint-v2",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Open"
    assert response.json()["retry_count"] == 0
    kwargs = orch._owner_resolve_duplicate_screening.call_args.kwargs
    assert kwargs["owner_login"] == "owner"
    assert kwargs["expected_fingerprint"] == "fingerprint-v2"
    assert kwargs["reason"] == "Reviewed all active peer tasks."


def test_needs_human_summary_advertises_authoritative_recovery_action():
    issue = _issue()
    record = inconclusive_record(
        new_claim_record(issue, owner="scheduler", retry_count=3),
        retry_count=3,
        retry_after=None,
        evidence="Infrastructure failures.",
    )
    issue.duplicate_screening = record.to_dict()
    orch = SimpleNamespace(config=ServiceConfig(duplicate_preflight_max_agents=1))

    summary = server_module._issue_duplicate_screening_summary(issue, orch)

    assert summary is not None
    assert "owner-resolution" in summary["recovery_action"]
    assert "rearm" in summary["recovery_action"]
