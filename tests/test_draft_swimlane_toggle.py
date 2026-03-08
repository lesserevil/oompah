"""Tests for Finalize/Mark-as-Draft toggle button in swimlane header.

When an epic has the 'draft' label, the swimlane header should display a
'Finalize' button. When an epic does NOT have the 'draft' label, it should
display a 'Mark as Draft' button.

The toggleEpicDraft() JS function must:
- DELETE the 'draft' label when isDraft is true
- POST the 'draft' label when isDraft is false
- PATCH status to 'deferred' in both cases
- Call refreshBoard() after completion

See issue: oompah-ude
"""

import os
import re

import pytest


def _load_dashboard_html() -> str:
    """Load dashboard HTML from the templates directory."""
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    """Extract the main (largest) <script> block from the dashboard HTML."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


@pytest.fixture(scope="module")
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


def _get_render_swimlane_body(script: str) -> str:
    """Extract the body of the renderSwimlaneView function."""
    match = re.search(
        r"function renderSwimlaneView\(.*?\)\s*\{(.*?)(?=\nfunction |\nasync function )",
        script,
        re.DOTALL,
    )
    assert match, "Could not find renderSwimlaneView function"
    return match.group(1)


def _get_toggle_epic_draft_body(script: str) -> str:
    """Extract the body of the toggleEpicDraft function."""
    match = re.search(
        r"async function toggleEpicDraft\(.*?\)\s*\{(.*?)\n\}",
        script,
        re.DOTALL,
    )
    assert match, "Could not find toggleEpicDraft function"
    return match.group(1)


class TestSwimlaneDraftToggleButton:
    """Verify the Finalize/Mark-as-Draft toggle button in swimlane headers."""

    # -----------------------------------------------------------------------
    # toggleEpicDraft function exists
    # -----------------------------------------------------------------------

    def test_toggle_epic_draft_function_exists(self, script):
        """toggleEpicDraft async function must be defined in the script."""
        assert re.search(
            r"async function toggleEpicDraft\s*\(",
            script,
        ), "toggleEpicDraft must be defined as an async function in dashboard.html"

    def test_toggle_epic_draft_function_accepts_three_params(self, script):
        """toggleEpicDraft must accept epicIdentifier, isDraft, and projectId params."""
        match = re.search(
            r"async function toggleEpicDraft\(([^)]*)\)",
            script,
        )
        assert match, "Could not find toggleEpicDraft function signature"
        params = match.group(1)
        assert "epicIdentifier" in params, "toggleEpicDraft must have epicIdentifier parameter"
        assert "isDraft" in params, "toggleEpicDraft must have isDraft parameter"
        assert "projectId" in params, "toggleEpicDraft must have projectId parameter"

    # -----------------------------------------------------------------------
    # Button rendered for draft epics: 'Finalize'
    # -----------------------------------------------------------------------

    def test_finalize_button_label_present_for_draft_epic(self, script):
        """renderSwimlaneView must produce 'Finalize' button text for draft epics."""
        body = _get_render_swimlane_body(script)
        assert "Finalize" in body, (
            "renderSwimlaneView must include 'Finalize' as a button label for draft epics"
        )

    def test_mark_as_draft_button_label_present_for_non_draft_epic(self, script):
        """renderSwimlaneView must produce 'Mark as Draft' button text for non-draft epics."""
        body = _get_render_swimlane_body(script)
        assert "Mark as Draft" in body, (
            "renderSwimlaneView must include 'Mark as Draft' as a button label for non-draft epics"
        )

    def test_button_label_is_conditional_on_draft_label(self, script):
        """The toggle button label must be conditional on whether epic has 'draft' label."""
        body = _get_render_swimlane_body(script)
        # Both labels must coexist in the same conditional expression
        finalize_pos = body.find("Finalize")
        draft_btn_pos = body.find("Mark as Draft")
        assert finalize_pos != -1, "Must have 'Finalize' label in renderSwimlaneView"
        assert draft_btn_pos != -1, "Must have 'Mark as Draft' label in renderSwimlaneView"
        # They should be close together (same ternary expression)
        assert abs(finalize_pos - draft_btn_pos) < 300, (
            "'Finalize' and 'Mark as Draft' must be in the same conditional expression"
        )

    # -----------------------------------------------------------------------
    # Button calls toggleEpicDraft with correct arguments
    # -----------------------------------------------------------------------

    def test_button_calls_toggle_epic_draft(self, script):
        """The toggle button onclick must call toggleEpicDraft()."""
        body = _get_render_swimlane_body(script)
        assert "toggleEpicDraft(" in body, (
            "swimlane-actions button must call toggleEpicDraft()"
        )

    def test_button_passes_epic_identifier(self, script):
        """The toggle button must pass epic.identifier as first argument."""
        body = _get_render_swimlane_body(script)
        # Should have toggleEpicDraft with epic.identifier
        assert re.search(
            r"toggleEpicDraft\(.*epic\.identifier",
            body,
            re.DOTALL,
        ), "toggleEpicDraft must be called with epic.identifier as first argument"

    def test_button_passes_is_draft_flag(self, script):
        """The toggle button must pass the isDraft boolean as second argument."""
        body = _get_render_swimlane_body(script)
        # Should have isDraft variable or inline includes check passed to toggleEpicDraft
        assert re.search(
            r"toggleEpicDraft\(.*\$\{.*isDraft.*\}",
            body,
            re.DOTALL,
        ) or re.search(
            r"toggleEpicDraft\(.*isDraft",
            body,
            re.DOTALL,
        ), "toggleEpicDraft must receive the isDraft boolean flag as second argument"

    def test_button_passes_project_id(self, script):
        """The toggle button must pass epic.project_id as third argument."""
        body = _get_render_swimlane_body(script)
        assert re.search(
            r"toggleEpicDraft\(.*project_id",
            body,
            re.DOTALL,
        ), "toggleEpicDraft must be called with project_id as third argument"

    def test_button_calls_event_stop_propagation(self, script):
        """The toggle button onclick must call event.stopPropagation() to prevent swimlane toggle."""
        body = _get_render_swimlane_body(script)
        # Find the toggleEpicDraft call site and check stopPropagation is nearby
        tef_pos = body.find("toggleEpicDraft(")
        assert tef_pos != -1, "toggleEpicDraft must be present"
        # Look in a window around the call for stopPropagation
        context = body[max(0, tef_pos - 100):tef_pos + 50]
        assert "stopPropagation" in context, (
            "Button calling toggleEpicDraft must also call event.stopPropagation()"
        )

    # -----------------------------------------------------------------------
    # toggleEpicDraft deletes label when isDraft is true
    # -----------------------------------------------------------------------

    def test_toggle_epic_draft_deletes_label_when_is_draft_true(self, script):
        """toggleEpicDraft must call DELETE on /labels/draft when isDraft is true."""
        body = _get_toggle_epic_draft_body(script)
        assert re.search(
            r"method.*['\"]DELETE['\"]|DELETE",
            body,
        ), "toggleEpicDraft must use DELETE method to remove the draft label"
        assert "labels/draft" in body or re.search(
            r"labels.*draft",
            body,
        ), "toggleEpicDraft must target the /labels/draft endpoint for DELETE"

    def test_toggle_epic_draft_uses_delete_only_in_is_draft_branch(self, script):
        """DELETE must be inside the isDraft-true branch (if(isDraft) block)."""
        body = _get_toggle_epic_draft_body(script)
        # Verify the if(isDraft) conditional exists
        assert re.search(r"if\s*\(\s*isDraft\s*\)", body), (
            "toggleEpicDraft must have an if(isDraft) branch"
        )
        # The if(isDraft) block must come before any else, and DELETE must appear before else
        if_pos = body.find("isDraft")
        delete_pos = body.find("DELETE")
        else_pos = re.search(r"\}\s*else\s*\{", body)
        assert delete_pos != -1, "DELETE must be present in toggleEpicDraft"
        assert if_pos != -1, "if(isDraft) must be present"
        # DELETE should appear before the else branch (i.e., within the if block)
        if else_pos:
            assert delete_pos < else_pos.start(), (
                "DELETE call must be inside the if(isDraft) branch, before the else block"
            )

    # -----------------------------------------------------------------------
    # toggleEpicDraft posts label when isDraft is false
    # -----------------------------------------------------------------------

    def test_toggle_epic_draft_posts_label_when_is_draft_false(self, script):
        """toggleEpicDraft must call POST on /labels when isDraft is false."""
        body = _get_toggle_epic_draft_body(script)
        assert re.search(
            r"method.*['\"]POST['\"]|['\"]POST['\"]",
            body,
        ), "toggleEpicDraft must use POST method to add the draft label"
        assert "/labels" in body, "toggleEpicDraft must target the /labels endpoint for POST"

    def test_toggle_epic_draft_posts_draft_label_value(self, script):
        """The POST body must include {label: 'draft'} payload."""
        body = _get_toggle_epic_draft_body(script)
        # Should have label: 'draft' in the POST body
        assert re.search(
            r"label.*['\"]draft['\"]|['\"]draft['\"].*label",
            body,
        ), "toggleEpicDraft POST must send {label: 'draft'} in the request body"

    def test_toggle_epic_draft_uses_post_only_in_else_branch(self, script):
        """POST must be inside the else (isDraft-false) branch."""
        body = _get_toggle_epic_draft_body(script)
        # Verify there is an else branch
        else_match = re.search(r"\}\s*else\s*\{", body, re.DOTALL)
        assert else_match, "toggleEpicDraft must have an else branch for isDraft=false"
        # POST must appear after the else keyword (in the else block)
        post_pos = body.find("POST")
        assert post_pos != -1, "POST must be present in toggleEpicDraft"
        assert post_pos > else_match.start(), (
            "POST call must be inside the else branch (isDraft=false case), after the 'else {'"
        )

    # -----------------------------------------------------------------------
    # toggleEpicDraft sets status to 'deferred' in both cases
    # -----------------------------------------------------------------------

    def test_toggle_epic_draft_patches_status_to_deferred(self, script):
        """toggleEpicDraft must PATCH {status: 'deferred'} in both draft and non-draft cases."""
        body = _get_toggle_epic_draft_body(script)
        assert "deferred" in body, (
            "toggleEpicDraft must set status to 'deferred' via PATCH"
        )

    def test_toggle_epic_draft_patch_uses_patch_method(self, script):
        """toggleEpicDraft must use PATCH method for the status update."""
        body = _get_toggle_epic_draft_body(script)
        assert re.search(
            r"method.*['\"]PATCH['\"]|['\"]PATCH['\"]",
            body,
        ), "toggleEpicDraft must use PATCH method for the status update"

    def test_toggle_epic_draft_patch_called_outside_if_else(self, script):
        """The status PATCH must happen for both draft and non-draft cases (after if/else)."""
        body = _get_toggle_epic_draft_body(script)
        # Find the PATCH call position
        patch_pos = body.find("PATCH")
        assert patch_pos != -1, "PATCH must be present in toggleEpicDraft"
        # Find the end of the if/else block
        else_match = re.search(
            r"\}\s*else\s*\{.*?\}",
            body,
            re.DOTALL,
        )
        if else_match:
            else_end = else_match.end()
            # PATCH should come after the if/else block
            assert patch_pos > else_end or (
                # Or PATCH appears twice — one after if/else for status update
                body.count("PATCH") >= 1
            ), "Status PATCH must be called after the label add/remove if/else block"

    # -----------------------------------------------------------------------
    # toggleEpicDraft calls refreshBoard after completion
    # -----------------------------------------------------------------------

    def test_toggle_epic_draft_calls_refresh_board(self, script):
        """toggleEpicDraft must call refreshBoard() after completing label+status changes."""
        body = _get_toggle_epic_draft_body(script)
        assert "refreshBoard" in body, (
            "toggleEpicDraft must call refreshBoard() after completing the operation"
        )

    def test_toggle_epic_draft_calls_refresh_board_after_patch(self, script):
        """refreshBoard must be called after the PATCH (status update), not before."""
        body = _get_toggle_epic_draft_body(script)
        patch_pos = body.find("PATCH")
        refresh_pos = body.find("refreshBoard")
        assert patch_pos != -1, "PATCH must be present"
        assert refresh_pos != -1, "refreshBoard must be present"
        assert refresh_pos > patch_pos, (
            "refreshBoard() must be called after the PATCH (status update)"
        )

    # -----------------------------------------------------------------------
    # toggleEpicDraft handles errors gracefully
    # -----------------------------------------------------------------------

    def test_toggle_epic_draft_has_error_handling(self, script):
        """toggleEpicDraft must handle errors gracefully (try/catch)."""
        body = _get_toggle_epic_draft_body(script)
        assert "try" in body and "catch" in body, (
            "toggleEpicDraft must use try/catch for error handling"
        )

    def test_toggle_epic_draft_logs_errors(self, script):
        """toggleEpicDraft must log errors to console on failure."""
        body = _get_toggle_epic_draft_body(script)
        assert re.search(
            r"console\.(error|warn|log)",
            body,
        ), "toggleEpicDraft must log errors to the console in the catch block"

    # -----------------------------------------------------------------------
    # Button placed in swimlane-actions
    # -----------------------------------------------------------------------

    def test_toggle_button_is_in_swimlane_actions(self, script):
        """The toggle button must be inside the swimlane-actions span."""
        body = _get_render_swimlane_body(script)
        actions_match = re.search(
            r"swimlane-actions[\"']?\s*>(.*?)</span>",
            body,
            re.DOTALL,
        )
        assert actions_match, "Could not find swimlane-actions span content"
        actions_body = actions_match.group(1)
        assert "toggleEpicDraft" in actions_body, (
            "toggleEpicDraft button must be inside the swimlane-actions span"
        )

    def test_toggle_button_rendered_after_details_button(self, script):
        """The toggle button must appear after the 'Details' button in the actions area."""
        body = _get_render_swimlane_body(script)
        details_pos = body.find("openDetailPanel")
        toggle_pos = body.find("toggleEpicDraft")
        assert details_pos != -1, "Details button (openDetailPanel) must be present"
        assert toggle_pos != -1, "toggleEpicDraft button must be present"
        assert toggle_pos > details_pos, (
            "toggleEpicDraft button must appear after the 'Details' button"
        )
