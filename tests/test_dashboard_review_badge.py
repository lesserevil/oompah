"""Static tests for the dashboard reviews badge."""

from __future__ import annotations

import os
import re


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_func_body(script: str, fn_name: str) -> str:
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\([^)]*\)\s*\{{")
    match = pattern.search(script)
    assert match, f"Could not find function {fn_name}"
    start = match.end() - 1
    depth = 0
    for index in range(start, len(script)):
        char = script[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1:index]
    raise AssertionError(f"Could not find end of function {fn_name}")


def test_reviews_badge_surfaces_unavailable_runners():
    html = _load_dashboard_html()
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts
    script = max(scripts, key=len)
    body = _extract_func_body(script, "updateReviewsBadge")

    assert "unavailable_runners" in body
    assert "runner unavailable" in body
    assert "runners unavailable" in body
    assert "Queued CI is waiting for unavailable self-hosted runner hardware" in body
