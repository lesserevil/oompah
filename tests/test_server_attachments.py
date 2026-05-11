"""Tests for the multimodal-attachment HTTP endpoints (Phase 4).

Covers:
- GET /api/v1/issues/{identifier}/attachments — list
- POST /api/v1/issues/{identifier}/attachments — upload (mime/size rejection)
- GET /api/v1/attachments/{path} — binary stream + path traversal + SVG sanitization
- DELETE /api/v1/attachments/{path} — user vs generated
"""

from __future__ import annotations

import io
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.config import ServiceConfig
from oompah.models import Project
from oompah.server import app


def _make_repo(tmp_path) -> str:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "README").write_text("hi")
    subprocess.run(["git", "add", "README"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return str(repo)


def _png(n: int = 64) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * max(0, n - 8)


def _make_orch(tmp_path):
    repo = _make_repo(tmp_path)
    project = Project(
        id="proj-1", name="r", repo_url="u", repo_path=repo,
        lfs_available=True,
    )
    orch = MagicMock()
    orch.config = ServiceConfig()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.get.side_effect = lambda pid: project if pid == "proj-1" else None
    return orch, project


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET list
# ---------------------------------------------------------------------------


class TestListAttachments:
    def test_returns_records_from_tracker(self, tmp_path, client):
        orch, _ = _make_orch(tmp_path)
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = [
            {"path": ".oompah/attachments/foo-1/x.png", "size": 10},
        ]
        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch.object(server_module, "_find_tracker_for_issue", return_value=(tracker, "proj-1", MagicMock())):
            r = client.get("/api/v1/issues/foo-1/attachments")
        assert r.status_code == 200
        assert r.json()[0]["path"].endswith("x.png")

    def test_unknown_issue_returns_404(self, tmp_path, client):
        orch, _ = _make_orch(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch.object(server_module, "_find_tracker_for_issue", return_value=(None, None, None)):
            r = client.get("/api/v1/issues/unknown/attachments")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST upload
# ---------------------------------------------------------------------------


class TestUploadAttachment:
    def test_rejects_unsupported_mime(self, tmp_path, client):
        orch, _ = _make_orch(tmp_path)
        tracker = MagicMock()
        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch.object(server_module, "_find_tracker_for_issue", return_value=(tracker, "proj-1", MagicMock())):
            r = client.post(
                "/api/v1/issues/foo-1/attachments",
                files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
            )
        assert r.status_code == 415
        tracker.set_attachments.assert_not_called()

    def test_happy_path(self, tmp_path, client):
        orch, project = _make_orch(tmp_path)
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = []
        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch.object(server_module, "_find_tracker_for_issue", return_value=(tracker, "proj-1", MagicMock())):
            r = client.post(
                "/api/v1/issues/foo-1/attachments",
                files={"file": ("shot.png", _png(100), "image/png")},
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["mime_type"] == "image/png"
        assert body["path"].startswith(".oompah/attachments/foo-1/")
        # File landed in the repo on disk.
        assert (
            tmp_path / "repo" / body["path"]
        ).exists()
        # Beads metadata write happened.
        tracker.set_attachments.assert_called_once()


# ---------------------------------------------------------------------------
# GET binary stream + path validation
# ---------------------------------------------------------------------------


class TestServeAttachment:
    def _land_file(self, repo: str, identifier: str, name: str, data: bytes) -> str:
        d = os.path.join(repo, ".oompah", "attachments", identifier)
        os.makedirs(d, exist_ok=True)
        full = os.path.join(d, name)
        with open(full, "wb") as f:
            f.write(data)
        return f".oompah/attachments/{identifier}/{name}"

    def test_serves_known_file(self, tmp_path, client):
        orch, project = _make_orch(tmp_path)
        rel = self._land_file(project.repo_path, "foo-1", "x.png", _png(80))
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.get(f"/api/v1/attachments/{rel}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")
        assert r.content.startswith(b"\x89PNG")

    def test_rejects_traversal(self, tmp_path, client):
        orch, _ = _make_orch(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.get("/api/v1/attachments/.oompah/attachments/../../etc/passwd")
        assert r.status_code == 404

    def test_rejects_outside_attachments_root(self, tmp_path, client):
        orch, _ = _make_orch(tmp_path)
        # Path doesn't start with .oompah/attachments/.
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.get("/api/v1/attachments/README")
        assert r.status_code == 404

    def test_sanitizes_svg(self, tmp_path, client):
        orch, project = _make_orch(tmp_path)
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<script>alert(1)</script>'
            b'<rect onload="evil()" width="10" height="10"/>'
            b'</svg>'
        )
        rel = self._land_file(project.repo_path, "foo-1", "x.svg", svg)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.get(f"/api/v1/attachments/{rel}")
        assert r.status_code == 200
        assert b"<script>" not in r.content
        assert b"onload" not in r.content
        # Structure preserved.
        assert b"<rect" in r.content


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


class TestDeleteAttachment:
    def _land(self, repo, identifier, name) -> str:
        d = os.path.join(repo, ".oompah", "attachments", identifier)
        os.makedirs(d, exist_ok=True)
        full = os.path.join(d, name)
        with open(full, "wb") as f:
            f.write(_png(40))
        return f".oompah/attachments/{identifier}/{name}"

    def test_deletes_user_attachment(self, tmp_path, client):
        orch, project = _make_orch(tmp_path)
        rel = self._land(project.repo_path, "foo-1", "x.png")
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = [{"path": rel, "generated": False}]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.delete(f"/api/v1/attachments/{rel}")
        assert r.status_code == 200
        tracker.set_attachments.assert_called_once()
        # File is gone on disk.
        assert not os.path.exists(os.path.join(project.repo_path, rel))

    def test_generated_requires_force(self, tmp_path, client):
        orch, project = _make_orch(tmp_path)
        rel = self._land(project.repo_path, "foo-1", "diag.png")
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = [{"path": rel, "generated": True}]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.delete(f"/api/v1/attachments/{rel}")
        assert r.status_code == 409
        tracker.set_attachments.assert_not_called()
        # File still on disk.
        assert os.path.exists(os.path.join(project.repo_path, rel))

    def test_generated_force_succeeds(self, tmp_path, client):
        orch, project = _make_orch(tmp_path)
        rel = self._land(project.repo_path, "foo-1", "diag.png")
        tracker = MagicMock()
        tracker.fetch_attachments.return_value = [{"path": rel, "generated": True}]
        orch._tracker_for_project = MagicMock(return_value=tracker)
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            r = client.delete(f"/api/v1/attachments/{rel}?force=generated")
        assert r.status_code == 200
        tracker.set_attachments.assert_called_once()
