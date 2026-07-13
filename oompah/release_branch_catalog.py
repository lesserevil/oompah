"""Release-branch catalog for supported release lines (OOMPAH-175).

Implements :class:`ReleaseBranchCatalog`, which resolves the current set of
remotely-available branches from a project's ``supported_release_branches``
list.  The catalog is consumed by:

- ``GET /api/v1/projects/{project_id}/release-branches`` — returns a
  structured JSON response with availability and staleness flags.
- The release-addendum approval dialog — to offer only verified candidates to
  the operator.

Design (section 5 of plans/release-branch-addendums.md)
--------------------------------------------------------

1. Run ``git ls-remote --heads origin`` in the project's ``repo_path``.
   Parse ref names; cache successful results for 60 seconds per project.
2. On remote failure, fall back to local ``refs/remotes/origin/*`` and mark
   the response ``stale: true``.
3. Offer a branch as *available* only when it exists remotely **and** is
   listed in ``supported_release_branches``.
4. Preserve the project's configured ordering; unconfigured branches use
   reverse-natural (``release/1.11`` before ``release/1.9``) then lexical
   ordering.
5. Return branches already represented by an addendum even if deleted, marked
   ``available: false``, so history remains inspectable.
6. Invalidate the cache when a tracked-branch push webhook arrives and after a
   successful addendum merge.

Discovery failure contract
--------------------------

- **First load** (no prior successful fetch): raise
  :class:`CatalogDiscoveryError` so the API can return ``503``.
- **Stale fallback** (prior success but remote currently unreachable): return
  a :class:`CatalogResult` with ``stale=True`` on every branch entry.

Thread safety
-------------

:class:`ReleaseBranchCatalog` uses an internal per-project lock so that a
slow ``git ls-remote`` call does not launch concurrent duplicate sub-processes
for the same project.  The module-level :data:`_default_catalog` singleton is
safe for concurrent HTTP handlers.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: How long a successful remote-discovery result is cached, in seconds.
CACHE_TTL_SECONDS: int = 60

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CatalogDiscoveryError(RuntimeError):
    """Raised when branch discovery fails on first load (no prior cache entry).

    The HTTP handler converts this to a ``503 Service Unavailable`` response.
    """


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseBranch:
    """One entry in the catalog response.

    Attributes:
        name: Exact branch name (e.g. ``"release/1.0"``).
        available: ``True`` when the branch exists remotely at discovery time
            (or was available at last successful discovery in the stale case).
            ``False`` for historically referenced branches that have since been
            deleted.
        stale: ``True`` when the entry originates from the stale-fallback path
            (local ``refs/remotes/origin/*``) rather than a live
            ``git ls-remote`` call.
    """

    name: str
    available: bool = True
    stale: bool = False


@dataclass
class CatalogResult:
    """Result of a single catalog resolution call.

    Attributes:
        project_id: The project this result belongs to.
        source_branch: The project's ``default_branch`` at resolution time.
        branches: Ordered list of :class:`ReleaseBranch` entries.
        refreshed_at: Unix timestamp (float) when discovery last succeeded.
        stale: ``True`` when **all** available entries originate from the
            stale-fallback path.
    """

    project_id: str
    source_branch: str
    branches: list[ReleaseBranch] = field(default_factory=list)
    refreshed_at: float = 0.0
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict for the API response.

        Returns:
            Dict with keys ``project_id``, ``source_branch``, ``branches``
            (list of ``{name, available, stale}``), and ``refreshed_at`` (ISO
            string or ``null``).
        """
        import datetime as _dt

        refreshed_iso: str | None = None
        if self.refreshed_at:
            refreshed_iso = _dt.datetime.fromtimestamp(
                self.refreshed_at, tz=_dt.timezone.utc
            ).isoformat()

        return {
            "project_id": self.project_id,
            "source_branch": self.source_branch,
            "branches": [
                {"name": b.name, "available": b.available, "stale": b.stale}
                for b in self.branches
            ],
            "refreshed_at": refreshed_iso,
            "stale": self.stale,
        }


# ---------------------------------------------------------------------------
# Natural sort key for branch names
# ---------------------------------------------------------------------------

_DIGIT_RE = re.compile(r"(\d+)")


def _natural_sort_key(name: str) -> tuple:
    """Return a sort key that orders numeric segments naturally.

    ``release/1.11`` sorts before ``release/1.9`` (numerically), while
    non-version names sort lexically after version-prefixed ones.

    Returns:
        Tuple of alternating strings and ints suitable for comparison.
    """
    parts = _DIGIT_RE.split(name)
    return tuple(int(p) if p.isdigit() else p for p in parts)


def _reverse_natural_sort_key(name: str) -> tuple:
    """Return a sort key for *reverse* natural order (higher versions first).

    Numeric segments are negated for descending sort; strings are left
    unchanged (ascending lexical order for non-numeric segments as a
    tie-breaker).
    """
    parts = _DIGIT_RE.split(name)
    return tuple(-int(p) if p.isdigit() else p for p in parts)


# ---------------------------------------------------------------------------
# Git discovery helpers
# ---------------------------------------------------------------------------


def _run_ls_remote(repo_path: str, timeout: int = 30) -> set[str]:
    """Run ``git ls-remote --heads origin`` and return the set of branch names.

    Args:
        repo_path: Absolute path to the local git clone.
        timeout: Subprocess timeout in seconds.

    Returns:
        Set of branch names discovered on the remote (e.g.
        ``{"main", "release/1.0", "release/1.1"}``).

    Raises:
        RuntimeError: When the ``git ls-remote`` command fails or times out.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git ls-remote --heads origin timed out after {timeout}s in {repo_path}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Failed to run git ls-remote in {repo_path}: {exc}"
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"git ls-remote --heads origin failed (rc={result.returncode}) "
            f"in {repo_path}: {stderr}"
        )

    branches: set[str] = set()
    prefix = "refs/heads/"
    for line in result.stdout.splitlines():
        parts = line.strip().split("\t", 1)
        if len(parts) == 2:
            ref = parts[1].strip()
            if ref.startswith(prefix):
                branches.add(ref[len(prefix):])
    return branches


def _run_local_remote_refs(repo_path: str, timeout: int = 10) -> set[str]:
    """Return branch names from local ``refs/remotes/origin/`` as a stale fallback.

    Uses ``git for-each-ref --format=%(refname:short) refs/remotes/origin/``
    to list cached remote-tracking refs without a network call.

    Args:
        repo_path: Absolute path to the local git clone.
        timeout: Subprocess timeout in seconds.

    Returns:
        Set of branch names (with ``origin/`` prefix stripped).  Returns an
        empty set on any error — the caller must handle the empty-set case.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/remotes/origin/",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return set()

    if result.returncode != 0:
        return set()

    branches: set[str] = set()
    for line in result.stdout.splitlines():
        name = line.strip()
        # Strip the "origin/" prefix from short refs like "origin/release/1.0"
        if name.startswith("origin/"):
            branches.add(name[len("origin/"):])
        # "HEAD" pseudo-ref — skip
    branches.discard("HEAD")
    return branches


# ---------------------------------------------------------------------------
# Per-project cache entry
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    """Cached result of a single successful remote discovery.

    Attributes:
        remote_branches: Set of branch names found on the remote at
            ``fetched_at``.
        fetched_at: ``time.monotonic()`` timestamp of the successful fetch.
    """

    remote_branches: set[str]
    fetched_at: float


# ---------------------------------------------------------------------------
# ReleaseBranchCatalog
# ---------------------------------------------------------------------------


class ReleaseBranchCatalog:
    """Resolve and cache the current set of remotely-available release branches.

    One instance per application lifetime (the module singleton
    :data:`_default_catalog`).  Call :meth:`list_candidates` from any
    thread; use :meth:`invalidate` to force re-discovery on the next call.

    Args:
        ttl_seconds: How long a successful discovery is cached.  Defaults to
            :data:`CACHE_TTL_SECONDS` (60 s).
        ls_remote_timeout: Timeout in seconds for ``git ls-remote``.
    """

    def __init__(
        self,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        ls_remote_timeout: int = 30,
    ) -> None:
        self._ttl = ttl_seconds
        self._ls_remote_timeout = ls_remote_timeout
        # project_id → _CacheEntry
        self._cache: dict[str, _CacheEntry] = {}
        # project_id → threading.Lock (prevents duplicate concurrent ls-remote)
        self._locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def list_candidates(self, project: Any) -> CatalogResult:
        """Return the ordered, availability-annotated list of release branches.

        Args:
            project: A :class:`~oompah.models.Project` instance.  The
                following attributes are read: ``id``, ``repo_path``,
                ``default_branch``, ``supported_release_branches``.

        Returns:
            A :class:`CatalogResult` with the resolved branch list.

        Raises:
            :class:`CatalogDiscoveryError`: When remote discovery fails **and**
                there is no prior cached result to fall back on.
        """
        project_id: str = project.id
        repo_path: str = getattr(project, "repo_path", "") or ""
        default_branch: str = getattr(project, "default_branch", "main") or "main"
        configured: list[str] = list(getattr(project, "supported_release_branches", []) or [])

        lock = self._get_project_lock(project_id)
        with lock:
            return self._resolve(
                project_id=project_id,
                repo_path=repo_path,
                default_branch=default_branch,
                configured=configured,
                project=project,
            )

    def invalidate(self, project_id: str) -> None:
        """Drop the cached discovery result for *project_id*.

        The next call to :meth:`list_candidates` for this project will
        perform a fresh ``git ls-remote``.

        Args:
            project_id: The project identifier to invalidate.
        """
        with self._meta_lock:
            self._cache.pop(project_id, None)
        logger.debug("ReleaseBranchCatalog: invalidated cache for %s", project_id)

    def invalidate_all(self) -> None:
        """Drop all cached discovery results."""
        with self._meta_lock:
            self._cache.clear()
        logger.debug("ReleaseBranchCatalog: invalidated all caches")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_project_lock(self, project_id: str) -> threading.Lock:
        """Return (or create) the per-project serialisation lock."""
        with self._meta_lock:
            if project_id not in self._locks:
                self._locks[project_id] = threading.Lock()
            return self._locks[project_id]

    def _resolve(
        self,
        *,
        project_id: str,
        repo_path: str,
        default_branch: str,
        configured: list[str],
        project: Any,
    ) -> CatalogResult:
        """Core resolution logic (called while holding the per-project lock).

        Attempts a fresh ``git ls-remote``.  On failure, falls back to the
        local remote-tracking refs or the prior cache entry.  Raises
        :class:`CatalogDiscoveryError` only when there is nothing to fall
        back on.
        """
        now = time.monotonic()
        cached = self._cache.get(project_id)
        cache_valid = cached is not None and (now - cached.fetched_at) < self._ttl

        # ----- Attempt remote discovery -----
        remote_branches: set[str] | None = None
        discovery_error: str | None = None

        if not cache_valid:
            if repo_path:
                try:
                    remote_branches = _run_ls_remote(
                        repo_path, timeout=self._ls_remote_timeout
                    )
                    # Cache the successful result
                    self._cache[project_id] = _CacheEntry(
                        remote_branches=remote_branches,
                        fetched_at=now,
                    )
                    cached = self._cache[project_id]
                    cache_valid = True
                    logger.debug(
                        "ReleaseBranchCatalog: discovered %d remote branches for %s",
                        len(remote_branches),
                        project_id,
                    )
                except RuntimeError as exc:
                    discovery_error = str(exc)
                    logger.warning(
                        "ReleaseBranchCatalog: remote discovery failed for %s: %s",
                        project_id,
                        exc,
                    )
            else:
                discovery_error = f"No repo_path configured for project {project_id!r}"
                logger.warning("ReleaseBranchCatalog: %s", discovery_error)

        # ----- Determine effective branch set and staleness -----
        stale = False
        refreshed_at: float = 0.0

        if cache_valid and cached is not None:
            # Fresh cache hit — not stale
            effective_branches = cached.remote_branches
            refreshed_at = cached.fetched_at
        elif discovery_error and repo_path:
            # Remote failed; try local refs/remotes/origin/* as stale fallback
            local_branches = _run_local_remote_refs(repo_path)
            if local_branches:
                effective_branches = local_branches
                stale = True
                # Keep prior refreshed_at from any older cache entry
                refreshed_at = cached.fetched_at if cached else 0.0
                logger.debug(
                    "ReleaseBranchCatalog: using stale local fallback (%d branches) for %s",
                    len(local_branches),
                    project_id,
                )
            elif cached is not None:
                # Use the expired cache entry as last resort
                effective_branches = cached.remote_branches
                stale = True
                refreshed_at = cached.fetched_at
                logger.debug(
                    "ReleaseBranchCatalog: using expired cache as fallback for %s",
                    project_id,
                )
            else:
                # Nothing to fall back on — first load failure
                raise CatalogDiscoveryError(
                    f"Branch discovery failed for project {project_id!r} "
                    f"and no prior result is available: {discovery_error}"
                )
        else:
            # No repo_path, no cache
            raise CatalogDiscoveryError(
                f"Branch discovery failed for project {project_id!r}: "
                f"{discovery_error or 'unknown error'}"
            )

        # ----- Collect historic branches from addendums -----
        historic_branches = self._collect_historic_branches(project)

        # ----- Build the ordered branch list -----
        branches = self._build_branch_list(
            configured=configured,
            effective_branches=effective_branches,
            historic_branches=historic_branches,
            stale=stale,
        )

        return CatalogResult(
            project_id=project_id,
            source_branch=default_branch,
            branches=branches,
            refreshed_at=refreshed_at,
            stale=stale,
        )

    def _collect_historic_branches(self, project: Any) -> set[str]:
        """Return the set of target branches referenced by any addendum on the project.

        This is a best-effort read.  We scan the project's tracker for all
        tasks that carry ``oompah.release_addendums`` metadata and collect
        their ``target_branch`` values.  Failures are swallowed to avoid
        blocking the catalog response.

        Args:
            project: A :class:`~oompah.models.Project` instance.

        Returns:
            Set of branch names that have ever appeared in a release addendum
            for this project.  May be empty when the feature has not been used
            or the tracker cannot be queried.
        """
        try:
            # Import late to avoid circular imports at module load
            from oompah import server as _server_module  # noqa: PLC0415

            orch = _server_module._get_orchestrator()
            tracker = orch._tracker_for_project(project.id)
            issues = tracker.list_issues() or []
        except Exception:
            return set()

        branches: set[str] = set()
        for issue in issues:
            identifier = getattr(issue, "identifier", None) or getattr(issue, "id", None)
            if not identifier:
                continue
            try:
                meta = tracker.get_metadata(identifier)
                raw_addendums = (meta or {}).get("oompah.release_addendums")
                if not raw_addendums:
                    continue
                if isinstance(raw_addendums, dict):
                    raw_addendums = [raw_addendums]
                if not isinstance(raw_addendums, list):
                    continue
                for entry in raw_addendums:
                    if isinstance(entry, dict):
                        tb = entry.get("target_branch")
                        if tb:
                            branches.add(str(tb).strip())
            except Exception:  # pragma: no cover
                continue

        return branches

    def _build_branch_list(
        self,
        *,
        configured: list[str],
        effective_branches: set[str],
        historic_branches: set[str],
        stale: bool,
    ) -> list[ReleaseBranch]:
        """Build the final ordered list of :class:`ReleaseBranch` entries.

        Ordering rules (section 5, item 4):
        1. Configured branches appear first, in their configured order.
        2. Historic-only branches (found in addendums but not in configured)
           are appended, sorted in reverse-natural order (higher versions
           first), then lexically for non-version names.

        Availability rules:
        - Available: branch is in *configured* AND in *effective_branches*.
        - Historic-unavailable: branch appeared in a past addendum but is
          neither currently available remotely nor in the current configured
          list.

        Args:
            configured: Ordered ``supported_release_branches`` from the project.
            effective_branches: Set of branch names currently visible on the
                remote (or stale local fallback).
            historic_branches: Set of branch names seen in past addendums.
            stale: Whether *effective_branches* came from the stale-fallback
                path.

        Returns:
            Ordered list of :class:`ReleaseBranch` entries.
        """
        seen: set[str] = set()
        result: list[ReleaseBranch] = []

        # 1. Configured branches in configured order
        for name in configured:
            if name in seen:
                continue
            seen.add(name)
            is_available = name in effective_branches
            result.append(ReleaseBranch(name=name, available=is_available, stale=stale and is_available))

        # 2. Historic-only branches (in addendums but not configured)
        extra: list[str] = sorted(
            {b for b in historic_branches if b not in seen},
            key=_reverse_natural_sort_key,
        )
        for name in extra:
            seen.add(name)
            # Historic branches not in configured list are never newly-selectable
            # regardless of remote presence (spec §5 item 5: "cannot be newly selected")
            is_available = False
            result.append(ReleaseBranch(name=name, available=is_available, stale=False))

        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: The default catalog instance used by the HTTP handler in server.py.
_default_catalog = ReleaseBranchCatalog()


def get_default_catalog() -> ReleaseBranchCatalog:
    """Return the module-level :class:`ReleaseBranchCatalog` singleton.

    Returns:
        The shared :data:`_default_catalog` instance.
    """
    return _default_catalog
