"""Tests that fetchIssues handles network errors gracefully.

Regression test for TASK-445: TypeError: Failed to fetch
    at fetchIssues (http://100.64.0.9:8090/:2167:21)
    at updateIssue (http://100.64.0.9:8090/:2218:24)
    at async HTMLDivElement.<anonymous> (http://100.64.0.9:8090/:2817:7)

The fetch() call in fetchIssues must be wrapped in a try-catch so that
network errors (which throw TypeError) are caught and the function returns
null instead of propagating the exception to callers like updateIssue.
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


def test_fetchIssues_wraps_fetch_in_try_catch():
    """fetchIssues must use try-catch around the fetch() call.

    fetch() throws TypeError on network errors (server unreachable, etc.).
    Without a try-catch the exception propagates to callers, including the
    error-recovery path in updateIssue which calls fetchIssues() to refresh
    the board after a failed update.
    """
    script = _load_dashboard_script()
    body = _function_body(script, "fetchIssues")

    assert "try {" in body, (
        "fetchIssues must use try { ... } catch to guard the fetch() call"
    )
    assert "} catch (err) {" in body or "} catch(err) {" in body, (
        "fetchIssues must have a catch block for network errors"
    )


def test_fetchIssues_returns_null_on_network_error():
    """fetchIssues must return null when a network error occurs.

    Callers like updateIssue already check 'if (data)' before using the result,
    so returning null is the correct signal for a failed fetch.
    """
    script = _load_dashboard_script()
    body = _function_body(script, "fetchIssues")

    catch_pos = body.find("} catch")
    assert catch_pos != -1, "fetchIssues must have a catch block"

    after_catch = body[catch_pos:]
    assert "return null" in after_catch, (
        "The catch block in fetchIssues must return null on network error"
    )


def test_fetchIssues_still_handles_http_errors():
    """fetchIssues must still check !res.ok for non-200 HTTP responses."""
    script = _load_dashboard_script()
    body = _function_body(script, "fetchIssues")

    assert "if (!res.ok)" in body, (
        "fetchIssues must still check res.ok to handle HTTP error responses"
    )


def test_fetchIssues_try_catch_precedes_ok_check():
    """The try-catch network guard must come before the !res.ok HTTP error check."""
    script = _load_dashboard_script()
    body = _function_body(script, "fetchIssues")

    try_pos = body.index("try {")
    ok_check_pos = body.index("if (!res.ok)")
    assert try_pos < ok_check_pos, (
        "try-catch must appear before the !res.ok check in fetchIssues"
    )
