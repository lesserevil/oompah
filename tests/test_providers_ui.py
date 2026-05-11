"""Tests for the ACP-mode toggle in the provider dialog (oompah-zlz_2-keb).

The dashboard UI lives in oompah/templates/providers.html. These tests
verify the static HTML/JS structure for the new Mode radio group, the
ACP-specific fields, the visibility toggling helper, and the API/ACP
badge in the provider list cards.
"""

from __future__ import annotations

import os
import re

import pytest


def _load_providers_html() -> str:
    path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "providers.html",
    )
    with open(path, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def html() -> str:
    return _load_providers_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    """Concatenate every <script>…</script> block."""
    matches = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    assert matches, "No <script> block found in providers.html"
    return "\n".join(matches)


class TestModeRadioGroup:
    """The provider dialog must let the operator pick API or ACP."""

    def test_mode_api_radio_present(self, html):
        assert 'id="prov-mode-api"' in html
        assert 'value="api"' in html

    def test_mode_acp_radio_present(self, html):
        assert 'id="prov-mode-acp"' in html
        assert 'value="acp"' in html

    def test_mode_radio_default_checked(self, html):
        # API is the default — preserves all legacy provider behavior.
        assert re.search(r'id="prov-mode-api"[^>]*checked', html), \
            "API radio must be checked by default"

    def test_mode_radio_group_share_name(self, html):
        # Both radios live in a single name= group so the browser
        # treats them as mutually exclusive.
        assert html.count('name="prov-mode"') >= 2


class TestAcpDialogFields:
    @pytest.mark.parametrize("field_id", [
        "prov-acp-permission-mode",
        "prov-acp-subscription-only",
        "prov-url-row",
        "prov-key-row",
        "prov-acp-permission-row",
        "prov-acp-subscription-row",
    ])
    def test_dialog_fields_present(self, html, field_id):
        assert f'id="{field_id}"' in html, f"Missing dialog id={field_id}"

    def test_permission_mode_options(self, html):
        # All four canonical Claude Agent SDK permission modes.
        for opt in ("default", "acceptEdits", "plan", "bypassPermissions"):
            assert f'value="{opt}"' in html, f"Missing permission mode option: {opt}"

    def test_subscription_only_default_checked(self, html):
        # New ACP providers default to subscription_only=true since the
        # common case is wiring up the operator's claude subscription.
        assert re.search(r'id="prov-acp-subscription-only"[^>]*checked', html)

    def test_acp_rows_hidden_by_default(self, html):
        # ACP-only rows must be display:none so they don't show on
        # initial Add Provider open (mode defaults to API).
        assert re.search(
            r'id="prov-acp-permission-row"[^>]*style="display:none', html
        ), "prov-acp-permission-row must be hidden by default"
        assert re.search(
            r'id="prov-acp-subscription-row"[^>]*style="display:none', html
        ), "prov-acp-subscription-row must be hidden by default"


class TestVisibilityToggle:
    """The helper that flips dialog rows on Mode change."""

    def test_helper_defined(self, script):
        assert "function applyProviderModeVisibility" in script

    def test_helper_called_on_dialog_open(self, script):
        assert "applyProviderModeVisibility()" in script

    def test_helper_wired_to_radio_change(self, html):
        # onchange on each radio invokes the helper so flipping the
        # Mode toggle immediately updates field visibility.
        assert html.count("applyProviderModeVisibility()") >= 2

    def test_helper_hides_url_and_key_in_acp(self, script):
        # The toggle must hide base_url + api_key when ACP is selected.
        assert "prov-url-row" in script
        assert "prov-key-row" in script
        # Match the api/acp visibility logic (display=none for api-only
        # rows when acp is checked).
        assert re.search(r"display\s*=\s*acp\s*\?\s*['\"]none['\"]", script), \
            "applyProviderModeVisibility must hide api-only rows when acp"

    def test_helper_shows_acp_rows_in_acp(self, script):
        assert "prov-acp-permission-row" in script
        assert "prov-acp-subscription-row" in script

    def test_helper_hides_fetch_models_in_acp(self, script):
        # Fetch Models hits the provider's /v1/models endpoint, which
        # is meaningless for an ACP provider.
        assert "fetch-models-btn" in script


class TestSubmitProvider:
    """The submit handler must serialize the new fields and validate."""

    def test_submit_reads_mode_radio(self, script):
        assert "prov-mode-acp" in script

    def test_submit_includes_mode_in_body(self, script):
        # mode is always sent; the server normalizes it.
        assert re.search(r"mode\s*[,:}]", script), \
            "submitProvider must include mode in the request body"

    def test_submit_includes_acp_permission_mode(self, script):
        assert "acp_permission_mode" in script

    def test_submit_includes_acp_subscription_only(self, script):
        assert "acp_subscription_only" in script

    def test_submit_skips_base_url_check_in_acp(self, script):
        # The client mirrors the server validation: api requires
        # base_url, acp does not.
        assert re.search(r"mode\s*===\s*['\"]api['\"]", script), \
            "submitProvider must branch on mode === 'api'"


class TestProviderCardBadge:
    """Provider list cards show an API/ACP badge so operators can tell at a glance."""

    def test_badge_uses_mode_field(self, script):
        # The card renderer prefixes a CSS class with mode-<mode>
        # mirroring the agent profile renderer.
        assert re.search(r"mode-\$\{esc\(.*mode.*\)\}", script) \
            or "mode-${esc(providerMode)}" in script

    def test_badge_text_is_uppercase_mode(self, script):
        # API/ACP badge text — toUpperCase on the rendered mode.
        assert "toUpperCase()" in script

    def test_acp_card_skips_url_and_key_lines(self, script):
        # ACP providers don't have a base_url or api_key to display;
        # the renderer must show the SDK-managed substitute instead.
        assert "managed by Claude Agent SDK" in script

    def test_card_renders_permission_mode_when_acp(self, script):
        # An ACP provider with a non-default permission mode shows
        # "Permission mode: <mode>" on its card.
        assert "acp_permission_mode" in script

    def test_card_renders_subscription_billing_when_acp(self, script):
        # An ACP provider with subscription_only=true shows a
        # "Billing: subscription-only" line.
        assert "subscription-only" in script
