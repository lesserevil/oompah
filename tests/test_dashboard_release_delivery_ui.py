"""Tests for the Release delivery overlay (OOMPAH-200).

Covers section 6 of plans/release-delivery-commit-inventory.md:

  CSS:
  - Legacy RBI CSS classes are removed (release-branch-inspector-overlay, rbi-*)
  - New RDI CSS classes are present (rdi-overlay, rdi-panel, rdi-table, etc.)
  - Status cell CSS variants for all states
  - Evidence-specific CSS for delivered-by-cherry-pick vs delivered-by-ancestry

  Toolbar:
  - Button opens openReleaseDelivery() (not openReleaseBranchInspector())
  - Button has id="btn-release-delivery" (not btn-release-branches)
  - Button label is "Release delivery"

  HTML overlay:
  - .rdi-overlay with correct id, role, aria attributes
  - Project selector, filter controls, search input
  - Branch column filter group
  - Outcome banner element (hidden by default)
  - Table body wrapper with aria-live
  - Pagination element
  - Bulk action bar with target branch list and queue button
  - Evidence drawer overlay

  State variables:
  - _rdiProjectId, _rdiVisibleBranches, _rdiFilter, _rdiQuery
  - _rdiCursor, _rdiSourceHead, _rdiSelectedSHAs, _rdiGen
  - _rdiLoading, _rdiCurrentPageData, _rdiOpener, _rdiDrawerSHA
  - _RDI_STATUS_LABELS map with all 7 states

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

  Project defaulting:
  - _rdiPopulateProject reads boardFilter (selectedProjectFilterValue)
  - Defaults to dashboard's active project filter
  - Falls back to first project if no board filter

  _rdiOnProjectChange():
  - Resets all state (cursor, sourceHead, selectedSHAs, etc.)
  - Resets filter UI controls
  - Calls _rdiLoadPage(null)

  _rdiLoadPage(cursor):
  - Builds URL with query params (branches, filter, query, cursor)
  - Uses generation counter to ignore stale responses
  - Handles 409 source_changed by resetting cursor and reloading
  - Handles network/HTTP errors with error message in body

  Status rendering:
  - _rdiRenderCell uses textContent (not innerHTML) for commit subjects
  - All 7 states render a label
  - 'delivered' with evidence='ancestry' shows 'Delivered (ancestry)'
  - 'delivered' with evidence='delivery' shows 'Delivered (cherry-pick)'
  - delivered-by-ancestry and delivered-by-cherry-pick have distinct CSS classes

  Merge commit rows:
  - Non-selectable rows render with rdi-row-merge class
  - No checkbox in the select column for merge commits

  No untrusted text in onclick handlers:
  - commit subjects never appear in onclick attributes
  - branch names use data-branch attributes, not onclick interpolation

  Selection:
  - _rdiToggleSHA adds/removes from _rdiSelectedSHAs
  - _rdiSelectAll (de)selects all selectable rows
  - _rdiUpdateSelectAll computes indeterminate state
  - _rdiClearSelection clears set and unchecks all checkboxes

  Action bar:
  - Shown when selection is non-empty, hidden when empty
  - Shows count of selected commits
  - Contains target branch checkboxes
  - Queue button calls _rdiQueueSelected

  _rdiQueueSelected():
  - Requires at least one target branch selected
  - Builds ordered SHA list in table row order
  - Posts to /api/v1/projects/{id}/release-delivery/commits
  - Sends Idempotency-Key header
  - Sends source_head, commits, target_branches in JSON body
  - On success: clears created/already_active/already_delivered SHAs from selection
  - On success: keeps invalid SHAs selected
  - Shows outcome summary banner
  - Reloads page one after success
  - Handles HTTP/network errors

  Outcome feedback:
  - _rdiShowOutcomeSummary shows created/active/delivered/invalid counts
  - _rdiShowOutcomeError shows error message
  - Outcome banner auto-hides after success

  Evidence drawer:
  - _rdiOpenDrawer renders full SHA, parents, subject, author, association, per-branch cells
  - delivered-by-cherry-pick shows 'Delivered by cherry-pick'
  - delivered-by-ancestry shows 'Delivered by ancestry'
  - PR link appears when pr_url is present
  - delivery_id appears in drawer
  - result_commits appears in drawer
  - _rdiCloseDrawer removes 'open' class
  - Escape closes drawer (then overlay on second Escape)

  Filter/search:
  - _rdiOnFilterChange updates _rdiFilter and reloads
  - _rdiOnSearchInput debounces and updates _rdiQuery
  - _rdiBranchFilterChange updates _rdiVisibleBranches

  Empty / error states:
  - No configured branches: empty state linking to project settings
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
  - No subject/author_name/error text interpolated into onclick= attributes

  Keyboard navigation:
  - rdi-overlay has role="dialog" and aria-modal="true"
  - rdi-drawer has role="dialog" and aria-modal="true"
  - Filter controls have role="radiogroup"
  - Branch filters have role="group"
  - Selectable cells have role="button" and tabindex="0"
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

    def test_rdi_pagination_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-pagination" in styles

    def test_rdi_drawer_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-drawer" in styles

    def test_rdi_drawer_panel_class(self):
        styles = _load_dashboard_styles()
        assert ".rdi-drawer-panel" in styles


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
        # They should be different rules (ancestry has italic or different background)
        ancestry_start = styles.index(".rdi-cell-delivered-ancestry")
        cherry_start = styles.index(".rdi-cell-delivered {")
        # Check that they define different styles
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
        # Backdrop click pattern
        assert "if(event.target===this)closeReleaseDelivery()" in html

    def test_project_selector_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-project-select"' in html

    def test_project_selector_has_onchange(self):
        html = _load_dashboard_html()
        assert '_rdiOnProjectChange()' in html

    def test_filter_radio_needs_delivery(self):
        html = _load_dashboard_html()
        assert 'value="needs_delivery"' in html
        assert 'name="rdi-filter"' in html

    def test_filter_radio_all(self):
        html = _load_dashboard_html()
        # Both the JS and HTML reference 'all' for the filter
        assert "value=\"all\"" in html or "'all'" in html

    def test_search_input_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-search"' in html

    def test_search_input_has_oninput(self):
        html = _load_dashboard_html()
        assert '_rdiOnSearchInput()' in html

    def test_branch_filters_container(self):
        html = _load_dashboard_html()
        assert 'id="rdi-branch-filters"' in html

    def test_outcome_banner_present_and_hidden(self):
        html = _load_dashboard_html()
        assert 'id="rdi-outcome"' in html
        assert 'hidden' in html

    def test_body_wrapper_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-body"' in html

    def test_body_wrapper_aria_live(self):
        html = _load_dashboard_html()
        # aria-live on the table body region
        assert 'aria-live="polite"' in html

    def test_pagination_element_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-pagination"' in html

    def test_action_bar_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-action-bar"' in html

    def test_action_bar_initially_hidden(self):
        html = _load_dashboard_html()
        # The action bar should start hidden
        idx = html.index('id="rdi-action-bar"')
        # Check hidden attribute appears within 150 chars of the id
        context = html[max(0, idx - 50) : idx + 150]
        assert "hidden" in context

    def test_selected_count_element(self):
        html = _load_dashboard_html()
        assert 'id="rdi-action-count"' in html

    def test_target_branch_list_element(self):
        html = _load_dashboard_html()
        assert 'id="rdi-target-list"' in html

    def test_queue_button_present(self):
        html = _load_dashboard_html()
        assert 'id="rdi-queue-btn"' in html
        assert '_rdiQueueSelected()' in html

    def test_clear_selection_button(self):
        html = _load_dashboard_html()
        assert '_rdiClearSelection()' in html


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

    def test_visible_branches_initialized(self):
        script = _load_dashboard_script()
        assert "_rdiVisibleBranches = []" in script

    def test_filter_initialized_to_needs_delivery(self):
        script = _load_dashboard_script()
        assert "_rdiFilter = 'needs_delivery'" in script

    def test_query_initialized_to_empty(self):
        script = _load_dashboard_script()
        assert "_rdiQuery = ''" in script

    def test_cursor_initialized_to_null(self):
        script = _load_dashboard_script()
        assert "_rdiCursor = null" in script

    def test_source_head_initialized_to_null(self):
        script = _load_dashboard_script()
        assert "_rdiSourceHead = null" in script

    def test_selected_shas_initialized_as_set(self):
        script = _load_dashboard_script()
        assert "_rdiSelectedSHAs = new Set()" in script

    def test_generation_counter_initialized(self):
        script = _load_dashboard_script()
        assert "_rdiGen = 0" in script

    def test_loading_flag_initialized(self):
        script = _load_dashboard_script()
        assert "_rdiLoading = false" in script

    def test_current_page_data_initialized(self):
        script = _load_dashboard_script()
        assert "_rdiCurrentPageData = null" in script

    def test_opener_initialized_to_null(self):
        script = _load_dashboard_script()
        assert "_rdiOpener = null" in script

    def test_drawer_sha_initialized_to_null(self):
        script = _load_dashboard_script()
        assert "_rdiDrawerSHA = null" in script

    def test_status_labels_map_present(self):
        script = _load_dashboard_script()
        assert "_RDI_STATUS_LABELS" in script

    def test_status_labels_has_all_states(self):
        script = _load_dashboard_script()
        for state in ["not_selected", "open", "in_progress", "in_review", "blocked", "delivered", "archived"]:
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

    def test_rdi_load_page_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiLoadPage(" in script

    def test_rdi_refresh_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRefresh(" in script

    def test_rdi_render_page_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderPage(" in script

    def test_rdi_render_meta_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderMeta(" in script

    def test_rdi_render_branch_filters_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderBranchFilters(" in script

    def test_rdi_render_row_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderRow(" in script

    def test_rdi_render_cell_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderCell(" in script

    def test_rdi_toggle_sha_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiToggleSHA(" in script

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

    def test_rdi_open_drawer_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiOpenDrawer(" in script

    def test_rdi_close_drawer_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiCloseDrawer(" in script

    def test_rdi_on_filter_change_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiOnFilterChange(" in script

    def test_rdi_on_search_input_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiOnSearchInput(" in script

    def test_rdi_branch_filter_change_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiBranchFilterChange(" in script

    def test_rdi_show_no_project_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiShowNoProject(" in script

    def test_rdi_find_row_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiFindRow(" in script


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
        # Drawer should be closed before the main overlay
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
        # Must use createElement / textContent for project names
        assert "createElement" in body or "textContent" in body

    def test_on_project_change_resets_state(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiCursor = null" in body
        assert "_rdiSourceHead = null" in body
        assert "_rdiSelectedSHAs = new Set()" in body

    def test_on_project_change_calls_load_page(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiLoadPage(null)" in body


# ===========================================================================
# Data Loading Tests
# ===========================================================================


class TestDataLoading:
    """Test _rdiLoadPage behavior."""

    def test_load_page_uses_correct_endpoint(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "release-delivery/commits" in body

    def test_load_page_increments_generation(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "_rdiGen" in body

    def test_load_page_ignores_stale_responses(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "myGen" in body
        # The stale response is ignored by comparing myGen to _rdiGen
        assert "myGen !== _rdiGen" in body or "_rdiGen" in body

    def test_load_page_handles_source_changed_409(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "source_changed" in body
        assert "409" in body

    def test_load_page_handles_http_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "!resp.ok" in body

    def test_load_page_handles_network_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert ".catch(" in body

    def test_load_page_includes_filter_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "filter" in body
        assert "URLSearchParams" in body or "params.set" in body

    def test_load_page_includes_query_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "query" in body

    def test_load_page_includes_cursor_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "cursor" in body

    def test_load_page_includes_branches_param(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "branches" in body

    def test_refresh_resets_cursor_and_reloads(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRefresh")
        assert "_rdiCursor = null" in body
        assert "_rdiLoadPage(null)" in body

    def test_target_picker_disables_branch_when_all_selected_commits_are_delivered(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderTargetBranches")
        assert "hasUndeliveredCommit" in body
        assert "cb.disabled = !hasUndeliveredCommit" in body
        assert "already delivered" in body

    def test_tracker_only_rows_are_grouped_into_one_selectable_checkbox(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiGroupTrackerRows")
        assert "tracker_only" in body
        assert "member_shas" in body
        assert ".oompah tracker updates" in body


# ===========================================================================
# Status Rendering Tests
# ===========================================================================


class TestStatusRendering:
    """Test status cell rendering."""

    def test_render_cell_exists(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderCell(" in script

    def test_render_cell_uses_status_labels(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "_RDI_STATUS_LABELS" in body

    def test_render_cell_ancestry_shows_ancestry_label(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "ancestry" in body
        assert "Delivered (ancestry)" in body

    def test_render_cell_delivery_shows_cherry_pick_label(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "delivery" in body
        assert "Delivered (cherry-pick)" in body or "cherry-pick" in body

    def test_render_cell_ancestry_uses_distinct_css_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "rdi-cell-delivered-ancestry" in body

    def test_render_cell_active_states_clickable(self):
        """Active and delivered cells should be clickable to open the drawer."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "rdi-cell-clickable" in body

    def test_render_cell_clickable_uses_event_listener(self):
        """Clickable cells must use addEventListener, not onclick interpolation."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "addEventListener" in body

    def test_render_row_subject_uses_textcontent(self):
        """Subject must be set via textContent, never innerHTML from API data."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        # subject must be set with textContent
        assert "textContent" in body
        # innerHTML should not contain the word 'subject' (would indicate interpolation)
        # We check that no innerHTML = ... subject ... pattern exists
        import re
        # Look for innerHTML assignments in the row function
        bad_pattern = re.compile(r'innerHTML\s*=.*subject', re.DOTALL)
        assert not bad_pattern.search(body), "subject must not be interpolated into innerHTML"

    def test_render_row_merge_commit_gets_merge_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        assert "rdi-row-merge" in body
        assert "!row.selectable" in body or "selectable" in body

    def test_render_row_merge_commit_no_checkbox(self):
        """Merge commits should not have a selection checkbox."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        # The checkbox creation should be conditional on selectable
        assert "isMerge" in body or "selectable" in body

    def test_render_row_association_uses_dom(self):
        """Association identifier must be set via textContent/dataset, not onclick interpolation."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        # Should use dataset.identifier or textContent for the identifier
        assert "dataset.identifier" in body or "textContent" in body

    def test_render_row_association_opens_detail_panel(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        assert "openDetailPanel" in body

    def test_render_row_sha_url_link(self):
        """SHA should link to forge when sha_url is available."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        assert "sha_url" in body


# ===========================================================================
# No Untrusted Text in Onclick Tests
# ===========================================================================


class TestXSSPrevention:
    """Verify no untrusted API text is interpolated into event handlers."""

    def test_commit_subject_not_in_onclick(self):
        """Commit subjects (user-controlled text) must never appear in onclick attributes."""
        html = _load_dashboard_html()
        script = _load_dashboard_script()
        # In the render functions, check that no string like:
        # onclick="... ${row.subject} ..." or onclick="... + subject + ..."
        # appears
        import re
        # Check for subject being concatenated into onclick strings
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
        body = _function_body(script, "_rdiLoadPage")
        # The error path should use esc() for the message
        assert "esc(" in body

    def test_render_row_builds_dom_nodes(self):
        """_rdiRenderRow must use DOM node creation, not innerHTML for the row itself."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderRow")
        assert "createElement" in body

    def test_branch_names_use_dataset_not_onclick(self):
        """Branch names (from API) must use data attributes, not onclick interpolation."""
        script = _load_dashboard_script()
        rdi_section = script[script.index("openReleaseDelivery"):] if "openReleaseDelivery" in script else script
        # _rdiBranchFilterChange should be called via addEventListener, not onclick="...(branchName)"
        assert "data-branch" in rdi_section or "dataset.branch" in rdi_section


# ===========================================================================
# Selection Tests
# ===========================================================================


class TestSelection:
    """Test commit selection behavior."""

    def test_toggle_sha_adds_to_set(self):
        script = _load_dashboard_script()
        # _rdiToggleSHA delegates to _rdiToggleSHAs which holds the shared logic
        body = _function_body(script, "_rdiToggleSHAs")
        assert "_rdiSelectedSHAs.add(" in body

    def test_toggle_sha_removes_from_set(self):
        script = _load_dashboard_script()
        # _rdiToggleSHA delegates to _rdiToggleSHAs which holds the shared logic
        body = _function_body(script, "_rdiToggleSHAs")
        assert "_rdiSelectedSHAs.delete(" in body

    def test_toggle_sha_updates_action_bar(self):
        script = _load_dashboard_script()
        # _rdiToggleSHA delegates to _rdiToggleSHAs which holds the shared logic
        body = _function_body(script, "_rdiToggleSHAs")
        assert "_rdiUpdateActionBar()" in body

    def test_select_all_adds_selectable_rows(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiSelectAll")
        assert "_rdiSelectedSHAs.add(" in body
        assert "selectable" in body

    def test_select_all_skips_merge_rows(self):
        """Select-all must skip non-selectable (merge) rows."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiSelectAll")
        assert "selectable" in body
        # Should have a continue/skip check
        assert "continue" in body or "if (!row.selectable)" in body

    def test_clear_selection_empties_set(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiClearSelection")
        assert "_rdiSelectedSHAs = new Set()" in body

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

    def test_queue_requires_target_branches(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "targetBranches" in body
        assert "targetBranches.length === 0" in body

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

    def test_queue_sends_ordered_commits(self):
        """Commits must be sent in table row order."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "commits" in body
        assert "orderedSHAs" in body or "ordered" in body.lower()

    def test_queue_sends_target_branches(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "target_branches" in body

    def test_queue_clears_successful_selections_on_success(self):
        """After success, created/already_active/already_delivered SHAs are deselected."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "created" in body
        assert "already_active" in body
        assert "already_delivered" in body
        assert "_rdiSelectedSHAs.delete(" in body

    def test_queue_keeps_invalid_selections(self):
        """Invalid pairs remain selected so the operator can retry or investigate."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        # invalid pairs are NOT added to successSHAs — they stay in _rdiSelectedSHAs
        assert "invalid" in body

    def test_queue_shows_outcome_summary(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiShowOutcomeSummary" in body

    def test_queue_reloads_page_one_on_success(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiQueueSelected", is_async=True)
        assert "_rdiLoadPage(null)" in body

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
# Evidence Drawer Tests
# ===========================================================================


class TestEvidenceDrawer:
    """Test per-row evidence drawer."""

    def test_drawer_opens_with_full_sha(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "sha" in body
        assert "textContent" in body

    def test_drawer_shows_parents(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "parents" in body

    def test_drawer_shows_subject(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "subject" in body
        assert "textContent" in body

    def test_drawer_shows_author(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "author" in body.lower()

    def test_drawer_shows_association(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "association" in body

    def test_drawer_shows_per_branch_evidence(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "release_status" in body
        assert "branch" in body

    def test_drawer_shows_delivered_by_cherry_pick(self):
        """Cherry-pick deliveries must be labeled distinctly in the drawer."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "Delivered by cherry-pick" in body

    def test_drawer_shows_delivered_by_ancestry(self):
        """Ancestry deliveries must be labeled distinctly in the drawer."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "Delivered by ancestry" in body

    def test_drawer_shows_pr_link(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "pr_url" in body

    def test_drawer_shows_delivery_id(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "delivery_id" in body

    def test_drawer_shows_result_commits(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "result_commits" in body

    def test_drawer_builds_dom_nodes_not_innerhtml(self):
        """Drawer must use DOM creation for untrusted text (subject, author, etc.)."""
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOpenDrawer")
        assert "createElement" in body
        assert "textContent" in body

    def test_close_drawer_removes_open_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "classList.remove('open')" in body

    def test_close_drawer_clears_sha(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiCloseDrawer")
        assert "_rdiDrawerSHA = null" in body


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

    def test_filter_change_resets_cursor(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "_rdiCursor = null" in body

    def test_filter_change_reloads(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnFilterChange")
        assert "_rdiLoadPage(null)" in body

    def test_search_input_debounced(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "setTimeout" in body

    def test_search_input_updates_query(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "_rdiQuery" in body

    def test_search_input_resets_cursor(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiOnSearchInput")
        assert "_rdiCursor = null" in body

    def test_branch_filter_adds_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiBranchFilterChange")
        assert "_rdiVisibleBranches" in body
        assert "push(" in body

    def test_branch_filter_removes_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiBranchFilterChange")
        assert "filter(" in body

    def test_branch_filter_reloads(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiBranchFilterChange")
        assert "_rdiLoadPage(null)" in body


# ===========================================================================
# Empty / Error State Tests
# ===========================================================================


class TestEmptyErrorStates:
    """Test rendering for empty and error conditions."""

    def test_no_project_message_shown(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiShowNoProject")
        assert "rdi-no-project" in body

    def test_no_configured_branches_message(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderPage")
        assert "supported_release_branches" in body or "No release lines" in body

    def test_no_rows_message_shows_filter(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderPage")
        assert "rdi-empty" in body

    def test_load_page_error_shows_error_div(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "rdi-error" in body

    def test_source_changed_409_triggers_reload(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiLoadPage")
        assert "source_changed" in body
        assert "_rdiLoadPage(null)" in body


# ===========================================================================
# Pagination Tests
# ===========================================================================


class TestPagination:
    """Test pagination rendering."""

    def test_render_pagination_defined(self):
        script = _load_dashboard_script()
        assert "function _rdiRenderPagination(" in script

    def test_render_pagination_hides_when_no_next_cursor(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderPagination")
        assert "hidden" in body

    def test_render_pagination_shows_button_with_next_cursor(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderPagination")
        assert "nextCursor" in body
        assert "Load next page" in body or "button" in body

    def test_pagination_button_calls_load_page_with_cursor(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderPagination")
        assert "_rdiLoadPage" in body
        assert "next_cursor" in body or "nextCursor" in body


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
        # Find the rdi-overlay div and check its attributes
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

    def test_branch_filter_group_has_role(self):
        html = _load_dashboard_html()
        idx = html.index('id="rdi-branch-filters"')
        context = html[max(0, idx - 100) : idx + 200]
        assert 'role="group"' in context

    def test_clickable_cell_has_role_button(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert 'role="button"' in body or "setAttribute('role', 'button')" in body

    def test_clickable_cell_has_tabindex(self):
        script = _load_dashboard_script()
        body = _function_body(script, "_rdiRenderCell")
        assert "tabindex" in body or 'tabIndex' in body

    def test_close_btn_has_aria_label(self):
        html = _load_dashboard_html()
        assert 'aria-label="Close Release delivery"' in html

    def test_drawer_close_btn_has_aria_label(self):
        html = _load_dashboard_html()
        assert 'aria-label="Close commit details"' in html


# ===========================================================================
# Old RBI Code Removal Tests
# ===========================================================================


class TestLegacyCodeRemoved:
    """Verify all old Release branches inspector code is removed."""

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
