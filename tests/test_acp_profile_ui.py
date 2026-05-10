"""Tests for the ACP-mode UI affordances in the Agent Profiles dialog.

Covers the rls-specific additions that go on top of the base
oompah-zlz_2-ynd dialog:

* mode=acp: dim the provider dropdown + show inline note pointing at
  docs/acp-agent.md.
* mode=acp: hide the command field (Claude Agent SDK manages the
  subprocess).
* mode=acp: model-field placeholder/hint switches to "claude model name".
* mode=acp: budget-bypass warning surfaces in the dialog.
* mode=acp: card list item shows a "bypasses budget gate" warning.

See bead oompah-zlz_2-rls.
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
    matches = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    assert matches
    return "\n".join(matches)


# ----------------------------------------------------------------------
# ACP inline note + provider dimming
# ----------------------------------------------------------------------

class TestAcpProviderAffordances:
    def test_provider_acp_note_present(self, html):
        # Inline advisory text required by the issue:
        # "ACP bypasses providers — billed against the operator's claude
        #  subscription. See docs/acp-agent.md."
        assert "ACP bypasses providers" in html
        assert "claude subscription" in html
        assert "docs/acp-agent.md" in html

    def test_provider_acp_note_has_id_for_toggle(self, html):
        assert 'id="ap-provider-acp-note"' in html

    def test_provider_acp_note_hidden_by_default(self, html):
        # Default-display:none so it only surfaces when mode=acp.
        m = re.search(
            r'id="ap-provider-acp-note"[^>]*style="[^"]*display:\s*none',
            html,
        )
        assert m, "provider-acp-note must default to display:none"

    def test_acp_mode_shows_note_and_dims(self, script):
        # The change handler must show the note AND apply field-dimmed
        # styling to the provider row when isAcp.
        assert "providerNote.style.display = isAcp ? 'block' : 'none'" in script
        assert "field-dimmed" in script

    def test_command_row_hidden_for_acp(self, script):
        # The command row is wrapped in a div with id ap-command-row;
        # the change handler toggles field-hidden on it.
        assert "ap-command-row" in script
        assert "commandRow.classList.toggle('field-hidden', isAcp)" in script


# ----------------------------------------------------------------------
# ACP budget-bypass warning
# ----------------------------------------------------------------------

class TestBudgetBypassWarning:
    def test_warning_present_in_dialog(self, html):
        # Mirrors the orchestrator's startup diagnostic.
        assert "bypass the budget gate" in html

    def test_warning_has_toggle_id(self, html):
        assert 'id="ap-budget-warning"' in html

    def test_warning_hidden_by_default(self, html):
        m = re.search(
            r'id="ap-budget-warning"[^>]*style="[^"]*display:\s*none',
            html,
        )
        assert m

    def test_warning_shown_when_acp(self, script):
        assert "budgetWarn.style.display = isAcp ? 'block' : 'none'" in script

    def test_card_warning_for_acp(self, script):
        # The renderProfiles card list also surfaces the warning so an
        # operator scanning the list sees which profiles are
        # subscription-billed.
        assert "bypass the budget gate" in script
        assert "subscription-billed" in script


# ----------------------------------------------------------------------
# ACP model-field affordances
# ----------------------------------------------------------------------

class TestAcpModelField:
    def test_model_hint_id_present(self, html):
        # The hint paragraph next to the model input has an id so the
        # change handler can rewrite its text.
        assert 'id="ap-model-hint"' in html

    def test_acp_swaps_model_placeholder(self, script):
        # The handler must swap to a claude-model placeholder for ACP.
        assert "claude-sonnet-4-6" in script
        assert "claude model name" in script

    def test_acp_swaps_model_hint(self, script):
        # The hint mentions the SDK / subscription endpoint when ACP.
        assert "Claude Agent SDK passes this through" in script \
            or "Claude Agent SDK" in script


# ----------------------------------------------------------------------
# Mode dropdown still has all four options
# ----------------------------------------------------------------------

class TestModeDropdown:
    def test_mode_options(self, html):
        for v in ("auto", "api", "cli", "acp"):
            assert f'value="{v}"' in html

    def test_acp_option_label_mentions_subscription(self, html):
        # Operator clue: the ACP option in the dropdown surfaces the
        # subscription distinction.
        assert "Claude Agent SDK" in html
        assert "subscription" in html.lower()


# ----------------------------------------------------------------------
# Submit path surfaces server warnings
# ----------------------------------------------------------------------

class TestSubmitWarnings:
    def test_warnings_displayed(self, script):
        # /api/v1/agent-profiles attaches a non-fatal "warnings" array
        # to success responses (e.g. mode=acp ignores provider_id).
        # The submit handler must surface them.
        assert "data.warnings" in script
        assert "Saved with warnings" in script
