"""Tests for the provider-whitelist UI added to projects.html (TASK-407.11).

The /projects-manage page now exposes a provider_whitelist control so
operators can configure project-level provider restrictions without
curl. These tests verify the static HTML/JS structure using the same
source-inspection approach as test_projects_template_fetch_errors.py.

Coverage:
  - Provider Whitelist row is displayed in project cards.
  - "All providers" label is shown when the whitelist is empty.
  - Edit form contains a checkbox group for provider names.
  - saveProject() reads selected provider names from the checkbox group.
  - PATCH body includes provider_whitelist (even when empty → []).
  - Unknown whitelist names are preserved in renderProviderWhitelistCheckboxes().
  - loadProviders() is defined and handles errors gracefully.
  - loadProviders() is called before loadProjects() in the page-load sequence.
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers (mirrors test_projects_template_fetch_errors.py)
# ---------------------------------------------------------------------------


def _load_projects_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "projects.html",
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_main_script(html: str) -> str:
    """Return the largest <script> block — that's the page logic."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in projects.html"
    return max(matches, key=len)


def _get_func_body(script: str, fn_name: str) -> str:
    """Extract a top-level function body via balanced-brace scan.

    Supports both ``function foo()`` and ``async function foo()`` declarations.
    """
    pattern = re.compile(
        rf"(?:async\s+)?function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{"
    )
    m = pattern.search(script)
    assert m, f"Could not find function {fn_name} in script"
    start = m.end() - 1
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
    return _load_projects_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_main_script(html)


# ---------------------------------------------------------------------------
# Provider Whitelist display in project card
# ---------------------------------------------------------------------------


class TestProviderWhitelistCardDisplay:
    """The project card must show the provider_whitelist value, or a friendly
    'All providers' label when the whitelist is empty."""

    def test_whitelist_field_row_present_in_card(self, script: str) -> None:
        """project card HTML includes a 'Whitelist:' field-row."""
        # The label text in the display row
        assert "Whitelist:" in script, (
            "The project card must include a 'Whitelist:' field-row "
            "showing the current provider_whitelist value."
        )

    def test_whitelist_field_row_has_data_attribute(self, html: str) -> None:
        """Field row carries data-field='provider-whitelist' for test targeting."""
        assert 'data-field="provider-whitelist"' in html, (
            "Provider whitelist field-row must carry data-field='provider-whitelist' "
            "so tests and future automation can reliably locate it."
        )

    def test_all_providers_shown_for_empty_whitelist(self, script: str) -> None:
        """When provider_whitelist is empty, display 'All providers'."""
        # The template conditional renders "All providers" when whitelist is falsy/empty
        assert "All providers" in script, (
            "When provider_whitelist is empty, the card must display "
            "'All providers' to make the permissive default self-documenting."
        )

    def test_whitelist_reads_provider_whitelist_field(self, script: str) -> None:
        """Display uses p.provider_whitelist to check if empty."""
        assert "p.provider_whitelist" in script, (
            "Card display must read p.provider_whitelist from the project data."
        )

    def test_whitelist_joins_names_for_display(self, script: str) -> None:
        """Non-empty whitelist is rendered as comma-separated names."""
        assert "provider_whitelist.join" in script, (
            "Non-empty provider_whitelist must be rendered with .join() "
            "to produce a readable comma-separated list."
        )


# ---------------------------------------------------------------------------
# Provider Whitelist edit form control
# ---------------------------------------------------------------------------


class TestProviderWhitelistEditControl:
    """The edit form must include a checkbox-based multi-select control
    for provider_whitelist."""

    def test_edit_form_has_whitelist_group(self, html: str) -> None:
        """Edit form contains a provider-whitelist checkbox group container."""
        assert 'data-field="provider-whitelist-edit"' in html, (
            "Edit form must include a form-group with "
            "data-field='provider-whitelist-edit' for test targeting."
        )

    def test_edit_form_whitelist_group_has_role(self, html: str) -> None:
        """Whitelist checkbox container carries role='group' for accessibility."""
        assert 'role="group"' in html, (
            "Provider whitelist checkbox container must carry role='group' "
            "so screen readers treat it as a grouped control."
        )

    def test_edit_form_whitelist_label_exists(self, html: str) -> None:
        """Edit form has a label for the Provider Whitelist field."""
        assert "Provider Whitelist" in html, (
            "Edit form must label the provider_whitelist control 'Provider Whitelist'."
        )

    def test_checkbox_name_includes_project_id(self, script: str) -> None:
        """Checkboxes use a name that includes the project ID for disambiguation."""
        assert "edit-provider-whitelist-cb-" in script, (
            "Provider whitelist checkboxes must use name 'edit-provider-whitelist-cb-<id>' "
            "so saveProject() can locate the right group per project."
        )

    def test_renderProviderWhitelistCheckboxes_defined(self, script: str) -> None:
        """renderProviderWhitelistCheckboxes helper function is defined."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        assert body, "renderProviderWhitelistCheckboxes must be defined"

    def test_checkboxes_use_provider_name_as_value(self, script: str) -> None:
        """Checkbox values are provider names (not IDs) — dispatch filters by name."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        # The value attribute is set from the provider name
        assert 'value="' in body or "value=" in body, (
            "renderProviderWhitelistCheckboxes must set a value on each checkbox."
        )
        assert "opt.name" in body, (
            "Checkbox value must come from opt.name (provider name, not ID) "
            "because dispatch filtering matches provider names."
        )

    def test_checkboxes_pre_checked_from_whitelist(self, script: str) -> None:
        """Checkboxes are pre-checked based on current project whitelist."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        assert "checked" in body and ("wl.includes" in body or "whitelist.includes" in body or "wl.indexOf" in body or ".includes(" in body), (
            "Checkboxes must be pre-checked when their name appears in the "
            "current provider_whitelist."
        )

    def test_empty_providers_message_is_handled(self, script: str) -> None:
        """When no providers exist, a helpful message is shown instead of empty list."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        assert "No providers" in body or "no providers" in body, (
            "renderProviderWhitelistCheckboxes must surface a helpful message "
            "when no providers are configured."
        )

    def test_checkboxes_have_aria_labels(self, script: str) -> None:
        """Each checkbox carries an aria-label for screen reader accessibility."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        assert "aria-label=" in body, (
            "Each provider whitelist checkbox must carry aria-label so screen "
            "readers identify which provider the checkbox controls."
        )


# ---------------------------------------------------------------------------
# Unknown whitelist name preservation
# ---------------------------------------------------------------------------


class TestUnknownWhitelistNamePreservation:
    """Names in provider_whitelist that are not in the current provider store
    must be shown as checked checkboxes so they are not silently dropped."""

    def test_unknown_names_collected(self, script: str) -> None:
        """renderProviderWhitelistCheckboxes detects names not in provider store."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        # The function uses a Set of known names to find unknown entries
        assert "knownNames" in body or "known" in body, (
            "renderProviderWhitelistCheckboxes must build a set of known "
            "provider names to detect unknown whitelist entries."
        )
        assert "unknown" in body.lower(), (
            "The function must handle the 'unknown' provider case."
        )

    def test_unknown_names_appended_to_options(self, script: str) -> None:
        """Unknown whitelist names are appended to the option list."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        assert "unknownInWhitelist" in body or "unknown" in body, (
            "Unknown whitelist names must be appended to the options list "
            "so they appear in the edit form as checked checkboxes."
        )

    def test_unknown_names_shown_with_note(self, script: str) -> None:
        """Unknown entries are labelled to distinguish them from live providers."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        assert "not currently configured" in body or "stored" in body, (
            "Unknown whitelist entries must be annotated so the operator "
            "understands they are not currently in the provider store."
        )

    def test_unknown_names_pre_checked(self, script: str) -> None:
        """Unknown entries are pre-checked (they were in the stored whitelist)."""
        body = _get_func_body(script, "renderProviderWhitelistCheckboxes")
        # The checked logic applies to all entries, including unknown ones —
        # they must be in wl (the whitelist), so they will be checked.
        assert "wl.includes" in body or ".includes(opt.name)" in body or ".includes(name)" in body, (
            "renderProviderWhitelistCheckboxes must check each option name "
            "against the stored whitelist, including unknown entries."
        )


# ---------------------------------------------------------------------------
# saveProject() — provider_whitelist in PATCH body
# ---------------------------------------------------------------------------


class TestSaveProjectWhitelistPayload:
    """saveProject() must collect checked checkboxes and include
    provider_whitelist in the PATCH body."""

    def test_saveProject_reads_checked_checkboxes(self, script: str) -> None:
        """saveProject() queries checked provider_whitelist checkboxes."""
        body = _get_func_body(script, "saveProject")
        assert "edit-provider-whitelist-cb-" in body, (
            "saveProject must querySelectorAll the provider whitelist checkboxes "
            "using their name prefix 'edit-provider-whitelist-cb-<id>'."
        )
        assert ":checked" in body, (
            "saveProject must select only :checked checkboxes to build the whitelist."
        )

    def test_saveProject_maps_checkboxes_to_values(self, script: str) -> None:
        """saveProject() maps checkbox elements to their .value (provider name)."""
        body = _get_func_body(script, "saveProject")
        assert "providerWhitelist" in body, (
            "saveProject must collect the provider whitelist into a variable."
        )
        assert ".value" in body or "cb.value" in body, (
            "saveProject must map checked checkboxes to .value to get provider names."
        )

    def test_saveProject_includes_provider_whitelist_in_body(self, script: str) -> None:
        """PATCH body includes provider_whitelist field."""
        body = _get_func_body(script, "saveProject")
        assert "provider_whitelist" in body, (
            "saveProject must include provider_whitelist in the PATCH request body."
        )

    def test_saveProject_empty_selection_sends_empty_list(self, script: str) -> None:
        """Empty checkbox selection produces [] (not undefined/null) in the body.

        Sending [] tells the server to clear the whitelist (allow all providers),
        which is distinct from omitting the field entirely.
        """
        body = _get_func_body(script, "saveProject")
        # The value comes from Array.from(NodeList).map(...); when nothing is
        # checked, NodeList is empty and the resulting array is [].
        assert "Array.from" in body or "Array.from(" in body or "providerWhitelistCbs" in body, (
            "saveProject must use Array.from() on the NodeList of checked checkboxes "
            "so an empty selection produces [] rather than undefined."
        )


# ---------------------------------------------------------------------------
# loadProviders() — fetch and caching
# ---------------------------------------------------------------------------


class TestLoadProviders:
    """loadProviders() fetches from /api/v1/providers and caches in _providers."""

    def test_loadProviders_defined(self, script: str) -> None:
        body = _get_func_body(script, "loadProviders")
        assert body, "loadProviders must be defined in projects.html"

    def test_loadProviders_fetches_providers_endpoint(self, script: str) -> None:
        body = _get_func_body(script, "loadProviders")
        assert "/api/v1/providers" in body, (
            "loadProviders must fetch from /api/v1/providers."
        )

    def test_loadProviders_has_try_catch(self, script: str) -> None:
        body = _get_func_body(script, "loadProviders")
        assert "try" in body and "catch" in body, (
            "loadProviders must wrap its fetch in try/catch so a provider "
            "API failure does not become an unhandled rejection."
        )

    def test_loadProviders_logs_on_error(self, script: str) -> None:
        body = _get_func_body(script, "loadProviders")
        assert "console.error" in body, (
            "loadProviders must log errors to console.error for developer visibility."
        )

    def test_loadProviders_checks_response_ok(self, script: str) -> None:
        body = _get_func_body(script, "loadProviders")
        assert "res.ok" in body, (
            "loadProviders must check res.ok and not attempt to parse non-OK responses."
        )

    def test_providers_module_level_variable_declared(self, script: str) -> None:
        """_providers module-level variable is declared."""
        assert "let _providers" in script or "var _providers" in script, (
            "A module-level _providers variable must be declared to cache the "
            "fetched provider list for use by renderProviderWhitelistCheckboxes."
        )

    def test_loadProviders_stores_into_module_variable(self, script: str) -> None:
        body = _get_func_body(script, "loadProviders")
        assert "_providers" in body, (
            "loadProviders must store the fetched providers into the _providers "
            "module-level variable."
        )


# ---------------------------------------------------------------------------
# Page-load sequence — providers loaded before projects
# ---------------------------------------------------------------------------


class TestPageLoadSequence:
    """loadProviders() must be called before loadProjects() so that
    renderProviderWhitelistCheckboxes() has a populated _providers list."""

    def test_loadProviders_called_before_loadProjects(self, script: str) -> None:
        """Page-load calls loadProviders() then loadProjects() (not in reverse)."""
        # The bottom of the script should have loadProviders().then(... loadProjects ...)
        # rather than standalone loadProjects() followed by loadProviders().
        pos_chain = script.rfind("loadProviders()")
        pos_load = script.rfind("loadProjects()")
        assert pos_chain != -1, "loadProviders() must be called at page load"
        assert pos_load != -1, "loadProjects() must be called at page load"
        # loadProviders() invocation at page load is before loadProjects() invocation
        # (or they are in a .then() chain where loadProviders comes first)
        assert pos_chain < pos_load, (
            "loadProviders() must appear before loadProjects() in the page-load "
            "sequence so _providers is populated when project cards are rendered."
        )

    def test_then_chain_connects_load_providers_to_load_projects(self, script: str) -> None:
        """loadProviders().then(…) chain leads to loadProjects()."""
        assert re.search(r"loadProviders\(\)\.then\(", script), (
            "Page-load must chain loadProviders().then(...) → loadProjects() "
            "to guarantee providers are available before project cards render."
        )

    def test_add_project_form_documents_whitelist_omission(self, html: str) -> None:
        """Add Project form includes a comment explaining why whitelist is omitted."""
        # The HTML comment in the add-form explains the design decision
        assert "provider_whitelist" in html, (
            "The Add Project form (or nearby HTML comment) must mention "
            "provider_whitelist to document why it is not included."
        )
        # Specifically, check that the comment about edit-after-create is present
        assert "edit-after-create" in html or "edit after" in html.lower() or "after creation" in html, (
            "The HTML should document that edit-after-create is the supported "
            "workflow for setting whitelist on new projects."
        )
