"""Tests for orchestrator conflict repair backoff and retry logic."""

from datetime import datetime, timedelta, timezone

from oompah.integration import IntegrationRecord
from oompah.models import Issue
from oompah.orchestrator import Orchestrator


class TestBackoffDetection:
    """Test the _is_integration_item_in_backoff method."""

    def _make_issue_with_backoff(self, backoff_until: str | None = None) -> Issue:
        """Create a test issue with optional backoff_until in integration metadata."""
        integration = IntegrationRecord(
            state="ready",
            task_branch="task-1",
            backoff_until=backoff_until,
        )
        issue = Issue(
            id="task-1",
            identifier="T-1",
            title="Test task",
        )
        # Manually set the integration field (normally set by tracker)
        object.__setattr__(issue, "integration", integration)
        return issue

    def test_no_backoff_when_no_integration_metadata(self):
        """Items without integration metadata should not be in backoff."""
        from oompah.orchestrator import Orchestrator
        from oompah.integration_queue import IntegrationQueueItem

        # Create a mock orchestrator (just need the method)
        orch = object.__new__(Orchestrator)
        
        item = IntegrationQueueItem(
            project_id="p1",
            epic_id="e1",
            task_id="t1",
            task_branch="br1",
            head_sha="abc123",
            base_sha=None,
            priority=0,
            submitted_at="2026-07-30T00:00:00Z",
            state="ready",
            attempts=1,
            lease_owner=None,
            lease_expires_at=None,
            updated_at="2026-07-30T00:00:00Z",
        )
        
        # Issue without integration metadata
        issue = Issue(id="t1", identifier="T-1", title="Test")
        
        # Should return False (no backoff)
        assert not orch._is_integration_item_in_backoff(item, issue)

    def test_no_backoff_when_no_backoff_until(self):
        """Items with integration but no backoff_until should not be in backoff."""
        from oompah.orchestrator import Orchestrator
        from oompah.integration_queue import IntegrationQueueItem

        orch = object.__new__(Orchestrator)
        
        item = IntegrationQueueItem(
            project_id="p1",
            epic_id="e1",
            task_id="t1",
            task_branch="br1",
            head_sha="abc123",
            base_sha=None,
            priority=0,
            submitted_at="2026-07-30T00:00:00Z",
            state="ready",
            attempts=1,
            lease_owner=None,
            lease_expires_at=None,
            updated_at="2026-07-30T00:00:00Z",
        )
        
        issue = self._make_issue_with_backoff(backoff_until=None)
        
        # Should return False (no backoff_until)
        assert not orch._is_integration_item_in_backoff(item, issue)

    def test_in_backoff_when_future_time(self):
        """Items with backoff_until in the future should be in backoff."""
        from oompah.orchestrator import Orchestrator
        from oompah.integration_queue import IntegrationQueueItem

        orch = object.__new__(Orchestrator)
        
        # Set backoff to 1 hour in the future
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        
        item = IntegrationQueueItem(
            project_id="p1",
            epic_id="e1",
            task_id="t1",
            task_branch="br1",
            head_sha="abc123",
            base_sha=None,
            priority=0,
            submitted_at="2026-07-30T00:00:00Z",
            state="ready",
            attempts=1,
            lease_owner=None,
            lease_expires_at=None,
            updated_at="2026-07-30T00:00:00Z",
        )
        
        issue = self._make_issue_with_backoff(backoff_until=future.isoformat())
        
        # Should return True (in backoff period)
        assert orch._is_integration_item_in_backoff(item, issue)

    def test_not_in_backoff_when_past_time(self):
        """Items with backoff_until in the past should not be in backoff."""
        from oompah.orchestrator import Orchestrator
        from oompah.integration_queue import IntegrationQueueItem

        orch = object.__new__(Orchestrator)
        
        # Set backoff to 1 hour in the past
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        
        item = IntegrationQueueItem(
            project_id="p1",
            epic_id="e1",
            task_id="t1",
            task_branch="br1",
            head_sha="abc123",
            base_sha=None,
            priority=0,
            submitted_at="2026-07-30T00:00:00Z",
            state="ready",
            attempts=1,
            lease_owner=None,
            lease_expires_at=None,
            updated_at="2026-07-30T00:00:00Z",
        )
        
        issue = self._make_issue_with_backoff(backoff_until=past.isoformat())
        
        # Should return False (backoff period expired)
        assert not orch._is_integration_item_in_backoff(item, issue)

    def test_invalid_timestamp_treated_as_no_backoff(self):
        """Items with invalid backoff_until timestamp should not be in backoff."""
        from oompah.orchestrator import Orchestrator
        from oompah.integration_queue import IntegrationQueueItem

        orch = object.__new__(Orchestrator)
        
        item = IntegrationQueueItem(
            project_id="p1",
            epic_id="e1",
            task_id="t1",
            task_branch="br1",
            head_sha="abc123",
            base_sha=None,
            priority=0,
            submitted_at="2026-07-30T00:00:00Z",
            state="ready",
            attempts=1,
            lease_owner=None,
            lease_expires_at=None,
            updated_at="2026-07-30T00:00:00Z",
        )
        
        issue = self._make_issue_with_backoff(backoff_until="not-a-valid-timestamp")
        
        # Should return False (invalid timestamp)
        assert not orch._is_integration_item_in_backoff(item, issue)
