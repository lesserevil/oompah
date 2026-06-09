"""Tests for the GitHub-specific create issue dialog in dashboard.html.

Covers:
- HTML elements for GitHub-specific fields (target branch, focus labels,
  parent epic selector).
- CSS for the GitHub fields section.
- JS: isGitHubBacked(), updateGitHubFieldsVisibility().
- submitCreateDialog() includes target_branch and labels for GitHub projects.
- enhanceCreateDialog() includes target_branch for GitHub projects.
- Legacy Backlog projects are not affected by the GitHub fields.
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _load_dashboard() -> str:
    path = Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html"
    return path.read_text(encoding="utf-8")


def _extract_script(html: str) -> str:
    """Return the content of the largest <script> block."""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "No <script> blocks found in dashboard.html"
    return max(scripts, key=len)


def _extract_func_body(script: str, fn_name: str) -> str:
    """Return the body of a named function (text between outermost braces)."""
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\([^)]*\)\s*\{{")
    match = pattern.search(script)
    assert match, f"Could not find function {fn_name}"
    start = match.end() - 1
    depth = 0
    for idx in range(start, len(script)):
        c = script[idx]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : idx]
    raise AssertionError(f"Could not find end of function {fn_name}")


# ---------------------------------------------------------------------------
# HTML elements
# ---------------------------------------------------------------------------


class TestCreateDialogGitHubHTML:
    def test_github_fields_div_exists(self):
        """The dialog has a #create-github-fields container div."""
        html = _load_dashboard()
        assert 'id="create-github-fields"' in html

    def test_target_branch_input_exists(self):
        """The dialog has a target-branch text input."""
        html = _load_dashboard()
        assert 'id="create-target-branch"' in html

    def test_target_branch_has_placeholder(self):
        """Target branch input has a helpful placeholder."""
        html = _load_dashboard()
        assert 'placeholder="e.g. main' in html or "placeholder='e.g. main" in html

    def test_focus_labels_input_exists(self):
        """The dialog has a focus-labels text input."""
        html = _load_dashboard()
        assert 'id="create-focus-labels"' in html

    def test_focus_labels_has_placeholder(self):
        """Focus labels input has a helpful placeholder."""
        html = _load_dashboard()
        assert "needs:frontend" in html

    def test_parent_epic_select_exists(self):
        """The dialog has a parent-epic-select dropdown."""
        html = _load_dashboard()
        assert 'id="create-parent-epic-select"' in html

    def test_parent_epic_row_hidden_by_default(self):
        """The parent epic row is hidden by default (populated only for GitHub projects)."""
        html = _load_dashboard()
        # Accept display:none with or without a trailing semicolon/space
        assert (
            'id="create-parent-epic-row" style="display:none"' in html
            or 'id="create-parent-epic-row" style="display:none;"' in html
            or 'id="create-parent-epic-row" style="display: none"' in html
            or 'id="create-parent-epic-row" style="display: none;"' in html
        )

    def test_github_fields_div_hidden_by_default(self):
        """The GitHub fields container is hidden by default."""
        html = _load_dashboard()
        assert (
            'id="create-github-fields" style="display:none"' in html
            or 'id="create-github-fields" style="display:none;"' in html
            or 'id="create-github-fields" style="display: none"' in html
            or 'id="create-github-fields" style="display: none;"' in html
        )

    def test_target_branch_label_present(self):
        """The dialog has a label for the Target Branch field."""
        html = _load_dashboard()
        assert "Target Branch" in html

    def test_focus_labels_label_present(self):
        """The dialog has a label for the Focus Labels field."""
        html = _load_dashboard()
        assert "Focus Labels" in html

    def test_parent_epic_label_present(self):
        """The dialog has a label for the Parent Epic field."""
        html = _load_dashboard()
        assert "Parent Epic" in html


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


class TestCreateDialogGitHubCSS:
    def test_github_fields_css_exists(self):
        """CSS has a rule for #create-github-fields."""
        html = _load_dashboard()
        assert "#create-github-fields {" in html or "#create-github-fields{" in html


# ---------------------------------------------------------------------------
# JS: isGitHubBacked helper
# ---------------------------------------------------------------------------


class TestIsGitHubBacked:
    def test_is_github_backed_function_exists(self):
        """isGitHubBacked() function is defined."""
        script = _extract_script(_load_dashboard())
        assert "function isGitHubBacked(" in script

    def test_is_github_backed_checks_tracker_kind(self):
        """isGitHubBacked checks tracker_kind === 'github_issues'."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "isGitHubBacked")
        assert "tracker_kind" in body
        assert "github_issues" in body

    def test_is_github_backed_looks_up_current_projects(self):
        """isGitHubBacked looks up the project in currentProjects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "isGitHubBacked")
        assert "currentProjects" in body

    def test_is_github_backed_returns_false_for_no_id(self):
        """isGitHubBacked returns falsy when projectId is empty."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "isGitHubBacked")
        # Must have an early return for empty/falsy projectId
        assert "return false" in body


# ---------------------------------------------------------------------------
# JS: updateGitHubFieldsVisibility
# ---------------------------------------------------------------------------


class TestUpdateGitHubFieldsVisibility:
    def test_function_exists(self):
        """updateGitHubFieldsVisibility() function is defined."""
        script = _extract_script(_load_dashboard())
        assert "function updateGitHubFieldsVisibility(" in script

    def test_shows_github_fields_for_github_project(self):
        """Function sets display='' (visible) for GitHub-backed projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "create-github-fields" in body
        assert "display" in body
        assert "github" in body.lower() or "isGitHubBacked" in body

    def test_hides_github_fields_for_non_github(self):
        """Function sets display='none' for non-GitHub-backed projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "'none'" in body or '"none"' in body

    def test_populates_epic_select(self):
        """Function populates the parent epic select from allIssuesFlat."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "create-parent-epic-select" in body
        assert "allIssuesFlat" in body

    def test_uses_resolve_project_cascade(self):
        """Function uses the same project ID cascade as submitCreateDialog."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "create-project-select" in body
        assert "project-filter" in body


# ---------------------------------------------------------------------------
# JS: openCreateDialog
# ---------------------------------------------------------------------------


class TestOpenCreateDialogGitHub:
    def test_calls_update_visibility(self):
        """openCreateDialog() calls updateGitHubFieldsVisibility()."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "openCreateDialog")
        assert "updateGitHubFieldsVisibility()" in body

    def test_resets_target_branch(self):
        """openCreateDialog() resets the target-branch input."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "openCreateDialog")
        assert "create-target-branch" in body

    def test_resets_focus_labels(self):
        """openCreateDialog() resets the focus-labels input."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "openCreateDialog")
        assert "create-focus-labels" in body


# ---------------------------------------------------------------------------
# JS: openCreateDialogForEpic
# ---------------------------------------------------------------------------


class TestOpenCreateDialogForEpicGitHub:
    def test_calls_update_visibility(self):
        """openCreateDialogForEpic() calls updateGitHubFieldsVisibility()."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "openCreateDialogForEpic")
        assert "updateGitHubFieldsVisibility()" in body

    def test_resets_target_branch(self):
        """openCreateDialogForEpic() resets the target-branch input."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "openCreateDialogForEpic")
        assert "create-target-branch" in body

    def test_resets_focus_labels(self):
        """openCreateDialogForEpic() resets the focus-labels input."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "openCreateDialogForEpic")
        assert "create-focus-labels" in body


# ---------------------------------------------------------------------------
# JS: onCreateProjectChange
# ---------------------------------------------------------------------------


class TestOnCreateProjectChangeGitHub:
    def test_calls_update_visibility(self):
        """onCreateProjectChange() calls updateGitHubFieldsVisibility()."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "onCreateProjectChange")
        assert "updateGitHubFieldsVisibility()" in body


# ---------------------------------------------------------------------------
# JS: submitCreateDialog — GitHub-specific fields included
# ---------------------------------------------------------------------------


class TestSubmitCreateDialogGitHub:
    def test_includes_target_branch_for_github(self):
        """submitCreateDialog() includes target_branch for GitHub-backed projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "target_branch" in body
        assert "create-target-branch" in body

    def test_includes_labels_for_github(self):
        """submitCreateDialog() includes labels array for GitHub-backed projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "labels" in body
        assert "create-focus-labels" in body

    def test_includes_parent_epic_for_github(self):
        """submitCreateDialog() reads parent epic from dropdown for GitHub projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "create-parent-epic-select" in body

    def test_gates_github_fields_on_is_github_backed(self):
        """submitCreateDialog() only sends GitHub fields when isGitHubBacked() is true."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "isGitHubBacked" in body

    def test_labels_parsed_as_array(self):
        """submitCreateDialog() parses comma-separated labels into an array."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        # The function splits by comma to produce the labels array
        assert "split(" in body


# ---------------------------------------------------------------------------
# JS: enhanceCreateDialog — target_branch included for GitHub
# ---------------------------------------------------------------------------


class TestEnhanceCreateDialogGitHub:
    def test_includes_target_branch_for_github(self):
        """enhanceCreateDialog() forwards target_branch for GitHub-backed projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "enhanceCreateDialog")
        assert "target_branch" in body
        assert "create-target-branch" in body

    def test_gates_on_is_github_backed(self):
        """enhanceCreateDialog() only adds target_branch when isGitHubBacked() is true."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "enhanceCreateDialog")
        assert "isGitHubBacked" in body
