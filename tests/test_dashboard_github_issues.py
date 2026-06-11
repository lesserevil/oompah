"""Tests for GitHub issues display in the dashboard board and detail views.

Covers:
- Card-level GitHub URL tracker link (AC #1: GitHub issue cards link to URL).
- Card-level legacy Backlog task badge (AC #2: legacy tasks visually distinct).
- Detail panel GitHub issue URL field.
- Detail panel tracker kind / owner / repo field.
- Detail panel legacy marker.
- CSS classes for the new visual elements.
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _load_dashboard() -> str:
    path = Path(__file__).resolve().parents[1] / "oompah" / "templates" / "dashboard.html"
    return path.read_text(encoding="utf-8")


def _extract_script(html: str) -> str:
    """Return the content of the largest <script> block."""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "No <script> blocks found in dashboard.html"
    return max(scripts, key=len)


def _extract_func_body(script: str, fn_name: str) -> str:
    """Return the body of a named function (text between outermost braces)."""
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\([^)]*\)\s*\{{")
    match = pattern.search(script)
    assert match, f"Could not find function {fn_name}"
    start = match.end() - 1
    depth = 0
    for idx in range(start, len(script)):
        c = script[idx]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : idx]
    raise AssertionError(f"Could not find end of function {fn_name}")


# ---------------------------------------------------------------------------
# CSS classes
# ---------------------------------------------------------------------------

class TestCSSClasses:
    def test_legacy_badge_css_exists(self):
        html = _load_dashboard()
        assert ".legacy-badge {" in html or ".legacy-badge{" in html

    def test_tracker_link_css_exists(self):
        html = _load_dashboard()
        assert ".tracker-link {" in html or ".tracker-link{" in html

    def test_card_identifier_link_css_exists(self):
        html = _load_dashboard()
        assert ".card-identifier-link {" in html or ".card-identifier-link{" in html

    def test_detail_github_link_css_exists(self):
        html = _load_dashboard()
        assert ".detail-github-link {" in html or ".detail-github-link{" in html


# ---------------------------------------------------------------------------
# createCard: GitHub URL tracker link
# ---------------------------------------------------------------------------

class TestCreateCardTrackerLink:
    def test_tracker_link_variable_built_from_issue_url(self):
        """createCard builds trackerLinkHtml from issue.url."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "trackerLinkHtml" in body
        assert "issue.url" in body

    def test_tracker_link_opens_external_url(self):
        """Tracker link uses target=_blank and rel=noopener."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert 'target="_blank"' in body
        assert 'rel="noopener noreferrer"' in body

    def test_tracker_link_uses_css_class(self):
        """Tracker link element uses the tracker-link CSS class."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert 'class="tracker-link"' in body

    def test_tracker_link_stops_propagation(self):
        """Tracker link onclick stops propagation so the card is not also clicked."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "event.stopPropagation()" in body

    def test_tracker_link_included_in_card_innerHTML(self):
        """trackerLinkHtml is interpolated into the card HTML."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "${trackerLinkHtml}" in body

    def test_github_card_identifier_is_external_link(self):
        """GitHub-backed cards make the visible identifier itself a link."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "cardIdentifierHtml" in body
        assert 'class="card-identifier card-identifier-link"' in body
        assert 'href="${esc(issue.url)}"' in body
        assert 'target="_blank"' in body
        assert 'rel="noopener noreferrer"' in body
        assert "${cardIdentifierHtml}${trackerLinkHtml}" in body

    def test_non_github_card_identifier_keeps_detail_click(self):
        """Cards without issue.url keep the old detail-panel identifier click."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "if (identifierEl && !issue.url)" in body
        assert "openDetailPanel(issue.identifier);" in body


# ---------------------------------------------------------------------------
# createCard: legacy Backlog badge
# ---------------------------------------------------------------------------

class TestCreateCardLegacyBadge:
    def test_legacy_badge_variable_built_from_is_legacy(self):
        """createCard builds legacyBadgeHtml from issue.is_legacy."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "legacyBadgeHtml" in body
        assert "issue.is_legacy" in body

    def test_legacy_badge_uses_css_class(self):
        """Legacy badge element uses the legacy-badge CSS class."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert 'class="legacy-badge"' in body

    def test_legacy_badge_included_in_card_innerHTML(self):
        """legacyBadgeHtml is interpolated into the card HTML."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert "${legacyBadgeHtml}" in body

    def test_legacy_badge_has_aria_label(self):
        """Legacy badge has an aria-label for accessibility."""
        script = _extract_script(_load_dashboard())
        body = _extract_func_body(script, "createCard")
        assert 'aria-label="Legacy Backlog task"' in body


# ---------------------------------------------------------------------------
# openDetailPanel: GitHub URL, tracker kind, legacy marker
# ---------------------------------------------------------------------------

class TestDetailPanelGitHubFields:
    def test_detail_panel_renders_github_url_when_set(self):
        """Detail panel script section shows GitHub URL link when detail.url is set."""
        script = _extract_script(_load_dashboard())
        assert "detail.url" in script
        assert 'class="detail-github-link"' in script

    def test_detail_panel_github_url_link_opens_externally(self):
        """The GitHub URL link uses target=_blank and rel=noopener."""
        script = _extract_script(_load_dashboard())
        # The detail-github-link pattern must coexist with target/_blank
        assert 'class="detail-github-link"' in script
        # Verify the anchor tag near the detail-github-link has the right attrs
        idx = script.index('class="detail-github-link"')
        surrounding = script[max(0, idx - 200) : idx + 200]
        assert 'target="_blank"' in surrounding
        assert 'rel="noopener noreferrer"' in surrounding

    def test_detail_panel_renders_tracker_kind_section(self):
        """Detail panel renders a Tracker field when detail.tracker_kind is set."""
        script = _extract_script(_load_dashboard())
        assert "detail.tracker_kind" in script
        assert "Tracker" in script

    def test_detail_panel_tracker_kind_includes_owner_repo(self):
        """Detail panel shows tracker_owner/tracker_repo when available."""
        script = _extract_script(_load_dashboard())
        assert "detail.tracker_owner" in script
        assert "detail.tracker_repo" in script

    def test_detail_panel_renders_legacy_marker(self):
        """Detail panel shows a legacy marker note when detail.is_legacy is set."""
        script = _extract_script(_load_dashboard())
        assert "detail.is_legacy" in script
        assert "Legacy Backlog.md task" in script

    def test_detail_panel_legacy_marker_uses_legacy_badge_class(self):
        """The legacy note in the detail panel uses the legacy-badge CSS class."""
        script = _extract_script(_load_dashboard())
        idx = script.index("Legacy Backlog.md task")
        surrounding = script[max(0, idx - 200) : idx + 200]
        assert 'class="legacy-badge"' in surrounding

    def test_detail_panel_github_issue_label(self):
        """Detail panel uses the label 'GitHub Issue' for the URL field."""
        script = _extract_script(_load_dashboard())
        assert "GitHub Issue" in script
