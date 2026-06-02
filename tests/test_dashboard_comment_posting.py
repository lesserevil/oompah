"""Tests for dashboard comment posting behavior."""

from __future__ import annotations

from pathlib import Path

import pytest


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


@pytest.fixture(scope="module")
def submit_comment_body() -> str:
    return _function_body(_load_dashboard_script(), "submitComment")


def test_submit_comment_checks_post_response(submit_comment_body):
    assert "res = await fetch" in submit_comment_body
    assert "if (!res.ok)" in submit_comment_body


def test_submit_comment_preserves_draft_on_api_failure(submit_comment_body):
    failure_pos = submit_comment_body.index("if (!res.ok)")
    restore_pos = submit_comment_body.index("input.value = text", failure_pos)
    assert restore_pos > failure_pos
    assert "alert(message)" in submit_comment_body


def test_submit_comment_clears_input_only_after_success(submit_comment_body):
    fetch_pos = submit_comment_body.index("await fetch")
    clear_pos = submit_comment_body.rindex("input.value = ''")
    reload_pos = submit_comment_body.index("await openDetailPanel")
    assert clear_pos > fetch_pos
    assert reload_pos > clear_pos
