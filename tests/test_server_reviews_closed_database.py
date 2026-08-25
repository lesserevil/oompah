from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

import oompah.server as server_module
from oompah.server import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_mock_orch() -> MagicMock:
    orch = MagicMock()
    orch.project_store.list_all.return_value = []
    orch.state.running = {}
    return orch


class TestApiReviewsClosedDatabase:
    def test_closed_database_errors_are_degraded_without_error_watcher(self, client):
        orch = _make_mock_orch()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module,
                "_fetch_open_reviews_for_api",
                side_effect=sqlite3.ProgrammingError("Cannot operate on a closed database."),
            ),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 503, resp.text
        body = resp.json()
        assert body["error"]["code"] == "store_closed"
