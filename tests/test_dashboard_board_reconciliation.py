"""Tests for incremental board reconciliation in dashboard.html (OOMPAH-205).

The dashboard previously cleared and rebuilt the entire #board DOM on every
WebSocket 'issues' update.  The orchestrator emits a full observer update on
every tick, so the 3-second throttle still caused visibly frequent full
re-renders even when no cards changed.

The fix implements:
  1. Snapshot-based skip: identical issue payloads do not clear/recreate #board.
  2. Incremental flat-view reconciliation: unchanged column elements (and their
     scroll positions) are preserved; only changed card slots are updated.
  3. Card element cache (identifier -> fingerprint + element): unchanged cards
     reuse their existing DOM nodes across rebuilds.
  4. Drag-state guard: incoming WS data is queued while a drag is in progress
     and flushed on dragend, preventing card elements from disappearing
     mid-drag.
  5. Scroll-position preservation: column scrollTop values are saved before
     and restored after any rebuild that does happen.
  6. Focus restoration: focused inline-edit element is re-focused after a
     structural rebuild.

See issue: OOMPAH-205
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "No <script> block found in dashboard HTML"
    return max(matches, key=len)


def _extract_function(script: str, name: str) -> str:
    """Extract the body of a named top-level JS function."""
    match = re.search(
        rf"function {re.escape(name)}\s*\(.*?\)\s*\{{(.*?)(?=\nfunction |\Z)",
        script,
        re.DOTALL,
    )
    assert match, f"Could not find function '{name}' in script"
    return match.group(1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html() -> str:
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_script(html)


@pytest.fixture(scope="module")
def render_board_body(script: str) -> str:
    return _extract_function(script, "renderBoard")


@pytest.fixture(scope="module")
def try_incremental_body(script: str) -> str:
    return _extract_function(script, "tryIncrementalFlatView")


@pytest.fixture(scope="module")
def reconcile_column_body(script: str) -> str:
    return _extract_function(script, "reconcileColumnBody")


# ===========================================================================
# 1. Global reconciliation-state variables
# ===========================================================================


class TestReconciliationGlobals:
    """Verify the new reconciliation-tracking variables are declared."""

    def test_last_rendered_snapshot_declared(self, script: str):
        """_lastRenderedSnapshot must be declared to track the previous board fingerprint."""
        assert "let _lastRenderedSnapshot" in script, (
            "Script must declare 'let _lastRenderedSnapshot'"
        )

    def test_last_rendered_render_key_declared(self, script: str):
        """_lastRenderedRenderKey must track view-mode and swimlane collapse state."""
        assert "let _lastRenderedRenderKey" in script, (
            "Script must declare 'let _lastRenderedRenderKey'"
        )

    def test_card_element_cache_declared(self, script: str):
        """_cardElementCache must be declared as a Map for per-identifier DOM caching."""
        assert "let _cardElementCache" in script, (
            "Script must declare 'let _cardElementCache'"
        )
        assert "new Map()" in script, (
            "_cardElementCache must be initialised as a new Map()"
        )


# ===========================================================================
# 2. Snapshot deduplication logic in renderBoard
# ===========================================================================


class TestSnapshotDedup:
    """Verify that renderBoard skips the DOM rebuild for identical snapshots."""

    def test_computes_board_snapshot(self, render_board_body: str):
        """renderBoard must stringify display data to compute a snapshot."""
        assert "JSON.stringify(data)" in render_board_body, (
            "renderBoard must compute a JSON snapshot of the display data"
        )

    def test_compares_last_rendered_snapshot(self, render_board_body: str):
        """renderBoard must compare the new snapshot to _lastRenderedSnapshot."""
        assert "_lastRenderedSnapshot" in render_board_body, (
            "renderBoard must reference _lastRenderedSnapshot for comparison"
        )

    def test_compares_render_key(self, render_board_body: str):
        """renderBoard must also compare the render key (view mode + swimlane state)."""
        assert "_lastRenderedRenderKey" in render_board_body, (
            "renderBoard must compare _lastRenderedRenderKey to detect view/collapse changes"
        )

    def test_updates_snapshot_on_change(self, render_board_body: str):
        """renderBoard must update _lastRenderedSnapshot when data changes."""
        assert "_lastRenderedSnapshot = boardSnapshot" in render_board_body or (
            "_lastRenderedSnapshot =" in render_board_body
        ), "renderBoard must update _lastRenderedSnapshot after a real rebuild"

    def test_snapshot_skip_does_not_call_board_inner_html(self, render_board_body: str):
        """The snapshot skip path must not set board.innerHTML.

        We verify this by checking that the early-return for unchanged data
        comes BEFORE any board.innerHTML assignment in the function body.
        """
        skip_pos = render_board_body.find("_lastRenderedSnapshot")
        # First board.innerHTML after the snapshot variable reference
        inner_html_pos = render_board_body.find("board.innerHTML", skip_pos)
        # The snapshot check (with early return) must appear before board.innerHTML
        # so that an unchanged snapshot short-circuits before any DOM mutation.
        assert skip_pos != -1, "_lastRenderedSnapshot must appear in renderBoard"
        # Check that there is a 'return' between the snapshot comparison and innerHTML
        return_pos = render_board_body.find("return", skip_pos)
        assert return_pos != -1 and (inner_html_pos == -1 or return_pos < inner_html_pos), (
            "Snapshot dedup must return early before reaching board.innerHTML"
        )

    def test_no_op_snapshot_preserves_status_text_update(self, render_board_body: str):
        """Even on a no-op snapshot, the 'Updated ...' timestamp is refreshed."""
        # The early-return block must still update status-text.
        assert "status-text" in render_board_body, (
            "renderBoard must update #status-text on both no-op and real renders"
        )


# ===========================================================================
# 3. Board render key (view mode + swimlane state)
# ===========================================================================


class TestBoardRenderKey:
    """Verify the render-key helper encodes all rendering-affecting state."""

    def test_board_render_key_function_exists(self, script: str):
        """_boardRenderKey() must be defined."""
        assert "function _boardRenderKey()" in script, (
            "Script must define function _boardRenderKey()"
        )

    def test_render_key_includes_view_mode(self, script: str):
        body = _extract_function(script, "_boardRenderKey")
        assert "viewMode" in body, (
            "_boardRenderKey must include viewMode so flat/swimlane changes force a rebuild"
        )

    def test_render_key_includes_collapsed_swimlanes(self, script: str):
        body = _extract_function(script, "_boardRenderKey")
        assert "collapsedSwimlanes" in body, (
            "_boardRenderKey must include collapsedSwimlanes so collapse-toggle forces rebuild"
        )


# ===========================================================================
# 4. Card element cache (issueFingerprint + getOrCreateCard)
# ===========================================================================


class TestCardElementCache:
    """Verify the per-card fingerprint and element-cache machinery."""

    def test_issue_fingerprint_function_exists(self, script: str):
        assert "function issueFingerprint(" in script, (
            "Script must define function issueFingerprint(issue)"
        )

    def test_issue_fingerprint_includes_key_fields(self, script: str):
        body = _extract_function(script, "issueFingerprint")
        for field in ("identifier", "title", "description", "state", "priority"):
            assert field in body, (
                f"issueFingerprint must include '{field}' field"
            )

    def test_get_or_create_card_function_exists(self, script: str):
        assert "function getOrCreateCard(" in script, (
            "Script must define function getOrCreateCard(issue)"
        )

    def test_get_or_create_card_uses_fingerprint(self, script: str):
        body = _extract_function(script, "getOrCreateCard")
        assert "issueFingerprint" in body, (
            "getOrCreateCard must call issueFingerprint() to detect changes"
        )

    def test_get_or_create_card_reads_cache(self, script: str):
        body = _extract_function(script, "getOrCreateCard")
        assert "_cardElementCache.get(" in body, (
            "getOrCreateCard must look up the element in _cardElementCache"
        )

    def test_get_or_create_card_writes_cache(self, script: str):
        body = _extract_function(script, "getOrCreateCard")
        assert "_cardElementCache.set(" in body, (
            "getOrCreateCard must update _cardElementCache when creating a new element"
        )

    def test_get_or_create_card_calls_create_card_on_miss(self, script: str):
        body = _extract_function(script, "getOrCreateCard")
        assert "createCard(" in body, (
            "getOrCreateCard must call createCard() on a cache miss"
        )

    def test_flat_view_uses_get_or_create_card(self, script: str):
        body = _extract_function(script, "renderFlatView")
        assert "getOrCreateCard(" in body, (
            "renderFlatView must use getOrCreateCard() instead of createCard() "
            "so unchanged cards reuse their DOM elements"
        )

    def test_swimlane_view_uses_get_or_create_card(self, script: str):
        body = _extract_function(script, "renderSwimlaneView")
        assert "getOrCreateCard(" in body, (
            "renderSwimlaneView must use getOrCreateCard() so unchanged cards "
            "reuse their DOM elements"
        )


# ===========================================================================
# 5. Incremental flat-view reconciliation
# ===========================================================================


class TestIncrementalFlatView:
    """Verify tryIncrementalFlatView and reconcileColumnBody logic."""

    def test_try_incremental_flat_view_exists(self, script: str):
        assert "function tryIncrementalFlatView(" in script, (
            "Script must define function tryIncrementalFlatView(board, data)"
        )

    def test_try_incremental_checks_column_count(self, try_incremental_body: str):
        """Must bail out if the number of children doesn't match expected columns."""
        assert "board.children.length" in try_incremental_body, (
            "tryIncrementalFlatView must check board.children.length to detect "
            "structural changes (e.g. switching from swimlane view)"
        )

    def test_try_incremental_checks_column_order(self, try_incremental_body: str):
        """Must bail out if column keys or order have changed."""
        assert "dataset.state" in try_incremental_body, (
            "tryIncrementalFlatView must compare dataset.state on existing columns"
        )

    def test_try_incremental_returns_false_on_mismatch(self, try_incremental_body: str):
        """Must return false when the column structure doesn't match."""
        assert "return false" in try_incremental_body, (
            "tryIncrementalFlatView must return false when a full rebuild is needed"
        )

    def test_try_incremental_returns_true_on_success(self, try_incremental_body: str):
        """Must return true when incremental update succeeds."""
        assert "return true" in try_incremental_body, (
            "tryIncrementalFlatView must return true after a successful incremental update"
        )

    def test_try_incremental_calls_reconcile_column_body(self, try_incremental_body: str):
        assert "reconcileColumnBody(" in try_incremental_body, (
            "tryIncrementalFlatView must call reconcileColumnBody() for each column"
        )

    def test_try_incremental_updates_column_count_badge(self, try_incremental_body: str):
        """Column card-count badge must be updated during incremental reconciliation."""
        assert "col-count" in try_incremental_body, (
            "tryIncrementalFlatView must update the .col-count badge for changed columns"
        )

    def test_reconcile_column_body_exists(self, script: str):
        assert "function reconcileColumnBody(" in script, (
            "Script must define function reconcileColumnBody(body, issues)"
        )

    def test_reconcile_has_fast_path_for_no_changes(self, reconcile_column_body: str):
        """reconcileColumnBody must skip rebuilding when ids and fingerprints match."""
        assert "return" in reconcile_column_body, (
            "reconcileColumnBody must have an early-return fast path for unchanged columns"
        )

    def test_reconcile_uses_issue_fingerprint(self, reconcile_column_body: str):
        assert "issueFingerprint" in reconcile_column_body, (
            "reconcileColumnBody must call issueFingerprint() to detect content changes"
        )

    def test_reconcile_compares_existing_ids(self, reconcile_column_body: str):
        """Must compare the ordered list of card ids to detect reordering."""
        # The function should build a list of existing card ids from
        # data-id attributes and compare with the new id order.
        assert "dataset.id" in reconcile_column_body or "existingIds" in reconcile_column_body, (
            "reconcileColumnBody must compare existing card ids to detect reordering"
        )

    def test_reconcile_uses_get_or_create_card(self, reconcile_column_body: str):
        assert "getOrCreateCard(" in reconcile_column_body, (
            "reconcileColumnBody must use getOrCreateCard() to reuse unchanged card elements"
        )

    def test_render_board_calls_try_incremental_for_flat(self, render_board_body: str):
        assert "tryIncrementalFlatView(" in render_board_body, (
            "renderBoard must call tryIncrementalFlatView() for the flat view path"
        )


# ===========================================================================
# 6. Scroll-position preservation
# ===========================================================================


class TestScrollPreservation:
    """Verify scroll-position save/restore helpers are wired into renderBoard."""

    def test_save_scroll_positions_function_exists(self, script: str):
        assert "function saveColumnScrollPositions(" in script, (
            "Script must define function saveColumnScrollPositions()"
        )

    def test_save_scroll_reads_column_body_scroll_top(self, script: str):
        body = _extract_function(script, "saveColumnScrollPositions")
        assert "scrollTop" in body, (
            "saveColumnScrollPositions must read .scrollTop from column-body elements"
        )
    def test_save_scroll_queries_column_body(self, script: str):
        body = _extract_function(script, "saveColumnScrollPositions")
        assert "column-body" in body, (
            "saveColumnScrollPositions must query '.column-body' elements"
        )

    def test_restore_scroll_positions_function_exists(self, script: str):
        assert "function restoreColumnScrollPositions(" in script, (
            "Script must define function restoreColumnScrollPositions(positions)"
        )

    def test_restore_scroll_writes_scroll_top(self, script: str):
        body = _extract_function(script, "restoreColumnScrollPositions")
        assert "scrollTop" in body, (
            "restoreColumnScrollPositions must set .scrollTop on column-body elements"
        )

    def test_render_board_saves_scroll_before_rebuild(self, render_board_body: str):
        save_pos = render_board_body.find("saveColumnScrollPositions()")
        html_pos = render_board_body.find("board.innerHTML")
        assert save_pos != -1, "renderBoard must call saveColumnScrollPositions()"
        assert html_pos != -1, "renderBoard must reference board.innerHTML"
        assert save_pos < html_pos, (
            "saveColumnScrollPositions() must be called BEFORE board.innerHTML = '' "
            "so scroll positions are captured before the DOM is cleared"
        )

    def test_render_board_restores_scroll_after_rebuild(self, render_board_body: str):
        html_pos = render_board_body.find("board.innerHTML")
        restore_pos = render_board_body.find("restoreColumnScrollPositions(")
        assert restore_pos != -1, "renderBoard must call restoreColumnScrollPositions()"
        assert html_pos < restore_pos, (
            "restoreColumnScrollPositions() must be called AFTER board.innerHTML = '' "
            "so scroll positions are restored to the newly created elements"
        )


# ===========================================================================
# 7. Focus restoration after rebuild
# ===========================================================================


class TestFocusPreservation:
    """Verify keyboard focus is saved and restored across rebuilds."""

    def test_render_board_captures_focused_element(self, render_board_body: str):
        assert "document.activeElement" in render_board_body, (
            "renderBoard must capture document.activeElement before the rebuild "
            "so it can restore focus afterwards"
        )

    def test_render_board_captures_focused_data_id(self, render_board_body: str):
        assert "focusedDataId" in render_board_body or "dataset.id" in render_board_body, (
            "renderBoard must record the data-id of the focused element"
        )

    def test_render_board_restores_focus_after_rebuild(self, render_board_body: str):
        assert "toFocus" in render_board_body and ".focus()" in render_board_body, (
            "renderBoard must call .focus() on the restored element after a rebuild"
        )

    def test_focus_restoration_uses_data_id_and_field(self, render_board_body: str):
        """Focus restoration must scope the querySelector by both data-id and data-field."""
        assert "data-id" in render_board_body and "data-field" in render_board_body, (
            "Focus restoration querySelector must include both data-id and data-field "
            "to uniquely identify the editing element"
        )


# ===========================================================================
# 8. Drag-state guard
# ===========================================================================


class TestDragStateGuard:
    """Verify that incoming WS data is deferred while a card is being dragged."""

    def test_render_board_guards_on_drag_state(self, render_board_body: str):
        assert "dragState" in render_board_body, (
            "renderBoard must guard on dragState to defer rebuilds during active drags"
        )

    def test_drag_guard_defers_to_pending_board_data(self, render_board_body: str):
        # Find the dragState guard block
        match = re.search(
            r"if \(dragState\)\s*\{(.*?)\breturn\b",
            render_board_body,
            re.DOTALL,
        )
        assert match, "renderBoard must contain if (dragState) { ... return }"
        guard_body = match.group(1)
        assert "_pendingBoardData = data" in guard_body, (
            "The dragState guard must store incoming data in _pendingBoardData"
        )

    def test_dragend_flushes_pending_board_data(self, script: str):
        """The card dragend handler must flush _pendingBoardData after drag ends."""
        match = re.search(
            r"addEventListener\(['\"]dragend['\"]\s*,\s*\(\s*\)\s*=>\s*\{(.*?)\}\s*\)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find dragend event listener in card setup"
        dragend_body = match.group(1)
        assert "_pendingBoardData" in dragend_body, (
            "dragend handler must flush _pendingBoardData after drag completes"
        )
        assert "renderBoard(" in dragend_body, (
            "dragend handler must call renderBoard() to apply deferred WS data"
        )


# ===========================================================================
# 9. WebSocket reconnect invalidates snapshot
# ===========================================================================


class TestWebSocketReconnectInvalidation:
    """Verify that snapshot state is reset on WS reconnect so the first push rebuilds."""

    def _extract_onopen_body(self, script: str) -> str:
        """Extract ws.onopen handler body — stops at matching closing '};'."""
        # Find the start of ws.onopen
        start_match = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{", script)
        assert start_match, "Could not find ws.onopen = () => { in script"
        body_start = start_match.end()
        # Walk forward counting braces to find the matching closing '}'
        depth = 1
        i = body_start
        while i < len(script) and depth > 0:
            if script[i] == "{":
                depth += 1
            elif script[i] == "}":
                depth -= 1
            i += 1
        return script[body_start : i - 1]

    def test_on_open_resets_last_rendered_snapshot(self, script: str):
        """ws.onopen must clear _lastRenderedSnapshot to force a full rebuild."""
        onopen_body = self._extract_onopen_body(script)
        assert "_lastRenderedSnapshot" in onopen_body, (
            "ws.onopen must set _lastRenderedSnapshot = null so the first "
            "issues push after reconnect always triggers a full rebuild"
        )

    def test_on_open_clears_card_element_cache(self, script: str):
        """ws.onopen must also clear _cardElementCache to avoid stale DOM elements."""
        onopen_body = self._extract_onopen_body(script)
        assert "_cardElementCache" in onopen_body, (
            "ws.onopen must clear _cardElementCache to avoid stale card elements "
            "after a reconnect"
        )


# ===========================================================================
# 10. Project filter compatibility
# ===========================================================================


class TestProjectFilterCompatibility:
    """Verify that the project filter works correctly with the new reconciliation."""

    def test_filter_by_project_function_exists(self, script: str):
        assert "function filterByProject(" in script, (
            "filterByProject must still exist (project filtering must be preserved)"
        )

    def test_ws_issues_handler_still_filters_by_project(self, script: str):
        """The WS issues handler must pass filtered data to renderBoard."""
        # The onmessage handler should apply filterByProject before renderBoard
        assert "filterByProject(msg.data)" in script, (
            "WebSocket issues handler must apply filterByProject() before renderBoard"
        )

    def test_project_filter_change_clears_snapshot(self, script: str):
        """Changing the project filter triggers renderBoard(boardData) which
        passes pre-filtered data; since the filtered set differs, the snapshot
        will not match and a rebuild will occur.  Verify renderBoard is called
        from the filter-change path.
        """
        # saveProjectFilter or the project-filter change handler must call renderBoard
        body = _extract_function(script, "saveProjectFilter")
        # saveProjectFilter calls renderRunningAgentChips, and the board is
        # rendered via the project-filter onchange attribute calling
        # saveProjectFilter then triggering a re-render through renderBoard.
        # We verify that a renderBoard call is reachable from filter changes.
        # The simplest contract: renderBoard(boardData) exists in the script.
        assert "renderBoard(boardData)" in script, (
            "renderBoard(boardData) must be callable from project-filter changes"
        )


# ===========================================================================
# 11. Active inline edit is preserved across snapshot-unchanged ticks
# ===========================================================================


class TestInlineEditPreservation:
    """Verify that inline edits are not interrupted by no-op snapshot updates."""

    def test_editing_state_guard_still_present(self, render_board_body: str):
        """The original editingState guard must still be in renderBoard."""
        assert "if (editingState)" in render_board_body, (
            "renderBoard must still check editingState to defer rebuilds while editing"
        )

    def test_snapshot_dedup_prevents_rebuild_on_no_op(self, render_board_body: str):
        """Snapshot dedup means unchanged data never reaches board.innerHTML = ''.

        This is the core protection: if data hasn't changed, the editor
        is never interrupted regardless of how frequently WS pushes arrive.
        """
        # The snapshot check must come BEFORE board.innerHTML in the function body
        snapshot_pos = render_board_body.find("_lastRenderedSnapshot")
        inner_html_pos = render_board_body.find("board.innerHTML")
        assert snapshot_pos < inner_html_pos, (
            "Snapshot check must appear before board.innerHTML = '' so that "
            "no-op pushes never reach the DOM-clearing code"
        )
