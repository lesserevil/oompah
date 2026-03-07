"""Tests for edit-state protection in the dashboard JavaScript.

When a user is inline-editing a bead's title or description in the web UI,
incoming WebSocket updates must NOT overwrite what the user is typing.
These tests verify that the JavaScript in DASHBOARD_HTML contains the
necessary edit-state tracking and deferred-render logic.

See issue: umpah-tgu
"""

import os
import re

import pytest


def _load_dashboard_html() -> str:
    """Load DASHBOARD_HTML from server.py without importing fastapi."""
    server_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "server.py"
    )
    with open(server_path, "r") as f:
        source = f.read()
    # Extract the DASHBOARD_HTML string literal
    match = re.search(
        r'DASHBOARD_HTML\s*=\s*"""\\\n(.*?)^"""',
        source,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "Could not find DASHBOARD_HTML in server.py"
    return match.group(1)


def _extract_script(html: str) -> str:
    """Extract the main <script> block from the dashboard HTML."""
    match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert match, "Could not find <script> block in DASHBOARD_HTML"
    return match.group(1)


@pytest.fixture(scope="module")
def script():
    html = _load_dashboard_html()
    return _extract_script(html)


class TestEditStateTracking:
    """Verify that editing-state globals and logic exist in the dashboard JS."""

    def test_editingState_global_declared(self, script):
        """editingState must be declared to track which field is being edited."""
        assert "let editingState" in script

    def test_pendingBoardData_global_declared(self, script):
        """_pendingBoardData must be declared to queue data during edits."""
        assert "let _pendingBoardData" in script

    def test_renderBoard_checks_editingState(self, script):
        """renderBoard() must check editingState and defer DOM rebuild."""
        assert "if (editingState)" in script
        assert "_pendingBoardData = data" in script

    def test_renderBoard_still_updates_boardData_when_deferred(self, script):
        """Even when deferring, boardData should be updated for lookups."""
        match = re.search(
            r"if \(editingState\)\s*\{(.*?)\breturn\b",
            script,
            re.DOTALL,
        )
        assert match, "Could not find editingState guard block"
        guard_block = match.group(1)
        assert "boardData = data" in guard_block
        assert "allIssuesFlat = flattenIssues(data)" in guard_block

    def test_focus_handler_sets_editingState(self, script):
        """Card focus handler must set editingState to protect the edit."""
        assert "editingState = { identifier:" in script or \
               "editingState = {identifier:" in script

    def test_blur_handler_clears_editingState(self, script):
        """Card blur handler must clear editingState when done editing."""
        assert "editingState = null" in script

    def test_blur_handler_flushes_pending_data(self, script):
        """After blur saves, any pending board data must be rendered."""
        assert "if (_pendingBoardData)" in script
        assert "renderBoard(pending)" in script

    def test_detail_panel_skips_refresh_when_comment_focused(self, script):
        """refreshOpenDetailPanel must not overwrite a focused comment input."""
        assert "document.activeElement === commentInput" in script or \
               "document.activeElement === ci" in script


class TestEditProtectionIntegration:
    """Higher-level checks that the edit protection is wired correctly."""

    def test_ws_onmessage_calls_renderBoard_which_defers(self, script):
        """The ws.onmessage handler calls renderBoard, which will defer if editing.

        renderBoard may receive data directly (renderBoard(msg.data)) or
        filtered through filterByProject (renderBoard(filterByProject(msg.data))).
        Either way, renderBoard is called with the WebSocket issues data.
        """
        assert "renderBoard(msg.data)" in script or \
               "renderBoard(filterByProject(msg.data))" in script
        assert "if (editingState)" in script

    def test_clear_before_save_not_after(self, script):
        """editingState must be cleared BEFORE the async updateIssue call.

        This ensures that any WebSocket update arriving during the save
        can immediately render (since the user is no longer editing).
        """
        blur_match = re.search(
            r"editingState = null;(.*?)await updateIssue",
            script,
            re.DOTALL,
        )
        assert blur_match is not None, \
            "editingState = null should appear before await updateIssue in blur handler"

    def test_pending_data_cleared_on_normal_render(self, script):
        """When renderBoard runs normally (no editing), _pendingBoardData is cleared."""
        match = re.search(
            r"if \(editingState\)\s*\{.*?\breturn;\s*\}(.*?)board\.innerHTML",
            script,
            re.DOTALL,
        )
        assert match, "Could not find normal render path after editingState guard"
        normal_path = match.group(1)
        assert "_pendingBoardData = null" in normal_path
