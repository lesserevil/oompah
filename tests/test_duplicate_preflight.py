"""Scheduler and lifecycle tests for Open-task duplicate preflight."""

from __future__ import annotations

import asyncio
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.duplicate_screening import (
    DETECTOR_VERSION,
    METADATA_KEY,
    ScreeningState,
    ScreeningVerdict,
    assess_screening,
    complete_claim_record,
    new_claim_record,
)
from oompah.events import EventBus
from oompah.models import Issue, OrchestratorState, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.statuses import (
    DONE,
    DUPLICATE_CANDIDATE,
    NEEDS_HUMAN,
    OPEN,
)


def _issue(
    identifier: str = "TASK-1",
    *,
    title: str = "Implement unique behavior",
    state: str = OPEN,
    priority: int = 2,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="Detailed implementation scope and acceptance criteria.",
        state=state,
        issue_type="task",
        project_id="project-1",
        priority=priority,
        tracker_kind="test",
    )


class _Tracker:
    def __init__(self, issues: list[Issue]):
        self.issues = {issue.identifier: copy.deepcopy(issue) for issue in issues}
        self.metadata: dict[str, dict[str, object]] = {
            issue.identifier: {} for issue in issues
        }
        self.comments: dict[str, list[dict]] = {
            issue.identifier: [] for issue in issues
        }
        self.status_updates: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def invalidate_read_cache(self):
        return None

    def fetch_issue_detail(self, identifier: str):
        with self._lock:
            issue = self.issues.get(identifier)
            if issue is None:
                return None
            result = copy.deepcopy(issue)
            raw = self.metadata.get(identifier, {}).get(METADATA_KEY)
            result.duplicate_screening = copy.deepcopy(raw)
            return result

    def fetch_issue_states_by_ids(self, identifiers):
        results = []
        for identifier in identifiers:
            issue = self.fetch_issue_detail(identifier)
            if issue is not None:
                results.append(issue)
        return results

    def get_metadata(self, identifier: str):
        with self._lock:
            return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object):
        with self._lock:
            self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def remove_label(self, identifier: str, label: str):
        with self._lock:
            issue = self.issues[identifier]
            issue.labels = [
                current
                for current in issue.labels
                if current.lower() != label.lower()
            ]

    def add_label(self, identifier: str, label: str):
        with self._lock:
            issue = self.issues[identifier]
            if label not in issue.labels:
                issue.labels.append(label)

    def fetch_comments(self, identifier: str):
        with self._lock:
            return copy.deepcopy(self.comments.get(identifier, []))

    def add_comment(self, identifier: str, text: str, author: str = "oompah"):
        with self._lock:
            comment = {
                "text": text,
                "author": author,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.comments.setdefault(identifier, []).append(comment)
            return copy.deepcopy(comment)

    def update_issue(self, identifier: str, **fields):
        status = fields.get("status")
        if status is not None:
            with self._lock:
                self.issues[identifier].state = str(status)
                self.status_updates.append((identifier, str(status)))

    def mark_needs_human(
        self,
        identifier: str,
        comment: str,
        author: str = "oompah",
    ):
        self.add_comment(identifier, comment, author)
        self.update_issue(identifier, status=NEEDS_HUMAN)


def _orch(tracker: _Tracker, *, slots: int = 3, preflight_limit: int = 1):
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = ServiceConfig(
        max_concurrent_agents=slots,
        duplicate_preflight_max_agents=preflight_limit,
    )
    orch.state = OrchestratorState(max_concurrent_agents=slots)
    orch._service_instance_id = "scheduler-1"
    orch._epic_maintenance_project_locks = {}
    orch._tracker_for_issue = lambda issue: tracker
    orch._tracker_for_project = lambda project_id: tracker
    return orch


def _entry(issue: Issue, claim_id: str, fingerprint: str) -> RunningEntry:
    return RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        focus_name="duplicate_detector",
        focus_role="Duplicate Investigator",
        duplicate_preflight=True,
        duplicate_preflight_claim_id=claim_id,
        duplicate_preflight_fingerprint=fingerprint,
    )


def test_concurrent_claim_attempts_have_exactly_one_winner():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    barrier = threading.Barrier(2)
    winners = []

    def attempt():
        barrier.wait()
        winners.append(orch._claim_duplicate_preflight(issue))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(record is not None for record in winners) == 1
    stored = tracker.get_metadata(issue.identifier)[METADATA_KEY]
    assert stored["claim_id"]


def test_wrong_claim_cannot_clear_or_complete_replacement_claim():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    first = orch._claim_duplicate_preflight(issue)
    assert first is not None
    replacement = new_claim_record(issue, owner="scheduler-2")
    tracker.set_metadata_field(issue.identifier, METADATA_KEY, replacement.to_dict())

    assert (
        orch._clear_duplicate_preflight_claim(
            issue,
            first.claim_id or "",
            reason="late worker",
        )
        is False
    )
    result = orch._finish_duplicate_preflight_sync(
        _entry(issue, first.claim_id or "", first.task_fingerprint),
        "normal",
        None,
    )

    assert result["outcome"] == "stale_claim"
    assert (
        tracker.get_metadata(issue.identifier)[METADATA_KEY]["claim_id"]
        == replacement.claim_id
    )


def test_expired_claim_is_recovered_and_reclaimed_after_restart():
    issue = _issue()
    tracker = _Tracker([issue])
    expired = new_claim_record(
        issue,
        owner="old-scheduler",
        now=datetime.now(timezone.utc) - timedelta(hours=1),
        ttl_seconds=1,
    )
    tracker.set_metadata_field(issue.identifier, METADATA_KEY, expired.to_dict())
    issue.duplicate_screening = expired.to_dict()
    restarted = _orch(tracker)
    restarted._service_instance_id = "new-scheduler"

    replacement = restarted._claim_duplicate_preflight(issue)

    assert replacement is not None
    assert replacement.claim_id != expired.claim_id
    assert replacement.claim_owner == "new-scheduler"


def test_live_claim_is_renewed_near_half_life():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    claim = orch._claim_duplicate_preflight(issue)
    assert claim is not None
    near_expiry = replace(
        claim,
        claim_expires_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    tracker.set_metadata_field(issue.identifier, METADATA_KEY, near_expiry.to_dict())
    entry = _entry(issue, claim.claim_id or "", claim.task_fingerprint)
    entry.issue.duplicate_screening = near_expiry.to_dict()
    orch.state.running[issue.id] = entry

    assert orch._renew_duplicate_preflight_claims() == 1
    renewed = tracker.get_metadata(issue.identifier)[METADATA_KEY]
    assert datetime.fromisoformat(renewed["claim_expires_at"]) > near_expiry.claim_expires_at


def test_task_edit_during_run_cannot_record_current_pass():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    claim = orch._claim_duplicate_preflight(issue)
    assert claim is not None
    tracker.issues[issue.identifier].description = "Changed scope."
    tracker.add_label(issue.identifier, "focus-complete:duplicate_detector")
    tracker.add_comment(
        issue.identifier,
        "Focus handoff: duplicate_detector\n"
        "Duplicate preflight verdict: no_duplicate\n"
        "Matches: none\nEvidence: no active equivalent.",
    )

    result = orch._finish_duplicate_preflight_sync(
        _entry(issue, claim.claim_id or "", claim.task_fingerprint),
        "normal",
        None,
    )

    assert result["outcome"] == "stale_task"
    refreshed = tracker.fetch_issue_detail(issue.identifier)
    assert assess_screening(refreshed).state == ScreeningState.STALE


def test_no_duplicate_completion_keeps_open_and_unlocks_implementation():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    claim = orch._claim_duplicate_preflight(issue)
    assert claim is not None
    tracker.add_label(issue.identifier, "focus-complete:duplicate_detector")
    tracker.add_comment(
        issue.identifier,
        "Focus handoff: duplicate_detector\n"
        "Duplicate preflight verdict: no_duplicate\n"
        "Matches: none\nEvidence: reviewed active tasks.",
    )

    result = orch._finish_duplicate_preflight_sync(
        _entry(issue, claim.claim_id or "", claim.task_fingerprint),
        "normal",
        None,
    )

    refreshed = tracker.fetch_issue_detail(issue.identifier)
    assert result["outcome"] == "checked"
    assert refreshed.state == OPEN
    assert assess_screening(refreshed).implementation_eligible is True
    assert (issue.identifier, "In Progress") not in tracker.status_updates


def test_only_active_verified_match_becomes_duplicate_candidate():
    issue = _issue()
    active = _issue("TASK-2", title="Existing active equivalent")
    terminal = _issue("TASK-3", title="Historical equivalent", state=DONE)
    tracker = _Tracker([issue, active, terminal])
    orch = _orch(tracker)

    claim = orch._claim_duplicate_preflight(issue)
    assert claim is not None
    tracker.add_label(issue.identifier, "focus-complete:duplicate_detector")
    tracker.add_comment(
        issue.identifier,
        "Focus handoff: duplicate_detector\n"
        "Duplicate preflight verdict: duplicate_candidate\n"
        "Matches: TASK-2\nEvidence: same active root cause.",
    )
    result = orch._finish_duplicate_preflight_sync(
        _entry(issue, claim.claim_id or "", claim.task_fingerprint),
        "normal",
        None,
    )
    assert result["outcome"] == "duplicate_candidate"
    assert tracker.fetch_issue_detail(issue.identifier).state == DUPLICATE_CANDIDATE

    second = _issue("TASK-4")
    tracker.issues[second.identifier] = copy.deepcopy(second)
    tracker.metadata[second.identifier] = {}
    tracker.comments[second.identifier] = []
    claim = orch._claim_duplicate_preflight(second)
    assert claim is not None
    tracker.add_label(second.identifier, "focus-complete:duplicate_detector")
    tracker.add_comment(
        second.identifier,
        "Focus handoff: duplicate_detector\n"
        "Duplicate preflight verdict: duplicate_candidate\n"
        "Matches: TASK-3\nEvidence: resembles historical work.",
    )
    result = orch._finish_duplicate_preflight_sync(
        _entry(second, claim.claim_id or "", claim.task_fingerprint),
        "normal",
        None,
    )
    assert result["outcome"] == "retry"
    assert tracker.fetch_issue_detail(second.identifier).state == OPEN


def test_third_inconclusive_attempt_moves_needs_human_with_action():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    claim = new_claim_record(issue, owner="scheduler", retry_count=2)
    tracker.set_metadata_field(issue.identifier, METADATA_KEY, claim.to_dict())

    result = orch._finish_duplicate_preflight_sync(
        _entry(issue, claim.claim_id or "", claim.task_fingerprint),
        "abnormal",
        "provider failed",
    )

    assert result["outcome"] == "needs_human"
    assert tracker.fetch_issue_detail(issue.identifier).state == NEEDS_HUMAN
    assert "Human action required" in tracker.fetch_comments(issue.identifier)[-1]["text"]


def test_selection_uses_spare_capacity_cap_and_priority_order():
    high = _issue("TASK-1", priority=1)
    low = _issue("TASK-2", priority=3)
    tracker = _Tracker([high, low])
    orch = _orch(tracker, slots=3, preflight_limit=1)
    orch._should_dispatch = lambda issue, duplicate_preflight=False: True

    selected = orch._select_duplicate_preflight_candidates([low, high])

    assert [item.identifier for item in selected] == ["TASK-1"]
    assert orch._last_duplicate_preflight_metrics["limit"] == 1


def test_zero_preflight_cap_disables_selection():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker, slots=3, preflight_limit=0)
    orch._should_dispatch = lambda issue, duplicate_preflight=False: True

    assert orch._select_duplicate_preflight_candidates([issue]) == []


def test_selection_skips_checked_running_and_backoff_records():
    checked_issue = _issue("TASK-1")
    running_issue = _issue("TASK-2")
    backoff_issue = _issue("TASK-3")
    unchecked_issue = _issue("TASK-4")
    now = datetime.now(timezone.utc)

    checked_claim = new_claim_record(checked_issue, owner="scheduler", now=now)
    checked_issue.duplicate_screening = complete_claim_record(
        checked_claim,
        verdict=ScreeningVerdict.NO_DUPLICATE,
        now=now,
    ).to_dict()
    running_issue.duplicate_screening = new_claim_record(
        running_issue,
        owner="scheduler",
        now=now,
    ).to_dict()
    backoff_claim = new_claim_record(backoff_issue, owner="scheduler", now=now)
    backoff = complete_claim_record(
        backoff_claim,
        verdict=ScreeningVerdict.INCONCLUSIVE,
        now=now,
    )
    backoff_issue.duplicate_screening = {
        **backoff.to_dict(),
        "checked_at": None,
        "retry_after": (now + timedelta(minutes=5)).isoformat(),
    }
    tracker = _Tracker([checked_issue, running_issue, backoff_issue, unchecked_issue])
    orch = _orch(tracker, slots=4, preflight_limit=4)
    orch._should_dispatch = lambda issue, duplicate_preflight=False: True

    selected = orch._select_duplicate_preflight_candidates(
        [checked_issue, running_issue, backoff_issue, unchecked_issue]
    )

    assert [item.identifier for item in selected] == ["TASK-4"]
    metrics = orch._last_duplicate_preflight_metrics
    assert metrics["skipped_checked"] == 1
    assert metrics["skipped_running"] == 1
    assert metrics["skipped_backoff"] == 1


@pytest.mark.asyncio
async def test_dispatch_preflight_does_not_move_task_in_progress():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker, slots=2, preflight_limit=1)
    orch._paused = False
    orch._tick_pool = ThreadPoolExecutor(max_workers=2)
    orch._match_agent_profile = lambda current: None
    orch._post_comment = MagicMock()
    orch._notify_observers = MagicMock()
    orch.event_bus = EventBus()
    stop = asyncio.Event()

    async def fake_worker(current, attempt, profile):
        await stop.wait()

    orch._run_worker = fake_worker
    claim = orch._claim_duplicate_preflight(issue)
    assert claim is not None

    await orch._dispatch(
        issue,
        attempt=None,
        duplicate_preflight_claim=claim,
    )

    entry = orch.state.running[issue.id]
    assert entry.duplicate_preflight is True
    assert entry.issue.state == OPEN
    assert (issue.identifier, "In Progress") not in tracker.status_updates

    stop.set()
    await entry.worker_task
    orch._tick_pool.shutdown(wait=True)


def test_normal_implementation_gate_requires_current_model_pass():
    issue = _issue()
    tracker = _Tracker([issue])
    orch = _orch(tracker)
    assert orch._implementation_duplicate_screening_ready(issue) is False

    claim = new_claim_record(issue, owner="scheduler")
    checked = complete_claim_record(
        claim,
        verdict=ScreeningVerdict.NO_DUPLICATE,
    )
    issue.duplicate_screening = checked.to_dict()
    assert orch._implementation_duplicate_screening_ready(issue) is True

    issue.title = "Changed after screening"
    assert orch._implementation_duplicate_screening_ready(issue) is False
