"""Contract tests for the repository-hygiene dashboard panel."""

from __future__ import annotations

import os
import re


def _load_dashboard() -> str:
    path = os.path.join(
        os.path.dirname(__file__), "..", "oompah", "templates", "dashboard.html"
    )
    with open(path, encoding="utf-8") as dashboard:
        return dashboard.read()


def _extract_function(name: str, html: str) -> str:
    pattern = re.compile(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{")
    match = pattern.search(html)
    if not match:
        return ""
    depth = 0
    for index in range(match.start(), len(html)):
        if html[index] == "{":
            depth += 1
        elif html[index] == "}":
            depth -= 1
            if depth == 0:
                return html[match.start() : index + 1]
    return html[match.start() :]


class TestRepositoryHygienePanel:
    def test_panel_is_accessible_and_hidden_until_state_arrives(self):
        html = _load_dashboard()
        match = re.search(r'<[^>]+id="repo-hygiene-health"[^>]*>', html)
        assert match is not None
        tag = match.group(0)
        assert "hidden" in tag
        assert 'role="status"' in tag
        assert 'aria-live="polite"' in tag
        assert 'aria-label="Repository hygiene health"' in tag

    def test_panel_has_inventory_and_actionable_detail_regions(self):
        html = _load_dashboard()
        for element_id in (
            "repo-hygiene-inventory",
            "repo-hygiene-overdue-list",
            "repo-hygiene-error-list",
        ):
            assert f'id="{element_id}"' in html

    def test_renderer_handles_health_and_clears_when_missing(self):
        html = _load_dashboard()
        function = _extract_function("renderRepoHygieneHealth", html)
        assert function
        assert "health.is_healthy" in function
        assert "health.worktrees" in function
        assert "health.branches_local" in function
        assert "health.branches_remote" in function
        assert "health.overdue_artifacts" in function
        assert "health.cleanup_errors" in function
        assert "panel.hidden = false" in function
        assert "panel.hidden = true" in function

    def test_renderer_escapes_artifact_identifiers(self):
        html = _load_dashboard()
        function = _extract_function("renderRepoHygieneHealth", html)
        assert "esc(String(artifact.identifier" in function
        assert "esc(String(error))" in function

    def test_state_update_reads_maintenance_health_payload(self):
        html = _load_dashboard()
        function = _extract_function("handleStateUpdate", html)
        assert "state.orchestrator_metrics" in function
        assert "maintenance.repo_hygiene_health" in function
        assert "renderRepoHygieneHealth" in function
