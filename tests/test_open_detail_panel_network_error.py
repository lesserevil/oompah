"""Tests that openDetailPanel handles network errors gracefully.

Regression test for TASK-444: TypeError: Failed to fetch
    at openDetailPanel (http://100.64.0.9:8090/:3265:21)

The fetch() call in openDetailPanel must be wrapped in a try-catch so that
network errors (which throw TypeError) are caught and shown to the user
instead of propagating as an unhandled exception.
"""

from __future__ import annotations

from pathlib import Path


def _load_dashboard_script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _function_body(script: str, name: str) -> str:
    marker = f"async function {name}("
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
                return script[brace + 1:pos]
    raise AssertionError(f"Could not find function body for {name}")


def test_openDetailPanel_wraps_fetch_in_try_catch():
    """openDetailPanel must use try-catch around the detail fetch call.

    fetch() throws TypeError on network errors (server unreachable, etc.).
    Without a try-catch the exception propagates uncaught to the browser console.
    """
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel")

    assert "try {" in body, (
        "openDetailPanel must use try { ... } catch to guard the fetch() call"
    )
    assert "} catch (err) {" in body or "} catch(err) {" in body, (
        "openDetailPanel must have a catch block for network errors"
    )


def test_openDetailPanel_shows_network_error_message_in_panel():
    """On network error, openDetailPanel must display an error message in the panel body."""
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel")

    # Find the catch block and verify it sets body.innerHTML to an error message
    catch_pos = body.find("} catch")
    assert catch_pos != -1, "openDetailPanel must have a catch block"

    after_catch = body[catch_pos:]
    assert "body.innerHTML" in after_catch, (
        "The catch block must update body.innerHTML to show an error to the user"
    )
    assert "network error" in after_catch, (
        "The error message shown on network failure must mention 'network error'"
    )


def test_openDetailPanel_still_handles_http_errors():
    """openDetailPanel must still check !res.ok for non-200 HTTP responses."""
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel")

    assert "if (!res.ok)" in body, (
        "openDetailPanel must still check res.ok to handle HTTP error responses"
    )


def test_openDetailPanel_try_catch_precedes_ok_check():
    """The try-catch network guard must come before the !res.ok HTTP error check."""
    script = _load_dashboard_script()
    body = _function_body(script, "openDetailPanel")

    try_pos = body.index("try {")
    ok_check_pos = body.index("if (!res.ok)")
    assert try_pos < ok_check_pos, (
        "try-catch must appear before the !res.ok check in openDetailPanel"
    )
