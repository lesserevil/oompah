"""Dashboard API URL construction regressions for GitHub issue identifiers."""

from __future__ import annotations

from pathlib import Path


def _script() -> str:
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
    start = script.index(f"function {name}(")
    brace = script.index("{", script.index(")", start))
    depth = 0
    for pos in range(brace, len(script)):
        if script[pos] == "{":
            depth += 1
        elif script[pos] == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : pos]
    raise AssertionError(f"Could not find function body for {name!r}")


def _async_function_body(script: str, name: str) -> str:
    start = script.index(f"async function {name}(")
    brace = script.index("{", script.index(")", start))
    depth = 0
    for pos in range(brace, len(script)):
        if script[pos] == "{":
            depth += 1
        elif script[pos] == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : pos]
    raise AssertionError(f"Could not find async function body for {name!r}")


def test_issue_api_url_carries_full_github_identifier_as_issue_key():
    script = _script()
    body = _function_body(script, "issueApiUrl")

    assert "issuePathIdentifier(identifier)" in body
    assert "query.set('issue_key', identifier)" in body
    assert "/api/v1/issues/${pathId}${suffix}" in body


def test_update_issue_uses_route_safe_url_and_issue_key_body():
    script = _script()
    body = _async_function_body(script, "updateIssue")

    assert "fetch(issueApiUrl(identifier)" in body
    assert "JSON.stringify(issueRequestBody(identifier, outgoing))" in body
    assert "`/api/v1/issues/${identifier}`" not in body


def test_detail_panel_uses_route_safe_detail_and_release_pick_urls():
    script = _script()
    body = _async_function_body(script, "openDetailPanel")

    assert "issueApiUrl(identifier, '/detail'" in body
    assert "issueApiUrl(identifier, '/release-picks'" in body
    assert "encodeURIComponent(identifier)}/detail" not in body
