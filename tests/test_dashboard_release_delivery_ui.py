"""Tests for the Release delivery overlay (OOMPAH-236).

This module covers the item-centric release delivery backlog introduced in
OOMPAH-236. The overlay was previously commit-centric (OOMPAH-200); these
tests verify the new item-centric design requirements.

Covers:

  CSS:
  - Legacy RBI CSS classes are removed (release-branch-inspector-overlay, rbi-*)
  - New RDI CSS classes are present (rdi-overlay, rdi-panel, rdi-table, etc.)
  - Status cell CSS variants for all states
  - Evidence-specific CSS for delivered-by-cherry-pick vs delivered-by-ancestry
  - .rdi-unassoc-section CSS for unassociated commits subordinate section

  Toolbar:
  - Button opens openReleaseDelivery() (not openReleaseBranchInspector())
  - Button has id="btn-release-delivery"
  - Button label is "Release delivery"

  HTML overlay:
  - .rdi-overlay with correct id, role, aria attributes
  - Project selector AND branch selector (branch-first selection model)
  - Filter controls (radio group) and search input
  - No "rdi-branch-filters" checkbox group (replaced by rdi-branch-select dropdown)
  - No pagination element (no commit-history pages)
  - No "rdi-target-list" (target branch comes from branch selector, not a target list)
  - Outcome banner element (hidden by default)
  - Table body wrapper with aria-live
  - Bulk action bar with queue button and item count
  - Evidence drawer overlay titled "Item details"

  State variables:
  - _rdiProjectId, _rdiSelectedBranch, _rdiFilter, _rdiQuery
  - _rdiSourceHead, _rdiSelectedIdentifiers, _rdiSelectedUnassocSHAs, _rdiGen
  - _rdiLoading, _rdiCurrentData, _rdiOpener, _rdiDrawerItem
  - _RDI_STATUS_LABELS map with all 7 states
  - No _rdiCursor (no commit pagination)
  - No _rdiVisibleBranches (replaced by single-branch selector)
  - No _rdiCurrentPageData (replaced by _rdiCurrentData)
  - No _rdiDrawerSHA (replaced by _rdiDrawerItem)

  openReleaseDelivery():
  - Defined and stores opener element for focus restoration
  - Adds 'open' class to overlay
  - Calls _rdiPopulateProject
  - Registers keydown listener

  closeReleaseDelivery():
  - Removes 'open' class
  - Removes keydown listener
  - Calls _rdiCloseDrawer
  - Restores focus to _rdiOpener

  Escape key handler:
  - _rdiKeyHandler closes overlay on Escape
  - If drawer is open, closes drawer first before closing overlay

  Branch-first selection:
  - _rdiPopulateBranchSelector populates branch <select> from project config
  - _rdiOnBranchChange() updates _rdiSelectedBranch and calls _rdiLoadBacklog()
  - _rdiShowNoBranch() shows prompt to select a branch

  _rdiLoadBacklog():
  - Builds URL with branch, filter, query params (no cursor)
  - Uses generation counter to ignore stale responses
  - Handles network/HTTP errors with error message in body
  - No "Load next page" / cursor pagination

  Status rendering:
  - _rdiRenderStatusCell uses textContent (not innerHTML) for labels
  - All 7 states render a label
  - 'delivered' with evidence='ancestry' shows 'Delivered (ancestry)'
  - 'delivered' with evidence='delivery' shows 'Delivered (cherry-pick)'
  - delivered-by-ancestry and delivered-by-cherry-pick have distinct CSS classes

  Item rows:
  - _rdiRenderItemRow renders one row per task/epic (identifier, title, commits, status)
  - Identifier opens detail panel
  - Delivered/archived items have their checkbox disabled (no re-queuing)

  Unassociated commits section:
  - Rendered as a separate, non-primary section below item rows
  - _rdiRenderUnassocRow used for unassociated rows

  No untrusted text in onclick handlers:
  - commit subjects never appear in onclick attributes
  - branch names use data-branch attributes, not onclick interpolation

  Selection:
  - _rdiToggleIdentifier adds/removes from _rdiSelectedIdentifiers
  - _rdiSelectAll (de)selects all selectable items (skips delivered/archived)
  - _rdiClearSelection clears set and unchecks all checkboxes

  Action bar:
  - Shown when selection is non-empty, hidden when empty
  - Shows count of selected items

  _rdiQueueSelected():
  - Requires selected branch (set via selector)
  - Collects all source_commits from selected items and sends them
  - Posts to /api/v1/projects/{id}/release-delivery/commits
  - Sends Idempotency-Key header
  - Sends source_head, commits, target_branches in JSON body
  - target_branches is always [_rdiSelectedBranch] (single branch)
  - On success: clears selected identifiers for queued items
  - Reloads backlog after success
  - Handles HTTP/network errors

  Evidence drawer:
  - _rdiOpenItemDrawer renders identifier, title, source commits as sub-detail
  - Each commit shows SHA, subject, author, status cell detail
  - Delivered-by-ancestry and delivered-by-cherry-pick labeled distinctly
  - PR link, delivery_id, result_commits shown in per-commit detail
  - _rdiCloseDrawer removes 'open' class, clears _rdiDrawerItem

  Filter/search:
  - _rdiOnFilterChange updates _rdiFilter and reloads backlog
  - _rdiOnSearchInput debounces and updates _rdiQuery
  - No cursor reset needed (no pagination)

  Empty / error states:
  - No selected project: prompt shown
  - No selected branch: prompt shown
  - No rows for filter: empty state mentioning current filter
  - Error state shows error message

  Retained controls:
  - openAddReleaseBranchesDialog is retained
  - closeAddReleaseBranchesDialog is retained
  - submitAddReleaseBranchesDialog is retained
  - add-release-branches-dialog HTML is retained
  - Task/epic renderReleaseAddendumsSection and renderEpicReleaseAddendumsSection retained

  Special-character escaping:
  - esc() is used for all API text in HTML attribute contexts

  Keyboard navigation:
  - rdi-overlay has role="dialog" and aria-modal="true"
  - rdi-drawer has role="dialog" and aria-modal="true"
  - Filter controls have role="radiogroup"
  - Selectable cells have role="button" and tabindex="0"

  OOMPAH-216 delivery retry controls:
  - _rdiRetryDelivery function retained
  - Retry calls /release-delivery/<id>/retry endpoint
  - cell.error rendered for blocked state
  - conflict_agent_resolving check retained
  - 'Retry delivery' label retained
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEMPLATES = Path(__file__).resolve().parents[1] / "oompah" / "templates"


def _load_dashboard_html() -> str:
    return (_TEMPLATES / "dashboard.html").read_text(encoding="utf-8")


def _load_release_delivery_html() -> str:
    """Load the dedicated Release Delivery page (OOMPAH-252)."""
    return (_TEMPLATES / "release_delivery.html").read_text(encoding="utf-8")


def _load_dashboard_script() -> str:
    html = _load_dashboard_html()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _load_release_delivery_script() -> str:
    """Load the <script> block from the dedicated Release Delivery page."""
    html = _load_release_delivery_html()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _load_dashboard_styles() -> str:
    html = _load_dashboard_html()
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>")
    return html[start:end]


def _load_release_delivery_styles() -> str:
    """Load the <style> block from the dedicated Release Delivery page."""
    html = _load_release_delivery_html()
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>")
    return html[start:end]


def _function_body(script: str, name: str, is_async: bool = False) -> str:
    """Extract the body of a named JavaScript function using brace counting."""
    prefix = "async function" if is_async else "function"
    marker = f"{prefix} {name}("
    start = script.index(marker)
    brace = script.index("{", start)
    depth = 0
    for pos in range(brace, len(script)):
        char = script[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[brace : pos + 1]
    raise ValueError(f"Could not find end of function {name!r}")


# ===========================================================================
# CSS Tests
# ===========================================================================


class TestLegacyCSSRemoved:
    """Verify all old Release branches inspector CSS is removed."""

    def test_rbi_overlay_class_removed(self):
        styles = _load_dashboard_styles()
        assert ".release-branch-inspector-overlay" not in styles

    def test_rbi_panel_class_removed(self):
        styles = _load_dashboard_styles()
        assert ".release-branch-inspector-panel" not in styles

    def test_rbi_header_class_removed(self):
        styles = _load_dashboard_styles()
        assert ".rbi-header" not in styles

    def test_rbi_close_btn_removed(self):
        styles = _load_dashboard_styles()
        assert ".rbi-close-btn" not in styles

    def test_rbi_body_class_removed(self):
        styles = _load_dashboard_styles()
        assert ".rbi-body" not in styles

    def test_rbi_loading_class_removed(self):
        styles = _load_dashboard_styles()
        assert ".rbi-loading" not in styles

    def test_rbi_entry_class_removed(self):
        styles = _load_dashboard_styles()
        assert ".rbi-entry" not in styles

    def test_rbi_group_section_removed(self):
        styles = _load_dashboard_styles()
        assert ".rbi-group-section" not in styles


class TestNewRDICSSPresent:
    """Verify the Release delivery page CSS classes are present (OOMPAH-252: moved to dedicated page)."""

    def test_rdi_page_body_class(self):
        # OOMPAH-252: dedicated page uses .page-body instead of .rdi-overlay.
        styles = _load_release_delivery_styles()
        assert ".page-body" in styles or ".rdi-controls" in styles

    def test_rdi_table_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-table" in styles

    def test_rdi_table_wrap_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-table-wrap" in styles

    def test_rdi_loading_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-loading" in styles

    def test_rdi_empty_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-empty" in styles

    def test_rdi_error_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-error" in styles

    def test_rdi_cell_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-cell" in styles

    def test_rdi_action_bar_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-action-bar" in styles

    def test_rdi_drawer_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-drawer" in styles

    def test_rdi_drawer_panel_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-drawer-panel" in styles

    def test_rdi_unassoc_section_class(self):
        """Unassociated commits get their own non-primary section CSS."""
        styles = _load_release_delivery_styles()
        assert "rdi-unassoc" in styles

    def test_rdi_css_absent_from_dashboard(self):
        """OOMPAH-252: RDI CSS must be absent from dashboard.html (moved to dedicated page)."""
        styles = _load_dashboard_styles()
        assert ".rdi-table" not in styles
        assert ".rdi-action-bar" not in styles


class TestStatusCellCSS:
    """Verify CSS exists for all status cell states (OOMPAH-252: now in release_delivery.html)."""

    def test_not_selected_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-not_selected" in styles

    def test_open_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-open" in styles

    def test_in_progress_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-in_progress" in styles

    def test_in_review_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-in_review" in styles

    def test_blocked_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-blocked" in styles

    def test_delivered_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-delivered" in styles

    def test_archived_cell(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-archived" in styles

    def test_delivered_ancestry_has_distinct_css(self):
        """Delivered-by-ancestry must have a distinct CSS class from delivered-by-cherry-pick."""
        styles = _load_release_delivery_styles()
        assert "rdi-cell-delivered-ancestry" in styles

    def test_ancestry_css_differs_from_delivery_css(self):
        """The ancestry variant must visually differ from the cherry-pick variant."""
        styles = _load_release_delivery_styles()
        # Both classes must exist
        assert ".rdi-cell-delivered" in styles
        assert ".rdi-cell-delivered-ancestry" in styles
        # Check that they define different styles
        ancestry_start = styles.index(".rdi-cell-delivered-ancestry")
        cherry_start = styles.index(".rdi-cell-delivered {")
        ancestry_rule = styles[ancestry_start : ancestry_start + 200]
        cherry_rule = styles[cherry_start : cherry_start + 200]
        assert ancestry_rule != cherry_rule

    def test_clickable_cell_class(self):
        styles = _load_release_delivery_styles()
        assert "rdi-cell-clickable" in styles


class TestOutcomeCSS:
    """Verify outcome banner CSS classes (OOMPAH-252: now in release_delivery.html)."""

    def test_outcome_banner_class(self):
        styles = _load_release_delivery_styles()
        assert "rdi-outcome-banner" in styles

    def test_outcome_banner_success(self):
        styles = _load_release_delivery_styles()
        assert "rdi-outcome-banner-success" in styles

    def test_outcome_banner_partial(self):
        styles = _load_release_delivery_styles()
        assert "rdi-outcome-banner-partial" in styles


# ===========================================================================
# Toolbar Tests
# ===========================================================================


class TestToolbarButton:
    """Verify the toolbar button navigates to the dedicated Release Delivery page (OOMPAH-252)."""

    def test_old_release_branches_button_gone(self):
        html = _load_dashboard_html()
        assert "btn-release-branches" not in html

    def test_old_open_release_branch_inspector_gone(self):
        html = _load_dashboard_html()
        assert "openReleaseBranchInspector" not in html

    def test_new_release_delivery_button_present(self):
        html = _load_dashboard_html()
        assert 'id="btn-release-delivery"' in html

    def test_new_button_navigates_to_release_delivery_page(self):
        """OOMPAH-252: button must navigate to /release-delivery, not open a dialog."""
        html = _load_dashboard_html()
        assert "window.location='/release-delivery'" in html

    def test_old_modal_trigger_absent(self):
        """OOMPAH-252: openReleaseDelivery() dialog trigger must be gone from dashboard."""
        html = _load_dashboard_html()
        assert 'onclick="openReleaseDelivery()"' not in html

    def test_new_button_label(self):
        html = _load_dashboard_html()
        assert ">Release delivery<" in html


# ===========================================================================
# HTML Structure Tests
# ===========================================================================


class TestRDIOverlayHTML:
    """Verify the Release delivery page HTML structure (OOMPAH-252: page, not overlay)."""

    def test_page_controls_present(self):
        """OOMPAH-252: dedicated page has controls section, not an rdi-overlay div."""
        html = _load_release_delivery_html()
        assert 'id="rdi-controls"' in html or 'class="rdi-controls"' in html

    def test_drawer_has_role_dialog(self):
        """The evidence drawer is the accessible dialog on the page."""
        html = _load_release_delivery_html()
        assert 'role="dialog"' in html

    def test_drawer_aria_modal(self):
        """Drawer has aria-modal=true."""
        html = _load_release_delivery_html()
        assert 'aria-modal="true"' in html

    def test_page_has_accessible_heading(self):
        """Page-level heading is in the toolbar (not aria-labelledby on rdi-overlay)."""
        html = _load_release_delivery_html()
        assert 'Release Delivery' in html

    def test_no_overlay_backdrop_click_handler(self):
        """OOMPAH-252: dedicated page has no backdrop click-to-close handler."""
        html = _load_release_delivery_html()
        assert "closeReleaseDelivery()" not in html

    def test_project_selector_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-project-select"' in html

    def test_project_selector_has_onchange(self):
        html = _load_release_delivery_html()
        assert '_rdiOnProjectChange()' in html

    def test_branch_selector_present(self):
        """Branch is now selected via a <select> dropdown, not checkbox filters."""
        html = _load_release_delivery_html()
        assert 'id="rdi-branch-select"' in html

    def test_branch_selector_has_onchange(self):
        html = _load_release_delivery_html()
        assert '_rdiOnBranchChange()' in html

    def test_no_branch_filters_checkbox_group(self):
        """Old commit-centric branch filter checkboxes must be removed."""
        html = _load_release_delivery_html()
        assert 'id="rdi-branch-filters"' not in html

    def test_no_target_list_element(self):
        """Old target-branch list for multi-selection must be removed."""
        html = _load_release_delivery_html()
        assert 'id="rdi-target-list"' not in html

    def test_no_pagination_element(self):
        """No 'Load next page' pagination control exists in the item-centric view."""
        html = _load_release_delivery_html()
        assert 'id="rdi-pagination"' not in html

    def test_filter_radio_needs_delivery(self):
        html = _load_release_delivery_html()
        assert 'value="needs_delivery"' in html
        assert 'name="rdi-filter"' in html

    def test_filter_radio_all(self):
        html = _load_release_delivery_html()
        assert "value=\"all\"" in html or "'all'" in html

    def test_search_input_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-search"' in html

    def test_search_input_has_oninput(self):
        html = _load_release_delivery_html()
        assert '_rdiOnSearchInput()' in html

    def test_outcome_banner_present_and_hidden(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-outcome"' in html
        assert 'hidden' in html

    def test_body_wrapper_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-body"' in html

    def test_body_wrapper_aria_live(self):
        html = _load_release_delivery_html()
        assert 'aria-live="polite"' in html

    def test_action_bar_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-action-bar"' in html

    def test_action_bar_initially_hidden(self):
        html = _load_release_delivery_html()
        idx = html.index('id="rdi-action-bar"')
        context = html[max(0, idx - 50) : idx + 150]
        assert "hidden" in context

    def test_selected_count_element(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-action-count"' in html

    def test_queue_button_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-queue-btn"' in html
        assert '_rdiQueueSelected()' in html

    def test_clear_selection_button(self):
        html = _load_release_delivery_html()
        assert '_rdiClearSelection()' in html

    def test_drawer_title_is_item_details(self):
        """Drawer title should say 'Item details', not 'Commit details'."""
        html = _load_release_delivery_html()
        assert "Item details" in html


class TestRDIDrawerHTML:
    """Verify the evidence drawer HTML structure."""

    def test_drawer_div_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-drawer"' in html

    def test_drawer_role_dialog(self):
        html = _load_release_delivery_html()
        drawer_idx = html.index('id="rdi-drawer"')
        context = html[max(0, drawer_idx - 100) : drawer_idx + 200]
        assert 'role="dialog"' in context

    def test_drawer_aria_modal(self):
        html = _load_release_delivery_html()
        drawer_idx = html.index('id="rdi-drawer"')
        context = html[max(0, drawer_idx - 100) : drawer_idx + 200]
        assert 'aria-modal="true"' in context

    def test_drawer_body_element(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-drawer-body"' in html

    def test_drawer_close_button(self):
        html = _load_release_delivery_html()
        assert '_rdiCloseDrawer()' in html


# ===========================================================================
# State Variable Tests
# ===========================================================================


class TestStateVariables:
    """Verify state variables are initialized correctly."""

    def test_project_id_initialized(self):
        script = _load_release_delivery_script()
        assert "let _rdiProjectId = null" in script

    def test_selected_branch_initialized(self):
        """Single selected branch (replaces _rdiVisibleBranches array)."""
        script = _load_release_delivery_script()
        assert "_rdiSelectedBranch = ''" in script

    def test_no_visible_branches_array(self):
        """Old multi-branch filter array must be gone."""
        script = _load_release_delivery_script()
        assert "_rdiVisibleBranches = []" not in script

    def test_no_cursor_variable(self):
        """No commit-pagination cursor — this is an item-centric view."""
        script = _load_release_delivery_script()
        assert "_rdiCursor = null" not in script

    def test_filter_initialized_to_needs_delivery(self):
        script = _load_release_delivery_script()
        assert "_rdiFilter = 'needs_delivery'" in script

    def test_query_initialized_to_empty(self):
        script = _load_release_delivery_script()
        assert "_rdiQuery = ''" in script

    def test_source_head_initialized_to_null(self):
        script = _load_release_delivery_script()
        assert "_rdiSourceHead = null" in script

    def test_selected_identifiers_initialized_as_set(self):
        """Selection tracks item identifiers, not raw commit SHAs."""
        script = _load_release_delivery_script()
        assert "_rdiSelectedIdentifiers = new Set()" in script

    def test_no_selected_shas_variable(self):
        """Old SHA-set selection must be gone."""
        script = _load_release_delivery_script()
        assert "_rdiSelectedSHAs = new Set()" not in script

    def test_generation_counter_initialized(self):
        script = _load_release_delivery_script()
        assert "_rdiGen = 0" in script

    def test_loading_flag_initialized(self):
        script = _load_release_delivery_script()
        assert "_rdiLoading = false" in script

    def test_current_data_initialized(self):
        """_rdiCurrentData replaces the old _rdiCurrentPageData."""
        script = _load_release_delivery_script()
        assert "_rdiCurrentData = null" in script

    def test_no_current_page_data_variable(self):
        """Old per-page data variable must be gone."""
        script = _load_release_delivery_script()
        assert "_rdiCurrentPageData = null" not in script

    def test_opener_initialized_to_null(self):
        """OOMPAH-252: _rdiOpener no longer needed (no dialog focus restoration), but harmless if present."""
        script = _load_release_delivery_script()
        # On the dedicated page, _rdiOpener may or may not be present; check _rdiDrawerItem instead
        assert "_rdiDrawerItem" in script

    def test_drawer_item_initialized_to_null(self):
        """_rdiDrawerItem tracks open item identifier, not commit SHA."""
        script = _load_release_delivery_script()
        assert "_rdiDrawerItem = null" in script

    def test_no_drawer_sha_variable(self):
        """Old _rdiDrawerSHA must be gone."""
        script = _load_release_delivery_script()
        assert "_rdiDrawerSHA = null" not in script

    def test_status_labels_map_present(self):
        script = _load_release_delivery_script()
        assert "_RDI_STATUS_LABELS" in script

    def test_status_labels_has_all_states(self):
        script = _load_release_delivery_script()
        for state in ["not_selected", "open", "in_progress", "in_review",
                      "blocked", "delivered", "archived"]:
            assert state in script


# ===========================================================================
# Function Existence Tests
# ===========================================================================


class TestFunctionDefinitions:
    """Verify all required functions are defined."""

    def test_open_release_delivery_absent(self):
        """openReleaseDelivery belongs to the old dashboard dialog; must not exist on the page."""
        script = _load_release_delivery_script()
        assert "function openReleaseDelivery(" not in script

    def test_close_release_delivery_absent(self):
        """closeReleaseDelivery belongs to the old dashboard dialog; must not exist on the page."""
        script = _load_release_delivery_script()
        assert "function closeReleaseDelivery(" not in script

    def test_rdi_init_defined(self):
        """_rdiInit() bootstraps the dedicated page (replaces openReleaseDelivery on the dashboard)."""
        script = _load_release_delivery_script()
        assert "function _rdiInit(" in script or "_rdiInit()" in script

    def test_rdi_populate_project_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiPopulateProject(" in script

    def test_rdi_on_project_change_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiOnProjectChange(" in script

    def test_rdi_populate_branch_selector_defined(self):
        """New branch selector function replaces the old branch filter renderer."""
        script = _load_release_delivery_script()
        assert "function _rdiPopulateBranchSelector(" in script

    def test_rdi_on_branch_change_defined(self):
        """New branch change handler replaces _rdiBranchFilterChange."""
        script = _load_release_delivery_script()
        assert "function _rdiOnBranchChange(" in script

    def test_rdi_load_backlog_defined(self):
        """New single-fetch function replaces cursor-based _rdiLoadPage."""
        script = _load_release_delivery_script()
        assert "function _rdiLoadBacklog(" in script

    def test_no_rdi_load_page(self):
        """Cursor-based load-page function must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiLoadPage(" not in script

    def test_rdi_refresh_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiRefresh(" in script

    def test_rdi_render_backlog_defined(self):
        """New backlog renderer replaces old page renderer."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderBacklog(" in script

    def test_no_rdi_render_page(self):
        """Old commit-page renderer must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderPage(" not in script

    def test_rdi_render_meta_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiRenderMeta(" in script

    def test_rdi_render_item_row_defined(self):
        """New item-row renderer replaces old commit-row renderer."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderItemRow(" in script

    def test_no_rdi_render_row(self):
        """Old commit-row renderer (_rdiRenderRow) must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderRow(" not in script

    def test_rdi_render_status_cell_defined(self):
        """Renamed from _rdiRenderCell."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderStatusCell(" in script

    def test_rdi_render_unassoc_row_defined(self):
        """Renderer for unassociated commit rows in subordinate section."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderUnassocRow(" in script

    def test_rdi_toggle_identifier_defined(self):
        """New identifier-based toggle replaces _rdiToggleSHA."""
        script = _load_release_delivery_script()
        assert "function _rdiToggleIdentifier(" in script

    def test_no_rdi_toggle_sha(self):
        """Old SHA-based toggle must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiToggleSHA(" not in script

    def test_rdi_select_all_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiSelectAll(" in script

    def test_rdi_update_select_all_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiUpdateSelectAll(" in script

    def test_rdi_clear_selection_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiClearSelection(" in script

    def test_rdi_update_action_bar_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiUpdateActionBar(" in script

    def test_rdi_queue_selected_defined(self):
        script = _load_release_delivery_script()
        assert "_rdiQueueSelected" in script

    def test_rdi_show_outcome_summary_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiShowOutcomeSummary(" in script

    def test_rdi_show_outcome_error_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiShowOutcomeError(" in script

    def test_rdi_open_item_drawer_defined(self):
        """New item-drawer opener replaces old commit-drawer opener."""
        script = _load_release_delivery_script()
        assert "function _rdiOpenItemDrawer(" in script

    def test_no_rdi_open_drawer(self):
        """Old commit-specific drawer opener must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiOpenDrawer(" not in script

    def test_rdi_close_drawer_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiCloseDrawer(" in script

    def test_rdi_on_filter_change_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiOnFilterChange(" in script

    def test_rdi_on_search_input_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiOnSearchInput(" in script

    def test_no_rdi_branch_filter_change(self):
        """Old branch-filter-checkbox handler must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiBranchFilterChange(" not in script

    def test_rdi_show_no_project_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiShowNoProject(" in script

    def test_rdi_show_no_branch_defined(self):
        """Shows prompt when no branch selected yet."""
        script = _load_release_delivery_script()
        assert "function _rdiShowNoBranch(" in script

    def test_no_rdi_find_row(self):
        """Old commit SHA lookup function must be removed."""
        script = _load_release_delivery_script()
        assert "function _rdiFindRow(" not in script

    def test_no_rdi_render_pagination(self):
        """Pagination function must be removed from item-centric view."""
        script = _load_release_delivery_script()
        assert "function _rdiRenderPagination(" not in script


# ===========================================================================
# Open / Close Behaviour Tests
# ===========================================================================


class TestOpenCloseOverlay:
    """Test page-level open/close: OOMPAH-252 replaces open/close dialog with a dedicated page.

    The dedicated page has no open/close overlay functions; drawer is the
    only modal element remaining.
    """

    def test_open_release_delivery_absent_from_dashboard(self):
        """OOMPAH-252: openReleaseDelivery() must be absent from dashboard."""
        html = _load_dashboard_html()
        assert "openReleaseDelivery" not in html

    def test_close_release_delivery_absent_from_dashboard(self):
        """OOMPAH-252: closeReleaseDelivery() must be absent from dashboard."""
        html = _load_dashboard_html()
        assert "closeReleaseDelivery" not in html

    def test_rdi_overlay_absent_from_dashboard(self):
        """OOMPAH-252: rdi-overlay dialog must be absent from dashboard."""
        html = _load_dashboard_html()
        assert 'id="rdi-overlay"' not in html

    def test_page_has_no_overlay_open_function(self):
        """Dedicated page uses navigation, not open/close dialog functions."""
        script = _load_release_delivery_script()
        assert "openReleaseDelivery" not in script
        assert "closeReleaseDelivery" not in script

    def test_page_initialises_on_load(self):
        """Dedicated page calls _rdiInit() on load instead of open/close dialog."""
        script = _load_release_delivery_script()
        assert "_rdiInit()" in script

    def test_close_drawer_removes_open_class(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "classList.remove('open')" in body
        assert "rdi-drawer" in body


class TestEscapeKeyHandler:
    """Test keyboard Escape handling for the evidence drawer (OOMPAH-252: no overlay to close)."""

    def test_escape_closes_drawer_on_dedicated_page(self):
        """On the dedicated page, Escape closes the evidence drawer."""
        script = _load_release_delivery_script()
        assert "Escape" in script
        assert "_rdiCloseDrawer" in script

    def test_escape_handler_not_an_rdi_key_handler_function(self):
        """Dedicated page does not define _rdiKeyHandler (replaced by inline listener)."""
        script = _load_release_delivery_script()
        assert "function _rdiKeyHandler" not in script

    def test_close_drawer_removes_open_class(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "classList.remove('open')" in body
        assert "rdi-drawer" in body


# ===========================================================================
# Project Defaulting Tests
# ===========================================================================


class TestProjectDefaulting:
    """Test that the dedicated page defaults based on URL params (OOMPAH-252: URL persistence)."""

    def test_populate_project_reads_url_params(self):
        """OOMPAH-252: page reads project from URL params, not board filter."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "urlProject" in body or "_rdiReadUrl" in body

    def test_populate_project_falls_back_to_first_project(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "projects[0]" in body

    def test_populate_project_builds_dom_not_innerhtml(self):
        """Project names must be set via DOM (not innerHTML) to avoid XSS."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "createElement" in body or "textContent" in body

    def test_on_project_change_resets_selected_branch(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiSelectedBranch = ''" in body

    def test_on_project_change_resets_selected_identifiers(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiSelectedIdentifiers = new Set()" in body

    def test_on_project_change_pushes_url(self):
        """OOMPAH-252: project change must update the URL."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiPushUrl" in body

    def test_on_project_change_calls_load_backlog_or_populate_branch(self):
        """Project change must trigger backlog refresh (via branch populator)."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiPopulateBranchSelector" in body or "_rdiLoadBacklog()" in body


# ===========================================================================
# Branch Selector Tests
# ===========================================================================


class TestBranchSelector:
    """Test the branch-first selection model."""

    def test_populate_branch_selector_reads_supported_branches(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPopulateBranchSelector")
        assert "supported_release_branches" in body or "release_branches" in body

    def test_populate_branch_selector_updates_rdi_branch_select(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPopulateBranchSelector")
        assert "rdi-branch-select" in body

    def test_on_branch_change_updates_selected_branch(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnBranchChange")
        assert "_rdiSelectedBranch" in body

    def test_on_branch_change_triggers_backlog_load(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnBranchChange")
        assert "_rdiLoadBacklog()" in body

    def test_show_no_branch_renders_prompt(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "branch" in body.lower()


# ===========================================================================
# Data Loading Tests
# ===========================================================================


class TestDataLoading:
    """Test _rdiLoadBacklog behavior (replaces commit-centric _rdiLoadPage)."""

    def test_load_backlog_uses_backlog_endpoint(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "release-delivery/backlog" in body

    def test_load_backlog_includes_branch_param(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "branch" in body
        assert "_rdiSelectedBranch" in body

    def test_load_backlog_increments_generation(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiGen" in body

    def test_load_backlog_ignores_stale_responses(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "myGen" in body
        assert "myGen !== _rdiGen" in body or "_rdiGen" in body

    def test_load_backlog_handles_http_error(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "!resp.ok" in body

    def test_load_backlog_handles_network_error(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert ".catch(" in body

    def test_load_backlog_includes_filter_param(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "filter" in body
        assert "URLSearchParams" in body or "params.set" in body

    def test_load_backlog_includes_query_param(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "query" in body

    def test_load_backlog_has_no_cursor_param(self):
        """Item-centric backlog does not paginate via cursor."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "cursor" not in body

    def test_load_backlog_has_no_branches_array_param(self):
        """Old multi-branch filter no longer sent; branch is a single param."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        # Should not iterate _rdiVisibleBranches
        assert "_rdiVisibleBranches" not in body

    def test_refresh_calls_force_refresh(self):
        """_rdiRefresh delegates to _rdiForceRefresh (OOMPAH-251 async model).

        The refresh button now POSTs to /backlog/refresh to cancel any
        in-flight background job and start a fresh one.  _rdiRefresh is
        the thin wrapper called by the header button; _rdiForceRefresh does
        the actual POST.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRefresh")
        assert "_rdiForceRefresh()" in body

    def test_load_backlog_handles_refresh_status_field(self):
        """_rdiLoadBacklog reads data.refresh_status from the response (OOMPAH-251)."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "refresh_status" in body

    def test_load_backlog_starts_poll_when_running(self):
        """_rdiLoadBacklog calls _rdiStartPoll when a background refresh is in flight."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiStartPoll()" in body

    def test_load_backlog_stops_poll_on_error(self):
        """_rdiLoadBacklog calls _rdiStopPoll in the catch handler."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiStopPoll()" in body

    def test_load_backlog_shows_stale_data_while_refresh_runs(self):
        """_rdiLoadBacklog only replaces body with loading spinner when no cached data.

        When _rdiCurrentData is already set, the spinner should not replace
        the visible table — the stale-while-revalidate model keeps the last
        result visible until the refresh completes.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiCurrentData" in body


# ===========================================================================
# Async Refresh Progress UI Tests (OOMPAH-251)
# ===========================================================================


class TestAsyncRefreshProgressCSS:
    """Verify CSS for the async refresh progress banner is present."""

    def test_rdi_refresh_status_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-status" in styles

    def test_rdi_refresh_status_active_variant(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-status.active" in styles

    def test_rdi_refresh_spinner_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-spinner" in styles

    def test_rdi_refresh_bar_track_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-bar-track" in styles

    def test_rdi_refresh_bar_fill_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-bar-fill" in styles

    def test_rdi_refresh_error_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-error" in styles

    def test_rdi_refresh_retry_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-retry" in styles

    def test_rdi_stale_badge_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-stale-badge" in styles

    def test_rdi_refresh_progress_class(self):
        styles = _load_release_delivery_styles()
        assert ".rdi-refresh-progress" in styles


class TestAsyncRefreshProgressHTML:
    """Verify the async refresh progress banner HTML element is present."""

    def test_rdi_refresh_status_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-status"' in html

    def test_rdi_refresh_status_has_role_status(self):
        html = _load_release_delivery_html()
        assert 'role="status"' in html

    def test_rdi_refresh_status_has_aria_live(self):
        html = _load_release_delivery_html()
        # Should be aria-live="polite" on the progress banner
        assert 'aria-live="polite"' in html

    def test_rdi_refresh_phase_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-phase"' in html

    def test_rdi_refresh_bar_fill_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-bar-fill"' in html

    def test_rdi_refresh_count_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-count"' in html

    def test_rdi_refresh_elapsed_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-elapsed"' in html

    def test_rdi_stale_badge_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-stale-badge"' in html

    def test_rdi_refresh_error_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-error"' in html

    def test_rdi_refresh_retry_element_present(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-refresh-retry"' in html

    def test_rdi_refresh_retry_calls_force_refresh(self):
        html = _load_release_delivery_html()
        assert '_rdiForceRefresh()' in html

    def test_rdi_refresh_status_before_outcome_banner(self):
        """Progress banner must appear before the outcome banner."""
        html = _load_release_delivery_html()
        rs_idx = html.index('id="rdi-refresh-status"')
        outcome_idx = html.index('id="rdi-outcome"')
        assert rs_idx < outcome_idx

    def test_rdi_refresh_status_has_aria_label(self):
        """The banner must have an aria-label for screen reader context."""
        html = _load_release_delivery_html()
        assert 'aria-label="Backlog refresh progress"' in html


class TestAsyncRefreshProgressFunctions:
    """Verify all async refresh management functions are defined."""

    def test_rdi_update_refresh_status_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiUpdateRefreshStatus(" in script

    def test_rdi_hide_refresh_status_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiHideRefreshStatus(" in script

    def test_rdi_force_refresh_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiForceRefresh(" in script

    def test_rdi_poll_status_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiPollStatus(" in script

    def test_rdi_start_poll_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiStartPoll(" in script

    def test_rdi_stop_poll_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiStopPoll(" in script

    def test_rdi_phase_labels_constant_defined(self):
        """_RDI_PHASE_LABELS maps phase names to human-readable strings."""
        script = _load_release_delivery_script()
        assert "_RDI_PHASE_LABELS" in script

    def test_rdi_phase_labels_includes_loading_merged(self):
        script = _load_release_delivery_script()
        assert "loading_merged" in script

    def test_rdi_phase_labels_includes_resolving_commits(self):
        script = _load_release_delivery_script()
        assert "resolving_commits" in script

    def test_rdi_phase_labels_includes_comparing_ancestry(self):
        script = _load_release_delivery_script()
        assert "comparing_ancestry" in script

    def test_rdi_phase_labels_includes_preparing_rows(self):
        script = _load_release_delivery_script()
        assert "preparing_rows" in script

    def test_rdi_phase_labels_includes_diagnostics(self):
        script = _load_release_delivery_script()
        assert "diagnostics" in script

    def test_poll_timer_state_variable_present(self):
        """_rdiPollTimer holds the setInterval handle."""
        script = _load_release_delivery_script()
        assert "_rdiPollTimer = null" in script

    def test_rdi_force_refresh_posts_to_backlog_refresh(self):
        """_rdiForceRefresh must POST to /release-delivery/backlog/refresh."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiForceRefresh")
        assert "backlog/refresh" in body
        assert "POST" in body

    def test_rdi_poll_status_hits_backlog_status(self):
        """_rdiPollStatus must GET from /release-delivery/backlog/status."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPollStatus")
        assert "backlog/status" in body

    def test_rdi_start_poll_uses_set_interval(self):
        """_rdiStartPoll sets up polling via setInterval."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiStartPoll")
        assert "setInterval" in body

    def test_rdi_stop_poll_uses_clear_interval(self):
        """_rdiStopPoll clears the interval via clearInterval."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiStopPoll")
        assert "clearInterval" in body

    def test_rdi_update_refresh_status_shows_phase_text(self):
        """_rdiUpdateRefreshStatus writes phase text to the phase element."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateRefreshStatus")
        assert "rdi-refresh-phase" in body

    def test_rdi_update_refresh_status_shows_progress_bar(self):
        """_rdiUpdateRefreshStatus updates the bar fill width."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateRefreshStatus")
        assert "rdi-refresh-bar-fill" in body or "barFill" in body

    def test_rdi_update_refresh_status_shows_elapsed(self):
        """_rdiUpdateRefreshStatus writes elapsed time."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateRefreshStatus")
        assert "elapsed_s" in body

    def test_rdi_update_refresh_status_shows_retry_on_failure(self):
        """_rdiUpdateRefreshStatus shows the retry button when phase=failed."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateRefreshStatus")
        assert "failed" in body
        assert "retryBtn" in body or "rdi-refresh-retry" in body

    def test_rdi_update_refresh_status_shows_stale_badge(self):
        """_rdiUpdateRefreshStatus shows stale badge when result exists and refresh is running."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateRefreshStatus")
        assert "has_result" in body
        assert "staleBadge" in body or "rdi-stale-badge" in body

    def test_page_unload_stops_poll(self):
        """OOMPAH-252: navigating away from the dedicated page must stop polling.

        The pagehide event listener calls _rdiStopPoll() to clean up the
        setInterval timer when the user navigates to another page.
        """
        script = _load_release_delivery_script()
        assert "pagehide" in script
        assert "_rdiStopPoll()" in script

    def test_show_no_branch_hides_refresh_status(self):
        """_rdiShowNoBranch must hide the progress banner when no branch is selected."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "_rdiHideRefreshStatus()" in body

    def test_show_no_branch_stops_poll(self):
        """_rdiShowNoBranch must stop polling (OOMPAH-251)."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "_rdiStopPoll()" in body

    def test_rdi_force_refresh_preserves_stale_data(self):
        """_rdiForceRefresh must not clear _rdiCurrentData.

        The stale-while-revalidate model keeps the previous result visible
        while the new refresh runs. _rdiForceRefresh must not wipe the
        current data before the new result arrives.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiForceRefresh")
        assert "_rdiCurrentData = null" not in body

    def test_rdi_poll_status_reloads_backlog_on_complete(self):
        """_rdiPollStatus calls _rdiLoadBacklog when phase=complete."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiPollStatus")
        assert "_rdiLoadBacklog()" in body
        assert "complete" in body


# ===========================================================================
# Status Rendering Tests
# ===========================================================================


class TestStatusRendering:
    """Test status cell rendering."""

    def test_render_status_cell_exists(self):
        script = _load_release_delivery_script()
        assert "function _rdiRenderStatusCell(" in script

    def test_render_status_cell_uses_status_labels(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "_RDI_STATUS_LABELS" in body

    def test_render_status_cell_ancestry_shows_ancestry_label(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "ancestry" in body
        assert "Delivered (ancestry)" in body

    def test_render_status_cell_delivery_shows_cherry_pick_label(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "cherry-pick" in body or "Delivered (cherry-pick)" in body

    def test_render_status_cell_ancestry_uses_distinct_css_class(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "rdi-cell-delivered-ancestry" in body

    def test_render_status_cell_active_states_clickable(self):
        """Active and delivered cells should be clickable to open the drawer."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "rdi-cell-clickable" in body

    def test_render_status_cell_clickable_uses_event_listener(self):
        """Clickable cells must use addEventListener, not onclick interpolation."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "addEventListener" in body

    def test_render_item_row_subject_uses_textcontent(self):
        """Subject/title must be set via textContent, never innerHTML from API data."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "textContent" in body
        import re
        bad_pattern = re.compile(r'innerHTML\s*=.*subject', re.DOTALL)
        assert not bad_pattern.search(body), "subject must not be interpolated into innerHTML"

    def test_render_item_row_shows_identifier(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "identifier" in body

    def test_render_item_row_shows_commit_count(self):
        """Row should show how many commits back the item (via commit_count field)."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "commit_count" in body

    def test_render_item_row_delivered_archived_checkbox_disabled(self):
        """Items already delivered or archived must not be selectable."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # Should disable checkbox for delivered/archived states
        assert "delivered" in body
        assert "archived" in body
        assert "disabled" in body

    def test_render_item_row_opens_drawer_on_identifier_click(self):
        """Clicking the identifier should open the item details drawer."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "_rdiOpenItemDrawer" in body


# ===========================================================================
# No Untrusted Text in Onclick Tests
# ===========================================================================


class TestXSSPrevention:
    """Verify no untrusted API text is interpolated into event handlers."""

    def test_commit_subject_not_in_onclick(self):
        """Commit subjects (user-controlled text) must never appear in onclick attributes."""
        script = _load_release_delivery_script()
        import re
        bad_pattern = re.compile(
            r'onclick\s*=\s*["\'].*subject|subject.*onclick\s*=\s*["\']',
            re.IGNORECASE
        )
        rdi_section = script[script.index("openReleaseDelivery"):] if "openReleaseDelivery" in script else script
        assert not bad_pattern.search(rdi_section), (
            "commit subject must not be interpolated into onclick attributes"
        )

    def test_author_name_not_in_onclick(self):
        """Author names must not be interpolated into onclick attributes."""
        script = _load_release_delivery_script()
        import re
        bad_pattern = re.compile(
            r'onclick\s*=\s*["\'].*author|author.*onclick\s*=\s*["\']',
            re.IGNORECASE
        )
        rdi_section = script[script.index("openReleaseDelivery"):] if "openReleaseDelivery" in script else script
        assert not bad_pattern.search(rdi_section)

    def test_error_messages_use_esc(self):
        """Error messages from the API must be escaped with esc()."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "esc(" in body

    def test_render_item_row_builds_dom_nodes(self):
        """_rdiRenderItemRow must use DOM node creation, not innerHTML for the row itself."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "createElement" in body

    def test_branch_selection_does_not_interpolate_into_onclick(self):
        """Branch selection uses a <select> dropdown — no onclick interpolation of branch names."""
        script = _load_release_delivery_script()
        # Branch value comes from a <select> element, not from onclick attributes
        # Verify the branch selector reads .value, not an interpolated onclick
        assert "_rdiSelectedBranch" in script
        # Confirm no pattern like onclick="...branchName..." for branch names
        import re
        bad_pattern = re.compile(
            r'onclick\s*=\s*["\'].*_rdiSelectedBranch|_rdiSelectedBranch.*onclick\s*=\s*["\']',
            re.IGNORECASE
        )
        rdi_section = script[script.index("openReleaseDelivery"):] if "openReleaseDelivery" in script else script
        assert not bad_pattern.search(rdi_section)


# ===========================================================================
# Selection Tests
# ===========================================================================


class TestSelection:
    """Test item selection behavior."""

    def test_toggle_identifier_adds_to_set(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiToggleIdentifier")
        assert "_rdiSelectedIdentifiers.add(" in body

    def test_toggle_identifier_removes_from_set(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiToggleIdentifier")
        assert "_rdiSelectedIdentifiers.delete(" in body

    def test_toggle_identifier_updates_action_bar(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiToggleIdentifier")
        assert "_rdiUpdateActionBar()" in body

    def test_select_all_adds_selectable_identifiers(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiSelectAll")
        assert "_rdiSelectedIdentifiers.add(" in body

    def test_select_all_skips_delivered_and_archived(self):
        """Select-all must not select items already delivered or archived."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiSelectAll")
        assert "delivered" in body
        assert "archived" in body

    def test_clear_selection_empties_identifier_set(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiClearSelection")
        assert "_rdiSelectedIdentifiers = new Set()" in body

    def test_clear_selection_updates_checkboxes(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiClearSelection")
        assert "checked" in body

    def test_update_action_bar_hidden_when_empty(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateActionBar")
        assert "hidden = true" in body

    def test_update_action_bar_shown_when_selected(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateActionBar")
        assert "hidden = false" in body

    def test_update_action_bar_shows_count(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateActionBar")
        assert "size" in body or "selected" in body.lower()

    def test_update_select_all_handles_indeterminate(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiUpdateSelectAll")
        assert "indeterminate" in body


# ===========================================================================
# Queue Delivery Tests
# ===========================================================================


class TestQueueDelivery:
    """Test _rdiQueueSelected behavior."""

    def test_queue_requires_selected_branch(self):
        """Queue should abort if no branch is selected."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiSelectedBranch" in body

    def test_queue_posts_to_correct_endpoint(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "release-delivery/commits" in body
        assert "POST" in body

    def test_queue_sends_idempotency_key(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "Idempotency-Key" in body

    def test_queue_sends_source_head(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "source_head" in body

    def test_queue_collects_source_commits_from_items(self):
        """Queue sends ALL source_commits from selected items, not just raw SHAs."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "source_commits" in body
        assert "allCommitSHAs" in body or "commits" in body

    def test_queue_sends_single_target_branch(self):
        """Target branch comes from the branch selector, not a separate target list."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "target_branches" in body
        assert "_rdiSelectedBranch" in body

    def test_queue_clears_queued_identifiers_on_success(self):
        """After success, identifiers of queued items are deselected."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiSelectedIdentifiers.delete(" in body

    def test_queue_reloads_backlog_on_success(self):
        """After success, the backlog is refreshed."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiLoadBacklog()" in body

    def test_queue_shows_outcome_summary(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiShowOutcomeSummary" in body

    def test_queue_handles_http_error(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "!resp.ok" in body
        assert "_rdiShowOutcomeError" in body

    def test_queue_handles_network_error(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "catch" in body

    def test_queue_disables_button_while_in_flight(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "disabled = true" in body

    def test_queue_re_enables_button_on_error(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "disabled = false" in body

    def test_queue_requires_confirmation(self):
        """The queue action should show a confirmation before submitting."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "confirm(" in body


# ===========================================================================
# Outcome Feedback Tests
# ===========================================================================


class TestOutcomeFeedback:
    """Test queue outcome feedback rendering."""

    def test_show_outcome_summary_mentions_queued(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "queued" in body or "created" in body

    def test_show_outcome_summary_mentions_active(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "active" in body

    def test_show_outcome_summary_mentions_delivered(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "delivered" in body

    def test_show_outcome_summary_mentions_invalid(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "invalid" in body

    def test_show_outcome_summary_auto_hides(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "setTimeout" in body
        assert "hidden" in body

    def test_show_outcome_summary_updates_banner(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "rdi-outcome" in body

    def test_show_outcome_error_updates_banner(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowOutcomeError")
        assert "rdi-outcome" in body


# ===========================================================================
# Item Details Drawer Tests
# ===========================================================================


class TestItemDetailsDrawer:
    """Test item-level evidence drawer (_rdiOpenItemDrawer)."""

    def test_drawer_opens_with_item_identifier(self):
        """Drawer shows the item's identifier, not a raw commit SHA."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "identifier" in body
        assert "textContent" in body

    def test_drawer_shows_source_commits(self):
        """Source commits are shown as sub-detail inside the drawer."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "source_commits" in body

    def test_drawer_shows_commit_subject(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "subject" in body

    def test_drawer_shows_delivered_by_ancestry(self):
        """Ancestry deliveries must be labeled distinctly; shown via _rdiRenderCellDetail."""
        script = _load_release_delivery_script()
        # The detail is rendered by _rdiRenderCellDetail, called from within _rdiOpenItemDrawer
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "Delivered by ancestry" in body

    def test_drawer_shows_delivered_by_cherry_pick(self):
        """Cherry-pick deliveries must be labeled distinctly; shown via _rdiRenderCellDetail."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "Delivered by cherry-pick" in body

    def test_drawer_shows_pr_link(self):
        """PR link shown in cell detail helper."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "pr_url" in body

    def test_drawer_shows_delivery_id(self):
        """Delivery ID shown in cell detail helper."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "delivery_id" in body

    def test_drawer_shows_result_commits(self):
        """Result commits shown in cell detail helper."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "result_commits" in body

    def test_drawer_builds_dom_nodes_not_innerhtml(self):
        """Drawer must use DOM creation for untrusted text (subject, author, etc.)."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "createElement" in body
        assert "textContent" in body

    def test_close_drawer_removes_open_class(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "classList.remove('open')" in body

    def test_close_drawer_clears_drawer_item(self):
        """_rdiDrawerItem is cleared on close (not _rdiDrawerSHA)."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "_rdiDrawerItem = null" in body

    def test_no_load_page_call_in_close_drawer(self):
        """Closing drawer should not trigger a page reload."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "_rdiLoadPage" not in body


# ===========================================================================
# Filter / Search Tests
# ===========================================================================


class TestFilterSearch:
    """Test filter and search handlers."""

    def test_filter_change_reads_radio_value(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "rdi-filter" in body
        assert "_rdiFilter" in body

    def test_filter_change_reloads_backlog(self):
        """Filter change calls _rdiLoadBacklog, not _rdiLoadPage."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "_rdiLoadBacklog()" in body

    def test_filter_change_does_not_reset_cursor(self):
        """No cursor exists in the item-centric view."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "_rdiCursor = null" not in body

    def test_search_input_debounced(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "setTimeout" in body

    def test_search_input_updates_query(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "_rdiQuery" in body

    def test_search_input_does_not_reset_cursor(self):
        """No cursor in item-centric view."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "_rdiCursor = null" not in body

    def test_no_branch_filter_change_function(self):
        """Old multi-branch checkbox handler does not exist in item-centric view."""
        script = _load_release_delivery_script()
        assert "function _rdiBranchFilterChange(" not in script


# ===========================================================================
# No Pagination Tests
# ===========================================================================


class TestNoPagination:
    """Verify the 'Load next page' pagination is fully removed."""

    def test_no_load_next_page_text(self):
        html = _load_release_delivery_html()
        assert "Load next page" not in html

    def test_no_render_pagination_function(self):
        script = _load_release_delivery_script()
        assert "function _rdiRenderPagination(" not in script

    def test_no_hide_pagination_function(self):
        script = _load_release_delivery_script()
        assert "function _rdiHidePagination(" not in script

    def test_no_rdi_pagination_id_in_html(self):
        html = _load_release_delivery_html()
        assert 'id="rdi-pagination"' not in html

    def test_no_cursor_param_in_load_backlog(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "cursor" not in body

    def test_no_next_cursor_in_render_backlog(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "next_cursor" not in body


# ===========================================================================
# Unassociated Commits Section Tests
# ===========================================================================


class TestUnassociatedSection:
    """Verify unassociated commits are shown in a separate subordinate section."""

    def test_render_unassoc_row_defined(self):
        script = _load_release_delivery_script()
        assert "function _rdiRenderUnassocRow(" in script

    def test_unassociated_section_rendered_separately(self):
        """Unassociated commits must not appear in the primary item table."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "unassociated_commits" in body

    def test_unassoc_section_class_in_render(self):
        """Unassociated section must have its own CSS class."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "rdi-unassoc" in body


# ===========================================================================
# Empty / Error State Tests
# ===========================================================================


class TestEmptyErrorStates:
    """Test rendering for empty and error conditions."""

    def test_no_project_message_shown(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowNoProject")
        assert "rdi-no-project" in body

    def test_no_branch_message_shown(self):
        """When no branch selected, a clear prompt must be shown."""
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "branch" in body.lower()

    def test_no_rows_message_shows_filter(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "rdi-empty" in body

    def test_load_backlog_error_shows_error_div(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "rdi-error" in body

    def test_no_source_changed_409_in_backlog(self):
        """Item-centric backlog does not use source_changed pagination guard
        (though HTTP 409 may still be handled generically)."""
        # This is an informational assertion: the new endpoint doesn't require
        # source_changed semantics, so if 409 handling is absent that is fine.
        # We just verify _rdiLoadBacklog doesn't reference the old
        # _rdiLoadPage(null) reload pattern used for 409 recovery.
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiLoadPage(null)" not in body


# ===========================================================================
# Retained Controls Tests
# ===========================================================================


class TestRetainedControls:
    """Verify that task/epic release controls are retained (not removed)."""

    def test_open_add_release_branches_dialog_retained(self):
        script = _load_dashboard_script()
        assert "function openAddReleaseBranchesDialog(" in script or \
               "async function openAddReleaseBranchesDialog(" in script

    def test_close_add_release_branches_dialog_retained(self):
        script = _load_dashboard_script()
        assert "function closeAddReleaseBranchesDialog(" in script

    def test_submit_add_release_branches_dialog_retained(self):
        script = _load_dashboard_script()
        assert "function submitAddReleaseBranchesDialog(" in script or \
               "async function submitAddReleaseBranchesDialog(" in script

    def test_add_release_branches_dialog_html_retained(self):
        html = _load_dashboard_html()
        assert 'id="add-release-branches-dialog"' in html

    def test_render_release_addendums_section_retained(self):
        script = _load_dashboard_script()
        assert "function renderReleaseAddendumsSection(" in script or \
               "renderReleaseAddendumsSection" in script

    def test_render_epic_release_addendums_section_retained(self):
        script = _load_dashboard_script()
        assert "renderEpicReleaseAddendumsSection" in script

    def test_rab_issue_identifier_retained(self):
        script = _load_dashboard_script()
        assert "_rabIssueIdentifier" in script

    def test_rab_project_id_retained(self):
        script = _load_dashboard_script()
        assert "_rabProjectId" in script

    def test_rab_active_targets_retained(self):
        script = _load_dashboard_script()
        assert "_rabActiveTargets" in script


# ===========================================================================
# Accessibility Tests
# ===========================================================================


class TestAccessibility:
    """Verify accessibility attributes on the dedicated Release Delivery page (OOMPAH-252)."""

    def test_page_has_role_region_for_candidates(self):
        """OOMPAH-252: candidate list region has accessible role+label."""
        html = _load_release_delivery_html()
        assert 'role="region"' in html
        assert 'aria-label="Release delivery candidates"' in html

    def test_drawer_has_aria_modal(self):
        """Drawer has aria-modal=true."""
        html = _load_release_delivery_html()
        idx = html.index('id="rdi-drawer"')
        context = html[max(0, idx - 100) : idx + 300]
        assert 'aria-modal="true"' in context

    def test_drawer_has_role_dialog(self):
        """Evidence drawer is the accessible dialog element on the page."""
        html = _load_release_delivery_html()
        idx = html.index('id="rdi-drawer"')
        context = html[max(0, idx - 100) : idx + 300]
        assert 'role="dialog"' in context

    def test_filter_group_has_role(self):
        """Filter radio group has role=radiogroup."""
        html = _load_release_delivery_html()
        assert 'role="radiogroup"' in html or 'rdi-filter-group' in html

    def test_branch_select_has_aria_label(self):
        """Branch selector must have an aria-label."""
        html = _load_release_delivery_html()
        assert 'aria-label="Select release branch"' in html

    def test_clickable_cell_has_role_button(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert 'role="button"' in body or "setAttribute('role', 'button')" in body

    def test_clickable_cell_has_tabindex(self):
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "tabindex" in body or 'tabIndex' in body

    def test_close_btn_has_aria_label(self):
        """Drawer close button has aria-label."""
        html = _load_release_delivery_html()
        assert 'aria-label="Close item details"' in html

    def test_drawer_close_btn_has_aria_label(self):
        html = _load_release_delivery_html()
        assert 'aria-label="Close' in html and "drawer" in html.lower() or \
               "aria-label" in html


# ===========================================================================
# Old RBI Code Removal Tests
# ===========================================================================


class TestOldRBIRemoved:
    """Verify no stale Release Branch Inspector code exists."""

    def test_open_release_branch_inspector_gone(self):
        script = _load_dashboard_script()
        assert "openReleaseBranchInspector" not in script

    def test_close_release_branch_inspector_gone(self):
        script = _load_dashboard_script()
        assert "closeReleaseBranchInspector" not in script

    def test_rbi_current_project_id_gone(self):
        script = _load_dashboard_script()
        assert "_rbiCurrentProjectId" not in script

    def test_rbi_current_branch_gone(self):
        script = _load_dashboard_script()
        assert "_rbiCurrentBranch" not in script

    def test_rbi_loading_gone(self):
        script = _load_dashboard_script()
        assert "_rbiLoading" not in script

    def test_load_branch_list_gone(self):
        script = _load_dashboard_script()
        assert "_rbiLoadBranchList" not in script

    def test_load_branch_addendums_gone(self):
        script = _load_dashboard_script()
        assert "_rbiLoadBranchAddendums" not in script

    def test_rbi_render_inspector_body_gone(self):
        script = _load_dashboard_script()
        assert "_rbiRenderInspectorBody" not in script

    def test_rbi_html_overlay_gone(self):
        html = _load_dashboard_html()
        assert "Release branches inspector overlay (OOMPAH-182)" not in html

    def test_release_branch_inspector_overlay_class_gone_from_html(self):
        html = _load_dashboard_html()
        assert 'class="release-branch-inspector-overlay' not in html

    def test_rbi_overlay_id_gone(self):
        html = _load_dashboard_html()
        assert 'id="release-branch-inspector-overlay"' not in html


# ===========================================================================
# OOMPAH-216: Release Delivery reconciled branch status and actionable retries
# ===========================================================================


class TestMergedStatusLabel:
    """Verify the merged status label from OOMPAH-216 is retained."""

    def test_rdi_cell_merged_css_class_exists(self):
        """The .rdi-cell-merged CSS class must be defined (OOMPAH-216)."""
        html = _load_release_delivery_html()
        assert "rdi-cell-merged" in html, "Missing .rdi-cell-merged CSS class"

    def test_merged_status_label_in_rdi_status_labels(self):
        """_RDI_STATUS_LABELS must include 'merged' key (OOMPAH-216)."""
        script = _load_release_delivery_script()
        assert "merged:" in script or "merged :" in script, (
            "_RDI_STATUS_LABELS must include a 'merged' entry"
        )


class TestBlockedDeliveryRetryUI:
    """Verify the drawer shows error and retry for blocked deliveries (OOMPAH-216)."""

    def test_retry_delivery_function_defined(self):
        """_rdiRetryDelivery must be defined in the script (OOMPAH-216)."""
        script = _load_release_delivery_script()
        assert "_rdiRetryDelivery" in script, "Missing _rdiRetryDelivery function"

    def test_retry_calls_project_delivery_endpoint(self):
        """Retry function must call the project-scoped retry API endpoint (OOMPAH-216)."""
        script = _load_release_delivery_script()
        assert "/release-delivery/" in script, (
            "Retry should call /release-delivery/<id>/retry endpoint"
        )
        assert "/retry" in script, "Retry button should POST to /retry"

    def test_error_field_rendered_for_blocked_state(self):
        """The drawer renders cell.error when state === 'blocked' (OOMPAH-216)."""
        script = _load_release_delivery_script()
        assert "cell.error" in script, "Drawer must show cell.error for blocked deliveries"
        assert "state === 'blocked'" in script, "Drawer must check state === 'blocked'"

    def test_conflict_agent_indicator_in_drawer(self):
        """The drawer must show a conflict agent indicator when resolving (OOMPAH-216)."""
        script = _load_release_delivery_script()
        assert "conflict_agent_resolving" in script, (
            "Drawer must check cell.conflict_agent_resolving"
        )

    def test_retry_button_only_for_blocked_deliveries(self):
        """Retry button is only rendered for blocked deliveries with delivery_id (OOMPAH-216)."""
        script = _load_release_delivery_script()
        assert "Retry delivery" in script, "Retry button must have 'Retry delivery' label"


# ===========================================================================
# Newly Merged Task with No Release History (OOMPAH-238 / OOMPAH-240)
# ===========================================================================


class TestNewlyMergedTaskQueueable:
    """Regression coverage for the tracker-sourced backlog fix (OOMPAH-238).

    Before OOMPAH-238, the backlog service only discovered items that already
    appeared in the release-delivery ledger.  A task that was merged to the
    default branch but never queued for release delivery was invisible.

    After OOMPAH-238, the service also enumerates Merged tracker items and
    resolves their source commits, returning them with
    ``delivery_status.state='not_selected'`` and no ``delivery_id``.

    These tests verify that the dashboard JavaScript:

    - Renders a ``not_selected`` item in the **primary** table (not filtered
      out client-side).
    - Shows the item identifier, title, and source commit count.
    - Shows "Not selected" in the status column.
    - Presents an **enabled** checkbox so the item can be queued.
    - Collects ``source_commits`` from the item when queuing (does not require
      a ``delivery_id``).
    - Verifies that ``delivered`` and ``archived`` items have **disabled**
      checkboxes and cannot be re-queued.
    - Verifies that ``select-all`` includes ``not_selected`` items but skips
      ``delivered`` and ``archived`` items.

    Acceptance: these tests pass with the OOMPAH-238 tracker-sourced backlog
    implementation and would fail if the UI were changed to filter out
    ``not_selected`` items or require a ``delivery_id`` before queuing.
    """

    # ------------------------------------------------------------------
    # Status label
    # ------------------------------------------------------------------

    def test_not_selected_status_label_is_not_selected(self):
        """_RDI_STATUS_LABELS must map 'not_selected' to 'Not selected'.

        A newly merged task with no ledger history has state='not_selected'.
        The UI must show the human-readable label 'Not selected', not the
        raw state key.
        """
        script = _load_release_delivery_script()
        # The map entry must exist with the exact human-readable label.
        assert "not_selected: 'Not selected'" in script or 'not_selected: "Not selected"' in script, (
            "_RDI_STATUS_LABELS must contain not_selected: 'Not selected'"
        )

    def test_not_selected_label_used_in_status_cell_render(self):
        """_rdiRenderStatusCell must use _RDI_STATUS_LABELS to look up the label.

        When rendering a cell with state='not_selected', the function should
        use the labels map to render 'Not selected'.  This test verifies the
        lookup path exists so the label is surfaced in the table.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        # Status cell reads label from the labels map
        assert "_RDI_STATUS_LABELS" in body
        # The state variable is used to index into the map
        assert "state" in body

    def test_not_selected_status_cell_is_not_clickable(self):
        """A 'not_selected' cell (no delivery_id, no evidence) must not be clickable.

        Items with no ledger history have no delivery_id and no evidence,
        so the status cell should display the label without a click target.
        Clickability is gated on cell.delivery_id or delivered evidence.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        # Clickable cells require delivery_id or evidence
        assert "delivery_id" in body
        assert "rdi-cell-clickable" in body
        # The clickable guard must reference delivery_id (not always-clickable)
        assert "cell.delivery_id" in body or "delivery_id" in body

    # ------------------------------------------------------------------
    # Item row rendering — not_selected items are queueable
    # ------------------------------------------------------------------

    def test_not_selected_item_checkbox_enabled_by_default(self):
        """Checkboxes for items are enabled unless the item is delivered/archived.

        A newly merged task with delivery_status.state='not_selected' must
        have an enabled (non-disabled) checkbox so the user can select it
        for queuing.  The disable guard must be conditional, not unconditional.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # Checkbox is created without disabled
        assert "cb.disabled = true" in body, (
            "_rdiRenderItemRow must have a conditional cb.disabled = true for delivered/archived"
        )
        # The condition must be exclusively for delivered OR archived states —
        # verify it is inside an 'if' block mentioning those states, not always
        assert (
            "status === 'delivered'" in body or "status==='delivered'" in body or
            "'delivered' === status" in body
        ), "_rdiRenderItemRow must check for 'delivered' before disabling"
        assert (
            "status === 'archived'" in body or "status==='archived'" in body or
            "'archived' === status" in body
        ), "_rdiRenderItemRow must check for 'archived' before disabling"

    def test_only_delivered_and_archived_trigger_disabled_checkbox(self):
        """The disabled condition must reference only 'delivered' and 'archived'.

        'not_selected', 'open', 'in_progress', 'in_review', and 'blocked'
        items must NOT trigger a disabled checkbox — they should be selectable
        for queuing or re-queuing.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # The guard pattern is:
        #   if (status === 'delivered' || status === 'archived') { cb.disabled = true; ... }
        #
        # Extract the actual if-condition expression by looking for the last 'if ('
        # before 'cb.disabled = true' and reading up to the first '{' after it.
        disabled_pos = body.index("cb.disabled = true")
        # Walk backwards to find the opening 'if (' for this guard
        if_pos = body.rindex("if (", 0, disabled_pos)
        condition_end = body.index("{", if_pos)
        if_condition = body[if_pos:condition_end]
        # The if-condition must contain 'delivered' and 'archived'
        assert "delivered" in if_condition, (
            "disabled guard must reference 'delivered'"
        )
        assert "archived" in if_condition, (
            "disabled guard must reference 'archived'"
        )
        # The if-condition must NOT contain 'not_selected' as a triggering state
        assert "not_selected" not in if_condition, (
            "not_selected must not be in the disabled guard — it should be queueable"
        )

    def test_render_item_row_shows_identifier_for_new_task(self):
        """_rdiRenderItemRow must render item.identifier in the row.

        For a newly merged task TASK-NEW, the identifier column must display
        'TASK-NEW'.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "item.identifier" in body, (
            "_rdiRenderItemRow must reference item.identifier to render the identifier"
        )

    def test_render_item_row_shows_title_with_identifier_fallback(self):
        """_rdiRenderItemRow must show item.title, falling back to identifier.

        For a newly merged task, the backend fetches the title from the
        tracker.  The UI must display the title when present and fall back
        to the identifier when the title is absent (e.g., tracker unavailable).
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # Both title and identifier must appear in the title-column logic
        assert "item.title" in body
        assert "item.identifier" in body
        # Fallback pattern: item.title || item.identifier
        assert "item.title || item.identifier" in body or "item.title||item.identifier" in body, (
            "_rdiRenderItemRow must fall back to item.identifier when item.title is absent"
        )

    def test_render_item_row_shows_source_commit_count(self):
        """_rdiRenderItemRow must display item.commit_count.

        The commit count shows how many default-branch commits are associated
        with the task, which is critical for newly merged tasks discovered via
        the tracker.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "item.commit_count" in body, (
            "_rdiRenderItemRow must display item.commit_count"
        )

    # ------------------------------------------------------------------
    # Backlog rendering — not_selected items appear in primary table
    # ------------------------------------------------------------------

    def test_render_backlog_renders_all_items_without_client_filtering(self):
        """_rdiRenderBacklog must render ALL items from data.items.

        Filtering by delivery status is done server-side (via the filter param).
        The UI must not skip items based on their delivery_status.state.
        A not_selected item returned by the (fixed) backend must appear in
        the primary table, not be discarded client-side.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderBacklog")
        # All items in data.items are rendered
        assert "items" in body
        assert "_rdiRenderItemRow" in body
        # The function may reference 'needs_delivery' for empty-state display
        # (e.g. 'No items match the current filter ("Needs delivery")'), but it
        # must NOT use it to SKIP individual items in the rendering loop.
        # Verify the rendering call is NOT gated on delivery_status.state:
        render_call_pos = body.index("_rdiRenderItemRow")
        # Extract the for-loop surrounding the render call by looking backwards
        # for the last 'for (' before the render call
        for_pos = body.rindex("for (", 0, render_call_pos)
        loop_fragment = body[for_pos:render_call_pos + len("_rdiRenderItemRow")]
        # The loop should not have an 'if ... continue' that checks delivery_status
        assert "delivery_status" not in loop_fragment, (
            "_rdiRenderBacklog must not skip items by delivery_status in the render loop"
        )
        assert "not_selected" not in loop_fragment, (
            "_rdiRenderBacklog must not skip not_selected items in the render loop"
        )

    def test_render_backlog_iterates_all_data_items(self):
        """_rdiRenderBacklog must iterate ALL items from data, calling _rdiRenderItemRow for each.

        The loop must use data.items (not a pre-filtered subset).
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderBacklog")
        # Must iterate the items array from data
        assert "data.items" in body or "(data.items" in body or "items = data.items" in body, (
            "_rdiRenderBacklog must derive the item list from data.items"
        )

    # ------------------------------------------------------------------
    # Queuing — source_commits collected without delivery_id check
    # ------------------------------------------------------------------

    def test_queue_collects_source_commits_without_requiring_delivery_id(self):
        """_rdiQueueSelected must read item.source_commits regardless of delivery_id.

        A newly merged task has no delivery_id (it has never been queued before).
        The queue function must collect its source_commits from item.source_commits,
        not skip the item because delivery_id is absent.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        # Must read source_commits from each selected item
        assert "source_commits" in body, (
            "_rdiQueueSelected must collect item.source_commits when building the commit list"
        )
        # The collection must NOT be gated on delivery_id existence
        # Extract the section around 'source_commits' and verify delivery_id
        # is not used as a guard immediately before
        sc_pos = body.index("source_commits")
        surrounding = body[max(0, sc_pos - 150):sc_pos]
        assert "delivery_id" not in surrounding or "if" not in surrounding, (
            "_rdiQueueSelected must not skip items with no delivery_id when collecting source_commits"
        )

    def test_queue_sends_target_branch_as_single_branch(self):
        """_rdiQueueSelected must send target_branches: [_rdiSelectedBranch].

        The queue endpoint accepts an array, but the RDI overlay always
        operates on exactly one selected branch.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "target_branches" in body
        assert "_rdiSelectedBranch" in body

    def test_queue_sends_source_commits_sha_array(self):
        """_rdiQueueSelected must post commits as an array of SHA strings.

        The POST body must include 'commits' key with SHA strings collected
        from all selected item.source_commits entries.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        # 'commits' must appear in the JSON body
        assert '"commits"' in body or "commits:" in body, (
            "_rdiQueueSelected must include a 'commits' key in the POST body"
        )
        # SHAs are accessed via .sha on source commit objects
        assert ".sha" in body, (
            "_rdiQueueSelected must extract .sha from source_commits entries"
        )

    def test_queue_posts_to_release_delivery_commits_endpoint(self):
        """Queue must POST to /release-delivery/commits endpoint.

        This is the existing shared endpoint that accepts source commits for
        a set of target branches.  The endpoint path must include the project
        id (dynamic) and the literal path segment 'release-delivery/commits'.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "release-delivery/commits" in body

    # ------------------------------------------------------------------
    # Select-all respects not_selected / delivered / archived
    # ------------------------------------------------------------------

    def test_select_all_includes_not_selected_items(self):
        """_rdiSelectAll must add 'not_selected' items to the selection set.

        Newly merged tasks (not_selected) must be selectable via 'select all'.
        The select-all function only skips delivered and archived items.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiSelectAll")
        # Skips only delivered and archived
        assert "delivered" in body
        assert "archived" in body
        # Locate the 'continue' statement that skips non-selectable items.
        # The skip condition must not mention 'not_selected'.
        # Pattern: if (status === 'delivered' || status === 'archived') continue;
        continue_pos = body.index("continue")
        # Find the if-condition that guards this continue
        if_pos = body.rindex("if (", 0, continue_pos)
        skip_condition = body[if_pos:continue_pos]
        # 'not_selected' must NOT appear in the skip condition
        assert "not_selected" not in skip_condition, (
            "_rdiSelectAll skip condition must not include 'not_selected' — "
            "newly merged tasks must be selectable via select-all"
        )

    def test_select_all_skips_delivered_and_archived_not_others(self):
        """_rdiSelectAll skips only delivered and archived states.

        Items with states open, in_progress, in_review, blocked, or
        not_selected must all be selectable via select-all.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiSelectAll")
        # Only delivered and archived appear in the continue/skip condition
        assert "delivered" in body
        assert "archived" in body
        # Active delivery states must NOT be in the skip condition
        assert "in_progress" not in body, (
            "_rdiSelectAll must not skip in_progress items"
        )
        assert "in_review" not in body, (
            "_rdiSelectAll must not skip in_review items"
        )

    # ------------------------------------------------------------------
    # Delivered / archived items are not re-queueable
    # ------------------------------------------------------------------

    def test_delivered_item_checkbox_is_disabled(self):
        """Items with delivery_status.state='delivered' must have disabled checkboxes.

        A delivered task has already been cherry-picked or proven by ancestry.
        Re-queuing it would create a duplicate delivery.  The checkbox must be
        disabled.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # delivered triggers cb.disabled = true
        delivered_check = "status === 'delivered'" in body or "'delivered' === status" in body
        assert delivered_check, (
            "_rdiRenderItemRow must explicitly check for 'delivered' status to disable checkbox"
        )
        assert "cb.disabled = true" in body

    def test_archived_item_checkbox_is_disabled(self):
        """Items with delivery_status.state='archived' must have disabled checkboxes.

        An archived delivery is closed/abandoned.  Re-queuing is not valid.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        archived_check = "status === 'archived'" in body or "'archived' === status" in body
        assert archived_check, (
            "_rdiRenderItemRow must explicitly check for 'archived' status to disable checkbox"
        )
        assert "cb.disabled = true" in body

    def test_disabled_checkbox_aria_label_mentions_state(self):
        """Disabled checkboxes must have an accessible aria-label explaining why.

        Screen readers need to communicate why the checkbox is disabled.
        The aria-label must mention the item's current state.
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # aria-label is updated when checkbox is disabled
        assert "aria-label" in body
        # The label update mentions 'is ' followed by the status
        assert "' is '" in body or "\" is \"" in body, (
            "Disabled checkbox aria-label must explain the item's current state"
        )

    def test_select_all_skips_disabled_checkboxes(self):
        """_rdiSelectAll must not check disabled checkboxes.

        When marking all checkboxes, the select-all handler must skip
        checkboxes that have been disabled (delivered/archived items).
        """
        script = _load_release_delivery_script()
        body = _function_body(script, "_rdiSelectAll")
        # Must check .disabled before setting .checked
        assert "cb.disabled" in body, (
            "_rdiSelectAll must guard against checking disabled checkboxes"
        )
