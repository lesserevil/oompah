"""Tests for filtering running-agent chips by the dashboard project filter."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def dashboard_script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text()
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def test_running_agent_filter_helpers_exist(dashboard_script: str):
    assert "function selectedProjectFilterValue()" in dashboard_script
    assert "function filterRunningAgentsForCurrentProject(running)" in dashboard_script
    assert "function renderRunningAgentChips(running, paused)" in dashboard_script


def test_running_agent_chips_use_project_filtered_entries(dashboard_script: str):
    assert (
        "const visibleRunning = filterRunningAgentsForCurrentProject(running);"
        in dashboard_script
    )
    assert "visibleRunning.map(r =>" in dashboard_script
    assert "countEl.textContent = visibleRunning.length;" in dashboard_script
    assert "visibleRunning.length === 0" in dashboard_script


def test_project_filter_change_rerenders_running_agent_chips(dashboard_script: str):
    assert "localStorage.setItem('oompah_selected_project', sel.value);" in (
        dashboard_script
    )
    assert "renderRunningAgentChips(lastRunningAgents, orchPaused);" in (
        dashboard_script
    )


def test_state_update_keeps_global_running_for_dispatch_diff(dashboard_script: str):
    assert "const running = state.running || [];" in dashboard_script
    assert "const newDispatchIds = running" in dashboard_script
    assert "lastRunningAgents = running;" in dashboard_script
    assert "renderRunningAgentChips(running, orchPaused);" in dashboard_script


def test_board_and_fetch_use_same_validated_project_filter(dashboard_script: str):
    assert "function filterByProject(data)" in dashboard_script
    assert "const pid = selectedProjectFilterValue();" in dashboard_script
    assert (
        "const url = pid ? '/api/v1/issues?project_id=' + encodeURIComponent(pid)"
        in dashboard_script
    )
