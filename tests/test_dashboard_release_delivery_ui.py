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


def _load_dashboard_html() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def _load_dashboard_script() -> str:
    html = _load_dashboard_html()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _load_dashboard_styles() -> str:
    html = _load_dashboard_html()
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
    """Verify the Release delivery overlay CSS classes are present."""

    def test_rdi_overlay_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-overlay" in styles

    def test_rdi_panel_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-panel" in styles

    def test_rdi_header_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-header" in styles

    def test_rdi_table_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-table" in styles

    def test_rdi_table_wrap_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-table-wrap" in styles

    def test_rdi_close_btn_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-close-btn" in styles

    def test_rdi_loading_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-loading" in styles

    def test_rdi_empty_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-empty" in styles

    def test_rdi_error_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-error" in styles

    def test_rdi_cell_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-cell" in styles

    def test_rdi_action_bar_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-action-bar" in styles

    def test_rdi_drawer_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-drawer" in styles

    def test_rdi_drawer_panel_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-drawer-panel" in styles

    def test_rdi_unassoc_section_class(self):
        """Unassociated commits get their own non-primary section CSS."""
        styles = _load_dashboard_styles()
        assert "rdi-unassoc" in styles


class TestStatusCellCSS:
    """Verify CSS exists for all status cell states."""

    def test_not_selected_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-not_selected" in styles

    def test_open_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-open" in styles

    def test_in_progress_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-in_progress" in styles

    def test_in_review_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-in_review" in styles

    def test_blocked_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-blocked" in styles

    def test_delivered_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-delivered" in styles

    def test_archived_cell(self):
        styles = _load_dashboard_styles()
        assert "rdi-cell-archived" in styles

    def test_delivered_ancestry_has_distinct_css(self):
        """Delivered-by-ancestry must have a distinct CSS class from delivered-by-cherry-pick."""
        styles = _load_dashboard_styles()
        assert "rdi-cell-delivered-ancestry" in styles

    def test_ancestry_css_differs_from_delivery_css(self):
        """The ancestry variant must visually differ from the cherry-pick variant."""
        styles = _load_dashboard_styles()
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
        styles = _load_dashboard_styles()
        assert "rdi-cell-clickable" in styles


class TestOutcomeCSS:
    """Verify outcome banner CSS classes."""

    def test_outcome_banner_class(self):
        styles = _load_dashboard_styles()
        assert "rdi-outcome-banner" in styles

    def test_outcome_banner_success(self):
        styles = _load_dashboard_styles()
        assert "rdi-outcome-banner-success" in styles

    def test_outcome_banner_partial(self):
        styles = _load_dashboard_styles()
        assert "rdi-outcome-banner-partial" in styles


# ===========================================================================
# Toolbar Tests
# ===========================================================================


class TestToolbarButton:
    """Verify the toolbar button opens the new Release delivery overlay."""

    def test_old_release_branches_button_gone(self):
        html = _load_dashboard_html()
        assert "btn-release-branches" not in html

    def test_old_open_release_branch_inspector_gone(self):
        html = _load_dashboard_html()
        assert "openReleaseBranchInspector" not in html

    def test_new_release_delivery_button_present(self):
        html = _load_dashboard_html()
        assert 'id="btn-release-delivery"' in html

    def test_new_button_calls_open_release_delivery(self):
        html = _load_dashboard_html()
        assert 'onclick="openReleaseDelivery()"' in html

    def test_new_button_label(self):
        html = _load_dashboard_html()
        assert ">Release delivery<" in html


# ===========================================================================
# HTML Structure Tests
# ===========================================================================


class TestRDIOverlayHTML:
    """Verify the Release delivery overlay HTML structure."""

    def test_overlay_div_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-overlay"' in html

    def test_overlay_role_dialog(self):
        html = _load_dashboard_html()
        assert 'role="dialog"' in html
        assert 'id="rdi-overlay"' in html

    def test_overlay_aria_modal(self):
        html = _load_dashboard_html()
        assert 'aria-modal="true"' in html

    def test_overlay_aria_labelledby(self):
        html = _load_dashboard_html()
        assert 'aria-labelledby="rdi-title"' in html

    def test_overlay_closes_on_backdrop_click(self):
        html = _load_dashboard_html()
        assert "closeReleaseDelivery()" in html
        assert "if(event.target===this)closeReleaseDelivery()" in html

    def test_project_selector_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-project-select"' in html

    def test_project_selector_has_onchange(self):
        html = _load_dashboard_html()
        assert '_rdiOnProjectChange()' in html

    def test_branch_selector_present(self):
        """Branch is now selected via a <select> dropdown, not checkbox filters."""
        html = _load_dashboard_html()
        assert 'id="rdi-branch-select"' in html

    def test_branch_selector_has_onchange(self):
        html = _load_dashboard_html()
        assert '_rdiOnBranchChange()' in html

    def test_no_branch_filters_checkbox_group(self):
        """Old commit-centric branch filter checkboxes must be removed."""
        html = _load_dashboard_html()
        assert 'id="rdi-branch-filters"' not in html

    def test_no_target_list_element(self):
        """Old target-branch list for multi-selection must be removed."""
        html = _load_dashboard_html()
        assert 'id="rdi-target-list"' not in html

    def test_no_pagination_element(self):
        """No 'Load next page' pagination control exists in the item-centric view."""
        html = _load_dashboard_html()
        assert 'id="rdi-pagination"' not in html

    def test_filter_radio_needs_delivery(self):
        html = _load_dashboard_html()
        assert 'value="needs_delivery"' in html
        assert 'name="rdi-filter"' in html

    def test_filter_radio_all(self):
        html = _load_dashboard_html()
        assert "value=\"all\"" in html or "'all'" in html

    def test_search_input_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-search"' in html

    def test_search_input_has_oninput(self):
        html = _load_dashboard_html()
        assert '_rdiOnSearchInput()' in html

    def test_outcome_banner_present_and_hidden(self):
        html = _load_dashboard_html()
        assert 'id="rdi-outcome"' in html
        assert 'hidden' in html

    def test_body_wrapper_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-body"' in html

    def test_body_wrapper_aria_live(self):
        html = _load_dashboard_html()
        assert 'aria-live="polite"' in html

    def test_action_bar_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-action-bar"' in html

    def test_action_bar_initially_hidden(self):
        html = _load_dashboard_html()
        idx = html.index('id="rdi-action-bar"')
        context = html[max(0, idx - 50) : idx + 150]
        assert "hidden" in context

    def test_selected_count_element(self):
        html = _load_dashboard_html()
        assert 'id="rdi-action-count"' in html

    def test_queue_button_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-queue-btn"' in html
        assert '_rdiQueueSelected()' in html

    def test_clear_selection_button(self):
        html = _load_dashboard_html()
        assert '_rdiClearSelection()' in html

    def test_drawer_title_is_item_details(self):
        """Drawer title should say 'Item details', not 'Commit details'."""
        html = _load_dashboard_html()
        assert "Item details" in html


class TestRDIDrawerHTML:
    """Verify the evidence drawer HTML structure."""

    def test_drawer_div_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-drawer"' in html

    def test_drawer_role_dialog(self):
        html = _load_dashboard_html()
        drawer_idx = html.index('id="rdi-drawer"')
        context = html[max(0, drawer_idx - 100) : drawer_idx + 200]
        assert 'role="dialog"' in context

    def test_drawer_aria_modal(self):
        html = _load_dashboard_html()
        drawer_idx = html.index('id="rdi-drawer"')
        context = html[max(0, drawer_idx - 100) : drawer_idx + 200]
        assert 'aria-modal="true"' in context

    def test_drawer_body_element(self):
        html = _load_dashboard_html()
        assert 'id="rdi-drawer-body"' in html

    def test_drawer_close_button(self):
        html = _load_dashboard_html()
        assert '_rdiCloseDrawer()' in html


# ===========================================================================
# State Variable Tests
# ===========================================================================


class TestStateVariables:
    """Verify state variables are initialized correctly."""

    def test_project_id_initialized(self):
        script = _load_dashboard_script()
        assert "let _rdiProjectId = null" in script

    def test_selected_branch_initialized(self):
        """Single selected branch (replaces _rdiVisibleBranches array)."""
        script = _load_dashboard_script()
        assert "_rdiSelectedBranch = ''" in script

    def test_no_visible_branches_array(self):
        """Old multi-branch filter array must be gone."""
        script = _load_dashboard_script()
        assert "_rdiVisibleBranches = []" not in script

    def test_no_cursor_variable(self):
        """No commit-pagination cursor — this is an item-centric view."""
        script = _load_dashboard_script()
        assert "_rdiCursor = null" not in script

    def test_filter_initialized_to_needs_delivery(self):
        script = _load_dashboard_script()
        assert "_rdiFilter = 'needs_delivery'" in script

    def test_query_initialized_to_empty(self):
        script = _load_dashboard_script()
        assert "_rdiQuery = ''" in script

    def test_source_head_initialized_to_null(self):
        script = _load_dashboard_script()
        assert "_rdiSourceHead = null" in script

    def test_selected_identifiers_initialized_as_set(self):
        """Selection tracks item identifiers, not raw commit SHAs."""
        script = _load_dashboard_script()
        assert "_rdiSelectedIdentifiers = new Set()" in script

    def test_no_selected_shas_variable(self):
        """Old SHA-set selection must be gone."""
        script = _load_dashboard_script()
        assert "_rdiSelectedSHAs = new Set()" not in script

    def test_generation_counter_initialized(self):
        script = _load_dashboard_script()
        assert "_rdiGen = 0" in script

    def test_loading_flag_initialized(self):
        script = _load_dashboard_script()
        assert "_rdiLoading = false" in script

    def test_current_data_initialized(self):
        """_rdiCurrentData replaces the old _rdiCurrentPageData."""
        script = _load_dashboard_script()
        assert "_rdiCurrentData = null" in script

    def test_no_current_page_data_variable(self):
        """Old per-page data variable must be gone."""
        script = _load_dashboard_script()
        assert "_rdiCurrentPageData = null" not in script

    def test_opener_initialized_to_null(self):
        script = _load_dashboard_script()
        assert "_rdiOpener = null" in script

    def test_drawer_item_initialized_to_null(self):
        """_rdiDrawerItem tracks open item identifier, not commit SHA."""
        script = _load_dashboard_script()
        assert "_rdiDrawerItem = null" in script

    def test_no_drawer_sha_variable(self):
        """Old _rdiDrawerSHA must be gone."""
        script = _load_dashboard_script()
        assert "_rdiDrawerSHA = null" not in script

    def test_status_labels_map_present(self):
        script = _load_dashboard_script()
        assert "_RDI_STATUS_LABELS" in script

    def test_status_labels_has_all_states(self):
        script = _load_dashboard_script()
        for state in ["not_selected", "open", "in_progress", "in_review",
                      "blocked", "delivered", "archived"]:
            assert state in script


# ===========================================================================
# Function Existence Tests
# ===========================================================================


class TestFunctionDefinitions:
    """Verify all required functions are defined."""

    def test_open_release_delivery_defined(self):
        script = _load_dashboard_script()
        assert "function openReleaseDelivery(" in script

    def test_close_release_delivery_defined(self):
        script = _load_dashboard_script()
        assert "function closeReleaseDelivery(" in script

    def test_rdi_key_handler_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiKeyHandler(" in script

    def test_rdi_populate_project_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiPopulateProject(" in script

    def test_rdi_on_project_change_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiOnProjectChange(" in script

    def test_rdi_populate_branch_selector_defined(self):
        """New branch selector function replaces the old branch filter renderer."""
        script = _load_dashboard_script()
        assert "function _rdiPopulateBranchSelector(" in script

    def test_rdi_on_branch_change_defined(self):
        """New branch change handler replaces _rdiBranchFilterChange."""
        script = _load_dashboard_script()
        assert "function _rdiOnBranchChange(" in script

    def test_rdi_load_backlog_defined(self):
        """New single-fetch function replaces cursor-based _rdiLoadPage."""
        script = _load_dashboard_script()
        assert "function _rdiLoadBacklog(" in script

    def test_no_rdi_load_page(self):
        """Cursor-based load-page function must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiLoadPage(" not in script

    def test_rdi_refresh_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRefresh(" in script

    def test_rdi_render_backlog_defined(self):
        """New backlog renderer replaces old page renderer."""
        script = _load_dashboard_script()
        assert "function _rdiRenderBacklog(" in script

    def test_no_rdi_render_page(self):
        """Old commit-page renderer must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiRenderPage(" not in script

    def test_rdi_render_meta_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderMeta(" in script

    def test_rdi_render_item_row_defined(self):
        """New item-row renderer replaces old commit-row renderer."""
        script = _load_dashboard_script()
        assert "function _rdiRenderItemRow(" in script

    def test_no_rdi_render_row(self):
        """Old commit-row renderer (_rdiRenderRow) must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiRenderRow(" not in script

    def test_rdi_render_status_cell_defined(self):
        """Renamed from _rdiRenderCell."""
        script = _load_dashboard_script()
        assert "function _rdiRenderStatusCell(" in script

    def test_rdi_render_unassoc_row_defined(self):
        """Renderer for unassociated commit rows in subordinate section."""
        script = _load_dashboard_script()
        assert "function _rdiRenderUnassocRow(" in script

    def test_rdi_toggle_identifier_defined(self):
        """New identifier-based toggle replaces _rdiToggleSHA."""
        script = _load_dashboard_script()
        assert "function _rdiToggleIdentifier(" in script

    def test_no_rdi_toggle_sha(self):
        """Old SHA-based toggle must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiToggleSHA(" not in script

    def test_rdi_select_all_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiSelectAll(" in script

    def test_rdi_update_select_all_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiUpdateSelectAll(" in script

    def test_rdi_clear_selection_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiClearSelection(" in script

    def test_rdi_update_action_bar_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiUpdateActionBar(" in script

    def test_rdi_queue_selected_defined(self):
        script = _load_dashboard_script()
        assert "_rdiQueueSelected" in script

    def test_rdi_show_outcome_summary_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiShowOutcomeSummary(" in script

    def test_rdi_show_outcome_error_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiShowOutcomeError(" in script

    def test_rdi_open_item_drawer_defined(self):
        """New item-drawer opener replaces old commit-drawer opener."""
        script = _load_dashboard_script()
        assert "function _rdiOpenItemDrawer(" in script

    def test_no_rdi_open_drawer(self):
        """Old commit-specific drawer opener must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiOpenDrawer(" not in script

    def test_rdi_close_drawer_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiCloseDrawer(" in script

    def test_rdi_on_filter_change_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiOnFilterChange(" in script

    def test_rdi_on_search_input_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiOnSearchInput(" in script

    def test_no_rdi_branch_filter_change(self):
        """Old branch-filter-checkbox handler must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiBranchFilterChange(" not in script

    def test_rdi_show_no_project_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiShowNoProject(" in script

    def test_rdi_show_no_branch_defined(self):
        """Shows prompt when no branch selected yet."""
        script = _load_dashboard_script()
        assert "function _rdiShowNoBranch(" in script

    def test_no_rdi_find_row(self):
        """Old commit SHA lookup function must be removed."""
        script = _load_dashboard_script()
        assert "function _rdiFindRow(" not in script

    def test_no_rdi_render_pagination(self):
        """Pagination function must be removed from item-centric view."""
        script = _load_dashboard_script()
        assert "function _rdiRenderPagination(" not in script


# ===========================================================================
# Open / Close Behaviour Tests
# ===========================================================================


class TestOpenCloseOverlay:
    """Test openReleaseDelivery / closeReleaseDelivery behaviour."""

    def test_open_adds_open_class_to_overlay(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openReleaseDelivery")
        assert "classList.add('open')" in body
        assert "rdi-overlay" in body

    def test_open_stores_opener_for_focus_restoration(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openReleaseDelivery")
        assert "_rdiOpener" in body
        assert "activeElement" in body

    def test_open_calls_populate_project(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openReleaseDelivery")
        assert "_rdiPopulateProject()" in body

    def test_open_registers_keydown_listener(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openReleaseDelivery")
        assert "addEventListener" in body
        assert "keydown" in body

    def test_open_focuses_close_btn(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openReleaseDelivery")
        assert "rdi-close-btn" in body
        assert "focus" in body

    def test_close_removes_open_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeReleaseDelivery")
        assert "classList.remove('open')" in body

    def test_close_removes_keydown_listener(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeReleaseDelivery")
        assert "removeEventListener" in body

    def test_close_calls_close_drawer(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeReleaseDelivery")
        assert "_rdiCloseDrawer()" in body

    def test_close_restores_focus(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeReleaseDelivery")
        assert "_rdiOpener" in body
        assert ".focus()" in body


class TestEscapeKeyHandler:
    """Test keyboard Escape handling."""

    def test_escape_handler_closes_overlay(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiKeyHandler")
        assert "Escape" in body
        assert "closeReleaseDelivery" in body

    def test_escape_closes_drawer_first_if_open(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiKeyHandler")
        assert "_rdiCloseDrawer" in body
        drawer_pos = body.index("_rdiCloseDrawer")
        close_pos = body.index("closeReleaseDelivery")
        assert drawer_pos < close_pos, "Drawer close must come before overlay close"

    def test_close_drawer_removes_open_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "classList.remove('open')" in body
        assert "rdi-drawer" in body


# ===========================================================================
# Project Defaulting Tests
# ===========================================================================


class TestProjectDefaulting:
    """Test that the overlay defaults to the dashboard's project filter."""

    def test_populate_project_reads_board_filter(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "selectedProjectFilterValue" in body

    def test_populate_project_defaults_to_board_filter(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "boardFilter" in body
        assert "sel.value = boardFilter" in body or "sel.value=" in body

    def test_populate_project_falls_back_to_first_project(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "projects[0]" in body

    def test_populate_project_builds_dom_not_innerhtml(self):
        """Project names must be set via DOM (not innerHTML) to avoid XSS."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "createElement" in body or "textContent" in body

    def test_on_project_change_resets_selected_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiSelectedBranch = ''" in body

    def test_on_project_change_resets_selected_identifiers(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiSelectedIdentifiers = new Set()" in body

    def test_on_project_change_calls_load_backlog_or_populate_branch(self):
        """Project change must trigger backlog refresh (via branch populator)."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiPopulateBranchSelector()" in body or "_rdiLoadBacklog()" in body


# ===========================================================================
# Branch Selector Tests
# ===========================================================================


class TestBranchSelector:
    """Test the branch-first selection model."""

    def test_populate_branch_selector_reads_supported_branches(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiPopulateBranchSelector")
        assert "supported_release_branches" in body or "release_branches" in body

    def test_populate_branch_selector_updates_rdi_branch_select(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiPopulateBranchSelector")
        assert "rdi-branch-select" in body

    def test_on_branch_change_updates_selected_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnBranchChange")
        assert "_rdiSelectedBranch" in body

    def test_on_branch_change_triggers_backlog_load(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnBranchChange")
        assert "_rdiLoadBacklog()" in body

    def test_show_no_branch_renders_prompt(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "branch" in body.lower()


# ===========================================================================
# Data Loading Tests
# ===========================================================================


class TestDataLoading:
    """Test _rdiLoadBacklog behavior (replaces commit-centric _rdiLoadPage)."""

    def test_load_backlog_uses_backlog_endpoint(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "release-delivery/backlog" in body

    def test_load_backlog_includes_branch_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "branch" in body
        assert "_rdiSelectedBranch" in body

    def test_load_backlog_increments_generation(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiGen" in body

    def test_load_backlog_ignores_stale_responses(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "myGen" in body
        assert "myGen !== _rdiGen" in body or "_rdiGen" in body

    def test_load_backlog_handles_http_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "!resp.ok" in body

    def test_load_backlog_handles_network_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert ".catch(" in body

    def test_load_backlog_includes_filter_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "filter" in body
        assert "URLSearchParams" in body or "params.set" in body

    def test_load_backlog_includes_query_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "query" in body

    def test_load_backlog_has_no_cursor_param(self):
        """Item-centric backlog does not paginate via cursor."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "cursor" not in body

    def test_load_backlog_has_no_branches_array_param(self):
        """Old multi-branch filter no longer sent; branch is a single param."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        # Should not iterate _rdiVisibleBranches
        assert "_rdiVisibleBranches" not in body

    def test_refresh_reloads_backlog(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRefresh")
        assert "_rdiLoadBacklog()" in body


# ===========================================================================
# Status Rendering Tests
# ===========================================================================


class TestStatusRendering:
    """Test status cell rendering."""

    def test_render_status_cell_exists(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderStatusCell(" in script

    def test_render_status_cell_uses_status_labels(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "_RDI_STATUS_LABELS" in body

    def test_render_status_cell_ancestry_shows_ancestry_label(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "ancestry" in body
        assert "Delivered (ancestry)" in body

    def test_render_status_cell_delivery_shows_cherry_pick_label(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "cherry-pick" in body or "Delivered (cherry-pick)" in body

    def test_render_status_cell_ancestry_uses_distinct_css_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "rdi-cell-delivered-ancestry" in body

    def test_render_status_cell_active_states_clickable(self):
        """Active and delivered cells should be clickable to open the drawer."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "rdi-cell-clickable" in body

    def test_render_status_cell_clickable_uses_event_listener(self):
        """Clickable cells must use addEventListener, not onclick interpolation."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "addEventListener" in body

    def test_render_item_row_subject_uses_textcontent(self):
        """Subject/title must be set via textContent, never innerHTML from API data."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "textContent" in body
        import re
        bad_pattern = re.compile(r'innerHTML\s*=.*subject', re.DOTALL)
        assert not bad_pattern.search(body), "subject must not be interpolated into innerHTML"

    def test_render_item_row_shows_identifier(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "identifier" in body

    def test_render_item_row_shows_commit_count(self):
        """Row should show how many commits back the item (via commit_count field)."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "commit_count" in body

    def test_render_item_row_delivered_archived_checkbox_disabled(self):
        """Items already delivered or archived must not be selectable."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderItemRow")
        # Should disable checkbox for delivered/archived states
        assert "delivered" in body
        assert "archived" in body
        assert "disabled" in body

    def test_render_item_row_opens_drawer_on_identifier_click(self):
        """Clicking the identifier should open the item details drawer."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "_rdiOpenItemDrawer" in body


# ===========================================================================
# No Untrusted Text in Onclick Tests
# ===========================================================================


class TestXSSPrevention:
    """Verify no untrusted API text is interpolated into event handlers."""

    def test_commit_subject_not_in_onclick(self):
        """Commit subjects (user-controlled text) must never appear in onclick attributes."""
        script = _load_dashboard_script()
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
        script = _load_dashboard_script()
        import re
        bad_pattern = re.compile(
            r'onclick\s*=\s*["\'].*author|author.*onclick\s*=\s*["\']',
            re.IGNORECASE
        )
        rdi_section = script[script.index("openReleaseDelivery"):] if "openReleaseDelivery" in script else script
        assert not bad_pattern.search(rdi_section)

    def test_error_messages_use_esc(self):
        """Error messages from the API must be escaped with esc()."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "esc(" in body

    def test_render_item_row_builds_dom_nodes(self):
        """_rdiRenderItemRow must use DOM node creation, not innerHTML for the row itself."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderItemRow")
        assert "createElement" in body

    def test_branch_selection_does_not_interpolate_into_onclick(self):
        """Branch selection uses a <select> dropdown — no onclick interpolation of branch names."""
        script = _load_dashboard_script()
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
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiToggleIdentifier")
        assert "_rdiSelectedIdentifiers.add(" in body

    def test_toggle_identifier_removes_from_set(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiToggleIdentifier")
        assert "_rdiSelectedIdentifiers.delete(" in body

    def test_toggle_identifier_updates_action_bar(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiToggleIdentifier")
        assert "_rdiUpdateActionBar()" in body

    def test_select_all_adds_selectable_identifiers(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiSelectAll")
        assert "_rdiSelectedIdentifiers.add(" in body

    def test_select_all_skips_delivered_and_archived(self):
        """Select-all must not select items already delivered or archived."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiSelectAll")
        assert "delivered" in body
        assert "archived" in body

    def test_clear_selection_empties_identifier_set(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiClearSelection")
        assert "_rdiSelectedIdentifiers = new Set()" in body

    def test_clear_selection_updates_checkboxes(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiClearSelection")
        assert "checked" in body

    def test_update_action_bar_hidden_when_empty(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiUpdateActionBar")
        assert "hidden = true" in body

    def test_update_action_bar_shown_when_selected(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiUpdateActionBar")
        assert "hidden = false" in body

    def test_update_action_bar_shows_count(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiUpdateActionBar")
        assert "size" in body or "selected" in body.lower()

    def test_update_select_all_handles_indeterminate(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiUpdateSelectAll")
        assert "indeterminate" in body


# ===========================================================================
# Queue Delivery Tests
# ===========================================================================


class TestQueueDelivery:
    """Test _rdiQueueSelected behavior."""

    def test_queue_requires_selected_branch(self):
        """Queue should abort if no branch is selected."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiSelectedBranch" in body

    def test_queue_posts_to_correct_endpoint(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "release-delivery/commits" in body
        assert "POST" in body

    def test_queue_sends_idempotency_key(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "Idempotency-Key" in body

    def test_queue_sends_source_head(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "source_head" in body

    def test_queue_collects_source_commits_from_items(self):
        """Queue sends ALL source_commits from selected items, not just raw SHAs."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "source_commits" in body
        assert "allCommitSHAs" in body or "commits" in body

    def test_queue_sends_single_target_branch(self):
        """Target branch comes from the branch selector, not a separate target list."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "target_branches" in body
        assert "_rdiSelectedBranch" in body

    def test_queue_clears_queued_identifiers_on_success(self):
        """After success, identifiers of queued items are deselected."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiSelectedIdentifiers.delete(" in body

    def test_queue_reloads_backlog_on_success(self):
        """After success, the backlog is refreshed."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiLoadBacklog()" in body

    def test_queue_shows_outcome_summary(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiShowOutcomeSummary" in body

    def test_queue_handles_http_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "!resp.ok" in body
        assert "_rdiShowOutcomeError" in body

    def test_queue_handles_network_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "catch" in body

    def test_queue_disables_button_while_in_flight(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "disabled = true" in body

    def test_queue_re_enables_button_on_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "disabled = false" in body

    def test_queue_requires_confirmation(self):
        """The queue action should show a confirmation before submitting."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "confirm(" in body


# ===========================================================================
# Outcome Feedback Tests
# ===========================================================================


class TestOutcomeFeedback:
    """Test queue outcome feedback rendering."""

    def test_show_outcome_summary_mentions_queued(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "queued" in body or "created" in body

    def test_show_outcome_summary_mentions_active(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "active" in body

    def test_show_outcome_summary_mentions_delivered(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "delivered" in body

    def test_show_outcome_summary_mentions_invalid(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "invalid" in body

    def test_show_outcome_summary_auto_hides(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "setTimeout" in body
        assert "hidden" in body

    def test_show_outcome_summary_updates_banner(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeSummary")
        assert "rdi-outcome" in body

    def test_show_outcome_error_updates_banner(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowOutcomeError")
        assert "rdi-outcome" in body


# ===========================================================================
# Item Details Drawer Tests
# ===========================================================================


class TestItemDetailsDrawer:
    """Test item-level evidence drawer (_rdiOpenItemDrawer)."""

    def test_drawer_opens_with_item_identifier(self):
        """Drawer shows the item's identifier, not a raw commit SHA."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "identifier" in body
        assert "textContent" in body

    def test_drawer_shows_source_commits(self):
        """Source commits are shown as sub-detail inside the drawer."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "source_commits" in body

    def test_drawer_shows_commit_subject(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "subject" in body

    def test_drawer_shows_delivered_by_ancestry(self):
        """Ancestry deliveries must be labeled distinctly; shown via _rdiRenderCellDetail."""
        script = _load_dashboard_script()
        # The detail is rendered by _rdiRenderCellDetail, called from within _rdiOpenItemDrawer
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "Delivered by ancestry" in body

    def test_drawer_shows_delivered_by_cherry_pick(self):
        """Cherry-pick deliveries must be labeled distinctly; shown via _rdiRenderCellDetail."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "Delivered by cherry-pick" in body

    def test_drawer_shows_pr_link(self):
        """PR link shown in cell detail helper."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "pr_url" in body

    def test_drawer_shows_delivery_id(self):
        """Delivery ID shown in cell detail helper."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "delivery_id" in body

    def test_drawer_shows_result_commits(self):
        """Result commits shown in cell detail helper."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCellDetail")
        assert "result_commits" in body

    def test_drawer_builds_dom_nodes_not_innerhtml(self):
        """Drawer must use DOM creation for untrusted text (subject, author, etc.)."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "createElement" in body
        assert "textContent" in body

    def test_close_drawer_removes_open_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "classList.remove('open')" in body

    def test_close_drawer_clears_drawer_item(self):
        """_rdiDrawerItem is cleared on close (not _rdiDrawerSHA)."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "_rdiDrawerItem = null" in body

    def test_no_load_page_call_in_close_drawer(self):
        """Closing drawer should not trigger a page reload."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "_rdiLoadPage" not in body


# ===========================================================================
# Filter / Search Tests
# ===========================================================================


class TestFilterSearch:
    """Test filter and search handlers."""

    def test_filter_change_reads_radio_value(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "rdi-filter" in body
        assert "_rdiFilter" in body

    def test_filter_change_reloads_backlog(self):
        """Filter change calls _rdiLoadBacklog, not _rdiLoadPage."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "_rdiLoadBacklog()" in body

    def test_filter_change_does_not_reset_cursor(self):
        """No cursor exists in the item-centric view."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "_rdiCursor = null" not in body

    def test_search_input_debounced(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "setTimeout" in body

    def test_search_input_updates_query(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "_rdiQuery" in body

    def test_search_input_does_not_reset_cursor(self):
        """No cursor in item-centric view."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "_rdiCursor = null" not in body

    def test_no_branch_filter_change_function(self):
        """Old multi-branch checkbox handler does not exist in item-centric view."""
        script = _load_dashboard_script()
        assert "function _rdiBranchFilterChange(" not in script


# ===========================================================================
# No Pagination Tests
# ===========================================================================


class TestNoPagination:
    """Verify the 'Load next page' pagination is fully removed."""

    def test_no_load_next_page_text(self):
        html = _load_dashboard_html()
        assert "Load next page" not in html

    def test_no_render_pagination_function(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderPagination(" not in script

    def test_no_hide_pagination_function(self):
        script = _load_dashboard_script()
        assert "function _rdiHidePagination(" not in script

    def test_no_rdi_pagination_id_in_html(self):
        html = _load_dashboard_html()
        assert 'id="rdi-pagination"' not in html

    def test_no_cursor_param_in_load_backlog(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "cursor" not in body

    def test_no_next_cursor_in_render_backlog(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "next_cursor" not in body


# ===========================================================================
# Unassociated Commits Section Tests
# ===========================================================================


class TestUnassociatedSection:
    """Verify unassociated commits are shown in a separate subordinate section."""

    def test_render_unassoc_row_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderUnassocRow(" in script

    def test_unassociated_section_rendered_separately(self):
        """Unassociated commits must not appear in the primary item table."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "unassociated_commits" in body

    def test_unassoc_section_class_in_render(self):
        """Unassociated section must have its own CSS class."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "rdi-unassoc" in body


# ===========================================================================
# Empty / Error State Tests
# ===========================================================================


class TestEmptyErrorStates:
    """Test rendering for empty and error conditions."""

    def test_no_project_message_shown(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowNoProject")
        assert "rdi-no-project" in body

    def test_no_branch_message_shown(self):
        """When no branch selected, a clear prompt must be shown."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "branch" in body.lower()

    def test_no_rows_message_shows_filter(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderBacklog")
        assert "rdi-empty" in body

    def test_load_backlog_error_shows_error_div(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "rdi-error" in body

    def test_no_source_changed_409_in_backlog(self):
        """Item-centric backlog does not use source_changed pagination guard
        (though HTTP 409 may still be handled generically)."""
        # This is an informational assertion: the new endpoint doesn't require
        # source_changed semantics, so if 409 handling is absent that is fine.
        # We just verify _rdiLoadBacklog doesn't reference the old
        # _rdiLoadPage(null) reload pattern used for 409 recovery.
        script = _load_dashboard_script()
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
    """Verify accessibility attributes on the overlay."""

    def test_overlay_has_role_dialog(self):
        html = _load_dashboard_html()
        idx = html.index('id="rdi-overlay"')
        context = html[max(0, idx - 100) : idx + 200]
        assert 'role="dialog"' in context

    def test_overlay_aria_modal(self):
        html = _load_dashboard_html()
        idx = html.index('id="rdi-overlay"')
        context = html[max(0, idx - 100) : idx + 200]
        assert 'aria-modal="true"' in context

    def test_drawer_has_role_dialog(self):
        html = _load_dashboard_html()
        idx = html.index('id="rdi-drawer"')
        context = html[max(0, idx - 100) : idx + 200]
        assert 'role="dialog"' in context

    def test_filter_group_has_role(self):
        html = _load_dashboard_html()
        assert 'role="radiogroup"' in html or 'rdi-filter-group' in html

    def test_branch_select_has_aria_label(self):
        """Branch selector must have an aria-label."""
        html = _load_dashboard_html()
        assert 'aria-label="Select release branch"' in html

    def test_clickable_cell_has_role_button(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert 'role="button"' in body or "setAttribute('role', 'button')" in body

    def test_clickable_cell_has_tabindex(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderStatusCell")
        assert "tabindex" in body or 'tabIndex' in body

    def test_close_btn_has_aria_label(self):
        html = _load_dashboard_html()
        assert 'aria-label="Close Release delivery"' in html

    def test_drawer_close_btn_has_aria_label(self):
        html = _load_dashboard_html()
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
        html = _load_dashboard_html()
        assert "rdi-cell-merged" in html, "Missing .rdi-cell-merged CSS class"

    def test_merged_status_label_in_rdi_status_labels(self):
        """_RDI_STATUS_LABELS must include 'merged' key (OOMPAH-216)."""
        script = _load_dashboard_script()
        assert "merged:" in script or "merged :" in script, (
            "_RDI_STATUS_LABELS must include a 'merged' entry"
        )


class TestBlockedDeliveryRetryUI:
    """Verify the drawer shows error and retry for blocked deliveries (OOMPAH-216)."""

    def test_retry_delivery_function_defined(self):
        """_rdiRetryDelivery must be defined in the script (OOMPAH-216)."""
        script = _load_dashboard_script()
        assert "_rdiRetryDelivery" in script, "Missing _rdiRetryDelivery function"

    def test_retry_calls_project_delivery_endpoint(self):
        """Retry function must call the project-scoped retry API endpoint (OOMPAH-216)."""
        script = _load_dashboard_script()
        assert "/release-delivery/" in script, (
            "Retry should call /release-delivery/<id>/retry endpoint"
        )
        assert "/retry" in script, "Retry button should POST to /retry"

    def test_error_field_rendered_for_blocked_state(self):
        """The drawer renders cell.error when state === 'blocked' (OOMPAH-216)."""
        script = _load_dashboard_script()
        assert "cell.error" in script, "Drawer must show cell.error for blocked deliveries"
        assert "state === 'blocked'" in script, "Drawer must check state === 'blocked'"

    def test_conflict_agent_indicator_in_drawer(self):
        """The drawer must show a conflict agent indicator when resolving (OOMPAH-216)."""
        script = _load_dashboard_script()
        assert "conflict_agent_resolving" in script, (
            "Drawer must check cell.conflict_agent_resolving"
        )

    def test_retry_button_only_for_blocked_deliveries(self):
        """Retry button is only rendered for blocked deliveries with delivery_id (OOMPAH-216)."""
        script = _load_dashboard_script()
        assert "Retry delivery" in script, "Retry button must have 'Retry delivery' label"
