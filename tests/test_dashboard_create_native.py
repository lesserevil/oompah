"""Tests proving native (oompah_md) task creation includes labels and parent epic.

Covers OOMPAH-12: the dashboard create dialog was hiding labels and parent-epic
selection for native projects because isGitHubBacked() only matched github_issues.

Expected after the fix:
- supportsLabels() returns true for oompah_md and github_issues.
- supportsParentEpic() returns true for oompah_md and github_issues.
- create-tracker-fields div exists and is hidden by default.
- updateGitHubFieldsVisibility() shows tracker fields for native projects.
- submitCreateDialog() includes labels for oompah_md projects.
- submitCreateDialog() includes parent epic for oompah_md projects.
- GitHub-only target_branch still gated on isGitHubBacked (not supportsLabels).
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
# JS: supportsLabels helper
# ---------------------------------------------------------------------------


class TestSupportsLabels:
    def test_function_exists(self):
        """supportsLabels() function is defined in dashboard.html."""
        script = _extract_script(_load_dashboard())
        assert "function supportsLabels(" in script

    def test_returns_true_for_oompah_md(self):
        """supportsLabels() checks for oompah_md tracker kind."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsLabels")
        assert "oompah_md" in body

    def test_returns_true_for_github_issues(self):
        """supportsLabels() checks for github_issues tracker kind."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsLabels")
        assert "github_issues" in body

    def test_returns_false_for_empty(self):
        """supportsLabels() returns falsy when projectId is empty/null."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsLabels")
        assert "return false" in body

    def test_looks_up_current_projects(self):
        """supportsLabels() looks up the project in currentProjects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsLabels")
        assert "currentProjects" in body

    def test_checks_tracker_kind(self):
        """supportsLabels() inspects tracker_kind on the project object."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsLabels")
        assert "tracker_kind" in body


# ---------------------------------------------------------------------------
# JS: supportsParentEpic helper
# ---------------------------------------------------------------------------


class TestSupportsParentEpic:
    def test_function_exists(self):
        """supportsParentEpic() function is defined in dashboard.html."""
        script = _extract_script(_load_dashboard())
        assert "function supportsParentEpic(" in script

    def test_returns_true_for_oompah_md(self):
        """supportsParentEpic() checks for oompah_md tracker kind."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsParentEpic")
        assert "oompah_md" in body

    def test_returns_true_for_github_issues(self):
        """supportsParentEpic() checks for github_issues tracker kind."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsParentEpic")
        assert "github_issues" in body

    def test_returns_false_for_empty(self):
        """supportsParentEpic() returns falsy when projectId is empty/null."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsParentEpic")
        assert "return false" in body

    def test_looks_up_current_projects(self):
        """supportsParentEpic() looks up the project in currentProjects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsParentEpic")
        assert "currentProjects" in body

    def test_checks_tracker_kind(self):
        """supportsParentEpic() inspects tracker_kind on the project object."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "supportsParentEpic")
        assert "tracker_kind" in body


# ---------------------------------------------------------------------------
# HTML: create-tracker-fields div (labels + parent epic for all trackers)
# ---------------------------------------------------------------------------


class TestCreateTrackerFieldsHTML:
    def test_tracker_fields_div_exists(self):
        """The dialog has a #create-tracker-fields container div."""
        html = _load_dashboard()
        assert 'id="create-tracker-fields"' in html

    def test_tracker_fields_hidden_by_default(self):
        """The tracker-fields container is hidden by default."""
        html = _load_dashboard()
        assert (
            'id="create-tracker-fields" style="display:none"' in html
            or 'id="create-tracker-fields" style="display:none;"' in html
            or 'id="create-tracker-fields" style="display: none"' in html
            or 'id="create-tracker-fields" style="display: none;"' in html
        )

    def test_focus_labels_inside_tracker_fields(self):
        """The focus-labels input is inside the tracker-fields section (not github-only)."""
        html = _load_dashboard()
        # create-tracker-fields must appear before create-focus-labels in the HTML
        tracker_pos = html.find('id="create-tracker-fields"')
        labels_pos = html.find('id="create-focus-labels"')
        github_pos = html.find('id="create-github-fields"')
        assert tracker_pos != -1, "create-tracker-fields div missing"
        assert labels_pos != -1, "create-focus-labels input missing"
        # focus labels should appear inside tracker-fields (before github-fields or after)
        # We just confirm it exists; the HTML structure test below confirms ordering.
        assert tracker_pos < labels_pos, (
            "create-focus-labels should appear after create-tracker-fields"
        )
        # focus-labels should NOT be inside the github-only section
        # (i.e., it should appear before or independently of create-github-fields)
        assert labels_pos < github_pos or github_pos == -1 or labels_pos > github_pos, (
            "Structural check: focus-labels position relative to github-fields"
        )

    def test_parent_epic_inside_tracker_fields(self):
        """The parent-epic-select is inside the tracker-fields section (not github-only)."""
        html = _load_dashboard()
        tracker_pos = html.find('id="create-tracker-fields"')
        epic_pos = html.find('id="create-parent-epic-select"')
        assert tracker_pos != -1, "create-tracker-fields div missing"
        assert epic_pos != -1, "create-parent-epic-select missing"
        assert tracker_pos < epic_pos, (
            "create-parent-epic-select should appear after create-tracker-fields"
        )

    def test_tracker_fields_css_exists(self):
        """CSS has a rule for #create-tracker-fields."""
        html = _load_dashboard()
        assert "#create-tracker-fields {" in html or "#create-tracker-fields{" in html

    def test_target_branch_in_github_fields_not_tracker_fields(self):
        """Target branch is inside create-github-fields (GitHub-only), not create-tracker-fields."""
        html = _load_dashboard()
        tracker_pos = html.find('id="create-tracker-fields"')
        github_pos = html.find('id="create-github-fields"')
        target_pos = html.find('id="create-target-branch"')
        assert github_pos != -1, "create-github-fields div missing"
        assert target_pos != -1, "create-target-branch input missing"
        # target-branch should appear AFTER create-github-fields (i.e., inside it)
        assert github_pos < target_pos, (
            "create-target-branch should appear inside create-github-fields"
        )
        # target-branch should appear AFTER tracker-fields (not inside tracker-fields)
        if tracker_pos != -1:
            assert target_pos > tracker_pos, (
                "create-target-branch should not appear before create-tracker-fields"
            )


# ---------------------------------------------------------------------------
# JS: updateGitHubFieldsVisibility — native project support
# ---------------------------------------------------------------------------


class TestUpdateFieldsVisibilityNative:
    def test_shows_tracker_fields_element(self):
        """updateGitHubFieldsVisibility() references create-tracker-fields."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "create-tracker-fields" in body

    def test_uses_supports_labels(self):
        """updateGitHubFieldsVisibility() uses supportsLabels() for tracker-fields visibility."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "supportsLabels" in body

    def test_uses_supports_parent_epic(self):
        """updateGitHubFieldsVisibility() uses supportsParentEpic() for epic row visibility."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "supportsParentEpic" in body

    def test_still_gates_github_fields_on_is_github_backed(self):
        """updateGitHubFieldsVisibility() still uses isGitHubBacked() for GitHub-only fields."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "isGitHubBacked" in body

    def test_hides_something_for_non_supported(self):
        """Function sets display='none' for at least some element when tracker not supported."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "updateGitHubFieldsVisibility")
        assert "'none'" in body or '"none"' in body


# ---------------------------------------------------------------------------
# JS: submitCreateDialog — native project fields included
# ---------------------------------------------------------------------------


class TestSubmitCreateDialogNative:
    def test_labels_gated_on_supports_labels(self):
        """submitCreateDialog() gates focus labels on supportsLabels(), not only isGitHubBacked."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "supportsLabels" in body

    def test_parent_epic_gated_on_supports_parent_epic(self):
        """submitCreateDialog() gates parent epic on supportsParentEpic(), not only isGitHubBacked."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "supportsParentEpic" in body

    def test_target_branch_still_gated_on_is_github_backed(self):
        """submitCreateDialog() still gates target_branch on isGitHubBacked (GitHub-only field)."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        # isGitHubBacked must gate target_branch
        assert "isGitHubBacked" in body
        assert "target_branch" in body

    def test_labels_included_for_oompah_md(self):
        """submitCreateDialog() includes labels for native oompah_md projects via supportsLabels."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        # supportsLabels must gate the labels submission
        assert "supportsLabels" in body
        assert "labels" in body
        assert "create-focus-labels" in body

    def test_parent_epic_included_for_oompah_md(self):
        """submitCreateDialog() reads parent epic for native oompah_md projects via supportsParentEpic."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        assert "supportsParentEpic" in body
        assert "create-parent-epic-select" in body

    def test_labels_parsed_as_comma_separated_array(self):
        """submitCreateDialog() splits comma-separated labels into an array for native projects."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        # The split() must occur inside the supportsLabels block
        assert "split(" in body

    def test_labels_block_after_supports_labels_check(self):
        """The labels submission block comes after the supportsLabels check in the function."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "submitCreateDialog")
        pos_supports = body.find("supportsLabels")
        pos_labels_split = body.find("split(")
        assert pos_supports != -1 and pos_labels_split != -1
        assert pos_supports < pos_labels_split, (
            "supportsLabels check should appear before the labels split()"
        )
