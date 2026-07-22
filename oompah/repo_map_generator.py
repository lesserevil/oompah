"""Repository-map generation and state-branch persistence orchestrator.

This module is the integration layer that connects:

- Tree-sitter symbol extraction (:mod:`oompah.repo_indexer`)
- Aider-style ranking (:mod:`oompah.repo_map_ranker`)
- State-branch lifecycle (:mod:`oompah.repo_map`)

See ``plans/repo-map-artifact.md`` for the artifact schema and lifecycle
rules.  See ``plans/state-branch-design.md`` for the state-branch invariants
this module enforces.

Public API
----------

``RepoMapResult``
    Dataclass describing the outcome of a map retrieval or generation request.

``RepoMapGenerator``
    Orchestrator class.  Instantiate once per managed project and call
    :meth:`~RepoMapGenerator.get_or_generate` to obtain a fresh repository
    map.

``STATUS_FRESH``
    Returned when an existing map was reused for the exact target commit SHA.

``STATUS_GENERATED``
    Returned when a new map was generated and written to the state branch.

``STATUS_FAILED``
    Returned when generation raised an unexpected exception.

``STATUS_TIMEOUT``
    Returned when generation did not complete within *timeout_s*.

``DEFAULT_TIMEOUT_S``
    Default generation timeout (120 seconds).

``DEFAULT_MAX_WORKERS``
    Default number of background generation workers (2).

Design invariants
-----------------

* Maps are written only to the state-branch checkout directory.  The generator
  never touches the managed project's main or release branches.
* Duplicate requests for the same commit SHA coalesce: a concurrent call
  blocks on the same background :class:`~concurrent.futures.Future` instead
  of starting a parallel indexing run.
* :func:`~oompah.repo_map.write_repo_map` uses ``os.replace()`` so readers
  either see a complete JSON document or no file — never a partial write.
* A failed or timed-out generation returns a diagnostic
  :class:`RepoMapResult`; it never propagates an exception to the caller.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from pathlib import Path

from oompah.repo_indexer import index_repository
from oompah.repo_map import (
    REPO_MAP_MAX_RETAINED,
    RepoMap,
    prune_repo_maps,
    read_repo_map,
    write_repo_map,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_FRESH = "fresh"
"""Map was reused from the state branch; the exact commit SHA was already indexed."""

STATUS_GENERATED = "generated"
"""A new map was generated and written to the state branch."""

STATUS_FAILED = "failed"
"""Generation failed with an unexpected exception."""

STATUS_TIMEOUT = "timeout"
"""Generation did not complete within :data:`DEFAULT_TIMEOUT_S` seconds."""

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_S: float = 120.0
"""Default maximum wall-clock time (seconds) for one generation run."""

DEFAULT_MAX_WORKERS: int = 2
"""Default number of concurrent background generation workers."""

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class RepoMapResult:
    """Outcome of a repository-map retrieval or generation request.

    Callers must check :attr:`status` before using :attr:`repo_map`.

    Attributes
    ----------
    status:
        One of :data:`STATUS_FRESH`, :data:`STATUS_GENERATED`,
        :data:`STATUS_FAILED`, :data:`STATUS_TIMEOUT`.
    repo_map:
        The retrieved or generated map, or ``None`` on failure.
    reused:
        ``True`` when an existing artifact was returned without re-running
        the indexer (i.e. ``status == STATUS_FRESH``).
    error:
        Human-readable description of the failure, populated when ``status``
        is :data:`STATUS_FAILED` or :data:`STATUS_TIMEOUT`.
    generation_duration_s:
        Wall-clock time in seconds spent waiting for the generation result.
        ``None`` for :data:`STATUS_FRESH` (cache hit, no generation occurred).
        Populated for :data:`STATUS_GENERATED`, :data:`STATUS_FAILED`, and
        :data:`STATUS_TIMEOUT`.
    file_count:
        Number of files indexed, from ``rendering_metadata.total_files``.
        ``None`` when ``repo_map`` is ``None``.
    symbol_count:
        Number of symbol tags extracted, from ``rendering_metadata.total_symbols``.
        ``None`` when ``repo_map`` is ``None``.
    """

    status: str
    repo_map: RepoMap | None = None
    reused: bool = False
    error: str | None = None
    generation_duration_s: float | None = None
    file_count: int | None = None
    symbol_count: int | None = None


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class RepoMapGenerator:
    """Orchestrator for repo-map generation and state-branch persistence.

    Instantiate one generator per managed project repository.  The generator
    is thread-safe: concurrent calls to :meth:`get_or_generate` with the
    same commit SHA block on a shared :class:`~concurrent.futures.Future`
    and receive the single generated artifact.

    Parameters
    ----------
    state_branch_dir:
        Root of the state-branch checkout (git worktree).  Map files are
        written under ``state_branch_dir/.oompah/repo-maps/``.  Must be a
        git-tracked directory so that ``git add`` / ``git commit`` succeed.
    repo_identity:
        Canonical URL or opaque identifier for the managed repository (same
        string used in :class:`~oompah.repo_map.RepoMap`).
    timeout_s:
        Maximum wall-clock time (seconds) to wait for one generation run
        before returning a :data:`STATUS_TIMEOUT` result.
    max_retained:
        Maximum number of maps to keep per repository slug.  Older maps are
        pruned after each successful write.
    max_workers:
        Background thread pool size.
    generator_version:
        Semantic version string embedded in every generated artifact.
    """

    def __init__(
        self,
        *,
        state_branch_dir: Path,
        repo_identity: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retained: int = REPO_MAP_MAX_RETAINED,
        max_workers: int = DEFAULT_MAX_WORKERS,
        generator_version: str = "1.0.0",
    ) -> None:
        self._state_dir = Path(state_branch_dir)
        self._repo_identity = repo_identity
        self._timeout_s = float(timeout_s)
        self._max_retained = int(max_retained)
        self._generator_version = generator_version

        # Coalescing map: commit_sha (normalised) → in-flight Future[RepoMap]
        self._in_flight: dict[str, Future[RepoMap]] = {}
        self._in_flight_lock = threading.Lock()

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="repo-map-gen",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_generate(
        self,
        repo_path: Path,
        commit_sha: str,
    ) -> RepoMapResult:
        """Return a fresh repository map, reusing or generating as needed.

        Algorithm
        ~~~~~~~~~

        1. Normalise *commit_sha* (lower-case, strip whitespace).
        2. Check the state-branch directory for an existing fresh map at
           *commit_sha*.  If found, return immediately
           (``status = STATUS_FRESH``).
        3. Check the coalescing table for an in-flight generation for this
           SHA.  If found, join that :class:`~concurrent.futures.Future`
           instead of starting a second indexing run.
        4. If not found, submit a new generation task to the thread pool.
        5. Wait for the Future result with a bounded *timeout_s*.
        6. On success, return the artifact (``status = STATUS_GENERATED``).
        7. On timeout, return ``status = STATUS_TIMEOUT`` without raising.
        8. On any other exception, return ``status = STATUS_FAILED``
           without raising.

        This method always returns without raising.  A failed or timed-out
        result means the artifact is unavailable for this request; callers
        must not block task dispatch on a non-:data:`STATUS_GENERATED` /
        non-:data:`STATUS_FRESH` result.

        Parameters
        ----------
        repo_path:
            Root directory of the managed project checkout to index.  Must
            be an existing directory.
        commit_sha:
            40-character hexadecimal HEAD SHA of the checkout.
        """
        sha = commit_sha.lower().strip()

        # Fast path: check for a pre-existing fresh map on the state branch.
        try:
            existing = read_repo_map(self._state_dir, self._repo_identity, sha)
        except Exception:  # noqa: BLE001
            existing = None

        if existing is not None:
            logger.debug(
                "repo-map cache hit for %s @ %.8s",
                self._repo_identity,
                sha,
            )
            return RepoMapResult(
                status=STATUS_FRESH,
                repo_map=existing,
                reused=True,
                file_count=existing.rendering_metadata.total_files,
                symbol_count=existing.rendering_metadata.total_symbols,
            )

        # Coalesce: get or create the in-flight Future for this SHA.
        with self._in_flight_lock:
            if sha not in self._in_flight:
                future: Future[RepoMap] = self._executor.submit(
                    self._generate_task, Path(repo_path), sha
                )
                self._in_flight[sha] = future
            else:
                future = self._in_flight[sha]

        # Wait for the result, bounded by timeout.
        _wait_start = time.monotonic()
        try:
            repo_map = future.result(timeout=self._timeout_s)
        except FutureTimeoutError:
            elapsed = time.monotonic() - _wait_start
            logger.warning(
                "repo-map generation timed out after %.1fs for %s @ %.8s",
                self._timeout_s,
                self._repo_identity,
                sha,
            )
            return RepoMapResult(
                status=STATUS_TIMEOUT,
                error=f"Generation timed out after {self._timeout_s:.0f}s",
                generation_duration_s=elapsed,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - _wait_start
            logger.error(
                "repo-map generation failed for %s @ %.8s: %s",
                self._repo_identity,
                sha,
                exc,
            )
            return RepoMapResult(
                status=STATUS_FAILED,
                error=str(exc),
                generation_duration_s=elapsed,
            )
        finally:
            # Remove from the coalescing table so the next caller re-checks
            # the state branch (which will find the new artifact on success,
            # or re-attempt generation on failure).
            with self._in_flight_lock:
                self._in_flight.pop(sha, None)

        elapsed = time.monotonic() - _wait_start
        return RepoMapResult(
            status=STATUS_GENERATED,
            repo_map=repo_map,
            generation_duration_s=elapsed,
            file_count=repo_map.rendering_metadata.total_files,
            symbol_count=repo_map.rendering_metadata.total_symbols,
        )

    def is_generating(self, commit_sha: str) -> bool:
        """Return ``True`` if a generation task for *commit_sha* is in flight.

        Thread-safe.  Returns ``False`` if the SHA is not normalised or if
        no generation for this SHA is currently running.

        This is used by the diagnostics layer to report the ``generating``
        state for a pending index run.

        Parameters
        ----------
        commit_sha:
            Commit SHA to check.  Case-insensitive; leading/trailing
            whitespace is stripped.
        """
        sha = commit_sha.lower().strip()
        with self._in_flight_lock:
            return sha in self._in_flight

    def shutdown(self, *, wait: bool = True) -> None:
        """Shut down the background thread pool.

        Parameters
        ----------
        wait:
            When ``True`` (default), block until all submitted tasks
            complete before returning.
        """
        self._executor.shutdown(wait=wait)

    def __enter__(self) -> "RepoMapGenerator":
        return self

    def __exit__(self, *_: object) -> None:
        self.shutdown()

    # ------------------------------------------------------------------
    # Internal helpers (background thread)
    # ------------------------------------------------------------------

    def _generate_task(self, repo_path: Path, commit_sha: str) -> RepoMap:
        """Index the repository, write the artifact, and commit to state branch.

        Runs inside a background thread pool worker.  Raises on any failure
        so that :meth:`get_or_generate` can translate the exception to a
        diagnostic :class:`RepoMapResult`.

        Steps
        ~~~~~

        1. Call :func:`~oompah.repo_indexer.index_repository` to extract
           symbols, edges, and file metadata.
        2. Atomically write the artifact via
           :func:`~oompah.repo_map.write_repo_map`.
        3. Commit the new file to the state-branch git repository.
        4. Prune old maps via :func:`~oompah.repo_map.prune_repo_maps`.
        5. Return the generated :class:`~oompah.repo_map.RepoMap`.
        """
        logger.debug(
            "starting repo-map generation for %s @ %.8s",
            self._repo_identity,
            commit_sha,
        )

        # Step 1: index the repository via Tree-sitter.
        repo_map = index_repository(
            repo_path=repo_path,
            repo_identity=self._repo_identity,
            commit_sha=commit_sha,
            generator_version=self._generator_version,
        )

        # Step 2: atomically write the artifact to the state-branch directory.
        written_path = write_repo_map(self._state_dir, repo_map)
        logger.debug("wrote repo-map artifact to %s", written_path)

        # Step 3: prune old maps from the filesystem BEFORE committing so
        # that the removal and the addition land in a single atomic commit.
        pruned = prune_repo_maps(
            self._state_dir, self._repo_identity, self._max_retained
        )
        if pruned:
            logger.debug("pruned %d old repo-map file(s)", len(pruned))

        # Step 4: commit the new file (and any pruned removals) to the state
        # branch, then push to origin so the artifact is visible to other
        # workers and persisted beyond the local checkout.
        self._commit_map_to_state_branch(written_path, commit_sha, pruned=pruned)
        self._push_state_branch()

        return repo_map

    def _commit_map_to_state_branch(
        self,
        written_path: Path,
        commit_sha: str,
        *,
        pruned: "list[Path] | None" = None,
    ) -> None:
        """Stage and commit *written_path* (and pruned removals) to the state branch.

        Idempotent: no-ops if the staged area has no changes after staging.

        This method intentionally targets only the specific map file (and
        the explicitly provided pruned paths) rather than using ``git add -A``,
        ensuring that source code files in the managed project's working tree
        are never accidentally staged.

        Parameters
        ----------
        written_path:
            Absolute path to the written JSON file inside the state-branch
            checkout directory.
        commit_sha:
            The indexed commit SHA (used in the commit subject line).
        pruned:
            Paths removed by :func:`~oompah.repo_map.prune_repo_maps` that
            must also be staged for deletion in the same commit.  Paths
            outside the state-branch directory are silently skipped.
        """
        rel = str(written_path.relative_to(self._state_dir))

        # Stage only the specific map file — never stage source code.
        self._git_run(["add", rel])

        # Stage removals of pruned files so they land in the same commit.
        for p in (pruned or []):
            try:
                rel_pruned = str(p.relative_to(self._state_dir))
            except ValueError:
                continue  # Path outside state_dir — skip safely.
            # ``--cached`` removes from the index (stages deletion); the file
            # is already gone from the working tree after prune_repo_maps.
            # ``--ignore-unmatch`` prevents errors when the file was never
            # tracked (e.g. the first commit of a slug directory).
            self._git_run(
                ["rm", "--cached", "--ignore-unmatch", rel_pruned],
                check=False,
            )

        # Short-circuit when the staged area has no changes (already committed).
        diff = self._git_run(["diff", "--cached", "--quiet"], check=False)
        if diff.returncode == 0:
            return  # Nothing new to commit.

        short_sha = commit_sha[:8]
        message = (
            f"repo-map: index {self._repo_identity} @ {short_sha}\n\n"
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
        )
        self._git_run(["commit", "-m", message])

        logger.debug(
            "committed repo-map for %s @ %.8s to state branch",
            self._repo_identity,
            commit_sha,
        )

    def _push_state_branch(self) -> None:
        """Push the current state-branch HEAD to ``origin``.

        Makes the artifact visible to other workers and persisted beyond the
        local checkout.  The state branch was cloned with tracking set up,
        so a bare ``git push origin HEAD`` is sufficient.
        """
        self._git_run(["push", "origin", "HEAD"])

    def _git_run(
        self,
        args: list[str],
        *,
        check: bool = True,
    ) -> "subprocess.CompletedProcess[str]":
        """Run a git command inside the state-branch worktree.

        Parameters
        ----------
        args:
            Git sub-command and arguments (without the leading ``git``).
        check:
            When ``True`` (default), raise :class:`RuntimeError` on non-zero
            exit codes.
        """
        result = subprocess.run(
            ["git", *args],
            cwd=str(self._state_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)!r} failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout.strip()}\n"
                f"stderr: {result.stderr.strip()}"
            )
        return result
