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
