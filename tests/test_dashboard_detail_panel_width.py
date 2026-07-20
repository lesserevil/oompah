"""Regression coverage for the dashboard task-detail pane width."""

from __future__ import annotations

from pathlib import Path


def test_open_task_detail_panel_is_wide_but_capped_to_viewport() -> None:
    """The right-side task detail pane is 800px at most and never over 40vw."""
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")

    assert ".detail-panel.open" in html
    assert "width: min(800px, 40vw);" in html
