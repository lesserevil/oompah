"""Tests for the YOLO 'Auto-resolving…' indicator in reviews.html.

Covers oompah-zlz_2-zvf2: on YOLO-enabled projects the manual
"Resolve Conflicts" button is redundant — the orchestrator's
``_yolo_notify_conflict`` path already tries ``provider.rebase_review``
then falls back to notifying the bead on the next full-sync tick. The
button is replaced with a passive ``<span class="conflict-badge
auto-resolving">Auto-resolving…</span>`` indicator (no click target).

Non-YOLO projects keep today's button so the operator still has the
manual lever.

These tests assert static template structure since pytest can't run JS;
behavioural coverage of the JS branch is provided by inspecting the
exact pattern that selects between button and span.
"""

from __future__ import annotations

import os
import re

import pytest


def _load_reviews_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "reviews.html"
    )
    with open(template_path, "r") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def html() -> str:
    return _load_reviews_html()


class TestAutoResolvingCSS:
    """A dedicated `.conflict-badge.auto-resolving` style must exist so
    the YOLO indicator is visually distinct from the red conflict badge
    (it's communicating 'work in progress', not 'human action required').
    """

    def test_class_defined(self, html: str):
        # CSS selector — accept either ".conflict-badge.auto-resolving"
        # or a standalone ".auto-resolving" rule, both are acceptable.
        assert (".conflict-badge.auto-resolving" in html
                or ".auto-resolving" in html), \
            "missing CSS rule for the Auto-resolving indicator"


class TestRenderReviewCardSignature:
    """``renderReviewCard()`` must accept the project_yolo flag so its
    callers can pass per-project YOLO state down."""

    def test_function_signature_includes_yolo(self, html: str):
        # Match the function declaration — must include a 4th positional
        # parameter for the YOLO flag.
        pattern = re.compile(
            r"function renderReviewCard\(\s*r\s*,\s*provider\s*,\s*projectId\s*,\s*projectYolo\s*\)"
        )
        assert pattern.search(html), (
            "renderReviewCard signature must include projectYolo "
            "(the YOLO flag from /api/v1/reviews)"
        )


class TestAutoResolvingBranch:
    """When ``has_conflicts`` is true, the template must branch on
    ``projectYolo``: YOLO → passive indicator; non-YOLO → manual button.
    """

    def test_auto_resolving_span_exists(self, html: str):
        """The literal Auto-resolving span must appear in the template
        (verbatim from the issue's required behavior)."""
        assert 'class="conflict-badge auto-resolving"' in html, \
            "Auto-resolving indicator span is missing"
        assert "Auto-resolving" in html, \
            "Auto-resolving label text is missing"

    def test_auto_resolving_has_no_click_handler(self, html: str):
        """The Auto-resolving span must be passive — no onclick, no
        button element, no JS handler bound to it. The issue is
        explicit: 'No click target.'"""
        # Find the span and assert no onclick within its tag.
        match = re.search(
            r'<span\s+class="conflict-badge auto-resolving"[^>]*>',
            html,
        )
        assert match, "Auto-resolving span not found"
        tag = match.group(0)
        assert "onclick" not in tag.lower(), (
            "Auto-resolving span must not have an onclick handler — "
            "it's a passive indicator, not a button"
        )

    def test_resolve_button_still_present_for_non_yolo(self, html: str):
        """Non-YOLO projects must keep the manual 'Resolve Conflicts'
        button — the operator needs the lever when auto-rebase is off."""
        assert "Resolve Conflicts" in html, \
            "manual button label removed (must remain for non-YOLO projects)"
        assert "btn-resolve" in html, \
            "btn-resolve CSS class removed (still needed for non-YOLO)"
        assert "resolveConflicts(" in html, \
            "resolveConflicts() handler removed (still needed for non-YOLO)"

    def test_yolo_branch_selects_between_button_and_span(self, html: str):
        """The conflict branch must contain an if/else on projectYolo
        choosing between button and span — not always one or the other.
        """
        # The conflict-handling block lives inside renderReviewCard
        # under `else if (r.has_conflicts) {`. Extract that branch and
        # assert it switches on projectYolo.
        match = re.search(
            r"else if \(r\.has_conflicts\)\s*\{(.*?)\}\s*else if",
            html, re.DOTALL,
        )
        assert match, "has_conflicts branch not found in renderReviewCard"
        body = match.group(1)
        assert "projectYolo" in body, (
            "has_conflicts branch must inspect projectYolo to choose "
            "between auto-resolving span and Resolve Conflicts button"
        )
        # Both the button and the span have to be reachable from the
        # branch — verify both occur in its body.
        assert "btn-resolve" in body, (
            "Resolve Conflicts button must still be reachable from the "
            "has_conflicts branch for non-YOLO projects"
        )
        assert "auto-resolving" in body, (
            "Auto-resolving span must be reachable from the has_conflicts "
            "branch for YOLO projects"
        )


class TestProjectYoloThreadedThroughRender:
    """The flag from /api/v1/reviews must reach renderReviewCard via
    both the default (group-by-project) and queue-sort rendering paths.
    """

    def test_queue_sort_path_passes_project_yolo(self, html: str):
        """The queue-sort branch reads item.project_yolo and passes it
        to renderReviewCard."""
        # The flat-list / queue-sort branch builds the card with
        # renderReviewCard(review, provider, row.item.project_id, ...).
        # Assert the 4th argument is the project_yolo flag from row.item.
        pattern = re.compile(
            r"renderReviewCard\([^)]*row\.item\.project_id\s*,\s*!!row\.item\.project_yolo\s*\)"
        )
        assert pattern.search(html), (
            "queue-sort path must pass row.item.project_yolo to "
            "renderReviewCard"
        )

    def test_group_by_project_path_captures_project_yolo(self, html: str):
        """The byProject map must capture each project's yolo flag so
        every card in the group inherits it."""
        # byProject[key] = { ..., project_yolo: !!item.project_yolo, ... }
        pattern = re.compile(
            r"project_yolo\s*:\s*!!item\.project_yolo"
        )
        assert pattern.search(html), (
            "byProject map must capture item.project_yolo so renderReviewCard "
            "can read it for the default (grouped) sort mode"
        )

    def test_group_by_project_path_passes_project_yolo(self, html: str):
        """The grouped-by-project loop hands group.project_yolo into
        renderReviewCard as the 4th argument."""
        pattern = re.compile(
            r"renderReviewCard\(r,\s*group\.provider,\s*group\.project_id,\s*group\.project_yolo\s*\)"
        )
        assert pattern.search(html), (
            "default render path must pass group.project_yolo to "
            "renderReviewCard"
        )


class TestRetryButtonYoloGating:
    """The CI-failed 'Retry' button must be YOLO-gated like Resolve
    Conflicts: on YOLO projects the orchestrator auto-re-files a CI-fix
    task, so the manual button is redundant friction — replaced with a
    passive 'Auto-retrying…' indicator. Non-YOLO keeps the button.
    """

    def test_retry_branch_switches_on_project_yolo(self, html: str):
        # The ci_status === 'failed' block must branch on projectYolo.
        match = re.search(
            r"r\.ci_status === 'failed' && !r\.agent_active\)\s*\{(.*?)\n\s*\}\n\s*\}",
            html, re.DOTALL,
        )
        assert match, "ci_status failed block not found"
        body = match.group(1)
        assert "projectYolo" in body, (
            "the CI-failed block must inspect projectYolo to choose between "
            "the manual Retry button and the passive Auto-retrying indicator"
        )
        assert "btn-retry" in body, "non-YOLO Retry button must remain reachable"
        assert "auto-retrying" in body.lower() or "Auto-retrying" in body, (
            "YOLO path must show a passive Auto-retrying indicator"
        )

    def test_auto_retrying_indicator_is_passive(self, html: str):
        match = re.search(
            r'<span\s+class="conflict-badge auto-resolving"[^>]*>Auto-retrying',
            html,
        )
        assert match, "Auto-retrying passive indicator span is missing"
        assert "onclick" not in match.group(0).lower(), (
            "Auto-retrying indicator must be passive (no onclick)"
        )

    def test_retry_button_still_present_for_non_yolo(self, html: str):
        assert "btn-retry" in html and "retryReview(" in html, (
            "manual Retry button/handler must remain for non-YOLO projects"
        )
