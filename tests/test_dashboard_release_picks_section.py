"""Tests for the Release Picks section in the task detail panel (TASK-456.2).

Verifies that the dashboard HTML:
  - Defines renderReleasePicksSection() helper function
  - Defines releasePickNextAction() helper function
  - Defines openAddReleasePicksModal() action function
  - Fetches the release-picks API endpoint in openDetailPanel()
  - Passes the release-picks data to renderReleasePicksSection()
  - Renders per-entry fields: branch, status, child task link, PR link, next action
  - Renders an "Add Release Picks" button
  - Gracefully degrades when the release-picks fetch fails
  - Defines CSS styles for the Release Picks section
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers for extracting script/style content from the dashboard HTML
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
# CSS styles
# ---------------------------------------------------------------------------


def test_css_defines_release_picks_list():
    """CSS must define .release-picks-list for the backport entry list."""
    styles = _load_dashboard_styles()
    assert ".release-picks-list" in styles, (
        "CSS must define .release-picks-list"
    )


def test_css_defines_release_pick_entry():
    """CSS must define .release-pick-entry for individual pick rows."""
    styles = _load_dashboard_styles()
    assert ".release-pick-entry" in styles, (
        "CSS must define .release-pick-entry"
    )


def test_css_defines_release_pick_branch():
    """CSS must define .release-pick-branch for the branch name chip."""
    styles = _load_dashboard_styles()
    assert ".release-pick-branch" in styles, (
        "CSS must define .release-pick-branch"
    )


def test_css_defines_release_pick_status():
    """CSS must define .release-pick-status for the status badge."""
    styles = _load_dashboard_styles()
    assert ".release-pick-status" in styles, (
        "CSS must define .release-pick-status"
    )


def test_css_defines_status_variants():
    """CSS must define colour variants for key status values."""
    styles = _load_dashboard_styles()
    for variant in ("waiting", "pr_open", "conflict", "merged", "needs_human"):
        assert f"release-pick-status-{variant}" in styles, (
            f"CSS must define .release-pick-status-{variant}"
        )


def test_css_defines_release_pick_task_link():
    """CSS must define .release-pick-task-link for child task links."""
    styles = _load_dashboard_styles()
    assert ".release-pick-task-link" in styles, (
        "CSS must define .release-pick-task-link"
    )


def test_css_defines_release_pick_pr_link():
    """CSS must define .release-pick-pr-link for PR links."""
    styles = _load_dashboard_styles()
    assert ".release-pick-pr-link" in styles, (
        "CSS must define .release-pick-pr-link"
    )


def test_css_defines_release_pick_next_action():
    """CSS must define .release-pick-next-action for the next-action hint."""
    styles = _load_dashboard_styles()
    assert ".release-pick-next-action" in styles, (
        "CSS must define .release-pick-next-action"
    )


# ---------------------------------------------------------------------------
# releasePickNextAction()
# ---------------------------------------------------------------------------


def test_releasePickNextAction_function_exists():
    """releasePickNextAction() must be defined in the dashboard script."""
    script = _load_dashboard_script()
    assert "function releasePickNextAction(" in script, (
        "dashboard must define releasePickNextAction()"
    )


def test_releasePickNextAction_covers_all_statuses():
    """releasePickNextAction must have entries for all lifecycle statuses."""
    script = _load_dashboard_script()
    body = _function_body(script, "releasePickNextAction")
    for status in (
        "waiting", "task_created", "cherry_picking", "pr_open",
        "conflict", "merged", "archived", "needs_human", "skipped",
    ):
        assert f"'{status}'" in body, (
            f"releasePickNextAction must have an entry for status '{status}'"
        )


def test_releasePickNextAction_conflict_instructs_resolution():
    """The 'conflict' status must hint at resolving the conflict."""
    script = _load_dashboard_script()
    body = _function_body(script, "releasePickNextAction")
    conflict_action_start = body.index("'conflict'")
    # The value after 'conflict': key should mention "conflict" or "resolve"
    snippet = body[conflict_action_start : conflict_action_start + 80].lower()
    assert "conflict" in snippet or "resolve" in snippet, (
        "releasePickNextAction for 'conflict' should hint about resolving conflicts"
    )


def test_releasePickNextAction_needs_human_instructs_manual_action():
    """The 'needs_human' status must hint at manual action."""
    script = _load_dashboard_script()
    body = _function_body(script, "releasePickNextAction")
    nh_start = body.index("'needs_human'")
    snippet = body[nh_start : nh_start + 80].lower()
    assert "manual" in snippet or "human" in snippet, (
        "releasePickNextAction for 'needs_human' should hint about manual action"
    )


# ---------------------------------------------------------------------------
# renderReleasePicksSection()
# ---------------------------------------------------------------------------


def test_renderReleasePicksSection_function_exists():
    """renderReleasePicksSection() must be defined in the dashboard script."""
    script = _load_dashboard_script()
    assert "function renderReleasePicksSection(" in script, (
        "dashboard must define renderReleasePicksSection()"
    )


def test_renderReleasePicksSection_renders_branch():
    """renderReleasePicksSection must render the branch name using .release-pick-branch."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "release-pick-branch" in body, (
        "renderReleasePicksSection must use .release-pick-branch for branch names"
    )
    assert "entry.branch" in body, (
        "renderReleasePicksSection must reference entry.branch"
    )


def test_renderReleasePicksSection_renders_status():
    """renderReleasePicksSection must render the status badge."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "release-pick-status" in body, (
        "renderReleasePicksSection must use .release-pick-status for status badges"
    )
    assert "entry.status" in body, (
        "renderReleasePicksSection must reference entry.status"
    )


def test_renderReleasePicksSection_renders_child_task_link():
    """renderReleasePicksSection must render child task links for entries with task_id."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "entry.task_id" in body, (
        "renderReleasePicksSection must reference entry.task_id"
    )
    assert "release-pick-task-link" in body, (
        "renderReleasePicksSection must use .release-pick-task-link for child task links"
    )
    assert "openDetailPanel" in body, (
        "renderReleasePicksSection must call openDetailPanel when child task is clicked"
    )


def test_renderReleasePicksSection_renders_pr_link():
    """renderReleasePicksSection must render PR links for entries with pr_url."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "entry.pr_url" in body, (
        "renderReleasePicksSection must reference entry.pr_url"
    )
    assert "release-pick-pr-link" in body, (
        "renderReleasePicksSection must use .release-pick-pr-link for PR links"
    )
    # PR links should open in a new tab
    assert "target=" in body, (
        "PR links should include a target attribute (open in new tab)"
    )


def test_renderReleasePicksSection_renders_next_action():
    """renderReleasePicksSection must render the next-action hint via releasePickNextAction."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "releasePickNextAction" in body, (
        "renderReleasePicksSection must call releasePickNextAction for per-entry hints"
    )
    assert "release-pick-next-action" in body, (
        "renderReleasePicksSection must use .release-pick-next-action CSS class"
    )


def test_renderReleasePicksSection_renders_add_button():
    """renderReleasePicksSection must render an 'Add Release Picks' button."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "Add Release Picks" in body, (
        "renderReleasePicksSection must include an '+ Add Release Picks' button"
    )
    assert "openAddReleasePicksModal" in body, (
        "The Add Release Picks button must call openAddReleasePicksModal"
    )


def test_renderReleasePicksSection_shows_empty_state():
    """renderReleasePicksSection must show a message when there are no picks."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    # Look for an empty-state message (e.g., "No release picks")
    assert "no release picks" in body.lower() or "no release picks yet" in body.lower(), (
        "renderReleasePicksSection must show an empty-state message when no picks exist"
    )


def test_renderReleasePicksSection_renders_backport_of():
    """renderReleasePicksSection must render the backport_of link for child tasks."""
    script = _load_dashboard_script()
    body = _function_body(script, "renderReleasePicksSection")
    assert "backportOf" in body or "backport_of" in body, (
        "renderReleasePicksSection must handle the backport_of field"
    )
    assert "Backport of" in body, (
        "renderReleasePicksSection must display 'Backport of' label for backport tasks"
    )


# ---------------------------------------------------------------------------
# openAddReleasePicksModal()
# ---------------------------------------------------------------------------


def test_openAddReleasePicksModal_function_exists():
    """openAddReleasePicksModal() must be defined in the dashboard script."""
    script = _load_dashboard_script()
    assert "function openAddReleasePicksModal(" in script, (
        "dashboard must define openAddReleasePicksModal()"
    )


def test_openAddReleasePicksModal_dispatches_custom_event():
    """openAddReleasePicksModal must dispatch an 'oompah:open-add-release-picks' event."""
    script = _load_dashboard_script()
    body = _function_body(script, "openAddReleasePicksModal")
    assert "oompah:open-add-release-picks" in body, (
        "openAddReleasePicksModal must dispatch CustomEvent 'oompah:open-add-release-picks'"
    )
    assert "dispatchEvent" in body or "CustomEvent" in body, (
        "openAddReleasePicksModal must use dispatchEvent/CustomEvent"
    )


# ---------------------------------------------------------------------------
# openDetailPanel() integration
# ---------------------------------------------------------------------------


def test_openDetailPanel_fetches_release_picks_endpoint():
    """openDetailPanel must fetch the release-picks API endpoint."""
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel", is_async=True)
    assert "release-picks" in body, (
        "openDetailPanel must fetch the /release-picks endpoint"
    )


def test_openDetailPanel_release_picks_fetch_starts_in_parallel():
    """The release-picks fetch must start before awaiting the detail fetch.

    Kicking off both fetches before the first await allows them to
    run concurrently, reducing perceived latency.
    """
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel", is_async=True)
    # The release-picks fetch assignment must appear before the detail await
    rp_fetch_pos = body.find("release-picks")
    detail_await_pos = body.find("await fetch")
    assert rp_fetch_pos < detail_await_pos, (
        "The release-picks fetch must be initiated before the first 'await fetch' "
        "so both requests run in parallel"
    )


def test_openDetailPanel_catches_release_picks_errors():
    """openDetailPanel must catch errors from the release-picks fetch gracefully."""
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel", is_async=True)
    # The release picks fetch should have error handling (either .catch() or try/catch)
    rp_idx = body.find("release-picks")
    after_rp = body[rp_idx:]
    assert ".catch(" in after_rp or "try {" in after_rp, (
        "openDetailPanel must handle release-picks fetch failures gracefully "
        "(use .catch() or try/catch)"
    )


def test_openDetailPanel_calls_renderReleasePicksSection():
    """openDetailPanel must define renderReleasePicksSection (kept for migration; active call moved to addendums).

    OOMPAH-180 replaced the active renderReleasePicksSection call in openDetailPanel with
    renderReleaseAddendumsSection. The old function remains for migration but is no longer
    called directly in openDetailPanel. This test now verifies the new renderer is called.
    """
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel", is_async=True)
    # The active release section is now rendered by renderReleaseAddendumsSection (OOMPAH-180).
    assert "renderReleaseAddendumsSection(" in body, (
        "openDetailPanel must call renderReleaseAddendumsSection() (OOMPAH-180)"
    )
    # The old function must still be defined in the script (kept for migration period).
    assert "function renderReleasePicksSection(" in script, (
        "renderReleasePicksSection() must still be defined for migration compatibility"
    )


def test_openDetailPanel_passes_picks_data_to_renderer():
    """openDetailPanel must pass addendum data to renderReleaseAddendumsSection (OOMPAH-180).

    The release-picks fetch is still present for migration compatibility, but the active
    renderer is renderReleaseAddendumsSection which receives _raData (addendum payload).
    """
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel", is_async=True)
    render_call_pos = body.index("renderReleaseAddendumsSection(")
    render_call = body[render_call_pos : render_call_pos + 100]
    # The renderer call must reference the variable holding the addendum data
    assert any(varname in render_call for varname in ["_raData", "raData", "addendumData"]), (
        "openDetailPanel must pass the fetched addendum data to renderReleaseAddendumsSection"
    )
