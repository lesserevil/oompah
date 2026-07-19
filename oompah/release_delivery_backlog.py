"""Item-centric release delivery backlog service (OOMPAH-236).

Replaces the commit-inventory pagination model with a bounded, single-branch
backlog where each row represents a source task or epic, not an individual
commit.

Design summary
--------------

1. Accept exactly one ``selected_branch`` (a configured supported release
   branch).  Require it before loading — there is no default-all-branches view.

2. Enumerate all non-merge commits reachable from ``origin/<default_branch>``
   using the existing :class:`~oompah.release_delivery_inventory.CommitInventoryService`
   infrastructure (fetch, resolve, cache, Git sub-processes).

3. Load every ledger delivery that targets the selected branch.

4. Group commits by their ``source_identifier`` from the ledger.  A commit
   belongs to a task/epic when it appears in any delivery's ``source_commits``
   list and that delivery has a non-empty ``source_identifier``.  Commits that
   belong to no delivery (or whose delivery has ``source_kind=commits`` and no
   ``source_identifier``) are collected separately as unassociated commits.

5. Compute one aggregated :class:`~oompah.release_delivery_inventory.ReleaseStatusCell`
   per item following the same §2.3 precedence used by the commit inventory
   (active > merged/delivery > ancestry > archived > not_selected).  An item's
   status is the *most advanced* status across all its commits.

6. Optionally enrich item rows with a human-readable title retrieved from
   the tracker.  Falls back gracefully when the tracker is unavailable.

7. Return a :class:`BacklogResult` with:
   - ``items`` — item rows in newest-first order (by most recent source commit)
   - ``unassociated_commits`` — direct-to-main commits with no task/epic link
   - No ``next_cursor`` — the backlog is a complete bounded list
   - An explicit ``total_commit_count`` for display when commits are capped

Thread safety
-------------

:class:`ItemBacklogService` is safe for concurrent use.  It delegates Git
sub-processes to the existing :class:`CommitInventoryService` which uses
per-project locks internally.

Status vocabulary
-----------------

Same as :mod:`oompah.release_delivery_inventory`:
``not_selected``, ``open``, ``in_progress``, ``in_review``, ``blocked``,
``delivered``, ``archived``.

Item status precedence (most advanced wins across all commits in the item):
1. ``blocked``
2. ``in_progress``
3. ``in_review``
4. ``open``
5. ``delivered``
6. ``archived``
7. ``not_selected``
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_inventory import (
    CommitInventoryService,
    InventoryError,
    ReleaseStatusCell,
    _ACTIVE_STATUSES,
    _STATUS_TO_CELL_STATE,
    _acquire_snapshot,
    _check_ancestry_batch,
    _compute_cell,
    _enumerate_commits,
    _find_branch_commits_in_main,
    _find_pr_commits_in_main,
    _is_tracker_only_commit,
    MAX_COMMITS,
)
from oompah.release_delivery_store import ReleaseDelivery, ReleaseDeliveryStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Maximum item rows returned by default.
MAX_BACKLOG_ITEMS: int = 500

#: Maximum number of unassociated commits that will have their
#: ``tracker_only`` flag computed via a ``git diff-tree`` subprocess.
#: Commits beyond this cap default to ``tracker_only=False`` so that
#: the primary backlog (item rows) is never blocked by O(N) git calls
#: when there are many direct-to-main commits (OOMPAH-239).
MAX_UNASSOC_TRACKER_ONLY_CHECK: int = 50

#: Status rank for aggregation (higher rank = more visible / actionable).
_STATUS_RANK: dict[str, int] = {
    "blocked": 7,
    "in_progress": 6,
    "in_review": 5,
    "open": 4,
    "delivered": 3,
    "archived": 2,
    "not_selected": 1,
}


def _rank_status(state: str) -> int:
    return _STATUS_RANK.get(state, 0)


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass
class SourceCommitInfo:
    """Minimal info about one source commit included in an item row.

    Attributes:
        sha: Full 40-character SHA.
        short_sha: First 7 characters of *sha*.
        subject: First line of the commit message.
        author_name: Git author name.
        authored_at: ISO-8601 author timestamp.
    """

    sha: str
    short_sha: str
    subject: str
    author_name: str
    authored_at: str


@dataclass
class ItemRow:
    """One row in the item-centric backlog — one source task or epic.

    Attributes:
        identifier: Task/epic identifier (e.g. ``"OOMPAH-123"``).
        title: Human-readable title from the tracker, or ``None``.
        kind: ``"task"`` or ``"epic"``.
        source_commits: Ordered list of commits on the default branch that
            are associated with this item (from the delivery ledger).
        delivery_status: Aggregated delivery status for the selected branch.
        delivery_id: Ledger delivery ID governing the status, if any.
        commit_count: Number of source commits.
        most_recent_commit_at: ISO-8601 timestamp of the newest source commit,
            or ``None`` when there are no commits.
        tracker_only: ``True`` when ALL commits in this item are tracker-only
            commits (only change files under ``.oompah/``).
    """

    identifier: str
    title: str | None
    kind: str
    source_commits: list[SourceCommitInfo]
    delivery_status: ReleaseStatusCell
    delivery_id: str | None
    commit_count: int
    most_recent_commit_at: str | None
    tracker_only: bool = False


@dataclass
class UnassociatedCommitRow:
    """A direct-to-main commit with no task/epic association in the ledger.

    Attributes:
        sha: Full 40-character SHA.
        short_sha: First 7 characters of *sha*.
        subject: First line of the commit message.
        author_name: Git author name.
        authored_at: ISO-8601 author timestamp.
        delivery_status: Delivery status for the selected branch.
        delivery_id: Ledger delivery ID, if any.
        tracker_only: ``True`` when the commit only touches ``.oompah/`` files.
    """

    sha: str
    short_sha: str
    subject: str
    author_name: str
    authored_at: str
    delivery_status: ReleaseStatusCell
    delivery_id: str | None
    tracker_only: bool = False


@dataclass
class BacklogResult:
    """Complete item-centric backlog for one project / branch combination.

    Attributes:
        project_id: Project identifier.
        source_branch: Default branch name (e.g. ``"main"``).
        source_head: SHA of ``origin/<source_branch>`` at snapshot time.
        selected_branch: The single release branch shown in this backlog.
        branch_head: Current SHA of ``origin/<selected_branch>``, or ``None``.
        branch_available: ``True`` when the selected branch exists locally.
        items: Item rows (one per task/epic) in newest-first order.
        unassociated_commits: Direct-to-main commits with no item association.
        stale: ``True`` when the snapshot used stale (local) refs.
        refreshed_at: ISO-8601 timestamp of the last successful remote fetch.
        total_commit_count: Total number of commits enumerated (may be capped
            at :data:`MAX_COMMITS`).
    """

    project_id: str
    source_branch: str
    source_head: str
    selected_branch: str
    branch_head: str | None
    branch_available: bool
    items: list[ItemRow]
    unassociated_commits: list[UnassociatedCommitRow]
    stale: bool
    refreshed_at: str | None
    total_commit_count: int = 0


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_cell_for_item(
    commit_shas: list[str],
    branch: str,
    deliveries_index: dict[str, dict[str, list[ReleaseDelivery]]],
    ancestry_set: set[str],
) -> tuple[ReleaseStatusCell, str | None]:
    """Compute the aggregated :class:`ReleaseStatusCell` for an item.

    Iterates all commits belonging to the item and picks the cell with the
    highest status rank (most actionable / most visible).

    Args:
        commit_shas: All source commit SHAs for this item.
        branch: Target release branch name.
        deliveries_index: Mapping ``sha → branch → [ReleaseDelivery]``.
        ancestry_set: SHAs reachable from the release branch.

    Returns:
        ``(aggregated_cell, delivery_id)`` tuple where ``delivery_id`` is
        the governing delivery's ID (if any).
    """
    best_cell = ReleaseStatusCell(state="not_selected")
    best_delivery_id: str | None = None
    best_rank = _rank_status("not_selected")

    for sha in commit_shas:
        sha_deliveries = deliveries_index.get(sha, {})
        cell = _compute_cell(sha, branch, sha_deliveries, ancestry_set)
        rank = _rank_status(cell.state)
        if rank > best_rank:
            best_rank = rank
            best_cell = cell
            best_delivery_id = cell.delivery_id

    return best_cell, best_delivery_id


# ---------------------------------------------------------------------------
# ItemBacklogService
# ---------------------------------------------------------------------------


class ItemBacklogService:
    """Synchronous item-centric release delivery backlog service.

    Groups commits from the default branch by their source task/epic (as
    identified by the delivery ledger) and returns one :class:`ItemRow` per
    unique source identifier.  Commits that have no association in the ledger
    are returned separately as :class:`UnassociatedCommitRow` objects.

    The service is synchronous; call it from ``asyncio.to_thread`` in async
    contexts.

    Args:
        project_root: Root directory of the managed git repository.
        project_id: Project identifier.
        default_branch: Default branch name (e.g. ``"main"``).
        delivery_store: Ledger store for reading deliveries.
        fetch_timeout: Timeout for remote ``git fetch``.
        ancestry_timeout: Per-call timeout for ``git merge-base``.
        revlist_timeout: Timeout for ``git rev-list``.
        max_commits: Maximum commits to enumerate.
        max_items: Maximum item rows to return.
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
        max_commits: int = MAX_COMMITS,
        max_items: int = MAX_BACKLOG_ITEMS,
        scm: Any | None = None,
        managed_repo: str | None = None,
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
        self._max_commits = max_commits
        self._max_items = max_items
        self._scm = scm
        self._managed_repo = (managed_repo or "").strip() or None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_backlog(
        self,
        *,
        selected_branch: str,
        filter: str = "needs_delivery",
        query: str | None = None,
        tracker: Any | None = None,
        progress_callback: Callable[[str, int, int | None], None] | None = None,
    ) -> BacklogResult:
        """Return the complete item-centric backlog for *selected_branch*.

        Args:
            selected_branch: The single release branch to compute delivery
                status for.  Must be non-empty.
            filter: ``"needs_delivery"`` (default) to include only items
                where the selected branch has a non-delivered state.
                ``"all"`` to include all items.
            query: Optional text substring to match against item identifier,
                title, commit subject, or author name.  Case-insensitive.
            tracker: Optional tracker instance for resolving item titles.
                When ``None``, titles are not fetched.
            progress_callback: Optional callable invoked at each phase
                transition to report progress.  Signature:
                ``(phase: str, completed: int, total: int | None) → None``.
                Phases emitted (in order):
                - ``"loading_merged"`` — fetching merged issue list from tracker
                - ``"resolving_commits"`` — resolving source commits per issue
                - ``"comparing_ancestry"`` — batch ancestry check
                - ``"preparing_rows"`` — building item rows / fetching titles
                - ``"diagnostics"`` — computing tracker_only for unassociated commits
                Exceptions raised by the callback are silently suppressed.

        Returns:
            :class:`BacklogResult` with the complete bounded item list.

        Raises:
            :class:`~oompah.release_delivery_inventory.InventoryError`: When
                the source ref cannot be resolved.
            ``ValueError``: When *selected_branch* is empty.
        """
        if not selected_branch or not selected_branch.strip():
            raise ValueError("selected_branch must not be empty")

        selected_branch = selected_branch.strip()

        def _emit(phase: str, completed: int, total: int | None) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(phase, completed, total)
                except Exception:  # noqa: BLE001
                    pass

        # 1. Fetch refs and build snapshot
        snapshot = _acquire_snapshot(
            self._repo_path,
            default_branch=self._default_branch,
            release_branches=[selected_branch],
            fetch_timeout=self._fetch_timeout,
        )

        branch_head = snapshot.release_heads.get(selected_branch)
        branch_available = branch_head is not None

        # 2. Enumerate all non-merge commits from source (bounded)
        source_ref = f"refs/remotes/origin/{self._default_branch}"
        all_commits = _enumerate_commits(
            self._repo_path,
            source_ref=source_ref,
            max_count=self._max_commits,
            timeout=self._revlist_timeout,
        )

        total_commit_count = len(all_commits)

        # 3. Load ALL deliveries for the selected branch from the ledger
        all_deliveries = self._load_all_deliveries_for_branch(selected_branch)

        # Build indexes for fast lookup
        # sha → {branch → [ReleaseDelivery]}
        deliveries_index: dict[str, dict[str, list[ReleaseDelivery]]] = {}
        for d in all_deliveries:
            for sha in d.source_commits:
                if sha not in deliveries_index:
                    deliveries_index[sha] = {}
                if d.target_branch not in deliveries_index[sha]:
                    deliveries_index[sha][d.target_branch] = []
                deliveries_index[sha][d.target_branch].append(d)

        # sha → {identifier, kind} (from ledger source_identifier)
        association_by_sha: dict[str, dict[str, str]] = {}
        for d in all_deliveries:
            if d.source_identifier:
                for sha in d.source_commits:
                    if sha not in association_by_sha:
                        association_by_sha[sha] = {
                            "identifier": d.source_identifier,
                            "kind": d.source_kind.value,
                        }

        # identifier → ordered list of commit SHAs (in enumeration order)
        # We preserve the order from all_commits (newest first)
        item_commits_map: dict[str, list[str]] = {}  # identifier → [sha, ...]
        item_kind_map: dict[str, str] = {}           # identifier → kind
        unassociated_shas: list[str] = []

        sha_set = {c.sha for c in all_commits}
        commit_info_by_sha = {c.sha: c for c in all_commits}

        for ci in all_commits:
            assoc = association_by_sha.get(ci.sha)
            if assoc and assoc.get("identifier"):
                ident = assoc["identifier"]
                kind = assoc.get("kind", "task")
                if ident not in item_commits_map:
                    item_commits_map[ident] = []
                    item_kind_map[ident] = kind
                item_commits_map[ident].append(ci.sha)
            else:
                unassociated_shas.append(ci.sha)

        # 3b. Tracker-sourced discovery: add merged tasks/epics with no ledger record.
        #
        # The ledger only contains items that have previously been queued for
        # delivery.  Items that were merged to the default branch but never
        # queued are invisible to ledger-only discovery.  When a tracker is
        # provided, enumerate all Merged items and resolve their source commits
        # using two strategies (in order of preference):
        #
        # Strategy 1 — live work branch (OOMPAH-238):
        #   Enumerate commits from refs/remotes/origin/<work_branch> and
        #   intersect with sha_set.  Only available while the branch ref exists.
        #
        # Strategy 2 — PR commit lookup (OOMPAH-248):
        #   When the work branch ref is gone (branch was deleted after PR merge,
        #   which is normal) or was never recorded, use the persisted review_number
        #   to call scm.get_pr_commits() and intersect with sha_set.  This gives
        #   durable merge evidence that survives branch cleanup.
        #
        # Only commits already in sha_set (reachable from origin/<default_branch>)
        # are eligible — this guards against stale / non-merged branches.
        #
        # The ledger takes precedence: if an identifier is already in
        # item_commits_map (from the ledger) we extend its commit list with any
        # additional commits found, but we never override a ledger-sourced
        # association for a commit.
        if tracker is not None:
            _emit("loading_merged", 0, None)
            try:
                merged_issues = tracker.fetch_issues_by_states(["Merged"])
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "ItemBacklogService: failed to fetch merged issues from tracker: %s",
                    exc,
                )
                merged_issues = []

            _n_merged = len(merged_issues)
            _emit("resolving_commits", 0, _n_merged)

            for _i, issue in enumerate(merged_issues):
                ident = getattr(issue, "identifier", None)
                if not ident:
                    _emit("resolving_commits", _i + 1, _n_merged)
                    continue

                work_branch = getattr(issue, "work_branch", None)
                review_number = getattr(issue, "review_number", None)

                # Strategy 1: try live work branch first (fast, no network call).
                branch_shas: list[str] = []
                if work_branch:
                    branch_shas = _find_branch_commits_in_main(
                        self._repo_path,
                        work_branch,
                        sha_set,
                        timeout=self._revlist_timeout,
                    )

                # Strategy 2: fallback to PR commit lookup when branch is missing.
                # Triggered when the work branch produced no commits (ref gone)
                # or when work_branch was never recorded (None).
                if not branch_shas and review_number and self._scm and self._managed_repo:
                    branch_shas = _find_pr_commits_in_main(
                        self._scm,
                        self._managed_repo,
                        review_number,
                        sha_set,
                        timeout=self._revlist_timeout,
                    )

                _emit("resolving_commits", _i + 1, _n_merged)

                # No evidence of a merge to main → exclude this item.
                if not branch_shas:
                    continue

                kind = (getattr(issue, "issue_type", None) or "task").strip() or "task"

                if ident not in item_commits_map:
                    item_commits_map[ident] = []
                    item_kind_map[ident] = kind

                existing_for_ident = set(item_commits_map[ident])
                for sha in branch_shas:
                    # Skip commits already ledger-associated to a *different* item.
                    if sha in association_by_sha and association_by_sha[sha].get("identifier") != ident:
                        continue
                    if sha not in existing_for_ident:
                        item_commits_map[ident].append(sha)
                        existing_for_ident.add(sha)
                        # Remove from unassociated list if it was placed there
                        if sha in unassociated_shas:
                            unassociated_shas.remove(sha)

        # 4. Ancestry check — check which unassociated SHAs + item SHAs need it
        _emit("comparing_ancestry", 0, None)
        all_shas_for_ancestry = list(sha_set)
        ancestry_set: set[str] = set()
        if branch_available and branch_head:
            target_ref = f"refs/remotes/origin/{selected_branch}"
            # Only check SHAs not already covered by a delivery
            shas_needing_ancestry = [
                sha for sha in all_shas_for_ancestry
                if not any(
                    sha in d.source_commits
                    for d in all_deliveries
                    if d.status in (_ACTIVE_STATUSES | {AddendumStatus.MERGED, AddendumStatus.ARCHIVED})
                )
            ]
            if shas_needing_ancestry:
                ancestry_set = _check_ancestry_batch(
                    self._repo_path,
                    shas=shas_needing_ancestry,
                    target_ref=target_ref,
                    timeout=self._ancestry_timeout,
                )

        # 5. Fetch titles from tracker (best-effort)
        _n_items_for_titles = len(item_commits_map)
        _emit("preparing_rows", 0, _n_items_for_titles)
        title_map: dict[str, str | None] = {}
        if tracker is not None:
            for _ti, ident in enumerate(item_commits_map):
                try:
                    issue = tracker.get_issue(ident)
                    if issue is not None:
                        title_map[ident] = getattr(issue, "title", None)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "ItemBacklogService: failed to fetch title for %s: %s",
                        ident,
                        exc,
                    )
                _emit("preparing_rows", _ti + 1, _n_items_for_titles)

        # 6. Build item rows
        query_lower = query.lower().strip() if query else None
        items: list[ItemRow] = []

        for ident, commit_shas in item_commits_map.items():
            kind = item_kind_map.get(ident, "task")
            title = title_map.get(ident)

            # Compute tracker_only for all commits in this item
            tracker_only_for_item = all(
                _is_tracker_only_commit(self._repo_path, sha)
                for sha in commit_shas
                if sha in commit_info_by_sha
            ) if commit_shas else False

            # Build SourceCommitInfo list (in newest-first order)
            source_commit_infos: list[SourceCommitInfo] = []
            for sha in commit_shas:
                ci = commit_info_by_sha.get(sha)
                if ci:
                    source_commit_infos.append(
                        SourceCommitInfo(
                            sha=ci.sha,
                            short_sha=ci.sha[:7],
                            subject=ci.subject,
                            author_name=ci.author_name,
                            authored_at=ci.authored_at,
                        )
                    )

            most_recent_at = source_commit_infos[0].authored_at if source_commit_infos else None

            # Aggregated delivery status for the selected branch
            agg_cell, delivery_id = _aggregate_cell_for_item(
                commit_shas=commit_shas,
                branch=selected_branch,
                deliveries_index=deliveries_index,
                ancestry_set=ancestry_set,
            )

            # Apply filter
            if filter == "needs_delivery":
                if agg_cell.state in ("delivered", "archived"):
                    continue

            # Apply text search
            if query_lower:
                searchable_parts = [ident, title or ""]
                for ci_info in source_commit_infos:
                    searchable_parts.extend([ci_info.subject, ci_info.author_name])
                if agg_cell.pr_url:
                    searchable_parts.append(agg_cell.pr_url)
                searchable = " ".join(p for p in searchable_parts if p).lower()
                if query_lower not in searchable:
                    continue

            items.append(
                ItemRow(
                    identifier=ident,
                    title=title,
                    kind=kind,
                    source_commits=source_commit_infos,
                    delivery_status=agg_cell,
                    delivery_id=delivery_id,
                    commit_count=len(commit_shas),
                    most_recent_commit_at=most_recent_at,
                    tracker_only=tracker_only_for_item,
                )
            )

            if len(items) >= self._max_items:
                break

        # 7. Build unassociated commit rows
        _emit("diagnostics", 0, None)
        #
        # Cap the number of ``_is_tracker_only_commit`` subprocess calls to
        # MAX_UNASSOC_TRACKER_ONLY_CHECK so that a large direct-to-main commit
        # history (e.g. hundreds of commits on the default branch without any
        # delivery ledger entries) does not cause O(N) git diff-tree calls and
        # time out the HTTP endpoint (OOMPAH-239).  Commits beyond the cap have
        # their tracker_only flag defaulted to False — this is diagnostic
        # information only and does not affect primary item row construction.
        unassociated_rows: list[UnassociatedCommitRow] = []
        _unassoc_tracker_only_checked: int = 0
        for sha in unassociated_shas:
            ci = commit_info_by_sha.get(sha)
            if not ci:
                continue
            sha_deliveries = deliveries_index.get(sha, {})
            cell = _compute_cell(sha, selected_branch, sha_deliveries, ancestry_set)
            delivery_id_for_commit = cell.delivery_id
            if _unassoc_tracker_only_checked < MAX_UNASSOC_TRACKER_ONLY_CHECK:
                tracker_only = _is_tracker_only_commit(self._repo_path, sha)
                _unassoc_tracker_only_checked += 1
            else:
                tracker_only = False
            unassociated_rows.append(
                UnassociatedCommitRow(
                    sha=sha,
                    short_sha=sha[:7],
                    subject=ci.subject,
                    author_name=ci.author_name,
                    authored_at=ci.authored_at,
                    delivery_status=cell,
                    delivery_id=delivery_id_for_commit,
                    tracker_only=tracker_only,
                )
            )

        # 8. Build refreshed_at
        import datetime as _dt

        refreshed_at: str | None = None
        if snapshot.fetched_at:
            wall_now = time.time()
            mono_now = time.monotonic()
            est_wall = wall_now - (mono_now - snapshot.fetched_at)
            refreshed_at = _dt.datetime.fromtimestamp(
                est_wall, tz=_dt.timezone.utc
            ).isoformat()

        return BacklogResult(
            project_id=self._project_id,
            source_branch=self._default_branch,
            source_head=snapshot.source_head,
            selected_branch=selected_branch,
            branch_head=branch_head,
            branch_available=branch_available,
            items=items,
            unassociated_commits=unassociated_rows,
            stale=snapshot.stale,
            refreshed_at=refreshed_at,
            total_commit_count=total_commit_count,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all_deliveries_for_branch(
        self, target_branch: str
    ) -> list[ReleaseDelivery]:
        """Load all ledger deliveries targeting *target_branch*.

        Args:
            target_branch: Release branch to filter by.

        Returns:
            List of matching :class:`~oompah.release_delivery_store.ReleaseDelivery`
            objects.
        """
        try:
            ledger = self._delivery_store.read_ledger()
        except Exception as exc:
            logger.warning(
                "ItemBacklogService: failed to read delivery ledger: %s", exc
            )
            return []

        return [d for d in ledger.deliveries if d.target_branch == target_branch]
