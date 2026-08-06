"""Dashboard coverage for authoritative durable workflow projections."""

from pathlib import Path


def _dashboard() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def test_dashboard_renders_only_enforced_workflow_decisions():
    html = _dashboard()

    assert "function setWorkflowProjections(runtime, projections)" in html
    assert "runtime.mode === 'enforce'" in html
    assert "function renderWorkflowDecisionSummary(issue)" in html
    assert "projection.responsible_owner" in html
    assert "projection.reason_code" in html
    assert "projection.unmet_prerequisites" in html
    assert "${renderWorkflowDecisionSummary(issue)}" in html


def test_projection_change_invalidates_card_and_board_render_caches():
    html = _dashboard()

    assert "workflow_projection: workflowProjectionFor(issue)" in html
    assert "workflowProjectionRenderRevision" in html
    assert "workflowProjectionsChanged" in html
    assert (
        "workflowProjectionKey(issue.project_id, issue.identifier)" in html
    )
