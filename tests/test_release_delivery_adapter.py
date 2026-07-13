"""Tests for oompah.release_delivery_adapter (OOMPAH-194).

Covers:
  - _addendum_to_delivery:
    - id has legacy: prefix
    - migrated_from set to addendum.id
    - all fields preserved
    - source_identifier, source_kind, project_id set correctly
  - _infer_source_kind (adapter module):
    - epic → EPIC
    - task and others → TASK
    - None → TASK
  - _parse_legacy_addendums_safe:
    - None/empty → empty list
    - valid list → parsed
    - dict → single item
    - malformed entries dropped silently
    - non-list/non-dict raw → empty list
  - DualReadDeliveryAdapter.list_deliveries_for_source:
    - empty ledger + no legacy addendums → empty list
    - ledger-only deliveries returned
    - legacy-only addendums returned as synthetic records
    - migrated addendum (in ledger with migrated_from) → not duplicated
    - non-migrated legacy addendum added alongside ledger records
    - mixed: some migrated, some not
    - malformed legacy addendum skipped (not included)
    - LedgerParseError propagated
    - tracker.get_metadata failure → empty legacy list (fallback)
    - tracker.fetch_issue_detail failure → source_kind defaults to TASK
  - DualReadDeliveryAdapter.list_all_deliveries:
    - empty everything → empty list
    - ledger entries returned in ledger order first
    - legacy addendums from all issues included when not migrated
    - migrated addendums (in ledger) suppressed from legacy
    - same addendum id on two issues only appears once (safety dedup)
    - fetch_all_issues failure → ledger-only fallback
    - LedgerParseError propagated
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from oompah.models import Issue
from oompah.release_addendum_schema import AddendumStatus, ReleaseAddendum
from oompah.release_delivery_adapter import (
    DualReadDeliveryAdapter,
    _addendum_to_delivery,
    _infer_source_kind,
    _parse_legacy_addendums_safe,
)
from oompah.release_delivery_store import (
    LEDGER_PATH,
    LedgerParseError,
    ReleaseDelivery,
    ReleaseDeliveryLedger,
    ReleaseDeliveryStore,
    SourceKind,
)
from oompah.statuses import OPEN

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_RESULT = "9" * 40
_QUEUED_AT = "2026-07-13T12:00:00Z"
_PROJECT_ID = "proj-123"


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
    pr_url: str | None = None,
    result_commits: list[str] | None = None,
    error: str | None = None,
    claimed_by: str | None = None,
    lease_expires_at: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
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
        pr_url=pr_url,
        result_commits=result_commits if result_commits is not None else [],
        error=error,
        claimed_by=claimed_by,
        lease_expires_at=lease_expires_at,
        started_at=started_at,
        completed_at=completed_at,
    )


def _make_delivery(
    *,
    delivery_id: str = "rd_001",
    project_id: str = _PROJECT_ID,
    source_branch: str = "main",
    source_kind: SourceKind = SourceKind.TASK,
    source_identifier: str | None = "TASK-1",
    source_commits: list[str] | None = None,
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    queued_at: str = _QUEUED_AT,
    migrated_from: str | None = None,
    **extra,
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=delivery_id,
        project_id=project_id,
        source_branch=source_branch,
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=source_commits if source_commits is not None else [_SHA_A],
        target_branch=target_branch,
        status=status,
        queued_at=queued_at,
        migrated_from=migrated_from,
        **extra,
    )


def _make_issue(
    identifier: str = "TASK-1",
    issue_type: str = "task",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="desc",
        state=OPEN,
        labels=[],
        issue_type=issue_type,
    )


def _make_store(
    tmp_path: Path,
    deliveries: list[ReleaseDelivery] | None = None,
    project_id: str = _PROJECT_ID,
) -> ReleaseDeliveryStore:
    store = ReleaseDeliveryStore(project_root=tmp_path, project_id=project_id)
    for delivery in (deliveries or []):
        store.append(delivery)
    return store


def _make_tracker(
    all_issues: list[Issue] | None = None,
    metadata_map: dict[str, dict] | None = None,
    detail_map: dict[str, Issue | None] | None = None,
) -> MagicMock:
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(all_issues or [])

    _meta = dict(metadata_map or {})

    def _get_meta(identifier: str) -> dict:
        return _meta.get(identifier, {})

    tracker.get_metadata.side_effect = _get_meta

    _detail = dict(detail_map or {})

    def _fetch_detail(identifier: str) -> Issue | None:
        return _detail.get(identifier)

    tracker.fetch_issue_detail.side_effect = _fetch_detail

    return tracker


def _raw_addendum(
    addendum_id: str = "TASK-1/release/1.0",
    target_branch: str = "release/1.0",
    status: str = "open",
    commits: list[str] | None = None,
    work_branch: str = "oompah/release/TASK-1/release-1.0",
    worktree_key: str = "release-TASK-1-release-1.0",
    queued_at: str = _QUEUED_AT,
    **extra,
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


def _write_malformed_ledger(tmp_path: Path) -> None:
    ledger_path = tmp_path / LEDGER_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("not: valid: yaml: [", encoding="utf-8")


# ---------------------------------------------------------------------------
# _addendum_to_delivery
# ---------------------------------------------------------------------------


class TestAddendumToDelivery:
    def test_id_has_legacy_prefix(self):
        addendum = _make_addendum(addendum_id="TASK-1/release/1.0")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.id == "legacy:TASK-1/release/1.0"

    def test_migrated_from_is_addendum_id(self):
        addendum = _make_addendum(addendum_id="TASK-1/release/1.0")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.migrated_from == "TASK-1/release/1.0"

    def test_source_identifier_set(self):
        addendum = _make_addendum()
        delivery = _addendum_to_delivery(
            addendum, "TASK-99", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.source_identifier == "TASK-99"

    def test_source_kind_epic(self):
        addendum = _make_addendum()
        delivery = _addendum_to_delivery(
            addendum, "EPIC-1", SourceKind.EPIC, _PROJECT_ID
        )
        assert delivery.source_kind == SourceKind.EPIC

    def test_project_id_set(self):
        addendum = _make_addendum()
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, "proj-xyz"
        )
        assert delivery.project_id == "proj-xyz"

    def test_source_branch_preserved(self):
        addendum = _make_addendum(source_branch="main")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.source_branch == "main"

    def test_target_branch_preserved(self):
        addendum = _make_addendum(target_branch="release/2.0")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.target_branch == "release/2.0"

    def test_commits_preserved_as_source_commits(self):
        addendum = _make_addendum(commits=[_SHA_A, _SHA_B])
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.source_commits == [_SHA_A, _SHA_B]

    def test_status_preserved(self):
        addendum = _make_addendum(status=AddendumStatus.IN_REVIEW)
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.status == AddendumStatus.IN_REVIEW

    def test_queued_at_preserved(self):
        addendum = _make_addendum(queued_at="2025-01-01T00:00:00Z")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.queued_at == "2025-01-01T00:00:00Z"

    def test_pr_url_preserved(self):
        addendum = _make_addendum(pr_url="https://github.com/org/repo/pull/7")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.pr_url == "https://github.com/org/repo/pull/7"

    def test_result_commits_preserved(self):
        addendum = _make_addendum(result_commits=[_SHA_RESULT])
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.result_commits == [_SHA_RESULT]

    def test_error_preserved(self):
        addendum = _make_addendum(error="conflict")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.error == "conflict"

    def test_work_branch_preserved(self):
        addendum = _make_addendum(work_branch="oompah/release/TASK-1/release-2.0")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.work_branch == "oompah/release/TASK-1/release-2.0"

    def test_claimed_by_preserved(self):
        addendum = _make_addendum(claimed_by="worker-x")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.claimed_by == "worker-x"

    def test_lease_expires_at_preserved(self):
        addendum = _make_addendum(lease_expires_at="2026-07-13T12:15:00Z")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.lease_expires_at == "2026-07-13T12:15:00Z"

    def test_pr_number_none(self):
        addendum = _make_addendum(pr_url="https://github.com/org/repo/pull/99")
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.pr_number is None

    def test_accepts_sentinel_commits(self):
        """Synthetic records may carry non-SHA commits (sentinels from OOMPAH-183)."""
        addendum = _make_addendum(commits=["migration-pending"])
        delivery = _addendum_to_delivery(
            addendum, "TASK-1", SourceKind.TASK, _PROJECT_ID
        )
        assert delivery.source_commits == ["migration-pending"]


# ---------------------------------------------------------------------------
# _infer_source_kind (adapter module)
# ---------------------------------------------------------------------------


class TestInferSourceKindAdapter:
    def test_epic(self):
        assert _infer_source_kind("epic") == SourceKind.EPIC

    def test_epic_uppercase(self):
        assert _infer_source_kind("EPIC") == SourceKind.EPIC

    def test_task(self):
        assert _infer_source_kind("task") == SourceKind.TASK

    def test_chore(self):
        assert _infer_source_kind("chore") == SourceKind.TASK

    def test_none(self):
        assert _infer_source_kind(None) == SourceKind.TASK

    def test_empty(self):
        assert _infer_source_kind("") == SourceKind.TASK


# ---------------------------------------------------------------------------
# _parse_legacy_addendums_safe
# ---------------------------------------------------------------------------


class TestParseLegacyAddendumsSafe:
    def test_none_returns_empty(self):
        assert _parse_legacy_addendums_safe(None, "TASK-1") == []

    def test_empty_list_returns_empty(self):
        assert _parse_legacy_addendums_safe([], "TASK-1") == []

    def test_valid_list_parsed(self):
        raw = [_raw_addendum()]
        result = _parse_legacy_addendums_safe(raw, "TASK-1")
        assert len(result) == 1
        assert result[0].id == "TASK-1/release/1.0"

    def test_dict_treated_as_single_item(self):
        raw = _raw_addendum()
        result = _parse_legacy_addendums_safe(raw, "TASK-1")
        assert len(result) == 1

    def test_malformed_entry_dropped_silently(self):
        raw = [{"id": ""}, _raw_addendum()]
        result = _parse_legacy_addendums_safe(raw, "TASK-1")
        assert len(result) == 1
        assert result[0].id == "TASK-1/release/1.0"

    def test_all_malformed_returns_empty(self):
        raw = [{"id": ""}, "not_a_dict"]
        result = _parse_legacy_addendums_safe(raw, "TASK-1")
        assert result == []

    def test_non_list_non_dict_returns_empty(self):
        result = _parse_legacy_addendums_safe("raw_string", "TASK-1")
        assert result == []

    def test_integer_value_returns_empty(self):
        result = _parse_legacy_addendums_safe(42, "TASK-1")
        assert result == []


# ---------------------------------------------------------------------------
# DualReadDeliveryAdapter.list_deliveries_for_source
# ---------------------------------------------------------------------------


class TestListDeliveriesForSource:
    def test_empty_ledger_no_legacy(self, tmp_path):
        store = _make_store(tmp_path)
        tracker = _make_tracker(metadata_map={"TASK-1": {}})
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert result == []

    def test_ledger_only_deliveries_returned(self, tmp_path):
        delivery = _make_delivery(delivery_id="rd_001", migrated_from=None)
        store = _make_store(tmp_path, deliveries=[delivery])
        tracker = _make_tracker(
            detail_map={"TASK-1": _make_issue("TASK-1")},
            metadata_map={"TASK-1": {}},
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert len(result) == 1
        assert result[0].id == "rd_001"

    def test_legacy_only_addendums_returned_as_synthetic(self, tmp_path):
        store = _make_store(tmp_path)
        tracker = _make_tracker(
            detail_map={"TASK-1": _make_issue("TASK-1")},
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]}
            },
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert len(result) == 1
        r = result[0]
        assert r.id == "legacy:TASK-1/release/1.0"
        assert r.migrated_from == "TASK-1/release/1.0"
        assert r.source_identifier == "TASK-1"

    def test_migrated_addendum_not_duplicated(self, tmp_path):
        """When a ledger entry exists with migrated_from matching a legacy addendum,
        only the ledger entry should appear — not both."""
        delivery = _make_delivery(
            delivery_id="rd_001",
            migrated_from="TASK-1/release/1.0",
        )
        store = _make_store(tmp_path, deliveries=[delivery])
        tracker = _make_tracker(
            detail_map={"TASK-1": _make_issue("TASK-1")},
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]}
            },
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert len(result) == 1
        assert result[0].id == "rd_001"  # ledger entry, not the legacy one

    def test_non_migrated_addendum_added_alongside_ledger(self, tmp_path):
        """A ledger entry for release/2.0 and a legacy addendum for release/1.0
        (not yet migrated) should both appear."""
        delivery = _make_delivery(
            delivery_id="rd_002",
            target_branch="release/2.0",
            migrated_from="TASK-1/release/2.0",
        )
        store = _make_store(tmp_path, deliveries=[delivery])
        tracker = _make_tracker(
            detail_map={"TASK-1": _make_issue("TASK-1")},
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
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert len(result) == 2
        ids = {r.id for r in result}
        assert "rd_002" in ids
        assert "legacy:TASK-1/release/1.0" in ids

    def test_malformed_legacy_addendum_skipped(self, tmp_path):
        """A malformed legacy addendum is skipped (not included in result)."""
        store = _make_store(tmp_path)
        tracker = _make_tracker(
            detail_map={"TASK-1": _make_issue("TASK-1")},
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [
                        {"id": ""},  # malformed: missing required fields
                    ]
                }
            },
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert result == []

    def test_ledger_parse_error_propagated(self, tmp_path):
        _write_malformed_ledger(tmp_path)
        store = _make_store(tmp_path)
        tracker = _make_tracker(metadata_map={"TASK-1": {}})
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        with pytest.raises(LedgerParseError):
            adapter.list_deliveries_for_source("TASK-1")

    def test_tracker_get_metadata_failure_returns_ledger_only(self, tmp_path):
        delivery = _make_delivery(delivery_id="rd_001", migrated_from=None)
        store = _make_store(tmp_path, deliveries=[delivery])

        tracker = MagicMock()
        tracker.get_metadata.side_effect = RuntimeError("metadata error")
        tracker.fetch_issue_detail.return_value = _make_issue("TASK-1")

        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        # Falls back to ledger-only when metadata read fails.
        assert len(result) == 1
        assert result[0].id == "rd_001"

    def test_fetch_issue_detail_failure_defaults_source_kind_to_task(self, tmp_path):
        store = _make_store(tmp_path)
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]}
            },
        )
        tracker.fetch_issue_detail.side_effect = RuntimeError("detail error")
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert len(result) == 1
        assert result[0].source_kind == SourceKind.TASK

    def test_ledger_entries_come_before_legacy_synthetic(self, tmp_path):
        """Ledger entries must appear before non-migrated legacy entries."""
        ledger_delivery = _make_delivery(
            delivery_id="rd_001",
            target_branch="release/2.0",
            migrated_from="TASK-1/release/2.0",
        )
        store = _make_store(tmp_path, deliveries=[ledger_delivery])
        tracker = _make_tracker(
            detail_map={"TASK-1": _make_issue("TASK-1")},
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
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("TASK-1")
        assert len(result) == 2
        assert result[0].id == "rd_001"  # ledger first
        assert result[1].id == "legacy:TASK-1/release/1.0"  # synthetic second

    def test_epic_source_kind_inferred(self, tmp_path):
        store = _make_store(tmp_path)
        tracker = _make_tracker(
            detail_map={"EPIC-1": _make_issue("EPIC-1", issue_type="epic")},
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
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_deliveries_for_source("EPIC-1")
        assert result[0].source_kind == SourceKind.EPIC


# ---------------------------------------------------------------------------
# DualReadDeliveryAdapter.list_all_deliveries
# ---------------------------------------------------------------------------


class TestListAllDeliveries:
    def test_empty_everything_returns_empty(self, tmp_path):
        store = _make_store(tmp_path)
        tracker = _make_tracker()
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        assert adapter.list_all_deliveries() == []

    def test_ledger_entries_in_order(self, tmp_path):
        d1 = _make_delivery(delivery_id="rd_001", source_identifier="TASK-1")
        d2 = _make_delivery(
            delivery_id="rd_002",
            source_identifier="TASK-2",
            target_branch="release/2.0",
        )
        store = _make_store(tmp_path, deliveries=[d1, d2])
        tracker = _make_tracker()
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        assert len(result) == 2
        assert result[0].id == "rd_001"
        assert result[1].id == "rd_002"

    def test_legacy_addendums_from_all_issues_included(self, tmp_path):
        store = _make_store(tmp_path)
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
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        assert len(result) == 2
        ids = {r.id for r in result}
        assert ids == {"legacy:TASK-1/release/1.0", "legacy:TASK-2/release/1.0"}

    def test_migrated_addendums_suppressed_from_legacy(self, tmp_path):
        delivery = _make_delivery(
            delivery_id="rd_001",
            migrated_from="TASK-1/release/1.0",
        )
        store = _make_store(tmp_path, deliveries=[delivery])
        issues = [_make_issue("TASK-1")]
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {
                    "oompah.release_addendums": [_raw_addendum()]
                }
            },
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        assert len(result) == 1
        assert result[0].id == "rd_001"

    def test_ledger_first_then_legacy(self, tmp_path):
        """Ledger entries appear before non-migrated legacy entries."""
        ledger_delivery = _make_delivery(
            delivery_id="rd_001",
            migrated_from="TASK-2/release/1.0",
            source_identifier="TASK-2",
        )
        store = _make_store(tmp_path, deliveries=[ledger_delivery])
        issues = [_make_issue("TASK-1")]  # TASK-2 addendum is in ledger (migrated)
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [_raw_addendum()]},
            },
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        assert len(result) == 2
        assert result[0].id == "rd_001"  # ledger first

    def test_same_addendum_id_on_two_issues_only_once(self, tmp_path):
        """Safety dedup: if same addendum.id appears on two different issues,
        only the first occurrence is included."""
        store = _make_store(tmp_path)
        # Two issues both claiming the same addendum ID (shouldn't happen, but be safe).
        issues = [_make_issue("TASK-1"), _make_issue("TASK-2")]
        same_raw = _raw_addendum(addendum_id="TASK-1/release/1.0")
        tracker = _make_tracker(
            all_issues=issues,
            metadata_map={
                "TASK-1": {"oompah.release_addendums": [same_raw]},
                "TASK-2": {"oompah.release_addendums": [same_raw]},
            },
        )
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        # Only one synthetic record for the same legacy ID.
        matching = [r for r in result if r.migrated_from == "TASK-1/release/1.0"]
        assert len(matching) == 1

    def test_fetch_all_issues_failure_returns_ledger_only(self, tmp_path):
        delivery = _make_delivery(delivery_id="rd_001")
        store = _make_store(tmp_path, deliveries=[delivery])

        tracker = MagicMock()
        tracker.fetch_all_issues.side_effect = RuntimeError("network error")

        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        assert len(result) == 1
        assert result[0].id == "rd_001"

    def test_ledger_parse_error_propagated(self, tmp_path):
        _write_malformed_ledger(tmp_path)
        store = _make_store(tmp_path)
        tracker = _make_tracker()
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        with pytest.raises(LedgerParseError):
            adapter.list_all_deliveries()

    def test_mixed_migrated_and_not_migrated(self, tmp_path):
        """Migration partial state: one release/1.0 migrated, one release/2.0 not yet."""
        ledger_delivery = _make_delivery(
            delivery_id="rd_001",
            target_branch="release/1.0",
            migrated_from="TASK-1/release/1.0",
        )
        store = _make_store(tmp_path, deliveries=[ledger_delivery])
        issues = [_make_issue("TASK-1")]
        tracker = _make_tracker(
            all_issues=issues,
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
        adapter = DualReadDeliveryAdapter(store, tracker, _PROJECT_ID)
        result = adapter.list_all_deliveries()
        assert len(result) == 2
        ids = {r.id for r in result}
        assert "rd_001" in ids  # migrated, ledger version
        assert "legacy:TASK-1/release/2.0" in ids  # not yet migrated
        # The migrated legacy addendum (release/1.0) must NOT appear as legacy.
        assert "legacy:TASK-1/release/1.0" not in ids
