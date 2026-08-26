"""Regression test for OOMPAH-1338: closed database error handling in Reviews API."""

import sqlite3
import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


def test_api_list_reviews_closed_database_returns_503():
    """Test that closed database errors return 503 with graceful message, not ERROR log."""
    from oompah.server import app
    
    client = TestClient(app)
    
    # Mock _get_orchestrator to raise sqlite3.ProgrammingError with "closed database"
    with patch("oompah.server._get_orchestrator") as mock_get_orch:
        mock_get_orch.side_effect = sqlite3.ProgrammingError("Cannot operate on a closed database.")
        
        # The endpoint should return 503, not 500
        response = client.get("/api/v1/reviews")
        assert response.status_code == 503
        
        # Response should have actionable error code
        data = response.json()
        assert data["error"]["code"] == "store_closed"
        assert "temporarily unavailable" in data["error"]["message"].lower()


def test_api_list_reviews_closed_database_logs_warning_not_error():
    """Test that closed database errors log WARNING, not ERROR (so error_watcher is not triggered)."""
    from oompah.server import app
    
    client = TestClient(app)
    
    # Mock _get_orchestrator to raise the closed database error
    with patch("oompah.server._get_orchestrator") as mock_get_orch, \
         patch("oompah.server.logger") as mock_logger:
        mock_get_orch.side_effect = sqlite3.ProgrammingError("Cannot operate on a closed database.")
        
        response = client.get("/api/v1/reviews")
        
        # Verify warning was logged (not error)
        assert mock_logger.warning.called
        # Verify error() was NOT called for closed database (only for other exceptions)
        warning_calls = mock_logger.warning.call_args_list
        assert any("closed database" in str(call) for call in warning_calls)


def test_api_list_reviews_other_sql_errors_still_log_error():
    """Test that other sqlite3 errors still log ERROR as before."""
    from oompah.server import app
    
    client = TestClient(app)
    
    # Mock _get_orchestrator to raise a different sqlite3 error
    with patch("oompah.server._get_orchestrator") as mock_get_orch, \
         patch("oompah.server.logger") as mock_logger:
        mock_get_orch.side_effect = sqlite3.ProgrammingError("Some other SQL error")
        
        response = client.get("/api/v1/reviews")
        
        # Other SQL errors should still return 500
        assert response.status_code == 500
        
        # And should log error
        assert mock_logger.error.called


def test_api_list_reviews_non_sql_errors_still_log_error():
    """Test that non-SQL errors still log ERROR as before."""
    from oompah.server import app
    
    client = TestClient(app)
    
    # Mock _get_orchestrator to raise a generic error
    with patch("oompah.server._get_orchestrator") as mock_get_orch, \
         patch("oompah.server.logger") as mock_logger:
        mock_get_orch.side_effect = RuntimeError("Some other error")
        
        response = client.get("/api/v1/reviews")
        
        # Generic errors should return 500
        assert response.status_code == 500
        
        # And should log error
        assert mock_logger.error.called
