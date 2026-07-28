"""Static dashboard regressions for duplicate-screening qualification state."""

from pathlib import Path


def _dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def test_dashboard_renders_all_duplicate_screening_states():
    html = _dashboard()

    assert "function renderDuplicateScreeningSummary(summary)" in html
    assert "Duplicate check pending" in html
    assert "Duplicate check running" in html
    assert "Duplicate checked" in html
    assert "Duplicate check stale" in html
    assert "${renderDuplicateScreeningSummary(issue.duplicate_screening)}" in html
    assert "renderDuplicateScreeningSummary(detail.duplicate_screening)" in html


def test_screening_badge_is_accessible_without_color():
    html = _dashboard()

    assert 'role="status"' in html
    assert 'aria-label="${esc(label + \': \' + detail)}"' in html
    assert "duplicate-screening-pill" in html


def test_preflight_agent_does_not_optimistically_move_card_in_progress():
    html = _dashboard()

    assert "!r.duplicate_preflight" in html
    assert "r.work_kind !== 'duplicate_screening'" in html
    assert "· screening" in html


def test_duplicate_screening_participates_in_card_fingerprint():
    html = _dashboard()

    assert "duplicate_screening: issue.duplicate_screening" in html
