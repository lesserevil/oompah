"""Tests that malformed JSON on POST/PATCH endpoints returns 400, not 500.

Regression tests for oompah-zlz_2-uemy: before the fix, any POST/PATCH
endpoint that called ``await request.json()`` without catching
json.JSONDecodeError would return HTTP 500 (Internal Server Error) when
the client sent an empty or invalid JSON body. The error watcher logged
the 500 and auto-filed this bug bead. After the fix, all such endpoints
return HTTP 400 (Bad Request) with a descriptive error message.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from fastapi.testclient import TestClient
from oompah.models import Project
from oompah.projects import ProjectStore


@pytest.fixture(autouse=True)
def client(tmp_path):
    """Set up a test client with a minimal mock orchestrator."""
    from oompah.server import app

    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )
    p = Project(
        id="proj-abc",
        name="testproject",
        repo_url="https://github.com/org/test.git",
        repo_path=str(tmp_path / "repos" / "test"),
        branch="main",
    )
    store._projects[p.id] = p
    store._save()

    orch = MagicMock()
    orch.project_store = store
    orch._observers = []
    orch._state_only_observers = []
    orch._activity_observers = []
    orch.get_snapshot.return_value = {"counts": {}, "running": {}}
    orch.tracker = MagicMock()
    orch.config = MagicMock()
    orch.config.tracker_terminal_states = ["closed"]
    orch.state = MagicMock()
    orch.state.running = {}
    orch.state.retry_attempts = {}
    orch.state.completed = set()
    orch.state.claimed = set()

    import oompah.server as srv

    old_orch = srv._orchestrator
    srv._orchestrator = orch
    srv._agent_profile_store = MagicMock()
    srv._role_store = MagicMock()
    srv._provider_store = MagicMock()
    srv._error_watcher = MagicMock()
    srv._log_watcher_manager = None
    srv._console_manager = None
    yield TestClient(app)
    srv._orchestrator = old_orch
    srv._agent_profile_store = MagicMock()
    srv._role_store = MagicMock()
    srv._provider_store = MagicMock()


# -----------------------------------------------------------------------
# Project endpoints (the original trigger for oompah-zlz_2-uemy)
# -----------------------------------------------------------------------

class TestProjectCreateMalformedJson:
    """POST /api/v1/projects with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/projects", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"

    def test_invalid_json(self, client):
        res = client.post("/api/v1/projects", content="not json", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"

    def test_json_array_not_object(self, client):
        """A JSON array is valid JSON but not a valid request body — must return 400."""
        res = client.post("/api/v1/projects", content="[]", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"
        assert "JSON object" in res.json()["error"]["message"]


class TestProjectUpdateMalformedJson:
    """PATCH /api/v1/projects/{id} with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.patch("/api/v1/projects/proj-abc", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"

    def test_invalid_json(self, client):
        res = client.patch("/api/v1/projects/proj-abc", content="bad", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


# -----------------------------------------------------------------------
# Issue endpoints
# -----------------------------------------------------------------------

class TestIssueCreateMalformedJson:
    """POST /api/v1/issues with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/issues", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"

    def test_invalid_json(self, client):
        res = client.post("/api/v1/issues", content="{", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


class TestIssueUpdateMalformedJson:
    """PATCH /api/v1/issues/{id} with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.patch("/api/v1/issues/issue-1", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


class TestIssueLabelAddMalformedJson:
    """POST /api/v1/issues/{id}/labels with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/issues/issue-1/labels", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


class TestIssueCommentAddMalformedJson:
    """POST /api/v1/issues/{id}/comments with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/issues/issue-1/comments", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


# -----------------------------------------------------------------------
# Provider endpoints
# -----------------------------------------------------------------------

class TestProviderCreateMalformedJson:
    """POST /api/v1/providers with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/providers", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


class TestProviderUpdateMalformedJson:
    """PATCH /api/v1/providers/{id} with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.patch("/api/v1/providers/prov-1", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


# -----------------------------------------------------------------------
# Error reporter endpoint
# -----------------------------------------------------------------------

class TestErrorReporterMalformedJson:
    """POST /api/v1/errors with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/errors", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


# -----------------------------------------------------------------------
# Focus endpoints
# -----------------------------------------------------------------------

class TestFocusCreateMalformedJson:
    """POST /api/v1/foci with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/foci", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


class TestFocusUpdateMalformedJson:
    """PATCH /api/v1/foci/{name} with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.patch("/api/v1/foci/test-focus", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


class TestFocusSuggestionUpdateMalformedJson:
    """PATCH /api/v1/foci/suggestions/{name} with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.patch("/api/v1/foci/suggestions/test-suggestion", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"


# -----------------------------------------------------------------------
# Providers fetch-models endpoint
# -----------------------------------------------------------------------

class TestFetchModelsMalformedJson:
    """POST /api/v1/providers/fetch-models with malformed body must return 400."""

    def test_empty_body(self, client):
        res = client.post("/api/v1/providers/fetch-models", content="", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation"
