"""Tests for the Add Release Picks modal (TASK-456.3).

Verifies:
  1. The modal HTML elements are present in dashboard.html.
  2. The three JS functions (openAddReleasePicksDialog,
     closeAddReleasePicksDialog, submitAddReleasePicksDialog) are defined
     in the dashboard script block.
  3. The modal includes all required form controls.
  4. The JS function bodies contain the correct API calls and branching logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers shared with other dashboard tests
# ---------------------------------------------------------------------------


def _load_dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def _script_block(html: str) -> str:
    """Extract the main <script> block content (first full script tag)."""
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _function_body(script: str, name: str, async_: bool = False) -> str:
    """Return the content between { } of the named function definition."""
    prefix = f"async function {name}(" if async_ else f"function {name}("
    alt_prefix = f"async function {name}(" if not async_ else f"function {name}("
    try:
        start = script.index(prefix)
    except ValueError:
        start = script.index(alt_prefix)
    brace = script.index("{", start)
    depth = 0
    for pos in range(brace, len(script)):
        char = script[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : pos]
    raise AssertionError(f"Could not find function body for {name!r}")


@pytest.fixture(scope="module")
def dashboard_html() -> str:
    return _load_dashboard()


@pytest.fixture(scope="module")
def script(dashboard_html: str) -> str:
    return _script_block(dashboard_html)


@pytest.fixture(scope="module")
def open_body(script: str) -> str:
    return _function_body(script, "openAddReleasePicksDialog", async_=True)


@pytest.fixture(scope="module")
def close_body(script: str) -> str:
    return _function_body(script, "closeAddReleasePicksDialog")


@pytest.fixture(scope="module")
def submit_body(script: str) -> str:
    return _function_body(script, "submitAddReleasePicksDialog", async_=True)


# ---------------------------------------------------------------------------
# 1. HTML structure
# ---------------------------------------------------------------------------


class TestModalHtmlPresence:
    def test_modal_overlay_exists(self, dashboard_html):
        assert 'id="add-release-picks-dialog"' in dashboard_html

    def test_modal_has_aria_role(self, dashboard_html):
        assert 'role="dialog"' in dashboard_html
        assert 'aria-modal="true"' in dashboard_html

    def test_modal_has_title_element(self, dashboard_html):
        assert 'id="rp-dialog-title"' in dashboard_html
        assert "Add Release Picks" in dashboard_html

    def test_strategy_select_exists(self, dashboard_html):
        assert 'id="rp-strategy"' in dashboard_html

    def test_strategy_has_pr_commits_option(self, dashboard_html):
        assert 'value="pr_commits"' in dashboard_html

    def test_strategy_has_single_option(self, dashboard_html):
        assert 'value="single"' in dashboard_html

    def test_strategy_has_manual_option(self, dashboard_html):
        assert 'value="manual"' in dashboard_html

    def test_mode_schedule_radio_exists(self, dashboard_html):
        assert 'id="rp-mode-schedule"' in dashboard_html
        assert 'value="schedule"' in dashboard_html

    def test_mode_create_radio_exists(self, dashboard_html):
        assert 'id="rp-mode-create"' in dashboard_html
        assert 'value="create"' in dashboard_html

    def test_schedule_mode_is_default(self, dashboard_html):
        # The schedule radio should have 'checked' attribute
        assert 'id="rp-mode-schedule"' in dashboard_html
        # Find the schedule radio input tag and verify it has checked
        idx = dashboard_html.index('id="rp-mode-schedule"')
        snippet = dashboard_html[max(0, idx - 200) : idx + 200]
        assert "checked" in snippet

    def test_branches_list_container_exists(self, dashboard_html):
        assert 'id="rp-branches-list"' in dashboard_html

    def test_error_div_exists(self, dashboard_html):
        assert 'id="rp-error"' in dashboard_html

    def test_submit_button_exists(self, dashboard_html):
        assert 'id="rp-submit-btn"' in dashboard_html

    def test_submit_button_calls_submit_fn(self, dashboard_html):
        assert "submitAddReleasePicksDialog()" in dashboard_html

    def test_cancel_button_calls_close_fn(self, dashboard_html):
        assert "closeAddReleasePicksDialog()" in dashboard_html

    def test_overlay_click_closes_dialog(self, dashboard_html):
        # The overlay onclick should call closeAddReleasePicksDialog
        idx = dashboard_html.index('id="add-release-picks-dialog"')
        snippet = dashboard_html[idx : idx + 300]
        assert "closeAddReleasePicksDialog()" in snippet


# ---------------------------------------------------------------------------
# 2. Event bridge connecting openAddReleasePicksModal (TASK-456.2) to the modal
# ---------------------------------------------------------------------------


class TestEventBridge:
    def test_event_listener_registered_for_custom_event(self, script):
        """The dashboard script must listen for oompah:open-add-release-picks."""
        assert "oompah:open-add-release-picks" in script

    def test_event_bridge_forwards_to_open_dialog(self, script):
        """The event listener must call openAddReleasePicksDialog."""
        assert "openAddReleasePicksDialog" in script

    def test_event_bridge_passes_identifier(self, script):
        # The bridge extracts identifier from the event detail
        assert "identifier" in script

    def test_event_bridge_passes_project_id(self, script):
        # The bridge extracts projectId from the event detail
        assert "projectId" in script


# ---------------------------------------------------------------------------
# 3. JS function definitions
# ---------------------------------------------------------------------------


class TestJsFunctionsDefined:
    def test_open_function_defined(self, script):
        assert "async function openAddReleasePicksDialog(" in script

    def test_close_function_defined(self, script):
        assert "function closeAddReleasePicksDialog(" in script

    def test_submit_function_defined(self, script):
        assert "async function submitAddReleasePicksDialog(" in script

    def test_state_variable_rp_issue_identifier(self, script):
        assert "_rpIssueIdentifier" in script

    def test_state_variable_rp_project_id(self, script):
        assert "_rpProjectId" in script

    def test_state_variable_rp_existing_branches(self, script):
        assert "_rpExistingBranches" in script


# ---------------------------------------------------------------------------
# 3. openAddReleasePicksDialog body
# ---------------------------------------------------------------------------


class TestOpenFunctionBody:
    def test_fetches_project_branches(self, open_body):
        assert "/api/v1/projects/" in open_body

    def test_fetches_existing_picks(self, open_body):
        assert "issueApiUrl(" in open_body
        assert "release-picks" in open_body

    def test_filters_default_branch(self, open_body):
        assert "default_branch" in open_body

    def test_renders_checkboxes(self, open_body):
        assert "checkbox" in open_body

    def test_marks_already_tracked_branches(self, open_body):
        assert "already tracked" in open_body or "_rpExistingBranches" in open_body

    def test_handles_empty_branch_list(self, open_body):
        # Should show a message when no release branches are configured
        assert "No release branches configured" in open_body or "releaseBranches.length === 0" in open_body

    def test_opens_dialog(self, open_body):
        assert "classList.add('open')" in open_body

    def test_sets_state_identifier(self, open_body):
        assert "_rpIssueIdentifier = identifier" in open_body

    def test_sets_state_project_id(self, open_body):
        assert "_rpProjectId = projectId" in open_body

    def test_resets_error_div(self, open_body):
        assert "rp-error" in open_body


# ---------------------------------------------------------------------------
# 4. closeAddReleasePicksDialog body
# ---------------------------------------------------------------------------


class TestCloseFunctionBody:
    def test_removes_open_class(self, close_body):
        assert "classList.remove('open')" in close_body

    def test_clears_identifier(self, close_body):
        assert "_rpIssueIdentifier = null" in close_body

    def test_clears_project_id(self, close_body):
        assert "_rpProjectId = null" in close_body

    def test_clears_existing_branches(self, close_body):
        assert "_rpExistingBranches = new Set()" in close_body


# ---------------------------------------------------------------------------
# 5. submitAddReleasePicksDialog body
# ---------------------------------------------------------------------------


class TestSubmitFunctionBody:
    def test_guards_on_missing_identifier(self, submit_body):
        assert "if (!identifier" in submit_body or "if (!_rpIssueIdentifier" in submit_body

    def test_reads_selected_checkboxes(self, submit_body):
        assert "checkbox" in submit_body
        assert ":checked" in submit_body
        assert ":not(:disabled)" in submit_body

    def test_validates_at_least_one_branch_selected(self, submit_body):
        assert "Select at least one target branch" in submit_body

    def test_reads_mode_radio(self, submit_body):
        assert "rp-mode" in submit_body

    def test_maps_schedule_mode_to_waiting_status(self, submit_body):
        assert "waiting" in submit_body

    def test_maps_create_mode_to_task_created_status(self, submit_body):
        assert "task_created" in submit_body

    def test_reads_strategy(self, submit_body):
        assert "rp-strategy" in submit_body

    def test_calls_patch_endpoint(self, submit_body):
        assert "PATCH" in submit_body
        assert "release-picks" in submit_body

    def test_sends_project_id_in_body(self, submit_body):
        assert "project_id" in submit_body

    def test_sends_backports_list(self, submit_body):
        assert "backports" in submit_body

    def test_handles_api_error_response(self, submit_body):
        assert "if (!resp.ok)" in submit_body

    def test_shows_error_message_on_failure(self, submit_body):
        assert "rp-error" in submit_body

    def test_closes_dialog_on_success(self, submit_body):
        assert "closeAddReleasePicksDialog()" in submit_body

    def test_refreshes_detail_panel_on_success(self, submit_body):
        assert "openDetailPanel" in submit_body

    def test_disables_submit_button_while_in_flight(self, submit_body):
        assert "submitBtn.disabled = true" in submit_body

    def test_re_enables_submit_button_on_error(self, submit_body):
        # The button should be re-enabled if the request fails
        assert "submitBtn.disabled = false" in submit_body

    def test_handles_network_error(self, submit_body):
        assert "Network error" in submit_body or "catch" in submit_body
