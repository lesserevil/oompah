"""Tests for the credential-error warning banner in dashboard.html (TASK-404).

Uses the same static-analysis approach as other dashboard tests: parse
dashboard.html, locate the relevant HTML elements and JS functions, and
assert that the credential warning rendering logic is correctly wired.

Acceptance criteria verified here:
- The credential-error banner element exists in the HTML with the correct id
- The banner is hidden by default (``hidden`` attribute)
- The banner has appropriate ARIA attributes for accessibility
- handleStateUpdate() separates cred_error alerts from other alerts
- handleStateUpdate() shows the banner when cred_error alerts are present
- handleStateUpdate() hides the banner when there are no cred_error alerts
- The banner renders alert messages using the esc() sanitiser (XSS safety)
- Non-cred-error alerts are still rendered in the agent-bar warnings span
- Non-credential alerts are also rendered in a dedicated banner with title,
  detail, action, and source context when provided
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers — load dashboard.html and extract JS/HTML
# ---------------------------------------------------------------------------


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


def _get_func_body(script: str, fn_name: str) -> str:
    """Extract the body of a top-level JS function by balanced-brace scan."""
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{")
    m = pattern.search(script)
    assert m, f"Could not find function {fn_name} in script"
    start = m.end() - 1  # index of '{'
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
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_script(html)


@pytest.fixture(scope="module")
def handle_state_body(script: str) -> str:
    return _get_func_body(script, "handleStateUpdate")


@pytest.fixture(scope="module")
def render_alert_item_body(script: str) -> str:
    return _get_func_body(script, "renderAlertItem")


@pytest.fixture(scope="module")
def render_alert_summary_body(script: str) -> str:
    return _get_func_body(script, "renderAlertSummary")


# ===========================================================================
# 1. HTML structure — banner element exists with correct attributes
# ===========================================================================


class TestCredentialBannerHTML:
    """The credential-error banner element must exist in the HTML markup."""

    def test_banner_element_exists(self, html: str):
        """The cred-error-banner div must be present."""
        assert 'id="cred-error-banner"' in html, (
            "dashboard must contain element with id='cred-error-banner'"
        )

    def test_banner_is_hidden_by_default(self, html: str):
        """The banner must have the 'hidden' attribute so it starts invisible."""
        # Find the cred-error-banner element
        match = re.search(r'id="cred-error-banner"[^>]*>', html)
        assert match, "cred-error-banner element not found"
        tag_str = match.group(0)
        assert "hidden" in tag_str, (
            "cred-error-banner must have 'hidden' attribute so it is invisible by default"
        )

    def test_banner_has_role_alert(self, html: str):
        """The banner must have role='alert' for screen reader accessibility."""
        match = re.search(r'id="cred-error-banner"[^>]*>', html)
        assert match, "cred-error-banner element not found"
        tag_str = match.group(0)
        assert 'role="alert"' in tag_str, (
            "cred-error-banner must have role='alert' for accessibility"
        )

    def test_banner_has_aria_live(self, html: str):
        """The banner must have aria-live for live region announcements."""
        match = re.search(r'id="cred-error-banner"[^>]*>', html)
        assert match, "cred-error-banner element not found"
        tag_str = match.group(0)
        assert "aria-live" in tag_str, (
            "cred-error-banner must have aria-live attribute"
        )

    def test_banner_has_aria_label(self, html: str):
        """The banner must have an aria-label for context."""
        match = re.search(r'id="cred-error-banner"[^>]*>', html)
        assert match, "cred-error-banner element not found"
        tag_str = match.group(0)
        assert "aria-label" in tag_str, (
            "cred-error-banner must have aria-label"
        )

    def test_cred_error_list_element_exists(self, html: str):
        """The cred-error-list ul element must exist inside the banner."""
        assert 'id="cred-error-list"' in html, (
            "dashboard must contain a ul with id='cred-error-list' for alert items"
        )

    def test_banner_placed_between_agent_bar_and_main_area(self, html: str):
        """The banner must appear between agent-bar and main-area in the DOM order."""
        pos_agent_bar = html.find('id="agent-bar"')
        pos_cred_banner = html.find('id="cred-error-banner"')
        pos_main_area = html.find('class="main-area"')
        assert pos_agent_bar != -1, "agent-bar element not found"
        assert pos_cred_banner != -1, "cred-error-banner element not found"
        assert pos_main_area != -1, "main-area element not found"
        assert pos_agent_bar < pos_cred_banner < pos_main_area, (
            "cred-error-banner must be placed after agent-bar and before main-area"
        )


# ===========================================================================
# 2. CSS — banner styles are present
# ===========================================================================


class TestCredentialBannerCSS:
    """The credential-error banner must have corresponding CSS."""

    def test_cred_error_banner_css_exists(self, html: str):
        assert ".cred-error-banner" in html, (
            "dashboard CSS must include .cred-error-banner rule"
        )

    def test_cred_error_banner_hidden_css_exists(self, html: str):
        assert ".cred-error-banner[hidden]" in html, (
            "dashboard CSS must include .cred-error-banner[hidden] rule to hide the banner"
        )

    def test_cred_error_uses_red_color_variable(self, html: str):
        # Find the .cred-error-banner CSS block and check it references --red
        style_section = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
        assert style_section, "no <style> block found"
        css = style_section.group(1)
        # Find .cred-error-banner rules
        cred_css_match = re.search(
            r"\.cred-error-banner\s*\{[^}]*\}", css, re.DOTALL
        )
        # The banner CSS block or one of its children should reference --red
        assert "var(--red)" in css, (
            "cred-error banner CSS must use var(--red) for the error color"
        )


# ===========================================================================
# 3. JavaScript — handleStateUpdate() renders the credential banner
# ===========================================================================


class TestHandleStateUpdateCredentialBanner:
    """handleStateUpdate() must show/hide the credential banner correctly."""

    def test_separates_cred_error_alerts_from_other_alerts(
        self, handle_state_body: str
    ):
        """Must filter alerts by source prefix 'cred_error:' into a separate array."""
        # The code must split alerts into cred-alerts and others
        assert re.search(
            r"source.*indexOf.*cred_error",
            handle_state_body,
        ), "must filter alerts by 'cred_error:' source prefix"

    def test_renders_cred_alerts_to_banner_list(self, handle_state_body: str):
        """Must populate cred-error-list with credential alert messages."""
        assert "cred-error-list" in handle_state_body, (
            "handleStateUpdate must reference cred-error-list to populate it"
        )

    def test_shows_banner_when_cred_alerts_present(self, handle_state_body: str):
        """Must set credBanner.hidden = false when there are credential alerts."""
        assert re.search(
            r"credBanner\.hidden\s*=\s*false",
            handle_state_body,
        ), "must set credBanner.hidden = false when credential alerts are present"

    def test_hides_banner_when_no_cred_alerts(self, handle_state_body: str):
        """Must set credBanner.hidden = true when there are no credential alerts."""
        assert re.search(
            r"credBanner\.hidden\s*=\s*true",
            handle_state_body,
        ), "must set credBanner.hidden = true when no credential alerts"

    def test_references_cred_error_banner_element(self, handle_state_body: str):
        """Must retrieve the cred-error-banner element."""
        assert re.search(
            r"getElementById\(['\"]cred-error-banner['\"]\)",
            handle_state_body,
        ), "must get the cred-error-banner element by id"

    def test_uses_esc_to_sanitise_messages(self, handle_state_body: str):
        """Credential alert messages must be sanitised through esc() before insertion."""
        # Find the part that renders cred alerts into list items
        # The pattern should be esc(a.message) when building the li content
        assert re.search(
            r"esc\(a\.message\)",
            handle_state_body,
        ), "alert messages must be sanitised with esc() to prevent XSS"

    def test_non_cred_alerts_still_rendered_in_agent_bar(
        self, handle_state_body: str
    ):
        """Non-credential alerts must still be rendered in the agent-warnings span."""
        assert "agent-warnings" in handle_state_body, (
            "agent-warnings span must still be updated for non-credential alerts"
        )

    def test_cred_alerts_not_in_agent_bar_warning(self, handle_state_body: str):
        """Credential alerts must be separated from the agent-bar warning span."""
        # The otherAlerts (non-cred) go to agent-warnings; credAlerts go to banner.
        # Verify there's a filter that excludes cred_error: from the agent bar path.
        assert re.search(
            r"otherAlerts|other_alerts",
            handle_state_body,
        ), "must have a separate variable for non-credential alerts rendered in agent bar"


# ===========================================================================
# 4. JavaScript — explanatory alert banner for non-credential alerts
# ===========================================================================


class TestGenericAlertBannerHTML:
    """Non-credential alerts must have a visible explanatory banner."""

    def test_alerts_banner_element_exists(self, html: str):
        assert 'id="alerts-banner"' in html, (
            "dashboard must contain element with id='alerts-banner'"
        )

    def test_alerts_banner_is_hidden_by_default(self, html: str):
        match = re.search(r'id="alerts-banner"[^>]*>', html)
        assert match, "alerts-banner element not found"
        assert "hidden" in match.group(0), (
            "alerts-banner must have 'hidden' so it starts invisible"
        )

    def test_alerts_banner_has_status_region(self, html: str):
        match = re.search(r'id="alerts-banner"[^>]*>', html)
        assert match, "alerts-banner element not found"
        tag_str = match.group(0)
        assert 'role="status"' in tag_str
        assert "aria-live" in tag_str
        assert "aria-label" in tag_str

    def test_alerts_list_element_exists(self, html: str):
        assert 'id="alerts-list"' in html, (
            "dashboard must contain a list with id='alerts-list'"
        )


class TestHandleStateUpdateGenericAlertBanner:
    """handleStateUpdate() must show explanatory fields for other alerts."""

    def test_references_alert_banner_elements(self, handle_state_body: str):
        assert re.search(
            r"getElementById\(['\"]alerts-banner['\"]\)",
            handle_state_body,
        ), "must get alerts-banner by id"
        assert re.search(
            r"getElementById\(['\"]alerts-list['\"]\)",
            handle_state_body,
        ), "must get alerts-list by id"

    def test_shows_alert_banner_when_other_alerts_present(
        self, handle_state_body: str
    ):
        assert re.search(
            r"alertsBanner\.hidden\s*=\s*false",
            handle_state_body,
        ), "must show alerts-banner when non-credential alerts are present"

    def test_hides_alert_banner_when_no_other_alerts(self, handle_state_body: str):
        assert re.search(
            r"alertsBanner\.hidden\s*=\s*true",
            handle_state_body,
        ), "must hide alerts-banner when no non-credential alerts are present"

    def test_renders_alert_items_into_alerts_list(self, handle_state_body: str):
        assert "renderAlertItem" in handle_state_body
        assert "alertsList.innerHTML" in handle_state_body

    def test_agent_bar_uses_explanatory_alert_summary(
        self, handle_state_body: str
    ):
        assert "renderAlertSummary" in handle_state_body


class TestGenericAlertRenderingHelpers:
    """Alert rendering helpers must use every explanatory field safely."""

    def test_summary_uses_title_detail_and_action(
        self, render_alert_summary_body: str
    ):
        assert "alertPrimaryText(alert)" in render_alert_summary_body
        assert "alertDetailText(alert)" in render_alert_summary_body
        assert "alertActionText(alert)" in render_alert_summary_body
        assert "tooltip" in render_alert_summary_body

    def test_item_renders_title_detail_action_and_source(
        self, render_alert_item_body: str
    ):
        assert "alertPrimaryText(alert)" in render_alert_item_body
        assert "alertDetailText(alert)" in render_alert_item_body
        assert "alertActionText(alert)" in render_alert_item_body
        assert "alert.source" in render_alert_item_body
        assert "alert-title" in render_alert_item_body
        assert "alert-detail" in render_alert_item_body
        assert "alert-action" in render_alert_item_body
        assert "alert-source" in render_alert_item_body

    def test_item_escapes_all_rendered_alert_fields(
        self, render_alert_item_body: str
    ):
        assert "esc(title)" in render_alert_item_body
        assert "esc(detail)" in render_alert_item_body
        assert "esc(action)" in render_alert_item_body
        assert "esc(source)" in render_alert_item_body
