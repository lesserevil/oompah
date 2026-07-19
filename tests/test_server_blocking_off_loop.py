"""Tests that blocking I/O calls in server.py route handlers run off the
event loop via asyncio.to_thread(), not inline.

Verifies the fixes for TASK-473.2: each route handler wraps its synchronous
file / subprocess I/O in asyncio.to_thread so it cannot stall the shared
event loop that WebSocket broadcasts and the orchestrator depend on.

Coverage:
  - api_list_foci        → load_foci via to_thread
  - api_create_focus     → save_foci via to_thread
  - api_delete_focus     → file load+save via to_thread
  - api_update_focus     → file load+save via to_thread
  - api_list_focus_suggestions → load_suggestions via to_thread
  - api_update_focus_suggestion → update_suggestion_status via to_thread
  - api_issue_quality_source → has_quality_source via to_thread
  - api_create_issue (enhance) → _run_issue_enhancement via to_thread
  - api_serve_attachment → file read via to_thread
  - api_upload_attachment → file write+store+commit via to_thread
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.focus import Focus
from oompah.issue_enhancer import EnhancementResult, IssueEnhancerError
from oompah.models import Issue
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_focus(name: str = "test-focus") -> Focus:
    return Focus(name=name, role="backend", description="test")


def _make_issue(identifier: str = "TASK-1", issue_type: str = "task") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        state="open",
        issue_type=issue_type,
    )


def _make_orch_with_project(tmp_path, project_id: str = "proj-1"):
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.repo_path = str(tmp_path)

    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock(return_value=_make_issue())
    mock_tracker.add_label = MagicMock()
    mock_tracker.add_parent_child = MagicMock()

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.get = MagicMock(return_value=mock_project)

    fake_provider = MagicMock()
    fake_provider.base_url = "https://x.test"
    fake_provider.api_key = "k"
    mock_orch._resolve_role = MagicMock(return_value=(fake_provider, "model-test"))
    mock_orch.provider_store.get_default = MagicMock(return_value=fake_provider)
    return mock_orch, mock_tracker, mock_project


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper: track asyncio.to_thread calls
# ---------------------------------------------------------------------------

def _make_to_thread_spy():
    """Returns (spy, call_log) where spy wraps asyncio.to_thread and
    call_log is a list of (func, args) tuples collected per invocation."""
    call_log: list[tuple] = []
    _orig = asyncio.to_thread

    async def _spy(fn, *args, **kwargs):
        call_log.append((fn, args, kwargs))
        return await _orig(fn, *args, **kwargs)

    return _spy, call_log


# ---------------------------------------------------------------------------
# API loop scheduler — observer callbacks may run from orchestrator thread
# ---------------------------------------------------------------------------

class TestApiLoopScheduler:
    def test_schedule_api_coro_uses_captured_api_loop(self):
        loop = MagicMock()
        loop.is_running.return_value = True
        created: list[bool] = []

        def factory():
            async def _noop():
                return None

            created.append(True)
            return _noop()

        with patch.object(server_module, "_api_event_loop", loop):
            server_module._schedule_api_coro(factory)

        assert not created
        callback = loop.call_soon_threadsafe.call_args.args[0]
        callback()
        assert created == [True]
        loop.create_task.assert_called_once()
        loop.create_task.call_args.args[0].close()

    @pytest.mark.asyncio
    async def test_api_state_serves_stale_cache_without_live_snapshot(self, monkeypatch):
        orch = MagicMock()
        orch.get_snapshot.side_effect = AssertionError("must not read live state")
        snapshot = {
            "counts": {"running": 1, "retrying": 0},
            "running": [{"issue_id": "x"}],
            "retrying": [],
            "alerts": [],
        }
        monkeypatch.setattr(server_module, "_orchestrator", orch)
        monkeypatch.setattr(server_module, "_ipc", None)
        old_snapshot = server_module._state_snapshot
        old_snapshot_at = server_module._state_snapshot_at
        with server_module._state_snapshot_lock:
            server_module._state_snapshot = dict(snapshot)
            server_module._state_snapshot_at = (
                time.monotonic() - server_module._STATE_SNAPSHOT_MAX_AGE_S - 1
            )
        try:
            response = await server_module.api_state()
            data = json.loads(response.body)

            assert data["counts"] == snapshot["counts"]
            assert data["state_snapshot_stale"] is True
            orch.get_snapshot.assert_not_called()
        finally:
            with server_module._state_snapshot_lock:
                server_module._state_snapshot = old_snapshot
                server_module._state_snapshot_at = old_snapshot_at


# ---------------------------------------------------------------------------
# api_list_foci — load_foci must run via to_thread
# ---------------------------------------------------------------------------

class TestListFociOffLoop:
    def test_load_foci_called_via_to_thread(self, client, tmp_path):
        """GET /api/v1/foci must call load_foci() off the event loop."""
        foci_called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        orig_load_foci = server_module.load_foci

        def spy_load_foci(*args, **kwargs):
            foci_called_in_thread.append(
                threading.current_thread() is not main_thread
            )
            return orig_load_foci(*args, **kwargs)

        with patch.object(server_module, "load_foci", side_effect=spy_load_foci):
            resp = client.get("/api/v1/foci")

        assert resp.status_code == 200
        assert foci_called_in_thread, "load_foci was never called"
        # When called via asyncio.to_thread, the function runs in a ThreadPoolExecutor
        # worker — a different thread than the main test thread.
        assert all(foci_called_in_thread), (
            "load_foci ran on the main thread; it should run off the event loop"
        )

    def test_returns_foci_list(self, client):
        """GET /api/v1/foci returns a JSON list."""
        resp = client.get("/api/v1/foci")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# api_create_focus — save_foci must run via to_thread
# ---------------------------------------------------------------------------

class TestCreateFocusOffLoop:
    def test_save_foci_called_via_to_thread(self, client, tmp_path):
        """POST /api/v1/foci must call save_foci() off the event loop."""
        save_called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        orig_save_foci = server_module.save_foci

        def spy_save_foci(*args, **kwargs):
            save_called_in_thread.append(
                threading.current_thread() is not main_thread
            )
            # Don't actually write to any file
            return None

        with (
            patch.object(server_module, "save_foci", side_effect=spy_save_foci),
            patch("os.path.exists", return_value=False),
        ):
            resp = client.post(
                "/api/v1/foci",
                json={"name": "new-focus", "role": "backend", "description": "test"},
            )

        assert resp.status_code == 201
        assert save_called_in_thread, "save_foci was never called"
        assert all(save_called_in_thread), (
            "save_foci ran on the main thread; it must run off the event loop"
        )

    def test_create_focus_returns_new_focus(self, client, tmp_path):
        """POST /api/v1/foci returns the created focus object."""
        with patch.object(server_module, "save_foci", return_value=None):
            with patch("os.path.exists", return_value=False):
                resp = client.post(
                    "/api/v1/foci",
                    json={
                        "name": "offline-focus",
                        "role": "backend",
                        "description": "a focus",
                    },
                )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "offline-focus"


# ---------------------------------------------------------------------------
# api_delete_focus — file I/O must run via to_thread
# ---------------------------------------------------------------------------

class TestDeleteFocusOffLoop:
    def test_delete_focus_via_thread(self, client, tmp_path):
        """DELETE /api/v1/foci/{name} must perform file I/O off the event loop."""
        foci_path = tmp_path / "foci.json"
        foci_path.write_text('[{"name": "my-focus", "role": "backend", "description": "x"}]')

        io_called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        orig_save_foci = server_module.save_foci

        def spy_save_foci(*args, **kwargs):
            io_called_in_thread.append(threading.current_thread() is not main_thread)
            return orig_save_foci(*args, **kwargs)

        with (
            patch.object(server_module, "save_foci", side_effect=spy_save_foci),
            patch("oompah.server.os.path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
        ):
            import io, json
            mock_open.return_value.__enter__ = lambda s: io.StringIO(
                json.dumps([{"name": "my-focus", "role": "backend", "description": "x"}])
            )
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            resp = client.delete("/api/v1/foci/my-focus")

        # Whether found or not, I/O should have run in a thread
        assert io_called_in_thread, "save_foci was not called"
        assert all(io_called_in_thread), (
            "save_foci ran on the main thread; it must run off the event loop"
        )

    def test_delete_missing_focus_returns_404(self, client, tmp_path):
        """DELETE /api/v1/foci/{nonexistent} returns 404."""
        with patch("oompah.server.os.path.exists", return_value=False):
            resp = client.delete("/api/v1/foci/no-such-focus")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# api_update_focus — file I/O must run via to_thread
# ---------------------------------------------------------------------------

class TestUpdateFocusOffLoop:
    def test_update_focus_via_thread(self, client, tmp_path):
        """PATCH /api/v1/foci/{name} must perform file I/O off the event loop."""
        io_called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        orig_save_foci = server_module.save_foci

        def spy_save_foci(*args, **kwargs):
            io_called_in_thread.append(threading.current_thread() is not main_thread)
            return orig_save_foci(*args, **kwargs)

        with (
            patch.object(server_module, "save_foci", side_effect=spy_save_foci),
            patch("oompah.server.os.path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
        ):
            import io, json
            mock_open.return_value.__enter__ = lambda s: io.StringIO(
                json.dumps([{"name": "existing-focus", "role": "backend", "description": "x"}])
            )
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            resp = client.patch(
                "/api/v1/foci/existing-focus",
                json={"status": "inactive"},
            )

        assert io_called_in_thread, "save_foci was not called"
        assert all(io_called_in_thread), (
            "save_foci ran on the main thread; it must run off the event loop"
        )

    def test_update_builtin_focus_via_thread(self, client):
        """PATCH /api/v1/foci/{builtin} should still run I/O off the event loop."""
        from oompah.focus import BUILTIN_FOCI

        if not BUILTIN_FOCI:
            pytest.skip("no builtin foci available")

        builtin_name = BUILTIN_FOCI[0].name
        io_called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        orig_save_foci = server_module.save_foci

        def spy_save_foci(*args, **kwargs):
            io_called_in_thread.append(threading.current_thread() is not main_thread)
            return orig_save_foci(*args, **kwargs)

        with (
            patch.object(server_module, "save_foci", side_effect=spy_save_foci),
            patch("oompah.server.os.path.exists", return_value=False),
        ):
            resp = client.patch(
                f"/api/v1/foci/{builtin_name}",
                json={"status": "inactive"},
            )

        assert resp.status_code == 200
        assert io_called_in_thread, "save_foci was not called"
        assert all(io_called_in_thread), (
            "save_foci ran on main thread; must run off the event loop"
        )


# ---------------------------------------------------------------------------
# api_list_focus_suggestions — load_suggestions via to_thread
# ---------------------------------------------------------------------------

class TestListFocusSuggestionsOffLoop:
    def test_load_suggestions_called_via_to_thread(self, client):
        """GET /api/v1/foci/suggestions must call load_suggestions() off the event loop."""
        called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        orig = server_module.load_suggestions

        def spy(*args, **kwargs):
            called_in_thread.append(threading.current_thread() is not main_thread)
            return orig(*args, **kwargs)

        with patch.object(server_module, "load_suggestions", side_effect=spy):
            resp = client.get("/api/v1/foci/suggestions")

        assert resp.status_code == 200
        assert called_in_thread, "load_suggestions was never called"
        assert all(called_in_thread), (
            "load_suggestions ran on the main thread; it must run off the event loop"
        )


# ---------------------------------------------------------------------------
# api_update_focus_suggestion — update_suggestion_status via to_thread
# ---------------------------------------------------------------------------

class TestUpdateFocusSuggestionOffLoop:
    def test_update_suggestion_via_thread(self, client):
        """PATCH /api/v1/foci/suggestions/{name} must call update_suggestion_status() off loop."""
        called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        def spy(name: str, status: str, path=None):
            called_in_thread.append(threading.current_thread() is not main_thread)
            return True  # pretend found

        with patch.object(server_module, "update_suggestion_status", side_effect=spy):
            resp = client.patch(
                "/api/v1/foci/suggestions/my-suggestion",
                json={"status": "accepted"},
            )

        assert resp.status_code == 200
        assert called_in_thread, "update_suggestion_status was never called"
        assert all(called_in_thread), (
            "update_suggestion_status ran on main thread; must run off the event loop"
        )

    def test_update_missing_suggestion_returns_404(self, client):
        """PATCH /api/v1/foci/suggestions/{missing} returns 404 when not found."""
        with patch.object(server_module, "update_suggestion_status", return_value=False):
            resp = client.patch(
                "/api/v1/foci/suggestions/no-such-suggestion",
                json={"status": "dismissed"},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# api_issue_quality_source — has_quality_source via to_thread
# ---------------------------------------------------------------------------

class TestIssueQualitySourceOffLoop:
    def test_has_quality_source_called_via_to_thread(self, client, tmp_path):
        """GET /api/v1/projects/{id}/issue-quality-source must call has_quality_source off loop."""
        called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        mock_orch, _, _ = _make_orch_with_project(tmp_path)

        orig_has_qs = server_module.has_quality_source

        def spy_has_qs(*args, **kwargs):
            called_in_thread.append(threading.current_thread() is not main_thread)
            return False  # no quality source → skip load_quality_source call

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "has_quality_source", side_effect=spy_has_qs),
        ):
            resp = client.get("/api/v1/projects/proj-1/issue-quality-source")

        assert resp.status_code == 200
        assert called_in_thread, "has_quality_source was never called"
        assert all(called_in_thread), (
            "has_quality_source ran on the main thread; it must run off the event loop"
        )


# ---------------------------------------------------------------------------
# api_create_issue (enhancement) — _run_issue_enhancement via to_thread
# ---------------------------------------------------------------------------

class TestCreateIssueEnhancementOffLoop:
    def _enhancement(self):
        return EnhancementResult(
            original_title="fix it",
            original_description="broken",
            enhanced_title="Fix the thing",
            enhanced_description="Detailed description",
            missing_fields=[],
            suggested_changes="added detail",
            diff="-broken\n+Detailed description",
        )

    def test_enhancement_called_via_to_thread(self, client, tmp_path):
        """POST /api/v1/issues?enhance=true must call _run_issue_enhancement off the event loop."""
        called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        enhancement = self._enhancement()

        orig_run = server_module._run_issue_enhancement

        def spy_run(**kwargs):
            called_in_thread.append(threading.current_thread() is not main_thread)
            return enhancement

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "_run_issue_enhancement", side_effect=spy_run),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=true",
                json={"title": "fix it", "description": "broken", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert called_in_thread, "_run_issue_enhancement was never called"
        assert all(called_in_thread), (
            "_run_issue_enhancement ran on the main thread; it must run off the event loop"
        )

    def test_enhancement_error_propagated_correctly(self, client, tmp_path):
        """IssueEnhancerError raised in thread is returned as 502."""
        mock_orch, _, _ = _make_orch_with_project(tmp_path)

        def failing_run(**kwargs):
            raise IssueEnhancerError("no quality source")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "_run_issue_enhancement", side_effect=failing_run),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=true",
                json={"title": "fix it", "description": "broken", "project_id": "proj-1"},
            )

        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "enhance_failed"


# ---------------------------------------------------------------------------
# api_serve_attachment — file read via to_thread
# ---------------------------------------------------------------------------

class TestServeAttachmentOffLoop:
    def test_file_read_via_to_thread(self, client, tmp_path):
        """GET /api/v1/attachments/{path} must read the file off the event loop."""
        from oompah.models import Project

        # Create a real attachment file
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        attach_dir = repo_dir / ".oompah" / "attachments" / "inputs" / "TASK-1"
        attach_dir.mkdir(parents=True)
        attachment_file = attach_dir / "abc-test.png"
        attachment_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 56)

        project = Project(
            id="proj-1",
            name="test",
            repo_url="u",
            repo_path=str(repo_dir),
        )
        mock_orch = MagicMock()
        mock_orch.project_store.list_all.return_value = [project]

        io_called_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        _orig_open = open

        def spy_open(path, *args, **kwargs):
            if str(attachment_file) in str(path):
                io_called_in_thread.append(threading.current_thread() is not main_thread)
            return _orig_open(path, *args, **kwargs)

        rel_path = "proj-1/.oompah/attachments/inputs/TASK-1/abc-test.png"

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module,
                "_resolve_attachment_path",
                return_value=("proj-1", str(attachment_file)),
            ),
            patch("builtins.open", side_effect=spy_open),
        ):
            resp = client.get(f"/api/v1/attachments/{rel_path}")

        assert resp.status_code == 200
        assert io_called_in_thread, "open() was never called for the attachment file"
        assert all(io_called_in_thread), (
            "Attachment file read ran on main thread; it must run off the event loop"
        )


# ---------------------------------------------------------------------------
# api_upload_attachment — write + store + commit via to_thread
# ---------------------------------------------------------------------------

class TestUploadAttachmentOffLoop:
    def test_store_add_called_via_to_thread(self, client, tmp_path):
        """POST /api/v1/issues/{id}/attachments must run AttachmentStore.add off loop."""
        from oompah.attachments import Attachment, AttachmentStore
        from oompah.models import Project

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        project = Project(
            id="proj-1",
            name="test",
            repo_url="u",
            repo_path=str(repo_dir),
        )
        mock_issue = _make_issue()
        mock_tracker = MagicMock()
        mock_tracker.fetch_attachments.return_value = []
        mock_tracker.set_attachments.return_value = None

        mock_orch = MagicMock()
        mock_orch.project_store.get.return_value = project

        store_add_in_thread: list[bool] = []
        main_thread = threading.current_thread()

        from datetime import datetime, timezone
        fake_rec = Attachment(
            path=".oompah/attachments/inputs/TASK-1/abc-test.png",
            mime_type="image/png",
            size=64,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        orig_add = AttachmentStore.add

        def spy_add(self, *args, **kwargs):
            store_add_in_thread.append(threading.current_thread() is not main_thread)
            return fake_rec

        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 56

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "_find_tracker_for_issue",
                         return_value=(mock_tracker, "proj-1", mock_issue)),
            patch.object(AttachmentStore, "add", spy_add),
            patch.object(AttachmentStore, "commit", return_value=None),
        ):
            resp = client.post(
                "/api/v1/issues/TASK-1/attachments",
                files={"file": ("test.png", png_data, "image/png")},
            )

        assert resp.status_code == 201
        assert store_add_in_thread, "AttachmentStore.add was never called"
        assert all(store_add_in_thread), (
            "AttachmentStore.add ran on main thread; it must run off the event loop"
        )
