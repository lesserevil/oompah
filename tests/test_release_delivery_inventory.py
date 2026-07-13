"""Tests for oompah.release_delivery_inventory (OOMPAH-197).

Covers all acceptance criteria from the task:

Commit enumeration
  - Only non-merge commits are included; squash commits are selectable.
  - Newest-first topological order is preserved.
  - Commits from branches other than origin/default_branch are excluded.

Cursor / pagination
  - Opaque cursors encode source HEAD and last SHA.
  - SourceChangedError raised when source HEAD changes between pages.
  - Malformed cursors raise ValueError.
  - Multiple pages cover the full commit list without duplication.

Status precedence (§2.3)
  - Active delivery (open/in_progress/in_review/blocked) beats ancestry.
  - Merged delivery beats ancestry.
  - Ancestry-only delivery (no ledger entry).
  - Archived delivery when nothing else applies.
  - No evidence → not_selected.
  - Cherry-pick: result SHA on branch but source SHA absent; merged delivery
    still marks the source as "delivered".

Filter / search
  - needs_delivery: rows with at least one non-delivered branch are included.
  - all: every commit is returned.
  - Text search matches SHA, subject, author name, association identifier.

Branch availability
  - Remote-ref failure falls back to local refs/remotes/origin/* (stale=True).
  - A branch that does not exist locally is marked available=False.
  - No fabricated release branch: a branch not in remote or local refs is
    absent, never invented.

Cache
  - 60-second TTL: a second call within TTL returns the same snapshot.
  - After TTL expires, a new fetch is performed.
  - invalidate() drops the cache entry for a project.
  - invalidate(None) drops all entries.

Ledger enrichment
  - Rows with a ledger source_identifier carry an association dict.
  - Rows without a source_identifier (commits-kind) have no association.
  - Do not guess association from commit subjects.

Cursor helpers
  - Round-trip: encode then decode returns original values.
  - Bad base64 or missing fields raise ValueError.

Unit helpers
  - _compute_cell respects all 5 precedence levels.
  - _enumerate_commits skips merge commits and returns non-merges only.
"""

from __future__ import annotations

import base64
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_inventory import (
    MAX_PAGE_LIMIT,
    CACHE_TTL_SECONDS,
    CommitInventoryService,
    InventoryError,
    InventoryPage,
    ReleaseStatusCell,
    SourceChangedError,
    _CacheEntry,
    _CommitInfo,
    _check_ancestry_batch,
    _compute_cell,
    _decode_cursor,
    _encode_cursor,
    _enumerate_commits,
    _fetch_refs,
    _resolve_remote_ref,
    _acquire_snapshot,
    RefSnapshot,
    reset_default_service,
)
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryLedger,
    ReleaseDeliveryStore,
    SourceKind,
)

# ---------------------------------------------------------------------------
# Shared SHA constants
# ---------------------------------------------------------------------------

_SHA_A = "a" * 40  # oldest
_SHA_B = "b" * 40
_SHA_C = "c" * 40  # newest
_SHA_RESULT = "1" * 40
_SHA_MERGE = "e" * 40

# ---------------------------------------------------------------------------
# Git repository fixture helpers
# ---------------------------------------------------------------------------

_GIT_ENV = {"GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
             "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00"}


def _git(args: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    """Run a git command in *cwd* and return the completed process."""
    env = {**_GIT_ENV}
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={**__import__("os").environ, **env},
        **kwargs,
    )


def _make_repo(tmp_path: Path, *, branch: str = "main") -> Path:
    """Create a minimal git repo and return its path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", branch], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)
    _git(["config", "user.email", "test@example.com"], cwd=repo)
    return repo


def _commit(repo: Path, msg: str, *, filename: str | None = None) -> str:
    """Make a commit and return its SHA."""
    fname = filename or f"file_{msg[:8].replace(' ', '_')}.txt"
    (repo / fname).write_text(f"{msg}\n")
    _git(["add", fname], cwd=repo)
    _git(["commit", "-m", msg], cwd=repo)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _make_origin_clone(tmp_path: Path, source_repo: Path) -> Path:
    """Clone *source_repo* as a bare 'origin' and set up a tracking remote."""
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source_repo), str(bare)],
        capture_output=True, check=True,
    )
    return bare


def _setup_remote(worker_repo: Path, origin_bare: Path) -> None:
    """Add *origin_bare* as the 'origin' remote in *worker_repo*."""
    _git(["remote", "add", "origin", str(origin_bare)], cwd=worker_repo)
    _git(["fetch", "origin"], cwd=worker_repo)


# ---------------------------------------------------------------------------
# Fixture: a repo with 3 commits on main, a release branch, and a remote
# ---------------------------------------------------------------------------

@pytest.fixture()
def three_commit_repo(tmp_path: Path):
    """Return a dict with:
      - repo_path: Path to a local clone with origin set up
      - sha_a: oldest commit SHA on main
      - sha_b: middle commit SHA on main
      - sha_c: newest commit SHA on main
      - release_sha: HEAD of release/1.0
    """
    # Build the "upstream" repo
    upstream = _make_repo(tmp_path, branch="main")
    sha_a = _commit(upstream, "commit A")
    sha_b = _commit(upstream, "commit B")
    sha_c = _commit(upstream, "commit C")

    # Create release/1.0 branching off sha_a
    subprocess.run(
        ["git", "branch", "release/1.0", sha_a],
        cwd=str(upstream), check=True, capture_output=True,
    )
    release_sha = sha_a

    # Clone as a local working repo with origin
    local = tmp_path / "local"
    local.mkdir()
    subprocess.run(
        ["git", "clone", str(upstream), str(local)],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(local), "config", "user.name", "Test"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(local), "config", "user.email", "test@example.com"],
        capture_output=True, check=True,
    )
    # Fetch all branches
    subprocess.run(
        ["git", "-C", str(local), "fetch", "--all"],
        capture_output=True, check=True,
    )

    return {
        "repo_path": local,
        "sha_a": sha_a,
        "sha_b": sha_b,
        "sha_c": sha_c,
        "release_sha": release_sha,
        "upstream": upstream,
    }


# ---------------------------------------------------------------------------
# Helper to make a ReleaseDelivery
# ---------------------------------------------------------------------------

def _make_delivery(
    *,
    id: str = "rd_01J",
    project_id: str = "proj-123",
    source_branch: str = "main",
    source_kind: SourceKind = SourceKind.TASK,
    source_identifier: str | None = "FOO-10",
    source_commits: list[str] | None = None,
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    queued_at: str = "2026-07-13T12:00:00Z",
    result_commits: list[str] | None = None,
    pr_url: str | None = None,
    **extra,
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=id,
        project_id=project_id,
        source_branch=source_branch,
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=source_commits if source_commits is not None else [_SHA_A],
        target_branch=target_branch,
        status=status,
        queued_at=queued_at,
        result_commits=result_commits or [],
        pr_url=pr_url,
        **extra,
    )


def _make_store_with_deliveries(
    tmp_path: Path,
    deliveries: list[ReleaseDelivery],
    *,
    project_id: str = "proj-123",
) -> ReleaseDeliveryStore:
    """Return a ReleaseDeliveryStore pre-populated with *deliveries*."""
    store = ReleaseDeliveryStore(tmp_path, project_id)
    # Write each delivery directly (bypass git_writer for unit tests)
    ledger = ReleaseDeliveryLedger(version=1, deliveries=deliveries)
    import yaml
    ledger_path = tmp_path / ".oompah" / "release-deliveries.yml"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(yaml.safe_dump(ledger.to_raw(), sort_keys=False), encoding="utf-8")
    return store


def _make_service(
    repo_path: Path,
    delivery_store: ReleaseDeliveryStore,
    *,
    project_id: str = "proj-123",
    default_branch: str = "main",
    cache_ttl: float = CACHE_TTL_SECONDS,
    fetch_timeout: int = 30,
    ancestry_timeout: int = 10,
) -> CommitInventoryService:
    return CommitInventoryService(
        project_root=repo_path,
        project_id=project_id,
        default_branch=default_branch,
        delivery_store=delivery_store,
        fetch_timeout=fetch_timeout,
        ancestry_timeout=ancestry_timeout,
        cache_ttl=cache_ttl,
    )


# ===========================================================================
# Section 1: Cursor helpers
# ===========================================================================

class TestCursorHelpers:
    """Tests for _encode_cursor / _decode_cursor."""

    def test_round_trip(self):
        sha1 = "a" * 40
        sha2 = "b" * 40
        cursor = _encode_cursor(sha1, sha2)
        head, after = _decode_cursor(cursor)
        assert head == sha1
        assert after == sha2

    def test_encode_is_urlsafe_base64(self):
        cursor = _encode_cursor("a" * 40, "b" * 40)
        # Should be decodable with standard urlsafe base64
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        payload = json.loads(decoded)
        assert "source_head" in payload
        assert "after_sha" in payload

    def test_decode_malformed_not_json(self):
        bad = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
        with pytest.raises(ValueError, match="Malformed"):
            _decode_cursor(bad)

    def test_decode_not_base64(self):
        with pytest.raises(ValueError, match="Malformed"):
            _decode_cursor("!!!not-base64!!!")

    def test_decode_missing_source_head(self):
        payload = json.dumps({"after_sha": "b" * 40}).encode()
        cursor = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
        with pytest.raises(ValueError, match="source_head"):
            _decode_cursor(cursor)

    def test_decode_invalid_sha(self):
        payload = json.dumps(
            {"source_head": "not-a-sha", "after_sha": "b" * 40}
        ).encode()
        cursor = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
        with pytest.raises(ValueError, match="source_head"):
            _decode_cursor(cursor)

    def test_decode_non_dict_payload(self):
        payload = json.dumps(["a", "b"]).encode()
        cursor = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
        with pytest.raises(ValueError, match="JSON object"):
            _decode_cursor(cursor)


# ===========================================================================
# Section 2: Status precedence (_compute_cell)
# ===========================================================================

class TestComputeCell:
    """Tests for _compute_cell following §2.3 precedence rules."""

    def _make_branch_deliveries(
        self, deliveries: list[ReleaseDelivery]
    ) -> dict[str, list[ReleaseDelivery]]:
        """Group deliveries by target_branch."""
        result: dict[str, list[ReleaseDelivery]] = {}
        for d in deliveries:
            result.setdefault(d.target_branch, []).append(d)
        return result

    def test_not_selected_when_no_evidence(self):
        cell = _compute_cell(_SHA_A, "release/1.0", {}, set())
        assert cell.state == "not_selected"
        assert cell.evidence is None
        assert cell.delivery_id is None

    def test_active_open_delivery_wins(self):
        d = _make_delivery(
            id="rd-open",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
        )
        branch_deliveries = self._make_branch_deliveries([d])
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, {_SHA_A})
        assert cell.state == "open"
        assert cell.delivery_id == "rd-open"

    def test_active_in_progress_delivery_wins(self):
        d = _make_delivery(
            id="rd-ip",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.IN_PROGRESS,
        )
        branch_deliveries = self._make_branch_deliveries([d])
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, {_SHA_A})
        assert cell.state == "in_progress"

    def test_active_in_review_delivery_wins(self):
        d = _make_delivery(
            id="rd-ir",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.IN_REVIEW,
            pr_url="https://github.com/org/repo/pull/42",
        )
        branch_deliveries = self._make_branch_deliveries([d])
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, {_SHA_A})
        assert cell.state == "in_review"
        assert cell.pr_url == "https://github.com/org/repo/pull/42"

    def test_active_blocked_delivery_wins(self):
        d = _make_delivery(
            id="rd-blocked",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.BLOCKED,
        )
        branch_deliveries = self._make_branch_deliveries([d])
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, set())
        assert cell.state == "blocked"

    def test_merged_delivery_beats_ancestry(self):
        d = _make_delivery(
            id="rd-merged",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.MERGED,
            result_commits=[_SHA_RESULT],
            pr_url="https://github.com/org/repo/pull/1",
        )
        branch_deliveries = self._make_branch_deliveries([d])
        # Even though SHA_A is "in" ancestry_set, merged delivery takes precedence over ancestry
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, {_SHA_A})
        assert cell.state == "delivered"
        assert cell.evidence == "delivery"
        assert cell.delivery_id == "rd-merged"
        assert cell.result_commits == [_SHA_RESULT]

    def test_ancestry_when_no_delivery(self):
        cell = _compute_cell(_SHA_A, "release/1.0", {}, {_SHA_A})
        assert cell.state == "delivered"
        assert cell.evidence == "ancestry"
        assert cell.delivery_id is None

    def test_archived_delivery_after_no_active_merged_ancestry(self):
        d = _make_delivery(
            id="rd-arch",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.ARCHIVED,
        )
        branch_deliveries = self._make_branch_deliveries([d])
        # Not in ancestry
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, set())
        assert cell.state == "archived"
        assert cell.delivery_id == "rd-arch"

    def test_active_beats_archived(self):
        d_open = _make_delivery(
            id="rd-open",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
        )
        d_arch = _make_delivery(
            id="rd-arch",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.ARCHIVED,
        )
        branch_deliveries = self._make_branch_deliveries([d_open, d_arch])
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, set())
        assert cell.state == "open"

    def test_different_branch_deliveries_ignored(self):
        """A delivery for a different branch must not affect the requested branch."""
        d = _make_delivery(
            id="rd-other",
            source_commits=[_SHA_A],
            target_branch="release/2.0",
            status=AddendumStatus.MERGED,
        )
        # Only pass delivery for "release/2.0", ask for "release/1.0"
        branch_deliveries = self._make_branch_deliveries([d])
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, set())
        assert cell.state == "not_selected"

    def test_cherry_pick_source_sha_not_ancestor_but_merged_delivery(self):
        """Cherry-pick scenario: source SHA not reachable from branch, but merged delivery."""
        d = _make_delivery(
            id="rd-cp",
            source_commits=[_SHA_A],
            target_branch="release/1.0",
            status=AddendumStatus.MERGED,
            result_commits=[_SHA_RESULT],  # different SHA on release branch
        )
        branch_deliveries = self._make_branch_deliveries([d])
        # SHA_A is NOT in the ancestry set (it's a cherry-pick, different SHA on branch)
        cell = _compute_cell(_SHA_A, "release/1.0", branch_deliveries, set())
        assert cell.state == "delivered"
        assert cell.evidence == "delivery"
        assert cell.result_commits == [_SHA_RESULT]


# ===========================================================================
# Section 3: Git enumeration (with real repo fixture)
# ===========================================================================

class TestEnumerateCommits:
    """Tests for _enumerate_commits with real git repos."""

    def test_returns_commits_newest_first(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]
        sha_b = three_commit_repo["sha_b"]
        sha_c = three_commit_repo["sha_c"]

        commits = _enumerate_commits(
            repo,
            source_ref="refs/remotes/origin/main",
        )
        shas = [c.sha for c in commits]
        # sha_c is newest, sha_a is oldest
        assert sha_c in shas
        assert sha_b in shas
        assert sha_a in shas
        # Topological order: newest first
        assert shas.index(sha_c) < shas.index(sha_b) < shas.index(sha_a)

    def test_merge_commits_excluded(self, tmp_path):
        """Merge commits must not appear in the enumeration."""
        upstream = _make_repo(tmp_path, branch="main")
        sha_base = _commit(upstream, "base")

        # Create a feature branch
        subprocess.run(
            ["git", "-C", str(upstream), "checkout", "-b", "feature"],
            capture_output=True, check=True,
        )
        sha_feat = _commit(upstream, "feature commit")

        # Merge back
        subprocess.run(
            ["git", "-C", str(upstream), "checkout", "main"],
            capture_output=True, check=True,
        )
        sha_before_merge = _commit(upstream, "pre-merge commit")
        subprocess.run(
            ["git", "-C", str(upstream), "merge", "--no-ff", "feature", "-m", "Merge feature"],
            capture_output=True, check=True,
        )
        sha_merge = subprocess.run(
            ["git", "-C", str(upstream), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        # Clone and fetch
        local = tmp_path / "local"
        subprocess.run(
            ["git", "clone", str(upstream), str(local)],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(local), "fetch", "--all"],
            capture_output=True, check=True,
        )

        commits = _enumerate_commits(
            local,
            source_ref="refs/remotes/origin/main",
        )
        shas = [c.sha for c in commits]

        # Merge commit must not appear
        assert sha_merge not in shas
        # Non-merge commits appear
        assert sha_base in shas
        assert sha_before_merge in shas
        assert sha_feat in shas

    def test_squash_commit_is_selectable(self, tmp_path):
        """A squash-merge commit (single parent) is not a merge commit and must appear."""
        upstream = _make_repo(tmp_path, branch="main")
        _commit(upstream, "initial")

        # Squash-merge simulation: create squash commit (single parent)
        (upstream / "squash.txt").write_text("squashed\n")
        _git(["add", "squash.txt"], cwd=upstream)
        _git(["commit", "-m", "Squash: combine F1 and F2"], cwd=upstream)

        sha_squash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(upstream), capture_output=True, text=True, check=True,
        ).stdout.strip()

        local = tmp_path / "local"
        subprocess.run(["git", "clone", str(upstream), str(local)],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(local), "fetch", "--all"],
                       capture_output=True, check=True)

        commits = _enumerate_commits(local, source_ref="refs/remotes/origin/main")
        shas = [c.sha for c in commits]
        assert sha_squash in shas

    def test_max_count_limits_results(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        commits = _enumerate_commits(
            repo,
            source_ref="refs/remotes/origin/main",
            max_count=2,
        )
        assert len(commits) <= 2

    def test_commit_fields_populated(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        commits = _enumerate_commits(repo, source_ref="refs/remotes/origin/main")
        assert commits, "Expected at least one commit"
        c = commits[0]
        assert len(c.sha) == 40
        assert c.sha.isalnum()
        assert c.subject  # non-empty subject
        assert c.author_name  # non-empty author
        assert c.authored_at  # non-empty date

    def test_invalid_source_ref_raises(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        with pytest.raises(RuntimeError, match="git rev-list failed"):
            _enumerate_commits(repo, source_ref="refs/remotes/origin/nonexistent-branch-xyz")


# ===========================================================================
# Section 4: Ref snapshot acquisition
# ===========================================================================

class TestRefSnapshot:
    """Tests for _resolve_remote_ref and _acquire_snapshot."""

    def test_resolve_remote_ref_success(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        sha_c = three_commit_repo["sha_c"]
        resolved = _resolve_remote_ref(repo, "main")
        assert resolved == sha_c

    def test_resolve_remote_ref_missing_branch(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        resolved = _resolve_remote_ref(repo, "nonexistent-branch-xyz")
        assert resolved is None

    def test_acquire_snapshot_success(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        sha_c = three_commit_repo["sha_c"]
        sha_a = three_commit_repo["sha_a"]

        snapshot = _acquire_snapshot(
            repo,
            default_branch="main",
            release_branches=["release/1.0"],
        )
        assert snapshot.source_head == sha_c
        assert snapshot.release_heads["release/1.0"] == sha_a
        assert not snapshot.stale

    def test_acquire_snapshot_missing_release_branch(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        snapshot = _acquire_snapshot(
            repo,
            default_branch="main",
            release_branches=["nonexistent/1.9"],
        )
        # Missing branch → None head
        assert snapshot.release_heads["nonexistent/1.9"] is None

    def test_acquire_snapshot_remote_failure_falls_back_stale(self, three_commit_repo):
        """When git fetch fails, fall back to local refs and mark stale=True."""
        repo = three_commit_repo["repo_path"]

        with patch(
            "oompah.release_delivery_inventory._fetch_refs",
            return_value=False,
        ):
            snapshot = _acquire_snapshot(
                repo,
                default_branch="main",
                release_branches=["release/1.0"],
            )

        assert snapshot.stale is True
        # Local refs still available
        assert snapshot.source_head is not None
        assert len(snapshot.source_head) == 40

    def test_acquire_snapshot_no_local_ref_raises(self, tmp_path):
        """When remote fails AND no local ref exists, raise InventoryError."""
        repo = _make_repo(tmp_path, branch="main")
        # No commit, no remote → refs/remotes/origin/main does not exist

        with patch(
            "oompah.release_delivery_inventory._fetch_refs",
            return_value=False,
        ):
            with pytest.raises(InventoryError, match="Cannot resolve"):
                _acquire_snapshot(
                    repo,
                    default_branch="main",
                    release_branches=[],
                )


# ===========================================================================
# Section 5: Ancestry batch check
# ===========================================================================

class TestCheckAncestryBatch:
    """Tests for _check_ancestry_batch with real git repos."""

    def test_ancestor_detected(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]
        # sha_a is the base of release/1.0
        ancestors = _check_ancestry_batch(
            repo,
            shas=[sha_a],
            target_ref="refs/remotes/origin/release/1.0",
        )
        assert sha_a in ancestors

    def test_non_ancestor_excluded(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]
        # sha_b is NOT on release/1.0
        ancestors = _check_ancestry_batch(
            repo,
            shas=[sha_b],
            target_ref="refs/remotes/origin/release/1.0",
        )
        assert sha_b not in ancestors

    def test_empty_shas_returns_empty(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        ancestors = _check_ancestry_batch(
            repo,
            shas=[],
            target_ref="refs/remotes/origin/release/1.0",
        )
        assert ancestors == set()

    def test_mixed_ancestors(self, three_commit_repo):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]
        sha_b = three_commit_repo["sha_b"]
        sha_c = three_commit_repo["sha_c"]
        ancestors = _check_ancestry_batch(
            repo,
            shas=[sha_a, sha_b, sha_c],
            target_ref="refs/remotes/origin/release/1.0",
        )
        # Only sha_a is an ancestor of release/1.0 (which was branched from sha_a)
        assert sha_a in ancestors
        assert sha_b not in ancestors
        assert sha_c not in ancestors


# ===========================================================================
# Section 6: CommitInventoryService — get_page
# ===========================================================================

class TestCommitInventoryServiceGetPage:
    """Integration tests for CommitInventoryService.get_page."""

    def _store(self, tmp_path: Path, deliveries=None) -> ReleaseDeliveryStore:
        return _make_store_with_deliveries(
            tmp_path,
            deliveries or [],
            project_id="proj-123",
        )

    def test_basic_page_returns_commits(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]
        sha_b = three_commit_repo["sha_b"]
        sha_c = three_commit_repo["sha_c"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        assert isinstance(page, InventoryPage)
        shas = [r.sha for r in page.rows]
        # All three non-merge commits should appear
        assert sha_a in shas
        assert sha_b in shas
        assert sha_c in shas
        # Newest first
        assert shas.index(sha_c) < shas.index(sha_b) < shas.index(sha_a)

    def test_only_non_merge_commits_appear(self, tmp_path):
        """Merge commits must not appear as rows."""
        upstream = _make_repo(tmp_path, branch="main")
        _commit(upstream, "base")

        subprocess.run(
            ["git", "-C", str(upstream), "checkout", "-b", "feature"],
            capture_output=True, check=True,
        )
        _commit(upstream, "feature commit")
        subprocess.run(
            ["git", "-C", str(upstream), "checkout", "main"],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(upstream), "merge", "--no-ff", "feature", "-m", "Merge feature"],
            capture_output=True, check=True,
        )
        sha_merge = subprocess.run(
            ["git", "-C", str(upstream), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        local = tmp_path / "local"
        subprocess.run(["git", "clone", str(upstream), str(local)],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(local), "fetch", "--all"],
                       capture_output=True, check=True)

        store = self._store(tmp_path)
        svc = _make_service(local, store)

        page = svc.get_page(release_branches=[], filter="all")
        shas = [r.sha for r in page.rows]
        assert sha_merge not in shas

    def test_squash_commit_is_selectable(self, tmp_path):
        upstream = _make_repo(tmp_path, branch="main")
        _commit(upstream, "initial")
        (upstream / "sq.txt").write_text("squash\n")
        _git(["add", "sq.txt"], cwd=upstream)
        _git(["commit", "-m", "Squash merge of feature"], cwd=upstream)
        sha_squash = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(upstream),
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        local = tmp_path / "local"
        subprocess.run(["git", "clone", str(upstream), str(local)],
                       capture_output=True, check=True)

        store = self._store(tmp_path)
        svc = _make_service(local, store)

        page = svc.get_page(release_branches=[], filter="all")
        shas = [r.sha for r in page.rows]
        assert sha_squash in shas
        # selectable = True
        row = next(r for r in page.rows if r.sha == sha_squash)
        assert row.selectable is True

    def test_source_head_in_response(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        sha_c = three_commit_repo["sha_c"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=[], filter="all")
        assert page.source_head == sha_c
        assert page.source_branch == "main"

    def test_release_branch_metadata_in_response(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        branch_info = next(b for b in page.release_branches if b.name == "release/1.0")
        assert branch_info.available is True
        assert branch_info.head == sha_a

    def test_missing_release_branch_unavailable(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["nonexistent/9.9"], filter="all")
        branch_info = next(b for b in page.release_branches if b.name == "nonexistent/9.9")
        assert branch_info.available is False
        assert branch_info.head is None

    def test_no_fabricated_release_branch(self, three_commit_repo, tmp_path):
        """A branch not in remote or local refs must never appear as available."""
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["fabricated/2.0"], filter="all")
        # The branch appears in release_branches list (it was requested) but is not available
        branch_info = next(b for b in page.release_branches if b.name == "fabricated/2.0")
        assert branch_info.available is False

    # ------------------------------------------------------------------
    # Status cells
    # ------------------------------------------------------------------

    def test_ancestry_delivery_state(self, three_commit_repo, tmp_path):
        """A commit reachable from origin/release/1.0 shows delivered by ancestry."""
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_a)
        cell = row.release_status["release/1.0"]
        assert cell.state == "delivered"
        assert cell.evidence == "ancestry"

    def test_active_delivery_state(self, three_commit_repo, tmp_path):
        """An open delivery for a commit on release/1.0 shows 'open'."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        d = _make_delivery(
            id="rd-01",
            project_id="proj-123",
            source_commits=[sha_b],
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_b)
        cell = row.release_status["release/1.0"]
        assert cell.state == "open"
        assert cell.delivery_id == "rd-01"

    def test_merged_delivery_state_with_result_commits(self, three_commit_repo, tmp_path):
        """A merged delivery shows delivered with evidence=delivery and result SHAs."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        d = _make_delivery(
            id="rd-merged",
            project_id="proj-123",
            source_commits=[sha_b],
            target_branch="release/1.0",
            status=AddendumStatus.MERGED,
            result_commits=[_SHA_RESULT],
            pr_url="https://github.com/org/repo/pull/5",
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_b)
        cell = row.release_status["release/1.0"]
        assert cell.state == "delivered"
        assert cell.evidence == "delivery"
        assert cell.result_commits == [_SHA_RESULT]
        assert cell.pr_url == "https://github.com/org/repo/pull/5"

    def test_archived_delivery_state(self, three_commit_repo, tmp_path):
        """An archived delivery with no other evidence shows archived."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        d = _make_delivery(
            id="rd-arch",
            project_id="proj-123",
            source_commits=[sha_b],
            target_branch="release/1.0",
            status=AddendumStatus.ARCHIVED,
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_b)
        cell = row.release_status["release/1.0"]
        assert cell.state == "archived"
        assert cell.delivery_id == "rd-arch"

    def test_not_selected_state(self, three_commit_repo, tmp_path):
        """A commit with no delivery and not reachable from branch → not_selected."""
        repo = three_commit_repo["repo_path"]
        sha_c = three_commit_repo["sha_c"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_c)
        cell = row.release_status["release/1.0"]
        assert cell.state == "not_selected"

    def test_cherry_pick_source_sha_marked_delivered_by_delivery(
        self, three_commit_repo, tmp_path
    ):
        """Cherry-pick scenario: source SHA → delivered via merged delivery, not ancestry."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        # sha_b is NOT an ancestor of release/1.0, but there's a merged delivery
        d = _make_delivery(
            id="rd-cp",
            project_id="proj-123",
            source_commits=[sha_b],
            target_branch="release/1.0",
            status=AddendumStatus.MERGED,
            result_commits=[_SHA_RESULT],
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_b)
        cell = row.release_status["release/1.0"]
        assert cell.state == "delivered"
        assert cell.evidence == "delivery"
        assert cell.result_commits == [_SHA_RESULT]

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def test_needs_delivery_filter_excludes_fully_delivered(
        self, three_commit_repo, tmp_path
    ):
        """needs_delivery: a commit delivered on all branches is excluded."""
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        # sha_a is an ancestor of release/1.0, so it is "delivered" by ancestry
        page = svc.get_page(release_branches=["release/1.0"], filter="needs_delivery")
        shas = [r.sha for r in page.rows]
        assert sha_a not in shas

    def test_needs_delivery_filter_includes_partially_undelivered(
        self, three_commit_repo, tmp_path
    ):
        """needs_delivery: a commit undelivered on any branch appears."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="needs_delivery")
        shas = [r.sha for r in page.rows]
        assert sha_b in shas

    def test_all_filter_includes_delivered_commits(
        self, three_commit_repo, tmp_path
    ):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        shas = [r.sha for r in page.rows]
        assert sha_a in shas

    # ------------------------------------------------------------------
    # Text search
    # ------------------------------------------------------------------

    def test_text_search_by_sha(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(
            release_branches=[], filter="all", query=sha_b[:7]
        )
        shas = [r.sha for r in page.rows]
        assert sha_b in shas
        # Other commits should not match
        for sha in shas:
            assert sha_b[:7] in sha

    def test_text_search_by_subject(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(
            release_branches=[], filter="all", query="commit B"
        )
        assert page.rows, "Expected at least one row matching 'commit B'"
        assert all("commit b" in r.subject.lower() for r in page.rows)

    def test_text_search_by_association_identifier(
        self, three_commit_repo, tmp_path
    ):
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        d = _make_delivery(
            id="rd-01",
            project_id="proj-123",
            source_commits=[sha_b],
            source_identifier="FOO-99",
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(
            release_branches=["release/1.0"], filter="all", query="FOO-99"
        )
        shas = [r.sha for r in page.rows]
        assert sha_b in shas

    def test_text_search_no_match_returns_empty(
        self, three_commit_repo, tmp_path
    ):
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(
            release_branches=[], filter="all", query="xyzzy_will_never_match_12345"
        )
        assert page.rows == []

    # ------------------------------------------------------------------
    # Association enrichment (no subject guessing)
    # ------------------------------------------------------------------

    def test_association_from_ledger_source_identifier(
        self, three_commit_repo, tmp_path
    ):
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        d = _make_delivery(
            id="rd-01",
            project_id="proj-123",
            source_commits=[sha_b],
            source_kind=SourceKind.TASK,
            source_identifier="FOO-10",
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_b)
        assert row.association is not None
        assert row.association["identifier"] == "FOO-10"
        assert row.association["kind"] == "task"

    def test_no_association_for_commits_kind(
        self, three_commit_repo, tmp_path
    ):
        """commits-kind deliveries (no source_identifier) produce no association."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]

        d = _make_delivery(
            id="rd-01",
            project_id="proj-123",
            source_commits=[sha_b],
            source_kind=SourceKind.COMMITS,
            source_identifier=None,
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
        )
        store = self._store(tmp_path, [d])
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=["release/1.0"], filter="all")
        row = next(r for r in page.rows if r.sha == sha_b)
        assert row.association is None

    def test_no_subject_guessing_for_unassociated_commit(
        self, tmp_path
    ):
        """A commit with 'FOO-10' in its subject but no ledger entry has no association."""
        upstream = _make_repo(tmp_path, branch="main")
        # Commit with task-like subject
        (upstream / "f.txt").write_text("foo\n")
        _git(["add", "f.txt"], cwd=upstream)
        _git(["commit", "-m", "FOO-10: implement feature"], cwd=upstream)
        sha_guess = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(upstream),
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        local = tmp_path / "local"
        subprocess.run(["git", "clone", str(upstream), str(local)],
                       capture_output=True, check=True)

        store = self._store(tmp_path)
        svc = _make_service(local, store)

        page = svc.get_page(release_branches=[], filter="all")
        row = next((r for r in page.rows if r.sha == sha_guess), None)
        assert row is not None, "Expected commit to appear"
        assert row.association is None, "Must not guess association from subject"

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def test_pagination_no_cursor_first_page(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=[], filter="all", limit=2)
        assert len(page.rows) == 2
        assert page.next_cursor is not None

    def test_pagination_second_page_via_cursor(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        sha_a = three_commit_repo["sha_a"]
        sha_b = three_commit_repo["sha_b"]
        sha_c = three_commit_repo["sha_c"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page1 = svc.get_page(release_branches=[], filter="all", limit=2)
        assert page1.next_cursor is not None
        page2 = svc.get_page(
            release_branches=[], filter="all",
            cursor=page1.next_cursor, limit=2,
        )
        # Pages should not overlap
        shas1 = {r.sha for r in page1.rows}
        shas2 = {r.sha for r in page2.rows}
        assert shas1.isdisjoint(shas2), "Pages must not overlap"
        # Together they should cover all three commits
        all_shas = shas1 | shas2
        assert sha_a in all_shas
        assert sha_b in all_shas
        assert sha_c in all_shas

    def test_pagination_last_page_has_no_next_cursor(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        # Get all 3 commits in one page
        page = svc.get_page(release_branches=[], filter="all", limit=100)
        # With 3 commits and limit=100, next_cursor should be None
        assert page.next_cursor is None

    def test_limit_clamped_to_max(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        page = svc.get_page(release_branches=[], filter="all", limit=999)
        # Result has at most MAX_PAGE_LIMIT rows
        assert len(page.rows) <= MAX_PAGE_LIMIT

    # ------------------------------------------------------------------
    # Cursor source-head validation
    # ------------------------------------------------------------------

    def test_source_changed_error_on_stale_cursor(self, three_commit_repo, tmp_path):
        """SourceChangedError raised when cursor source_head != current source_head."""
        repo = three_commit_repo["repo_path"]
        sha_b = three_commit_repo["sha_b"]
        sha_c = three_commit_repo["sha_c"]

        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        # Build a cursor that refers to an old source head
        stale_cursor = _encode_cursor("f" * 40, sha_b)

        with pytest.raises(SourceChangedError) as exc_info:
            svc.get_page(
                release_branches=[], filter="all", cursor=stale_cursor
            )
        assert exc_info.value.cursor_head == "f" * 40
        assert exc_info.value.current_head == sha_c

    def test_malformed_cursor_raises_value_error(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store)

        with pytest.raises(ValueError, match="Malformed|cursor"):
            svc.get_page(
                release_branches=[], filter="all", cursor="not-a-valid-cursor"
            )

    # ------------------------------------------------------------------
    # Stale fallback
    # ------------------------------------------------------------------

    def test_stale_flag_when_remote_fetch_fails(self, three_commit_repo, tmp_path):
        """stale=True when remote fetch fails but local refs exist."""
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store, cache_ttl=0.0)  # no cache

        with patch(
            "oompah.release_delivery_inventory._fetch_refs",
            return_value=False,
        ):
            page = svc.get_page(release_branches=["release/1.0"], filter="all")

        assert page.stale is True

    def test_stale_branch_metadata_when_remote_fails(self, three_commit_repo, tmp_path):
        """When stale, branch info still shows available branches from local refs."""
        repo = three_commit_repo["repo_path"]
        store = self._store(tmp_path)
        svc = _make_service(repo, store, cache_ttl=0.0)

        with patch(
            "oompah.release_delivery_inventory._fetch_refs",
            return_value=False,
        ):
            page = svc.get_page(release_branches=["release/1.0"], filter="all")

        branch_info = next(
            b for b in page.release_branches if b.name == "release/1.0"
        )
        assert branch_info.available is True  # local ref exists
        assert branch_info.stale is True


# ===========================================================================
# Section 7: Cache behaviour
# ===========================================================================

class TestCacheBehaviour:
    """Tests for 60-second TTL cache and invalidation."""

    def test_cache_used_within_ttl(self, three_commit_repo, tmp_path):
        """Two calls within the TTL window do not redo git fetch."""
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=60.0)

        fetch_calls: list[int] = []
        original_fetch = svc._get_or_refresh_cache.__func__

        with patch("oompah.release_delivery_inventory._acquire_snapshot") as mock_acquire:
            mock_acquire.return_value = RefSnapshot(
                source_head="c" * 40,
                release_heads={},
                stale=False,
                fetched_at=time.monotonic(),
            )
            with patch("oompah.release_delivery_inventory._enumerate_commits") as mock_enum:
                mock_enum.return_value = []
                svc.get_page(release_branches=[], filter="all")
                svc.get_page(release_branches=[], filter="all")

        # _acquire_snapshot and _enumerate_commits called only once (second call hits cache)
        assert mock_acquire.call_count == 1
        assert mock_enum.call_count == 1

    def test_cache_refreshed_after_ttl(self, three_commit_repo, tmp_path):
        """A call after TTL expiry triggers a new fetch."""
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=0.0)  # zero TTL = always refresh

        with patch("oompah.release_delivery_inventory._acquire_snapshot") as mock_acquire:
            mock_acquire.return_value = RefSnapshot(
                source_head="c" * 40,
                release_heads={},
                stale=False,
                fetched_at=time.monotonic(),
            )
            with patch("oompah.release_delivery_inventory._enumerate_commits") as mock_enum:
                mock_enum.return_value = []
                svc.get_page(release_branches=[], filter="all")
                svc.get_page(release_branches=[], filter="all")

        # Both calls trigger a new fetch
        assert mock_acquire.call_count == 2

    def test_invalidate_project_clears_cache(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=60.0)

        with patch("oompah.release_delivery_inventory._acquire_snapshot") as mock_acquire:
            mock_acquire.return_value = RefSnapshot(
                source_head="c" * 40,
                release_heads={},
                stale=False,
                fetched_at=time.monotonic(),
            )
            with patch("oompah.release_delivery_inventory._enumerate_commits") as mock_enum:
                mock_enum.return_value = []
                svc.get_page(release_branches=[], filter="all")
                svc.invalidate("proj-123")
                svc.get_page(release_branches=[], filter="all")

        assert mock_acquire.call_count == 2

    def test_invalidate_none_clears_all(self, three_commit_repo, tmp_path):
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=60.0)

        with patch("oompah.release_delivery_inventory._acquire_snapshot") as mock_acquire:
            mock_acquire.return_value = RefSnapshot(
                source_head="c" * 40,
                release_heads={},
                stale=False,
                fetched_at=time.monotonic(),
            )
            with patch("oompah.release_delivery_inventory._enumerate_commits") as mock_enum:
                mock_enum.return_value = []
                svc.get_page(release_branches=[], filter="all")
                svc.invalidate(None)  # clear all
                svc.get_page(release_branches=[], filter="all")

        assert mock_acquire.call_count == 2

    def test_invalidate_different_project_does_not_affect_this_project(
        self, three_commit_repo, tmp_path
    ):
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=60.0)

        with patch("oompah.release_delivery_inventory._acquire_snapshot") as mock_acquire:
            mock_acquire.return_value = RefSnapshot(
                source_head="c" * 40,
                release_heads={},
                stale=False,
                fetched_at=time.monotonic(),
            )
            with patch("oompah.release_delivery_inventory._enumerate_commits") as mock_enum:
                mock_enum.return_value = []
                svc.get_page(release_branches=[], filter="all")
                svc.invalidate("proj-OTHER")  # different project
                svc.get_page(release_branches=[], filter="all")

        # Cache for "proj-123" was not dropped
        assert mock_acquire.call_count == 1

    def test_cache_keyed_by_branch_set(self, three_commit_repo, tmp_path):
        """Different branch sets use different cache entries."""
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=60.0)

        with patch("oompah.release_delivery_inventory._acquire_snapshot") as mock_acquire:
            mock_acquire.return_value = RefSnapshot(
                source_head="c" * 40,
                release_heads={"release/1.0": "a" * 40},
                stale=False,
                fetched_at=time.monotonic(),
            )
            with patch("oompah.release_delivery_inventory._enumerate_commits") as mock_enum:
                mock_enum.return_value = []
                # Different branch sets → different cache keys → two fetches
                svc.get_page(release_branches=["release/1.0"], filter="all")
                svc.get_page(release_branches=["release/2.0"], filter="all")

        assert mock_acquire.call_count == 2


# ===========================================================================
# Section 8: Thread safety
# ===========================================================================

class TestThreadSafety:
    """Verify that concurrent calls do not duplicate fetches or corrupt state."""

    def test_concurrent_requests_single_fetch(self, three_commit_repo, tmp_path):
        """Concurrent calls for the same project+branch set trigger only one fetch."""
        repo = three_commit_repo["repo_path"]
        store = _make_store_with_deliveries(tmp_path, [])
        svc = _make_service(repo, store, cache_ttl=60.0)

        fetch_count = [0]
        fetch_lock = threading.Lock()

        def _slow_acquire(*args, **kwargs):
            with fetch_lock:
                fetch_count[0] += 1
            time.sleep(0.05)
            return RefSnapshot(
                source_head="c" * 40,
                release_heads={},
                stale=False,
                fetched_at=time.monotonic(),
            )

        with patch(
            "oompah.release_delivery_inventory._acquire_snapshot",
            side_effect=_slow_acquire,
        ):
            with patch(
                "oompah.release_delivery_inventory._enumerate_commits",
                return_value=[],
            ):
                threads = [
                    threading.Thread(
                        target=lambda: svc.get_page(release_branches=[], filter="all")
                    )
                    for _ in range(5)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        assert fetch_count[0] == 1, (
            f"Expected 1 fetch but got {fetch_count[0]}: "
            "concurrent requests must serialise under the per-project lock"
        )


# ===========================================================================
# Section 9: Constructor validation
# ===========================================================================

class TestConstructorValidation:
    def test_empty_project_id_raises(self, tmp_path):
        store = ReleaseDeliveryStore(tmp_path, "proj-1")
        with pytest.raises(ValueError, match="project_id"):
            CommitInventoryService(tmp_path, "", "main", store)

    def test_empty_default_branch_raises(self, tmp_path):
        store = ReleaseDeliveryStore(tmp_path, "proj-1")
        with pytest.raises(ValueError, match="default_branch"):
            CommitInventoryService(tmp_path, "proj-1", "", store)


# ===========================================================================
# Section 10: Module-level singleton
# ===========================================================================

class TestModuleSingleton:
    def test_reset_and_get_default_service(self, tmp_path):
        from oompah.release_delivery_inventory import get_default_service

        reset_default_service()
        store = ReleaseDeliveryStore(tmp_path, "proj-1")
        svc1 = get_default_service(tmp_path, "proj-1", "main", store)
        svc2 = get_default_service(tmp_path, "proj-1", "main", store)
        assert svc1 is svc2  # same singleton

        reset_default_service()
        svc3 = get_default_service(tmp_path, "proj-1", "main", store)
        assert svc3 is not svc1  # fresh instance after reset
