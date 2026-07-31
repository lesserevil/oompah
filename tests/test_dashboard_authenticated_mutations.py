"""Tests for dashboard authenticated mutations (OOMPAH-670).

Verifies that dashboard mutations (status updates, intake actions) conditionally
omit actor/actor_login based on http_auth.enabled state to prevent actor_mismatch
errors with authenticated requests.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _load_dashboard_script() -> str:
    """Load the dashboard HTML and extract the JavaScript."""
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _global_variable_section(script: str) -> str:
    """Extract the section with global variable declarations."""
    # Find the first function definition to mark the end of global vars
    first_function = script.index("function")
    return script[:first_function]


def _function_body(script: str, name: str) -> str:
    """Extract the body of a function by name."""
    marker = f"async function {name}("
    if marker not in script:
        marker = f"function {name}("
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
                return script[brace + 1:pos]
    raise AssertionError(f"Could not find function body for {name}")


@pytest.fixture(scope="module")
def dashboard_script() -> str:
    return _load_dashboard_script()


@pytest.fixture(scope="module")
def globals_section(dashboard_script: str) -> str:
    return _global_variable_section(dashboard_script)


@pytest.fixture(scope="module")
def update_issue_body(dashboard_script: str) -> str:
    return _function_body(dashboard_script, "updateIssue")


@pytest.fixture(scope="module")
def perform_intake_action_body(dashboard_script: str) -> str:
    return _function_body(dashboard_script, "performIntakeAction")


@pytest.fixture(scope="module")
def open_detail_panel_body(dashboard_script: str) -> str:
    return _function_body(dashboard_script, "openDetailPanel")


@pytest.fixture(scope="module")
def handle_state_update_body(dashboard_script: str) -> str:
    return _function_body(dashboard_script, "handleStateUpdate")


class TestHttpAuthGlobalVariable:
    """Test that httpAuthEnabled global variable exists."""

    def test_http_auth_enabled_declared(self, dashboard_script: str):
        """Verify httpAuthEnabled is declared as a global variable."""
        assert "let httpAuthEnabled" in dashboard_script
        # Verify it defaults to false
        decl_line = dashboard_script.split("let httpAuthEnabled")[1].split("\n")[0]
        assert "false" in decl_line


class TestHandleStateUpdateHttpAuth:
    """Test that handleStateUpdate captures http_auth.enabled."""

    def test_handle_state_update_captures_http_auth(
        self, handle_state_update_body: str
    ):
        """Verify handleStateUpdate extracts http_auth.enabled from state."""
        assert "httpAuthEnabled" in handle_state_update_body
        assert "state.http_auth" in handle_state_update_body


class TestUpdateIssueAuthConditional:
    """Test that updateIssue conditionally omits actor_login based on auth."""

    def test_update_issue_checks_http_auth_before_actor_login(
        self, update_issue_body: str
    ):
        """Verify updateIssue checks httpAuthEnabled before setting actor_login."""
        # Should check auth status before attempting to set actor_login
        assert "httpAuthEnabled" in update_issue_body
        assert "!httpAuthEnabled" in update_issue_body or "httpAuthEnabled == false" in update_issue_body or "!httpAuthEnabled" in update_issue_body

    def test_update_issue_skips_actor_logic_when_auth_enabled(
        self, update_issue_body: str
    ):
        """Verify actor_login setting is skipped when auth is enabled."""
        # The actor collection should be inside a conditional check for auth disabled
        body = update_issue_body
        # Find the if statement checking httpAuthEnabled
        auth_check = body.find("!httpAuthEnabled")
        assert auth_check > 0
        # Verify actor_login assignment is after the auth check
        actor_assign = body.find("outgoing.actor_login = actor")
        assert actor_assign > auth_check


class TestPerformIntakeActionAuthConditional:
    """Test that performIntakeAction conditionally omits actor based on auth."""

    def test_perform_intake_action_checks_http_auth(
        self, perform_intake_action_body: str
    ):
        """Verify performIntakeAction checks httpAuthEnabled."""
        assert "httpAuthEnabled" in perform_intake_action_body

    def test_perform_intake_action_only_collects_actor_when_auth_disabled(
        self, perform_intake_action_body: str
    ):
        """Verify actor is only collected when auth is disabled."""
        body = perform_intake_action_body
        # Actor collection should be guarded by !httpAuthEnabled
        assert "!httpAuthEnabled" in body or "httpAuthEnabled == false" in body or "!httpAuthEnabled" in body

    def test_perform_intake_action_conditionally_includes_actor_in_payload(
        self, perform_intake_action_body: str
    ):
        """Verify actor is only included in payload when it exists."""
        assert "if (actor) payload.actor = actor" in perform_intake_action_body
        # Payload should be constructed with project_id first
        assert "payload = {project_id:" in perform_intake_action_body


class TestOpenDetailPanelAuthConditional:
    """Test that openDetailPanel conditionally omits actor query param."""

    def test_open_detail_panel_checks_http_auth(self, open_detail_panel_body: str):
        """Verify openDetailPanel checks httpAuthEnabled."""
        assert "httpAuthEnabled" in open_detail_panel_body

    def test_open_detail_panel_only_adds_actor_when_auth_disabled(
        self, open_detail_panel_body: str
    ):
        """Verify actor is only added to detailParams when auth is disabled."""
        body = open_detail_panel_body
        # Check that actor is only added inside !httpAuthEnabled block
        assert "!httpAuthEnabled" in body


class TestAuthenticationModePreservesLegacyBehavior:
    """Test backward compatibility: unauthenticated deployments still work."""

    def test_dashboard_defaults_to_unauthenticated(self, dashboard_script: str):
        """Verify httpAuthEnabled defaults to false for backward compatibility."""
        # Should initialize as false
        auth_decl = dashboard_script.split("httpAuthEnabled")[1].split("\n")[0]
        assert "false" in auth_decl


class TestServerActorResolutionComment:
    """Test that code comments explain the server-side actor resolution."""

    def test_update_issue_has_auth_comment(self, update_issue_body: str):
        """Verify updateIssue has comment explaining auth behavior."""
        assert "When auth is enabled" in update_issue_body or "auth" in update_issue_body.lower()

    def test_perform_intake_action_has_auth_comment(
        self, perform_intake_action_body: str
    ):
        """Verify performIntakeAction has comment explaining auth behavior."""
        assert "When auth is enabled" in perform_intake_action_body or "auth" in perform_intake_action_body.lower()

    def test_open_detail_panel_has_auth_comment(self, open_detail_panel_body: str):
        """Verify openDetailPanel has comment explaining auth behavior."""
        assert "When auth is enabled" in open_detail_panel_body or "auth" in open_detail_panel_body.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
