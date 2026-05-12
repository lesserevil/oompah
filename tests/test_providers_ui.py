"""Tests for the provider dialog UI (oompah-zlz_2-zvm0).

The dashboard UI lives in oompah/templates/providers.html. These tests
verify the static HTML/JS structure after the dialog cleanup that
collapsed the legacy three-way Provider Type dropdown (openai |
anthropic | custom) and the separate Mode radio group into a single
two-value Provider Type dropdown (openai_compatible | acp). The
Backend sub-selector is hidden when Provider Type is openai_compatible
and revealed when it's acp; Fetch Models is ACP-aware.

Companion to:
* test_acp_backends.py (deeper Backend dropdown + registry tests).
* test_providers.py (the server-side dialog API surface).
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


class TestProviderTypeDropdown:
    """The Provider Type dropdown is the single source of api/acp choice.

    The legacy three-way dropdown (openai | anthropic | custom) has
    been collapsed to exactly two canonical values, and the separate
    Mode radio group has been removed entirely.
    """

    def test_dropdown_has_openai_compatible_option(self, html):
        assert re.search(
            r'<option value="openai_compatible">OpenAI Compatible</option>',
            html,
        )

    def test_dropdown_has_acp_option(self, html):
        # Display label is "Agent Control Protocol" (the full name).
        assert re.search(
            r'<option value="acp">Agent Control Protocol</option>',
            html,
        )

    def test_dropdown_does_not_have_legacy_anthropic_option(self, html):
        # The legacy "Anthropic" option was vestigial; the issue
        # explicitly requires it gone.
        assert not re.search(
            r'<option value="anthropic">', html
        ), "Legacy 'anthropic' option must be removed"

    def test_dropdown_does_not_have_legacy_custom_option(self, html):
        assert not re.search(
            r'<option value="custom">', html
        ), "Legacy 'custom' option must be removed"

    def test_dropdown_does_not_have_legacy_openai_option(self, html):
        # "openai" (lowercase legacy value) was the legacy id; we now
        # use "openai_compatible". The option element with that value
        # should be gone.
        assert not re.search(
            r'<option value="openai">', html
        ), "Legacy 'openai' option must be replaced by 'openai_compatible'"

    def test_dropdown_onchange_calls_visibility_helper(self, html):
        # Flipping the Provider Type must immediately re-evaluate which
        # fields are visible (Backend, Permission Mode, etc.).
        assert re.search(
            r'<select id="prov-type"[^>]*onchange="applyProviderModeVisibility\(\)"',
            html,
        )


class TestModeRadioRemoved:
    """The keb-era Mode radio group has been removed entirely.

    Provider Type is now the single source of truth for api/acp.
    """

    def test_mode_api_radio_absent(self, html):
        assert 'id="prov-mode-api"' not in html
        assert 'name="prov-mode"' not in html

    def test_mode_acp_radio_absent(self, html):
        assert 'id="prov-mode-acp"' not in html

    def test_mode_row_wrapper_absent(self, html):
        assert 'id="prov-mode-row"' not in html


class TestBackendSubSelector:
    """Backend dropdown for ACP-mode providers (oompah-zlz_2-zvm0 §2)."""

    def test_backend_row_present(self, html):
        assert 'id="prov-backend-row"' in html

    def test_backend_row_hidden_by_default(self, html):
        # The whole row is display:none until the operator picks ACP.
        assert re.search(
            r'id="prov-backend-row"[^>]*style="display:none', html,
        ), "prov-backend-row must be hidden by default"

    def test_backend_select_present(self, html):
        assert 'id="prov-backend"' in html

    def test_backend_select_has_claude_default(self, html):
        assert re.search(
            r'<select id="prov-backend"[^>]*>\s*<option value="claude">claude</option>',
            html, re.DOTALL,
        )

    def test_backend_disabled_when_single_entry(self, script):
        # renderBackendOptions() disables the dropdown when only one
        # backend is registered (today's state).
        assert "acpBackends.length <= 1" in script

    def test_backend_disabled_state_has_tooltip(self, script):
        # The disabled-with-tooltip state must mention upcoming backends.
        assert "Additional backends" in script

    def test_backend_onchange_refreshes_fetch_models(self, html):
        # Changing backend must refresh the Fetch Models button state
        # (some backends have a catalog, some don't).
        assert re.search(
            r'<select id="prov-backend"[^>]*onchange="updateFetchModelsButtonState\(\)"',
            html,
        )


class TestAcpFieldVisibility:
    """ACP-only dialog rows are hidden until Provider Type = acp."""

    @pytest.mark.parametrize("field_id", [
        "prov-backend-row",
        "prov-acp-permission-row",
        "prov-acp-subscription-row",
        "prov-billing-model-row",
    ])
    def test_acp_rows_hidden_by_default(self, html, field_id):
        # All ACP-only rows must default to display:none so opening
        # Add Provider (which defaults to openai_compatible) doesn't
        # show them.
        assert re.search(
            rf'id="{field_id}"[^>]*style="display:none', html,
        ), f"{field_id} must be hidden by default"

    def test_permission_mode_options(self, html):
        # All four canonical Claude Agent SDK permission modes.
        for opt in ("default", "acceptEdits", "plan", "bypassPermissions"):
            assert f'value="{opt}"' in html, f"Missing permission mode option: {opt}"

    def test_subscription_only_default_checked(self, html):
        assert re.search(r'id="prov-acp-subscription-only"[^>]*checked', html)


class TestVisibilityHelper:
    """applyProviderModeVisibility() flips rows based on prov-type."""

    def test_helper_defined(self, script):
        assert "function applyProviderModeVisibility" in script

    def test_helper_reads_prov_type(self, script):
        # Source-of-truth is the dropdown, not the (removed) radio.
        assert "prov-type" in script
        assert re.search(
            r"ptype\s*===\s*['\"]acp['\"]|providerType\s*===\s*['\"]acp['\"]",
            script,
        )

    def test_helper_called_on_dialog_open(self, script):
        assert "applyProviderModeVisibility()" in script

    def test_helper_toggles_backend_row(self, script):
        # The Backend sub-selector is one of the rows the helper flips.
        assert "prov-backend-row" in script

    def test_helper_toggles_permission_row(self, script):
        assert "prov-acp-permission-row" in script


class TestFetchModelsAcpAware:
    """Fetch Models button dispatches on provider type + backend."""

    def test_fetch_models_btn_present(self, html):
        assert 'id="fetch-models-btn"' in html

    def test_fetch_models_state_helper_defined(self, script):
        # The button is disabled with a tooltip when the selected ACP
        # backend has no model catalog (Claude SDK's case).
        assert "function updateFetchModelsButtonState" in script

    def test_fetch_models_sends_mode_and_backend(self, script):
        # The submit body to /api/v1/providers/fetch-models must carry
        # the mode + backend so the server can dispatch through the
        # ACP backend registry.
        assert re.search(r"mode\s*[,:]", script)
        assert re.search(r"backend\s*[,:]", script)

    def test_fetch_models_handles_note_response(self, script):
        # ACP backends with no catalog return {"models": [], "note": "..."}
        # — the dashboard surfaces the note as an inline alert rather
        # than a generic "no models" error.
        assert re.search(r"data\.note", script)

    def test_claude_descriptor_has_subscription_note(self, script):
        # The hardcoded fallback descriptor for "claude" carries the
        # subscription-managed note required by issue §3.
        assert "Claude SDK manages model selection via subscription." in script


class TestSubmitProvider:
    """The submit handler derives mode from provider_type."""

    def test_submit_does_not_read_radio(self, script):
        # Mode radio is removed — submit must NOT reference it.
        assert "prov-mode-acp" not in script
        assert "prov-mode-api" not in script

    def test_submit_derives_mode_from_provider_type(self, script):
        # mode = (providerType === 'acp') ? 'acp' : 'api'.
        assert re.search(r"providerType\s*===\s*['\"]acp['\"]", script)

    def test_submit_includes_provider_type_in_body(self, script):
        assert re.search(r"provider_type\s*:\s*providerType", script)

    def test_submit_includes_mode_in_body(self, script):
        assert re.search(r"mode\s*[,:}]", script), \
            "submitProvider must include mode in the request body"

    def test_submit_includes_backend_in_body(self, script):
        assert re.search(r"backend\s*:", script)

    def test_submit_includes_acp_permission_mode(self, script):
        assert "acp_permission_mode" in script

    def test_submit_includes_acp_subscription_only(self, script):
        assert "acp_subscription_only" in script


class TestProviderCardBadge:
    """Provider list cards show a single API/ACP badge."""

    def test_card_badge_uses_mode(self, script):
        # Single badge driven off mode; legacy duplicate provider_type
        # badge was removed since the two fields are now isomorphic.
        assert "providerMode.toUpperCase()" in script

    def test_card_does_not_render_duplicate_provider_type_badge(self, script):
        # The legacy second badge (p.provider_type) was dropped.
        assert not re.search(
            r"<span class=\"provider-type\">\$\{esc\(p\.provider_type\)\}",
            script,
        )

    def test_acp_card_skips_url_and_key_lines(self, script):
        assert "managed by Claude Agent SDK" in script

    def test_card_renders_permission_mode_when_acp(self, script):
        assert "acp_permission_mode" in script

   def test_card_renders_billing_model_when_acp(self, script):
        # An ACP provider's card surfaces its billing_model
        # (subscription / per_token) so the operator can tell at a
        # glance which providers meter against the budget.
        assert "p.billing_model" in script
