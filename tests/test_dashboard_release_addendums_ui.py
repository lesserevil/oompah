"""Tests for the release-addendum selection and status UI (OOMPAH-180).

Covers section 7 (Task detail) of plans/release-branch-addendums.md:

  CSS:
  - All .release-addendum-* CSS classes present
  - Status-variant classes for open, in_progress, in_review, blocked, merged, archived

  renderReleaseAddendumsSection():
  - Function is defined
  - Renders target_branch (branch chip), status badge, PR link, blocked error
  - Does NOT render child-task link (no entry.task_id / release-pick-task-link)
  - Shows "Add release branches" button only when task state is Merged
  - Renders empty state when no addendums
  - Calls openAddReleaseBranchesDialog (not the old release-picks modal)

  openDetailPanel() integration:
  - Fetches /release-addendums in parallel with /release-picks
  - Calls renderReleaseAddendumsSection with fetched data and task state
  - Gracefully degrades on addendums fetch failure

  Add release branches dialog HTML:
  - Dialog overlay with correct id and aria attributes
  - fieldset/legend accessible checkbox group
  - Stale warning element
  - Error element (hidden by default)
  - Cancel button and "Queue release merges" submit button

  openAddReleaseBranchesDialog():
  - Function defined
  - Fetches /release-addendums to determine active targets
  - Fetches /release-branches catalog
  - Renders checkboxes for available branches
  - Prechecks and disables active (non-archived, non-merged) selections
  - Opens dialog and focuses first interactive element
  - Shows stale warning when catalog is stale
  - Handles empty branch list with empty-state message
  - Handles catalog fetch error

  closeAddReleaseBranchesDialog():
  - Removes 'open' class
  - Clears module-level state variables

  submitAddReleaseBranchesDialog():
  - Reads selected (non-disabled) checkboxes
  - Validates at least one branch selected
  - Sends POST to /release-addendums with target_branches array and idempotency_key
  - Sends all selected branches in ONE request (acceptance criterion)
  - Includes project_id in request body
  - Disables submit button while request is outstanding
  - Re-enables on error
  - Closes dialog on success
  - Refreshes task detail panel (refresh-to-open after success)

  Escape-to-close:
  - Keydown listener registered for Escape key
"""

from __future__ import annotations

from pathlib import Path


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
                return script[brace + 1 : pos]
    raise AssertionError(f"Could not find function body for {name}")


# ---------------------------------------------------------------------------
# CSS: release addendum classes
# ---------------------------------------------------------------------------


class TestReleaseAddendumCss:
    def test_css_defines_release_addendum_list(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-list" in styles

    def test_css_defines_release_addendum_entry(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-entry" in styles

    def test_css_defines_release_addendum_branch(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-branch" in styles

    def test_css_defines_release_addendum_status(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status" in styles

    def test_css_defines_status_open(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status-open" in styles

    def test_css_defines_status_in_progress(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status-in_progress" in styles

    def test_css_defines_status_in_review(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status-in_review" in styles

    def test_css_defines_status_blocked(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status-blocked" in styles

    def test_css_defines_status_merged(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status-merged" in styles

    def test_css_defines_status_archived(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-status-archived" in styles

    def test_css_defines_release_addendum_pr_link(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-pr-link" in styles

    def test_css_defines_release_addendum_error(self):
        styles = _load_dashboard_styles()
        assert ".release-addendum-error" in styles

    def test_css_defines_rab_fieldset(self):
        """CSS must style the accessible fieldset used in the dialog."""
        styles = _load_dashboard_styles()
        assert ".rab-fieldset" in styles

    def test_css_defines_rab_legend(self):
        styles = _load_dashboard_styles()
        assert ".rab-legend" in styles

    def test_css_defines_rab_stale_warning(self):
        styles = _load_dashboard_styles()
        assert ".rab-stale-warning" in styles


# ---------------------------------------------------------------------------
# renderReleaseAddendumsSection()
# ---------------------------------------------------------------------------


class TestRenderReleaseAddendumsSection:
    def test_function_is_defined(self):
        script = _load_dashboard_script()
        assert "function renderReleaseAddendumsSection(" in script

    def test_renders_target_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "entry.target_branch" in body
        assert "release-addendum-branch" in body

    def test_renders_status_badge(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "entry.status" in body
        assert "release-addendum-status" in body

    def test_renders_pr_link(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "entry.pr_url" in body
        assert "release-addendum-pr-link" in body
        assert "target=" in body

    def test_renders_blocked_error(self):
        """Blocked error must be shown when status is 'blocked' and error is set."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "entry.error" in body
        assert "release-addendum-error" in body
        assert "blocked" in body

    def test_no_child_task_link(self):
        """The new renderer must NOT render a child-task link (no entry.task_id)."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "entry.task_id" not in body, (
            "renderReleaseAddendumsSection must not render child-task links"
        )
        assert "release-pick-task-link" not in body, (
            "renderReleaseAddendumsSection must not use release-pick-task-link CSS class"
        )

    def test_no_backport_of(self):
        """The new renderer must NOT render a backport_of link."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "backportOf" not in body
        assert "backport_of" not in body

    def test_shows_add_button_for_merged_tasks(self):
        """'Add release branches' button must appear only for Merged tasks."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "Merged" in body, (
            "renderReleaseAddendumsSection must conditionally show button for Merged state"
        )
        assert "taskState" in body, (
            "renderReleaseAddendumsSection must check taskState to gate the button"
        )

    def test_add_button_calls_new_dialog(self):
        """The 'Add release branches' button must call openAddReleaseBranchesDialog."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "openAddReleaseBranchesDialog(" in body

    def test_add_button_text(self):
        """The button text must say 'Add release branches'."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "Add release branches" in body

    def test_section_heading(self):
        """Section label must say 'Release addendums', not 'Release Picks'."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        assert "Release addendums" in body

    def test_empty_state_message(self):
        """Must show an empty-state message when no addendums exist."""
        script = _load_dashboard_script()
        body = _function_body(script, "renderReleaseAddendumsSection")
        body_lower = body.lower()
        assert "no release addendum" in body_lower, (
            "renderReleaseAddendumsSection must show a message when no addendums exist"
        )


# ---------------------------------------------------------------------------
# openDetailPanel() integration
# ---------------------------------------------------------------------------


class TestOpenDetailPanelAddendumIntegration:
    def test_fetches_release_addendums_endpoint(self):
        """openDetailPanel must fetch /release-addendums in parallel."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        assert "release-addendums" in body

    def test_addendums_fetch_starts_before_await(self):
        """The /release-addendums fetch must start before the first await."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        ra_pos = body.find("release-addendums")
        first_await = body.find("await fetch")
        assert ra_pos < first_await, (
            "The /release-addendums fetch must start before the first 'await fetch'"
        )

    def test_addendums_fetch_degrades_gracefully(self):
        """openDetailPanel must handle addendums fetch failure gracefully."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        ra_idx = body.find("release-addendums")
        after_ra = body[ra_idx:]
        assert ".catch(" in after_ra or "try {" in after_ra, (
            "openDetailPanel must handle /release-addendums fetch failures gracefully"
        )

    def test_calls_render_release_addendums_section(self):
        """openDetailPanel must call renderReleaseAddendumsSection."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        assert "renderReleaseAddendumsSection(" in body

    def test_passes_addendum_data_to_renderer(self):
        """openDetailPanel must pass the fetched addendum data to renderReleaseAddendumsSection."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        render_call_pos = body.index("renderReleaseAddendumsSection(")
        render_call = body[render_call_pos : render_call_pos + 100]
        assert any(varname in render_call for varname in ["_raData", "raData", "addendumData"]), (
            "openDetailPanel must pass the fetched addendum data to renderReleaseAddendumsSection"
        )

    def test_passes_task_state_to_renderer(self):
        """openDetailPanel must pass the task state to renderReleaseAddendumsSection."""
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel", is_async=True)
        render_call_pos = body.index("renderReleaseAddendumsSection(")
        render_call = body[render_call_pos : render_call_pos + 120]
        assert "detail.state" in render_call or "taskState" in render_call or "state" in render_call, (
            "openDetailPanel must pass the task state to renderReleaseAddendumsSection"
        )


# ---------------------------------------------------------------------------
# Add release branches dialog HTML
# ---------------------------------------------------------------------------


class TestAddReleaseBranchesDialogHtml:
    def test_dialog_overlay_exists(self):
        html = _load_dashboard_html()
        assert 'id="add-release-branches-dialog"' in html

    def test_dialog_has_aria_role(self):
        html = _load_dashboard_html()
        idx = html.index('id="add-release-branches-dialog"')
        snippet = html[idx : idx + 300]
        assert 'role="dialog"' in snippet
        assert 'aria-modal="true"' in snippet

    def test_dialog_has_aria_labelledby(self):
        html = _load_dashboard_html()
        assert 'aria-labelledby="rab-dialog-title"' in html

    def test_dialog_has_title_element(self):
        html = _load_dashboard_html()
        assert 'id="rab-dialog-title"' in html
        assert "Add release branches" in html

    def test_dialog_has_fieldset(self):
        """The branch list must use a fieldset for accessible checkbox group."""
        html = _load_dashboard_html()
        assert 'id="rab-branches-fieldset"' in html
        assert "<fieldset" in html

    def test_dialog_has_legend(self):
        """The fieldset must include a legend describing the group."""
        html = _load_dashboard_html()
        assert "Target release branches" in html

    def test_dialog_has_stale_warning(self):
        html = _load_dashboard_html()
        assert 'id="rab-stale-warning"' in html

    def test_stale_warning_hidden_by_default(self):
        html = _load_dashboard_html()
        idx = html.index('id="rab-stale-warning"')
        snippet = html[max(0, idx - 10) : idx + 200]
        assert "hidden" in snippet

    def test_dialog_has_error_div(self):
        html = _load_dashboard_html()
        assert 'id="rab-error"' in html

    def test_error_div_hidden_by_default(self):
        html = _load_dashboard_html()
        idx = html.index('id="rab-error"')
        snippet = html[max(0, idx - 10) : idx + 150]
        assert "hidden" in snippet

    def test_dialog_has_cancel_button(self):
        html = _load_dashboard_html()
        assert 'id="rab-cancel-btn"' in html

    def test_cancel_button_calls_close(self):
        html = _load_dashboard_html()
        assert "closeAddReleaseBranchesDialog()" in html

    def test_dialog_has_submit_button(self):
        html = _load_dashboard_html()
        assert 'id="rab-submit-btn"' in html

    def test_submit_button_says_queue_release_merges(self):
        html = _load_dashboard_html()
        assert "Queue release merges" in html

    def test_submit_button_calls_submit_fn(self):
        html = _load_dashboard_html()
        assert "submitAddReleaseBranchesDialog()" in html

    def test_overlay_click_closes_dialog(self):
        html = _load_dashboard_html()
        idx = html.index('id="add-release-branches-dialog"')
        snippet = html[idx : idx + 300]
        assert "closeAddReleaseBranchesDialog()" in snippet


# ---------------------------------------------------------------------------
# JS function definitions
# ---------------------------------------------------------------------------


class TestJsFunctionsDefined:
    def test_open_function_defined(self):
        script = _load_dashboard_script()
        assert "async function openAddReleaseBranchesDialog(" in script

    def test_close_function_defined(self):
        script = _load_dashboard_script()
        assert "function closeAddReleaseBranchesDialog(" in script

    def test_submit_function_defined(self):
        script = _load_dashboard_script()
        assert "async function submitAddReleaseBranchesDialog(" in script

    def test_state_variable_rab_issue_identifier(self):
        script = _load_dashboard_script()
        assert "_rabIssueIdentifier" in script

    def test_state_variable_rab_project_id(self):
        script = _load_dashboard_script()
        assert "_rabProjectId" in script

    def test_state_variable_rab_active_targets(self):
        script = _load_dashboard_script()
        assert "_rabActiveTargets" in script


# ---------------------------------------------------------------------------
# openAddReleaseBranchesDialog() body
# ---------------------------------------------------------------------------


class TestOpenAddReleaseBranchesDialogBody:
    def test_sets_state_identifier(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "_rabIssueIdentifier = identifier" in body

    def test_sets_state_project_id(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "_rabProjectId = projectId" in body

    def test_fetches_existing_addendums(self):
        """Must fetch /release-addendums to determine which branches are already active."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "release-addendums" in body

    def test_fetches_release_branch_catalog(self):
        """Must fetch the /release-branches catalog endpoint."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "release-branches" in body

    def test_renders_checkboxes_for_branches(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "checkbox" in body

    def test_prechecks_and_disables_active_selections(self):
        """Active (non-archived, non-merged) branches must be prechecked and disabled."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "_rabActiveTargets" in body
        assert "disabled" in body
        assert "checked" in body

    def test_marks_active_branches(self):
        """Active branches must be visually marked (e.g. 'active' badge)."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "active" in body

    def test_opens_dialog(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "classList.add('open')" in body

    def test_resets_error_div(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "rab-error" in body

    def test_shows_stale_warning_when_stale(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "stale" in body
        assert "rab-stale-warning" in body

    def test_empty_state_when_no_available_branches(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        lower = body.lower()
        assert "no supported release" in lower or "no release branch" in lower or "length === 0" in body

    def test_handles_catalog_fetch_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "catch" in body or "Failed to load" in body

    def test_filters_only_available_branches(self):
        """Only branches with available=true from the catalog may be rendered as selectable."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "available" in body

    def test_focuses_first_element_on_open(self):
        """Dialog must focus the first interactive element after opening."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "focus()" in body

    def test_active_target_uses_status_not_archived_not_merged(self):
        """Active targets exclude archived and merged addendums only."""
        script = _load_dashboard_script()
        body = _function_body(script, "openAddReleaseBranchesDialog", is_async=True)
        assert "archived" in body
        assert "merged" in body


# ---------------------------------------------------------------------------
# closeAddReleaseBranchesDialog() body
# ---------------------------------------------------------------------------


class TestCloseAddReleaseBranchesDialogBody:
    def test_removes_open_class(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeAddReleaseBranchesDialog")
        assert "classList.remove('open')" in body

    def test_clears_identifier(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeAddReleaseBranchesDialog")
        assert "_rabIssueIdentifier = null" in body

    def test_clears_project_id(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeAddReleaseBranchesDialog")
        assert "_rabProjectId = null" in body

    def test_clears_active_targets(self):
        script = _load_dashboard_script()
        body = _function_body(script, "closeAddReleaseBranchesDialog")
        assert "_rabActiveTargets = new Set()" in body


# ---------------------------------------------------------------------------
# submitAddReleaseBranchesDialog() body
# ---------------------------------------------------------------------------


class TestSubmitAddReleaseBranchesDialogBody:
    def test_guards_on_missing_identifier(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "if (!identifier" in body or "if (!_rabIssueIdentifier" in body

    def test_reads_selected_non_disabled_checkboxes(self):
        """Must only collect non-disabled checked checkboxes (active selections excluded)."""
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "checkbox" in body
        assert ":checked" in body
        assert ":not(:disabled)" in body

    def test_validates_at_least_one_branch(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "Select at least one target branch" in body

    def test_calls_post_endpoint(self):
        """Submit must call POST /release-addendums (not the old /release-picks)."""
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "POST" in body
        assert "release-addendums" in body

    def test_sends_target_branches_array(self):
        """The POST body must include target_branches (not backports list)."""
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "target_branches" in body

    def test_does_not_send_backports_key(self):
        """Must use the new release-addendums API shape, not the old backports format."""
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "backports" not in body, (
            "submitAddReleaseBranchesDialog must not send the old 'backports' key"
        )

    def test_sends_idempotency_key(self):
        """Request must include an idempotency_key for safe retries."""
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "idempotency_key" in body

    def test_sends_project_id(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "project_id" in body

    def test_sends_all_branches_in_one_request(self):
        """All selected branches must be submitted in a SINGLE POST request.

        This is the acceptance criterion: selecting two branches queues two
        addendums with one user action (not two separate HTTP requests).
        """
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        # There must be exactly one fetch call in the submit body (the POST).
        fetch_count = body.count("await fetch(")
        assert fetch_count == 1, (
            f"submitAddReleaseBranchesDialog must send exactly one request "
            f"(found {fetch_count} 'await fetch(' occurrences)"
        )
        # And it sends all branches in that one call via target_branches array.
        assert "target_branches" in body
        assert "selectedBranches" in body or "selected" in body.lower()

    def test_disables_submit_while_in_flight(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "submitBtn.disabled = true" in body

    def test_re_enables_submit_on_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "submitBtn.disabled = false" in body

    def test_shows_error_on_failure(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "rab-error" in body
        assert "if (!resp.ok)" in body

    def test_closes_dialog_on_success(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "closeAddReleaseBranchesDialog()" in body

    def test_refreshes_detail_panel_on_success(self):
        """On success the task panel must be refreshed so new addendum appears in 'open'."""
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "openDetailPanel" in body, (
            "After success, submitAddReleaseBranchesDialog must call openDetailPanel "
            "to refresh the panel and show the new addendum in 'open' state"
        )

    def test_handles_network_error(self):
        script = _load_dashboard_script()
        body = _function_body(script, "submitAddReleaseBranchesDialog", is_async=True)
        assert "Network error" in body or "catch" in body


# ---------------------------------------------------------------------------
# Escape-to-close keyboard handler
# ---------------------------------------------------------------------------


class TestEscapeToClose:
    def test_escape_keydown_listener_registered(self):
        """A keydown listener must close the dialog when Escape is pressed."""
        script = _load_dashboard_script()
        assert "Escape" in script
        assert "closeAddReleaseBranchesDialog" in script

    def test_escape_listener_checks_dialog_open(self):
        """The Escape handler must only close the dialog when it is open.

        Finds the Escape handler that calls closeAddReleaseBranchesDialog and verifies
        that it checks whether the dialog is open before closing it.
        """
        script = _load_dashboard_script()
        # Find the Escape check that is closest to closeAddReleaseBranchesDialog
        close_fn = "closeAddReleaseBranchesDialog"
        # Scan for all 'Escape' occurrences and find the one near the close function
        search = "'Escape'"
        pos = 0
        found_snippet = None
        while True:
            idx = script.find(search, pos)
            if idx == -1:
                break
            snippet = script[max(0, idx - 50) : idx + 500]
            if close_fn in snippet:
                found_snippet = snippet
                break
            pos = idx + 1
        assert found_snippet is not None, (
            "Script must have an Escape keydown handler that calls closeAddReleaseBranchesDialog"
        )
        assert "add-release-branches-dialog" in found_snippet or "classList.contains('open')" in found_snippet


# ---------------------------------------------------------------------------
# State variable initialisation
# ---------------------------------------------------------------------------


class TestStateVariables:
    def test_rab_issue_identifier_initialised_to_null(self):
        script = _load_dashboard_script()
        assert "let _rabIssueIdentifier = null" in script

    def test_rab_project_id_initialised_to_null(self):
        script = _load_dashboard_script()
        assert "let _rabProjectId = null" in script

    def test_rab_active_targets_initialised_to_empty_set(self):
        script = _load_dashboard_script()
        assert "let _rabActiveTargets = new Set()" in script
