"""Tests for tracker settings UI added to projects.html (TASK-459.4).

The /projects-manage page now exposes tracker backend, central task hub,
legacy Backlog visibility/dispatch flags, and a guarded cutover action.
These tests verify the static HTML/JS structure using the same
source-inspection approach as test_projects_whitelist_ui.py.

Coverage:
  - Tracker section with tracker_kind, task hub, and legacy Backlog flags is
    rendered in each project card.
  - Cutover modal element is present with the migration-warning copy.
  - Cutover button appears for non-github_issues projects.
  - Edit form includes tracker settings section with all 6 tracker fields.
  - saveProject() reads and sends tracker fields in the PATCH body.
  - showCutoverModal / closeCutoverModal / confirmCutover JS functions exist.
  - confirmCutover() sends tracker_kind=github_issues and tracker_cutover_at.
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers (mirrors test_projects_whitelist_ui.py)
# ---------------------------------------------------------------------------


def _load_projects_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "projects.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_main_script(html: str) -> str:
    """Return the largest <script> block — that's the page logic."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in projects.html"
    return max(matches, key=len)


def _get_func_body(script: str, fn_name: str) -> str:
    """Extract a top-level function body via balanced-brace scan.

    Supports both ``function foo()`` and ``async function foo()`` declarations.
    """
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


@pytest.fixture(scope="module")
def html() -> str:
    return _load_projects_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_main_script(html)


# ---------------------------------------------------------------------------
# Cutover modal HTML
# ---------------------------------------------------------------------------


class TestCutoverModal:
    """The cutover warning modal must be present in the HTML with the required
    migration-warning copy and action buttons."""

    def test_cutover_modal_element_present(self, html: str) -> None:
        """HTML includes the cutover modal overlay element."""
        assert 'id="cutover-modal"' in html

    def test_cutover_modal_has_role_dialog(self, html: str) -> None:
        """Cutover modal element carries role=dialog for accessibility."""
        # The modal div should have both id and role
        assert 'role="dialog"' in html

    def test_cutover_modal_warns_no_migration(self, html: str) -> None:
        """Modal body explicitly states Backlog.md tasks will NOT be migrated."""
        assert "will" in html and "not" in html.lower()
        # More specific: look for the key phrase
        assert "not be migrated" in html.lower() or "not</strong> be migrated" in html.lower()

    def test_cutover_modal_mentions_backlog_md(self, html: str) -> None:
        """Warning references Backlog.md by name."""
        assert "Backlog.md" in html

    def test_cutover_modal_project_name_slot(self, html: str) -> None:
        """Modal contains a slot element for the project name."""
        assert 'id="cutover-modal-project-name"' in html

    def test_cutover_modal_has_cancel_button(self, html: str) -> None:
        """Modal contains a Cancel button."""
        assert "closeCutoverModal()" in html

    def test_cutover_modal_has_confirm_button(self, html: str) -> None:
        """Modal contains a Proceed / confirm button."""
        assert "confirmCutover()" in html

    def test_cutover_modal_sets_tracker_kind_in_copy(self, html: str) -> None:
        """Modal copy mentions github_issues as the new tracker kind."""
        assert "github_issues" in html


# ---------------------------------------------------------------------------
# Tracker section in project card
# ---------------------------------------------------------------------------


class TestTrackerCardDisplay:
    """Project cards must render a tracker section with backend, task hub, and
    legacy Backlog flags."""

    def test_tracker_section_present(self, script: str) -> None:
        """loadProjects() card template includes a data-section='tracker' div."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'data-section="tracker"' in load_body

    def test_tracker_backend_field_row(self, script: str) -> None:
        """Card template renders a data-field='tracker-kind' row."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'data-field="tracker-kind"' in load_body

    def test_tracker_kind_fallback_label(self, script: str) -> None:
        """Card template shows legacy Backlog when tracker_kind is not set."""
        load_body = _get_func_body(script, "loadProjects")
        assert "backlog (legacy)" in load_body

    def test_task_hub_field_row(self, script: str) -> None:
        """Card template renders a data-field='task-hub' row."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'data-field="task-hub"' in load_body

    def test_task_hub_references_tracker_owner_and_repo(self, script: str) -> None:
        """Task Hub row uses tracker_owner and tracker_repo from the project."""
        load_body = _get_func_body(script, "loadProjects")
        assert "tracker_owner" in load_body
        assert "tracker_repo" in load_body

    def test_legacy_backlog_flags_row(self, script: str) -> None:
        """Card template renders a data-field='legacy-backlog-flags' row."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'data-field="legacy-backlog-flags"' in load_body

    def test_legacy_backlog_enabled_shown(self, script: str) -> None:
        """Card template references legacy_backlog_enabled."""
        load_body = _get_func_body(script, "loadProjects")
        assert "legacy_backlog_enabled" in load_body

    def test_legacy_backlog_dispatch_shown(self, script: str) -> None:
        """Card template references legacy_backlog_dispatch."""
        load_body = _get_func_body(script, "loadProjects")
        assert "legacy_backlog_dispatch" in load_body


# ---------------------------------------------------------------------------
# Cutover button in project card
# ---------------------------------------------------------------------------


class TestCutoverButton:
    """Project cards must show a cutover button for projects not yet on GitHub
    Issues, and the button must invoke showCutoverModal."""

    def test_cutover_button_present_for_non_github_tracker(self, script: str) -> None:
        """Card template renders a btn-cutover button."""
        load_body = _get_func_body(script, "loadProjects")
        assert "btn-cutover" in load_body

    def test_cutover_button_calls_show_cutover_modal(self, script: str) -> None:
        """Cutover button onclick calls showCutoverModal."""
        load_body = _get_func_body(script, "loadProjects")
        assert "showCutoverModal" in load_body

    def test_cutover_button_hidden_for_github_issues(self, script: str) -> None:
        """Button is conditionally rendered — not shown for github_issues projects."""
        load_body = _get_func_body(script, "loadProjects")
        # The condition must check that tracker_kind !== 'github_issues'
        assert "github_issues" in load_body
        # The cutover button is inside a conditional expression
        assert "btn-cutover" in load_body and "tracker_kind" in load_body


# ---------------------------------------------------------------------------
# Edit form tracker fields
# ---------------------------------------------------------------------------


class TestTrackerEditForm:
    """The edit form must include inputs for all 6 tracker fields so operators
    can configure them without curl."""

    def test_tracker_kind_select_in_edit_form(self, script: str) -> None:
        """Edit form contains a tracker-kind select element."""
        load_body = _get_func_body(script, "loadProjects")
        assert "edit-tracker-kind-" in load_body

    def test_tracker_owner_input_in_edit_form(self, script: str) -> None:
        """Edit form contains a tracker-owner text input."""
        load_body = _get_func_body(script, "loadProjects")
        assert "edit-tracker-owner-" in load_body

    def test_tracker_repo_input_in_edit_form(self, script: str) -> None:
        """Edit form contains a tracker-repo text input."""
        load_body = _get_func_body(script, "loadProjects")
        assert "edit-tracker-repo-" in load_body

    def test_github_project_node_id_input_in_edit_form(self, script: str) -> None:
        """Edit form contains a github-project-node-id text input."""
        load_body = _get_func_body(script, "loadProjects")
        assert "edit-github-project-node-id-" in load_body

    def test_legacy_backlog_enabled_checkbox_in_edit_form(self, script: str) -> None:
        """Edit form contains a legacy_backlog_enabled checkbox."""
        load_body = _get_func_body(script, "loadProjects")
        assert "edit-legacy-backlog-enabled-" in load_body

    def test_legacy_backlog_dispatch_checkbox_in_edit_form(self, script: str) -> None:
        """Edit form contains a legacy_backlog_dispatch checkbox."""
        load_body = _get_func_body(script, "loadProjects")
        assert "edit-legacy-backlog-dispatch-" in load_body

    def test_tracker_section_heading_in_edit_form(self, script: str) -> None:
        """Edit form includes a Tracker Settings section heading."""
        load_body = _get_func_body(script, "loadProjects")
        assert "Tracker Settings" in load_body

    def test_tracker_kind_has_github_issues_option(self, script: str) -> None:
        """The tracker-kind select offers 'github_issues' as an option."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'value="github_issues"' in load_body

    def test_tracker_kind_has_backlog_option(self, script: str) -> None:
        """The tracker-kind select offers 'backlog' as an option."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'value="backlog"' in load_body

    def test_tracker_kind_has_oompah_md_option(self, script: str) -> None:
        """The tracker-kind select offers native oompah Markdown as an option."""
        load_body = _get_func_body(script, "loadProjects")
        assert 'value="oompah_md"' in load_body


class TestAddProjectTrackerDefaults:
    """The add form must create paused native-tracker projects."""

    def test_add_project_sends_oompah_md_tracker_kind(self, script: str) -> None:
        add_body = _get_func_body(script, "addProject")
        assert "tracker_kind: 'oompah_md'" in add_body

    def test_add_project_sends_paused_true(self, script: str) -> None:
        add_body = _get_func_body(script, "addProject")
        assert "paused: true" in add_body


# ---------------------------------------------------------------------------
# saveProject() reads and sends tracker fields
# ---------------------------------------------------------------------------


class TestSaveProjectTrackerFields:
    """saveProject() must read all tracker fields and include them in the
    PATCH body sent to /api/v1/projects/<id>."""

    def test_save_project_reads_tracker_kind(self, script: str) -> None:
        """saveProject reads the tracker_kind select value."""
        body = _get_func_body(script, "saveProject")
        assert "edit-tracker-kind-" in body

    def test_save_project_reads_tracker_owner(self, script: str) -> None:
        """saveProject reads the tracker_owner input."""
        body = _get_func_body(script, "saveProject")
        assert "edit-tracker-owner-" in body

    def test_save_project_reads_tracker_repo(self, script: str) -> None:
        """saveProject reads the tracker_repo input."""
        body = _get_func_body(script, "saveProject")
        assert "edit-tracker-repo-" in body

    def test_save_project_reads_github_project_node_id(self, script: str) -> None:
        """saveProject reads the github_project_node_id input."""
        body = _get_func_body(script, "saveProject")
        assert "edit-github-project-node-id-" in body

    def test_save_project_reads_legacy_backlog_enabled(self, script: str) -> None:
        """saveProject reads the legacy_backlog_enabled checkbox."""
        body = _get_func_body(script, "saveProject")
        assert "edit-legacy-backlog-enabled-" in body

    def test_save_project_reads_legacy_backlog_dispatch(self, script: str) -> None:
        """saveProject reads the legacy_backlog_dispatch checkbox."""
        body = _get_func_body(script, "saveProject")
        assert "edit-legacy-backlog-dispatch-" in body

    def test_save_project_sends_tracker_kind_in_body(self, script: str) -> None:
        """PATCH body includes tracker_kind."""
        body = _get_func_body(script, "saveProject")
        assert "tracker_kind" in body

    def test_save_project_sends_tracker_owner_in_body(self, script: str) -> None:
        """PATCH body includes tracker_owner."""
        body = _get_func_body(script, "saveProject")
        assert "tracker_owner" in body

    def test_save_project_sends_tracker_repo_in_body(self, script: str) -> None:
        """PATCH body includes tracker_repo."""
        body = _get_func_body(script, "saveProject")
        assert "tracker_repo" in body

    def test_save_project_sends_github_project_node_id_in_body(self, script: str) -> None:
        """PATCH body includes github_project_node_id."""
        body = _get_func_body(script, "saveProject")
        assert "github_project_node_id" in body

    def test_save_project_sends_legacy_backlog_enabled_in_body(self, script: str) -> None:
        """PATCH body includes legacy_backlog_enabled."""
        body = _get_func_body(script, "saveProject")
        assert "legacy_backlog_enabled" in body

    def test_save_project_sends_legacy_backlog_dispatch_in_body(self, script: str) -> None:
        """PATCH body includes legacy_backlog_dispatch."""
        body = _get_func_body(script, "saveProject")
        assert "legacy_backlog_dispatch" in body


# ---------------------------------------------------------------------------
# Cutover modal JS functions
# ---------------------------------------------------------------------------


class TestCutoverModalFunctions:
    """showCutoverModal, closeCutoverModal, and confirmCutover must be defined
    and implement the right behavior."""

    def test_show_cutover_modal_function_defined(self, script: str) -> None:
        """showCutoverModal is a top-level function."""
        assert "function showCutoverModal" in script

    def test_close_cutover_modal_function_defined(self, script: str) -> None:
        """closeCutoverModal is a top-level function."""
        assert "function closeCutoverModal" in script

    def test_confirm_cutover_function_defined(self, script: str) -> None:
        """confirmCutover is a top-level function."""
        assert "function confirmCutover" in script

    def test_show_cutover_modal_opens_modal(self, script: str) -> None:
        """showCutoverModal adds the 'open' class to the modal overlay."""
        body = _get_func_body(script, "showCutoverModal")
        assert "open" in body

    def test_show_cutover_modal_sets_project_id(self, script: str) -> None:
        """showCutoverModal stores projectId in the modal's dataset."""
        body = _get_func_body(script, "showCutoverModal")
        assert "projectId" in body or "project_id" in body or "dataset" in body

    def test_close_cutover_modal_removes_open_class(self, script: str) -> None:
        """closeCutoverModal removes the 'open' class from the overlay."""
        body = _get_func_body(script, "closeCutoverModal")
        assert "open" in body or "remove" in body

    def test_confirm_cutover_sends_patch(self, script: str) -> None:
        """confirmCutover sends a PATCH request."""
        body = _get_func_body(script, "confirmCutover")
        assert "PATCH" in body

    def test_confirm_cutover_sets_tracker_kind_github_issues(self, script: str) -> None:
        """confirmCutover sends tracker_kind: 'github_issues' in the body."""
        body = _get_func_body(script, "confirmCutover")
        assert "github_issues" in body
        assert "tracker_kind" in body

    def test_confirm_cutover_sets_tracker_cutover_at(self, script: str) -> None:
        """confirmCutover includes tracker_cutover_at (ISO timestamp) in the body."""
        body = _get_func_body(script, "confirmCutover")
        assert "tracker_cutover_at" in body

    def test_confirm_cutover_calls_load_projects_on_success(self, script: str) -> None:
        """confirmCutover calls loadProjects() after a successful PATCH."""
        body = _get_func_body(script, "confirmCutover")
        assert "loadProjects" in body

    def test_confirm_cutover_closes_modal_before_fetch(self, script: str) -> None:
        """confirmCutover closes the modal before making the network request."""
        body = _get_func_body(script, "confirmCutover")
        # closeCutoverModal must appear before _runMutation in the function body
        close_pos = body.find("closeCutoverModal")
        run_pos = body.find("_runMutation")
        assert close_pos != -1 and run_pos != -1
        assert close_pos < run_pos, "closeCutoverModal must be called before _runMutation"
