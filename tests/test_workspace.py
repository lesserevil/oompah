"""Tests for oompah.workspace."""

import os

import pytest

from oompah.workspace import WorkspaceError, WorkspaceManager, sanitize_identifier


class TestSanitizeIdentifier:
    def test_clean_string(self):
        assert sanitize_identifier("beads-001") == "beads-001"

    def test_special_chars(self):
        assert sanitize_identifier("beads/001 foo") == "beads_001_foo"

    def test_dots_and_underscores(self):
        assert sanitize_identifier("beads_001.txt") == "beads_001.txt"

    def test_empty(self):
        assert sanitize_identifier("") == ""


class TestWorkspaceManager:
    def test_create_and_path(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={},
        )
        ws = mgr.create_for_issue("beads-001")
        assert ws.created_now is True
        assert os.path.isdir(ws.path)
        assert ws.workspace_key == "beads-001"

    def test_reuse_existing(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={},
        )
        ws1 = mgr.create_for_issue("beads-001")
        ws2 = mgr.create_for_issue("beads-001")
        assert ws1.path == ws2.path
        assert ws2.created_now is False

    def test_remove_workspace(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={},
        )
        ws = mgr.create_for_issue("beads-002")
        assert os.path.isdir(ws.path)
        mgr.remove_workspace("beads-002")
        assert not os.path.isdir(ws.path)

    def test_remove_nonexistent_is_noop(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={},
        )
        mgr.remove_workspace("nonexistent")  # should not raise

    def test_path_traversal_prevented(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={},
        )
        # sanitize_identifier replaces / and .. chars, so traversal chars become underscores
        ws = mgr.create_for_issue("..%2F..%2Fetc")
        assert str(tmp_path) in ws.path

    def test_workspace_path_for(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={},
        )
        path = mgr.workspace_path_for("beads-001")
        assert path.endswith("beads-001")

    def test_after_create_hook(self, tmp_path):
        marker = tmp_path / "hook_ran"
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={"after_create": f"touch {marker}"},
        )
        ws = mgr.create_for_issue("beads-hook")
        assert ws.created_now is True
        assert marker.exists()

    def test_after_create_hook_failure_cleans_up(self, tmp_path):
        mgr = WorkspaceManager(
            workspace_root=str(tmp_path / "workspaces"),
            hooks={"after_create": "exit 1"},
        )
        with pytest.raises(WorkspaceError):
            mgr.create_for_issue("beads-fail")
        # Workspace should be cleaned up on hook failure
        ws_path = mgr.workspace_path_for("beads-fail")
        assert not os.path.exists(ws_path)
