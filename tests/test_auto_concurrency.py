"""Tests for automatic agent concurrency sizing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from oompah.config import ServiceConfig
from oompah.orchestrator import Orchestrator


def _make_orchestrator(tmp_path, configured_max: int) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(max_concurrent_agents=configured_max),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


class TestAutoConcurrency:
    def test_zero_configuration_uses_cpu_and_available_memory(self, tmp_path):
        orch = _make_orchestrator(tmp_path, configured_max=0)

        with (
            patch("oompah.orchestrator.os.cpu_count", return_value=32),
            patch("oompah.orchestrator._available_memory_bytes", return_value=40 * 1024**3),
        ):
            assert orch._refresh_effective_concurrency() == 8

        assert orch.state.max_concurrent_agents == 8
        snapshot = orch.get_snapshot()
        assert snapshot["concurrency"] == {
            "mode": "auto",
            "configured_max": 0,
            "effective_max": 8,
        }

    def test_auto_limit_is_recalculated_each_refresh(self, tmp_path):
        orch = _make_orchestrator(tmp_path, configured_max=0)

        with patch.object(orch, "_auto_concurrency_limit", side_effect=[12, 6]):
            assert orch._refresh_effective_concurrency() == 12
            assert orch._refresh_effective_concurrency() == 6

        assert orch.state.max_concurrent_agents == 6

    def test_lower_auto_limit_never_terminates_running_agents(self, tmp_path):
        orch = _make_orchestrator(tmp_path, configured_max=0)
        orch.state.running = {str(index): MagicMock() for index in range(8)}

        with patch.object(orch, "_auto_concurrency_limit", return_value=4):
            orch._refresh_effective_concurrency()

        assert len(orch.state.running) == 8
        assert orch.state.max_concurrent_agents == 4
        assert orch._available_slots() == 0

    def test_positive_configuration_remains_fixed(self, tmp_path):
        orch = _make_orchestrator(tmp_path, configured_max=7)

        with patch.object(orch, "_auto_concurrency_limit") as auto_limit:
            assert orch._refresh_effective_concurrency() == 7

        auto_limit.assert_not_called()
