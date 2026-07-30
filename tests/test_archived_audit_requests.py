"""Tests for guarded Archived-audit requests from maintenance workers."""

from __future__ import annotations

import copy
import threading
from typing import Any

from oompah.archived_audit_requests import (
    cancel_pending_archived_audit,
    request_archived_audit,
)
from oompah.models import Issue
from oompah.statuses import ARCHIVED, DONE, IN_VALIDATION
from oompah.terminal_audit import RequestState, TargetState
from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata


class _ProjectStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def project_write_lock(self, _project_id: str) -> threading.RLock:
        return self._lock


class _Tracker:
    def __init__(self, issue: Issue, *, fail_updates: bool = False) -> None:
        self.issue = issue
        self.metadata: dict[str, dict[str, Any]] = {}
        self.comments: list[str] = []
        self.update_calls: list[dict[str, Any]] = []
        self.fail_updates = fail_updates

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        assert identifier == self.issue.identifier
        return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        assert identifier == self.issue.identifier
        self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def update_issue(self, identifier: str, **fields: Any) -> None:
        assert identifier == self.issue.identifier
        self.update_calls.append(dict(fields))
        if self.fail_updates:
            raise RuntimeError("tracker unavailable")
        if "status" in fields:
            self.issue.state = str(fields["status"])

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> None:
        assert identifier == self.issue.identifier
        assert author == "oompah"
        self.comments.append(text)


def _issue(state: str = DONE) -> Issue:
    return Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Archive candidate",
        state=state,
    )


def _records(tracker: _Tracker):
    document = TerminalAuditMetadata.from_dict(
        tracker.metadata[tracker.issue.identifier][METADATA_KEY]
    )
    return document.pending_chain


def test_queues_aged_done_audit_with_pre_archive_state_and_comment() -> None:
    issue = _issue(DONE)
    tracker = _Tracker(issue)

    queued = request_archived_audit(
        issue,
        tracker,
        "proj-test",
        "Aged Done auto-archive (closed 8 days ago)",
        project_store=_ProjectStore(),
        trigger_source="auto_archive",
    )

    assert queued is True
    assert issue.state == IN_VALIDATION
    records = _records(tracker)
    assert len(records) == 1
    assert records[0].target_state == TargetState.ARCHIVED
    assert records[0].request_state == RequestState.PENDING
    assert records[0].previous_state == DONE
    assert records[0].requested_by is not None
    assert records[0].requested_by.source == "auto_archive"
    assert tracker.comments == [
        "Queued Archived audit: Aged Done auto-archive (closed 8 days ago). "
        "An auditor will review before the task is retired."
    ]


def test_pending_archive_coalesces_even_when_retention_reason_changes() -> None:
    issue = _issue()
    tracker = _Tracker(issue)
    store = _ProjectStore()

    assert request_archived_audit(
        issue, tracker, "proj-test", "Aged Done auto-archive (closed 8 days ago)", store
    )
    assert not request_archived_audit(
        issue, tracker, "proj-test", "Aged Done auto-archive (closed 9 days ago)", store
    )

    assert len(_records(tracker)) == 1
    assert len(tracker.comments) == 1
    assert tracker.update_calls == [{"status": IN_VALIDATION}]


def test_retries_only_the_staging_write_after_a_tracker_failure() -> None:
    issue = _issue()
    tracker = _Tracker(issue, fail_updates=True)
    store = _ProjectStore()

    assert not request_archived_audit(
        issue, tracker, "proj-test", "Aged Done auto-archive", store
    )
    assert issue.state == DONE
    assert len(_records(tracker)) == 1

    tracker.fail_updates = False
    assert request_archived_audit(
        issue, tracker, "proj-test", "Aged Done auto-archive (retry)", store
    )

    assert issue.state == IN_VALIDATION
    assert len(_records(tracker)) == 1
    assert len(tracker.comments) == 1


def test_rejects_missing_disposition_evidence_without_writing() -> None:
    issue = _issue()
    tracker = _Tracker(issue)

    assert not request_archived_audit(issue, tracker, "proj-test", "", _ProjectStore())
    assert tracker.metadata == {}
    assert tracker.update_calls == []
    assert tracker.comments == []


def test_grandfathered_archived_issue_is_not_requeued() -> None:
    issue = _issue(ARCHIVED)
    tracker = _Tracker(issue)

    assert not request_archived_audit(
        issue, tracker, "proj-test", "Aged archived upgrade record", _ProjectStore()
    )
    assert tracker.metadata == {}
    assert tracker.update_calls == []


def test_cancelling_unsafe_retirement_returns_the_recorded_prior_state() -> None:
    issue = _issue("Open")
    tracker = _Tracker(issue)
    store = _ProjectStore()
    assert request_archived_audit(
        issue, tracker, "proj-test", "External issue closed", store
    )

    cancelled, previous_state = cancel_pending_archived_audit(
        issue,
        tracker,
        "proj-test",
        "external issue reopened before retirement completed",
        store,
    )

    assert cancelled is True
    assert previous_state == "Open"
    assert _records(tracker)[0].request_state == RequestState.CANCELLED
    assert tracker.comments[-1].startswith("Cancelled Archived audit:")
