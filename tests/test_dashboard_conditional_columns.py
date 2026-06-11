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


def test_proposed_column_is_first_core_column():
    script = _dashboard_script()
    columns = re.findall(r"\{key:\s*'([^']+)'", script)

    assert columns[:4] == ["Proposed", "Backlog", "Open", "In Progress"]

    config = _column_config(script, "Proposed")
    assert "label: 'Proposed'" in config
    assert "status: 'Proposed'" in config
    assert "base: true" in config


def test_needs_ci_fix_column_is_conditional():
    config = _column_config(_dashboard_script(), "Needs CI Fix")

    assert "label: 'Needs CI Fix'" in config
    assert "status: 'Needs CI Fix'" in config
    assert "base: false" in config


def test_proposed_column_is_first_base_column():
    script = _dashboard_script()
    proposed = _column_config(script, "Proposed")
    backlog = _column_config(script, "Backlog")

    assert "label: 'Proposed'" in proposed
    assert "status: 'Proposed'" in proposed
    assert "base: true" in proposed
    assert script.index(proposed) < script.index(backlog)


def test_needs_rebase_column_is_conditional():
    config = _column_config(_dashboard_script(), "Needs Rebase")

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


def test_visible_columns_hides_archived_when_inflight_only_is_on():
    script = _dashboard_script()
    match = re.search(
        r"function visibleColumns\(data\)\s*\{(?P<body>.*?)\n\}",
        script,
        re.DOTALL,
    )
    assert match, "Could not find visibleColumns helper"

    body = match.group("body")
    assert "c.key === 'Archived'" in body
    assert "isHideMergedOn()" in body
    assert "return false" in body
