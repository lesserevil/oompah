"""Tests for column heading behaviour when switching between flat and swimlane views.

In flat view:  4 columns each have a `.column-header` showing "Backlog / Open /
               In Progress / Closed" at the top of the column.

In swimlane view (the broken behaviour): each swimlane sub-column ALSO rendered
               a `.column-header` which caused the same 4 labels to appear inside
               every single swimlane row — visually cluttered and confusing.

Fix:
  - Add a single `.swimlane-board-header` row at the top of the board that shows
    the 4 column labels once.
  - Hide per-swimlane `.column-header` elements via CSS so the labels do not
    repeat inside every swimlane.

See issue: oompah-8h6
"""

import os
import re

import pytest


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "No <script> block found in dashboard.html"
    return max(matches, key=len)


@pytest.fixture(scope="module")
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


# ---------------------------------------------------------------------------
# CSS: swimlane-board-header class
# ---------------------------------------------------------------------------

class TestSwimlaneboardHeaderCSS:
    """Verify the .swimlane-board-header CSS class exists and is styled correctly."""

    def test_swimlane_board_header_css_class_exists(self, html):
        """.swimlane-board-header CSS rule must be present in the stylesheet."""
        assert ".swimlane-board-header" in html, (
            ".swimlane-board-header CSS class must be defined in dashboard.html"
        )

    def test_swimlane_board_header_is_flex(self, html):
        """The .swimlane-board-header must use display:flex for column alignment."""
        match = re.search(r"\.swimlane-board-header\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .swimlane-board-header CSS rule"
        block = match.group(1)
        assert "display" in block and "flex" in block, (
            ".swimlane-board-header must set display:flex"
        )

    def test_swimlane_board_header_col_heading_class_exists(self, html):
        """The .col-heading CSS class for items inside .swimlane-board-header must exist."""
        assert ".swimlane-board-header .col-heading" in html or ".col-heading" in html, (
            ".col-heading class must be defined (used inside .swimlane-board-header)"
        )

    def test_col_heading_has_font_styling(self, html):
        """.col-heading must have font-size and/or font-weight for readable labels."""
        # Find the .col-heading rule (may be nested under .swimlane-board-header)
        match = re.search(
            r"(?:\.swimlane-board-header\s+\.col-heading|\.col-heading)\s*\{([^}]+)\}",
            html,
            re.DOTALL,
        )
        assert match, "Could not find .col-heading CSS rule"
        block = match.group(1)
        assert "font-size" in block or "font-weight" in block, (
            ".col-heading must have font-size or font-weight styling"
        )


# ---------------------------------------------------------------------------
# CSS: per-swimlane column-headers are hidden
# ---------------------------------------------------------------------------

class TestSwimlaneColumnHeaderHiddenCSS:
    """Verify that .column-header inside .swimlane-columns is hidden via CSS."""

    def test_swimlane_column_header_hidden(self, html):
        """.swimlane-columns .column-header must have display:none."""
        match = re.search(
            r"\.swimlane-columns\s+\.column-header\s*\{([^}]+)\}",
            html,
            re.DOTALL,
        )
        assert match, (
            "CSS rule '.swimlane-columns .column-header' must exist to hide "
            "per-swimlane column headers"
        )
        block = match.group(1)
        assert "display" in block and "none" in block, (
            ".swimlane-columns .column-header must set display:none"
        )


# ---------------------------------------------------------------------------
# JS: renderSwimlaneView creates the board-header element
# ---------------------------------------------------------------------------

class TestRenderSwimlaneViewBoardHeader:
    """Verify that renderSwimlaneView() creates the .swimlane-board-header element."""

    def _get_render_swimlane_body(self, script: str) -> str:
        match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderSwimlaneView function"
        return match.group(1)

    def test_board_header_element_created(self, script):
        """renderSwimlaneView must create a .swimlane-board-header element."""
        body = self._get_render_swimlane_body(script)
        assert "swimlane-board-header" in body, (
            "renderSwimlaneView must create a div with class 'swimlane-board-header'"
        )

    def test_board_header_uses_column_labels(self, script):
        """renderSwimlaneView must populate the board-header with COLUMN_LABELS."""
        body = self._get_render_swimlane_body(script)
        assert "COLUMN_LABELS" in body, (
            "renderSwimlaneView must use COLUMN_LABELS to populate the board-header headings"
        )

    def test_board_header_iterates_columns(self, script):
        """renderSwimlaneView must iterate over COLUMNS to build the board-header."""
        body = self._get_render_swimlane_body(script)
        # The header-building code should reference the COLUMNS constant
        assert "COLUMNS" in body, (
            "renderSwimlaneView must iterate over COLUMNS array when building board-header"
        )

    def test_board_header_appended_to_board(self, script):
        """The .swimlane-board-header element must be appended to the board."""
        body = self._get_render_swimlane_body(script)
        assert "board.appendChild" in body, (
            "renderSwimlaneView must call board.appendChild to add the board-header"
        )

    def test_board_header_added_before_swimlanes(self, script):
        """The board-header must be added BEFORE the swimlane rows (at the top)."""
        body = self._get_render_swimlane_body(script)
        header_pos = body.find("swimlane-board-header")
        first_epic_pos = body.find("for (const epic of epics)")
        assert header_pos != -1, "swimlane-board-header must be present"
        assert first_epic_pos != -1, "Epic iteration loop must be present"
        assert header_pos < first_epic_pos, (
            "swimlane-board-header must be created and appended BEFORE the epic swimlane loop"
        )


# ---------------------------------------------------------------------------
# JS: flat view still has column headers
# ---------------------------------------------------------------------------

class TestFlatViewColumnHeadersPresent:
    """Verify that renderFlatView() still creates column headers for each column."""

    def _get_render_flat_body(self, script: str) -> str:
        match = re.search(
            r"function renderFlatView\(.*?\)\s*\{(.*?)(?=\nfunction |\nasync function )",
            script,
            re.DOTALL,
        )
        assert match, "Could not find renderFlatView function"
        return match.group(1)

    def test_flat_view_still_has_column_header(self, script):
        """renderFlatView must still render .column-header for each column."""
        body = self._get_render_flat_body(script)
        assert "column-header" in body, (
            "renderFlatView must still create .column-header elements for each column"
        )

    def test_flat_view_column_header_shows_column_labels(self, script):
        """renderFlatView column headers must display the COLUMN_LABELS text."""
        body = self._get_render_flat_body(script)
        assert "COLUMN_LABELS[col]" in body, (
            "renderFlatView must use COLUMN_LABELS[col] to label each column header"
        )

    def test_flat_view_column_header_shows_count(self, script):
        """renderFlatView column headers must show the issue count."""
        body = self._get_render_flat_body(script)
        assert "col-count" in body, (
            "renderFlatView must include a .col-count element in each column header"
        )

    def test_flat_view_no_swimlane_board_header(self, script):
        """renderFlatView must NOT create a .swimlane-board-header (that's only for swimlane view)."""
        body = self._get_render_flat_body(script)
        assert "swimlane-board-header" not in body, (
            "renderFlatView must not create a swimlane-board-header — that belongs only in swimlane view"
        )


# ---------------------------------------------------------------------------
# JS: setViewMode triggers renderBoard
# ---------------------------------------------------------------------------

class TestSetViewModeCallsRenderBoard:
    """Verify that setViewMode() updates the mode and calls renderBoard."""

    def _get_set_view_mode_body(self, script: str) -> str:
        match = re.search(
            r"function setViewMode\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert match, "Could not find setViewMode function"
        return match.group(1)

    def test_setViewMode_updates_viewMode_variable(self, script):
        """setViewMode() must update the global viewMode variable."""
        body = self._get_set_view_mode_body(script)
        assert "viewMode = mode" in body, (
            "setViewMode must assign the new mode to the viewMode variable"
        )

    def test_setViewMode_calls_renderBoard(self, script):
        """setViewMode() must call renderBoard to re-render the board."""
        body = self._get_set_view_mode_body(script)
        assert "renderBoard(" in body, (
            "setViewMode must call renderBoard() to re-render the board after mode change"
        )

    def test_setViewMode_passes_boardData_to_renderBoard(self, script):
        """setViewMode() must pass boardData to renderBoard."""
        body = self._get_set_view_mode_body(script)
        assert "renderBoard(boardData)" in body, (
            "setViewMode must call renderBoard(boardData) to re-render with current data"
        )

    def test_setViewMode_toggles_flat_button(self, script):
        """setViewMode() must toggle the 'active' class on the flat button."""
        body = self._get_set_view_mode_body(script)
        assert "btn-flat" in body, (
            "setViewMode must update the btn-flat button active state"
        )

    def test_setViewMode_toggles_swimlane_button(self, script):
        """setViewMode() must toggle the 'active' class on the swimlane button."""
        body = self._get_set_view_mode_body(script)
        assert "btn-swimlane" in body, (
            "setViewMode must update the btn-swimlane button active state"
        )
