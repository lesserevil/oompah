"""Tests for GitLab-specific UI and forge configuration in projects.html (OOMPAH-327).

Covers:
- Forge selector (GitHub/GitLab) in Add and Edit forms.
- Forge-kind badge display in project card.
- Conditional GitLab Base URL field (shown only for gitlab forge).
- gitlab_issues option in Tracker Kind select.
- Conditional 'Merge Request' vs 'Pull Request' terminology.
- Conditional 'GL Intake' vs 'GH Intake' label based on forge.
- Webhook health display (renderWebhookHealth helper).
- GitLab webhook endpoint hint displayed for gitlab projects.
- forge_kind and forge_base_url included in Add (POST) and Edit (PATCH) payloads.
- GitHub project UI behaviour is unchanged when forge is github.
"""

from __future__ import annotations

import os
import re


# ---------------------------------------------------------------------------
# Helpers (mirrors test_projects_whitelist_ui.py)
# ---------------------------------------------------------------------------


def _load_projects_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "projects.html",
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_main_script(html: str) -> str:
    """Return the largest <script> block — that's the page logic."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in projects.html"
    return max(matches, key=len)


def _get_func_body(script: str, fn_name: str) -> str:
    """Extract a top-level function body via balanced-brace scan."""
    pattern = re.compile(
        rf"(?:async\s+)?function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{"
    )
    m = pattern.search(script)
    assert m, f"Could not find function {fn_name} in script"
    start = m.end() - 1
    depth = 0
    for i in range(start, len(script)):
        c = script[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : i]
    raise AssertionError(f"Could not find end of function {fn_name}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


import pytest


@pytest.fixture(scope="module")
def html() -> str:
    return _load_projects_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_main_script(html)


# ---------------------------------------------------------------------------
# Forge badge display in project card
# ---------------------------------------------------------------------------


class TestForgeBadgeDisplay:
    """The project card must render a forge badge showing github or gitlab."""

    def test_forge_kind_field_row_has_data_attribute(self, html: str) -> None:
        """Field row carries data-field='forge-kind' for test targeting."""
        assert 'data-field="forge-kind"' in html, (
            "Forge kind field-row must carry data-field='forge-kind'."
        )

    def test_forge_badge_class_present(self, html: str) -> None:
        """Project card uses forge-badge CSS class."""
        assert "forge-badge" in html, (
            "The project card must use a 'forge-badge' class to display the forge."
        )

    def test_forge_badge_uses_forge_kind_value(self, script: str) -> None:
        """Badge class is dynamically set from p.forge_kind."""
        assert "p.forge_kind" in script, (
            "Forge badge must read p.forge_kind from the project API data."
        )

    def test_forge_badge_github_css_class_defined(self, html: str) -> None:
        """CSS defines .forge-badge-github class."""
        assert "forge-badge-github" in html, (
            "CSS must define .forge-badge-github for GitHub project cards."
        )

    def test_forge_badge_gitlab_css_class_defined(self, html: str) -> None:
        """CSS defines .forge-badge-gitlab class."""
        assert "forge-badge-gitlab" in html, (
            "CSS must define .forge-badge-gitlab for GitLab project cards."
        )


# ---------------------------------------------------------------------------
# GitLab base URL display in project card
# ---------------------------------------------------------------------------


class TestForgeBaseUrlDisplay:
    """For self-managed GitLab projects, the base URL must appear in the card."""

    def test_forge_base_url_shown_for_non_default_gitlab(self, script: str) -> None:
        """Card shows forge_base_url link for non-default (self-managed) GitLab."""
        assert "forge_base_url" in script, (
            "Project card must include forge_base_url for display."
        )

    def test_gitlab_webhook_endpoint_hint_present(self, html: str) -> None:
        """GitLab webhook endpoint row appears for gitlab projects."""
        assert 'data-field="gitlab-webhook-endpoint"' in html, (
            "A field-row with data-field='gitlab-webhook-endpoint' must exist "
            "to guide operators to the correct webhook endpoint path."
        )

    def test_gitlab_webhook_endpoint_shows_path(self, script: str) -> None:
        """Endpoint row shows the /api/v1/webhooks/gitlab path."""
        assert "/api/v1/webhooks/gitlab" in script, (
            "The GitLab webhook endpoint row must include the /api/v1/webhooks/gitlab "
            "path so operators know where to point their webhook."
        )

    def test_gitlab_webhook_endpoint_conditional_on_gitlab(self, script: str) -> None:
        """Webhook endpoint row is only shown for gitlab forge projects."""
        # The template uses p.forge_kind === 'gitlab' to conditionally render
        assert "p.forge_kind === 'gitlab'" in script, (
            "Gitlab webhook endpoint row must be conditional on forge_kind === 'gitlab'."
        )


# ---------------------------------------------------------------------------
# Webhook health display
# ---------------------------------------------------------------------------


class TestWebhookHealthDisplay:
    """The project card must render webhook health status."""

    def test_webhook_health_field_row_has_data_attribute(self, html: str) -> None:
        """Webhook health row carries data-field='webhook-health'."""
        assert 'data-field="webhook-health"' in html, (
            "Webhook health field-row must carry data-field='webhook-health' "
            "for test targeting."
        )

    def test_renderWebhookHealth_defined(self, script: str) -> None:
        """renderWebhookHealth helper function is defined."""
        body = _get_func_body(script, "renderWebhookHealth")
        assert body, "renderWebhookHealth must be defined in projects.html"

    def test_renderWebhookHealth_handles_no_webhook(self, script: str) -> None:
        """Returns a 'not configured' message when no webhook received yet."""
        body = _get_func_body(script, "renderWebhookHealth")
        assert "No webhook received" in body or "polling" in body, (
            "renderWebhookHealth must handle projects with no last_webhook_received_at."
        )

    def test_renderWebhookHealth_shows_healthy_when_recent(self, script: str) -> None:
        """Returns 'healthy' indicator when webhook was received within 150s."""
        body = _get_func_body(script, "renderWebhookHealth")
        assert "healthy" in body, (
            "renderWebhookHealth must show a 'healthy' state for recent webhooks."
        )

    def test_renderWebhookHealth_shows_stale_when_old(self, script: str) -> None:
        """Returns 'stale' indicator when webhook is older than threshold."""
        body = _get_func_body(script, "renderWebhookHealth")
        assert "stale" in body, (
            "renderWebhookHealth must show a 'stale' state for old webhooks."
        )

    def test_renderWebhookHealth_uses_150s_threshold(self, script: str) -> None:
        """Healthy threshold is 150 seconds (matching orchestrator constant)."""
        body = _get_func_body(script, "renderWebhookHealth")
        assert "150" in body, (
            "renderWebhookHealth must use the 150s threshold to match the "
            "orchestrator's is_webhook_healthy() definition."
        )

    def test_renderWebhookHealth_reads_last_webhook_field(self, script: str) -> None:
        """Reads last_webhook_received_at from the project data."""
        body = _get_func_body(script, "renderWebhookHealth")
        assert "last_webhook_received_at" in body, (
            "renderWebhookHealth must read p.last_webhook_received_at."
        )

    def test_hook_healthy_css_class_defined(self, html: str) -> None:
        """CSS defines .hook-healthy class."""
        assert "hook-healthy" in html, (
            "CSS must define .hook-healthy for the healthy webhook state."
        )

    def test_hook_stale_css_class_defined(self, html: str) -> None:
        """CSS defines .hook-stale class."""
        assert "hook-stale" in html, (
            "CSS must define .hook-stale for the stale webhook state."
        )

    def test_hook_unconfigured_css_class_defined(self, html: str) -> None:
        """CSS defines .hook-unconfigured class."""
        assert "hook-unconfigured" in html, (
            "CSS must define .hook-unconfigured for when no webhook has been received."
        )


# ---------------------------------------------------------------------------
# Merge Request / Pull Request terminology
# ---------------------------------------------------------------------------


class TestMergeRequestTerminology:
    """UI must show 'Merge Request' terminology for GitLab forge projects
    and 'Pull Request' / 'PR' for GitHub forge projects."""

    def test_mr_label_when_gitlab_forge(self, script: str) -> None:
        """'MRs' label is used when forge_kind is gitlab."""
        assert "'MRs'" in script or '"MRs"' in script, (
            "The project card must show 'MRs' for GitLab forge projects."
        )

    def test_pr_label_when_github_forge(self, script: str) -> None:
        """'PRs' label is used when forge_kind is github."""
        assert "'PRs'" in script or '"PRs"' in script, (
            "The project card must show 'PRs' for GitHub forge projects."
        )

    def test_max_in_flight_field_row_has_data_attribute(self, html: str) -> None:
        """Max in-flight row carries data-field='max-in-flight'."""
        assert 'data-field="max-in-flight"' in html, (
            "Max in-flight field row must carry data-field='max-in-flight' "
            "for targeting in tests."
        )

    def test_gitlab_auto_merge_note_present(self, script: str) -> None:
        """GitLab auto-merge uses merge_when_pipeline_succeeds (not Merge Queue)."""
        assert "merge_when_pipeline_succeeds" in script, (
            "For GitLab projects, the UI must show merge_when_pipeline_succeeds "
            "and note that merge trains are not supported."
        )

    def test_gitlab_merge_trains_unsupported_note(self, script: str) -> None:
        """A note must appear that GitLab merge trains are not supported."""
        assert "merge train" in script.lower() or "merge trains" in script.lower(), (
            "The UI must note that GitLab merge trains are not supported in v1."
        )

    def test_merge_queue_shown_only_for_github(self, script: str) -> None:
        """Merge Queue toggle is conditional on forge_kind !== 'gitlab'."""
        # The template uses forge_kind !== 'gitlab' to show/hide the Merge Queue row
        assert "forge_kind !== 'gitlab'" in script or "forge_kind === 'gitlab'" in script, (
            "Merge Queue toggle must be conditional on forge kind."
        )


# ---------------------------------------------------------------------------
# External intake label is forge-conditional
# ---------------------------------------------------------------------------


class TestIntakeLabelForgeParity:
    """The issue-intake field label must change based on forge kind."""

    def test_external_intake_field_row_has_data_attribute(self, html: str) -> None:
        """Intake field row carries data-field='external-issue-intake'."""
        assert 'data-field="external-issue-intake"' in html, (
            "External intake field row must carry data-field='external-issue-intake' "
            "so tests can reliably locate it."
        )

    def test_gl_intake_label_for_gitlab(self, script: str) -> None:
        """Shows 'GL Intake' label for GitLab forge projects."""
        assert "GL Intake" in script, (
            "The project card must show 'GL Intake' for GitLab forge projects."
        )

    def test_gh_intake_label_for_github(self, script: str) -> None:
        """Shows 'GH Intake' label for GitHub forge projects."""
        assert "GH Intake" in script, (
            "The project card must show 'GH Intake' for GitHub forge projects."
        )

    def test_intake_reads_external_issue_intake_enabled(self, script: str) -> None:
        """Card reads external_issue_intake_enabled (forge-neutral alias)."""
        assert "external_issue_intake_enabled" in script, (
            "The intake display must read p.external_issue_intake_enabled "
            "for forge-neutral compatibility."
        )

    def test_gitlab_intake_label_in_edit_form(self, html: str) -> None:
        """Edit form shows 'GitLab Issue Intake' label for gitlab projects."""
        assert "GitLab Issue Intake" in html, (
            "Edit form must show 'GitLab Issue Intake' for GitLab projects."
        )

    def test_github_intake_label_in_edit_form(self, html: str) -> None:
        """Edit form shows 'GitHub Issue Intake' label for github projects."""
        assert "GitHub Issue Intake" in html, (
            "Edit form must show 'GitHub Issue Intake' for GitHub projects."
        )

    def test_onEditForgeChange_updates_intake_label(self, script: str) -> None:
        """onEditForgeChange() updates the intake label text."""
        body = _get_func_body(script, "onEditForgeChange")
        assert "GitLab Issue Intake" in body or "GitLab" in body, (
            "onEditForgeChange must update the intake label to GitLab wording "
            "when the forge is switched to gitlab."
        )


# ---------------------------------------------------------------------------
# Forge selector in Add form
# ---------------------------------------------------------------------------


class TestAddFormForgeSelector:
    """Add form must expose a forge selector and optional GitLab base URL field."""

    def test_forge_kind_select_in_add_form(self, html: str) -> None:
        """Add form has a forge kind <select>."""
        assert 'id="add-forge-kind"' in html, (
            "Add Project form must include a forge kind selector."
        )

    def test_forge_kind_select_has_github_option(self, html: str) -> None:
        """Forge selector has a 'GitHub' option."""
        # Check the option exists after the add-forge-kind select
        assert 'value="github"' in html, (
            "Forge selector must include a GitHub option."
        )

    def test_forge_kind_select_has_gitlab_option(self, html: str) -> None:
        """Forge selector has a 'GitLab' option."""
        assert 'value="gitlab"' in html, (
            "Forge selector must include a GitLab option."
        )

    def test_add_forge_base_url_field_present(self, html: str) -> None:
        """Add form has a forge base URL field for self-managed GitLab."""
        assert 'id="add-forge-base-url"' in html, (
            "Add Project form must include a forge base URL input for GitLab."
        )

    def test_add_forge_base_url_initially_hidden(self, html: str) -> None:
        """GitLab base URL field is hidden when forge is github (default)."""
        # The containing group has class 'gitlab-only' which sets display:none
        assert 'id="add-forge-base-url-group"' in html, (
            "Add form forge base URL group must have an id for show/hide control."
        )
        assert 'class="form-group gitlab-only"' in html or "gitlab-only" in html, (
            "Forge base URL container must use .gitlab-only class to be hidden by default."
        )

    def test_gitlab_only_css_class_defined(self, html: str) -> None:
        """.gitlab-only CSS class hides GitLab-only controls by default."""
        assert ".gitlab-only" in html, (
            "CSS must define .gitlab-only with display:none to hide GitLab controls."
        )

    def test_add_forge_base_url_has_aria_hidden(self, html: str) -> None:
        """GitLab base URL group has aria-hidden when initially not shown."""
        assert 'aria-hidden="true"' in html, (
            "GitLab base URL field group must start with aria-hidden='true' "
            "so screen readers skip it when it is not visible."
        )

    def test_onAddForgeChange_defined(self, script: str) -> None:
        """onAddForgeChange() function is defined to show/hide base URL field."""
        body = _get_func_body(script, "onAddForgeChange")
        assert body, "onAddForgeChange must be defined in projects.html"

    def test_onAddForgeChange_controls_base_url_visibility(self, script: str) -> None:
        """onAddForgeChange() shows/hides the base URL field."""
        body = _get_func_body(script, "onAddForgeChange")
        assert "add-forge-base-url-group" in body, (
            "onAddForgeChange must control the add-forge-base-url-group element."
        )

    def test_onAddForgeChange_updates_aria_hidden(self, script: str) -> None:
        """onAddForgeChange() updates aria-hidden on the base URL group."""
        body = _get_func_body(script, "onAddForgeChange")
        assert "aria-hidden" in body, (
            "onAddForgeChange must update aria-hidden for accessibility."
        )

    def test_inferAddForgeFromUrl_defined(self, script: str) -> None:
        """inferAddForgeFromUrl() auto-selects forge based on URL host."""
        body = _get_func_body(script, "inferAddForgeFromUrl")
        assert body, "inferAddForgeFromUrl must be defined in projects.html"

    def test_inferAddForgeFromUrl_detects_gitlab(self, script: str) -> None:
        """inferAddForgeFromUrl() selects gitlab when URL contains 'gitlab'."""
        body = _get_func_body(script, "inferAddForgeFromUrl")
        assert "gitlab" in body, (
            "inferAddForgeFromUrl must detect GitLab from the URL and select gitlab."
        )

    def test_repo_url_input_calls_infer_on_input(self, html: str) -> None:
        """Repo URL input calls inferAddForgeFromUrl() on input event."""
        assert "inferAddForgeFromUrl" in html, (
            "The repo URL input must call inferAddForgeFromUrl() on input "
            "to auto-set the forge kind."
        )


# ---------------------------------------------------------------------------
# Forge selector in Edit form
# ---------------------------------------------------------------------------


class TestEditFormForgeSelector:
    """Edit form must include forge selector and GitLab base URL fields."""

    def test_edit_forge_kind_select_present(self, html: str) -> None:
        """Edit form contains a forge kind selector."""
        assert "edit-forge-kind-" in html, (
            "Edit form must include a forge kind select named edit-forge-kind-<id>."
        )

    def test_edit_forge_kind_select_has_github_option(self, html: str) -> None:
        """Edit form forge selector includes GitHub option."""
        # We need to distinguish the edit form's options from the add form
        assert "edit-forge-kind" in html and "GitHub" in html, (
            "Edit form forge selector must include a GitHub option."
        )

    def test_edit_forge_kind_select_has_gitlab_option(self, html: str) -> None:
        """Edit form forge selector includes GitLab option."""
        assert "edit-forge-kind" in html and "GitLab" in html, (
            "Edit form forge selector must include a GitLab option."
        )

    def test_edit_forge_base_url_input_present(self, html: str) -> None:
        """Edit form has a GitLab base URL input."""
        assert "edit-forge-base-url-" in html, (
            "Edit form must include a GitLab base URL input named edit-forge-base-url-<id>."
        )

    def test_edit_forge_base_url_group_has_data_attribute(self, html: str) -> None:
        """Edit form base URL group has data-field attribute."""
        assert 'data-field="edit-forge-base-url"' in html, (
            "Edit form GitLab base URL group must have data-field='edit-forge-base-url'."
        )

    def test_onEditForgeChange_defined(self, script: str) -> None:
        """onEditForgeChange() function is defined for the edit form."""
        body = _get_func_body(script, "onEditForgeChange")
        assert body, "onEditForgeChange must be defined in projects.html"

    def test_onEditForgeChange_controls_base_url_visibility(self, script: str) -> None:
        """onEditForgeChange() shows/hides the GitLab base URL group."""
        body = _get_func_body(script, "onEditForgeChange")
        assert "edit-forge-base-url-group-" in body, (
            "onEditForgeChange must control the edit-forge-base-url-group element."
        )

    def test_edit_forge_section_header_present(self, html: str) -> None:
        """Edit form includes a 'Forge Settings' section header."""
        assert "Forge Settings" in html, (
            "Edit form must have a 'Forge Settings' section header "
            "to group forge-related controls."
        )

    def test_forge_settings_section_has_data_attribute(self, html: str) -> None:
        """Forge settings section has data-section attribute."""
        assert 'data-section="forge-settings"' in html, (
            "Forge settings section must have data-section='forge-settings' "
            "for test targeting."
        )


# ---------------------------------------------------------------------------
# gitlab_issues tracker kind option
# ---------------------------------------------------------------------------


class TestGitLabTrackerKindOption:
    """The Tracker Kind select must include a gitlab_issues option."""

    def test_gitlab_issues_option_present(self, html: str) -> None:
        """Edit form tracker kind select has a gitlab_issues option."""
        assert 'value="gitlab_issues"' in html, (
            "Tracker Kind select must include a 'gitlab_issues' option."
        )

    def test_tracker_kind_select_has_oompah_md_option(self, html: str) -> None:
        """Tracker kind select still has oompah_md option (backward compat)."""
        assert 'value="oompah_md"' in html, (
            "Tracker Kind select must still include 'oompah_md' for backward compat."
        )

    def test_tracker_kind_select_has_github_issues_option(self, html: str) -> None:
        """Tracker kind select still has github_issues option (backward compat)."""
        assert 'value="github_issues"' in html, (
            "Tracker Kind select must still include 'github_issues' for backward compat."
        )

    def test_tracker_kind_label_mentions_gitlab_issues(self, html: str) -> None:
        """Tracker Kind field label mentions gitlab_issues."""
        assert "gitlab_issues" in html, (
            "Tracker Kind label must mention gitlab_issues so operators "
            "understand it is available."
        )


# ---------------------------------------------------------------------------
# forge_kind in Add form POST body
# ---------------------------------------------------------------------------


class TestAddProjectForgePayload:
    """addProject() must include forge_kind and forge_base_url in the POST body."""

    def test_addProject_includes_forge_kind(self, script: str) -> None:
        """POST body includes forge_kind."""
        body = _get_func_body(script, "addProject")
        assert "forge_kind" in body, (
            "addProject must include forge_kind in the POST body."
        )

    def test_addProject_reads_forge_kind_from_select(self, script: str) -> None:
        """addProject() reads forge kind from the add-forge-kind select."""
        body = _get_func_body(script, "addProject")
        assert "add-forge-kind" in body, (
            "addProject must read forge kind from the 'add-forge-kind' select element."
        )

    def test_addProject_includes_forge_base_url(self, script: str) -> None:
        """POST body includes forge_base_url when forge is gitlab."""
        body = _get_func_body(script, "addProject")
        assert "forge_base_url" in body, (
            "addProject must include forge_base_url in the POST body for GitLab projects."
        )

    def test_addProject_defaults_forge_kind_to_github(self, script: str) -> None:
        """addProject() falls back to 'github' if no forge is selected."""
        body = _get_func_body(script, "addProject")
        assert "'github'" in body or '"github"' in body, (
            "addProject must default forge_kind to 'github' when the select has no value."
        )


# ---------------------------------------------------------------------------
# forge_kind in Edit form PATCH body
# ---------------------------------------------------------------------------


class TestSaveProjectForgePayload:
    """saveProject() must include forge_kind and forge_base_url in the PATCH body."""

    def test_saveProject_includes_forge_kind(self, script: str) -> None:
        """PATCH body includes forge_kind."""
        body = _get_func_body(script, "saveProject")
        assert "forge_kind" in body, (
            "saveProject must include forge_kind in the PATCH request body."
        )

    def test_saveProject_reads_forge_kind_from_select(self, script: str) -> None:
        """saveProject() reads forge kind from the edit-forge-kind-<id> select."""
        body = _get_func_body(script, "saveProject")
        assert "edit-forge-kind-" in body, (
            "saveProject must read forge_kind from the 'edit-forge-kind-<id>' select."
        )

    def test_saveProject_includes_forge_base_url_for_gitlab(self, script: str) -> None:
        """PATCH body includes forge_base_url for GitLab projects."""
        body = _get_func_body(script, "saveProject")
        assert "forge_base_url" in body, (
            "saveProject must include forge_base_url in the PATCH body for GitLab."
        )

    def test_saveProject_reads_forge_base_url_from_input(self, script: str) -> None:
        """saveProject() reads forge_base_url from the edit-forge-base-url-<id> input."""
        body = _get_func_body(script, "saveProject")
        assert "edit-forge-base-url-" in body, (
            "saveProject must read forge_base_url from the 'edit-forge-base-url-<id>' input."
        )

    def test_saveProject_conditional_forge_base_url(self, script: str) -> None:
        """forge_base_url is only set in the body for gitlab forge."""
        body = _get_func_body(script, "saveProject")
        # The function only sets body.forge_base_url when forgeKind === 'gitlab'
        assert "gitlab" in body and "forge_base_url" in body, (
            "saveProject must conditionally include forge_base_url "
            "only for GitLab projects."
        )


# ---------------------------------------------------------------------------
# GitHub project backward compatibility
# ---------------------------------------------------------------------------


class TestGitHubBackwardCompatibility:
    """Existing GitHub project UI/API behavior must be unchanged."""

    def test_github_intake_label_still_present(self, script: str) -> None:
        """'GH Intake' label is still rendered for GitHub forge projects."""
        assert "GH Intake" in script, (
            "GitHub projects must still show the 'GH Intake' label."
        )

    def test_merge_queue_still_present_for_github(self, script: str) -> None:
        """Merge Queue toggle is still shown for GitHub projects."""
        assert "Merge Queue" in script, (
            "Merge Queue toggle must still appear for GitHub projects."
        )

    def test_github_merge_queue_enqueue_text_unchanged(self, script: str) -> None:
        """Existing 'enqueue PRs via GitHub Merge Queue' text is preserved."""
        assert "GitHub Merge Queue" in script, (
            "The GitHub Merge Queue description text must remain unchanged."
        )

    def test_max_in_flight_prs_label_for_github(self, script: str) -> None:
        """'PRs' label appears in the Max in-flight field for GitHub projects."""
        assert "'PRs'" in script or '"PRs"' in script, (
            "Max in-flight field must show 'PRs' for GitHub projects."
        )

    def test_gh_intake_label_remains_in_card(self, html: str) -> None:
        """The old 'GH Intake' label concept is still present in the HTML."""
        assert "GH Intake" in html, (
            "The intake label must still contain 'GH Intake' for GitHub projects."
        )
