"""Tests for oompah.release_addendum_migration (OOMPAH-194).

Covers:
  - _all_commits_valid: valid SHAs, invalid SHAs, OOMPAH-183 sentinels
  - _make_delivery_id: produces rd_ prefix, unique values
  - _infer_source_kind: epic vs task
  - build_delivery_from_addendum:
    - all fields preserved (execution evidence byte-for-byte)
    - custom delivery_id used when supplied
    - raises ValueError for non-SHA commits (sentinel strings)
    - raises ValueError for empty commit list
    - sets migrated_from to the legacy addendum ID
    - source_kind and source_identifier set correctly
  - AddendumMigrationResult: changed property
  - run_addendum_migration:
    - migrates task addendums
    - migrates epic addendums
    - every lifecycle status migrated correctly
    - skips entries with non-SHA commits (sentinel values) as skipped_malformed
    - skips structurally malformed addendum dict as skipped_malformed
    - idempotency: second run produces no new records
    - partial migration: first run migrates some; second run fills the rest
    - malformed single entry does not block valid entries on same issue
    - malformed entry on one issue does not block migration of other issues
    - issues_scanned counts issues with parseable addendums only
    - ledger read failure aborts migration and returns error count
    - fetch_all_issues failure aborts migration and returns error count
    - get_metadata failure for one issue is silently skipped
    - store append failure increments errors
    - duplicate addendum IDs: second run counts them as skipped_duplicate
    - all fields preserved byte-for-byte (evidence round-trip)
    - result_commits preserved
    - work_branch preserved
    - pr_url preserved
    - error field preserved
    - claimed_by and lease_expires_at preserved
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from oompah.models import Issue
from oompah.release_addendum_migration import (
    AddendumMigrationResult,
    _all_commits_valid,
    _infer_source_kind,
    _make_delivery_id,
    build_delivery_from_addendum,
    run_addendum_migration,
)
from oompah.release_addendum_schema import AddendumStatus, ReleaseAddendum
from oompah.release_delivery_store import (
    LEDGER_PATH,
    LedgerParseError,
    ReleaseDelivery,
    ReleaseDeliveryLedger,
    ReleaseDeliveryStore,
    SourceKind,
)
from oompah.statuses import OPEN, MERGED, ARCHIVED

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_C = "c" * 40
_SHA_RESULT = "9" * 40

_QUEUED_AT = "2026-07-13T12:00:00Z"
_STARTED_AT = "2026-07-13T13:00:00Z"
_COMPLETED_AT = "2026-07-13T14:00:00Z"
_LEASE_EXPIRES_AT = "2026-07-13T12:15:00Z"

_SENTINEL_PENDING = "migration-pending"
_SENTINEL_NO_COMMITS = "migration-no-commits"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_addendum(
    *,
    addendum_id: str = "TASK-1/release/1.0",
    source_branch: str = "main",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    commits: list[str] | None = None,
    work_branch: str = "oompah/release/TASK-1/release-1.0",
    worktree_key: str = "release-TASK-1-release-1.0",
    queued_at: str = _QUEUED_AT,
    started_at: str | None = None,
    completed_at: str | None = None,
    pr_url: str | None = None,
    result_commits: list[str] | None = None,
    error: str | None = None,
    claimed_by: str | None = None,
    lease_expires_at: str | None = None,
    included_child_ids: list[str] | None = None,
) -> ReleaseAddendum:
    return ReleaseAddendum(
        id=addendum_id,
        source_branch=source_branch,
        target_branch=target_branch,
        status=status,
        commits=commits if commits is not None else [_SHA_A],
        work_branch=work_branch,
        worktree_key=worktree_key,
        queued_at=queued_at,
        started_at=started_at,
        completed_at=completed_at,
        pr_url=pr_url,
        result_commits=result_commits if result_commits is not None else [],
        error=error,
        claimed_by=claimed_by,
        lease_expires_at=lease_expires_at,
        included_child_ids=included_child_ids if included_child_ids is not None else [],
    )


def _make_issue(
    identifier: str = "TASK-1",
    issue_type: str = "task",
    state: str = OPEN,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="desc",
        state=state,
        labels=[],
        issue_type=issue_type,
    )


def _make_tracker(
    all_issues: list[Issue] | None = None,
    metadata_map: dict[str, dict] | None = None,
) -> MagicMock:
    """Build a minimal mock tracker."""
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(all_issues or [])

    _meta = dict(metadata_map or {})

    def _get_meta(identifier: str) -> dict:
        return _meta.get(identifier, {})

    tracker.get_metadata.side_effect = _get_meta
    return tracker


def _make_store(tmp_path: Path, project_id: str = "proj-123") -> ReleaseDeliveryStore:
    """Return a filesystem-only store (no git writer)."""
    return ReleaseDeliveryStore(project_root=tmp_path, project_id=project_id)


def _write_raw_ledger(tmp_path: Path, data: object) -> None:
    ledger_path = tmp_path / LEDGER_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _raw_addendum(
    *,
    addendum_id: str = "TASK-1/release/1.0",
    target_branch: str = "release/1.0",
    status: str = "open",
    commits: list[str] | None = None,
    work_branch: str = "oompah/release/TASK-1/release-1.0",
    worktree_key: str = "release-TASK-1-release-1.0",
    queued_at: str = _QUEUED_AT,
    **extra: Any,
) -> dict:
    d = {
        "id": addendum_id,
        "source_branch": "main",
        "target_branch": target_branch,
        "status": status,
        "commits": commits if commits is not None else [_SHA_A],
        "work_branch": work_branch,
        "worktree_key": worktree_key,
        "queued_at": queued_at,
    }
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# _all_commits_valid
# ---------------------------------------------------------------------------


class TestAllCommitsValid:
    def test_valid_sha_returns_true(self):
        assert _all_commits_valid([_SHA_A]) is True

    def test_multiple_valid_shas(self):
        assert _all_commits_valid([_SHA_A, _SHA_B, _SHA_C]) is True

    def test_empty_list_returns_true(self):
        # vacuous truth — no invalid commits
        assert _all_commits_valid([]) is True

    def test_sentinel_pending_returns_false(self):
        assert _all_commits_valid([_SENTINEL_PENDING]) is False

    def test_sentinel_no_commits_returns_false(self):
        assert _all_commits_valid([_SENTINEL_NO_COMMITS]) is False

    def test_short_hex_returns_false(self):
        assert _all_commits_valid(["abcdef0123456789"]) is False

    def test_uppercase_returns_false(self):
        assert _all_commits_valid(["A" * 40]) is False

    def test_mixed_valid_and_invalid(self):
        assert _all_commits_valid([_SHA_A, _SENTINEL_PENDING]) is False


# ---------------------------------------------------------------------------
# _make_delivery_id
# ---------------------------------------------------------------------------


class TestMakeDeliveryId:
    def test_has_rd_prefix(self):
        assert _make_delivery_id().startswith("rd_")

    def test_unique_on_each_call(self):
        ids = {_make_delivery_id() for _ in range(50)}
        assert len(ids) == 50

    def test_hex_body(self):
        did = _make_delivery_id()
        body = did[len("rd_"):]
        assert len(body) == 32
        assert all(c in "0123456789abcdef" for c in body)


# ---------------------------------------------------------------------------
# _infer_source_kind
# ---------------------------------------------------------------------------


class TestInferSourceKind:
    def test_epic_string(self):
        assert _infer_source_kind("epic") == SourceKind.EPIC

    def test_epic_uppercase(self):
        assert _infer_source_kind("EPIC") == SourceKind.EPIC

    def test_task_string(self):
        assert _infer_source_kind("task") == SourceKind.TASK

    def test_chore_string(self):
        assert _infer_source_kind("chore") == SourceKind.TASK

    def test_empty_string(self):
        assert _infer_source_kind("") == SourceKind.TASK

    def test_none_coerces_to_task(self):
        assert _infer_source_kind(None) == SourceKind.TASK


# ---------------------------------------------------------------------------
# build_delivery_from_addendum
# ---------------------------------------------------------------------------


class TestBuildDeliveryFromAddendum:
    def test_migrated_from_set_to_addendum_id(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.migrated_from == "TASK-1/release/1.0"

    def test_source_identifier_set(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.source_identifier == "TASK-1"

    def test_source_kind_task(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.source_kind == SourceKind.TASK

    def test_source_kind_epic(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "EPIC-1", SourceKind.EPIC, "proj-123"
        )
        assert delivery.source_kind == SourceKind.EPIC

    def test_project_id_set(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-abc"
        )
        assert delivery.project_id == "proj-abc"

    def test_source_branch_preserved(self):
        addendum = _make_addendum(source_branch="main")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.source_branch == "main"

    def test_target_branch_preserved(self):
        addendum = _make_addendum(target_branch="release/2.0")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.target_branch == "release/2.0"

    def test_source_commits_preserved(self):
        addendum = _make_addendum(commits=[_SHA_A, _SHA_B])
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.source_commits == [_SHA_A, _SHA_B]

    def test_status_preserved(self):
        for status in AddendumStatus:
            addendum = _make_addendum(status=status)
            delivery = build_delivery_from_addendum(
                addendum, "TASK-1", SourceKind.TASK, "proj-123"
            )
            assert delivery.status == status, (
                f"Expected status {status!r} to be preserved"
            )

    def test_queued_at_preserved(self):
        addendum = _make_addendum(queued_at="2025-12-31T10:00:00Z")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.queued_at == "2025-12-31T10:00:00Z"

    def test_work_branch_preserved(self):
        addendum = _make_addendum(work_branch="oompah/release/FOO-10/release-1.0")
        delivery = build_delivery_from_addendum(
            addendum, "FOO-10", SourceKind.TASK, "proj-123"
        )
        assert delivery.work_branch == "oompah/release/FOO-10/release-1.0"

    def test_pr_url_preserved(self):
        addendum = _make_addendum(pr_url="https://github.com/org/repo/pull/42")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.pr_url == "https://github.com/org/repo/pull/42"

    def test_result_commits_preserved(self):
        addendum = _make_addendum(result_commits=[_SHA_RESULT])
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.result_commits == [_SHA_RESULT]

    def test_error_preserved(self):
        addendum = _make_addendum(error="cherry-pick conflict")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.error == "cherry-pick conflict"

    def test_started_at_preserved(self):
        addendum = _make_addendum(started_at=_STARTED_AT)
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.started_at == _STARTED_AT

    def test_completed_at_preserved(self):
        addendum = _make_addendum(completed_at=_COMPLETED_AT)
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.completed_at == _COMPLETED_AT

    def test_claimed_by_preserved(self):
        addendum = _make_addendum(claimed_by="worker-1")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.claimed_by == "worker-1"

    def test_lease_expires_at_preserved(self):
        addendum = _make_addendum(lease_expires_at=_LEASE_EXPIRES_AT)
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.lease_expires_at == _LEASE_EXPIRES_AT

    def test_custom_delivery_id_used(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123",
            delivery_id="rd_custom123",
        )
        assert delivery.id == "rd_custom123"

    def test_generated_id_when_none(self):
        addendum = _make_addendum()
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.id.startswith("rd_")
        assert len(delivery.id) > 3

    def test_sentinel_pending_raises_value_error(self):
        addendum = _make_addendum(commits=[_SENTINEL_PENDING])
        with pytest.raises(ValueError, match="invalid source_commits"):
            build_delivery_from_addendum(
                addendum, "TASK-1", SourceKind.TASK, "proj-123"
            )

    def test_sentinel_no_commits_raises_value_error(self):
        addendum = _make_addendum(commits=[_SENTINEL_NO_COMMITS])
        with pytest.raises(ValueError, match="invalid source_commits"):
            build_delivery_from_addendum(
addendum, "TASK-1", SourceKind.TASK, "proj-123"
            )

    def test_non_sha_string_raises_value_error(self):
        addendum = _make_addendum(commits=["not-a-sha"])
        with pytest.raises(ValueError, match="invalid source_commits"):
            build_delivery_from_addendum(
                addendum, "TASK-1", SourceKind.TASK, "proj-123"
            )

    def test_mixed_valid_and_sentinel_raises(self):
        addendum = _make_addendum(commits=[_SHA_A, _SENTINEL_PENDING])
        with pytest.raises(ValueError, match="invalid source_commits"):
            build_delivery_from_addendum(
                addendum, "TASK-1", SourceKind.TASK, "proj-123"
            )

    def test_sentinel_hint_in_error_message(self):
        addendum = _make_addendum(commits=[_SENTINEL_PENDING])
        with pytest.raises(ValueError, match="OOMPAH-183"):
            build_delivery_from_addendum(
                addendum, "TASK-1", SourceKind.TASK, "proj-123"
            )

    def test_pr_number_none(self):
        """ReleaseAddendum has no pr_number field; delivery.pr_number must be None."""
        addendum = _make_addendum(pr_url="https://github.com/org/repo/pull/7")
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        assert delivery.pr_number is None

    def test_source_commits_is_copy(self):
        """Mutations to the addendum's commits must not affect the delivery."""
        original_commits = [_SHA_A, _SHA_B]
        addendum = _make_addendum(commits=original_commits)
        delivery = build_delivery_from_addendum(
            addendum, "TASK-1", SourceKind.TASK, "proj-123"
        )
        original_commits.append(_SHA_C)
        assert delivery.source_commits == [_SHA_A, _SHA_B]


# ---------------------------------------------------------------------------
# AddendumMigrationResult
# ---------------------------------------------------------------------------


class TestAddendumMigrationResult:
    def test_changed_false_when_empty(self):
        r = AddendumMigrationResult()
        assert r.changed is False

    def test_changed_true_when_migrated(self):
        r = AddendumMigrationResult(migrated=1)
        assert r.changed is True

    def test_changed_false_with_only_skipped_duplicate(self):
        r = AddendumMigrationResult(skipped_duplicate=3)
        assert r.changed is False

    def test_changed_false_with_only_skipped_malformed(self):
        r = AddendumMigrationResult(skipped_malformed=2)
        assert r.changed is False

    def test_changed_false_with_only_errors(self):
        r = AddendumMigrationResult(errors=5)
        assert r.changed is False

    def test_default_counts_all_zero(self):
        r = AddendumMigrationResult()
        assert r.issues_scanned == 0
        assert r.migrated == 0
        assert r.skipped_duplicate == 0
        assert r.skipped_malformed == 0
        assert r.errors == 0


# ---------------------------------------------------------------------------
# run_addendum_migration — basic migration
# ---------------------------------------------------------------------------


class TestRunAddendumMigrationBasic:
    def test_no_issues(self, tmp_path):
        store = _make_store(tmp_path)
        tracker = _make_tracker()
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 0
        assert result.issues_scanned == 0
        assert not store.read_ledger().deliveries

    def test_migrates_task_addendum(self, tmp_path):
        issue = _make_issue("TASK-1", issue_type="task")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [_raw_addendum()]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.issues_scanned == 1
        deliveries = store.read_ledger().deliveries
        assert len(deliveries) == 1
        d = deliveries[0]
        assert d.source_kind == SourceKind.TASK
        assert d.source_identifier == "TASK-1"
        assert d.migrated_from == "TASK-1/release/1.0"

    def test_migrates_epic_addendum(self, tmp_path):
        issue = _make_issue("EPIC-1", issue_type="epic")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "EPIC-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="EPIC-1/release/1.0",
                            work_branch="oompah/release/EPIC-1/release-1.0",
                            worktree_key="release-EPIC-1-release-1.0",
                        )
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        deliveries = store.read_ledger().deliveries
        assert deliveries[0].source_kind == SourceKind.EPIC
        assert deliveries[0].source_identifier == "EPIC-1"

    def test_migrates_multiple_addendums_on_one_issue(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="TASK-1/release/1.0",
                            target_branch="release/1.0",
                        ),
                        _raw_addendum(
                            addendum_id="TASK-1/release/2.0",
                            target_branch="release/2.0",
                            work_branch="oompah/release/TASK-1/release-2.0",
                            worktree_key="release-TASK-1-release-2.0",
                        ),
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 2
        assert len(store.read_ledger().deliveries) == 2

    def test_migrates_addendums_across_multiple_issues(self, tmp_path):
        issues = [_make_issue("TASK-1"), _make_issue("TASK-2")]
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]},
                "TASK-2": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="TASK-2/release/1.0",
                            work_branch="oompah/release/TASK-2/release-1.0",
                            worktree_key="release-TASK-2-release-1.0",
                        )
                    ]
                },
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 2
        assert result.issues_scanned == 2

    def test_issues_with_no_addendums_skipped(self, tmp_path):
        issues = [_make_issue("TASK-1"), _make_issue("TASK-2")]
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {},  # no addendums
                "TASK-2": {"oompah.release_addendums": [_raw_addendum(addendum_id="TASK-2/release/1.0", work_branch="oompah/release/TASK-2/release-1.0", worktree_key="release-TASK-2-release-1.0")]},
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.issues_scanned == 1


# ---------------------------------------------------------------------------
# All lifecycle statuses migrated correctly
# ---------------------------------------------------------------------------


class TestAllStatusesMigrated:
    @pytest.mark.parametrize("status", list(AddendumStatus))
    def test_status_preserved(self, tmp_path, status):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(status=status.value)
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        deliveries = store.read_ledger().deliveries
        assert deliveries[0].status == status


# ---------------------------------------------------------------------------
# Terminal items are included (archived, merged, done tasks)
# ---------------------------------------------------------------------------


class TestTerminalItemsIncluded:
    @pytest.mark.parametrize("task_state", [MERGED, ARCHIVED, "Done"])
    def test_terminal_task_state_migrated(self, tmp_path, task_state):
        issue = _make_issue("TASK-OLD", state=task_state)
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-OLD": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="TASK-OLD/release/1.0",
                            status="merged",
                            work_branch="oompah/release/TASK-OLD/release-1.0",
                            worktree_key="release-TASK-OLD-release-1.0",
                        )
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1

    def test_epic_in_done_state_migrated(self, tmp_path):
        epic = _make_issue("EPIC-OLD", issue_type="epic", state="Done")
        tracker = _make_tracker(
            all_issues=[epic],
            metadata_map={
                "EPIC-OLD": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="EPIC-OLD/release/1.0",
                            status="archived",
                            work_branch="oompah/release/EPIC-OLD/release-1.0",
                            worktree_key="release-EPIC-OLD-release-1.0",
                        )
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1


# ---------------------------------------------------------------------------
# Sentinel commits → skipped_malformed
# ---------------------------------------------------------------------------


class TestSentinelCommitsSkipped:
    def test_sentinel_pending_skipped(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(commits=[_SENTINEL_PENDING])
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 0
        assert result.skipped_malformed == 1
        assert not store.read_ledger().deliveries

    def test_sentinel_no_commits_skipped(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(commits=[_SENTINEL_NO_COMMITS])
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 0
        assert result.skipped_malformed == 1

    def test_sentinel_does_not_block_valid_on_same_issue(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="TASK-1/release/1.0",
                            commits=[_SENTINEL_PENDING],
                        ),
                        _raw_addendum(
                            addendum_id="TASK-1/release/2.0",
                            target_branch="release/2.0",
                            work_branch="oompah/release/TASK-1/release-2.0",
                            worktree_key="release-TASK-1-release-2.0",
                            commits=[_SHA_A],
                        ),
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.skipped_malformed == 1
        deliveries = store.read_ledger().deliveries
        assert len(deliveries) == 1
        assert deliveries[0].target_branch == "release/2.0"


# ---------------------------------------------------------------------------
# Malformed records
# ---------------------------------------------------------------------------


class TestMalformedRecords:
    def test_malformed_addendum_dict_skipped(self, tmp_path):
        """Addendum missing required fields is skipped with skipped_malformed."""
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        {"id": "", "target_branch": "release/1.0"}  # missing many fields
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 0
        assert result.skipped_malformed == 1

    def test_malformed_entry_does_not_block_valid_entry_on_same_issue(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        {"id": ""},  # malformed
                        _raw_addendum(
                            addendum_id="TASK-1/release/2.0",
                            target_branch="release/2.0",
                            work_branch="oompah/release/TASK-1/release-2.0",
                            worktree_key="release-TASK-1-release-2.0",
                        ),
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.skipped_malformed == 1

    def test_malformed_entry_on_one_issue_does_not_block_other_issues(self, tmp_path):
        issues = [_make_issue("TASK-1"), _make_issue("TASK-2")]
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        {"id": "broken", "status": "not_a_real_status"}
                    ]
                },
                "TASK-2": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="TASK-2/release/1.0",
                            work_branch="oompah/release/TASK-2/release-1.0",
                            worktree_key="release-TASK-2-release-1.0",
                        )
                    ]
                },
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.skipped_malformed >= 1

    def test_unexpected_addendums_type_skipped(self, tmp_path):
        """oompah.release_addendums that is a bare string is skipped."""
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {"oompah.release_addendums": "not_a_list"}
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 0
        assert result.skipped_malformed == 1

    def test_non_dict_entry_in_list_skipped(self, tmp_path):
        """An entry that is not a dict is skipped as malformed."""
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        "not_a_dict",
                        _raw_addendum(
                            addendum_id="TASK-1/release/2.0",
                            target_branch="release/2.0",
                            work_branch="oompah/release/TASK-1/release-2.0",
                            worktree_key="release-TASK-1-release-2.0",
                        ),
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.skipped_malformed == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_run_produces_no_new_records(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]}
            },
        )
        store = _make_store(tmp_path)

        result1 = run_addendum_migration(tracker, store, "proj-123")
        assert result1.migrated == 1

        result2 = run_addendum_migration(tracker, store, "proj-123")
        assert result2.migrated == 0
        assert result2.skipped_duplicate == 1
        assert result2.changed is False

        # Ledger must still have exactly one entry.
        assert len(store.read_ledger().deliveries) == 1

    def test_second_run_counts_skipped_duplicate(self, tmp_path):
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(addendum_id="TASK-1/release/1.0"),
                        _raw_addendum(
                            addendum_id="TASK-1/release/2.0",
                            target_branch="release/2.0",
                            work_branch="oompah/release/TASK-1/release-2.0",
                            worktree_key="release-TASK-1-release-2.0",
                        ),
                    ]
                }
            },
        )
        store = _make_store(tmp_path)
        run_addendum_migration(tracker, store, "proj-123")
        result2 = run_addendum_migration(tracker, store, "proj-123")
        assert result2.skipped_duplicate == 2
        assert result2.migrated == 0

    def test_partial_migration_completed_on_second_run(self, tmp_path):
        """Simulate a first run that only migrated one of two addendums."""
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        _raw_addendum(addendum_id="TASK-1/release/1.0"),
                        _raw_addendum(
                            addendum_id="TASK-1/release/2.0",
                            target_branch="release/2.0",
                            work_branch="oompah/release/TASK-1/release-2.0",
                            worktree_key="release-TASK-1-release-2.0",
                        ),
                    ]
                }
            },
        )
        store = _make_store(tmp_path)

        # Simulate partial first run: pre-populate one delivery.
        from oompah.release_addendum_migration import build_delivery_from_addendum
        from oompah.release_addendum_schema import ReleaseAddendum as RA

        partial_addendum = RA.from_raw(_raw_addendum(addendum_id="TASK-1/release/1.0"))
        partial_delivery = build_delivery_from_addendum(
            partial_addendum, "TASK-1", SourceKind.TASK, "proj-123",
            delivery_id="rd_partial",
        )
        store.append(partial_delivery)

        # Second run should migrate only the missing release/2.0 entry.
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.migrated == 1
        assert result.skipped_duplicate == 1

        deliveries = store.read_ledger().deliveries
        assert len(deliveries) == 2
        migrated_from_values = {d.migrated_from for d in deliveries}
        assert migrated_from_values == {"TASK-1/release/1.0", "TASK-1/release/2.0"}

    def test_no_commit_when_nothing_changes(self, tmp_path):
        """When all addendums are already migrated, the store is not written."""
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={"TASK-1": {"oompah.release_addendums": [_raw_addendum()]}},
        )
        store = _make_store(tmp_path)
        run_addendum_migration(tracker, store, "proj-123")

        # Replace store internals with a spy to detect writes.
        original_write = store._write_ledger
        write_calls = []

        def _spy_write(ledger, subject):
            write_calls.append(subject)
            return original_write(ledger, subject)

        store._write_ledger = _spy_write

        # Second run must not write.
        run_addendum_migration(tracker, store, "proj-123")
        assert not write_calls, (
            "Expected no ledger write on second run, got: %s" % write_calls
        )


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_ledger_read_failure_aborts(self, tmp_path):
        """A malformed ledger aborts the migration and increments errors."""
        _write_raw_ledger(tmp_path, "this: is: not: valid: yaml: [")
        issue = _make_issue("TASK-1")
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={"TASK-1": {"oompah.release_addendums": [_raw_addendum()]}},
        )
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.errors == 1
        assert result.migrated == 0

    def test_fetch_all_issues_failure_aborts(self, tmp_path):
        """fetch_all_issues failure aborts migration and increments errors."""
        tracker = MagicMock()
        tracker.fetch_all_issues.side_effect = RuntimeError("network error")
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        assert result.errors == 1
        assert result.migrated == 0

    def test_get_metadata_failure_silently_skipped(self, tmp_path):
        """A tracker.get_metadata failure for one issue is silently skipped."""
        issue1 = _make_issue("TASK-1")
        issue2 = _make_issue("TASK-2")

        tracker = MagicMock()
        tracker.fetch_all_issues.return_value = [issue1, issue2]

        def _get_meta(identifier: str) -> dict:
            if identifier == "TASK-1":
                raise RuntimeError("metadata read error")
            return {
                "oompah.release_addendums": [
                    _raw_addendum(
                        addendum_id="TASK-2/release/1.0",
                        work_branch="oompah/release/TASK-2/release-1.0",
                        worktree_key="release-TASK-2-release-1.0",
                    )
                ]
            }

        tracker.get_metadata.side_effect = _get_meta
        store = _make_store(tmp_path)
        result = run_addendum_migration(tracker, store, "proj-123")
        # TASK-1 failure is silent; TASK-2 migrates normally.
        assert result.migrated == 1
        assert result.errors == 0

    def test_store_append_failure_increments_errors(self, tmp_path):
        """A store append failure for one delivery increments errors and continues."""
        issues = [_make_issue("TASK-1"), _make_issue("TASK-2")]
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]},
                "TASK-2": {
                    "oompah.release_addendums": [
                        _raw_addendum(
                            addendum_id="TASK-2/release/1.0",
                            work_branch="oompah/release/TASK-2/release-1.0",
                            worktree_key="release-TASK-2-release-1.0",
                        )
                    ]
                },
            },
        )
        store = _make_store(tmp_path)

        original_append = store.append
        call_count = {"n": 0}

        def _failing_append(delivery: ReleaseDelivery) -> ReleaseDelivery:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("disk full")
            return original_append(delivery)

        store.append = _failing_append
        result = run_addendum_migration(tracker, store, "proj-123")

        assert result.errors == 1
        assert result.migrated == 1  # Second issue's delivery succeeded.


# ---------------------------------------------------------------------------
# Evidence preservation (byte-for-byte round-trip)
# ---------------------------------------------------------------------------


class TestEvidenceRoundTrip:
    def test_all_evidence_fields_preserved(self, tmp_path):
        """All execution evidence fields are preserved byte-for-byte in the ledger."""
        issue = _make_issue("TASK-1")
        raw = _raw_addendum(
            addendum_id="TASK-1/release/1.0",
            status="in_review",
            commits=[_SHA_A, _SHA_B],
            pr_url="https://github.com/org/repo/pull/99",
            **{
                "started_at": _STARTED_AT,
                "completed_at": None,
                "result_commits": [_SHA_RESULT],
                "error": None,
                "claimed_by": "worker-42",
                "lease_expires_at": _LEASE_EXPIRES_AT,
            },
        )
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={"TASK-1": {"oompah.release_addendums": [raw]}},
        )
        store = _make_store(tmp_path)
        run_addendum_migration(tracker, store, "proj-123")

        d = store.read_ledger().deliveries[0]
        assert d.source_commits == [_SHA_A, _SHA_B]
        assert d.pr_url == "https://github.com/org/repo/pull/99"
        assert d.started_at == _STARTED_AT
        assert d.completed_at is None
        assert d.result_commits == [_SHA_RESULT]
        assert d.error is None
        assert d.claimed_by == "worker-42"
        assert d.lease_expires_at == _LEASE_EXPIRES_AT
        assert d.work_branch == "oompah/release/TASK-1/release-1.0"

    def test_error_field_preserved(self, tmp_path):
        issue = _make_issue("TASK-1")
        raw = _raw_addendum(status="blocked", **{"error": "cherry-pick conflict in foo.py"})
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={"TASK-1": {"oompah.release_addendums": [raw]}},
        )
        store = _make_store(tmp_path)
        run_addendum_migration(tracker, store, "proj-123")
        d = store.read_ledger().deliveries[0]
        assert d.error == "cherry-pick conflict in foo.py"

    def test_multiple_result_commits_preserved(self, tmp_path):
        issue = _make_issue("TASK-1")
        raw = _raw_addendum(
            status="merged",
            **{"result_commits": [_SHA_RESULT, _SHA_B]},
        )
        tracker = _make_tracker(
            all_issues=[issue],
            metadata_map={"TASK-1": {"oompah.release_addendums": [raw]}},
        )
        store = _make_store(tmp_path)
        run_addendum_migration(tracker, store, "proj-123")
        d = store.read_ledger().deliveries[0]
        assert d.result_commits == [_SHA_RESULT, _SHA_B]
