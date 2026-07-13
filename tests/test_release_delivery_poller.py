"""Tests for :mod:`oompah.release_delivery_poller`.

Covers:
- non-in_review delivery is returned unchanged.
- delivery with no pr_url is returned unchanged.
- open PR → no change.
- merged PR → transition to merged, completed_at set.
- merged PR on already-merged delivery (race) → no error, returns merged.
- closed PR → error field updated, status stays in_review.
- closed PR already marked (idempotent) → no second write.
- SCM query failure → delivery returned unchanged.
- PR not found → delivery returned unchanged.
- PR merge reconciliation marks exact delivery merged (not another).
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from oompah.release_addendum_schema import AddendumStatus, InvalidTransitionError
from oompah.release_delivery_poller import (
    CLOSED_UNMERGED_ERROR_PREFIX,
    _handle_closed,
    _handle_merged,
    poll_delivery_pr,
)
from oompah.release_delivery_store import (
    DeliveryNotFoundError,
    ReleaseDelivery,
    SourceKind,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = "proj-poller"


def _sha(c: str) -> str:
    return c * 40


def _delivery(
    delivery_id: str = "rd_poll_001",
    *,
    status: AddendumStatus = AddendumStatus.IN_REVIEW,
    pr_url: str | None = "https://github.com/org/repo/pull/1",
    work_branch: str | None = "oompah/release/FOO-10/release-1.0",
    error: str | None = None,
    source_identifier: str | None = "FOO-10",
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=delivery_id,
        project_id=PROJECT_ID,
        source_branch="main",
        source_kind=SourceKind.TASK,
        source_identifier=source_identifier,
        source_commits=[_sha("a")],
        target_branch="release/1.0",
        status=status,
        queued_at=NOW.isoformat(),
        pr_url=pr_url,
        work_branch=work_branch,
        error=error,
    )


class _FakeStore:
    """Thread-safe in-memory store for poller tests."""

    def __init__(self, deliveries: list[ReleaseDelivery]) -> None:
        self._lock = threading.Lock()
        self._deliveries = list(deliveries)
        self.update_calls: list[dict[str, Any]] = []

    def lookup_by_id(self, delivery_id: str) -> ReleaseDelivery | None:
        with self._lock:
            return next((d for d in self._deliveries if d.id == delivery_id), None)

    def update(self, delivery_id: str, **fields: Any) -> ReleaseDelivery:
        from oompah.release_addendum_schema import AddendumStatus as AS, is_valid_transition
        from oompah.release_delivery_store import (
            DeliveryNotFoundError,
            _IMMUTABLE_FIELDS,
            _MUTABLE_FIELDS,
            ImmutableFieldError,
        )

        self.update_calls.append({"delivery_id": delivery_id, **fields})

        immutable_attempts = set(fields) & _IMMUTABLE_FIELDS
        if immutable_attempts:
            raise ImmutableFieldError(f"Cannot change: {immutable_attempts}")

        with self._lock:
            idx = next(
                (i for i, d in enumerate(self._deliveries) if d.id == delivery_id),
                None,
            )
            if idx is None:
                raise DeliveryNotFoundError(f"Not found: {delivery_id}")

            current = self._deliveries[idx]
            new_status = current.status
            if "status" in fields:
                raw = fields["status"]
                new_status = raw if isinstance(raw, AS) else AS.from_raw(raw)
                if not is_valid_transition(current.status, new_status):
                    from oompah.release_addendum_schema import InvalidTransitionError
                    raise InvalidTransitionError(
                        f"Invalid: {current.status} → {new_status}"
                    )

            updated = dataclasses.replace(
                current,
                status=new_status,
                error=fields.get("error", current.error),
                completed_at=fields.get("completed_at", current.completed_at),
            )
            self._deliveries[idx] = updated
            return updated


def _pr(state: str, url: str = "https://github.com/org/repo/pull/1") -> SimpleNamespace:
    return SimpleNamespace(state=state, url=url, id=1, number=1)


def _scm(*, pr: Any = None) -> MagicMock:
    scm = MagicMock()
    scm.find_pr_for_branch.return_value = pr
    return scm


# ---------------------------------------------------------------------------
# Tests: guard conditions
# ---------------------------------------------------------------------------


def test_poll_delivery_non_in_review_is_noop():
    for status in (
        AddendumStatus.OPEN,
        AddendumStatus.IN_PROGRESS,
        AddendumStatus.BLOCKED,
        AddendumStatus.MERGED,
        AddendumStatus.ARCHIVED,
    ):
        d = _delivery(status=status)
        store = _FakeStore([d])
        result = poll_delivery_pr(store, d, scm=_scm(), repo="org/repo", now=NOW)
        assert result.status is status
        assert store.update_calls == []


def test_poll_delivery_no_pr_url_is_noop():
    d = _delivery(pr_url=None)
    store = _FakeStore([d])
    result = poll_delivery_pr(store, d, scm=_scm(), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW
    assert store.update_calls == []


def test_poll_delivery_scm_query_failure_returns_unchanged():
    d = _delivery()
    store = _FakeStore([d])
    scm = MagicMock()
    scm.find_pr_for_branch.side_effect = RuntimeError("network timeout")
    result = poll_delivery_pr(store, d, scm=scm, repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW
    assert store.update_calls == []


def test_poll_delivery_pr_not_found_returns_unchanged():
    d = _delivery()
    store = _FakeStore([d])
    result = poll_delivery_pr(store, d, scm=_scm(pr=None), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW
    assert store.update_calls == []


def test_poll_delivery_open_pr_is_noop():
    d = _delivery()
    store = _FakeStore([d])
    result = poll_delivery_pr(store, d, scm=_scm(pr=_pr("open")), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW
    assert store.update_calls == []


# ---------------------------------------------------------------------------
# Tests: merged PR
# ---------------------------------------------------------------------------


def test_poll_delivery_merged_pr_transitions_to_merged():
    d = _delivery()
    store = _FakeStore([d])
    result = poll_delivery_pr(store, d, scm=_scm(pr=_pr("merged")), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.MERGED
    assert result.completed_at == NOW.isoformat()


def test_poll_delivery_merged_writes_completed_at():
    d = _delivery()
    store = _FakeStore([d])
    poll_delivery_pr(store, d, scm=_scm(pr=_pr("merged")), repo="org/repo", now=NOW)
    assert any(
        c.get("status") is AddendumStatus.MERGED for c in store.update_calls
    )
    assert any(
        c.get("completed_at") == NOW.isoformat() for c in store.update_calls
    )


def test_poll_delivery_merged_already_merged_is_idempotent():
    """A race where another poller already transitioned: no error, return merged."""
    d = _delivery(status=AddendumStatus.MERGED)
    store = _FakeStore([d])
    # status=merged → poll is a no-op (guard check at the start)
    result = poll_delivery_pr(store, d, scm=_scm(pr=_pr("merged")), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.MERGED
    assert store.update_calls == []


def test_handle_merged_race_with_already_merged():
    """_handle_merged raises InvalidTransitionError → re-reads and returns merged."""
    d = _delivery(status=AddendumStatus.IN_REVIEW)
    # Simulate a store that raises InvalidTransitionError on the first update
    already_merged = dataclasses.replace(d, status=AddendumStatus.MERGED, completed_at=NOW.isoformat())
    store = MagicMock()
    store.update.side_effect = InvalidTransitionError("already merged")
    store.lookup_by_id.return_value = already_merged

    from oompah.release_delivery_poller import _handle_merged
    result = _handle_merged(store, d, now=NOW)
    assert result.status is AddendumStatus.MERGED


# ---------------------------------------------------------------------------
# Tests: closed PR
# ---------------------------------------------------------------------------


def test_poll_delivery_closed_pr_records_error():
    d = _delivery()
    store = _FakeStore([d])
    result = poll_delivery_pr(store, d, scm=_scm(pr=_pr("closed")), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW  # status unchanged
    assert result.error is not None
    assert result.error.startswith(CLOSED_UNMERGED_ERROR_PREFIX)
    assert d.pr_url in result.error


def test_poll_delivery_closed_pr_idempotent():
    """Already-marked closed PR: no second write."""
    existing_error = f"{CLOSED_UNMERGED_ERROR_PREFIX} https://github.com/org/repo/pull/1"
    d = _delivery(error=existing_error)
    store = _FakeStore([d])
    result = poll_delivery_pr(store, d, scm=_scm(pr=_pr("closed")), repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW
    # No additional write
    assert store.update_calls == []


def test_closed_unmerged_pr_can_be_retried():
    """After closed marker: delivery can be transitioned back to open (retry)."""
    existing_error = f"{CLOSED_UNMERGED_ERROR_PREFIX} https://github.com/org/repo/pull/1"
    d = _delivery(status=AddendumStatus.IN_REVIEW, error=existing_error)
    # Simulate retry: transition in_review → open
    store = _FakeStore([d])
    updated = store.update(d.id, status=AddendumStatus.OPEN)
    assert updated.status is AddendumStatus.OPEN


# ---------------------------------------------------------------------------
# Tests: PR reconciliation marks exact delivery
# ---------------------------------------------------------------------------


def test_poll_delivery_merged_marks_exact_delivery_not_others():
    """Only the polled delivery is transitioned; other deliveries are untouched."""
    d1 = _delivery("rd_1")
    d2 = _delivery("rd_2")
    store = _FakeStore([d1, d2])
    poll_delivery_pr(store, d1, scm=_scm(pr=_pr("merged")), repo="org/repo", now=NOW)
    # d2 must be unchanged
    d2_current = store.lookup_by_id("rd_2")
    assert d2_current.status is AddendumStatus.IN_REVIEW


# ---------------------------------------------------------------------------
# Tests: work_branch derivation when not set
# ---------------------------------------------------------------------------


def test_poll_delivery_derives_work_branch_when_missing():
    """When work_branch is null, it is derived before looking up the PR."""
    d = _delivery(work_branch=None)
    store = _FakeStore([d])
    scm = _scm(pr=_pr("open"))
    # Should not raise; find_pr_for_branch gets a non-null branch name
    result = poll_delivery_pr(store, d, scm=scm, repo="org/repo", now=NOW)
    assert result.status is AddendumStatus.IN_REVIEW
    # The branch passed to find_pr_for_branch should be non-empty
    called_branch = scm.find_pr_for_branch.call_args[0][1]
    assert called_branch and "release" in called_branch
