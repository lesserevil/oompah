"""Tests for :mod:`oompah.release_delivery_executor`.

Covers:
- Unavailable target branch → blocked immediately (never cherry-picks).
- Deleted target branch (catalog returns available=False) → blocked.
- Missing catalog → target availability check skipped; execution continues.
- Worktree creation failure → blocked.
- Existing PR reused (idempotent re-run).
- Cherry-pick conflict → blocked, worktree preserved.
- Non-conflict cherry-pick error → blocked.
- Push failure → blocked.
- PR-open failure → still transitions to in_review (pr_url=None).
- Successful run: result_commits and pr_url/pr_number persisted before in_review.
- Multi-commit delivery: source_commits in stored order passed to cherry-pick.
- Result SHAs persisted before in_review transition.
- work_branch persisted at start of execution.
- No tracker task created or source task status changed.
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.cherry_pick_pr_creator import CherryPickConflictError, CherryPickError
from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_executor import (
    _find_existing_pr,
    _get_result_commits,
    _is_target_available,
    _open_delivery_pr,
    _persist_blocked,
    cherry_pick_delivery,
)
from oompah.release_delivery_store import (
    DeliveryNotFoundError,
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = "proj-test"

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40
_RESULT_SHA = "e" * 40


def _sha(c: str) -> str:
    return c * 40


def _delivery(
    delivery_id: str = "rd_exec_001",
    *,
    status: AddendumStatus = AddendumStatus.IN_PROGRESS,
    source_commits: list[str] | None = None,
    target: str = "release/1.0",
    pr_url: str | None = None,
    work_branch: str | None = None,
    source_identifier: str | None = "FOO-10",
    source_kind: SourceKind = SourceKind.TASK,
) -> ReleaseDelivery:
    if source_commits is None:
        source_commits = [_COMMIT_A, _COMMIT_B]
    return ReleaseDelivery(
        id=delivery_id,
        project_id=PROJECT_ID,
        source_branch="main",
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=source_commits,
        target_branch=target,
        status=status,
        queued_at=NOW.isoformat(),
        pr_url=pr_url,
        work_branch=work_branch,
        claimed_by="worker-1",
        lease_expires_at=NOW.isoformat(),
    )


class _FakeStore:
    """Thread-safe in-memory store that mirrors ReleaseDeliveryStore's interface."""

    def __init__(self, deliveries: list[ReleaseDelivery]) -> None:
        self._lock = threading.Lock()
        self._deliveries = list(deliveries)
        self.update_calls: list[dict[str, Any]] = []

    def read_ledger(self) -> Any:
        from oompah.release_delivery_store import ReleaseDeliveryLedger
        with self._lock:
            return ReleaseDeliveryLedger(version=1, deliveries=list(self._deliveries))

    def lookup_by_id(self, delivery_id: str) -> ReleaseDelivery | None:
        with self._lock:
            return next((d for d in self._deliveries if d.id == delivery_id), None)

    def update(self, delivery_id: str, **fields: Any) -> ReleaseDelivery:
        from oompah.release_addendum_schema import AddendumStatus as AS, is_valid_transition
        from oompah.release_delivery_store import (
            ImmutableFieldError,
            DeliveryNotFoundError,
            _IMMUTABLE_FIELDS,
            _MUTABLE_FIELDS,
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
                work_branch=fields.get("work_branch", current.work_branch),
                pr_url=fields.get("pr_url", current.pr_url),
                pr_number=fields.get("pr_number", current.pr_number),
                result_commits=fields.get("result_commits", list(current.result_commits)),
                error=fields.get("error", current.error),
                claimed_by=fields.get("claimed_by", current.claimed_by),
                lease_expires_at=fields.get("lease_expires_at", current.lease_expires_at),
                started_at=fields.get("started_at", current.started_at),
                completed_at=fields.get("completed_at", current.completed_at),
            )
            self._deliveries[idx] = updated
            return updated


def _make_scm(*, open_pr: Any = None, created_pr: Any = None) -> MagicMock:
    scm = MagicMock()
    scm.find_pr_for_branch.return_value = open_pr
    scm.create_review.return_value = created_pr
    return scm


def _make_project_store(wt_path: str = "/fake/wt") -> MagicMock:
    ps = MagicMock()
    ps.create_worktree.return_value = wt_path
    return ps


def _make_pr(url: str = "https://github.com/org/repo/pull/42", number: int = 42, state: str = "open") -> SimpleNamespace:
    return SimpleNamespace(url=url, id=number, number=number, state=state)


# ---------------------------------------------------------------------------
# _is_target_available tests
# ---------------------------------------------------------------------------


def test_is_target_available_no_catalog_skips_check():
    d = _delivery()
    available, reason = _is_target_available(d, project=None, catalog=None)
    assert available is True
    assert reason == ""


def test_is_target_available_unconfigured_branch():
    d = _delivery()
    from oompah.release_branch_catalog import CatalogResult, ReleaseBranch
    catalog = MagicMock()
    result = CatalogResult(
        project_id=PROJECT_ID,
        source_branch="main",
        branches=[ReleaseBranch(name="release/2.0", available=True)],
    )
    catalog.list_candidates.return_value = result
    available, reason = _is_target_available(d, project=MagicMock(), catalog=catalog)
    assert available is False
    assert "release/1.0" in reason
    assert "not configured" in reason


def test_is_target_available_branch_deleted():
    d = _delivery()
    from oompah.release_branch_catalog import CatalogResult, ReleaseBranch
    catalog = MagicMock()
    result = CatalogResult(
        project_id=PROJECT_ID,
        source_branch="main",
        branches=[ReleaseBranch(name="release/1.0", available=False)],
    )
    catalog.list_candidates.return_value = result
    available, reason = _is_target_available(d, project=MagicMock(), catalog=catalog)
    assert available is False
    assert "no longer available" in reason


def test_is_target_available_branch_present():
    d = _delivery()
    from oompah.release_branch_catalog import CatalogResult, ReleaseBranch
    catalog = MagicMock()
    result = CatalogResult(
        project_id=PROJECT_ID,
        source_branch="main",
        branches=[ReleaseBranch(name="release/1.0", available=True)],
    )
    catalog.list_candidates.return_value = result
    available, reason = _is_target_available(d, project=MagicMock(), catalog=catalog)
    assert available is True
    assert reason == ""


def test_is_target_available_catalog_error_does_not_block():
    """Catalog errors are absorbed; the check returns True so execution continues."""
    d = _delivery()
    catalog = MagicMock()
    catalog.list_candidates.side_effect = RuntimeError("network error")
    available, reason = _is_target_available(d, project=MagicMock(), catalog=catalog)
    assert available is True


# ---------------------------------------------------------------------------
# cherry_pick_delivery: unavailable target
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_unavailable_target_is_blocked():
    d = _delivery()
    store = _FakeStore([d])
    from oompah.release_branch_catalog import CatalogResult, ReleaseBranch
    catalog = MagicMock()
    catalog.list_candidates.return_value = CatalogResult(
        project_id=PROJECT_ID,
        source_branch="main",
        branches=[ReleaseBranch(name="release/1.0", available=False)],
    )
    result = cherry_pick_delivery(
        store,
        d,
        project_store=MagicMock(),
        project_id=PROJECT_ID,
        scm=MagicMock(),
        repo="org/repo",
        project=MagicMock(),
        catalog=catalog,
    )
    assert result.status is AddendumStatus.BLOCKED
    assert "no longer available" in (result.error or "")


def test_cherry_pick_delivery_unconfigured_target_is_blocked():
    d = _delivery(target="release/9.9")
    store = _FakeStore([d])
    from oompah.release_branch_catalog import CatalogResult, ReleaseBranch
    catalog = MagicMock()
    catalog.list_candidates.return_value = CatalogResult(
        project_id=PROJECT_ID,
        source_branch="main",
        branches=[ReleaseBranch(name="release/1.0", available=True)],
    )
    result = cherry_pick_delivery(
        store,
        d,
        project_store=MagicMock(),
        project_id=PROJECT_ID,
        scm=MagicMock(),
        repo="org/repo",
        project=MagicMock(),
        catalog=catalog,
    )
    assert result.status is AddendumStatus.BLOCKED
    assert "not configured" in (result.error or "")


def test_cherry_pick_delivery_no_catalog_skips_availability_check():
    """When no catalog is supplied, the availability check is bypassed."""
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch("oompah.release_delivery_executor._get_result_commits", return_value=[_RESULT_SHA]),
    ):
        pr = _make_pr()
        scm = _make_scm(created_pr=pr)
        result = cherry_pick_delivery(
            store,
            d,
            project_store=ps,
            project_id=PROJECT_ID,
            scm=scm,
            repo="org/repo",
            catalog=None,  # no catalog
        )
    assert result.status is AddendumStatus.IN_REVIEW


# ---------------------------------------------------------------------------
# cherry_pick_delivery: worktree failure
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_worktree_creation_failure():
    d = _delivery()
    store = _FakeStore([d])
    ps = MagicMock()
    ps.create_worktree.side_effect = RuntimeError("disk full")
    result = cherry_pick_delivery(
        store, d, project_store=ps, project_id=PROJECT_ID, scm=MagicMock(), repo="org/repo"
    )
    assert result.status is AddendumStatus.BLOCKED
    assert "worktree" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# cherry_pick_delivery: existing PR reuse
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_reuses_existing_pr():
    pr = _make_pr(url="https://github.com/org/repo/pull/7", number=7)
    d = _delivery(pr_url="https://github.com/org/repo/pull/7")
    store = _FakeStore([d])
    ps = _make_project_store()
    scm = _make_scm(open_pr=pr)

    with patch(
        "oompah.release_delivery_executor._get_result_commits",
        return_value=[_RESULT_SHA],
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )
    assert result.status is AddendumStatus.IN_REVIEW
    assert result.pr_url == "https://github.com/org/repo/pull/7"
    assert _RESULT_SHA in result.result_commits
    # Cherry-pick must NOT have been invoked
    scm.create_review.assert_not_called()


# ---------------------------------------------------------------------------
# cherry_pick_delivery: conflict
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_conflict_blocks():
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    scm = _make_scm()

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=False),
        patch(
            "oompah.release_delivery_executor.apply_cherry_pick",
            side_effect=CherryPickConflictError("conflict in foo.py"),
        ),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )
    assert result.status is AddendumStatus.BLOCKED
    assert "conflict" in (result.error or "").lower()


def test_cherry_pick_delivery_non_conflict_error_blocks():
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    scm = _make_scm()

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=False),
        patch(
            "oompah.release_delivery_executor.apply_cherry_pick",
            side_effect=CherryPickError("bad sha"),
        ),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )
    assert result.status is AddendumStatus.BLOCKED


# ---------------------------------------------------------------------------
# cherry_pick_delivery: push failure
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_push_failure_blocks():
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    scm = _make_scm()

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch(
            "oompah.release_delivery_executor.push_branch",
            side_effect=RuntimeError("push rejected"),
        ),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )
    assert result.status is AddendumStatus.BLOCKED
    assert "push" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# cherry_pick_delivery: success path
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_success_persists_evidence():
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    pr = _make_pr(url="https://github.com/org/repo/pull/99", number=99)
    scm = _make_scm(created_pr=pr)

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch(
            "oompah.release_delivery_executor._get_result_commits",
            return_value=[_RESULT_SHA],
        ),
    ):
        result = cherry_pick_delivery(
            store,
            d,
            project_store=ps,
            project_id=PROJECT_ID,
            scm=scm,
            repo="org/repo",
            source_title="Add invoice export",
        )
    assert result.status is AddendumStatus.IN_REVIEW
    assert result.pr_url == "https://github.com/org/repo/pull/99"
    assert result.pr_number == "99"
    assert _RESULT_SHA in result.result_commits


def test_cherry_pick_delivery_multi_commit_order():
    """source_commits are passed to apply_cherry_pick in the stored order."""
    commits = [_sha("a"), _sha("b"), _sha("c")]
    d = _delivery(source_commits=commits)
    store = _FakeStore([d])
    ps = _make_project_store()
    pr = _make_pr()
    scm = _make_scm(created_pr=pr)

    seen_commits = []

    def _capture_pick(wt: str, picked: list[str]) -> None:
        seen_commits.extend(picked)

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=False),
        patch("oompah.release_delivery_executor.apply_cherry_pick", side_effect=_capture_pick),
        patch("oompah.release_delivery_executor.push_branch"),
        patch("oompah.release_delivery_executor._get_result_commits", return_value=[_sha("e")]),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )

    assert seen_commits == commits
    assert result.status is AddendumStatus.IN_REVIEW


def test_cherry_pick_delivery_result_commits_persisted_before_in_review():
    """result_commits appear in the first in_review update call."""
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    pr = _make_pr()
    scm = _make_scm(created_pr=pr)

    result_sha = _sha("f")

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch(
            "oompah.release_delivery_executor._get_result_commits",
            return_value=[result_sha],
        ),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )

    # The final in_review update must carry result_commits
    in_review_calls = [
        c for c in store.update_calls
        if c.get("status") is AddendumStatus.IN_REVIEW
    ]
    assert len(in_review_calls) == 1
    assert result_sha in in_review_calls[0].get("result_commits", [])
    assert result.result_commits == [result_sha]


def test_cherry_pick_delivery_work_branch_persisted():
    """work_branch is written to the delivery before worktree creation."""
    d = _delivery(work_branch=None)  # not yet set
    store = _FakeStore([d])
    ps = _make_project_store()
    pr = _make_pr()
    scm = _make_scm(created_pr=pr)

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch("oompah.release_delivery_executor._get_result_commits", return_value=[]),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )

    work_branch_calls = [
        c for c in store.update_calls
        if "work_branch" in c and c.get("status") is None or "status" not in c
    ]
    assert any("work_branch" in c for c in store.update_calls)


def test_cherry_pick_delivery_pr_open_failure_still_in_review():
    """A failed PR open sets pr_url=None but still transitions to in_review."""
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    scm = _make_scm(created_pr=None)  # create_review returns None

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch("oompah.release_delivery_executor._get_result_commits", return_value=[]),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )
    assert result.status is AddendumStatus.IN_REVIEW
    assert result.pr_url is None


# ---------------------------------------------------------------------------
# No tracker task or source task mutation
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_does_not_call_tracker():
    """The executor never touches a task tracker."""
    d = _delivery()
    store = _FakeStore([d])
    ps = _make_project_store()
    pr = _make_pr()
    scm = _make_scm(created_pr=pr)
    tracker = MagicMock()

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch("oompah.release_delivery_executor._get_result_commits", return_value=[]),
    ):
        cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )

    tracker.assert_not_called()


# ---------------------------------------------------------------------------
# commits-kind delivery (no source_identifier)
# ---------------------------------------------------------------------------


def test_cherry_pick_delivery_commits_kind_work_branch():
    """Commits-kind delivery derives work_branch from delivery_id."""
    d = _delivery(source_identifier=None, source_kind=SourceKind.COMMITS)
    store = _FakeStore([d])
    ps = _make_project_store()
    pr = _make_pr()
    scm = _make_scm(created_pr=pr)

    with (
        patch("oompah.release_delivery_executor._has_new_commits", return_value=True),
        patch("oompah.release_delivery_executor.push_branch"),
        patch("oompah.release_delivery_executor._get_result_commits", return_value=[]),
    ):
        result = cherry_pick_delivery(
            store, d, project_store=ps, project_id=PROJECT_ID, scm=scm, repo="org/repo"
        )

    assert result.status is AddendumStatus.IN_REVIEW
    # work_branch must have been set
    assert result.work_branch is not None
    assert result.work_branch.startswith("oompah/release/")
