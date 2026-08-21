"""Regression tests for OOMPAH-1203: StateBranchFetchError handling in contributor evidence persistence.

When git fetch fails while persisting contributor evidence before provider launch,
the error must be logged at WARNING (not ERROR) so error_watcher is not triggered.

Root cause: _stage_work_contributor_launch caught all exceptions with a
catch-all handler that returned an error message, which was then converted to
ProviderStartupError and logged at ERROR level, triggering error_watcher.

Fix: Catch StateBranchFetchError specifically (a transient network error) and
log it at WARNING, then return None so the provider dispatch can proceed.
The background persistence task will retry its state-branch write naturally.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.models import AgentProfile, Issue, Provider
from oompah.orchestrator import Orchestrator, ProviderStartupError
from oompah.providers import ProviderStore
from oompah.tracker import StateBranchFetchError


def _make_orchestrator(tmp_path: Path) -> Orchestrator:
    """Create a minimal orchestrator for testing."""
    from oompah.agent_profile_store import AgentProfileStore
    from oompah.config import ServiceConfig
    from oompah.oompah_md_tracker import OompahMarkdownTracker
    from oompah.projects import ProjectStore
    from oompah.roles import RoleStore

    config = ServiceConfig()
    tracker = OompahMarkdownTracker(root_path=str(tmp_path / "repo"))
    provider_store = ProviderStore()
    project_store = ProjectStore()
    role_store = RoleStore(provider_store=provider_store)
    agent_profile_store = AgentProfileStore()

    orch = Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        provider_store=provider_store,
        project_store=project_store,
        agent_profile_store=agent_profile_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


def _make_issue(identifier: str, project_id: str | None = None) -> Issue:
    """Create a test issue."""
    return Issue(
        id="issue-1",
        identifier=identifier,
        title="Test issue",
        body="Test description",
        state="Open",
        authority="test-authority",
        project_id=project_id or "test-project",
    )


class TestStateBranchFetchErrorInContributorEvidence:
    """Verify StateBranchFetchError is handled gracefully during evidence persistence."""

    def test_state_branch_fetch_error_logs_warning_not_error(
        self, tmp_path: Path, caplog
    ) -> None:
        """StateBranchFetchError during evidence persistence must log at WARNING, not ERROR.

        This is the regression fix: when _persist_work_contributor raises
        StateBranchFetchError, the exception handler must catch it specifically
        and log at WARNING so error_watcher is not triggered.
        """
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("fetch-transient")
        orch.state.running[issue.id] = MagicMock(
            issue=issue,
            run_id="test-run",
            provider_id="test-provider",
            model="test-model",
        )

        # Mock _persist_work_contributor to raise StateBranchFetchError
        fetch_error = StateBranchFetchError(
            "Cannot sync state branch: git fetch origin failed: network unreachable"
        )
        orch._persist_work_contributor = MagicMock(side_effect=fetch_error)

        with caplog.at_level(logging.WARNING):
            error = asyncio.run(
                orch._stage_work_contributor_launch(
                    issue,
                    run_id="test-run",
                    provider_id="test-provider",
                    provider_name="Test Provider",
                    model="test-model",
                    focus="implementation",
                )
            )

        # The error should be None (graceful handling), not an error message
        assert error is None, "StateBranchFetchError should return None for graceful degradation"

        # Check that we logged at WARNING level with the fetch error
        warning_records = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and "contributor evidence persistence" in r.message
        ]
        assert warning_records, (
            "StateBranchFetchError must be logged at WARNING level. "
            "Got records: " + str([r.message for r in caplog.records])
        )

    def test_state_branch_fetch_error_does_not_raise_provider_startup_error(
        self, tmp_path: Path
    ) -> None:
        """When evidence persistence fails with StateBranchFetchError, provider dispatch should not raise.

        The caller of _stage_work_contributor_launch checks if the return value
        is not None before raising ProviderStartupError. When StateBranchFetchError
        occurs, we return None so the provider can proceed.
        """
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("fetch-allows-provider")
        orch.state.running[issue.id] = MagicMock(
            issue=issue,
            run_id="test-run",
            provider_id="test-provider",
            model="test-model",
        )

        # Mock _persist_work_contributor to raise StateBranchFetchError
        fetch_error = StateBranchFetchError("git fetch failed")
        orch._persist_work_contributor = MagicMock(side_effect=fetch_error)

        error = asyncio.run(
            orch._stage_work_contributor_launch(
                issue,
                run_id="test-run",
                provider_id="test-provider",
                provider_name="Test Provider",
                model="test-model",
                focus="implementation",
            )
        )

        # Returning None means the provider will proceed (caller won't raise ProviderStartupError)
        assert error is None

    def test_other_exceptions_still_raise_provider_startup_error(
        self, tmp_path: Path
    ) -> None:
        """Real errors (not StateBranchFetchError) should still cause ProviderStartupError.

        Only StateBranchFetchError is treated as transient/retryable. Other tracker
        errors should still be reported as provider startup failures.
        """
        from oompah.tracker import TrackerError

        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("tracker-error-fatal")
        orch.state.running[issue.id] = MagicMock(
            issue=issue,
            run_id="test-run",
            provider_id="test-provider",
            model="test-model",
        )

        # Mock _persist_work_contributor to raise a generic TrackerError
        real_error = TrackerError("Tracker write failed permanently")
        orch._persist_work_contributor = MagicMock(side_effect=real_error)

        error = asyncio.run(
            orch._stage_work_contributor_launch(
                issue,
                run_id="test-run",
                provider_id="test-provider",
                provider_name="Test Provider",
                model="test-model",
                focus="implementation",
            )
        )

        # Non-fetch errors should return an error message (will cause ProviderStartupError)
        assert error is not None, "Non-fetch TrackerError should return an error message"
        assert "TrackerError" in error or "Tracker" in error

    def test_state_branch_fetch_error_releases_budget_reservation(
        self, tmp_path: Path
    ) -> None:
        """When handling StateBranchFetchError, budget reservation must be released.

        If we reserved audit budget before persisting evidence failed, we need to
        release it so other workers can use it.
        """
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("fetch-release-budget")
        orch.state.running[issue.id] = MagicMock(
            issue=issue,
            run_id="test-run",
            provider_id="test-provider",
            model="test-model",
        )

        # Mock the budget reservation as being held
        orch._audit_budget_reservations["test-key"] = True
        orch._audit_reservation_key_for_issue = MagicMock(return_value="test-key")
        orch._release_audit_budget_reservation = MagicMock(return_value=True)

        # Mock _persist_work_contributor to raise StateBranchFetchError
        fetch_error = StateBranchFetchError("git fetch failed")
        orch._persist_work_contributor = MagicMock(side_effect=fetch_error)

        error = asyncio.run(
            orch._stage_work_contributor_launch(
                issue,
                run_id="test-run",
                provider_id="test-provider",
                provider_name="Test Provider",
                model="test-model",
                focus="implementation",
            )
        )

        # Should have called release_audit_budget_reservation
        assert orch._release_audit_budget_reservation.called or (
            "test-key" not in orch._audit_budget_reservations
        ), "Budget reservation should be released after StateBranchFetchError"

        # Error should be None (graceful handling)
        assert error is None
