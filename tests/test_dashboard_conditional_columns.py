"""Tests for dashboard columns that should only render when populated."""

from __future__ import annotations

import re
from pathlib import Path


def _dashboard_script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _column_config(script: str, key: str) -> str:
    match = re.search(rf"\{{key:\s*'{re.escape(key)}'[^}}]+\}}", script)
    assert match, f"Could not find dashboard column config for {key}"
    return match.group(0)


def test_needs_ci_fix_column_is_conditional():
    config = _column_config(_dashboard_script(), "needs_ci_fix")

    assert "label: 'Needs CI Fix'" in config
    assert "status: 'Needs CI Fix'" in config
    assert "base: false" in config


def test_needs_rebase_column_is_conditional():
    config = _column_config(_dashboard_script(), "needs_rebase")

    assert "label: 'Needs Rebase'" in config
    assert "status: 'Needs Rebase'" in config
    assert "base: false" in config


def test_visible_columns_keeps_conditional_columns_when_populated():
    script = _dashboard_script()
    match = re.search(
        r"function visibleColumns\(data\)\s*\{(?P<body>.*?)\n\}",
        script,
        re.DOTALL,
    )
    assert match, "Could not find visibleColumns helper"

    body = match.group("body")
    assert "c.base || ((data && data[c.key]) || []).length > 0" in body
