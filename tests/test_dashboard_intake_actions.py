"""Tests for intake action controls in the dashboard detail panel."""

from __future__ import annotations

import re
from pathlib import Path


def _load_dashboard_script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _function_body(script: str, name: str) -> str:
    pattern = re.compile(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{")
    match = pattern.search(script)
    assert match, f"Could not find function {name}"
    brace = match.end() - 1
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


class TestDashboardIntakeActions:
    def test_css_classes_exist(self):
        html = (
            Path(__file__).resolve().parents[1]
            / "oompah"
            / "templates"
            / "dashboard.html"
        ).read_text(encoding="utf-8")

        assert ".intake-actions" in html
        assert ".intake-action-button" in html
        assert ".intake-actor-button" in html

    def test_open_detail_panel_passes_actor_to_detail_api(self):
        script = _load_dashboard_script()
        body = _function_body(script, "openDetailPanel")

        assert "const intakeActor = intakeActorLogin();" in body
        assert "detailParams.actor = intakeActor" in body
        assert "issueApiUrl(identifier, '/detail', detailParams)" in body

    def test_render_intake_actions_only_for_proposed_state(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderIntakeActions")

        assert "statusKey(detail.state) !== 'proposed'" in body
        assert "return ''" in body

    def test_requestor_button_depends_on_requestor_permission(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderIntakeActions")

        idx = body.index("perms.can_requestor_approve")
        surrounding = body[idx : idx + 260]
        assert "Approve Scope" in surrounding
        assert "requestor-approve" in surrounding

    def test_owner_buttons_depend_on_owner_permissions(self):
        script = _load_dashboard_script()
        body = _function_body(script, "renderIntakeActions")

        assert "perms.can_request_changes" in body
        assert "Request Changes" in body
        assert "perms.can_override_readiness" in body
        assert "Override Readiness" in body
        assert "perms.can_promote_to_backlog" in body
        assert "Promote to Backlog" in body

    def test_perform_intake_action_posts_to_intake_endpoint(self):
        script = _load_dashboard_script()
        body = _function_body(script, "performIntakeAction")

        assert "'/intake/' + action" in body
        assert "method: 'POST'" in body
        assert "issueRequestBody(identifier, payload)" in body
        assert "actor" in body

    def test_update_issue_adds_project_status_actor_for_protected_moves(self):
        script = _load_dashboard_script()
        body = _function_body(script, "updateIssue")

        assert "statusChangeNeedsProjectActor" in body
        assert "await refreshProjectConfigForStatusActor" in body
        assert "projectStatusActorLogin(project)" in body
        assert "outgoing.actor_login = actor" in body
        assert "prompt(" not in body

    def test_status_actor_needed_when_local_issue_missing_but_opening_github_project(self):
        script = _load_dashboard_script()
        body = _function_body(script, "statusChangeNeedsProjectActor")

        assert "(project && project.tracker_kind) || (issue && issue.tracker_kind)" in body
        assert "trackerKind !== 'github_issues'" in body
        assert "const toKey = statusKey(targetStatus)" in body
        assert "if (toKey === 'open') return true" in body
        assert "if (!issue) return false" in body

    def test_status_actor_needed_for_optimistic_drag_to_open(self):
        script = _load_dashboard_script()
        body = _function_body(script, "statusChangeNeedsProjectActor")

        assert "if (toKey === 'open') return true" in body
        assert "fromKey === 'proposed' && toKey === 'backlog'" in body

    def test_update_issue_refreshes_project_config_for_protected_moves(self):
        script = _load_dashboard_script()
        body = _function_body(script, "refreshProjectConfigForStatusActor")

        assert "fetch('/api/v1/state')" in body
        assert "currentProjects = state.projects" in body
        assert "currentProjects.find(p => p.id === projectId)" in body

    def test_project_status_actor_prefers_configured_actor(self):
        script = _load_dashboard_script()
        body = _function_body(script, "projectStatusActorLogin")

        assert "project.status_actor_login" in body
        assert "project.status_label_authorized_logins" in body
        assert "project.tracker_owner" in body

    def test_update_issue_surfaces_persistent_board_errors(self):
        script = _load_dashboard_script()
        body = _function_body(script, "updateIssue")

        assert "showBoardError(message)" in body
        assert "clearBoardError()" in body

    def test_board_error_region_exists(self):
        html = (
            Path(__file__).resolve().parents[1]
            / "oompah"
            / "templates"
            / "dashboard.html"
        ).read_text(encoding="utf-8")

        assert 'id="board-error"' in html
        assert 'role="alert"' in html
