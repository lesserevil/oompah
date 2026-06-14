"""Tests for release-pick reconciler integration with GitHub Issues (TASK-462.5).

Verifies that:
  - Release-pick children are created as GitHub Issues when the tracker uses
    GitHub-format identifiers (owner/repo#N).
  - backports, backport_of, and target_branch metadata round-trips correctly
    through the GitHub Issue body JSON storage format.
  - Conflict comments are surfaced on GitHub-backed source tasks.
  - The full reconcile pass works end-to-end with a GitHub tracker mock.
  - _build_child_index correctly matches GitHub identifiers using uppercase keys.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from oompah.models import Issue
from oompah.release_pick_reconciler import (
    _build_child_index,
    _create_backport_child,
    _post_conflict_source_comment,
    reconcile_release_picks,
)
from oompah.release_pick_schema import (
    BackportEntry,
    BackportOf,
    ReleasePick,
    backports_to_raw,
    parse_backport_of,
    parse_backports,
)
from oompah.statuses import MERGED, OPEN


# ---------------------------------------------------------------------------
# Test helpers — GitHub-flavoured
# ---------------------------------------------------------------------------

_OWNER = "example-org"
_REPO = "oompah-tasks"


def _gh_id(number: int) -> str:
    """Return a fully-qualified GitHub identifier like ``example-org/oompah-tasks#N``."""
    return f"{_OWNER}/{_REPO}#{number}"


def _gh_issue(
    number: int = 1,
    title: str = "Do something",
    state: str = OPEN,
    target_branch: str | None = None,
    backports=None,
    backport_of=None,
    release_pick_metadata_loaded: bool = True,
) -> Issue:
    """Build a minimal GitHub Issue with release-pick metadata pre-loaded."""
    identifier = _gh_id(number)
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="desc",
        state=state,
        target_branch=target_branch,
        backports=backports,
        backport_of=backport_of,
        release_pick_metadata_loaded=release_pick_metadata_loaded,
        tracker_kind="github_issues",
    )


def _make_gh_tracker(
    all_issues: list[Issue] | None = None,
    metadata_map: dict[str, dict] | None = None,
    created_issues: list[Issue] | None = None,
) -> MagicMock:
    """Build a mock GitHub tracker with pre-configured return values."""
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(all_issues or [])
    tracker.fetch_issue_detail.return_value = None

    _meta = dict(metadata_map or {})

    def _get_meta(identifier: str) -> dict:
        return _meta.get(identifier, {})

    tracker.get_metadata.side_effect = _get_meta

    _created = list(created_issues or [])
    _create_idx = [0]

    def _create_issue(*args, **kwargs):
        idx = _create_idx[0]
        if idx < len(_created):
            issue = _created[idx]
            _create_idx[0] += 1
            return issue
        auto_number = 100 + idx
        _create_idx[0] += 1
        return _gh_issue(number=auto_number, title=kwargs.get("title", "child"))

    tracker.create_issue.side_effect = _create_issue
    return tracker


# ---------------------------------------------------------------------------
# TestCreateBackportChildGitHub
# ---------------------------------------------------------------------------


class TestCreateBackportChildGitHub:
    """Tests for _create_backport_child when source and child are GitHub Issues."""

    def test_creates_issue_with_correct_title(self):
        source = _gh_issue(number=10, title="Fix important bug")
        entry = BackportEntry(branch="release/1.0")
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        tracker.create_issue.assert_called_once()
        call_kw = tracker.create_issue.call_args
        assert (
            call_kw.kwargs.get("title") or call_kw.args[0]
        ) == "Backport Fix important bug to release/1.0"

    def test_creates_with_backport_label(self):
        source = _gh_issue(number=10, title="Fix bug")
        entry = BackportEntry(branch="release/2.0")
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        call_kw = tracker.create_issue.call_args
        labels = call_kw.kwargs.get("labels") or []
        assert "backport" in labels

    def test_creates_with_github_source_as_parent(self):
        """parent= should be the fully-qualified GitHub identifier."""
        source = _gh_issue(number=10, title="Fix bug")
        entry = BackportEntry(branch="release/2.0")
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        call_kw = tracker.create_issue.call_args
        parent = call_kw.kwargs.get("parent")
        assert parent == _gh_id(10)

    def test_sets_backport_of_metadata_with_github_source(self):
        """oompah.backport_of.source should store the full GitHub identifier."""
        source = _gh_issue(number=10, title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.backport_of"
        ]
        assert len(meta_calls) == 1
        assert meta_calls[0].args[0] == _gh_id(11)
        value = meta_calls[0].args[2]
        assert value["source"] == _gh_id(10), (
            f"Expected source={_gh_id(10)!r}, got {value['source']!r}"
        )

    def test_sets_target_branch_metadata(self):
        source = _gh_issue(number=10, title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        _create_backport_child(tracker, source, entry)

        meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.target_branch"
        ]
        assert len(meta_calls) == 1
        assert meta_calls[0].args[2] == "release/1.0"

    def test_returns_refreshed_github_issue(self):
        source = _gh_issue(number=10, title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _gh_issue(number=11)
        refreshed = _gh_issue(number=11, title="Backport Fix bug to release/1.0")
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = refreshed

        result = _create_backport_child(tracker, source, entry)

        assert result is refreshed

    def test_returns_original_when_refresh_returns_none(self):
        source = _gh_issue(number=10, title="Fix bug")
        entry = BackportEntry(branch="release/1.0")
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(created_issues=[child])
        tracker.fetch_issue_detail.return_value = None

        result = _create_backport_child(tracker, source, entry)

        assert result is child


# ---------------------------------------------------------------------------
# TestBuildChildIndexGitHub
# ---------------------------------------------------------------------------


class TestBuildChildIndexGitHub:
    """Tests for _build_child_index with GitHub-format identifiers."""

    def test_indexes_github_child_by_source_and_branch(self):
        """Children with oompah.backport_of pointing to GitHub source should be indexed."""
        source_id = _gh_id(10)
        child = _gh_issue(
            number=11,
            target_branch="release/1.0",
            backport_of={"source": source_id, "status": "task_created"},
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker()

        index = _build_child_index(tracker, [child])

        key = (source_id.upper(), "release/1.0")
        assert key in index
        assert child in index[key]

    def test_lookup_key_uppercase_github_identifier(self):
        """Key must be (upper(source_id), branch) — GitHub IDs have mixed-case."""
        source_id = "Example-Org/oompah-tasks#42"
        child = _gh_issue(
            number=100,
            target_branch="release/2.0",
            backport_of={"source": source_id, "status": "waiting"},
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker()

        index = _build_child_index(tracker, [child])

        expected_key = (source_id.upper(), "release/2.0")
        assert expected_key in index

    def test_reconciler_matches_github_source_key(self):
        """The key produced by the reconciler must match the index key."""
        source = _gh_issue(number=10)
        child = _gh_issue(
            number=11,
            target_branch="release/1.0",
            backport_of={"source": source.identifier, "status": "waiting"},
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker()
        index = _build_child_index(tracker, [child])

        # The reconciler builds key as (source.identifier.upper(), entry.branch)
        source_key = source.identifier.upper()
        assert (source_key, "release/1.0") in index

    def test_does_not_index_issues_without_backport_of(self):
        """Regular issues without backport_of should not appear in the index."""
        regular_issue = _gh_issue(number=5, release_pick_metadata_loaded=False)
        tracker = _make_gh_tracker()
        tracker.get_metadata.return_value = {}  # No backport_of in metadata

        index = _build_child_index(tracker, [regular_issue])

        assert index == {}


# ---------------------------------------------------------------------------
# TestBackportsMetadataRoundtrip
# ---------------------------------------------------------------------------


class TestBackportsMetadataRoundtrip:
    """Tests that backports metadata survives the GitHub Issue JSON storage roundtrip."""

    def test_waiting_entry_roundtrips_as_string(self):
        """A compact (branch-only) entry survives serialise → parse."""
        entries = [BackportEntry(branch="release/1.0")]
        raw = backports_to_raw(entries)
        # Compact form: just the branch string
        assert raw == ["release/1.0"]
        parsed = parse_backports(raw)
        assert len(parsed) == 1
        assert parsed[0].branch == "release/1.0"
        assert parsed[0].status == ReleasePick.WAITING

    def test_task_created_entry_with_github_task_id_roundtrips(self):
        """An entry with a GitHub task_id survives serialise → parse."""
        entries = [
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.TASK_CREATED,
                task_id=_gh_id(42),
            )
        ]
        raw = backports_to_raw(entries)
        assert isinstance(raw[0], dict)
        assert raw[0]["task_id"] == _gh_id(42)

        parsed = parse_backports(raw)
        assert parsed[0].task_id == _gh_id(42)
        assert parsed[0].status == ReleasePick.TASK_CREATED

    def test_pr_open_entry_with_github_pr_url_roundtrips(self):
        """An entry with a GitHub PR URL survives serialise → parse."""
        pr_url = "https://github.com/example-org/trickle/pull/99"
        entries = [
            BackportEntry(
                branch="release/1.0",
                status=ReleasePick.PR_OPEN,
                task_id=_gh_id(42),
                pr_url=pr_url,
            )
        ]
        raw = backports_to_raw(entries)
        parsed = parse_backports(raw)
        assert parsed[0].pr_url == pr_url
        assert parsed[0].status == ReleasePick.PR_OPEN

    def test_backport_of_with_github_source_roundtrips(self):
        """BackportOf with a GitHub source ID roundtrips through raw form."""
        bof = BackportOf(source=_gh_id(10), status=ReleasePick.PR_OPEN)
        raw = bof.to_raw()
        assert isinstance(raw, dict)
        assert raw["source"] == _gh_id(10)

        parsed = parse_backport_of(raw)
        assert parsed is not None
        assert parsed.source == _gh_id(10)
        assert parsed.status == ReleasePick.PR_OPEN

    def test_backport_of_plain_github_string_roundtrips(self):
        """BackportOf with default status and GitHub source roundtrips as plain string."""
        bof = BackportOf(source=_gh_id(10))
        raw = bof.to_raw()
        # Default status (WAITING): returned as plain string.
        assert raw == _gh_id(10)

        parsed = parse_backport_of(raw)
        assert parsed is not None
        assert parsed.source == _gh_id(10)


# ---------------------------------------------------------------------------
# TestConflictCommentGitHub
# ---------------------------------------------------------------------------


class TestConflictCommentGitHub:
    """Tests for _post_conflict_source_comment with GitHub Issues."""

    def test_posts_comment_on_github_source(self):
        source = _gh_issue(number=10, title="Fix important bug")
        child = _gh_issue(number=11)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.CONFLICT,
            task_id=_gh_id(11),
        )
        tracker = _make_gh_tracker()

        _post_conflict_source_comment(tracker, source, entry, child)

        tracker.add_comment.assert_called_once()
        call_args = tracker.add_comment.call_args
        # First positional arg is the identifier of the source task.
        assert call_args.args[0] == _gh_id(10)

    def test_comment_mentions_target_branch(self):
        source = _gh_issue(number=10, title="Fix important bug")
        child = _gh_issue(number=11)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.CONFLICT,
            task_id=_gh_id(11),
        )
        tracker = _make_gh_tracker()

        _post_conflict_source_comment(tracker, source, entry, child)

        comment_text = tracker.add_comment.call_args.args[1]
        assert "release/1.0" in comment_text

    def test_comment_mentions_child_github_identifier(self):
        source = _gh_issue(number=10, title="Fix important bug")
        child = _gh_issue(number=11)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.CONFLICT,
            task_id=_gh_id(11),
        )
        tracker = _make_gh_tracker()

        _post_conflict_source_comment(tracker, source, entry, child)

        comment_text = tracker.add_comment.call_args.args[1]
        assert _gh_id(11) in comment_text

    def test_comment_author_is_oompah(self):
        source = _gh_issue(number=10)
        child = _gh_issue(number=11)
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.CONFLICT)
        tracker = _make_gh_tracker()

        _post_conflict_source_comment(tracker, source, entry, child)

        call_kw = tracker.add_comment.call_args
        author = call_kw.kwargs.get("author") or (call_kw.args[2] if len(call_kw.args) > 2 else None)
        assert author == "oompah"

    def test_comment_failure_does_not_raise(self):
        """add_comment failure must not propagate out of the helper."""
        source = _gh_issue(number=10)
        child = _gh_issue(number=11)
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.CONFLICT)
        tracker = _make_gh_tracker()
        tracker.add_comment.side_effect = Exception("GitHub 503")

        # Should not raise.
        _post_conflict_source_comment(tracker, source, entry, child)

    def test_comment_preserves_worktree_message(self):
        """The conflict comment must mention that the worktree has been preserved."""
        source = _gh_issue(number=10, title="Fix critical bug")
        child = _gh_issue(number=11)
        entry = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.CONFLICT,
            task_id=_gh_id(11),
        )
        tracker = _make_gh_tracker()

        _post_conflict_source_comment(tracker, source, entry, child)

        comment_text = tracker.add_comment.call_args.args[1]
        # The comment should mention worktree preservation.
        assert "worktree" in comment_text.lower()


# ---------------------------------------------------------------------------
# TestReconcileGitHubIntegration
# ---------------------------------------------------------------------------


class TestReconcileGitHubIntegration:
    """End-to-end reconcile_release_picks with a GitHub tracker mock."""

    def test_creates_github_child_for_waiting_entry(self):
        """A waiting entry on a GitHub source creates a GitHub Issue child."""
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        source = _gh_issue(
            number=10,
            title="Add feature",
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(all_issues=[source], created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        result = reconcile_release_picks(tracker)

        assert result.created == 1
        assert result.advanced == 1
        tracker.create_issue.assert_called_once()

    def test_created_child_has_github_identifier_in_task_id(self):
        """The backports entry task_id should contain the new GitHub Issue identifier."""
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        source = _gh_issue(
            number=10,
            title="Add feature",
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(number=42)
        tracker = _make_gh_tracker(all_issues=[source], created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        reconcile_release_picks(tracker)

        # Check the written backports metadata contains the child's GitHub ID.
        set_meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == _gh_id(10) and c.args[1] == "oompah.backports"
        ]
        assert len(set_meta_calls) >= 1
        written_raw = set_meta_calls[-1].args[2]
        # written_raw is from backports_to_raw(...) — a list
        assert isinstance(written_raw, list)
        entry_dict = written_raw[0]
        assert isinstance(entry_dict, dict)
        assert entry_dict["task_id"] == _gh_id(42)
        assert entry_dict["status"] == "task_created"

    def test_created_child_backport_of_has_github_source(self):
        """The child's oompah.backport_of.source must be the GitHub source identifier."""
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        source = _gh_issue(
            number=10,
            title="Fix regression",
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(number=42)
        tracker = _make_gh_tracker(all_issues=[source], created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        reconcile_release_picks(tracker)

        bof_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[1] == "oompah.backport_of"
        ]
        assert len(bof_calls) >= 1
        value = bof_calls[0].args[2]
        assert value["source"] == _gh_id(10)

    def test_second_pass_does_not_create_duplicate(self):
        """A second pass with the child already in the index should not create another."""
        source_id = _gh_id(10)
        # First pass: source has a waiting entry, child not yet created.
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        source = _gh_issue(
            number=10,
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(
            number=11,
            target_branch="release/1.0",
            backport_of={"source": source_id, "status": "task_created"},
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker(all_issues=[source, child], created_issues=[])

        result = reconcile_release_picks(tracker)

        # Should heal (advance waiting → task_created) without creating.
        assert result.created == 0
        tracker.create_issue.assert_not_called()

    def test_healed_waiting_entry_uses_existing_child_identifier(self):
        """Healed entry task_id should point to the existing GitHub child identifier."""
        source_id = _gh_id(10)
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        source = _gh_issue(
            number=10,
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(
            number=11,
            state=OPEN,
            target_branch="release/1.0",
            backport_of={"source": source_id, "status": "task_created"},
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker(all_issues=[source, child])

        reconcile_release_picks(tracker)

        set_meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == _gh_id(10) and c.args[1] == "oompah.backports"
        ]
        assert len(set_meta_calls) >= 1
        written_raw = set_meta_calls[-1].args[2]
        entry_dict = written_raw[0]
        assert entry_dict["task_id"] == _gh_id(11)

    def test_terminal_github_child_mirrors_merged_status(self):
        """When a GitHub child is Merged, the parent backports entry → merged."""
        source_id = _gh_id(10)
        backports_raw = [
            {
                "branch": "release/1.0",
                "status": "task_created",
                "task_id": _gh_id(11),
            }
        ]
        source = _gh_issue(
            number=10,
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(
            number=11,
            state=MERGED,
            target_branch="release/1.0",
            backport_of={"source": source_id, "status": "task_created"},
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker(all_issues=[source, child])

        result = reconcile_release_picks(tracker)

        assert result.advanced == 1
        set_meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == _gh_id(10) and c.args[1] == "oompah.backports"
        ]
        assert len(set_meta_calls) >= 1
        written_raw = set_meta_calls[-1].args[2]
        entry_dict = written_raw[0]
        assert entry_dict["status"] == "merged"

    def test_multiple_branches_create_multiple_github_children(self):
        """Multiple waiting branches each create their own GitHub Issue."""
        backports_raw = [
            {"branch": "release/1.0", "status": "waiting"},
            {"branch": "release/2.0", "status": "waiting"},
        ]
        source = _gh_issue(
            number=10,
            title="Fix bug",
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child_1 = _gh_issue(number=11)
        child_2 = _gh_issue(number=12)
        tracker = _make_gh_tracker(
            all_issues=[source],
            created_issues=[child_1, child_2],
        )
        tracker.fetch_issue_detail.side_effect = [child_1, child_2]

        result = reconcile_release_picks(tracker)

        assert result.created == 2
        assert tracker.create_issue.call_count == 2

    def test_backports_metadata_written_to_source_github_issue(self):
        """After creating a child, the updated backports are written back to the source."""
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        source = _gh_issue(
            number=10,
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        child = _gh_issue(number=11)
        tracker = _make_gh_tracker(all_issues=[source], created_issues=[child])
        tracker.fetch_issue_detail.return_value = child

        reconcile_release_picks(tracker)

        # The backports metadata must be written to the source issue.
        set_meta_calls = [
            c for c in tracker.set_metadata_field.call_args_list
            if c.args[0] == _gh_id(10) and c.args[1] == "oompah.backports"
        ]
        assert len(set_meta_calls) >= 1, "Expected set_metadata_field call for source backports"

    def test_no_creation_when_no_backports(self):
        """Source issues with no backports metadata produce no child tasks."""
        source = _gh_issue(
            number=10,
            backports=None,
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker(all_issues=[source])

        result = reconcile_release_picks(tracker)

        assert result.scanned == 0
        tracker.create_issue.assert_not_called()

    def test_already_terminal_entry_not_advanced(self):
        """A merged backports entry should not trigger any further work."""
        backports_raw = [
            {
                "branch": "release/1.0",
                "status": "merged",
                "task_id": _gh_id(11),
            }
        ]
        source = _gh_issue(
            number=10,
            backports=backports_raw,
            release_pick_metadata_loaded=True,
        )
        tracker = _make_gh_tracker(all_issues=[source])

        result = reconcile_release_picks(tracker)

        # Scanned but no advancement.
        assert result.scanned == 1
        assert result.advanced == 0
        tracker.create_issue.assert_not_called()
