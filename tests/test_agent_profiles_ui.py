"""Tests for the Agent Profiles section in providers.html.

The UI is defined in oompah/templates/providers.html. These tests verify
the static HTML/JS structure: the section + dialog markup, the field set
defined in the issue (name/mode/provider/model_role/model/max_turns/
issue_types/keywords/min_priority/max_priority/command), CRUD wiring to
/api/v1/agent-profiles, and the mode->provider visibility behavior.

See issue: oompah-zlz_2-ynd
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
    """Concatenate every <script>…</script> block (the page has more than one)."""
    matches = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    assert matches, "No <script> block found in providers.html"
    return "\n".join(matches)


class TestSectionPresence:
    def test_section_heading(self, html):
        # The new section must say "Agent Profiles"
        assert "Agent Profiles" in html

    def test_section_has_add_button(self, html):
        assert "openProfileDialog()" in html
        assert "+ Add Profile" in html

    def test_profiles_list_container(self, html):
        assert 'id="profiles-list"' in html


class TestDialogStructure:
    def test_profile_dialog_overlay(self, html):
        assert 'id="profile-dialog"' in html

    def test_profile_dialog_title_element(self, html):
        assert 'id="profile-dialog-title"' in html

    @pytest.mark.parametrize("field_id", [
        "ap-name",
        "ap-mode",
        "ap-provider",
        "ap-model-role",
        "ap-model",
        "ap-max-turns",
        "ap-min-priority",
        "ap-max-priority",
        "ap-command",
        "ap-types-input",
        "ap-keywords-input",
    ])
    def test_dialog_fields_present(self, html, field_id):
        assert f'id="{field_id}"' in html, f"Missing dialog field id={field_id}"

    def test_mode_dropdown_options(self, html):
        # mode dropdown must include all four valid values
        for mode in ("auto", "api", "cli", "acp"):
            assert f'value="{mode}"' in html, f"Missing mode option: {mode}"

    def test_command_advanced_disclosure(self, html):
        # command lives inside <details> so it's collapsed by default
        # The <details> block should contain the ap-command input
        m = re.search(r"<details[^>]*>(.*?)</details>", html, re.DOTALL)
        assert m, "No <details> disclosure block in providers.html"
        assert 'id="ap-command"' in m.group(1), \
            "ap-command must live inside the advanced <details> disclosure"

    def test_command_default_value(self, html):
        # Default command must include 'claude --dangerously-skip-permissions'
        assert "claude --dangerously-skip-permissions" in html

    def test_priority_bounds_in_html(self, html):
        # min/max priority inputs should be 0..4 bounded
        assert re.search(r'id="ap-min-priority"[^>]*min="0"', html)
        assert re.search(r'id="ap-max-priority"[^>]*max="4"', html)

    def test_provider_label_id(self, html):
        # The provider label is dynamically updated based on mode; needs an id
        assert 'id="ap-provider-label"' in html


class TestModelRoleSuggestions:
    def test_datalist_present(self, html):
        # model_role free-text suggestions powered by a <datalist>
        assert 'id="ap-model-role-suggestions"' in html
        assert 'list="ap-model-role-suggestions"' in html

    def test_default_suggestions(self, script):
        # Default tier suggestions when no provider model_roles available
        assert "'fast'" in script and "'standard'" in script and "'deep'" in script

    def test_updates_when_provider_changes(self, script):
        assert "updateModelRoleSuggestions" in script
        assert "addEventListener('change', updateModelRoleSuggestions)" in script


class TestApiWiring:
    def test_loads_agent_profiles(self, script):
        assert "loadAgentProfiles" in script
        assert "/api/v1/agent-profiles" in script

    def test_fetches_providers_for_select(self, script):
        # Providers feed the provider select; so the page calls /api/v1/providers
        assert "/api/v1/providers" in script

    def test_create_uses_post(self, script):
        # Without an editing target, the form submits via POST
        assert re.search(r"method:\s*['\"]POST['\"]", script)
        assert "/api/v1/agent-profiles" in script

    def test_update_uses_patch(self, script):
        # When editing, the form submits via PATCH /api/v1/agent-profiles/<name>
        assert re.search(r"method:\s*['\"]PATCH['\"]", script)
        assert "encodeURIComponent(editingProfileName)" in script

    def test_delete_uses_delete(self, script):
        assert "deleteProfile" in script
        assert re.search(r"method:\s*['\"]DELETE['\"]", script)

    def test_delete_confirms(self, script):
        # Issue requires "Delete with confirm"
        assert re.search(r"confirm\([^)]*agent profile", script, re.IGNORECASE)


class TestModeBehavior:
    def test_acp_disables_provider(self, script):
        # When mode=acp, the provider select must be disabled and the
        # label must say "N/A for acp".
        assert "N/A for acp" in script
        assert "providerSelect.disabled = true" in script

    def test_other_modes_enable_provider(self, script):
        assert "providerSelect.disabled = false" in script


class TestRendering:
    def test_renders_mode_badge(self, script):
        # The card renderer prefixes a CSS class with mode-<mode>
        assert "mode-${esc(mode)}" in script or 'mode-"+esc(mode)' in script \
            or 'class="provider-type mode-' in script

    def test_resolves_provider_name(self, script):
        # The card resolves provider name via providers.find(...)
        assert "providers.find" in script
        assert "p.provider_id" in script

    def test_constraint_summary_function(self, script):
        # A helper renders the issue_types / keywords / priority summary
        assert "renderProfileConstraints" in script


class TestTagInputs:
    def test_issue_types_tag_input(self, html):
        assert 'id="ap-types-input"' in html
        assert 'id="ap-types-wrap"' in html

    def test_keywords_tag_input(self, html):
        assert 'id="ap-keywords-input"' in html
        assert 'id="ap-keywords-wrap"' in html

    def test_setup_helper(self, script):
        assert "setupProfileTagInput" in script


class TestNameUniquenessAndImmutability:
    def test_name_disabled_on_edit(self, script):
        # Editing must lock the name field — name is the unique key
        assert "nameInput.disabled = !!profile" in script
