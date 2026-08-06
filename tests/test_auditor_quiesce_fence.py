"""Tests for auditor dispatch fencing during quiesce (OOMPAH-854).

Verifies that the terminal-audit scheduler respects quiesce state and does not
spawn new auditor provider processes during graceful restart drain.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from oompah.auditor_dispatch import AuditorDispatchLane, AuditDispatchPlan
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.roles import Candidate
from oompah.statuses import IN_VALIDATION
from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)


def _orchestrator(tmp_path) -> Orchestrator:
    """Create a minimal orchestrator for testing."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _audit_record(audit_id: str = "audit-1", state: RequestState = RequestState.PENDING) -> TerminalAuditRecord:
    """Create a minimal audit record for testing."""
    # Use a valid SHA-256 hash (64 hex characters)
    valid_hash = "a" * 64
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-1",
        task_id="OOMPAH-854",
        request_state=state,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(valid_hash),
        attempts=[],
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _audit_plan(audit_id: str = "audit-1") -> AuditDispatchPlan:
    """Create a minimal audit dispatch plan for testing."""
    # Use a valid SHA-256 hash (64 hex characters)
    valid_hash = "a" * 64
    return AuditDispatchPlan(
        audit_id=audit_id,
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(valid_hash),
        candidate=Candidate(provider_id="provider-1", model="model-1"),
        rotation_count=0,
        branch_key="epic-branch",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _issue(identifier: str = "OOMPAH-854") -> Issue:
    """Create a minimal issue for testing."""
    return Issue(
        id="issue-1",
        identifier=identifier,
        title="Test auditor dispatch",
        description="Testing quiesce fence",
        state=IN_VALIDATION,
        project_id="project-1",
        branch_name="epic-branch",
    )


class TestAuditorQuiesceFence:
    """Verify auditor dispatch respects quiesce state (OOMPAH-854)."""

    def test_dispatch_blocked_by_quiesce(self, tmp_path):
        """Verify _dispatch_is_blocked() returns True when quiesced."""
        orch = _orchestrator(tmp_path)
        assert orch._dispatch_is_blocked() is False
        orch.quiesce()
        assert orch._dispatch_is_blocked() is True

    def test_dispatch_aborts_auditor_on_quiesce_fence(self, tmp_path):
        """Verify auditor dispatch aborts if quiesce is set before provider spawn."""
        orch = _orchestrator(tmp_path)
        issue = _issue()
        auditor_plan = _audit_plan()
        
        # Simulate dispatch being called while not quiesced, then quiesce before
        # the final fence check
        async def dispatch_with_quiesce():
            # Mock the intermediate async operations
            with patch.object(orch, "_tracker_for_issue") as mock_tracker:
                mock_tracker_inst = MagicMock()
                mock_tracker_inst.fetch_issue_states_by_ids = MagicMock(
                    return_value=[issue]
                )
                mock_tracker_inst.get_metadata = MagicMock(return_value={})
                mock_tracker.return_value = mock_tracker_inst
                
                with patch.object(orch, "_match_agent_profile") as mock_profile:
                    mock_profile_inst = MagicMock()
                    mock_profile_inst.name = "auditor"
                    mock_profile.return_value = mock_profile_inst
                    
                    with patch.object(orch, "_run_worker", new_callable=AsyncMock):
                        # Set up the running entry to track if worker was registered
                        initial_running_count = len(orch.state.running)
                        
                        # Manually set up for dispatch (skip early checks)
                        orch.state.claimed.add(issue.id)
                        orch.state.claimed_issues[issue.id] = issue
                        
                        # Quiesce right before the dispatch would execute
                        orch.quiesce()
                        
                        # This should be a no-op, but let's verify by calling
                        # _dispatch with auditor_plan
                        await orch._dispatch(issue, attempt=0, auditor_plan=auditor_plan)
                        
                        # Verify the running entry was NOT created
                        assert len(orch.state.running) == initial_running_count
                        assert issue.id not in orch.state.running
                        assert issue.id not in orch.state.claimed

        asyncio.run(dispatch_with_quiesce())

    def test_auditor_branch_claim_released_on_quiesce_abort(self, tmp_path):
        """Verify audit branch claim is released when dispatch aborts due to quiesce."""
        orch = _orchestrator(tmp_path)
        issue = _issue()
        auditor_plan = _audit_plan()
        branch_key = auditor_plan.branch_key
        
        async def dispatch_releases_branch_claim():
            with patch.object(orch, "_tracker_for_issue") as mock_tracker:
                mock_tracker_inst = MagicMock()
                mock_tracker_inst.fetch_issue_states_by_ids = MagicMock(
                    return_value=[issue]
                )
                mock_tracker_inst.get_metadata = MagicMock(return_value={})
                mock_tracker.return_value = mock_tracker_inst
                
                with patch.object(orch, "_match_agent_profile") as mock_profile:
                    mock_profile_inst = MagicMock()
                    mock_profile_inst.name = "auditor"
                    mock_profile.return_value = mock_profile_inst
                    
                    with patch.object(orch, "_run_worker", new_callable=AsyncMock):
                        # Set audit branch claim
                        orch._audit_branch_claims[branch_key] = auditor_plan.attempt_id
                        
                        # Set up for dispatch
                        orch.state.claimed.add(issue.id)
                        orch.state.claimed_issues[issue.id] = issue
                        
                        # Quiesce before final fence
                        orch.quiesce()
                        
                        # Dispatch should clean up
                        await orch._dispatch(issue, attempt=0, auditor_plan=auditor_plan)
                        
                        # Verify branch claim was released
                        assert orch._audit_branch_claims.get(branch_key) is None
        
        asyncio.run(dispatch_releases_branch_claim())

    def test_dispatch_proceeds_when_not_quiesced(self, tmp_path):
        """Verify normal dispatch proceeds when orchestrator is not quiesced."""
        orch = _orchestrator(tmp_path)
        issue = _issue()
        auditor_plan = _audit_plan()
        
        async def normal_dispatch():
            with patch.object(orch, "_tracker_for_issue") as mock_tracker:
                mock_tracker_inst = MagicMock()
                mock_tracker_inst.fetch_issue_states_by_ids = MagicMock(
                    return_value=[issue]
                )
                mock_tracker_inst.get_metadata = MagicMock(return_value={})
                mock_tracker.return_value = mock_tracker_inst
                
                with patch.object(orch, "_match_agent_profile") as mock_profile:
                    mock_profile_inst = MagicMock()
                    mock_profile_inst.name = "auditor"
                    mock_profile.return_value = mock_profile_inst
                    
                    with patch.object(orch, "_run_worker", new_callable=AsyncMock):
                        with patch.object(orch, "_register_running_entry"):
                            # Set up for dispatch
                            orch.state.claimed.add(issue.id)
                            orch.state.claimed_issues[issue.id] = issue
                            
                            # Ensure not quiesced
                            assert orch._dispatch_is_blocked() is False
                            
                            # Dispatch should proceed
                            await orch._dispatch(issue, attempt=0, auditor_plan=auditor_plan)
                            
                            # Verify _register_running_entry was called (indicates dispatch proceeded)
                            orch._register_running_entry.assert_called_once()
        
        asyncio.run(normal_dispatch())


class TestAuditorQuiesceRecovery:
    """Verify queued audits are recovered correctly after quiesce abort."""

    def test_persisted_audit_plan_remains_in_progress(self, tmp_path):
        """Verify audit plan persisted before quiesce abort remains in IN_PROGRESS state."""
        # This test verifies that when a plan is persisted to durable storage
        # and then dispatch is aborted due to quiesce, the attempt stays IN_PROGRESS
        # in storage until the next scan recovers it as abandoned.
        
        record = _audit_record()
        plan = _audit_plan()
        
        # Persist the plan
        lane = AuditorDispatchLane(MagicMock())
        persisted = lane.persist_plan(record, plan)
        
        # Verify it's IN_PROGRESS after persist
        assert persisted.request_state == RequestState.IN_PROGRESS
        assert len(persisted.attempts) == 1
        assert persisted.attempts[0].request_state == RequestState.IN_PROGRESS

    def test_abandoned_attempt_recovered_as_pending(self, tmp_path):
        """Verify abandoned in-progress attempt is recovered as PENDING."""
        # When an attempt is IN_PROGRESS but has no active worker,
        # recovery should mark it as PENDING for retry
        
        record = _audit_record()
        plan = _audit_plan()
        
        lane = AuditorDispatchLane(MagicMock())
        persisted = lane.persist_plan(record, plan)
        
        # Simulate the attempt being IN_PROGRESS but having no active worker
        active_attempt_ids = set()  # Empty - no active workers
        
        recovery = lane.recover(persisted, active_attempt_ids=active_attempt_ids)
        
        # Verify it's marked as ready for retry
        assert recovery.ready is True
        assert recovery.record.request_state == RequestState.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
