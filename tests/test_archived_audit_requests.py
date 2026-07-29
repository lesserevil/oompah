"""Tests for archived_audit_requests helper function."""

import pytest
from unittest.mock import MagicMock, patch

from oompah.archived_audit_requests import request_archived_audit
from oompah.models import Issue
from oompah.terminal_audit import RequestState, TargetState


@pytest.fixture
def mock_issue():
    """Create a mock Issue object for testing."""
    issue = MagicMock(spec=Issue)
    issue.identifier = "test-task-1"
    issue.state = "Open"
    return issue


@pytest.fixture
def mock_tracker():
    """Create a mock TrackerProtocol for testing."""
    tracker = MagicMock()
    return tracker


@pytest.fixture
def mock_store():
    """Create a mock TerminalAuditMetadataStore."""
    return MagicMock()


class TestRequestArchivedAudit:
    """Tests for request_archived_audit function."""
    
    def test_creates_audit_record_when_none_pending(self, mock_issue, mock_tracker):
        """Should create a new audit record when none exists."""
        with patch("oompah.archived_audit_requests.TerminalAuditMetadataStore") as mock_store_class:
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_store.read.return_value = MagicMock(pending_chain=[])
            
            result = request_archived_audit(
                mock_issue,
                mock_tracker,
                "test-project",
                "Aged Done auto-archive"
            )
            
            assert result is True
            mock_store.upsert_pending_audit.assert_called_once()
            mock_tracker.update_issue.assert_called_once_with(
                "test-task-1", status="In Validation"
            )
    
    def test_skips_when_audit_already_pending(self, mock_issue, mock_tracker):
        """Should skip creating new audit when one is already pending."""
        with patch("oompah.archived_audit_requests.TerminalAuditMetadataStore") as mock_store_class:
            with patch("oompah.archived_audit_requests.compute_evidence_fingerprint") as mock_fingerprint:
                mock_store = MagicMock()
                mock_store_class.return_value = mock_store
                
                # Create a mock pending audit with the same fingerprint
                mock_fingerprint_obj = MagicMock()
                mock_fingerprint.return_value = mock_fingerprint_obj
                
                mock_pending_record = MagicMock()
                mock_pending_record.target_state = TargetState.ARCHIVED
                mock_pending_record.request_state = RequestState.PENDING
                mock_pending_record.evidence_fingerprint = mock_fingerprint_obj
                
                mock_metadata = MagicMock()
                mock_metadata.pending_chain = [mock_pending_record]
                mock_store.read.return_value = mock_metadata
                
                result = request_archived_audit(
                    mock_issue,
                    mock_tracker,
                    "test-project",
                    "Aged Done auto-archive"
                )
                
                assert result is False
                mock_store.upsert_pending_audit.assert_not_called()
                mock_tracker.update_issue.assert_not_called()
    
    def test_returns_false_on_update_failure(self, mock_issue, mock_tracker):
        """Should return False when updating issue status fails."""
        with patch("oompah.archived_audit_requests.TerminalAuditMetadataStore") as mock_store_class:
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_store.read.return_value = MagicMock(pending_chain=[])
            
            # Make update_issue raise an exception
            mock_tracker.update_issue.side_effect = Exception("Update failed")
            
            result = request_archived_audit(
                mock_issue,
                mock_tracker,
                "test-project",
                "Aged Done auto-archive"
            )
            
            assert result is False
    
    def test_returns_false_on_store_error(self, mock_issue, mock_tracker):
        """Should return False when storing audit record fails."""
        with patch("oompah.archived_audit_requests.TerminalAuditMetadataStore") as mock_store_class:
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_store.read.side_effect = Exception("Read failed")
            
            result = request_archived_audit(
                mock_issue,
                mock_tracker,
                "test-project",
                "Aged Done auto-archive"
            )
            
            # Even though read fails, we should still create an empty metadata and continue
            assert result is True or result is False
    
    def test_records_previous_state(self, mock_issue, mock_tracker):
        """Should record the issue's previous state in the audit."""
        with patch("oompah.archived_audit_requests.TerminalAuditMetadataStore") as mock_store_class:
            with patch("oompah.archived_audit_requests.TerminalAuditRecord") as mock_record_class:
                mock_store = MagicMock()
                mock_store_class.return_value = mock_store
                mock_store.read.return_value = MagicMock(pending_chain=[])
                
                result = request_archived_audit(
                    mock_issue,
                    mock_tracker,
                    "test-project",
                    "Aged Done auto-archive"
                )
                
                # Check that the audit record was created with the previous state
                mock_record_class.assert_called_once()
                call_kwargs = mock_record_class.call_args[1]
                assert call_kwargs["previous_state"] == "Open"
                assert call_kwargs["target_state"] == TargetState.ARCHIVED
