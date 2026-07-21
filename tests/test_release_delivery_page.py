"""Tests for the dedicated Release Delivery page (OOMPAH-252).

Covers:
  - Server route: GET /release-delivery returns 200 with correct HTML
  - Navigation: dashboard has a nav entry linking to /release-delivery
  - No dashboard modal: old rdi-overlay dialog is absent from dashboard
  - Page structure: title, controls, URL persistence functions
  - URL persistence: _rdiReadUrl, _rdiPushUrl defined and used
  - Bootstrap: _rdiInit() called on page load
  - Accessibility: labelled controls, role attributes, focus management hooks
  - OOMPAH-251 integration: progress API, stale-while-revalidate, pagehide cleanup
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

_TEMPLATES = Path(__file__).resolve().parents[1] / "oompah" / "templates"


def _load_html(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _page_html() -> str:
    return _load_html("release_delivery.html")


def _page_script() -> str:
    html = _page_html()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _page_styles() -> str:
    html = _page_html()
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>")
    return html[start:end]


def _dashboard_html() -> str:
    return _load_html("dashboard.html")


def _function_body(script: str, name: str) -> str:
    """Extract the body of a top-level JS function by name."""
    marker = f"function {name}("
    start = script.index(marker)
    brace_open = script.index("{", start)
    depth = 0
    pos = brace_open
    while pos < len(script):
        if script[pos] == "{":
            depth += 1
        elif script[pos] == "}":
            depth -= 1
            if depth == 0:
                return script[brace_open : pos + 1]
        pos += 1
    return script[brace_open:]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Route tests
# ===========================================================================


class TestReleaseDeliveryRoute:
    """Server route tests for GET /release-delivery."""

    def test_route_returns_200(self, client):
        """Direct page load returns HTTP 200."""
        resp = client.get("/release-delivery")
        assert resp.status_code == 200

    def test_route_returns_html_content_type(self, client):
        """Response content-type is text/html."""
        resp = client.get("/release-delivery")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_route_body_is_not_empty(self, client):
        """Response body is non-empty HTML."""
        resp = client.get("/release-delivery")
        assert len(resp.text) > 100

    def test_route_contains_title(self, client):
        """Response body contains the page title."""
        resp = client.get("/release-delivery")
        assert "Release Delivery" in resp.text

    def test_route_contains_rdi_controls(self, client):
        """Response body contains the project/branch controls section."""
        resp = client.get("/release-delivery")
        assert "rdi-project-select" in resp.text

    def test_route_does_not_redirect(self, client):
        """GET /release-delivery serves the page directly, no redirect."""
        resp = client.get("/release-delivery", follow_redirects=False)
        assert resp.status_code == 200


# ===========================================================================
# Navigation entry tests
# ===========================================================================


class TestDashboardNavigation:
    """Dashboard has a persistent nav entry linking to /release-delivery."""

    def test_btn_release_delivery_present(self):
        """Dashboard toolbar has the Release delivery nav button."""
        html = _dashboard_html()
        assert 'id="btn-release-delivery"' in html

    def test_btn_links_to_release_delivery_page(self):
        """Nav button navigates to /release-delivery (not a dialog opener)."""
        html = _dashboard_html()
        assert "window.location='/release-delivery'" in html

    def test_btn_label(self):
        """Nav button label is 'Release delivery'."""
        html = _dashboard_html()
        assert ">Release delivery<" in html

    def test_old_modal_trigger_absent(self):
        """Dashboard button must NOT call openReleaseDelivery() anymore."""
        html = _dashboard_html()
        assert 'onclick="openReleaseDelivery()"' not in html

    def test_rdi_overlay_absent_from_dashboard(self):
        """The old modal overlay div is no longer in dashboard.html."""
        html = _dashboard_html()
        assert 'id="rdi-overlay"' not in html

    def test_rdi_js_absent_from_dashboard(self):
        """Release delivery JS functions are absent from dashboard (moved to page)."""
        html = _dashboard_html()
        assert "function _rdiLoadBacklog(" not in html
        assert "function _rdiRenderBacklog(" not in html

    def test_rdi_css_absent_from_dashboard(self):
        """Release delivery CSS is absent from dashboard (moved to page)."""
        html = _dashboard_html()
        assert ".rdi-table {" not in html
        assert ".rdi-action-bar" not in html


# ===========================================================================
# Page title and structure tests
# ===========================================================================


class TestPageStructure:
    """Verify the basic HTML structure of the dedicated page."""

    def test_page_title(self):
        """Browser tab title is 'oompah - Release Delivery'."""
        html = _page_html()
        assert "<title>oompah - Release Delivery</title>" in html

    def test_toolbar_heading(self):
        """Toolbar heading contains 'Release Delivery'."""
        html = _page_html()
        assert "Release Delivery" in html

    def test_back_to_dashboard_link(self):
        """Page has a button/link back to the Dashboard."""
        html = _page_html()
        assert "window.location='/'" in html or "href='/'" in html

    def test_project_selector_present(self):
        html = _page_html()
        assert 'id="rdi-project-select"' in html

    def test_branch_selector_present(self):
        html = _page_html()
        assert 'id="rdi-branch-select"' in html

    def test_filter_controls_present(self):
        html = _page_html()
        assert 'name="rdi-filter"' in html

    def test_search_input_present(self):
        html = _page_html()
        assert 'id="rdi-search"' in html

    def test_candidate_body_region_present(self):
        html = _page_html()
        assert 'id="rdi-body"' in html

    def test_action_bar_present(self):
        html = _page_html()
        assert 'id="rdi-action-bar"' in html

    def test_outcome_banner_present(self):
        html = _page_html()
        assert 'id="rdi-outcome"' in html

    def test_evidence_drawer_present(self):
        html = _page_html()
        assert 'id="rdi-drawer"' in html

    def test_refresh_status_banner_present(self):
        html = _page_html()
        assert 'id="rdi-refresh-status"' in html

    def test_no_rdi_overlay_div(self):
        """Page is a first-class page, not a dialog overlay."""
        html = _page_html()
        assert 'id="rdi-overlay"' not in html


# ===========================================================================
# URL persistence tests
# ===========================================================================


class TestURLPersistence:
    """URL-based project/branch selection and history API."""

    def test_rdi_read_url_defined(self):
        """_rdiReadUrl() reads project and branch from URL params."""
        script = _page_script()
        assert "function _rdiReadUrl(" in script

    def test_rdi_push_url_defined(self):
        """_rdiPushUrl() writes project+branch selection to the URL."""
        script = _page_script()
        assert "function _rdiPushUrl(" in script

    def test_rdi_read_url_reads_project_param(self):
        script = _page_script()
        body = _function_body(script, "_rdiReadUrl")
        assert "project" in body
        assert "URLSearchParams" in body or "searchParams" in body

    def test_rdi_read_url_reads_branch_param(self):
        script = _page_script()
        body = _function_body(script, "_rdiReadUrl")
        assert "branch" in body

    def test_rdi_push_url_uses_history_replace_state(self):
        """URL is updated without adding a history entry."""
        script = _page_script()
        body = _function_body(script, "_rdiPushUrl")
        assert "history.replaceState" in body or "replaceState" in body

    def test_rdi_push_url_sets_project_param(self):
        script = _page_script()
        body = _function_body(script, "_rdiPushUrl")
        assert "project" in body

    def test_rdi_push_url_sets_branch_param(self):
        script = _page_script()
        body = _function_body(script, "_rdiPushUrl")
        assert "branch" in body

    def test_on_project_change_calls_push_url(self):
        """Project selection change updates the URL."""
        script = _page_script()
        body = _function_body(script, "_rdiOnProjectChange")
        assert "_rdiPushUrl" in body

    def test_on_branch_change_calls_push_url(self):
        """Branch selection change updates the URL."""
        script = _page_script()
        body = _function_body(script, "_rdiOnBranchChange")
        assert "_rdiPushUrl" in body

    def test_populate_project_reads_url_for_initial_selection(self):
        """On page load, project is selected from URL params."""
        script = _page_script()
        body = _function_body(script, "_rdiPopulateProject")
        assert "_rdiReadUrl" in body or "urlProject" in body


# ===========================================================================
# Bootstrap tests
# ===========================================================================


class TestBootstrap:
    """_rdiInit() is called on page load to bootstrap the page."""

    def test_rdi_init_defined(self):
        script = _page_script()
        assert "function _rdiInit(" in script or "async function _rdiInit(" in script

    def test_rdi_init_called_at_end_of_script(self):
        """_rdiInit() is invoked at the end of the script block."""
        script = _page_script()
        assert "_rdiInit()" in script

    def test_rdi_init_fetches_projects(self):
        """_rdiInit() fetches the project list from the API."""
        script = _page_script()
        body = _function_body(script, "_rdiInit")
        assert "/api/v1/projects" in body

    def test_rdi_init_calls_populate_project(self):
        """_rdiInit() calls _rdiPopulateProject() after fetching projects."""
        script = _page_script()
        body = _function_body(script, "_rdiInit")
        assert "_rdiPopulateProject(" in body

    def test_no_open_release_delivery(self):
        """openReleaseDelivery is not defined; page initialises via _rdiInit."""
        script = _page_script()
        assert "function openReleaseDelivery(" not in script

    def test_no_close_release_delivery(self):
        """closeReleaseDelivery is not defined; navigation replaces dialog close."""
        script = _page_script()
        assert "function closeReleaseDelivery(" not in script


# ===========================================================================
# OOMPAH-251 progress integration tests
# ===========================================================================


class TestProgressIntegration:
    """OOMPAH-251 async refresh model is integrated into the dedicated page."""

    def test_force_refresh_defined(self):
        script = _page_script()
        assert "function _rdiForceRefresh(" in script or "async function _rdiForceRefresh(" in script

    def test_rdi_refresh_wrapper_defined(self):
        """_rdiRefresh() is the thin wrapper called by the toolbar button."""
        script = _page_script()
        assert "function _rdiRefresh(" in script

    def test_rdi_refresh_delegates_to_force_refresh(self):
        script = _page_script()
        body = _function_body(script, "_rdiRefresh")
        assert "_rdiForceRefresh()" in body

    def test_poll_status_defined(self):
        script = _page_script()
        assert "function _rdiPollStatus(" in script

    def test_start_poll_defined(self):
        script = _page_script()
        assert "function _rdiStartPoll(" in script

    def test_stop_poll_defined(self):
        script = _page_script()
        assert "function _rdiStopPoll(" in script

    def test_update_refresh_status_defined(self):
        script = _page_script()
        assert "function _rdiUpdateRefreshStatus(" in script

    def test_pagehide_stops_polling(self):
        """Navigating away stops the polling timer to prevent background fetch leaks."""
        script = _page_script()
        assert "pagehide" in script
        assert "_rdiStopPoll()" in script

    def test_load_backlog_uses_stale_while_revalidate(self):
        """Stale result remains visible while a refresh is in progress."""
        script = _page_script()
        body = _function_body(script, "_rdiLoadBacklog")
        assert "_rdiCurrentData" in body

    def test_force_refresh_does_not_wipe_stale_data(self):
        """_rdiForceRefresh must not clear _rdiCurrentData (stale-while-revalidate)."""
        script = _page_script()
        body = _function_body(script, "_rdiForceRefresh")
        assert "_rdiCurrentData = null" not in body

    def test_refresh_status_banner_shows_progress(self):
        """Progress banner contains phase, bar-fill and elapsed elements."""
        html = _page_html()
        assert "rdi-refresh-phase" in html
        assert "rdi-refresh-bar-fill" in html

    def test_retry_button_present(self):
        """Retry button is shown when refresh fails."""
        html = _page_html()
        assert 'id="rdi-refresh-retry"' in html


# ===========================================================================
# Empty-state tests
# ===========================================================================


class TestEmptyStates:
    """Invalid / unavailable selections show actionable empty states."""

    def test_show_no_project_defined(self):
        script = _page_script()
        assert "function _rdiShowNoProject(" in script

    def test_show_no_branch_defined(self):
        script = _page_script()
        assert "function _rdiShowNoBranch(" in script

    def test_show_no_project_renders_message(self):
        script = _page_script()
        body = _function_body(script, "_rdiShowNoProject")
        assert "rdi-no-project" in body or "No project" in body or "Select a project" in body

    def test_show_no_branch_renders_message(self):
        script = _page_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "Select a release branch" in body or "rdi-no-branch" in body or "No branch" in body

    def test_show_no_branch_stops_poll(self):
        """Empty state must stop any running poll (OOMPAH-251 contract)."""
        script = _page_script()
        body = _function_body(script, "_rdiShowNoBranch")
        assert "_rdiStopPoll()" in body


# ===========================================================================
# Accessibility tests
# ===========================================================================


class TestPageAccessibility:
    """Accessible labels, roles, and keyboard support on the dedicated page."""

    def test_project_select_has_aria_label(self):
        html = _page_html()
        assert 'aria-label="Select project"' in html

    def test_branch_select_has_aria_label(self):
        html = _page_html()
        assert 'aria-label="Select release branch"' in html

    def test_filter_group_has_radiogroup_role(self):
        html = _page_html()
        assert 'role="radiogroup"' in html

    def test_filter_group_has_aria_label(self):
        html = _page_html()
        assert 'aria-label="Item filter"' in html

    def test_search_has_aria_label(self):
        html = _page_html()
        assert 'aria-label="Search items"' in html

    def test_candidate_region_has_aria_live(self):
        html = _page_html()
        assert 'aria-live="polite"' in html

    def test_candidate_region_has_role_region(self):
        html = _page_html()
        assert 'role="region"' in html

    def test_refresh_status_has_role_status(self):
        html = _page_html()
        assert 'role="status"' in html

    def test_drawer_has_role_dialog(self):
        html = _page_html()
        idx = html.index('id="rdi-drawer"')
        context = html[max(0, idx - 100) : idx + 400]
        assert 'role="dialog"' in context

    def test_drawer_has_aria_modal(self):
        html = _page_html()
        idx = html.index('id="rdi-drawer"')
        context = html[max(0, idx - 100) : idx + 400]
        assert 'aria-modal="true"' in context

    def test_drawer_close_button_has_aria_label(self):
        html = _page_html()
        assert 'aria-label="Close item details"' in html

    def test_escape_closes_drawer(self):
        """Keyboard Escape closes the evidence drawer."""
        script = _page_script()
        assert "Escape" in script
        assert "_rdiCloseDrawer" in script

    def test_item_checkbox_gets_aria_label(self):
        """Row checkboxes are programmatically labelled."""
        script = _page_script()
        assert 'aria-label' in script
        assert 'Select item' in script or "'Select item '" in script

    def test_identifier_span_gets_tabindex(self):
        """Identifier spans are keyboard-focusable."""
        script = _page_script()
        assert "tabindex" in script or 'tabIndex' in script

    def test_identifier_span_gets_aria_label(self):
        """Identifier spans have accessible labels."""
        script = _page_script()
        assert "Open" in script and "details" in script


# ===========================================================================
# OOMPAH-292: Summary in rows, drawer width, full task detail
# ===========================================================================

class TestItemSummaryInRow:
    """Tests that item summaries are rendered in Release Delivery item rows."""

    def test_rdi_item_summary_css_class_defined(self):
        """The .rdi-item-summary CSS class is defined in the page styles."""
        styles = _page_styles()
        assert ".rdi-item-summary" in styles

    def test_rdi_item_summary_rendered_when_present(self):
        """The JS row renderer appends a summary span when item.summary is set."""
        script = _page_script()
        assert "rdi-item-summary" in script
        assert "item.summary" in script

    def test_rdi_item_summary_uses_text_content_not_innerHTML(self):
        """Summary text is set via textContent (not innerHTML) for HTML safety."""
        script = _page_script()
        # Find the block that handles item.summary
        idx = script.find("rdi-item-summary")
        assert idx >= 0
        # After the class assignment, textContent must be used, not innerHTML
        context = script[idx : idx + 500]
        assert "textContent" in context

    def test_rdi_item_summary_has_aria_label(self):
        """Summary span has an aria-label for screen-reader accessibility."""
        script = _page_script()
        idx = script.find("rdi-item-summary")
        context = script[idx : idx + 600]
        assert "aria-label" in context

    def test_rdi_item_summary_only_when_present(self):
        """Summary element is only appended when item.summary is truthy."""
        script = _page_script()
        idx = script.find("item.summary")
        assert idx >= 0
        # There must be a conditional check (if item.summary)
        context = script[max(0, idx - 50) : idx + 20]
        assert "if" in context


class TestDrawerWidth:
    """Tests for the drawer width change (OOMPAH-292 / OOMPAH-263 parity)."""

    def test_drawer_panel_uses_min_800px_40vw(self):
        """The drawer panel uses min(800px, 40vw) matching the dashboard detail panel."""
        styles = _page_styles()
        assert "min(800px, 40vw)" in styles

    def test_drawer_panel_retains_max_width_fallback(self):
        """The drawer panel retains a max-width fallback for narrow viewports."""
        styles = _page_styles()
        # max-width must be set to handle very narrow viewports
        assert "max-width:" in styles
        # The fallback must be ≥ 90vw or similar (not narrower than usable)
        assert "90vw" in styles

    def test_drawer_no_longer_uses_420px_fixed_width(self):
        """The old hard-coded 420px width has been removed from the drawer panel."""
        styles = _page_styles()
        # The 420px value must not appear as the primary width
        # (it may appear in other contexts but not as `.rdi-drawer-panel { width: 420px }`)
        idx = styles.find(".rdi-drawer-panel")
        assert idx >= 0
        # Extract the rule block
        brace = styles.index("{", idx)
        end = styles.index("}", brace)
        rule = styles[brace:end]
        assert "420px" not in rule


class TestFullTaskDetailInDrawer:
    """Tests for the full task detail loaded in the evidence drawer (OOMPAH-292)."""

    def test_fetch_task_detail_function_defined(self):
        """_rdiFetchTaskDetail() async function is defined in the page script."""
        script = _page_script()
        assert "function _rdiFetchTaskDetail(" in script or "async function _rdiFetchTaskDetail(" in script

    def test_fetch_task_detail_calls_detail_endpoint(self):
        """_rdiFetchTaskDetail fetches /api/v1/issues/{identifier}/detail."""
        script = _page_script()
        assert "/detail" in script
        assert "identifier" in script

    def test_fetch_task_detail_passes_project_id(self):
        """_rdiFetchTaskDetail includes project_id in the detail request."""
        script = _page_script()
        body = _function_body(script, "_rdiFetchTaskDetail")
        assert "project_id" in body

    def test_render_task_detail_function_defined(self):
        """_rdiRenderTaskDetail() renders the core task fields."""
        script = _page_script()
        assert "function _rdiRenderTaskDetail(" in script

    def test_render_task_detail_shows_title(self):
        """_rdiRenderTaskDetail renders the task title field."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "title" in body.lower()

    def test_render_task_detail_shows_state(self):
        """_rdiRenderTaskDetail renders the task state field."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "state" in body

    def test_render_task_detail_shows_priority(self):
        """_rdiRenderTaskDetail renders the task priority field."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "priority" in body.lower()

    def test_render_task_detail_shows_labels(self):
        """_rdiRenderTaskDetail renders labels."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "labels" in body.lower()

    def test_render_task_detail_shows_type(self):
        """_rdiRenderTaskDetail renders the task type (issue_type)."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "issue_type" in body or "type" in body.lower()

    def test_render_task_detail_shows_description(self):
        """_rdiRenderTaskDetail renders the task description."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "description" in body.lower()

    def test_render_task_detail_shows_children(self):
        """_rdiRenderTaskDetail renders children for epics."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "children" in body.lower()

    def test_render_task_detail_shows_comments(self):
        """_rdiRenderTaskDetail renders comments."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "comments" in body.lower()

    def test_render_task_detail_shows_source_links(self):
        """_rdiRenderTaskDetail renders source/repository URL links."""
        script = _page_script()
        body = _function_body(script, "_rdiRenderTaskDetail")
        assert "url" in body.lower()

    def test_drawer_shows_loading_state_while_fetching(self):
        """_rdiOpenItemDrawer shows a loading message before detail fetch completes."""
        script = _page_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        assert "Loading" in body or "loading" in body

    def test_drawer_error_displayed_safely(self):
        """_rdiFetchTaskDetail renders errors without using innerHTML for error text."""
        script = _page_script()
        body = _function_body(script, "_rdiFetchTaskDetail")
        # Error messages must be rendered safely (via textContent or _rdiEsc helper)
        assert "rdi-drawer-error" in body

    def test_delivery_evidence_preserved_in_drawer(self):
        """Delivery evidence is kept visible when task details are loading/errored."""
        script = _page_script()
        body = _function_body(script, "_rdiOpenItemDrawer")
        # The delivery section must be built and appended BEFORE awaiting detail fetch
        assert "_rdiBuildDeliverySection" in body or "deliverySection" in body

    def test_build_delivery_section_function_defined(self):
        """_rdiBuildDeliverySection() is defined and builds the evidence block."""
        script = _page_script()
        assert "function _rdiBuildDeliverySection(" in script

    def test_esc_helper_defined_for_error_sanitisation(self):
        """_rdiEsc() string-escape helper is defined for safe error display."""
        script = _page_script()
        assert "function _rdiEsc(" in script
