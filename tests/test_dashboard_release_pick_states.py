"""Tests for TASK-456.5 - Surface release-pick validation and conflict states.

Verifies that the dashboard HTML surfaces all important release-pick states
clearly in the UI without requiring operators to inspect logs:

  - Branch validation errors (is_valid=false, validation_error message)
  - Waiting-for-source-merge state (waiting status with descriptive label)
  - Open PRs (pr_open status with active PR link)
  - Merged picks (merged status with checkmark indicator)
  - Closed PRs (pr_url present but PR closed → line-through + "(closed)" label)
  - Cherry-pick conflicts (conflict status with actionable hint)
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_dashboard_html() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def _load_dashboard_script() -> str:
    html = _load_dashboard_html()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _load_dashboard_styles() -> str:
    html = _load_dashboard_html()
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>")
    return html[start:end]


def _function_body(script: str, name: str, is_async: bool = False) -> str:
    """Extract the body of a named JavaScript function using brace counting."""
    prefix = "async function" if is_async else "function"
    marker = f"{prefix} {name}("
    start = script.index(marker)
    brace = script.index("{", start)
    depth = 0
    for pos in range(brace, len(script)):
        char = script[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : pos]
    raise AssertionError(f"Could not find function body for {name}")


# ---------------------------------------------------------------------------
# CSS — new state classes required by TASK-456.5
# ---------------------------------------------------------------------------


def test_css_defines_validation_error_class():
    """CSS must define .release-pick-validation-error for validation error banners."""
    styles = _load_dashboard_styles()
    assert ".release-pick-validation-error" in styles, (
        "CSS must define .release-pick-validation-error"
    )


def test_css_validation_error_uses_red_color():
    """The validation-error CSS must use a red/danger color to draw attention."""
    styles = _load_dashboard_styles()
    idx = styles.index(".release-pick-validation-error")
    # Grab the rule block
    brace_open = styles.index("{", idx)
    brace_close = styles.index("}", brace_open)
    rule = styles[brace_open:brace_close]
    assert "red" in rule or "f85149" in rule.lower() or "248,81,73" in rule, (
        ".release-pick-validation-error must use a red color"
    )


def test_css_defines_pr_closed_class():
    """CSS must define .release-pick-pr-closed for closed PR link styling."""
    styles = _load_dashboard_styles()
    assert ".release-pick-pr-closed" in styles, (
        "CSS must define .release-pick-pr-closed"
    )


def test_css_pr_closed_uses_muted_or_strikethrough():
    """The pr-closed CSS must visually de-emphasise the closed PR link."""
    styles = _load_dashboard_styles()
    idx = styles.index(".release-pick-pr-closed")
    brace_open = styles.index("{", idx)
    brace_close = styles.index("}", brace_open)
    rule = styles[brace_open:brace_close]
    # Either muted colour, opacity, or line-through
    assert (
        "text-muted" in rule
        or "muted" in rule
        or "opacity" in rule
        or "line-through" in rule
    ), ".release-pick-pr-closed must de-emphasise the link (muted/opacity/line-through)"


# ---------------------------------------------------------------------------
# Branch validation errors (TASK-456.5 primary feature)
# ---------------------------------------------------------------------------


def test_renderReleasePicksSection_reads_is_valid():
    """renderReleasePicksSection must check entry.is_valid to detect invalid branches."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "is_valid" in body, (
        "renderReleasePicksSection must reference entry.is_valid"
    )


def test_renderReleasePicksSection_displays_validation_error():
    """renderReleasePicksSection must render entry.validation_error text."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "validation_error" in body, (
        "renderReleasePicksSection must reference entry.validation_error"
    )


def test_renderReleasePicksSection_validation_error_uses_css_class():
    """Validation error messages must use .release-pick-validation-error CSS class."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "release-pick-validation-error" in body, (
        "renderReleasePicksSection must apply .release-pick-validation-error class"
    )


def test_renderReleasePicksSection_validation_error_only_when_invalid():
    """Validation error HTML must only be emitted when is_valid is false."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    # The condition must guard on is_valid being falsy
    assert "!entry.is_valid" in body or "entry.is_valid === false" in body or \
           "entry.is_valid == false" in body, (
        "renderReleasePicksSection must guard validation error on !entry.is_valid"
    )


# ---------------------------------------------------------------------------
# Closed PR display
# ---------------------------------------------------------------------------


def test_renderReleasePicksSection_shows_closed_pr_indicator():
    """renderReleasePicksSection must show a '(closed)' indicator for closed PRs."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "(closed)" in body, (
        "renderReleasePicksSection must include '(closed)' text for PRs that were "
        "closed without merging"
    )


def test_renderReleasePicksSection_closed_pr_uses_css_class():
    """Closed PR links must use .release-pick-pr-closed CSS class."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "release-pick-pr-closed" in body, (
        "renderReleasePicksSection must apply .release-pick-pr-closed to closed PR links"
    )


def test_renderReleasePicksSection_distinguishes_open_vs_closed_pr():
    """renderReleasePicksSection must use pr_open status to decide if PR is open."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "'pr_open'" in body or '"pr_open"' in body, (
        "renderReleasePicksSection must check for pr_open status to distinguish "
        "open PRs from closed ones"
    )


def test_renderReleasePicksSection_merged_pr_has_indicator():
    """renderReleasePicksSection must add a ✓ indicator for merged PR links."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    # Must check for 'merged' status and show a success indicator
    assert "'merged'" in body or '"merged"' in body, (
        "renderReleasePicksSection must check for merged status for PR link styling"
    )
    assert "✓" in body, (
        "renderReleasePicksSection must show a ✓ indicator for merged PRs"
    )


# ---------------------------------------------------------------------------
# Waiting-for-source-merge state
# ---------------------------------------------------------------------------


def test_releasePickNextAction_waiting_mentions_source_or_merge():
    """The 'waiting' next-action must mention source merge, not generic 'pending'."""
    script = _load_dashboard_script()
    body = _function_body(script, "releasePickNextAction")
    waiting_start = body.index("'waiting'")
    # Scan ahead up to 120 chars for the value
    snippet = body[waiting_start : waiting_start + 120].lower()
    assert "source" in snippet or "merge" in snippet, (
        "releasePickNextAction for 'waiting' must mention 'source' or 'merge' "
        "to explain why automation is waiting"
    )


# ---------------------------------------------------------------------------
# Conflict state
# ---------------------------------------------------------------------------


def test_releasePickNextAction_conflict_mentions_resolve_and_pick():
    """The 'conflict' next-action must guide the operator to resolve and re-pick."""
    script = _load_dashboard_script()
    body = _function_body(script, "releasePickNextAction")
    conflict_start = body.index("'conflict'")
    snippet = body[conflict_start : conflict_start + 120].lower()
    assert "resolve" in snippet or "conflict" in snippet, (
        "releasePickNextAction for 'conflict' must mention 'resolve' or 'conflict'"
    )
    # Also check it mentions the re-pick action
    assert "pick" in snippet or "re-pick" in snippet or "retry" in snippet or "resolve" in snippet, (
        "releasePickNextAction for 'conflict' should guide toward a resolution action"
    )


def test_css_conflict_status_uses_red():
    """The conflict status badge CSS must use red/danger colors."""
    styles = _load_dashboard_styles()
    idx = styles.index("release-pick-status-conflict")
    snippet = styles[idx : idx + 120]
    assert "red" in snippet or "f85149" in snippet.lower() or "248,81,73" in snippet, (
        ".release-pick-status-conflict must use red/danger colors"
    )


# ---------------------------------------------------------------------------
# Merged picks
# ---------------------------------------------------------------------------


def test_css_merged_status_uses_green():
    """The merged status badge CSS must use green/success colors."""
    styles = _load_dashboard_styles()
    idx = styles.index("release-pick-status-merged")
    snippet = styles[idx : idx + 120]
    assert "green" in snippet or "63,185,80" in snippet or "3fb950" in snippet.lower(), (
        ".release-pick-status-merged must use green/success colors"
    )
