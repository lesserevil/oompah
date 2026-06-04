"""Tests for TASK-433: Show provider and model in agent log popup.

The activity overlay panel should display the provider and model name
associated with the agent run on its own line in the popup header.
These tests use static analysis of dashboard.html (JS and HTML) and
unit-test the server/orchestrator snapshot API.
"""

from __future__ import annotations

import os
import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — load dashboard.html and extract relevant JS pieces
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
    """Extract the body of a top-level function by balanced-brace scan."""
    pattern = re.compile(rf"(?:async\s+)?function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{")
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
def html():
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


# ===========================================================================
# 1. HTML: provider/model div exists and is correctly placed
# ===========================================================================


class TestProviderModelHTMLElement:
    """The provider/model element must be present in the activity panel header."""

    def test_element_exists(self, html):
        assert 'id="activity-provider-model"' in html, (
            "Element with id='activity-provider-model' must be present in dashboard HTML"
        )

    def test_element_initially_hidden(self, html):
        """Element should start hidden and be shown only when data is available."""
        match = re.search(
            r'id="activity-provider-model"([^>]*>)',
            html,
        )
        assert match, "Could not find activity-provider-model element"
        tag = match.group(0)
        assert "hidden" in tag, (
            "activity-provider-model must have the 'hidden' attribute initially "
            "so it doesn't show an empty line when no metadata is available"
        )

    def test_element_inside_activity_overlay(self, html):
        overlay_idx = html.find('id="activity-overlay"')
        pm_idx = html.find('id="activity-provider-model"')
        title_idx = html.find('id="activity-title"')
        assert overlay_idx != -1, "activity-overlay must exist"
        assert pm_idx != -1, "activity-provider-model must exist"
        assert title_idx != -1, "activity-title must exist"
        assert overlay_idx < pm_idx, (
            "activity-provider-model must be inside activity-overlay"
        )

    def test_element_after_title(self, html):
        """Provider/model line must come after the agent title."""
        title_idx = html.find('id="activity-title"')
        pm_idx = html.find('id="activity-provider-model"')
        assert title_idx < pm_idx, (
            "activity-provider-model must appear after activity-title in the DOM"
        )

    def test_element_before_toolbar(self, html):
        """Provider/model line must be in the header, before the toolbar."""
        pm_idx = html.find('id="activity-provider-model"')
        toolbar_idx = html.find('class="activity-toolbar"')
        assert pm_idx < toolbar_idx, (
            "activity-provider-model must appear before the activity-toolbar"
        )


# ===========================================================================
# 2. CSS: provider/model metadata is styled for readability
# ===========================================================================


class TestProviderModelCSS:
    """CSS must style the provider/model line as muted and readable."""

    def test_css_rule_exists(self, html):
        assert ".activity-provider-model" in html, (
            ".activity-provider-model CSS class must be defined"
        )

    def test_css_uses_muted_color(self, html):
        match = re.search(r"\.activity-provider-model\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .activity-provider-model CSS rule"
        css = match.group(1)
        assert "text-muted" in css, (
            ".activity-provider-model must use var(--text-muted) for muted appearance"
        )

    def test_css_handles_overflow(self, html):
        """Long provider/model strings must not break the layout."""
        match = re.search(r"\.activity-provider-model\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .activity-provider-model CSS rule"
        css = match.group(1)
        assert "overflow" in css or "text-overflow" in css or "ellipsis" in css, (
            ".activity-provider-model must handle overflow for long strings "
            "(overflow:hidden, text-overflow:ellipsis, or similar)"
        )

    def test_css_small_font(self, html):
        match = re.search(r"\.activity-provider-model\s*\{([^}]+)\}", html, re.DOTALL)
        assert match, "Could not find .activity-provider-model CSS rule"
        css = match.group(1)
        assert "font-size" in css, (
            ".activity-provider-model must set a small font-size to distinguish "
            "it from the main title"
        )


# ===========================================================================
# 3. JS: setActivityProviderModel function exists with correct logic
# ===========================================================================


class TestSetActivityProviderModelFunction:
    """setActivityProviderModel must correctly build and display the text."""

    def test_function_exists(self, script):
        assert "function setActivityProviderModel(" in script, (
            "setActivityProviderModel() must be defined in the dashboard script"
        )

    def test_joins_provider_and_model_with_middot(self, script):
        body = _get_func_body(script, "setActivityProviderModel")
        assert "·" in body, (
            "setActivityProviderModel must join provider and model with '·' middot"
        )

    def test_sets_tooltip_title(self, script):
        body = _get_func_body(script, "setActivityProviderModel")
        assert ".title" in body, (
            "setActivityProviderModel must set el.title for tooltip on truncated long values"
        )

    def test_hides_when_no_data(self, script):
        body = _get_func_body(script, "setActivityProviderModel")
        assert "hidden" in body, (
            "setActivityProviderModel must set el.hidden=true when no metadata is available"
        )

    def test_unhides_when_data_present(self, script):
        body = _get_func_body(script, "setActivityProviderModel")
        assert "false" in body, (
            "setActivityProviderModel must set el.hidden=false when metadata is available"
        )


# ===========================================================================
# 4. JS: openActivityPanel reads provider/model from running agent snapshot
# ===========================================================================


class TestOpenActivityPanelReadsMetadata:
    """openActivityPanel must populate the provider/model element from lastRunningAgents."""

    def test_reads_provider_name(self, script):
        body = _get_func_body(script, "openActivityPanel")
        assert "provider_name" in body, (
            "openActivityPanel must read agent.provider_name from the running agent snapshot"
        )

    def test_reads_model_name(self, script):
        body = _get_func_body(script, "openActivityPanel")
        assert "model_name" in body, (
            "openActivityPanel must read agent.model_name from the running agent snapshot"
        )

    def test_calls_set_activity_provider_model(self, script):
        body = _get_func_body(script, "openActivityPanel")
        assert "setActivityProviderModel" in body, (
            "openActivityPanel must call setActivityProviderModel() to update the header"
        )

    def test_gets_pm_element(self, script):
        body = _get_func_body(script, "openActivityPanel")
        assert "activity-provider-model" in body, (
            "openActivityPanel must look up the activity-provider-model DOM element"
        )


# ===========================================================================
# 5. JS: refreshActivity updates provider/model from API response
# ===========================================================================


class TestRefreshActivityUpdatesMetadata:
    """refreshActivity must update the provider/model element from the API response."""

    def test_reads_provider_name_from_data(self, script):
        body = _get_func_body(script, "refreshActivity")
        assert "provider_name" in body, (
            "refreshActivity must read data.provider_name from the API response"
        )

    def test_reads_model_name_from_data(self, script):
        body = _get_func_body(script, "refreshActivity")
        assert "model_name" in body, (
            "refreshActivity must read data.model_name from the API response"
        )

    def test_calls_set_activity_provider_model(self, script):
        body = _get_func_body(script, "refreshActivity")
        assert "setActivityProviderModel" in body, (
            "refreshActivity must call setActivityProviderModel() when API returns metadata"
        )


# ===========================================================================
# 6. JS: closeActivityPanel clears provider/model element
# ===========================================================================


class TestCloseActivityPanelClearsMetadata:
    """closeActivityPanel must clear the provider/model element on close."""

    def test_clears_pm_element(self, script):
        body = _get_func_body(script, "closeActivityPanel")
        assert "activity-provider-model" in body, (
            "closeActivityPanel must clear/reset the activity-provider-model element"
        )


# ===========================================================================
# 7. Backend: get_snapshot includes provider_name and model_name in running rows
# ===========================================================================


class TestOrchestratorSnapshot:
    """get_snapshot() must include provider_name and model_name in running rows.

    We verify this via static analysis of orchestrator.py — the get_snapshot
    method's running row dict must contain both fields.
    """

    @pytest.fixture(scope="class")
    def get_snapshot_body(self):
        orch_path = os.path.join(
            os.path.dirname(__file__), os.pardir, "oompah", "orchestrator.py"
        )
        with open(orch_path) as f:
            code = f.read()

        # Extract the get_snapshot method body
        match = re.search(
            r"def get_snapshot\(self\).*?(?=\n    def |\Z)",
            code,
            re.DOTALL,
        )
        assert match, "Could not find get_snapshot in orchestrator.py"
        return match.group(0)

    def test_snapshot_includes_provider_name(self, get_snapshot_body):
        assert '"provider_name"' in get_snapshot_body or "'provider_name'" in get_snapshot_body, (
            "get_snapshot() must include 'provider_name' in the running row dict"
        )

    def test_snapshot_includes_model_name(self, get_snapshot_body):
        assert '"model_name"' in get_snapshot_body or "'model_name'" in get_snapshot_body, (
            "get_snapshot() must include 'model_name' in the running row dict"
        )

    def test_snapshot_reads_entry_provider_name(self, get_snapshot_body):
        assert "entry.provider_name" in get_snapshot_body, (
            "get_snapshot() must read provider_name from the RunningEntry"
        )

    def test_snapshot_reads_entry_model_name(self, get_snapshot_body):
        assert "entry.model_name" in get_snapshot_body, (
            "get_snapshot() must read model_name from the RunningEntry"
        )


# ===========================================================================
# 8. Backend: activity API returns provider_name and model_name
# ===========================================================================


class TestActivityAPIResponse:
    """The /api/v1/agents/{id}/activity endpoint must include provider/model."""

    def test_api_response_includes_provider_name(self):
        """Confirm the server code references provider_name in the activity response."""
        server_path = os.path.join(
            os.path.dirname(__file__), os.pardir, "oompah", "server.py"
        )
        with open(server_path) as f:
            server_code = f.read()

        # Find the api_agent_activity function body
        match = re.search(
            r"async def api_agent_activity\(identifier.*?\n(.*?)(?=\n@app\.|\Z)",
            server_code,
            re.DOTALL,
        )
        assert match, "Could not find api_agent_activity function in server.py"
        body = match.group(1)
        assert "provider_name" in body, (
            "api_agent_activity must include provider_name in the response"
        )
        assert "model_name" in body, (
            "api_agent_activity must include model_name in the response"
        )
