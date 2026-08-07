"""Orchestrator-level integration tests for OOMPAH-871.

These cover the durable fence that keeps provenance-only terminal tasks
non-dispatchable across watchdog ticks, reconciliation sweeps, and
restart recovery.  Every path documented in the OOMPAH-871 acceptance
criteria is exercised end to end at the orchestrator boundary.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

import oompah.orchestrator as orchestrator_module
from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.provenance_suppression import (
    PROVENANCE_SUPPRESSION_KEY,
    ProvenanceGuardedTracker,
    authorize_new_revision,
    mark_provenance_only,
)
from oompah.scm import ReviewRequest
from oompah.statuses import MERGED, OPEN
from oompah.terminal_audit import ContributorIdentity
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadataStore,
)


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


class _LockStore:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def project_write_lock(self, project_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(project_id, threading.RLock())


class _MetadataTracker:
    """Minimal tracker double supporting the metadata API + a few methods."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._metadata: dict[str, dict[str, Any]] = {}
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.comments: list[tuple[str, str, str]] = []
        # Populated by tests to return from fetch methods.
        self.issues_by_state: dict[str, list[Issue]] = {}
        self.issue_details: dict[str, Issue] = {}

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        with self._guard:
            return copy.deepcopy(self._metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        with self._guard:
            payload = self._metadata.setdefault(identifier, {})
            payload[key] = copy.deepcopy(value)

    def fetch_issues_by_states(self, states: list[str]) -> list[Issue]:
        result: list[Issue] = []
        for state in states:
            result.extend(self.issues_by_state.get(state, []))
        return result

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issue_details.get(identifier)

    def update_issue(self, identifier: str, **fields: Any) -> None:
        self.updates.append((identifier, dict(fields)))

    def add_comment(self, identifier: str, body: str, *, author: str = "") -> None:
        self.comments.append((identifier, body, author))


def _make_project() -> Any:
    project = MagicMock()
    project.id = "proj-1"
    project.name = "proj"
    project.repo_url = "https://example.test/owner/repo"
    project.repo_path = "/tmp/repo"
    project.default_branch = "main"
    project.branches = ["main"]
    project.access_token = None
    project.merge_queue_enabled = False
    project.paused = False
    project.churn_magnet_gate_enabled = False
    project.churn_magnet_top_n = 10
    project.epic_strategy = "shared"
    return project


def _issue(identifier: str, state: str = OPEN, *, project_id: str = "proj-1") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Body long enough to pass the dispatch empty-description gate.",
        state=state,
        issue_type="task",
        project_id=project_id,
    )


def _make_orchestrator(tmp_path, tracker: _MetadataTracker) -> Orchestrator:
    project = _make_project()
    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda pid: project if pid == project.id else None

    def _project_write_lock(project_id: str) -> threading.RLock:
        return _lock_store.project_write_lock(project_id)

    _lock_store = _LockStore()
    project_store.project_write_lock = _project_write_lock

    orch = Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._project_trackers[project.id] = tracker  # type: ignore[assignment]
    return orch


def _owner() -> ContributorIdentity:
    return ContributorIdentity(identity="alice", source="github")


def test_managed_project_tracker_is_centrally_guarded(tmp_path, monkeypatch):
    tracker = _MetadataTracker()
    project = _make_project()
    project.tracker_kind = "provenance-test"
    monkeypatch.setitem(
        orchestrator_module.ADAPTER_REGISTRY,
        "provenance-test",
        lambda **_kwargs: tracker,
    )
    orch = _make_orchestrator(tmp_path, tracker)

    resolved = orch._new_tracker_for_project(project)

    assert isinstance(resolved, ProvenanceGuardedTracker)
    assert not hasattr(resolved, "wrapped_tracker")


def _seed_suppression(tracker: _MetadataTracker, identifier: str) -> None:
    store = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")
    mark_provenance_only(
        store,
        identifier,
        _owner(),
        "retained purely as terminal provenance for the merged record.",
        now=datetime(2026, 8, 7, tzinfo=timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Contract 1: watchdog ticks cannot reopen a provenance-only record
# ---------------------------------------------------------------------------


class TestTerminalOpenReviewReconciliationRespectsSuppression:
    def test_suppressed_merged_task_survives_repeated_ticks(self, tmp_path):
        tracker = _MetadataTracker()
        _seed_suppression(tracker, "TASK-576")

        orch = _make_orchestrator(tmp_path, tracker)
        orch._reviews_cache = {
            "proj-1": [
                ReviewRequest(
                    id="222",
                    title="PR #222",
                    url="https://example.test/pull/222",
                    author="alice",
                    state="open",
                    source_branch="TASK-576",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        orch._merged_branches = set()
        tracker.issues_by_state[MERGED] = [_issue("TASK-576", state=MERGED)]

        # A watchdog observes a stale open-review signal on the branch
        # associated with a Merged, provenance-only record.  Every tick
        # must leave the record untouched.
        for _ in range(3):
            orch._reconcile_terminal_open_reviews()

        assert tracker.updates == []
        assert tracker.comments == []

    def test_suppression_survives_service_restart(self, tmp_path):
        tracker = _MetadataTracker()
        _seed_suppression(tracker, "TASK-576")

        # First orchestrator instance runs a reconciliation tick.
        orch1 = _make_orchestrator(tmp_path, tracker)
        orch1._reviews_cache = {
            "proj-1": [
                ReviewRequest(
                    id="222",
                    title="PR #222",
                    url="https://example.test/pull/222",
                    author="alice",
                    state="open",
                    source_branch="TASK-576",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        tracker.issues_by_state[MERGED] = [_issue("TASK-576", state=MERGED)]
        orch1._reconcile_terminal_open_reviews()

        # Second orchestrator instance simulates a service restart on the
        # same durable tracker payload.
        orch2 = _make_orchestrator(tmp_path, tracker)
        orch2._reviews_cache = orch1._reviews_cache
        tracker.issues_by_state[MERGED] = [_issue("TASK-576", state=MERGED)]
        orch2._reconcile_terminal_open_reviews()

        assert tracker.updates == []


# ---------------------------------------------------------------------------
# Contract 2: owner-authorized new revision clears suppression
# ---------------------------------------------------------------------------


class TestAuthorizedRevisionEnablesDispatch:
    def test_new_revision_bumps_generation_and_permits_reopen(self, tmp_path):
        tracker = _MetadataTracker()
        _seed_suppression(tracker, "TASK-576")

        # Simulate an owner explicitly starting a new revision.
        store = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")
        outcome = authorize_new_revision(
            store,
            "TASK-576",
            _owner(),
            "reopened for follow-up work",
        )
        assert outcome.marker.authority_generation == 1
        assert outcome.marker.suppressed is False

        orch = _make_orchestrator(tmp_path, tracker)
        # Once the tracker has moved the task back to Open, `_should_dispatch`
        # must accept it.  Wire the minimal state that gate needs.
        issue = _issue("TASK-576", state=OPEN)
        status = orch._provenance_suppression_status(issue, "proj-1", tracker)
        assert status.suppressed is False
        assert status.authority_generation == 1


class TestDispatchFenceRefusesSuppressedRecord:
    def test_dispatch_rejects_provenance_suppressed_task(self, tmp_path):
        tracker = _MetadataTracker()
        _seed_suppression(tracker, "TASK-576")
        orch = _make_orchestrator(tmp_path, tracker)

        # A durable suppression marker forbids dispatch even for an Open
        # tracker state (e.g. an operator manually reopened the tracker
        # label without going through authorize_new_revision).
        issue = _issue("TASK-576", state=OPEN)
        assert orch._should_dispatch(issue) is False
        assert orch.state.reject_streak[issue.id][0] == "provenance_suppressed"

    def test_dispatch_permits_task_after_authorized_revision(self, tmp_path):
        tracker = _MetadataTracker()
        _seed_suppression(tracker, "TASK-576")
        orch = _make_orchestrator(tmp_path, tracker)

        # Owner authorizes a new revision, bumping the authority generation.
        store = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")
        authorize_new_revision(
            store, "TASK-576", _owner(), "starting a follow-up"
        )

        issue = _issue("TASK-576", state=OPEN)
        assert orch._should_dispatch(issue) is True


# ---------------------------------------------------------------------------
# Contract 3: stale branch or review observations cannot silently reopen
# ---------------------------------------------------------------------------


class TestStaleObservationsAreInert:
    def test_stale_in_review_reopen_is_refused(self, tmp_path):
        tracker = _MetadataTracker()
        _seed_suppression(tracker, "TASK-576")
        orch = _make_orchestrator(tmp_path, tracker)

        issue = _issue("TASK-576", state=MERGED)
        # A historical stale-review observation would otherwise call the
        # reopen helper.  The fence must reject it silently.
        orch._reopen_stale_in_review_task(
            tracker,
            issue,
            branch="TASK-576",
            target_branch="main",
            commits_ahead=1,
            commit_lines=["abc123 stale commit"],
            review=None,
        )

        assert tracker.updates == []
        assert tracker.comments == []


# ---------------------------------------------------------------------------
# Contract 4: malformed provenance metadata surfaces an alert without mutation
# ---------------------------------------------------------------------------


class TestMalformedMarkerAlertsWithoutMutation:
    def test_malformed_marker_does_not_reopen_or_mutate_status(self, tmp_path, caplog):
        tracker = _MetadataTracker()
        tracker._metadata["TASK-576"] = {
            METADATA_KEY: {
                "version": 1,
                "pending_chain": [],
                "attempt_history": [],
                PROVENANCE_SUPPRESSION_KEY: {"version": 99},  # malformed
            }
        }
        orch = _make_orchestrator(tmp_path, tracker)

        orch._reviews_cache = {
            "proj-1": [
                ReviewRequest(
                    id="222",
                    title="PR #222",
                    url="https://example.test/pull/222",
                    author="alice",
                    state="open",
                    source_branch="TASK-576",
                    target_branch="main",
                    created_at="2026-01-01",
                    updated_at="2026-01-01",
                )
            ]
        }
        tracker.issues_by_state[MERGED] = [_issue("TASK-576", state=MERGED)]

        with caplog.at_level("WARNING"):
            orch._reconcile_terminal_open_reviews()

        assert tracker.updates == []
        joined = "\n".join(caplog.messages)
        assert "provenance-suppression" in joined
        assert "TASK-576" in joined
