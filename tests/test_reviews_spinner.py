"""Tests for the loading spinner on the reviews page.

The reviews page must show a visual spinner (animated SVG) while reviews
are being fetched from the backend, rather than plain text. This gives
users feedback that the backend is actively working.

See issue: oompah-h15
"""

import os
import re

import pytest


def _load_reviews_html() -> str:
    """Load reviews HTML from the templates directory."""
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "reviews.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    """Extract the main (largest) <script> block from the reviews HTML."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in reviews HTML"
    return max(matches, key=len)


def _extract_style(html: str) -> str:
    """Extract the <style> block from the reviews HTML."""
    matches = re.findall(r"<style>(.*?)</style>", html, re.DOTALL)
    assert matches, "Could not find any <style> block in reviews HTML"
    return max(matches, key=len)


@pytest.fixture(scope="module")
def html():
    return _load_reviews_html()


@pytest.fixture(scope="module")
def script(html):
    return _extract_script(html)


@pytest.fixture(scope="module")
def style(html):
    return _extract_style(html)


class TestSpinnerCSS:
    """Verify CSS rules for the spinner animation exist."""

    def test_spinner_class_has_animation(self, style):
        """A .spinner CSS rule must exist with spin animation."""
        match = re.search(r"\.spinner\s*\{([^}]+)\}", style)
        assert match, "Could not find .spinner CSS rule"
        css_block = match.group(1)
        assert "animation" in css_block
        assert "spin" in css_block

    def test_spin_keyframes_defined(self, style):
        """@keyframes spin must be defined for the rotation animation."""
        assert "@keyframes spin" in style

    def test_spin_keyframes_rotates(self, style):
        """@keyframes spin must rotate to 360deg."""
        match = re.search(r"@keyframes\s+spin\s*\{([^}]+)\}", style)
        assert match, "Could not find @keyframes spin"
        body = match.group(1)
        assert "rotate" in body

    def test_loading_class_uses_flexbox(self, style):
        """The .loading class should use flexbox for centering spinner and text."""
        match = re.search(r"\.loading\s*\{([^}]+)\}", style)
        assert match, "Could not find .loading CSS rule"
        css_block = match.group(1)
        assert "display" in css_block
        assert "flex" in css_block

    def test_loading_class_has_gap(self, style):
        """The .loading class should have a gap for spacing between spinner and text."""
        match = re.search(r"\.loading\s*\{([^}]+)\}", style)
        assert match, "Could not find .loading CSS rule"
        css_block = match.group(1)
        assert "gap" in css_block


class TestSpinnerInInitialHTML:
    """Verify the initial page HTML includes the spinner."""

    def test_initial_loading_contains_svg_spinner(self, html):
        """The initial reviews-container must include an SVG spinner element."""
        # Find the reviews-container initial content
        match = re.search(
            r'id="reviews-container">(.*?)</div>',
            html,
            re.DOTALL,
        )
        assert match, "Could not find reviews-container initial content"
        content = match.group(1)
        assert "<svg" in content, "Initial loading must include an SVG spinner"
        assert "spinner" in content, "SVG must have the spinner class"

    def test_initial_loading_has_role_status(self, html):
        """The initial loading div must have role='status' for accessibility."""
        match = re.search(
            r'id="reviews-container">(.*?)</div>',
            html,
            re.DOTALL,
        )
        assert match
        content = match.group(1)
        assert 'role="status"' in content

    def test_initial_loading_has_aria_label(self, html):
        """The initial loading div must have an aria-label for screen readers."""
        match = re.search(
            r'id="reviews-container">(.*?)</div>',
            html,
            re.DOTALL,
        )
        assert match
        content = match.group(1)
        assert "aria-label" in content

    def test_initial_spinner_svg_is_aria_hidden(self, html):
        """The spinner SVG should be aria-hidden since the text provides meaning."""
        match = re.search(
            r'id="reviews-container">(.*?)</div>',
            html,
            re.DOTALL,
        )
        assert match
        content = match.group(1)
        assert 'aria-hidden="true"' in content


class TestSpinnerInJavaScript:
    """Verify the loadReviews() function uses the spinner in its loading state."""

    def test_load_reviews_sets_spinner_html(self, script):
        """loadReviews() must set innerHTML with a spinner SVG while loading."""
        # The function sets container.innerHTML to a loading state with spinner
        assert "spinner" in script, "loadReviews must reference spinner class"
        # Check that the spinner SVG appears in the innerHTML assignment
        assert "<svg" in script, "loadReviews must include an SVG element in loading HTML"

    def test_load_reviews_loading_has_role_status(self, script):
        """The loading HTML in loadReviews must have role='status'."""
        assert 'role="status"' in script

    def test_load_reviews_loading_has_aria_label(self, script):
        """The loading HTML in loadReviews must have an aria-label."""
        assert "aria-label" in script

    def test_spinner_svg_has_circle(self, script):
        """The spinner SVG must use a circle element (matching dashboard pattern)."""
        assert "<circle" in script

    def test_spinner_svg_is_aria_hidden(self, script):
        """The spinner SVG must be aria-hidden (decorative, text provides meaning)."""
        # The SVG is decorative — the text "Loading reviews…" conveys meaning
        assert 'aria-hidden=\\"true\\"' in script or "aria-hidden" in script
