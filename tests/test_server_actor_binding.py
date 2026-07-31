"""OOMPAH-624: Server-side actor binding to the authenticated principal.

Covers the six regression scenarios called out in the issue:

1. Authenticated project owner passes owner-gated intake action without
   ``--actor`` / ``actor_login``.
2. Authenticated non-owner is denied owner-only operations.
3. Supplying another user's ``actor_login`` cannot spoof owner access.
4. A conflicting ``actor_login`` is rejected and does not mutate state.
5. Configured username-to-actor mapping resolves the correct owner.
6. Authenticated principal is ignored for unauthenticated (read-only)
   compatibility deployments.
"""

from __future__ import annotations

import base64
import contextlib
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.actor_mapping import ActorMap
from oompah.http_auth import HtpasswdCredentials, VerificationError
from oompah.models import Issue
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _basic(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def _htpasswd_creds(users: dict[str, str]) -> HtpasswdCredentials:
    creds = HtpasswdCredentials(enabled=True)

    def verifier(u: str, p: str) -> None:
        if users.get(u) == p:
            return
        raise VerificationError("Invalid credentials")

    creds.verifier = verifier
    creds.htpasswd_path = "/test/.htpasswd"
    return creds


def _make_issue(state: str = "Proposed", requestor_login: str = "alice") -> Issue:
    return Issue(
        id="owner/repo#1",
        identifier="owner/repo#1",
        title="Proposed work",
        description="Enough detail",
        state=state,
        requestor_login=requestor_login,
        tracker_kind="github_issues",
    )


def _make_orchestrator(
    issue: Issue | None = None,
    *,
    status_actor_login: str = "owner-login",
    tracker_owner: str = "owner-login",
    status_label_authorized_logins: list[str] | None = None,
):
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue or _make_issue()
    tracker.update_issue = MagicMock()
    tracker.add_comment = MagicMock(return_value={"ok": True})

    project = MagicMock()
    project.id = "proj-1"
    project.tracker_kind = "github_issues"
    project.tracker_owner = tracker_owner
    project.status_actor_login = status_actor_login
    project.status_label_authorized_logins = list(status_label_authorized_logins or [])

    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = [project]
    orch.tracker = tracker
    return orch, tracker, project


@contextlib.contextmanager
def _server_auth(
    users: dict[str, str] | None = None,
    actor_map: ActorMap | None = None,
) -> Generator[None, None, None]:
    """Install htpasswd credentials and an optional actor map."""

    if users is None:
        users = {"owner-login": "secret", "carol": "carolpw"}
    creds = _htpasswd_creds(users)
    prior_creds = server_module._http_credentials
    prior_map = server_module._actor_map
    server_module._http_credentials = creds
    server_module._actor_map = actor_map
    try:
        yield
    finally:
        server_module._http_credentials = prior_creds
        server_module._actor_map = prior_map


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Authenticated owner passes without --actor
# ---------------------------------------------------------------------------


class TestAuthenticatedOwnerPassesWithoutActor:
    def test_owner_promote_without_actor_field_succeeds(self, client):
        orch, tracker, _ = _make_orchestrator()
        with (
            _server_auth(),
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    # NB: no `actor` field — the server binds to the principal.
                },
                headers={"Authorization": _basic("owner-login", "secret")},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "Backlog"
        tracker.update_issue.assert_called_once_with("owner/repo#1", status="Backlog")


# ---------------------------------------------------------------------------
# 2. Authenticated non-owner is denied owner-only operations
# ---------------------------------------------------------------------------


class TestAuthenticatedNonOwnerDenied:
    def test_non_owner_cannot_promote_to_backlog(self, client):
        orch, tracker, _ = _make_orchestrator()
        with (
            _server_auth(),
            patch.object(server_module, "_get_orchestrator", return_value=orch),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                },
                headers={"Authorization": _basic("carol", "carolpw")},
            )
        # `carol` is neither the requestor nor a project owner.
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] in {"not_owner", "owner_required", "forbidden"}
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Actor spoofing is rejected (owner cannot spoof another actor either)
# ---------------------------------------------------------------------------


class TestActorSpoofingRejected:
    def test_non_owner_supplying_owner_login_still_denied(self, client):
        """Authenticate as `carol`; request `actor: owner-login`.

        The server must derive the actor from the authenticated principal
        (`carol`) and reject the spoofed body value.  No mutation occurs.
        """

        orch, tracker, _ = _make_orchestrator()
        with (
            _server_auth(),
            patch.object(server_module, "_get_orchestrator", return_value=orch),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "owner-login",  # spoof attempt
                },
                headers={"Authorization": _basic("carol", "carolpw")},
            )
        # Must be 403 with structured actor_mismatch (never 200).
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "actor_mismatch"
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Conflicting actor_login is rejected AND does not mutate state
# ---------------------------------------------------------------------------


class TestConflictingActorRejected:
    def test_owner_who_asserts_wrong_actor_gets_actor_mismatch(self, client):
        """Even the owner cannot claim a different actor identity."""

        orch, tracker, _ = _make_orchestrator()
        with (
            _server_auth(),
            patch.object(server_module, "_get_orchestrator", return_value=orch),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "carol",  # conflict with authenticated principal
                },
                headers={"Authorization": _basic("owner-login", "secret")},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "actor_mismatch"
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Username-to-actor mapping works end-to-end
# ---------------------------------------------------------------------------


class TestActorMappingResolvesOwner:
    def test_mapped_ci_bot_gets_owner_login(self, client):
        """`ci-bot` htpasswd credential maps to project actor `owner-login`."""

        orch, tracker, _ = _make_orchestrator()
        actor_map = ActorMap(entries={"ci-bot": "owner-login"}, source="test")
        with (
            _server_auth(users={"ci-bot": "botpw"}, actor_map=actor_map),
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                },
                headers={"Authorization": _basic("ci-bot", "botpw")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Backlog"
        tracker.update_issue.assert_called_once_with("owner/repo#1", status="Backlog")

    def test_strict_mode_unmapped_user_cannot_mutate(self, client):
        """Strict mode + no mapping entry → authorization denied."""

        orch, tracker, _ = _make_orchestrator()
        actor_map = ActorMap(entries={"ci-bot": "owner-login"}, strict=True, source="test")
        with (
            _server_auth(users={"ci-bot": "botpw", "orphan": "pw"}, actor_map=actor_map),
            patch.object(server_module, "_get_orchestrator", return_value=orch),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                },
                headers={"Authorization": _basic("orphan", "pw")},
            )
        # Rejected via the actor gate (no owner mapping → not an owner).
        assert resp.status_code in {400, 403}
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Unauthenticated regression coverage — read-only compatibility preserved.
# ---------------------------------------------------------------------------


class TestUnauthenticatedCompatibility:
    def test_auth_disabled_client_supplied_actor_still_accepted(self, client):
        """When auth is off, the client-supplied `actor` value is still used.

        This preserves backward compatibility for deployments that have
        not enabled HTTP Basic authentication yet.
        """

        orch, tracker, _ = _make_orchestrator()
        # Explicitly disabled auth.
        prior = server_module._http_credentials
        server_module._http_credentials = None
        try:
            with (
                patch.object(server_module, "_get_orchestrator", return_value=orch),
                patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            ):
                resp = client.post(
                    "/api/v1/issues/placeholder/intake/promote-to-backlog",
                    json={
                        "issue_key": "owner/repo#1",
                        "project_id": "proj-1",
                        "actor": "owner-login",
                    },
                )
        finally:
            server_module._http_credentials = prior
        assert resp.status_code == 200
        assert resp.json()["status"] == "Backlog"
