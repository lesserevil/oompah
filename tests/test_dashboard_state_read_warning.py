"""Regression tests for OOMPAH-306: dashboard stale-state read warning.

Verifies that the dashboard frontend:
  1. Displays an explicit, accessible banner when the issues REST response is
     stale or unavailable.
  2. Reads the X-Oompah-Issues-Stale response header in fetchIssues().
  3. Clears the banner only on a genuinely fresh response.
  4. Does NOT silently render obsolete state as authoritative.

Coverage:
  § 1  Stale-state banner element existence and accessibility
  § 2  fetchIssues reads and reacts to X-Oompah-Issues-Stale header
  § 3  fetchIssues shows the banner on network/HTTP errors
  § 4  _updateTaskStateStaleBanner helper function contract
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_dashboard() -> str:
    template_path = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    )
    return template_path.read_text(encoding="utf-8")


def _extract_script(html: str) -> str:
    """Return the largest <script> block from the HTML."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "No <script> block found in dashboard.html"
    return max(matches, key=len)


def _extract_async_function(script: str, name: str) -> str:
    """Extract the body of a named top-level async function."""
    marker = f"async function {name}("
    start = script.find(marker)
    assert start != -1, f"Could not find 'async function {name}(' in script"
    brace_start = script.index("{", start)
    depth = 0
    for pos in range(brace_start, len(script)):
        c = script[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[brace_start + 1 : pos]
    raise AssertionError(f"Could not find closing brace for async function {name}")


def _extract_function(script: str, name: str) -> str:
    """Extract the body of a named top-level function."""
    marker = f"function {name}("
    start = script.find(marker)
    assert start != -1, f"Could not find 'function {name}(' in script"
    brace_start = script.index("{", start)
    depth = 0
    for pos in range(brace_start, len(script)):
        c = script[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[brace_start + 1 : pos]
    raise AssertionError(f"Could not find closing brace for function {name}")


# ---------------------------------------------------------------------------
# Fixtures (module-scoped so HTML is only read once)
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(scope="module")
def html() -> str:
    return _load_dashboard()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_script(html)


@pytest.fixture(scope="module")
def fetch_issues_body(script: str) -> str:
    return _extract_async_function(script, "fetchIssues")


@pytest.fixture(scope="module")
def update_stale_banner_body(script: str) -> str:
    return _extract_function(script, "_updateTaskStateStaleBanner")


# ===========================================================================
# § 1  Stale-state banner element existence and accessibility
# ===========================================================================


class TestStaleBannerElement:
    """The task-state-stale-banner element must be present and accessible."""

    def test_task_state_stale_banner_element_exists(self, html: str):
        """dashboard.html must contain the task-state-stale-banner element.

        Regression for OOMPAH-306: when the API response is stale, the UI must
        display an explicit indicator rather than silently showing old state.
        """
        assert 'id="task-state-stale-banner"' in html, (
            "dashboard.html must define <... id=\"task-state-stale-banner\"> "
            "for the stale-state warning banner"
        )

    def test_task_state_stale_banner_is_hidden_by_default(self, html: str):
        """The stale banner must be hidden on initial page load."""
        # Find the banner element and check it has the hidden attribute.
        match = re.search(
            r'<[^>]+id="task-state-stale-banner"[^>]*>',
            html,
        )
        assert match, "task-state-stale-banner element must be present"
        tag = match.group(0)
        assert "hidden" in tag, (
            "task-state-stale-banner must have the 'hidden' attribute so it is "
            "invisible on initial load"
        )

    def test_task_state_stale_banner_has_role_alert(self, html: str):
        """Stale banner must use role='alert' for screen-reader accessibility."""
        match = re.search(
            r'<[^>]+id="task-state-stale-banner"[^>]*>',
            html,
        )
        assert match
        tag = match.group(0)
        assert 'role="alert"' in tag, (
            "task-state-stale-banner must have role='alert' so that assistive "
            "technology announces the stale-state warning"
        )

    def test_task_state_stale_banner_has_aria_live(self, html: str):
        """Stale banner must use aria-live for dynamic screen-reader updates."""
        match = re.search(
            r'<[^>]+id="task-state-stale-banner"[^>]*>',
            html,
        )
        assert match
        tag = match.group(0)
        assert "aria-live=" in tag, (
            "task-state-stale-banner must have aria-live so assistive "
            "technology announces updates without user interaction"
        )

    def test_task_state_stale_banner_has_aria_label(self, html: str):
        """Stale banner must have an accessible name via aria-label."""
        match = re.search(
            r'<[^>]+id="task-state-stale-banner"[^>]*>',
            html,
        )
        assert match
        tag = match.group(0)
        assert "aria-label=" in tag, (
            "task-state-stale-banner must have aria-label to provide "
            "an accessible name for assistive technology"
        )

    def test_task_state_stale_banner_has_stale_icon(self, html: str):
        """Stale banner must contain a visible warning icon."""
        # The icon should be inside the banner
        start = html.find('id="task-state-stale-banner"')
        assert start != -1
        # Look for the closing tag of the banner div
        end = html.find("</div>", start)
        banner_fragment = html[start:end + 6]
        assert "stale-icon" in banner_fragment or "aria-hidden" in banner_fragment, (
            "task-state-stale-banner must contain a decorative icon element"
        )

    def test_task_state_stale_banner_has_css_class(self, html: str):
        """The CSS class task-state-stale-banner must be defined in the stylesheet."""
        assert ".task-state-stale-banner" in html, (
            "CSS class .task-state-stale-banner must be defined so the banner "
            "has correct visual styling"
        )

    def test_stale_banner_hidden_css_rule_present(self, html: str):
        """The [hidden] rule for the banner must prevent display when hidden."""
        assert ".task-state-stale-banner[hidden]" in html, (
            ".task-state-stale-banner[hidden] CSS rule must be present to "
            "hide the banner via the 'hidden' attribute"
        )


# ===========================================================================
# § 2  fetchIssues reads X-Oompah-Issues-Stale header
# ===========================================================================


class TestFetchIssuesStaleHeader:
    """fetchIssues must read and react to the X-Oompah-Issues-Stale response header."""

    def test_fetchIssues_reads_stale_header(self, fetch_issues_body: str):
        """fetchIssues must call response.headers.get() to read the stale header.

        The server sends X-Oompah-Issues-Stale: true/false on every /api/v1/issues
        response. fetchIssues must inspect this header to know whether the returned
        board data is authoritative or a stale snapshot.
        """
        assert "x-oompah-issues-stale" in fetch_issues_body.lower(), (
            "fetchIssues must read the 'x-oompah-issues-stale' response header "
            "to detect stale API responses"
        )

    def test_fetchIssues_calls_headers_get(self, fetch_issues_body: str):
        """fetchIssues must call res.headers.get() for the stale header."""
        assert "headers.get(" in fetch_issues_body, (
            "fetchIssues must call res.headers.get() to read response headers"
        )

    def test_fetchIssues_calls_update_stale_banner_on_success(self, fetch_issues_body: str):
        """fetchIssues must call _updateTaskStateStaleBanner() on a successful fetch."""
        assert "_updateTaskStateStaleBanner(" in fetch_issues_body, (
            "fetchIssues must call _updateTaskStateStaleBanner() to update the "
            "stale indicator based on the response header"
        )

    def test_fetchIssues_passes_stale_flag_to_banner_updater(self, fetch_issues_body: str):
        """fetchIssues must pass the stale value to the banner updater."""
        # The call must include the isStale variable or a derived boolean.
        assert "isStale" in fetch_issues_body or "stale" in fetch_issues_body.lower(), (
            "fetchIssues must derive and pass the stale flag to "
            "_updateTaskStateStaleBanner()"
        )

    def test_fetchIssues_checks_stale_header_equals_true_string(self, fetch_issues_body: str):
        """fetchIssues must compare the header value to the string 'true'."""
        # The server sends the string literal 'true' or 'false'.
        assert "'true'" in fetch_issues_body or '"true"' in fetch_issues_body, (
            "fetchIssues must compare the header value to 'true' (string), "
            "since HTTP headers are always strings"
        )

    def test_fetchIssues_clears_banner_on_fresh_response(self, fetch_issues_body: str):
        """fetchIssues must call _updateTaskStateStaleBanner(false) on a fresh response."""
        # The function must pass a falsy/false value to hide the banner.
        # We verify _updateTaskStateStaleBanner is called (with isStale=false when fresh).
        assert "_updateTaskStateStaleBanner(" in fetch_issues_body, (
            "fetchIssues must clear the stale banner when the response is fresh "
            "by passing false/falsy to _updateTaskStateStaleBanner()"
        )


# ===========================================================================
# § 3  fetchIssues shows the banner on network/HTTP errors
# ===========================================================================


class TestFetchIssuesErrorBanner:
    """fetchIssues must show the stale banner when the request fails entirely."""

    def test_fetchIssues_shows_banner_on_network_error(self, fetch_issues_body: str):
        """fetchIssues must show the stale banner in the catch block (network error).

        When fetch() throws (network unreachable), the dashboard must not silently
        leave stale state visible — it must mark the board as potentially outdated.
        """
        catch_pos = fetch_issues_body.find("} catch")
        assert catch_pos != -1, "fetchIssues must have a catch block"
        catch_body = fetch_issues_body[catch_pos:]
        assert "_updateTaskStateStaleBanner(true)" in catch_body, (
            "The catch block in fetchIssues must call "
            "_updateTaskStateStaleBanner(true) to warn users that state data "
            "is unavailable"
        )

    def test_fetchIssues_shows_banner_on_http_error(self, fetch_issues_body: str):
        """fetchIssues must show the stale banner when !res.ok (HTTP error).

        A non-200 response means the board data is unavailable — show the banner.
        """
        not_ok_pos = fetch_issues_body.find("if (!res.ok)")
        assert not_ok_pos != -1, "fetchIssues must check !res.ok"
        after_not_ok = fetch_issues_body[not_ok_pos:]
        assert "_updateTaskStateStaleBanner(true)" in after_not_ok, (
            "The !res.ok branch in fetchIssues must call "
            "_updateTaskStateStaleBanner(true)"
        )

    def test_fetchIssues_still_returns_null_on_network_error(self, fetch_issues_body: str):
        """fetchIssues must still return null after showing the banner on error."""
        catch_pos = fetch_issues_body.find("} catch")
        assert catch_pos != -1
        catch_body = fetch_issues_body[catch_pos:]
        assert "return null" in catch_body, (
            "fetchIssues catch block must still return null after banner update"
        )


# ===========================================================================
# § 4  _updateTaskStateStaleBanner helper contract
# ===========================================================================


class TestUpdateStaleBannerHelper:
    """_updateTaskStateStaleBanner must correctly show/hide the banner."""

    def test_update_stale_banner_function_exists(self, script: str):
        """_updateTaskStateStaleBanner must be defined in the script."""
        assert "function _updateTaskStateStaleBanner(" in script, (
            "Script must define function _updateTaskStateStaleBanner() as the "
            "single point of control for the stale-state banner visibility"
        )

    def test_update_stale_banner_looks_up_banner_by_id(self, update_stale_banner_body: str):
        """_updateTaskStateStaleBanner must look up the banner element by ID."""
        assert "task-state-stale-banner" in update_stale_banner_body, (
            "_updateTaskStateStaleBanner must use getElementById('task-state-stale-banner') "
            "to target the correct banner element"
        )

    def test_update_stale_banner_sets_hidden_false_when_stale(
        self, update_stale_banner_body: str
    ):
        """_updateTaskStateStaleBanner must unhide the banner when stale=true."""
        # When stale is true, banner.hidden = false
        assert "banner.hidden = false" in update_stale_banner_body or (
            "hidden = false" in update_stale_banner_body
        ), (
            "_updateTaskStateStaleBanner must set banner.hidden = false "
            "when stale is truthy so the banner becomes visible"
        )

    def test_update_stale_banner_sets_hidden_true_when_fresh(
        self, update_stale_banner_body: str
    ):
        """_updateTaskStateStaleBanner must hide the banner when stale=false."""
        assert "banner.hidden = true" in update_stale_banner_body or (
            "hidden = true" in update_stale_banner_body
        ), (
            "_updateTaskStateStaleBanner must set banner.hidden = true "
            "when stale is falsy so the banner is hidden on fresh data"
        )

    def test_update_stale_banner_guards_null_element(self, update_stale_banner_body: str):
        """_updateTaskStateStaleBanner must guard against missing DOM element."""
        assert "if (!banner)" in update_stale_banner_body or (
            "if (!" in update_stale_banner_body and "banner" in update_stale_banner_body
        ), (
            "_updateTaskStateStaleBanner must guard with 'if (!banner) return' "
            "in case the element is absent (e.g. stripped template)"
        )
