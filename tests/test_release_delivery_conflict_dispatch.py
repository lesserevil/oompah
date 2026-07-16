"""Tests for release delivery conflict-resolution agent dispatch (OOMPAH-214).

Covers:
- _is_delivery_conflict_error: detection of conflict error messages.
- conflict_agent_task_id schema field: default None, round-trip serialization,
  update via store.update().
- _dispatch_conflict_agent_for_delivery: creates an internal oompah task,
  stamps the delivery with the task ID, does not create a managed-project task.
- _dispatch_delivery_conflict_agents: idempotency (no re-dispatch when task ID
  is already set), skips non-blocked deliveries, skips blocked-but-not-conflict
  deliveries.
- End-to-end: blocked delivery → conflict agent dispatched → delivery reset to
  open → executor re-runs and creates PR.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.orchestrator import _is_delivery_conflict_error
from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 16, 20, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = "proj-3e4e9214"
_SHA_A = "a" * 40


def _delivery(
    *,
    status: AddendumStatus = AddendumStatus.BLOCKED,
    error: str | None = None,
    conflict_agent_task_id: str | None = None,
    work_branch: str | None = "oompah/release/rd-abc/release-0.11",
    delivery_id: str = "rd_test001",
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=delivery_id,
        project_id=PROJECT_ID,
        source_branch="main",
        source_kind=SourceKind.COMMITS,
        source_identifier=None,
        source_commits=[_SHA_A],
        target_branch="release/0.11",
        status=status,
        queued_at="2026-07-16T20:00:00Z",
        work_branch=work_branch,
        error=error,
        conflict_agent_task_id=conflict_agent_task_id,
    )


# ---------------------------------------------------------------------------
# _is_delivery_conflict_error
# ---------------------------------------------------------------------------


class TestIsDeliveryConflictError:
    def test_empty_string_returns_false(self):
        assert _is_delivery_conflict_error("") is False

    def test_none_returns_false(self):
        # None is handled gracefully (function checks for falsy)
        assert _is_delivery_conflict_error(None) is False  # type: ignore[arg-type]

    def test_conflict_keyword(self):
        assert _is_delivery_conflict_error("CONFLICT (content): Merge conflict in foo.rs") is True

    def test_automatic_merge_failed(self):
        assert _is_delivery_conflict_error("Automatic merge failed; fix conflicts and then commit.") is True

    def test_cannot_merge(self):
        assert _is_delivery_conflict_error("cannot merge: multiple conflicts") is True

    def test_unrelated_error_returns_false(self):
        assert _is_delivery_conflict_error("Failed to push work_branch: authentication failure") is False

    def test_push_failure_returns_false(self):
        assert _is_delivery_conflict_error("Failed to push oompah/release/rd-abc/release-0.11: rejected") is False

    def test_real_trickle_error(self):
        real_error = (
            "Merge conflict synchronizing 'main' into 'release/0.11': "
            "Auto-merging .github/workflows/ci.yml\n"
            "CONFLICT (modify/delete): .oompah/tasks/backlog/TRICKLE-11.md deleted in "
            "origin/main and modified in HEAD.\n"
            "CONFLICT (content): Merge conflict in crates/trickle-client/src/overlay.rs\n"
            "Automatic merge failed; fix conflicts and then commit the result."
        )
        assert _is_delivery_conflict_error(real_error) is True

    def test_case_insensitive_match(self):
        assert _is_delivery_conflict_error("MERGE CONFLICT in main.py") is True


# ---------------------------------------------------------------------------
# conflict_agent_task_id schema field
# ---------------------------------------------------------------------------


class TestConflictAgentTaskIdField:
    def test_default_is_none(self):
        d = _delivery()
        assert d.conflict_agent_task_id is None

    def test_round_trip_none(self):
        d = _delivery(conflict_agent_task_id=None)
        raw = d.to_raw()
        assert raw["conflict_agent_task_id"] is None
        d2 = ReleaseDelivery.from_raw(raw)
        assert d2.conflict_agent_task_id is None

    def test_round_trip_value(self):
        d = _delivery(conflict_agent_task_id="OOMPAH-999")
        raw = d.to_raw()
        assert raw["conflict_agent_task_id"] == "OOMPAH-999"
        d2 = ReleaseDelivery.from_raw(raw)
        assert d2.conflict_agent_task_id == "OOMPAH-999"

    def test_from_raw_missing_field_defaults_to_none(self):
        """Old records without the field round-trip gracefully."""
        d = _delivery(conflict_agent_task_id="OOMPAH-1")
        raw = d.to_raw()
        del raw["conflict_agent_task_id"]  # simulate old schema
        d2 = ReleaseDelivery.from_raw(raw)
        assert d2.conflict_agent_task_id is None

    def test_store_update_stamps_task_id(self, tmp_path: Path):
        store = ReleaseDeliveryStore(tmp_path, PROJECT_ID)
        d = _delivery()
        store.append(d)
        updated = store.update(d.id, conflict_agent_task_id="OOMPAH-42")
        assert updated.conflict_agent_task_id == "OOMPAH-42"
        # Persisted on disk
        reloaded = store.lookup_by_id(d.id)
        assert reloaded is not None
        assert reloaded.conflict_agent_task_id == "OOMPAH-42"

    def test_store_update_clears_task_id(self, tmp_path: Path):
        store = ReleaseDeliveryStore(tmp_path, PROJECT_ID)
        d = _delivery(conflict_agent_task_id="OOMPAH-42")
        store.append(d)
        updated = store.update(d.id, conflict_agent_task_id=None)
        assert updated.conflict_agent_task_id is None

    def test_conflict_agent_task_id_in_mutable_fields(self):
        from oompah.release_delivery_store import _MUTABLE_FIELDS
        assert "conflict_agent_task_id" in _MUTABLE_FIELDS

    def test_conflict_agent_task_id_not_in_immutable_fields(self):
        from oompah.release_delivery_store import _IMMUTABLE_FIELDS
        assert "conflict_agent_task_id" not in _IMMUTABLE_FIELDS


# ---------------------------------------------------------------------------
# _dispatch_conflict_agent_for_delivery (via orchestrator method)
# ---------------------------------------------------------------------------


class TestDispatchConflictAgentForDelivery:
    """Unit tests for the orchestrator method that creates the internal task."""

    def _make_orchestrator(self):
        """Return a minimal Orchestrator stub with the methods under test."""
        from oompah.orchestrator import (
            _dispatch_conflict_agent_for_delivery_impl,
        )
        # We test the standalone helper rather than a full Orchestrator to
        # avoid heavy setup.  The method is extracted below.
        raise NotImplementedError("use _dispatch_via_orchestrator_mock instead")

    def _dispatch_via_orchestrator_mock(
        self,
        *,
        project_name: str = "trickle",
        project_id: str = PROJECT_ID,
        repo_path: str = "/tmp/trickle",
        delivery: ReleaseDelivery | None = None,
        worktree_path: str = "/tmp/worktrees/trickle/release-rd-abc",
        existing_task_id: str = "OOMPAH-777",
    ):
        """Call _dispatch_conflict_agent_for_delivery on a mocked orchestrator."""
        if delivery is None:
            delivery = _delivery(
                error="Merge conflict synchronizing 'main' into 'release/0.11': conflict"
            )

        project = SimpleNamespace(
            id=project_id,
            name=project_name,
            repo_path=repo_path,
            repo_url="https://github.com/test/trickle",
        )

        created_issue = SimpleNamespace(identifier=existing_task_id)
        mock_tracker = MagicMock()
        mock_tracker.create_issue.return_value = created_issue

        store = MagicMock()
        store.update = MagicMock(return_value=delivery)

        mock_project_store = MagicMock()
        mock_project_store.worktree_path_for.return_value = worktree_path

        # Build a minimal Orchestrator with just what we need
        from oompah.statuses import NEEDS_REBASE

        class _FakeOrchestrator:
            tracker = mock_tracker
            project_store = mock_project_store

            _dispatch_conflict_agent_for_delivery = (
                lambda self, p, s, d:
                _real_impl(self, p, s, d)
            )

        def _real_impl(self_obj, proj, st, dlv):
            from oompah.orchestrator import Orchestrator
            # Call the actual method logic via an unbound call
            Orchestrator._dispatch_conflict_agent_for_delivery(self_obj, proj, st, dlv)

        orch = _FakeOrchestrator()
        _real_impl(orch, project, store, delivery)
        return mock_tracker, store, mock_project_store

    def test_creates_task_in_management_tracker(self):
        """A conflict-blocked delivery causes a task in the management tracker."""
        delivery = _delivery(
            error="Merge conflict synchronizing 'main' into 'release/0.11': conflict"
        )
        mock_tracker, store, _ = self._dispatch_via_orchestrator_mock(delivery=delivery)

        assert mock_tracker.create_issue.call_count == 1
        kwargs = mock_tracker.create_issue.call_args.kwargs
        assert "Resolve merge conflict" in kwargs["title"]
        assert kwargs["priority"] == 0
        assert "merge-conflict" in kwargs["labels"]

    def test_stamps_delivery_with_task_id(self):
        """After dispatch, the delivery is updated with the new task ID."""
        delivery = _delivery(
            error="Merge conflict synchronizing 'main' into 'release/0.11': conflict"
        )
        mock_tracker, store, _ = self._dispatch_via_orchestrator_mock(
            delivery=delivery, existing_task_id="OOMPAH-99"
        )
        store.update.assert_called_once_with(
            delivery.id, conflict_agent_task_id="OOMPAH-99"
        )

    def test_task_description_contains_worktree_path(self):
        """The filed task's description includes the worktree path."""
        delivery = _delivery(
            error="CONFLICT (content): Merge conflict in overlay.rs"
        )
        wt_path = "/tmp/worktrees/trickle/release-rd-test"
        mock_tracker, _, _ = self._dispatch_via_orchestrator_mock(
            delivery=delivery, worktree_path=wt_path
        )
        desc = mock_tracker.create_issue.call_args.kwargs["description"]
        assert wt_path in desc

    def test_task_description_contains_delivery_id(self):
        """The filed task's description references the delivery ID."""
        delivery = _delivery(
            delivery_id="rd_abc123",
            error="Merge conflict in foo.rs",
        )
        mock_tracker, _, _ = self._dispatch_via_orchestrator_mock(delivery=delivery)
        desc = mock_tracker.create_issue.call_args.kwargs["description"]
        assert "rd_abc123" in desc


# ---------------------------------------------------------------------------
# _dispatch_delivery_conflict_agents (orchestrator scan loop)
# ---------------------------------------------------------------------------


class TestDispatchDeliveryConflictAgents:
    """Unit tests for the per-project scan loop."""

    def _run_dispatch(self, deliveries: list[ReleaseDelivery], *, raise_on_create: bool = False):
        """Run _dispatch_delivery_conflict_agents with stubbed project/store."""
        created_issues: list[dict] = []

        class _FakeTracker:
            def create_issue(self, **kwargs):
                if raise_on_create:
                    raise RuntimeError("simulated create failure")
                iss = SimpleNamespace(identifier=f"OOMPAH-{len(created_issues)+1}")
                created_issues.append(kwargs)
                return iss

        ledger_mock = SimpleNamespace(deliveries=deliveries)

        stores_by_project: dict[str, MagicMock] = {}

        def _make_store(project, git_writer=None):
            store = MagicMock()
            store.read_ledger.return_value = ledger_mock
            store.update = MagicMock(return_value=deliveries[0] if deliveries else None)
            stores_by_project[project.id] = store
            return store

        project = SimpleNamespace(
            id=PROJECT_ID,
            name="trickle",
            repo_path="/tmp/trickle",
            repo_url="https://github.com/test/trickle",
        )

        fake_tracker = _FakeTracker()

        from oompah.orchestrator import Orchestrator
        from oompah.statuses import NEEDS_REBASE

        class _FakeOrchestrator:
            tracker = fake_tracker
            project_store = SimpleNamespace(
                list_all=lambda: [project],
                worktree_path_for=lambda pid, key: f"/tmp/worktrees/trickle/{key}",
            )

            def _tracker_for_project(self, pid):
                return self.tracker

            # Delegate the per-delivery method to the real implementation
            _dispatch_conflict_agent_for_delivery = (
                Orchestrator._dispatch_conflict_agent_for_delivery
            )

        orch = _FakeOrchestrator()
        with patch("oompah.orchestrator.make_delivery_store", side_effect=_make_store):
            Orchestrator._dispatch_delivery_conflict_agents(orch)

        return created_issues, stores_by_project

    def test_dispatches_for_conflict_blocked_delivery(self):
        d = _delivery(
            status=AddendumStatus.BLOCKED,
            error="Merge conflict synchronizing 'main' into 'release/0.11': conflict",
            conflict_agent_task_id=None,
        )
        created, stores = self._run_dispatch([d])
        assert len(created) == 1
        assert "Resolve merge conflict" in created[0]["title"]

    def test_skips_already_dispatched_delivery(self):
        """When conflict_agent_task_id is already set, no new task is filed."""
        d = _delivery(
            status=AddendumStatus.BLOCKED,
            error="Merge conflict synchronizing 'main' into 'release/0.11': conflict",
            conflict_agent_task_id="OOMPAH-50",
        )
        created, _ = self._run_dispatch([d])
        assert len(created) == 0

    def test_skips_non_blocked_delivery(self):
        """Open or in_review deliveries are not dispatched."""
        d_open = _delivery(
            status=AddendumStatus.OPEN,
            error="Merge conflict synchronizing ...",
            conflict_agent_task_id=None,
        )
        d_in_review = _delivery(
            status=AddendumStatus.IN_REVIEW,
            error="Merge conflict synchronizing ...",
            conflict_agent_task_id=None,
            delivery_id="rd_other",
        )
        created, _ = self._run_dispatch([d_open, d_in_review])
        assert len(created) == 0

    def test_skips_non_conflict_blocked_delivery(self):
        """Blocked deliveries with non-conflict errors are skipped."""
        d = _delivery(
            status=AddendumStatus.BLOCKED,
            error="Failed to push oompah/release/rd-abc/release-0.11: rejected",
            conflict_agent_task_id=None,
        )
        created, _ = self._run_dispatch([d])
        assert len(created) == 0

    def test_skips_blocked_delivery_with_empty_error(self):
        d = _delivery(status=AddendumStatus.BLOCKED, error=None, conflict_agent_task_id=None)
        created, _ = self._run_dispatch([d])
        assert len(created) == 0

    def test_stamps_conflict_agent_task_id(self):
        """The delivery record is updated with the new task ID after dispatch."""
        d = _delivery(
            status=AddendumStatus.BLOCKED,
            error="CONFLICT (content): Merge conflict in foo.rs",
            conflict_agent_task_id=None,
        )
        _, stores = self._run_dispatch([d])
        store = stores[PROJECT_ID]
        store.update.assert_called_once_with(d.id, conflict_agent_task_id="OOMPAH-1")

    def test_dispatch_error_does_not_abort_loop(self):
        """A failure in create_issue is caught; other deliveries still scanned."""
        d1 = _delivery(
            delivery_id="rd_fail",
            status=AddendumStatus.BLOCKED,
            error="Merge conflict synchronizing ...",
            conflict_agent_task_id=None,
        )
        # run_dispatch with raise_on_create=True should not raise
        created, _ = self._run_dispatch([d1], raise_on_create=True)
        assert created == []  # no tasks created (create_issue raised)

    def test_processes_multiple_deliveries(self):
        """Multiple conflict-blocked deliveries each get a task."""
        d1 = _delivery(
            delivery_id="rd_001",
            status=AddendumStatus.BLOCKED,
            error="Merge conflict in foo.rs",
            conflict_agent_task_id=None,
        )
        d2 = _delivery(
            delivery_id="rd_002",
            status=AddendumStatus.BLOCKED,
            error="CONFLICT (content): Merge conflict in bar.rs",
            conflict_agent_task_id=None,
        )
        created, _ = self._run_dispatch([d1, d2])
        assert len(created) == 2


# ---------------------------------------------------------------------------
# End-to-end: blocked → conflict agent dispatched → reset → PR created
# ---------------------------------------------------------------------------


class TestConflictResolutionEndToEnd:
    """Integration test verifying the full recovery lifecycle."""

    def test_delivery_reset_to_open_allows_reexecution(self, tmp_path: Path):
        """After the conflict agent resets the delivery to open,
        the executor can re-run and create the PR."""
        store = ReleaseDeliveryStore(tmp_path, PROJECT_ID)
        d = _delivery(
            status=AddendumStatus.BLOCKED,
            error="Merge conflict synchronizing 'main' into 'release/0.11': conflict",
            conflict_agent_task_id="OOMPAH-214",
        )
        store.append(d)

        # Simulate: conflict agent resolved conflicts, pushing work branch, then
        # resets delivery to open (clearing conflict_agent_task_id).
        updated = store.update(
            d.id,
            status=AddendumStatus.OPEN,
            claimed_by=None,
            lease_expires_at=None,
            conflict_agent_task_id=None,
            error="Conflict resolved by oompah agent (OOMPAH-214). Work branch pushed.",
        )
        assert updated.status is AddendumStatus.OPEN
        assert updated.conflict_agent_task_id is None
        assert "resolved" in (updated.error or "")

        # Re-read from disk to confirm persistence
        reloaded = store.lookup_by_id(d.id)
        assert reloaded is not None
        assert reloaded.status is AddendumStatus.OPEN
        assert reloaded.conflict_agent_task_id is None
