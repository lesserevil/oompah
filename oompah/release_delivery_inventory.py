"""Commit inventory service for the release delivery UI (OOMPAH-197).

Implements :class:`CommitInventoryService` — a synchronous, independently
testable module.  All Git sub-processes run on the calling thread; callers
from async code must wrap the call with ``asyncio.to_thread``.

Plan reference
--------------
plans/release-delivery-commit-inventory.md section 4.1.

Design summary
--------------

1. For a given project + visible release branches, fetch only those refs
   from the remote (bounded timeout).  On remote failure, fall back to
   local ``refs/remotes/origin/*`` and set ``stale: true``.

2. Resolve each ref to an immutable SHA snapshot and cache the snapshot
   (plus the full non-merge commit list from the source ref) for 60 s
   per ``(project_id, frozenset(visible_branches))``.

3. Return a page of non-merge commits in topological, newest-first order,
   identified by an opaque cursor containing the source HEAD SHA and the
   last-returned SHA.  Reject a cursor when the source HEAD has changed
   (→ :class:`SourceChangedError`).

4. For each commit × release branch, compute the delivery status following
   the precedence in §2.3:

   a. Any **non-archived** delivery (open / in_progress / in_review / blocked)
      whose ``source_commits`` contains this SHA and ``target_branch`` matches
      → corresponding queue state.
   b. Any **merged** delivery whose ``source_commits`` contains this SHA and
      ``target_branch`` matches → Delivered (evidence: ``"delivery"``).
   c. SHA is reachable from ``origin/<release>`` → Delivered
      (evidence: ``"ancestry"``).
   d. Any **archived** delivery containing this SHA → Archived.
   e. Nothing → Not selected.

5. Enrich rows with task/epic info only from ledger ``source_identifier`` —
   never guess from commit subjects.

6. Cache completed project/ref-set snapshots (ref SHAs + commit list) for
   60 s per ``(project_id, frozenset(visible_branches))``.  Expose
   :meth:`CommitInventoryService.invalidate` for push webhook and delivery
   lifecycle callers.

7. Report ``stale: true`` when falling back to local tracking refs after a
   remote fetch failure.  Never fabricate a release branch that does not
   exist locally.

Thread safety
-------------

:class:`CommitInventoryService` uses an internal per-project-scope lock so
that concurrent requests for the same project + branch set do not launch
duplicate Git sub-processes.  The module-level :data:`_default_service`
singleton is safe for concurrent HTTP handlers.

Status vocabulary
-----------------

Cell ``state`` values match the plan and map to ``AddendumStatus`` where an
active delivery governs:

- ``"not_selected"`` — no delivery evidence.
- ``"open"`` — delivery in ``AddendumStatus.OPEN``.
- ``"in_progress"`` — delivery in ``AddendumStatus.IN_PROGRESS``.
- ``"in_review"`` — delivery in ``AddendumStatus.IN_REVIEW``.
- ``"blocked"`` — delivery in ``AddendumStatus.BLOCKED``.
- ``"delivered"`` — merged delivery or ancestry-proved presence.
- ``"archived"`` — archived delivery.

"""

from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_store import ReleaseDelivery, ReleaseDeliveryStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Default cache TTL in seconds.
CACHE_TTL_SECONDS: float = 60.0

#: Default maximum number of commits fetched from ``git rev-list`` per
#: project.  Limits memory use for large repositories.
MAX_COMMITS: int = 10_000

#: Default page size cap.
MAX_PAGE_LIMIT: int = 250

#: Pattern that matches a full 40-character lowercase hex SHA.
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SourceChangedError(RuntimeError):
    """Raised when a cursor's source HEAD does not match the current HEAD.

    The HTTP handler must convert this to a ``409 source_changed`` response
    so the UI refreshes instead of combining pages from two histories.

    Attributes:
        cursor_head: Source HEAD SHA recorded in the cursor.
        current_head: Actual current source HEAD SHA.
    """

    def __init__(self, cursor_head: str, current_head: str) -> None:
        super().__init__(
            f"Source HEAD changed: cursor has {cursor_head!r}, "
            f"current is {current_head!r}.  "
            "Refresh the inventory to start a new page sequence."
        )
        self.cursor_head = cursor_head
        self.current_head = current_head


class InventoryError(RuntimeError):
    """Raised when the inventory cannot be produced due to a Git or config error.

    The HTTP handler should convert this to a ``503 Service Unavailable``
    response when there is no prior stale result, or return a stale result
    with ``stale: true`` when one is available.
    """


# ---------------------------------------------------------------------------
# Internal data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CommitInfo:
    """Minimal information about one commit as returned by ``git rev-list``.

    Attributes:
        sha: Full 40-character commit SHA.
        parents: Space-separated parent SHAs (empty string for the root).
        subject: First line of the commit message.
        author_name: Git author name.
        authored_at: ISO-8601 author timestamp.
    """

    sha: str
    parents: list[str]
    subject: str
    author_name: str
    authored_at: str

    @property
    def parent_count(self) -> int:
        """Number of parents (0 = root, 1 = normal, ≥2 = merge commit)."""
        return len(self.parents)

    @property
    def is_merge(self) -> bool:
        """``True`` when this commit has two or more parents."""
        return self.parent_count >= 2


@dataclass(frozen=True)
class RefSnapshot:
    """Immutable snapshot of the source and release ref SHAs at fetch time.

    Attributes:
        source_head: Full SHA of ``origin/<default_branch>``.
        release_heads: Mapping from release branch name to its current SHA.
            The value is ``None`` when the branch does not exist locally.
        stale: ``True`` when any ref came from the local stale-fallback path
            (because the remote was unreachable).
        fetched_at: ``time.monotonic()`` timestamp of the fetch.
    """

    source_head: str
    release_heads: dict[str, str | None]
    stale: bool
    fetched_at: float


@dataclass
class _CacheEntry:
    """One cached project+branch-set result.

    Attributes:
        snapshot: Immutable ref snapshot (SHAs).
        commits: Full non-merge commit list from the source ref.
        cached_at: ``time.monotonic()`` timestamp when the entry was stored.
    """

    snapshot: RefSnapshot
    commits: list[_CommitInfo]
    cached_at: float


# ---------------------------------------------------------------------------
# Public result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseStatusCell:
    """Per-branch delivery status for one source commit.

    Attributes:
        state: One of the status vocabulary strings listed in the module
            docstring (e.g. ``"not_selected"``, ``"delivered"``).
        evidence: How delivery was proved (``"delivery"`` or ``"ancestry"``),
            or ``None`` when state is not ``"delivered"``.
        delivery_id: The ledger delivery ID, if any delivery governs this cell.
        pr_url: PR URL from the governing delivery, when present.
        result_commits: Target SHAs written by the executor (cherry-pick
            result), from the governing delivery.
    """

    state: str
    evidence: str | None = None
    delivery_id: str | None = None
    pr_url: str | None = None
    result_commits: list[str] = field(default_factory=list)


@dataclass
class CommitRow:
    """One row in the inventory table — one non-merge source commit.

    Attributes:
        sha: Full 40-character SHA.
        short_sha: First 7 characters of *sha*.
        subject: First line of the commit message.
        author_name: Git author name.
        authored_at: ISO-8601 author timestamp.
        parents: Full SHAs of parent commits.
        selectable: ``True`` for non-merge commits (always ``True`` here since
            merge commits are excluded from enumeration).
        association: Linked task/epic info from the ledger, or ``None``.
            Dict keys: ``kind`` (``"task"`` | ``"epic"``),
            ``identifier`` (e.g. ``"FOO-10"``).
        release_status: Mapping from branch name to :class:`ReleaseStatusCell`.
    """

    sha: str
    short_sha: str
    subject: str
    author_name: str
    authored_at: str
    parents: list[str]
    selectable: bool
    association: dict[str, str] | None
    release_status: dict[str, ReleaseStatusCell]


@dataclass
class ReleaseBranchInfo:
    """Branch metadata returned in the response header.

    Attributes:
        name: Branch name (e.g. ``"release/1.0"``).
        head: Current SHA of ``origin/<name>``, or ``None`` if unavailable.
        available: ``True`` when the branch exists on the remote (or locally
            in the stale-fallback case).
        stale: ``True`` when the info came from the local stale-fallback path.
    """

    name: str
    head: str | None
    available: bool
    stale: bool = False


@dataclass
class InventoryPage:
    """One page of the commit inventory response.

    Attributes:
        project_id: Project identifier.
        source_branch: Default branch name (e.g. ``"main"``).
        source_head: SHA of ``origin/<source_branch>`` at snapshot time.
        release_branches: Ordered metadata for each visible release branch.
        rows: Ordered list of :class:`CommitRow` objects for this page.
        next_cursor: Opaque cursor to pass for the next page, or ``None``
            when this is the last page.
        stale: ``True`` when the snapshot used stale (local) refs.
        refreshed_at: ISO-8601 timestamp of the last successful remote fetch,
            or ``None`` when no fresh fetch has occurred.
    """

    project_id: str
    source_branch: str
    source_head: str
    release_branches: list[ReleaseBranchInfo]
    rows: list[CommitRow]
    next_cursor: str | None
    stale: bool
    refreshed_at: str | None


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------


def _encode_cursor(source_head: str, after_sha: str) -> str:
    """Return an opaque base64-encoded cursor string.

    Args:
        source_head: Source HEAD SHA at time of first page request.
        after_sha: Full SHA of the last commit returned in the current page.

    Returns:
        URL-safe base64 string encoding a JSON payload.
    """
    payload = {"source_head": source_head, "after_sha": after_sha}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    """Decode a cursor produced by :func:`_encode_cursor`.

    Args:
        cursor: Opaque cursor string.

    Returns:
        ``(source_head, after_sha)`` tuple.

    Raises:
        ValueError: When the cursor is malformed or missing required fields.
    """
    # Re-pad to a multiple of 4
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
        payload = json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Malformed cursor: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Cursor payload must be a JSON object, got {type(payload)}")
    source_head = payload.get("source_head", "")
    after_sha = payload.get("after_sha", "")
    if not _FULL_SHA_RE.match(source_head):
        raise ValueError(f"Cursor source_head is not a valid SHA: {source_head!r}")
    if not _FULL_SHA_RE.match(after_sha):
        raise ValueError(f"Cursor after_sha is not a valid SHA: {after_sha!r}")
    return source_head, after_sha


# ---------------------------------------------------------------------------
# Low-level Git helpers
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str],
    *,
    repo_path: str | Path,
    timeout: int = 30,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a git command in *repo_path* and return the result.

    Args:
        args: Arguments after ``"git"`` (not including ``"git"`` itself).
        repo_path: Working directory for the subprocess.
        timeout: Subprocess timeout in seconds.
        check: If ``True``, raise :class:`subprocess.CalledProcessError` on
            non-zero exit code.

    Returns:
        :class:`subprocess.CompletedProcess` with ``stdout`` and ``stderr``
        as text strings.

    Raises:
        RuntimeError: On subprocess timeout or OS-level failure.
        subprocess.CalledProcessError: When *check* is ``True`` and exit != 0.
    """
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git {args[0]!r} timed out after {timeout}s in {repo_path}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Failed to run git {args[0]!r} in {repo_path}: {exc}"
        ) from exc


def _fetch_refs(
    repo_path: str | Path,
    *,
    default_branch: str,
    release_branches: list[str],
    timeout: int = 30,
) -> bool:
    """Fetch the source and release refs from the remote.

    Runs::

        git fetch origin <default_branch> [<release_branch>...] --no-tags

    Args:
        repo_path: Local git clone path.
        default_branch: Default branch name (e.g. ``"main"``).
        release_branches: Release branch names to fetch.
        timeout: Subprocess timeout in seconds.

    Returns:
        ``True`` on success, ``False`` on any failure.
    """
    refs = [default_branch] + list(release_branches)
    result = _run_git(
        ["fetch", "origin"] + refs + ["--no-tags"],
        repo_path=repo_path,
        timeout=timeout,
    )
    if result.returncode != 0:
        logger.warning(
            "CommitInventoryService: git fetch failed (rc=%d): %s",
            result.returncode,
            (result.stderr or result.stdout or "").strip()[:200],
        )
        return False
    return True


def _resolve_remote_ref(
    repo_path: str | Path,
    branch: str,
    *,
    timeout: int = 10,
) -> str | None:
    """Resolve ``refs/remotes/origin/<branch>`` to a full SHA.

    First tries the remote tracking ref; falls back to ``origin/<branch>``.
    Returns ``None`` when the ref does not exist locally.

    Args:
        repo_path: Local git clone path.
        branch: Branch name (without ``origin/`` prefix).
        timeout: Subprocess timeout in seconds.

    Returns:
        40-character hex SHA or ``None``.
    """
    for ref in (f"refs/remotes/origin/{branch}", f"origin/{branch}"):
        result = _run_git(
            ["rev-parse", "--verify", ref],
            repo_path=repo_path,
            timeout=timeout,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if _FULL_SHA_RE.match(sha):
                return sha
    return None


def _enumerate_commits(
    repo_path: str | Path,
    *,
    source_ref: str,
    max_count: int = MAX_COMMITS,
    timeout: int = 60,
) -> list[_CommitInfo]:
    """Enumerate non-merge commits reachable from *source_ref* in topo order.

    Uses a multi-line record format to avoid embedded-NUL issues with
    subprocess argument strings::

        git rev-list --topo-order --no-merges
            --format=<multi-line sentinel format>
            --max-count=<max_count>
            <source_ref>

    Each commit occupies 6 lines:
    - SHA (40 hex chars)
    - Space-separated parent SHAs (may be empty for root commits)
    - Subject (first line of commit message)
    - Author name
    - Author ISO date
    - Sentinel line ``<COMMIT-END>``

    The ``commit <sha>`` header line emitted by ``git rev-list --format``
    is detected by the ``^commit `` prefix and skipped.

    Args:
        repo_path: Local git clone path.
        source_ref: Full ref or SHA to enumerate from (e.g.
            ``"refs/remotes/origin/main"``).
        max_count: Maximum number of commits to return.
        timeout: Subprocess timeout in seconds.

    Returns:
        Ordered list of :class:`_CommitInfo` objects, newest first.

    Raises:
        RuntimeError: On subprocess failure or timeout.
    """
    sentinel = "<COMMIT-END>"
    fmt = f"%H%n%P%n%s%n%an%n%aI%n{sentinel}"

    result = _run_git(
        [
            "rev-list",
            "--topo-order",
            "--no-merges",
            f"--format={fmt}",
            f"--max-count={max_count}",
            source_ref,
        ],
        repo_path=repo_path,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git rev-list failed (rc={result.returncode}) for {source_ref!r}: "
            f"{(result.stderr or result.stdout or '').strip()[:300]}"
        )

    commits: list[_CommitInfo] = []
    # Collect lines for each commit between sentinel records.
    # git rev-list --format emits a "commit <sha>" header before each
    # formatted record; we skip those lines.
    current: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        # Skip the "commit <sha>" header emitted by git rev-list
        if line.startswith("commit ") and _FULL_SHA_RE.match(line[7:]):
            continue
        if line == sentinel:
            # Parse the accumulated fields
            if len(current) >= 5:
                sha = current[0].strip()
                parents_raw = current[1].strip()
                subject = current[2]  # preserve leading spaces for display
                author_name = current[3]
                authored_at = current[4].strip()
                if _FULL_SHA_RE.match(sha):
                    parent_list = [
                        p for p in parents_raw.split()
                        if _FULL_SHA_RE.match(p)
                    ]
                    commits.append(
                        _CommitInfo(
                            sha=sha,
                            parents=parent_list,
                            subject=subject,
                            author_name=author_name,
                            authored_at=authored_at,
                        )
                    )
            current = []
        else:
            current.append(line)

    return commits


def _check_ancestry_batch(
    repo_path: str | Path,
    *,
    shas: list[str],
    target_ref: str,
    timeout: int = 10,
) -> set[str]:
    """Return the subset of *shas* that are ancestors of *target_ref*.

    Uses ``git rev-list <target_ref> --ancestry-path`` restricted to the
    candidate set to avoid loading the full release-branch history.  Falls
    back to per-SHA ``git merge-base --is-ancestor`` when the batch approach
    is unavailable.

    For each SHA in *shas*, calls::

        git merge-base --is-ancestor <sha> <target_ref>

    and collects those where the exit code is 0 (= is ancestor).

    Args:
        repo_path: Local git clone path.
        shas: Candidate source commit SHAs to check.
        target_ref: Remote tracking ref for the release branch (e.g.
            ``"refs/remotes/origin/release/1.0"``).
        timeout: Per-subprocess timeout in seconds.

    Returns:
        Set of SHAs from *shas* that are reachable from *target_ref*.
    """
    if not shas:
        return set()
    ancestors: set[str] = set()
    for sha in shas:
        result = _run_git(
            ["merge-base", "--is-ancestor", sha, target_ref],
            repo_path=repo_path,
            timeout=timeout,
        )
        if result.returncode == 0:
            ancestors.add(sha)
    return ancestors


# ---------------------------------------------------------------------------
# Status precedence helpers
# ---------------------------------------------------------------------------

#: Active (non-terminal, non-archived) statuses that govern a cell.
_ACTIVE_STATUSES: frozenset[AddendumStatus] = frozenset(
    {
        AddendumStatus.OPEN,
        AddendumStatus.IN_PROGRESS,
        AddendumStatus.IN_REVIEW,
        AddendumStatus.BLOCKED,
    }
)

#: Map from AddendumStatus to the string used in the API cell state.
_STATUS_TO_CELL_STATE: dict[AddendumStatus, str] = {
    AddendumStatus.OPEN: "open",
    AddendumStatus.IN_PROGRESS: "in_progress",
    AddendumStatus.IN_REVIEW: "in_review",
    AddendumStatus.BLOCKED: "blocked",
    AddendumStatus.MERGED: "delivered",
    AddendumStatus.ARCHIVED: "archived",
}


def _compute_cell(
    sha: str,
    branch: str,
    deliveries_by_branch: dict[str, list[ReleaseDelivery]],
    ancestry_set: set[str],
) -> ReleaseStatusCell:
    """Compute one status cell for *(sha, branch)* following §2.3 precedence.

    Args:
        sha: Source commit SHA.
        branch: Release branch name.
        deliveries_by_branch: Mapping from branch name to a list of
            :class:`ReleaseDelivery` objects that contain *sha* in their
            ``source_commits``.
        ancestry_set: Set of source SHAs that are reachable from the
            release branch (i.e. ``git merge-base --is-ancestor`` is True).

    Returns:
        :class:`ReleaseStatusCell` with the computed state.
    """
    branch_deliveries = deliveries_by_branch.get(branch, [])

    # Precedence 1: active delivery (open/in_progress/in_review/blocked)
    for d in branch_deliveries:
        if d.status in _ACTIVE_STATUSES:
            return ReleaseStatusCell(
                state=_STATUS_TO_CELL_STATE[d.status],
                delivery_id=d.id,
                pr_url=d.pr_url,
                result_commits=list(d.result_commits) if d.result_commits else [],
            )

    # Precedence 2: merged delivery
    for d in branch_deliveries:
        if d.status == AddendumStatus.MERGED:
            return ReleaseStatusCell(
                state="delivered",
                evidence="delivery",
                delivery_id=d.id,
                pr_url=d.pr_url,
                result_commits=list(d.result_commits) if d.result_commits else [],
            )

    # Precedence 3: ancestry
    if sha in ancestry_set:
        return ReleaseStatusCell(
            state="delivered",
            evidence="ancestry",
        )

    # Precedence 4: archived delivery
    for d in branch_deliveries:
        if d.status == AddendumStatus.ARCHIVED:
            return ReleaseStatusCell(
                state="archived",
                delivery_id=d.id,
            )

    # Precedence 5: not selected
    return ReleaseStatusCell(state="not_selected")


# ---------------------------------------------------------------------------
# RefSnapshot acquisition
# ---------------------------------------------------------------------------


def _acquire_snapshot(
    repo_path: str | Path,
    *,
    default_branch: str,
    release_branches: list[str],
    fetch_timeout: int = 30,
) -> RefSnapshot:
    """Fetch remote refs and build an immutable :class:`RefSnapshot`.

    Attempts a real ``git fetch``.  On failure, falls back to local
    ``refs/remotes/origin/*`` and marks ``stale: True``.

    Args:
        repo_path: Local git clone path.
        default_branch: Default branch name.
        release_branches: Release branch names to resolve.
        fetch_timeout: Timeout for the ``git fetch`` call.

    Returns:
        :class:`RefSnapshot` with SHA snapshot and staleness flag.

    Raises:
        :class:`InventoryError`: When the source ref cannot be resolved even
            from local refs (no prior fetch for this branch).
    """
    stale = False
    fetch_ok = _fetch_refs(
        repo_path,
        default_branch=default_branch,
        release_branches=release_branches,
        timeout=fetch_timeout,
    )
    if not fetch_ok:
        stale = True
        logger.warning(
            "CommitInventoryService: remote fetch failed for %s; using stale local refs",
            default_branch,
        )

    # Resolve source HEAD
    source_head = _resolve_remote_ref(repo_path, default_branch)
    if not source_head:
        raise InventoryError(
            f"Cannot resolve refs/remotes/origin/{default_branch!r}: "
            "no prior fetch and remote is unreachable.  "
            "Ensure the repository has been cloned and at least one fetch has succeeded."
        )

    # Resolve release branch HEADs
    release_heads: dict[str, str | None] = {}
    for branch in release_branches:
        release_heads[branch] = _resolve_remote_ref(repo_path, branch)

    return RefSnapshot(
        source_head=source_head,
        release_heads=release_heads,
        stale=stale,
        fetched_at=time.monotonic(),
    )


# ---------------------------------------------------------------------------
# CommitInventoryService
# ---------------------------------------------------------------------------


class CommitInventoryService:
    """Synchronous commit inventory service for the release delivery UI.

    Enumerate non-merge commits reachable from ``origin/<default_branch>``,
    compute per-release delivery status, and return paginated results.

    The service is synchronous; call it from ``asyncio.to_thread`` in async
    contexts.  It is independently testable without a running oompah server.

    Args:
        project_root: Root directory of the managed git repository.
        project_id: Project identifier (used for cache keying and logging).
        default_branch: Default branch name (e.g. ``"main"``).
        delivery_store: Ledger store for reading deliveries.
        fetch_timeout: Timeout for remote ``git fetch``.
        ancestry_timeout: Per-call timeout for ``git merge-base``.
        revlist_timeout: Timeout for ``git rev-list``.
        cache_ttl: How long to cache completed ref snapshots and commit lists.
        max_commits: Maximum commits to enumerate per cache entry.

    Example::

        store = ReleaseDeliveryStore(project_root, project_id)
        svc = CommitInventoryService(
            project_root, project_id, "main", store
        )
        page = svc.get_page(release_branches=["release/1.0"], limit=50)
    """

    def __init__(
        self,
        project_root: str | Path,
        project_id: str,
        default_branch: str,
        delivery_store: ReleaseDeliveryStore,
        *,
        fetch_timeout: int = 30,
        ancestry_timeout: int = 10,
        revlist_timeout: int = 60,
        cache_ttl: float = CACHE_TTL_SECONDS,
        max_commits: int = MAX_COMMITS,
    ) -> None:
        self._repo_path = Path(project_root)
        self._project_id = str(project_id).strip()
        if not self._project_id:
            raise ValueError("project_id must not be empty")
        self._default_branch = str(default_branch).strip()
        if not self._default_branch:
            raise ValueError("default_branch must not be empty")
        self._delivery_store = delivery_store
        self._fetch_timeout = fetch_timeout
        self._ancestry_timeout = ancestry_timeout
        self._revlist_timeout = revlist_timeout
        self._cache_ttl = cache_ttl
        self._max_commits = max_commits

        # Cache: (project_id, frozenset(branch_names)) → _CacheEntry
        self._cache: dict[tuple[str, frozenset[str]], _CacheEntry] = {}
        # Per-cache-key lock to prevent duplicate concurrent fetches
        self._cache_locks: dict[tuple[str, frozenset[str]], threading.Lock] = {}
        self._meta_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_page(
        self,
        *,
        release_branches: list[str],
        cursor: str | None = None,
        filter: str = "needs_delivery",
        query: str | None = None,
        limit: int = 100,
    ) -> InventoryPage:
        """Return one page of the commit inventory.

        Args:
            release_branches: Ordered list of release branch names to show.
                Must be a subset of the project's configured
                ``supported_release_branches``.  If empty, the source
                snapshot is returned with no branch columns and no ancestry
                checks.
            cursor: Opaque pagination cursor from the previous page's
                ``next_cursor``.  ``None`` for the first page.
            filter: ``"needs_delivery"`` (default) to include only rows
                where at least one visible branch has a non-delivered state;
                ``"all"`` to include all commits.
            query: Optional text substring to match against SHA, subject,
                author name, source association identifier, or PR URL.
                Case-insensitive.
            limit: Maximum rows to return per page.  Clamped to
                ``[1, MAX_PAGE_LIMIT]``.

        Returns:
            :class:`InventoryPage` for the requested page.

        Raises:
            :class:`SourceChangedError`: When *cursor* refers to a source
                HEAD that is no longer current.
            :class:`InventoryError`: When the source ref cannot be resolved.
            :class:`ValueError`: When *cursor* is malformed or *limit* is
                invalid.
        """
        limit = max(1, min(int(limit), MAX_PAGE_LIMIT))

        # Validate and normalise branch list
        visible_branches: list[str] = list(dict.fromkeys(release_branches))  # deduplicate preserving order

        # Obtain (or refresh) the cached snapshot + commit list
        cache_key: tuple[str, frozenset[str]] = (
            self._project_id,
            frozenset(visible_branches),
        )
        entry = self._get_or_refresh_cache(cache_key, visible_branches)
        snapshot = entry.snapshot
        all_commits = entry.commits

        # Decode cursor and validate source HEAD
        after_sha: str | None = None
        if cursor is not None:
            cursor_head, after_sha = _decode_cursor(cursor)
            if cursor_head != snapshot.source_head:
                raise SourceChangedError(
                    cursor_head=cursor_head,
                    current_head=snapshot.source_head,
                )

        # Paginate: find start position
        if after_sha is not None:
            try:
                idx = next(
                    i for i, c in enumerate(all_commits) if c.sha == after_sha
                )
                page_commits = all_commits[idx + 1 :]
            except StopIteration:
                # after_sha not found (possibly truncated) — start from beginning
                page_commits = all_commits
        else:
            page_commits = all_commits

        # Load ledger deliveries for all commits in the full page (before filter)
        # to support text-search over association and PR URL
        # We load for the slice we're about to examine, bounded.
        examine_window = page_commits[: limit * 4 + 100]  # generous window for filtering

        # Gather all deliveries touching this project's target branches
        all_deliveries = self._load_deliveries(
            shas={c.sha for c in examine_window},
            target_branches=visible_branches,
        )

        # For each release branch, run ancestry checks for commits not
        # already covered by a delivery
        ancestry_by_branch: dict[str, set[str]] = {}
        for branch in visible_branches:
            head = snapshot.release_heads.get(branch)
            if head is None:
                # Branch doesn't exist locally — no ancestry
                ancestry_by_branch[branch] = set()
                continue
            # Collect SHAs that don't already have delivery evidence for this branch
            shas_needing_ancestry = [
                c.sha
                for c in examine_window
                if not any(
                    c.sha in d.source_commits and d.target_branch == branch
                    for d in all_deliveries
                    if d.status in (_ACTIVE_STATUSES | {AddendumStatus.MERGED, AddendumStatus.ARCHIVED})
                )
            ]
            if shas_needing_ancestry:
                target_ref = f"refs/remotes/origin/{branch}"
                ancestry_by_branch[branch] = _check_ancestry_batch(
                    self._repo_path,
                    shas=shas_needing_ancestry,
                    target_ref=target_ref,
                    timeout=self._ancestry_timeout,
                )
            else:
                ancestry_by_branch[branch] = set()

        # Build deliveries-by-(sha, branch) index
        deliveries_index: dict[str, dict[str, list[ReleaseDelivery]]] = {}
        for d in all_deliveries:
            for sha in d.source_commits:
                if sha not in deliveries_index:
                    deliveries_index[sha] = {}
                if d.target_branch not in deliveries_index[sha]:
                    deliveries_index[sha][d.target_branch] = []
                deliveries_index[sha][d.target_branch].append(d)

        # Build association enrichment: sha → association dict
        association_index: dict[str, dict[str, str]] = {}
        for d in all_deliveries:
            if d.source_identifier:
                for sha in d.source_commits:
                    if sha not in association_index:
                        association_index[sha] = {
                            "kind": d.source_kind.value,
                            "identifier": d.source_identifier,
                        }

        # Build rows, apply filter, apply text search, then paginate
        rows: list[CommitRow] = []
        last_sha: str | None = None
        result_count = 0

        query_lower = query.lower().strip() if query else None

        for ci in examine_window:
            # Build release_status for this commit
            release_status: dict[str, ReleaseStatusCell] = {}
            branch_deliveries_for_sha: dict[str, list[ReleaseDelivery]] = (
                deliveries_index.get(ci.sha, {})
            )
            for branch in visible_branches:
                release_status[branch] = _compute_cell(
                    ci.sha,
                    branch,
                    branch_deliveries_for_sha,
                    ancestry_by_branch.get(branch, set()),
                )

            assoc = association_index.get(ci.sha)

            row = CommitRow(
                sha=ci.sha,
                short_sha=ci.sha[:7],
                subject=ci.subject,
                author_name=ci.author_name,
                authored_at=ci.authored_at,
                parents=list(ci.parents),
                selectable=True,  # only non-merge commits are enumerated
                association=assoc,
                release_status=release_status,
            )

            # Apply filter
            if filter == "needs_delivery":
                has_undelivered = any(
                    cell.state not in ("delivered", "archived")
                    for cell in release_status.values()
                ) if release_status else True
                if not has_undelivered:
                    continue

            # Apply text search
            if query_lower:
                searchable_parts = [
                    ci.sha,
                    ci.subject,
                    ci.author_name,
                ]
                if assoc:
                    searchable_parts.append(assoc.get("identifier") or "")
                for cell in release_status.values():
                    if cell.pr_url:
                        searchable_parts.append(cell.pr_url)
                searchable = " ".join(p for p in searchable_parts if p).lower()
                if query_lower not in searchable:
                    continue

            rows.append(row)
            last_sha = ci.sha
            result_count += 1
            if result_count >= limit:
                break

        # Determine next_cursor
        next_cursor: str | None = None
        if result_count >= limit and last_sha is not None:
            # Check if there are more commits after the current window
            # We already found `limit` matching rows; there may be more
            next_cursor = _encode_cursor(snapshot.source_head, last_sha)

        # Build release branch metadata for response
        import datetime as _dt

        branch_infos: list[ReleaseBranchInfo] = [
            ReleaseBranchInfo(
                name=branch,
                head=snapshot.release_heads.get(branch),
                available=snapshot.release_heads.get(branch) is not None,
                stale=snapshot.stale,
            )
            for branch in visible_branches
        ]

        refreshed_at: str | None = None
        if snapshot.fetched_at:
            # Convert monotonic to a rough wall-clock estimate; for
            # display/staleness labelling only.
            wall_now = time.time()
            mono_now = time.monotonic()
            est_wall = wall_now - (mono_now - snapshot.fetched_at)
            refreshed_at = _dt.datetime.fromtimestamp(
                est_wall, tz=_dt.timezone.utc
            ).isoformat()

        return InventoryPage(
            project_id=self._project_id,
            source_branch=self._default_branch,
            source_head=snapshot.source_head,
            release_branches=branch_infos,
            rows=rows,
            next_cursor=next_cursor,
            stale=snapshot.stale,
            refreshed_at=refreshed_at,
        )

    def invalidate(self, project_id: str | None = None) -> None:
        """Invalidate cached snapshots.

        Drop the cached ref snapshot and commit list for the given project,
        forcing a fresh ``git fetch`` on the next call.  When *project_id*
        is ``None``, all cached entries are dropped.

        Call this after a push webhook or delivery lifecycle update.

        Args:
            project_id: Project to invalidate, or ``None`` to invalidate all.
        """
        with self._meta_lock:
            if project_id is None:
                self._cache.clear()
                logger.debug("CommitInventoryService: invalidated all caches")
            else:
                keys_to_drop = [k for k in self._cache if k[0] == project_id]
                for k in keys_to_drop:
                    del self._cache[k]
                logger.debug(
                    "CommitInventoryService: invalidated %d cache entries for %s",
                    len(keys_to_drop),
                    project_id,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_project_scope_lock(
        self, cache_key: tuple[str, frozenset[str]]
    ) -> threading.Lock:
        """Return (or create) the serialisation lock for *cache_key*."""
        with self._meta_lock:
            if cache_key not in self._cache_locks:
                self._cache_locks[cache_key] = threading.Lock()
            return self._cache_locks[cache_key]

    def _get_or_refresh_cache(
        self,
        cache_key: tuple[str, frozenset[str]],
        visible_branches: list[str],
    ) -> _CacheEntry:
        """Return a valid cache entry, refreshing if expired or missing.

        Args:
            cache_key: ``(project_id, frozenset(branch_names))``.
            visible_branches: Ordered list of branch names (for fetch).

        Returns:
            Valid :class:`_CacheEntry`.
        """
        lock = self._get_project_scope_lock(cache_key)
        with lock:
            now = time.monotonic()
            cached = self._cache.get(cache_key)
            if cached is not None and (now - cached.cached_at) < self._cache_ttl:
                return cached

            # Refresh
            snapshot = _acquire_snapshot(
                self._repo_path,
                default_branch=self._default_branch,
                release_branches=visible_branches,
                fetch_timeout=self._fetch_timeout,
            )
            source_ref = f"refs/remotes/origin/{self._default_branch}"
            commits = _enumerate_commits(
                self._repo_path,
                source_ref=source_ref,
                max_count=self._max_commits,
                timeout=self._revlist_timeout,
            )
            entry = _CacheEntry(
                snapshot=snapshot,
                commits=commits,
                cached_at=now,
            )
            with self._meta_lock:
                self._cache[cache_key] = entry
            logger.debug(
                "CommitInventoryService: cached %d commits for %s (stale=%s)",
                len(commits),
                self._project_id,
                snapshot.stale,
            )
            return entry

    def _load_deliveries(
        self,
        *,
        shas: set[str],
        target_branches: list[str],
    ) -> list[ReleaseDelivery]:
        """Load all ledger deliveries that touch any SHA in *shas* and any branch in *target_branches*.

        Uses :meth:`ReleaseDeliveryStore.read_ledger` to read all deliveries,
        then filters in Python.

        Args:
            shas: Set of source commit SHAs of interest.
            target_branches: Release branch names of interest.

        Returns:
            List of matching :class:`ReleaseDelivery` objects.
        """
        if not shas and not target_branches:
            return []
        try:
            ledger = self._delivery_store.read_ledger()
        except Exception as exc:
            logger.warning(
                "CommitInventoryService: failed to read delivery ledger: %s", exc
            )
            return []

        branch_set = set(target_branches)
        result: list[ReleaseDelivery] = []
        for d in ledger.deliveries:
            if d.target_branch not in branch_set:
                continue
            # Include when any source_commit intersects with the SHA set we care about
            if shas and not (set(d.source_commits) & shas):
                continue
            result.append(d)
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Default service instance.  Initialised lazily via :func:`get_default_service`.
_default_service: CommitInventoryService | None = None
_default_service_lock = threading.Lock()


def get_default_service(
    project_root: str | Path,
    project_id: str,
    default_branch: str,
    delivery_store: ReleaseDeliveryStore,
) -> CommitInventoryService:
    """Return (or create) the module-level :class:`CommitInventoryService` singleton.

    The singleton is created lazily on first call.  If the project or branch
    configuration has changed, call :func:`reset_default_service` first.

    Args:
        project_root: Root directory of the managed git repository.
        project_id: Project identifier.
        default_branch: Default branch name.
        delivery_store: Ledger store for reading deliveries.

    Returns:
        Shared :class:`CommitInventoryService` instance.
    """
    global _default_service
    with _default_service_lock:
        if _default_service is None:
            _default_service = CommitInventoryService(
                project_root=project_root,
                project_id=project_id,
                default_branch=default_branch,
                delivery_store=delivery_store,
            )
    return _default_service


def reset_default_service() -> None:
    """Reset the module-level singleton (mainly for testing).

    After calling this, the next :func:`get_default_service` call creates a
    fresh instance.
    """
    global _default_service
    with _default_service_lock:
        _default_service = None
