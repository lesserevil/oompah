"""HTTP tests for the per-project console endpoints (oompah-zlz_2-ebwe).

Covers:

* GET /api/v1/console/{project_id}/transcript — page over JSONL
  transcript when no in-memory session exists yet.
* 404 on unknown project.
* 503 when the console manager hasn't been wired (cold-start sanity).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.console import ConsoleManager, ConsoleStore
from oompah.models import Project
from oompah.server import app


def _make_project(tmp_path: Path) -> Project:
    repo = tmp_path / "repo"
    repo.mkdir()
    return Project(
        id="proj-T",
        name="testproj",
        repo_url="u",
        repo_path=str(repo),
    )


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def wired_console(tmp_path, client):
    """Install a ConsoleManager + minimal orchestrator into the server
    module for the duration of one test, then restore."""
    project = _make_project(tmp_path)
    orch = MagicMock()
    orch.project_store.get.side_effect = (
        lambda pid: project if pid == project.id else None
    )

    def _resolve_backend(pid: str) -> dict:
        return {"backend_name": "claude", "permission_mode": "acceptEdits"}

    def _resolve_project(pid: str):
        if pid != project.id:
            return None
        return {"repo_path": project.repo_path, "name": project.name}

    mgr = ConsoleManager(
        resolve_backend=_resolve_backend,
        broadcast=lambda pid, ev: None,
        resolve_project=_resolve_project,
        base_dir=str(tmp_path / "console"),
    )
    prior_orch = server_module._orchestrator
    prior_mgr = server_module._console_manager
    server_module._orchestrator = orch
    server_module._console_manager = mgr
    try:
        yield {"project": project, "mgr": mgr, "tmp_path": tmp_path}
    finally:
        server_module._orchestrator = prior_orch
        server_module._console_manager = prior_mgr


class TestTranscriptEndpoint:
    def test_returns_empty_for_unused_project(self, client, wired_console):
        pid = wired_console["project"].id
        r = client.get(f"/api/v1/console/{pid}/transcript")
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == pid
        assert data["events"] == []
        assert data["total"] == 0

    def test_returns_persisted_events(self, client, wired_console):
        pid = wired_console["project"].id
        # Pre-seed JSONL on disk via a separate ConsoleStore.
        base_dir = str(wired_console["tmp_path"] / "console")
        store = ConsoleStore(pid, base_dir=base_dir)
        store.append("operator_input", {"text": "hello"})
        store.append("acp_text", {"text": "hi"})
        store.close()
        r = client.get(f"/api/v1/console/{pid}/transcript")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        kinds = [e["kind"] for e in data["events"]]
        assert kinds == ["operator_input", "acp_text"]

    def test_404_on_unknown_project(self, client, wired_console):
        r = client.get("/api/v1/console/proj-nope/transcript")
        assert r.status_code == 404
        body = r.json()
        assert body["error"]["code"] == "no_project"

    def test_503_when_not_initialized(self, client):
        prior = server_module._console_manager
        server_module._console_manager = None
        try:
            r = client.get("/api/v1/console/anything/transcript")
            assert r.status_code == 503
        finally:
            server_module._console_manager = prior

    def test_limit_capped(self, client, wired_console):
        """limit > 1000 should be capped, not return 400."""
        pid = wired_console["project"].id
        r = client.get(
            f"/api/v1/console/{pid}/transcript?limit=999999",
        )
        assert r.status_code == 200
        assert r.json()["limit"] == 1000

    def test_pagination_before(self, client, wired_console):
        pid = wired_console["project"].id
        base_dir = str(wired_console["tmp_path"] / "console")
        store = ConsoleStore(pid, base_dir=base_dir)
        for i in range(10):
            store.append("operator_input", {"text": f"m{i}"})
        store.close()
        r = client.get(
            f"/api/v1/console/{pid}/transcript?limit=5&before=5",
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 10
        assert len(data["events"]) == 5
        assert [e["payload"]["text"] for e in data["events"]] == [
            f"m{i}" for i in range(5)
        ]
