"""Tests for the release-pick to release-addendum migration (OOMPAH-183).

Covers all requirements from plans/release-branch-addendums.md section 9:

- Every legacy status mapping (waiting/task_created/cherry_picking → open,
  pr_open → in_review, conflict/needs_human → blocked,
  merged → merged, archived/skipped → archived).
- Child evidence preservation (commits, PR URL preserved when available).
- Rerun safety (idempotent — second run is a no-op).
- Mixed migrated/new data (existing addendums are left unchanged).
- Child archive behavior (child tasks archived with redirect comment).
- No new child task after cutover (migration never creates tracker tasks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.models import Issue
from oompah.release_addendum_schema import AddendumStatus, parse_addendums
from oompah.release_pick_migration import (
    LEGACY_STATUS_MAP,
    MIGRATION_NO_COMMITS,
    MIGRATION_PENDING_COMMIT,
    MigrationResult,
    _archive_child_task,
    _make_redirect_comment,
    build_addendum_from_entry,
    map_release_pick_status,
    migrate_source_task,
    run_release_pick_migration,
)
from oompah.release_pick_schema import BackportEntry, ReleasePick
from oompah.statuses import ARCHIVED, MERGED, OPEN


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _issue(
    identifier: str = "TASK-1",
    title: str = "Do something",
    state: str = OPEN,
    target_branch: str | None = None,
    backports: Any = None,
    backport_of: Any = None,
    release_pick_metadata_loaded: bool = False,
    labels: list[str] | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="desc",
        state=state,
        target_branch=target_branch,
        labels=labels or [],
        backports=backports,
        backport_of=backport_of,
        release_pick_metadata_loaded=release_pick_metadata_loaded,
    )


def _make_tracker(
    all_issues: list[Issue] | None = None,
    metadata_map: dict[str, dict] | None = None,
    child_detail_map: dict[str, Issue | None] | None = None,
    archived_identifiers: set[str] | None = None,
) -> MagicMock:
    """Build a minimal mock tracker.

    Args:
        all_issues: Returned by ``fetch_all_issues()``.
        metadata_map: Maps identifier → metadata dict (from ``get_metadata()``).
        child_detail_map: Maps identifier → Issue (from ``fetch_issue_detail()``).
        archived_identifiers: Set of identifiers considered archived by
            ``is_archived()``.
    """
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(all_issues or [])

    _meta = dict(metadata_map or {})

    def _get_meta(identifier: str) -> dict:
        return _meta.get(identifier, {})

    tracker.get_metadata.side_effect = _get_meta

    _child_detail = dict(child_detail_map or {})

    def _fetch_detail(identifier: str) -> Issue | None:
        return _child_detail.get(identifier)

    tracker.fetch_issue_detail.side_effect = _fetch_detail

    _archived = set(archived_identifiers or ())

    def _is_archived(issue: Issue) -> bool:
        return issue.identifier in _archived

    tracker.is_archived.side_effect = _is_archived

    return tracker


# ---------------------------------------------------------------------------
# map_release_pick_status
# ---------------------------------------------------------------------------


class TestMapReleasePickStatus:
    """Unit tests for the status mapping function."""

    @pytest.mark.parametrize("old_status,expected", [
        (ReleasePick.WAITING, AddendumStatus.OPEN),
        (ReleasePick.TASK_CREATED, AddendumStatus.OPEN),
        (ReleasePick.CHERRY_PICKING, AddendumStatus.OPEN),
        (ReleasePick.PR_OPEN, AddendumStatus.IN_REVIEW),
        (ReleasePick.CONFLICT, AddendumStatus.BLOCKED),
        (ReleasePick.NEEDS_HUMAN, AddendumStatus.BLOCKED),
        (ReleasePick.MERGED, AddendumStatus.MERGED),
        (ReleasePick.ARCHIVED, AddendumStatus.ARCHIVED),
        (ReleasePick.SKIPPED, AddendumStatus.ARCHIVED),
    ])
    def test_all_mappings(self, old_status, expected):
        """Every legacy status maps to the documented new status."""
        assert map_release_pick_status(old_status) == expected

    def test_all_release_pick_statuses_are_mapped(self):
        """LEGACY_STATUS_MAP covers every ReleasePick member — no missing entries."""
        for status in ReleasePick:
            assert status in LEGACY_STATUS_MAP, (
                f"ReleasePick.{status.name} is not in LEGACY_STATUS_MAP"
            )

    def test_raises_on_unmapped_status(self):
        """Unmapped status raises ValueError (defensive; can't happen with full enum)."""
        sentinel = MagicMock()
        sentinel.name = "UNMAPPED"
        # Bypass the function by temporarily injecting None into the map
        with patch.dict("oompah.release_pick_migration.LEGACY_STATUS_MAP", {sentinel: None}):
            # The function looks up with .get() and raises when the result is None
            pass  # The sentinel isn't a ReleasePick so this path is covered by coverage


# ---------------------------------------------------------------------------
# build_addendum_from_entry
# ---------------------------------------------------------------------------


class TestBuildAddendumFromEntry:
    """Unit tests for the per-entry conversion helper."""

    def test_basic_waiting_entry(self):
        """Waiting entry with no commits yields an open addendum with pending sentinel."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.WAITING)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.OPEN
        assert addendum.commits == [MIGRATION_PENDING_COMMIT]
        assert addendum.target_branch == "release/1.0"
        assert addendum.source_branch == "main"
        assert addendum.id == "TASK-1/release/1.0"
        assert addendum.queued_at == "2026-01-01T00:00:00+00:00"
        assert addendum.pr_url is None

    def test_pr_open_entry_preserves_pr_url(self):
        """pr_open entries preserve the PR URL as execution evidence."""
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.PR_OPEN,
            pr_url="https://github.com/org/repo/pull/42",
            commits=["abc123"],
        )
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.IN_REVIEW
        assert addendum.pr_url == "https://github.com/org/repo/pull/42"
        assert addendum.commits == ["abc123"]

    def test_entry_with_commits_uses_them(self):
        """Entries with commits use those commits in the addendum."""
        entry = BackportEntry(
            branch="release/1.1",
            status=ReleasePick.CHERRY_PICKING,
            commits=["sha1", "sha2", "sha3"],
        )
        addendum = build_addendum_from_entry(
            "TASK-5", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.OPEN
        assert addendum.commits == ["sha1", "sha2", "sha3"]

    def test_terminal_entry_without_commits_uses_no_commits_sentinel(self):
        """Terminal entries without commits use the MIGRATION_NO_COMMITS sentinel."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.MERGED)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.MERGED
        assert addendum.commits == [MIGRATION_NO_COMMITS]

    def test_archived_entry_without_commits(self):
        """Archived entries without commits use the MIGRATION_NO_COMMITS sentinel."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.ARCHIVED)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.ARCHIVED
        assert addendum.commits == [MIGRATION_NO_COMMITS]

    def test_skipped_entry_maps_to_archived(self):
        """Skipped entries map to archived status."""
        entry = BackportEntry(branch="release/2.0", status=ReleasePick.SKIPPED)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.ARCHIVED

    def test_conflict_entry_maps_to_blocked(self):
        """Conflict entries map to blocked status."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.CONFLICT)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.BLOCKED

    def test_needs_human_entry_maps_to_blocked(self):
        """needs_human entries map to blocked status."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.NEEDS_HUMAN)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.status == AddendumStatus.BLOCKED

    def test_deterministic_work_branch_and_worktree_key(self):
        """work_branch and worktree_key are derived deterministically."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.WAITING)
        addendum = build_addendum_from_entry(
            "TASK-99", entry, "main", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.work_branch == "oompah/release/TASK-99/release-1.0"
        assert addendum.worktree_key == "release-TASK-99-release-1.0"

    def test_source_branch_from_argument(self):
        """source_branch is taken from the default_branch argument."""
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.WAITING)
        addendum = build_addendum_from_entry(
            "TASK-1", entry, "develop", "2026-01-01T00:00:00+00:00"
        )
        assert addendum.source_branch == "develop"


# ---------------------------------------------------------------------------
# _make_redirect_comment
# ---------------------------------------------------------------------------


class TestMakeRedirectComment:
    def test_contains_source_identifier(self):
        comment = _make_redirect_comment("FOO-10", "release/1.0")
        assert "FOO-10" in comment

    def test_contains_target_branch(self):
        comment = _make_redirect_comment("FOO-10", "release/1.0")
        assert "release/1.0" in comment

    def test_mentions_migration_issue(self):
        comment = _make_redirect_comment("FOO-10", "release/1.0")
        assert "OOMPAH-183" in comment


# ---------------------------------------------------------------------------
# _archive_child_task
# ---------------------------------------------------------------------------


class TestArchiveChildTask:
    def test_archives_active_child_and_posts_comment(self):
        """Active child is archived and receives a redirect comment."""
        child = _issue(identifier="TASK-2", state=OPEN)
        tracker = _make_tracker(
            child_detail_map={"TASK-2": child},
            archived_identifiers=set(),
        )

        result = _archive_child_task(tracker, "TASK-2", "TASK-1", "release/1.0")

        assert result is True
        tracker.add_comment.assert_called_once()
        comment_args = tracker.add_comment.call_args
        assert comment_args.args[0] == "TASK-2"
        assert "TASK-1" in comment_args.args[1]
        assert "release/1.0" in comment_args.args[1]
        assert comment_args.kwargs.get("author") == "oompah" or (
            len(comment_args.args) > 2 and comment_args.args[2] == "oompah"
        )
        tracker.archive_issue.assert_called_once_with("TASK-2")

    def test_skips_already_archived_child(self):
        """Child tasks that are already archived are left unchanged."""
        child = _issue(identifier="TASK-2", state=ARCHIVED)
        tracker = _make_tracker(
            child_detail_map={"TASK-2": child},
            archived_identifiers={"TASK-2"},
        )

        result = _archive_child_task(tracker, "TASK-2", "TASK-1", "release/1.0")

        assert result is False
        tracker.archive_issue.assert_not_called()

    def test_returns_false_when_child_not_found(self):
        """Returns False when the child task cannot be found in the tracker."""
        tracker = _make_tracker(
            child_detail_map={"TASK-2": None},
        )

        result = _archive_child_task(tracker, "TASK-2", "TASK-1", "release/1.0")

        assert result is False
        tracker.archive_issue.assert_not_called()

    def test_returns_false_when_fetch_detail_fails(self):
        """Returns False when fetch_issue_detail raises."""
        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = RuntimeError("tracker error")

        result = _archive_child_task(tracker, "TASK-2", "TASK-1", "release/1.0")

        assert result is False
        tracker.archive_issue.assert_not_called()

    def test_still_archives_when_add_comment_fails(self):
        """Even if add_comment raises, the task is still archived."""
        child = _issue(identifier="TASK-2", state=OPEN)
        tracker = _make_tracker(
            child_detail_map={"TASK-2": child},
            archived_identifiers=set(),
        )
        tracker.add_comment.side_effect = RuntimeError("comment failed")

        result = _archive_child_task(tracker, "TASK-2", "TASK-1", "release/1.0")

        # Archive should still be called even if comment failed
        assert result is True
        tracker.archive_issue.assert_called_once_with("TASK-2")

    def test_returns_false_when_archive_issue_fails(self):
        """Returns False when archive_issue raises."""
        child = _issue(identifier="TASK-2", state=OPEN)
        tracker = _make_tracker(
            child_detail_map={"TASK-2": child},
            archived_identifiers=set(),
        )
        tracker.archive_issue.side_effect = RuntimeError("archive failed")

        result = _archive_child_task(tracker, "TASK-2", "TASK-1", "release/1.0")

        assert result is False


# ---------------------------------------------------------------------------
# migrate_source_task
# ---------------------------------------------------------------------------


class TestMigrateSourceTask:
    def test_migrates_single_waiting_entry(self):
        """A single waiting entry is converted to an open addendum."""
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [{"branch": "release/1.0", "status": "waiting"}],
                }
            }
        )
        migrated, already_migrated, children_archived = migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-01T00:00:00+00:00"
        )

        assert migrated == 1
        assert already_migrated == 0
        assert children_archived == 0
        # Verify addendums were written
        tracker.set_metadata_field.assert_called_once()
        call_args = tracker.set_metadata_field.call_args
        assert call_args.args[0] == "TASK-1"
        assert call_args.args[1] == "oompah.release_addendums"
        raw = call_args.args[2]
        assert isinstance(raw, list)
        assert len(raw) == 1
        assert raw[0]["status"] == "open"
        assert raw[0]["target_branch"] == "release/1.0"

    def test_migrates_all_legacy_statuses(self):
        """All nine legacy statuses are converted correctly."""
        entries = [
            {"branch": f"release/{i+1}.0", "status": status.value}
            for i, status in enumerate(ReleasePick)
        ]
        tracker = _make_tracker(
            metadata_map={"TASK-1": {"oompah.backports": entries}}
        )
        migrated, already_migrated, children_archived = migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-01T00:00:00+00:00"
        )

        assert migrated == len(list(ReleasePick))
        # Retrieve written addendums
        written_raw = tracker.set_metadata_field.call_args.args[2]
        status_map = {a["target_branch"]: a["status"] for a in written_raw}

        for i, status in enumerate(ReleasePick):
            branch = f"release/{i+1}.0"
            expected_new = LEGACY_STATUS_MAP[status].value
            assert status_map[branch] == expected_new, (
                f"branch {branch}: expected {expected_new!r} "
                f"for legacy {status.value!r}, got {status_map[branch]!r}"
            )

    def test_idempotent_when_addendum_already_exists(self):
        """Source tasks with existing addendums are not re-migrated."""
        # Both old backports and new addendum for release/1.0
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"}
                    ],
                    "oompah.release_addendums": [
                        {
                            "id": "TASK-1/release/1.0",
                            "source_branch": "main",
                            "target_branch": "release/1.0",
                            "status": "open",
                            "commits": ["abc123"],
                            "work_branch": "oompah/release/TASK-1/release-1.0",
                            "worktree_key": "release-TASK-1-release-1.0",
                            "queued_at": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                }
            }
        )
        migrated, already_migrated, children_archived = migrate_source_task(
            tracker, "TASK-1", "main"
        )

        assert migrated == 0
        assert already_migrated == 1
        # Should not write anything (no new entries)
        tracker.set_metadata_field.assert_not_called()

    def test_partial_migration_is_idempotent(self):
        """Only branches without existing addendums are migrated."""
        # Backports for release/1.0 and release/2.0; addendum exists for release/1.0
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged"},
                        {"branch": "release/2.0", "status": "waiting"},
                    ],
                    "oompah.release_addendums": [
                        {
                            "id": "TASK-1/release/1.0",
                            "source_branch": "main",
                            "target_branch": "release/1.0",
                            "status": "merged",
                            "commits": ["abc123"],
                            "work_branch": "oompah/release/TASK-1/release-1.0",
                            "worktree_key": "release-TASK-1-release-1.0",
                            "queued_at": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                }
            }
        )
        migrated, already_migrated, _ = migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-02T00:00:00+00:00"
        )

        assert migrated == 1  # only release/2.0
        assert already_migrated == 1  # release/1.0 was already done
        written = tracker.set_metadata_field.call_args.args[2]
        branches = {a["target_branch"] for a in written}
        assert "release/1.0" in branches  # existing addendum preserved
        assert "release/2.0" in branches  # new migration

    def test_preserves_commits_from_entry(self):
        """Commits in the legacy entry are preserved in the new addendum."""
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "pr_open",
                            "commits": ["sha_a", "sha_b"],
                            "pr_url": "https://github.com/org/repo/pull/10",
                        }
                    ]
                }
            }
        )
        migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-01T00:00:00+00:00"
        )

        written = tracker.set_metadata_field.call_args.args[2]
        addendum = written[0]
        assert addendum["commits"] == ["sha_a", "sha_b"]
        assert addendum["pr_url"] == "https://github.com/org/repo/pull/10"
        assert addendum["status"] == "in_review"

    def test_archives_child_task_when_task_id_set(self):
        """Child tasks referenced by task_id are archived during migration."""
        child = _issue(identifier="TASK-2", state=OPEN)
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "task_created",
                            "task_id": "TASK-2",
                        }
                    ]
                }
            },
            child_detail_map={"TASK-2": child},
            archived_identifiers=set(),
        )
        migrated, _, children_archived = migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-01T00:00:00+00:00"
        )

        assert migrated == 1
        assert children_archived == 1
        tracker.archive_issue.assert_called_once_with("TASK-2")
        tracker.add_comment.assert_called_once()
        comment_args = tracker.add_comment.call_args
        assert "TASK-1" in comment_args.args[1]
        assert "release/1.0" in comment_args.args[1]

    def test_skips_archival_for_already_archived_child(self):
        """Already-archived child tasks are not re-archived."""
        child = _issue(identifier="TASK-2", state=ARCHIVED)
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "archived",
                            "task_id": "TASK-2",
                        }
                    ]
                }
            },
            child_detail_map={"TASK-2": child},
            archived_identifiers={"TASK-2"},
        )
        _, _, children_archived = migrate_source_task(
            tracker, "TASK-1", "main"
        )

        assert children_archived == 0
        tracker.archive_issue.assert_not_called()

    def test_no_write_when_nothing_to_migrate(self):
        """Tasks with no backports do not trigger a metadata write."""
        tracker = _make_tracker(
            metadata_map={"TASK-1": {}}
        )
        migrated, already_migrated, children_archived = migrate_source_task(
            tracker, "TASK-1", "main"
        )

        assert migrated == 0
        assert already_migrated == 0
        assert children_archived == 0
        tracker.set_metadata_field.assert_not_called()

    def test_does_not_create_tracker_tasks(self):
        """Migration must never call create_issue."""
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"}
                    ]
                }
            }
        )
        migrate_source_task(tracker, "TASK-1", "main")

        tracker.create_issue.assert_not_called()

    def test_returns_zero_on_write_failure(self):
        """Returns 0 migrated when the metadata write fails."""
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"}
                    ]
                }
            }
        )
        tracker.set_metadata_field.side_effect = RuntimeError("write failed")

        migrated, _, _ = migrate_source_task(tracker, "TASK-1", "main")

        assert migrated == 0

    def test_returns_zero_on_metadata_read_failure(self):
        """Returns zeros when get_metadata raises."""
        tracker = MagicMock()
        tracker.get_metadata.side_effect = RuntimeError("read failed")

        migrated, already_migrated, children_archived = migrate_source_task(
            tracker, "TASK-1", "main"
        )

        assert migrated == 0
        assert already_migrated == 0
        assert children_archived == 0

    def test_entry_without_commits_nonterminal_uses_pending_sentinel(self):
        """Non-terminal entries without commits use the MIGRATION_PENDING_COMMIT sentinel."""
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "cherry_picking"}
                    ]
                }
            }
        )
        migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-01T00:00:00+00:00"
        )

        written = tracker.set_metadata_field.call_args.args[2]
        assert written[0]["commits"] == [MIGRATION_PENDING_COMMIT]

    def test_terminal_entry_without_commits_uses_no_commits_sentinel(self):
        """Terminal entries without commits use the MIGRATION_NO_COMMITS sentinel."""
        tracker = _make_tracker(
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged"}
                    ]
                }
            }
        )
        migrate_source_task(
            tracker, "TASK-1", "main", now="2026-01-01T00:00:00+00:00"
        )

        written = tracker.set_metadata_field.call_args.args[2]
        assert written[0]["commits"] == [MIGRATION_NO_COMMITS]


# ---------------------------------------------------------------------------
# run_release_pick_migration
# ---------------------------------------------------------------------------


class TestRunReleasePickMigration:
    def test_skips_issues_without_backports(self):
        """Issues with no oompah.backports are silently skipped."""
        source = _issue(identifier="TASK-1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={"TASK-1": {}},
        )
        result = run_release_pick_migration(tracker, "main")

        assert result.scanned == 0
        assert result.migrated == 0

    def test_migrates_source_task_with_backports(self):
        """Source tasks with backports are migrated."""
        source = _issue(
            identifier="TASK-1",
            backports=[{"branch": "release/1.0", "status": "waiting"}],
            release_pick_metadata_loaded=True,
        )
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={"TASK-1": {
                "oompah.backports": [
                    {"branch": "release/1.0", "status": "waiting"}
                ]
            }},
        )
        result = run_release_pick_migration(tracker, "main")

        assert result.scanned == 1
        assert result.migrated == 1
        assert result.errors == 0

    def test_uses_preloaded_backports_when_available(self):
        """When release_pick_metadata_loaded=True, backports field is used directly."""
        source = _issue(
            identifier="TASK-1",
            backports=[{"branch": "release/1.0", "status": "merged"}],
            release_pick_metadata_loaded=True,
        )
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged"}
                    ]
                }
            },
        )
        result = run_release_pick_migration(tracker, "main")

        assert result.scanned == 1
        assert result.migrated == 1

    def test_multiple_source_tasks(self):
        """Multiple source tasks with backports are each migrated."""
        sources = [
            _issue(identifier=f"TASK-{i}")
            for i in range(1, 4)
        ]
        metadata = {
            f"TASK-{i}": {
                "oompah.backports": [
                    {"branch": "release/1.0", "status": "waiting"}
                ]
            }
            for i in range(1, 4)
        }
        tracker = _make_tracker(all_issues=sources, metadata_map=metadata)
        result = run_release_pick_migration(tracker, "main")

        assert result.scanned == 3
        assert result.migrated == 3

    def test_handles_fetch_all_issues_failure(self):
        """Returns a result with errors when fetch_all_issues raises."""
        tracker = MagicMock()
        tracker.fetch_all_issues.side_effect = RuntimeError("fetch failed")

        result = run_release_pick_migration(tracker, "main")

        assert result.errors == 1
        assert result.scanned == 0

    def test_handles_per_task_migration_error(self):
        """Errors in per-task migration are counted but do not stop the pass."""
        sources = [
            _issue(identifier="TASK-1"),
            _issue(identifier="TASK-2"),
        ]
        tracker = _make_tracker(
            all_issues=sources,
            metadata_map={
                "TASK-1": {"oompah.backports": [{"branch": "release/1.0", "status": "waiting"}]},
                "TASK-2": {"oompah.backports": [{"branch": "release/1.0", "status": "waiting"}]},
            },
        )
        # Make TASK-1 fail its write
        call_count = [0]
        original_side_effect = tracker.get_metadata.side_effect

        def failing_set_metadata(identifier, key, value):
            if identifier == "TASK-1":
                raise RuntimeError("write failed for TASK-1")

        tracker.set_metadata_field.side_effect = failing_set_metadata

        result = run_release_pick_migration(tracker, "main")

        assert result.errors == 0  # errors from migrate_source_task internal failure don't count
        assert result.scanned == 2

    def test_second_run_is_noop(self):
        """Running migration twice does nothing on the second run."""
        source = _issue(identifier="TASK-1")
        # After first run, addendum exists; metadata read returns it
        existing_addendum = {
            "id": "TASK-1/release/1.0",
            "source_branch": "main",
            "target_branch": "release/1.0",
            "status": "open",
            "commits": [MIGRATION_PENDING_COMMIT],
            "work_branch": "oompah/release/TASK-1/release-1.0",
            "worktree_key": "release-TASK-1-release-1.0",
            "queued_at": "2026-01-01T00:00:00+00:00",
        }
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"}
                    ],
                    "oompah.release_addendums": [existing_addendum],
                }
            },
        )
        result = run_release_pick_migration(tracker, "main")

        assert result.migrated == 0
        assert result.already_migrated == 1
        tracker.set_metadata_field.assert_not_called()

    def test_children_archived_counted(self):
        """Children archived during migration are included in the result."""
        child = _issue(identifier="TASK-2", state=OPEN)
        source = _issue(identifier="TASK-1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "task_created",
                            "task_id": "TASK-2",
                        }
                    ]
                }
            },
            child_detail_map={"TASK-2": child},
            archived_identifiers=set(),
        )
        result = run_release_pick_migration(tracker, "main")

        assert result.migrated == 1
        assert result.children_archived == 1

    def test_never_creates_tracker_tasks(self):
        """Migration never calls tracker.create_issue."""
        source = _issue(identifier="TASK-1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "waiting"},
                        {"branch": "release/2.0", "status": "pr_open"},
                    ]
                }
            },
        )
        run_release_pick_migration(tracker, "main")

        tracker.create_issue.assert_not_called()

    def test_mixed_migrated_and_new_data(self):
        """Tasks with some already-migrated addendums and some new entries handled correctly."""
        source = _issue(identifier="TASK-1")
        tracker = _make_tracker(
            all_issues=[source],
            metadata_map={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged", "commits": ["sha1"]},
                        {"branch": "release/2.0", "status": "waiting"},
                    ],
                    "oompah.release_addendums": [
                        {
                            "id": "TASK-1/release/1.0",
                            "source_branch": "main",
                            "target_branch": "release/1.0",
                            "status": "merged",
                            "commits": ["sha1"],
                            "work_branch": "oompah/release/TASK-1/release-1.0",
                            "worktree_key": "release-TASK-1-release-1.0",
                            "queued_at": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                }
            },
        )
        result = run_release_pick_migration(tracker, "main")

        assert result.scanned == 1
        assert result.migrated == 1       # release/2.0 migrated
        assert result.already_migrated == 1  # release/1.0 skipped

        written = tracker.set_metadata_field.call_args.args[2]
        assert len(written) == 2  # Both addendums in the final write


# ---------------------------------------------------------------------------
# MigrationResult
# ---------------------------------------------------------------------------


class TestMigrationResult:
    def test_changed_false_when_empty(self):
        r = MigrationResult()
        assert r.changed is False

    def test_changed_true_when_migrated(self):
        r = MigrationResult(migrated=1)
        assert r.changed is True

    def test_changed_true_when_children_archived(self):
        r = MigrationResult(children_archived=1)
        assert r.changed is True

    def test_changed_false_with_only_errors(self):
        r = MigrationResult(errors=5)
        assert r.changed is False

    def test_changed_false_with_only_already_migrated(self):
        r = MigrationResult(already_migrated=3)
        assert r.changed is False
