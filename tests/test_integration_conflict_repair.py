"""Tests for conflict repair lifecycle with backoff and infrastructure failure handling."""

from datetime import datetime, timedelta, timezone

import pytest

from oompah.integration import (
    IntegrationRecord,
    classify_conflict_repair_failure,
)


class TestConflictRepairFailureClassification:
    """Test classification of conflict repair failures."""

    def test_real_conflict_detected(self):
        """Real merge conflicts should be classified as 'conflict'."""
        assert classify_conflict_repair_failure("merge conflict") == "conflict"
        assert classify_conflict_repair_failure("Automatic merge failed") == "conflict"
        assert classify_conflict_repair_failure("cannot merge") == "conflict"
        assert classify_conflict_repair_failure("conflict markers") == "conflict"
        assert classify_conflict_repair_failure("Rebase conflict") == "conflict"

    def test_auth_failures_detected(self):
        """Authentication failures should be classified as 'auth_failed'."""
        assert classify_conflict_repair_failure("401 Unauthorized") == "auth_failed"
        assert classify_conflict_repair_failure("403 Forbidden") == "auth_failed"
        assert classify_conflict_repair_failure("authentication failed") == "auth_failed"
        assert classify_conflict_repair_failure("auth failed") == "auth_failed"

    def test_rate_limit_detected(self):
        """Rate limit errors should be classified as 'rate_limited'."""
        assert classify_conflict_repair_failure("429 Too Many Requests") == "rate_limited"
        assert classify_conflict_repair_failure("rate limit exceeded") == "rate_limited"
        assert classify_conflict_repair_failure("rate_limited") == "rate_limited"

    def test_timeout_detected(self):
        """Timeout errors should be classified as 'timeout'."""
        assert classify_conflict_repair_failure("timed out") == "timeout"
        assert classify_conflict_repair_failure("timeout") == "timeout"
        assert classify_conflict_repair_failure("deadline exceeded") == "timeout"

    def test_provider_overloaded_detected(self):
        """Overload errors should be classified as 'overloaded'."""
        assert classify_conflict_repair_failure("503 Service Unavailable") == "overloaded"
        assert classify_conflict_repair_failure("504 Gateway Timeout") == "overloaded"
        assert classify_conflict_repair_failure("529 Overloaded") == "overloaded"
        assert classify_conflict_repair_failure("overloaded") == "overloaded"

    def test_provider_unavailable_detected(self):
        """Provider unavailability errors should be classified."""
        assert classify_conflict_repair_failure("provider not available") == "provider_unavailable"
        assert classify_conflict_repair_failure("500 Internal Server Error") == "provider_unavailable"
        assert classify_conflict_repair_failure("connection refused") == "provider_unavailable"

    def test_missing_credentials_detected(self):
        """Missing credential errors should be classified."""
        assert classify_conflict_repair_failure("missing credentials") == "missing_credentials"
        assert classify_conflict_repair_failure("no api key") == "missing_credentials"

    def test_invalid_model_detected(self):
        """Invalid model errors should be classified."""
        assert classify_conflict_repair_failure("invalid model") == "invalid_model"
        assert classify_conflict_repair_failure("model not found") == "invalid_model"

    def test_unclassifiable_error_returns_none(self):
        """Errors that don't match any pattern return None."""
        assert classify_conflict_repair_failure("some random error") is None
        assert classify_conflict_repair_failure("") is None
        assert classify_conflict_repair_failure(None) is None


class TestIntegrationRecordBackoffTracking:
    """Test integration record backoff and repair failure tracking."""

    def test_integration_record_with_backoff_until(self):
        """IntegrationRecord should support backoff_until field."""
        now = datetime.now(timezone.utc)
        backoff_time = now + timedelta(minutes=5)
        
        record = IntegrationRecord(
            state="ready",
            task_branch="task-1",
            base_branch="epic-1",
            attempts=1,
            backoff_until=backoff_time.isoformat(),
            repair_failure_reason="auth_failed",
        )
        
        # Round-trip through dict
        roundtrip = IntegrationRecord.from_dict(record.to_dict())
        assert roundtrip.backoff_until == backoff_time.isoformat()
        assert roundtrip.repair_failure_reason == "auth_failed"

    def test_integration_record_needs_human_state(self):
        """IntegrationRecord should support 'needs_human' state."""
        record = IntegrationRecord(
            state="needs_human",
            task_branch="task-1",
            base_branch="epic-1",
            repair_failure_reason="timeout",
        )
        
        # Should validate without error
        assert record.state == "needs_human"
        
        # Round-trip should work
        roundtrip = IntegrationRecord.from_dict(record.to_dict())
        assert roundtrip.state == "needs_human"

    def test_integration_record_preserves_repair_metadata(self):
        """IntegrationRecord should preserve both backoff and repair data."""
        record = IntegrationRecord(
            state="ready",
            task_branch="task-1",
            base_branch="epic-1",
            attempts=2,
            last_error="503 Provider Overloaded",
            backoff_until="2026-07-30T15:45:00Z",
            repair_failure_reason="overloaded",
        )
        
        data = record.to_dict()
        assert data["last_error"] == "503 Provider Overloaded"
        assert data["backoff_until"] == "2026-07-30T15:45:00Z"
        assert data["repair_failure_reason"] == "overloaded"


class TestIntegrationRecordVersionMigration:
    """Test that old v1 records are compatible with v2."""

    def test_v1_record_loads_as_v2(self):
        """Old v1 integration records should load and migrate to v2."""
        v1_data = {
            "version": 1,
            "state": "blocked",
            "task_branch": "task-1",
            "base_branch": "epic-1",
            "attempts": 1,
            "last_error": "merge conflict",
        }
        
        # v1 records load and are upgraded to v2
        record = IntegrationRecord.from_dict(v1_data)
        assert record.state == "blocked"
        assert record.backoff_until is None
        assert record.repair_failure_reason is None
        # Stored record should be version 2
        assert record.version == 2
        
        # Round-tripped v1 data is now v2
        assert record.to_dict()["version"] == 2

    def test_v2_record_rejects_unknown_future_versions(self):
        """v2 should reject records from future versions beyond 2."""
        v3_data = {
            "version": 3,
            "state": "ready",
            "task_branch": "task-1",
            "backoff_until": "2026-07-30T15:45:00Z",
        }
        
        # Should reject unsupported future version (requires migration code)
        from oompah.integration import parse_integration_record
        record = parse_integration_record(v3_data)
        assert record is None
