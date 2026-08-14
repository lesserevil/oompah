"""Native oompah Markdown task tracker.

Stores canonical task state under ``.oompah/tasks`` in the managed repository.
The running oompah service is the intended writer; humans can inspect the files
directly on the project's default branch.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from oompah.checkpoint_queue import CheckpointQueue
from oompah.git_credentials import (
    git_credential_environment,
    redact_git_output,
)
from oompah.integration import parse_integration_record
from oompah.models import BlockerRef, Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    OPEN,
    PROPOSED,
    canonicalize_status,
    is_terminal_status,
    status_key,
)
from oompah.tracker import (
    BatchIdempotencyConflictError,
    BatchPreconditionError,
    CreateOnceConflictError,
    StateBranchFetchError,
    StateBranchMissingError,
    TrackerError,
    _parse_timestamp,
    _sanitize_identifier,
    _sort_issues_for_dispatch,
    _string_list,
    append_tracker_comment,
    comment_author_field,
    format_comment_timestamp,
    normalize_priority_int,
    parse_tracker_comments,
    validate_needs_human_comment,
)

logger = logging.getLogger(__name__)

TRACKER_KIND = "oompah_md"
_READ_CONTROL_PLANE_YIELD_INTERVAL = 32

# ---------------------------------------------------------------------------
# Module-level write-lock registry (OOMPAH-267 / OOMPAH-268)
#
# All OompahMarkdownTracker instances that point to the same git repository
# share one RLock, keyed by the resolved repo path.  A per-instance RLock
# only serializes threads within one instance; after a graceful reload
# (reload_config clears _project_trackers) a new tracker instance is created
# while an in-flight write still holds the old instance's lock.  Both
# instances would then run git commit concurrently, producing:
#
#   fatal: cannot lock ref 'HEAD': is at <old> but expected <new>
#
# Using a module-level dict keyed by repo path ensures that the old and new
# instances share the same RLock and therefore serialize through it.
# ---------------------------------------------------------------------------

_repo_write_locks: dict[str, threading.RLock] = {}
_repo_write_locks_guard = threading.Lock()
# Read caches are per tracker instance, but status changes can be made through
# another instance after a config reload.  Keep a lightweight per-repository
# generation alongside the shared lock so that such a write invalidates every
# instance's cache before the next read.
_repo_read_generations: dict[str, int] = {}
_repo_read_changes: dict[str, list[tuple[int, str | None, str | None]]] = {}
_repo_read_change_floors: dict[str, int] = {}
_REPO_READ_CHANGE_HISTORY_LIMIT = 4096


def _repo_write_lock(repo_path: str) -> threading.RLock:
    """Return the shared write lock for the given resolved repo path.

    All :class:`OompahMarkdownTracker` instances that point to the same git
    repository share the same :class:`~threading.RLock`, regardless of when
    each instance was created.  This prevents concurrent git commits across
    tracker instances that are created during a graceful reload.
    """
    with _repo_write_locks_guard:
        if repo_path not in _repo_write_locks:
            _repo_write_locks[repo_path] = threading.RLock()
        _repo_read_generations.setdefault(repo_path, 0)
        _repo_read_changes.setdefault(repo_path, [])
        return _repo_write_locks[repo_path]


def _repo_read_generation(repo_path: str) -> int:
    """Return the current read-cache generation for *repo_path*."""
    with _repo_write_locks_guard:
        return _repo_read_generations.setdefault(repo_path, 0)


def _advance_repo_read_generation(
    repo_path: str,
    *,
    task_id: str | None = None,
    authority_kind: str | None = None,
) -> int:
    """Invalidate read caches held by all tracker instances for *repo_path*."""
    with _repo_write_locks_guard:
        generation = _repo_read_generations.setdefault(repo_path, 0) + 1
        _repo_read_generations[repo_path] = generation
        changes = _repo_read_changes.setdefault(repo_path, [])
        changes.append(
            (
                generation,
                str(task_id or "").strip() or None,
                str(authority_kind or "").strip() or None,
            )
        )
        excess = len(changes) - _REPO_READ_CHANGE_HISTORY_LIMIT
        if excess > 0:
            _repo_read_change_floors[repo_path] = changes[excess - 1][0]
            del changes[:excess]
        return generation


TASKS_DIR = ".oompah/tasks"
DEFAULT_TASK_PREFIX = "TASK"
_IMPORT_INDEX_FILE = "external-imports.yml"
_YAML_SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

_STATUS_DIRS: dict[str, str] = {
    "proposed": "proposed",
    "backlog": "backlog",
    "open": "open",
    "in progress": "in-progress",
    "needs answer": "needs-answer",
    "needs human": "needs-human",
    "needs ci fix": "needs-ci-fix",
    "needs rebase": "needs-rebase",
    "in review": "in-review",
    "in validation": "in-validation",
    "decomposed": "decomposed",
    "duplicate candidate": "duplicate-candidate",
    "done": "done",
    "merged": "merged",
    "archived": "archived",
}
_ISSUE_TYPES = frozenset({"bug", "feature", "task", "epic", "chore"})
_SUMMARY_UNSAFE_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)

# Maximum number of push attempts in _commit_and_push and write_and_commit_ledger_file.
# Each failed push is followed by a _sync_from_remote + short backoff before the next
# attempt, so 3 total attempts means 2 sync+retry cycles.  Under concurrent writers
# this dramatically reduces the probability of all attempts failing (OOMPAH-265).
_PUSH_MAX_RETRIES = 3

# A module-level RLock serializes tracker instances inside one server process,
# but it cannot coordinate a brief old/new process overlap during a restart or
# a mixed-version writer that still accesses the same state worktree directly.
# Git's index and ref locks make those overlaps fail safely.  Wait briefly for
# the legitimate lock owner and retry the complete stage/commit transaction;
# never remove Git-owned lock files (OOMPAH-1071).
_STATE_BRANCH_GIT_LOCK_MAX_ATTEMPTS = 4
_STATE_BRANCH_GIT_LOCK_BACKOFF_SECONDS = 0.05


def _is_transient_state_branch_git_lock_error(output: str) -> bool:
    """Return whether Git reports short-lived index or ref contention.

    Deliberately recognize only Git's canonical lock-race diagnostics.  Other
    ``cannot lock ref`` failures, such as a permanent nested-ref namespace
    collision, remain immediately fatal instead of being pointlessly retried.
    """
    detail = str(output or "").lower()
    if "index.lock" in detail and "file exists" in detail:
        return True
    if "cannot lock ref" not in detail:
        return False
    return (
        (".lock" in detail and "file exists" in detail)
        or (" is at " in detail and " expected " in detail)
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _status_dir(status: str) -> str:
    key = status_key(canonicalize_status(status))
    return _STATUS_DIRS.get(key, key.replace(" ", "-") or "backlog")


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    return cleaned.strip(".-_") or "task"


def _section(body: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)"
    )
    match = pattern.search(body or "")
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _summary_safe_description(description: str | None) -> str:
    """Preserve structured Markdown inside a native task's Summary section.

    Descriptions are stored below ``## Summary``. H1/H2 headings supplied by
    callers would otherwise terminate that section, allowing a non-empty task
    body to parse as an empty description later. Demote only those headings;
    H3+ headings are already safe and the supplied structure remains visible.
    """
    content = (description or "").strip()
    return _SUMMARY_UNSAFE_HEADING_RE.sub(
        lambda match: f"### {match.group(2)}",
        content,
    )


def _replace_section(body: str, heading: str, text: str | None) -> str:
    new_text = (text or "").strip()
    section_text = f"## {heading}\n\n{new_text}\n"
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n?.*?(?=^##\s+|\Z)"
    )
    if pattern.search(body or ""):
        return pattern.sub(section_text, body).rstrip() + "\n"
    prefix = (body or "").rstrip()
    if prefix:
        return f"{prefix}\n\n{section_text}"
    return section_text


def _read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot read native task {path}: {exc}") from exc
    if not content.startswith("---\n"):
        raise TrackerError(f"Missing YAML front matter in native task {path}")
    end = content.find("\n---", 4)
    if end < 0:
        raise TrackerError(f"Unterminated YAML front matter in native task {path}")
    frontmatter = content[4:end]
    body_start = end + len("\n---")
    if content[body_start : body_start + 1] == "\n":
        body_start += 1
    try:
        meta = yaml.load(frontmatter, Loader=_YAML_SAFE_LOADER) or {}
    except yaml.YAMLError as exc:
        raise TrackerError(f"Cannot parse native task metadata {path}: {exc}") from exc
    if not isinstance(meta, dict):
        meta = {}
    return meta, content[body_start:]


def _is_missing_task_file_error(exc: TrackerError) -> bool:
    """Return whether ``exc`` wraps an ENOENT raised while opening a task."""
    return isinstance(exc.__cause__, FileNotFoundError)


def _atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* using a temporary file + atomic rename.

    The destination file is NEVER left empty or partially written.  If any
    error occurs before the full payload is durable, the original *path* is
    left intact (or absent if it did not exist before the call).

    Sequence:
    1. Create a temp file in the *same* directory as *path* (so both are on the
       same filesystem, guaranteeing that ``os.replace`` is an atomic rename).
    2. Write the full payload and fsync (best-effort — not all VMs expose it).
    3. Rename the temp file over *path* atomically.
    4. On any failure, delete the temp file and re-raise.

    Note: Uses ``.tmp`` suffix (not ``.md``) so that stale temp files left by
    a crash are never picked up by the ``*/*.md`` glob in :meth:`_read_records`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        fd, tmp_str = tempfile.mkstemp(
            dir=path.parent, prefix=".oompah_tmp_", suffix=".tmp"
        )
        tmp_path = Path(tmp_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass  # fsync is best-effort; not all filesystems support it
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            tmp_path = None
            raise
        tmp_path.replace(path)
        tmp_path = None
    except OSError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def _write_markdown(path: Path, meta: dict[str, Any], body: str) -> None:
    payload = yaml.safe_dump(dict(meta), sort_keys=False, allow_unicode=False)
    try:
        _atomic_write(path, f"---\n{payload}---\n{body}")
    except OSError as exc:
        raise TrackerError(f"Cannot write native task {path}: {exc}") from exc


class OompahMarkdownTracker:
    """Tracker adapter backed by native Markdown files under ``.oompah/tasks``.

    When ``state_branch_enabled=True``, all task reads and writes are routed
    through a dedicated git worktree checked out on ``state_branch_name``
    (e.g. ``oompah/state/<project-id>``).  The shared code checkout is never
    switched to the state branch; it remains on the default branch throughout.

    Legacy behavior (``state_branch_enabled=False``, the default) is unchanged:
    reads and writes use the default branch in the project's main checkout.
    """

    # The server uses this capability marker before calling the optional
    # generation-bound read methods below.  A marker avoids accidentally
    # treating permissive proxy objects (notably mocks) as implementations of
    # the extension interface.
    supports_generation_bound_reads = True
    supports_atomic_create_once = True
    supports_atomic_batch_updates = True
    supports_bounded_state_reads = True

    def __init__(
        self,
        *,
        active_states: list[str],
        terminal_states: list[str],
        cwd: str | None = None,
        default_branch: str | None = None,
        git_sync: bool = True,
        state_branch_enabled: bool = False,
        state_branch_name: str | None = None,
        state_branch_checkpoint_debounce_ms: int = 5000,
        state_branch_checkpoint_max_delay_ms: int = 30000,
        state_branch_push_retry_count: int = 3,
        state_branch_push_retry_backoff_ms: int = 1000,
        state_branch_shadow_write: bool = False,
        allow_default_branch_task_writes: bool = True,
        access_token: str | None = None,
        forge_kind: str = "github",
        canonical_remote_url: str | None = None,
        _checkpoint_timer_factory: Any = None,
        _on_checkpoint_flushed: Any = None,
    ) -> None:
        self.active_states = [canonicalize_status(s) for s in active_states]
        self.terminal_states = [canonicalize_status(s) for s in terminal_states]
        self.cwd = cwd
        self._root = Path(cwd or os.getcwd()).resolve()
        self.default_branch = (default_branch or "").strip() or None
        self.git_sync = bool(git_sync)
        self.state_branch_enabled = bool(state_branch_enabled)
        self.state_branch_name = (state_branch_name or "").strip() or None
        self.state_branch_shadow_write = bool(state_branch_shadow_write)
        self.allow_default_branch_task_writes = bool(
            allow_default_branch_task_writes
        )
        # Forge credentials for authenticated Git network operations.
        # Token is never stored in git config or URLs; only in ephemeral subprocess env.
        self._access_token = str(access_token or "")
        self._forge_kind = str(forge_kind or "github").strip().lower() or "github"
        # Managed state-branch operations must resolve the server-owned remote
        # from project configuration, not from a clone's possibly stale origin.
        # The URL is injected as command-scoped Git configuration and is never
        # written back to the repository.
        self._canonical_remote_url = str(canonical_remote_url or "").strip() or None
        if self._canonical_remote_url:
            try:
                parsed_remote = urlsplit(self._canonical_remote_url)
            except ValueError as exc:
                raise TrackerError(
                    "Managed canonical remote URL is malformed"
                ) from exc
            if parsed_remote.scheme.lower() in {"http", "https"}:
                if parsed_remote.password is not None:
                    raise TrackerError(
                        "Managed canonical remote URL must not contain credentials"
                    )
                if parsed_remote.username is not None:
                    # Legacy project registrations may include a non-secret
                    # clone username (for example ``https://actor@github``).
                    # The managed token remains askpass-only; remove that
                    # user-info before placing the canonical URL in argv.
                    self._canonical_remote_url = parsed_remote._replace(
                        netloc=parsed_remote.netloc.rsplit("@", 1)[-1]
                    ).geturl()
        # Optional callback invoked after each successful state-branch checkpoint
        # flush. Used by server.py to invalidate the issues snapshot cache so
        # clients receive fresh data without waiting for the 60-second TTL.
        self._on_checkpoint_flushed = _on_checkpoint_flushed
        self._push_retry_count = max(1, int(state_branch_push_retry_count))
        self._push_retry_backoff_ms = max(0, int(state_branch_push_retry_backoff_ms))
        if self.state_branch_enabled and not self.state_branch_name:
            raise TrackerError(
                "state_branch_enabled=True requires state_branch_name to be set"
            )
        # Lazily-initialised path to the state-branch git worktree.
        # Protected by _state_worktree_lock so concurrent reads don't race
        # on first-time worktree creation.
        self._state_root: Path | None = None
        self._state_worktree_lock = threading.Lock()
        # One managed service owns state-branch writes for a project.  Sync the
        # worktree once when this tracker generation first mutates it, then let
        # the checkpoint queue coalesce local writes without repeating a
        # network fetch under the repository write lock.  Push rejection still
        # fetches/rebases in _commit_and_push_state_branch, preserving recovery
        # if another process advanced the remote during a restart overlap.
        self._state_branch_write_synced = False
        # Shared per-repo lock — all tracker instances for the same git repo
        # serialize through this lock, even across graceful reloads where
        # reload_config() clears the tracker cache and creates a new instance
        # while an in-flight write still holds the old instance's lock.
        self._repo_lock_key = str(self._root)
        self._write_lock = _repo_write_lock(self._repo_lock_key)
        self._read_cache: list[dict[str, Any]] | None = None
        self._read_cache_by_id: dict[str, dict[str, Any]] | None = None
        self._read_cache_status_by_id: dict[str, str] | None = None
        self._read_cache_generation: int | None = None
        self._corrupt_stubs: list[dict[str, Any]] | None = None
        self._read_cache_guard = threading.Lock()
        # Consumers such as the HTTP server can subscribe to authoritative
        # task-read changes.  This is deliberately a small callback surface
        # rather than a server import: tracker instances are also used by the
        # task CLI and by background workers.
        self._read_change_callbacks: list[Any] = []
        # A project tracker cache generation can outlive its configuration
        # authority because callers may retain the old object.  Cutover sets
        # this event before publishing the new configuration; every mutation
        # checks it under the shared repository write lock.
        self._writer_retired = threading.Event()
        # Monotonic timestamp of the last successful state-branch checkpoint
        # flush.  Updated by _do_checkpoint_flush so callers (e.g. server.py
        # issues-snapshot logic) can detect when a checkpoint has advanced past
        # the last snapshot refresh and force-refresh their own caches.
        self.last_checkpoint_at: float = 0.0

        # Checkpoint coalescing queue (state_branch_enabled=True only).
        # When enabled, mutations are buffered and flushed as one atomic commit
        # after the debounce window, reducing Git commit volume (design § 5).
        self._checkpoint_queue: CheckpointQueue | None = None
        if self.state_branch_enabled:
            kwargs: dict[str, Any] = {}
            if _checkpoint_timer_factory is not None:
                kwargs["_timer_factory"] = _checkpoint_timer_factory
            self._checkpoint_queue = CheckpointQueue(
                debounce_ms=int(state_branch_checkpoint_debounce_ms),
                max_delay_ms=int(state_branch_checkpoint_max_delay_ms),
                flush_fn=self._do_checkpoint_flush,
                incident_key=f"state_branch:{self.state_branch_name}",
                **kwargs,
            )

    # ------------------------------------------------------------------
    # Checkpoint coalescing — public interface (design § 5.3, § 5.7)
    # ------------------------------------------------------------------

    def flush_checkpoint(self, *, reason: str) -> int:
        """Flush all pending state-branch mutations immediately.

        Called for mandatory-flush events (design § 5.3): terminal task status
        transitions, human-initiated API mutations, service SIGTERM, agent
        session exit, and ``release_addendum`` state changes.

        When ``state_branch_enabled=False`` (legacy mode), this is a no-op.

        Parameters
        ----------
        reason:
            Short label identifying why the flush was triggered.  Used in log
            output and the commit message subject.

        Returns
        -------
        int
            Number of mutations that were flushed.  Zero when there was nothing
            pending or when state-branch mode is disabled.
        """
        if self._checkpoint_queue is None:
            return 0
        return self._checkpoint_queue.flush(reason=reason)

    def shutdown_checkpoint(self) -> None:
        """Flush any pending mutations and release timer threads (graceful shutdown).

        Must be called on service ``SIGTERM`` / ``shutdown`` lifecycle events.
        Safe to call even when ``state_branch_enabled=False``.
        """
        if self._checkpoint_queue is not None:
            self._checkpoint_queue.shutdown()

    def retire_checkpoint_writer(self, *, reason: str) -> int:
        """Permanently fence this tracker before a configuration cutover.

        No pending task state is discarded.  Timer publication is cancelled,
        an in-flight flush is allowed to finish under the old authority, and a
        shared repository-lock barrier waits for already-started mutations.
        The successor tracker then adopts the dirty worktree/local head using
        the new forge credentials.
        """

        del reason  # Reserved for structured cutover diagnostics.
        self._writer_retired.set()
        transferred = (
            self._checkpoint_queue.retire()
            if self._checkpoint_queue is not None
            else 0
        )
        # Every mutation holds this shared lock from its authority check until
        # its file write and queue schedule complete.  Acquiring it here proves
        # no old-generation mutation remains in flight when this method returns.
        with self._write_lock:
            pass
        return transferred

    def adopt_checkpoint_state(self, *, reason: str) -> int:
        """Publish preserved state through this tracker's current authority.

        A synthetic queue item is intentional: a predecessor may already have
        committed locally before its push failed, leaving no dirty file for
        ``git commit`` to discover.  The state-branch flush therefore also
        publishes an unchanged local head.
        """

        self._assert_writer_active()
        if self._checkpoint_queue is None:
            return 0
        self._checkpoint_queue.schedule()
        return self._checkpoint_queue.flush(reason=reason)

    @property
    def checkpoint_pending_mutations(self) -> int:
        """Number of mutations waiting in the checkpoint buffer.

        Returns 0 when ``state_branch_enabled=False``.
        """
        if self._checkpoint_queue is None:
            return 0
        return self._checkpoint_queue.pending_mutations

    @property
    def checkpoint_last_push_at(self) -> str | None:
        """ISO-8601 timestamp of the last successful checkpoint push, or None."""
        if self._checkpoint_queue is None:
            return None
        return self._checkpoint_queue.last_push_at

    @property
    def checkpoint_push_failures(self) -> int:
        """Count of checkpoint flush/push failures since startup."""
        if self._checkpoint_queue is None:
            return 0
        return self._checkpoint_queue.push_failures

    def get_checkpoint_observability(self) -> dict[str, Any] | None:
        """Return the ``state_branch`` observability dict for GET /api/v1/state.

        Returns ``None`` when ``state_branch_enabled=False`` (field should be
        omitted from the state response for legacy projects).

        Example output (design § 5.7)::

            {
                "branch": "oompah/state/proj-14849f1b",
                "last_push_at": "2026-07-20T16:00:00Z",
                "pending_mutations": 0,
                "push_failures": 0,
                "alert": null,
            }

        When ``last_push_at`` is ``None`` (i.e. the checkpoint queue has not
        flushed since startup — common immediately after bootstrap), the method
        falls back to querying ``git log`` for the latest commit timestamp on
        the state branch so the API reports an accurate last-checkpoint time
        rather than ``null`` (OOMPAH-283).
        """
        if self._checkpoint_queue is None or not self.state_branch_name:
            return None
        obs = self._checkpoint_queue.get_observability_dict(
            branch=self.state_branch_name
        )
        # Fallback: when no flush has occurred yet (e.g. right after bootstrap),
        # read the timestamp of the latest git commit on the state branch so the
        # API does not report "Last push: never" for a branch that was pushed.
        if obs.get("last_push_at") is None:
            obs = dict(obs)  # shallow copy — avoid mutating the queue's data
            obs["last_push_at"] = self._get_state_branch_last_commit_at()
        return obs

    def _get_state_branch_last_commit_at(self) -> str | None:
        """Return the ISO-8601 author timestamp of the latest state-branch commit.

        Queries ``git log`` on the local clone (``self._root``).  Returns
        ``None`` when the branch has no commits or the git command fails.
        """
        branch = self.state_branch_name
        if not branch:
            return None
        try:
            result = self._git(["log", "-1", "--format=%aI", branch], check=False)
            if result.returncode == 0:
                ts = result.stdout.strip()
                return ts if ts else None
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Internal checkpoint helpers
    # ------------------------------------------------------------------

    def _do_checkpoint_flush(self) -> None:
        """Build and push a coalesced checkpoint commit.

        Called by the ``CheckpointQueue`` flush function.  Uses the tracker's
        ``_write_lock`` to prevent concurrent git operations.  The pending
        in-memory task files have already been written to the state-branch
        worktree directory by the individual mutation methods; this step just
        does ``git add`` + ``git commit`` + ``git push``.

        When ``state_branch_shadow_write=True`` (Stage A migration), also
        shadow-commits the same task files to the default branch for zero-
        data-loss rollback capability (design § 6.2 Stage A).

        After a successful commit, invokes ``_on_checkpoint_flushed`` if set so
        callers (e.g. server.py) can invalidate their read-layer caches and push
        fresh data to connected clients without waiting for the normal TTL to
        expire.
        """
        with self._write_lock:
            self._commit_and_push_state_branch("Checkpoint oompah task state")
            if self.state_branch_shadow_write:
                self._shadow_write_to_default_branch(
                    "Shadow checkpoint (Stage A migration)"
                )
        # Record the checkpoint time so server.py can detect when its issues
        # snapshot is older than the latest state-branch commit.
        self.last_checkpoint_at = time.monotonic()
        # A checkpoint advances the durable state-branch generation even when
        # the mutation was made through another tracker instance.  Notify
        # subscribers after the commit so list/detail caches cannot continue
        # presenting the pre-checkpoint state.
        self._notify_read_change()
        # Invoke the post-checkpoint callback outside the write lock to avoid
        # deadlocks when the callback tries to read tracker state.
        if callable(self._on_checkpoint_flushed):
            try:
                self._on_checkpoint_flushed()
            except Exception:  # noqa: BLE001 — callback failures must not abort the flush
                logger.exception("Error in _on_checkpoint_flushed callback")

    def add_read_change_callback(self, callback: Any) -> None:
        """Register *callback* for direct mutations and checkpoint commits.

        Callbacks are best-effort observers.  They must not be able to make a
        successful task mutation fail, and duplicate registrations are ignored.
        """
        if not callable(callback):
            return
        with self._read_cache_guard:
            if callback not in self._read_change_callbacks:
                self._read_change_callbacks.append(callback)

    def _notify_read_change(self) -> None:
        with self._read_cache_guard:
            callbacks = list(self._read_change_callbacks)
        for callback in callbacks:
            try:
                callback()
            except Exception:  # noqa: BLE001 — observers must not break writes
                logger.exception("Error in native tracker read-change callback")

    def _schedule_checkpoint(self) -> None:
        """Notify the checkpoint queue that a new mutation is pending.

        Called after every state-branch task mutation.  If there is no queue
        (legacy mode or state-branch not yet enabled), this is a no-op.
        """
        if self._checkpoint_queue is not None:
            self._checkpoint_queue.schedule()

    def _maybe_mandatory_flush(self, new_status: str | None) -> None:
        """Trigger an immediate checkpoint flush for mandatory events (§ 5.3).

        Mandatory flush triggers:
        - Terminal statuses (Done, Merged, Archived)
        - In Review transition

        Other mandatory-flush events (human API edits, SIGTERM, session exit)
        are triggered by callers via :meth:`flush_checkpoint`.
        """
        if self._checkpoint_queue is None:
            return
        status = canonicalize_status(new_status)
        if is_terminal_status(status) or status == IN_REVIEW:
            reason = f"terminal_status:{status}" if is_terminal_status(status) else "in_review"
            self._checkpoint_queue.flush(reason=reason)

    @property
    def root_path(self) -> Path:
        return self._root

    @property
    def tasks_root(self) -> Path:
        """Return the ``.oompah/tasks`` directory for this tracker.

        When ``state_branch_enabled=True``, returns the tasks directory inside
        the dedicated state-branch git worktree so that all reads and writes
        target the state branch without switching the shared code checkout.
        """
        if self.state_branch_enabled:
            return self._get_state_root() / TASKS_DIR
        return self._root / TASKS_DIR

    def fetch_candidate_issues(self) -> list[Issue]:
        active = {
            status_key(state)
            for state in self.active_states
            if canonicalize_status(state) not in {PROPOSED, IN_VALIDATION}
        }
        issues = [
            issue
            for issue in self.fetch_all_issues()
            if status_key(issue.state) in active
            and canonicalize_status(issue.state) not in {PROPOSED, IN_VALIDATION}
        ]
        return _sort_issues_for_dispatch(issues)

    def fetch_in_progress_issues(self) -> list[Issue]:
        """Fetch tasks currently in In Progress state for orphan cleanup."""
        return self.fetch_issues_by_states([IN_PROGRESS])

    def fetch_all_issues(self) -> list[Issue]:
        # Native dependency metadata stores identifiers, not a duplicated
        # status.  Resolve every edge from the same coherent record cut that
        # produced its task so workflow facts never interpret an absent
        # ``BlockerRef.state`` as Backlog.
        with self._write_lock:
            records = self._read_records()
            with self._read_cache_guard:
                states = dict(self._read_cache_status_by_id or {})
            return [
                self._with_dependency_states(self._normalize_record(rec), states)
                for rec in records
            ]

    def fetch_all_issues_with_generation(self) -> tuple[list[Issue], str | None]:
        """Return issues and the exact state-branch generation they represent.

        Normalization and generation capture share the repository mutation
        lock.  A status-file move therefore cannot occur after the records are
        read but before their generation is sampled.
        """
        with self._write_lock:
            issues = self.fetch_all_issues()
            return issues, self._state_branch_generation_locked()

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return self.fetch_all_issues()

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        # Keep the task row and every dependency status under the shared
        # repository mutation lock.  A concurrent status-file move therefore
        # appears wholly before or wholly after this detail observation.
        with self._write_lock:
            self._recover_batch_manifest()
            rec = self._read_record(identifier)
            if rec is None:
                return None
            with self._read_cache_guard:
                states = dict(self._read_cache_status_by_id or {})
            return self._with_dependency_states(
                self._normalize_record(rec), states
            )

    def fetch_issue_detail_with_generation(
        self, identifier: str
    ) -> tuple[Issue | None, str | None]:
        """Return one issue and the exact state-branch generation it represents."""
        with self._write_lock:
            issue = self.fetch_issue_detail(identifier)
            return issue, self._state_branch_generation_locked()

    def fetch_children(self, epic_id: str) -> list[Issue]:
        needle = self._lookup_id(epic_id)
        children = []
        for issue in self.fetch_all_issues():
            if issue.parent_id and self._lookup_id(issue.parent_id) == needle:
                children.append(issue)
        return _sort_issues_for_dispatch(children)

    def fetch_comments(self, identifier: str) -> list[dict]:
        rec = self._read_record(identifier)
        if not rec:
            return []
        return parse_tracker_comments(str(rec["body"]))

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        wanted = {status_key(canonicalize_status(s)) for s in state_names}
        return [
            issue
            for issue in self.fetch_all_issues()
            if status_key(issue.state) in wanted
        ]

    def fetch_issues_by_states_page(
        self,
        state_names: list[str],
        *,
        after: str | None,
        limit: int,
    ) -> tuple[list[Issue], int, str | None, bool]:
        """Read one bounded, stable page from selected native status folders.

        The cursor is the task path relative to ``tasks_root``.  Resumption is
        strictly after that key, so deleting or moving the exact cursor row
        cannot replay the already-examined prefix.  Paths are enumerated under
        the repository mutation lock, but Markdown parsing and normalization
        are limited to at most ``limit`` records from a cold cache.
        """

        if limit <= 0:
            return [], 0, after, True
        wanted_dirs = {
            _status_dir(canonicalize_status(state)) for state in state_names
        }
        wanted_states = {
            status_key(canonicalize_status(state)) for state in state_names
        }
        with self._write_lock:
            keyed_paths: list[tuple[str, Path]] = []
            for status_dir in sorted(wanted_dirs):
                directory = self.tasks_root / status_dir
                if not directory.is_dir():
                    continue
                keyed_paths.extend(
                    (f"{status_dir}/{path.name}", path)
                    for path in directory.glob("*.md")
                    if path.is_file()
                )
            keyed_paths.sort(key=lambda item: item[0])
            keys = [item[0] for item in keyed_paths]
            start = bisect.bisect_right(keys, after) if after is not None else 0
            selected = keyed_paths[start : start + limit]
            issues: list[Issue] = []
            for _key, path in selected:
                try:
                    meta, body = _read_markdown(path)
                    issue = self._normalize_record(
                        {"path": path, "meta": meta, "body": body}
                    )
                except TrackerError as exc:
                    logger.warning(
                        "Skipping unreadable native task during bounded state scan "
                        "path=%s error=%s",
                        path,
                        exc,
                    )
                    continue
                if status_key(issue.state) in wanted_states:
                    issues.append(issue)
            examined = len(selected)
            cursor = selected[-1][0] if selected else after
            deferred = start + examined < len(keyed_paths)
            return issues, examined, cursor, deferred

    def fetch_issues_by_labels(
        self,
        labels: list[str],
        *,
        states: list[str] | None = None,
    ) -> list[Issue]:
        wanted_labels = {label.strip().lower() for label in labels if label.strip()}
        wanted_states = (
            {status_key(canonicalize_status(state)) for state in states}
            if states is not None
            else None
        )
        matched = []
        for issue in self.fetch_all_issues():
            present = {label.strip().lower() for label in (issue.labels or [])}
            if wanted_labels and not wanted_labels.issubset(present):
                continue
            if wanted_states is not None and status_key(issue.state) not in wanted_states:
                continue
            matched.append(issue)
        return _sort_issues_for_dispatch(matched)

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        wanted = {self._lookup_id(issue_id) for issue_id in issue_ids if issue_id}
        if not wanted:
            return []
        # Resolve the complete batch from one coherent cached scan. This avoids
        # N detail reads and guarantees every preflight member belongs to the
        # same repository generation even when another process is publishing.
        with self._write_lock:
            records = self._read_records()
            with self._read_cache_guard:
                states = dict(self._read_cache_status_by_id or {})
            found: dict[str, Issue] = {}
            for record in records:
                issue = self._normalize_record(record)
                key = self._lookup_id(issue.identifier)
                if key in wanted:
                    found[key] = self._with_dependency_states(issue, states)
            return [
                found[key]
                for issue_id in issue_ids
                if (key := self._lookup_id(issue_id)) in found
            ]

    def fetch_memories(self) -> dict[str, str]:
        return {}

    def create_issue(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
        initial_status: str | None = None,
        labels: list[str] | None = None,
        parent: str | None = None,
    ) -> Issue:
        clean_title = str(title or "").strip()
        if not clean_title:
            raise TrackerError("Native oompah task title is required")
        status = canonicalize_status(initial_status or BACKLOG)
        with self._write_lock:
            self._prepare_default_branch_for_write()
            identifier = self._next_identifier()
            now = _now_iso()
            issue_type = (issue_type or "task").strip().lower()
            if issue_type not in _ISSUE_TYPES:
                issue_type = "task"
            effective_labels = _dedupe_strings(labels or [])
            meta: dict[str, Any] = {
                "id": identifier,
                "type": issue_type,
                "status": status,
                "priority": priority,
                "title": clean_title,
                "parent": parent or None,
                "children": [],
                "blocked_by": [],
                "start_blocked_by": [],
                "labels": effective_labels,
                "assignee": None,
                "created_at": now,
                "updated_at": now,
                "work_branch": None,
                "target_branch": None,
                "review_url": None,
                "review_number": None,
                "review_head": None,
                "merged_at": None,
            }
            body = self._initial_body(description)
            path = self._path_for(identifier, status)
            _write_markdown(path, meta, body)
            if parent:
                self._add_child_to_parent(parent, identifier)
            self._invalidate_after_mutation(
                task_id=identifier if not parent else None
            )
            self._commit_and_push(f"Create oompah task {identifier}")
        created = self.fetch_issue_detail(identifier)
        if not created:
            raise TrackerError(f"Created native oompah task disappeared: {identifier}")
        return created

    def create_issue_once(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
        initial_status: str | None = None,
        labels: list[str] | None = None,
        parent: str | None = None,
        *,
        project_id: str,
        operation_kind: str,
        creation_marker: str,
    ) -> Issue:
        """Atomically create or recover the issue for one durable marker.

        The marker and a fingerprint of the normalized request live in the
        task front matter.  Lookup, identifier allocation, task creation, and
        parent linkage all run under the repository-wide mutation lock.  A
        retry after an ambiguous response therefore returns the original task
        and a mismatched reuse of the same key fails closed.
        """
        clean_project_id = str(project_id or "").strip()
        clean_operation_kind = str(operation_kind or "").strip()
        clean_marker = str(creation_marker or "").strip()
        if not clean_project_id:
            raise TrackerError("Atomic create-once requires a project id")
        if not clean_operation_kind:
            raise TrackerError("Atomic create-once requires an operation kind")
        if not clean_marker:
            raise TrackerError("Atomic create-once requires a creation marker")
        if max(
            len(clean_project_id),
            len(clean_operation_kind),
            len(clean_marker),
        ) > 512:
            raise TrackerError("Atomic create-once key fields must not exceed 512 bytes")

        clean_title = str(title or "").strip()
        if not clean_title:
            raise TrackerError("Native oompah task title is required")
        status = canonicalize_status(initial_status or BACKLOG)
        clean_issue_type = (issue_type or "task").strip().lower()
        if clean_issue_type not in _ISSUE_TYPES:
            clean_issue_type = "task"
        effective_labels = _dedupe_strings(labels or [])
        normalized_description = _summary_safe_description(description)
        normalized_parent = str(parent or "").strip() or None
        request_payload = {
            "title": clean_title,
            "issue_type": clean_issue_type,
            "description": normalized_description,
            "priority": priority,
            "initial_status": status,
            "labels": effective_labels,
            "parent": normalized_parent,
        }
        request_fingerprint = hashlib.sha256(
            json.dumps(
                request_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        creation_key = {
            "version": 1,
            "project_id": clean_project_id,
            "operation_kind": clean_operation_kind,
            "creation_marker": clean_marker,
            "request_fingerprint": request_fingerprint,
        }

        with self._write_lock:
            self._prepare_default_branch_for_write()
            matches: list[dict[str, Any]] = []
            for record in self._read_records():
                recorded = record["meta"].get("oompah.create_once")
                if not isinstance(recorded, dict):
                    continue
                if (
                    str(recorded.get("project_id") or "").strip()
                    == clean_project_id
                    and str(recorded.get("operation_kind") or "").strip()
                    == clean_operation_kind
                    and str(recorded.get("creation_marker") or "").strip()
                    == clean_marker
                ):
                    matches.append(record)
            if len(matches) > 1:
                identifiers = sorted(
                    str(record["meta"].get("id") or Path(record["path"]).stem)
                    for record in matches
                )
                raise CreateOnceConflictError(
                    "Atomic create-once key resolves to multiple native tasks: "
                    + ", ".join(identifiers)
                )
            if matches:
                recorded_fingerprint = str(
                    matches[0]["meta"].get("oompah.create_once", {}).get(
                        "request_fingerprint"
                    )
                    or ""
                )
                if recorded_fingerprint != request_fingerprint:
                    raise CreateOnceConflictError(
                        "Atomic create-once key was already used with a different payload"
                    )
                # The first request may have written the task and then lost
                # the commit/push response before publication was confirmed.
                # Re-drive the same durable boundary; this is a no-op when the
                # original commit already landed and schedules the pending
                # state-branch mutation when it did not.
                identifier = str(
                    matches[0]["meta"].get("id") or Path(matches[0]["path"]).stem
                )
                self._commit_and_push(f"Recover create-once task {identifier}")
                return self._normalize_record(matches[0])

            identifier = self._next_identifier()
            now = _now_iso()
            meta: dict[str, Any] = {
                "id": identifier,
                "type": clean_issue_type,
                "status": status,
                "priority": priority,
                "title": clean_title,
                "parent": normalized_parent,
                "children": [],
                "blocked_by": [],
                "start_blocked_by": [],
                "labels": effective_labels,
                "assignee": None,
                "created_at": now,
                "updated_at": now,
                "work_branch": None,
                "target_branch": None,
                "review_url": None,
                "review_number": None,
                "review_head": None,
                "merged_at": None,
                "oompah.create_once": creation_key,
            }
            body = self._initial_body(normalized_description)
            path = self._path_for(identifier, status)
            _write_markdown(path, meta, body)
            if normalized_parent:
                self._add_child_to_parent(normalized_parent, identifier)
            self._invalidate_after_mutation(
                task_id=str(meta["id"]) if not normalized_parent else None
            )
            self._commit_and_push(f"Create oompah task {identifier}")
            record = self._read_record_uncached(identifier)
            if record is None:
                raise TrackerError(
                    f"Created native oompah task disappeared: {identifier}"
                )
            return self._normalize_record(record)

    def update_issue(self, identifier: str, **fields: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            path = Path(rec["path"])
            meta: dict[str, Any] = dict(rec["meta"])
            body = str(rec["body"])
            old_status = canonicalize_status(str(meta.get("status") or BACKLOG))
            for key, value in fields.items():
                body = self._apply_field(meta, body, key, value)
            meta["updated_at"] = _now_iso()
            new_status = canonicalize_status(str(meta.get("status") or old_status))
            if new_status != old_status:
                prior_revision = meta.get("oompah.lifecycle_revision", 0)
                if isinstance(prior_revision, bool) or not isinstance(
                    prior_revision, int
                ):
                    prior_revision = 0
                meta["oompah.lifecycle_revision"] = prior_revision + 1
            new_path = self._path_for(str(meta["id"]), new_status)
            if new_path == path:
                _write_markdown(path, meta, body)
            else:
                # Persist the new record at the currently authoritative path,
                # then atomically rename that inode into its canonical status
                # directory.  Readers outside this process can observe the old
                # path or the new path, but never the former copy-plus-unlink
                # window where both status files existed simultaneously.
                _write_markdown(path, meta, body)
                new_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    path.replace(new_path)
                except OSError as exc:
                    raise TrackerError(
                        f"Cannot move native task {path} to {new_path}: {exc}"
                    ) from exc
            self._invalidate_after_mutation(task_id=identifier)
            self._commit_and_push(f"Update oompah task {meta['id']}")
        # Mandatory flush for terminal/In Review transitions (design § 5.3).
        # Called OUTSIDE _write_lock to avoid nested-lock deadlock with
        # CheckpointQueue._lock, which is acquired inside flush().
        if self._checkpoint_queue is not None and new_status != old_status:
            self._maybe_mandatory_flush(new_status)

    def batch_update_issues(
        self,
        updates: list[dict[str, Any]],
        *,
        project_id: str,
        actor: str,
        idempotency_key: str,
        request_hash: str,
        operation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply one ordered compare-and-swap batch in one tracker transaction.

        Every record and the idempotency receipt are written while the shared
        repository lock is held, then published by one commit/checkpoint.  A
        stale member or local write failure restores the complete pre-batch
        file set before releasing the lock.
        """

        from oompah.task_transition_service import issue_authority_version

        if not updates:
            raise BatchPreconditionError(
                [{"code": "empty_batch", "message": "updates must not be empty"}]
            )
        identifiers = [str(update.get("identifier") or "").strip() for update in updates]
        if any(not identifier for identifier in identifiers):
            raise BatchPreconditionError(
                [{"code": "invalid_identifier", "message": "identifier is required"}]
            )
        if len(set(identifiers)) != len(identifiers):
            raise BatchPreconditionError(
                [
                    {
                        "code": "duplicate_identifier",
                        "message": "batch identifiers must be unique",
                    }
                ]
            )

        receipt_key = f"{project_id}:{idempotency_key}"
        with self._write_lock:
            self._prepare_default_branch_for_write()
            receipts = self._read_batch_receipts()
            prior_receipt = receipts.get(receipt_key)
            if isinstance(prior_receipt, dict):
                if prior_receipt.get("request_hash") != request_hash:
                    raise BatchIdempotencyConflictError(
                        "Idempotency-Key was already used for a different batch."
                    )
                return {
                    "batch_id": str(prior_receipt.get("batch_id") or ""),
                    "replayed": True,
                    "results": list(prior_receipt.get("results") or []),
                }
            records: dict[str, dict[str, Any]] = {}
            rejections: list[dict[str, Any]] = []
            for identifier in identifiers:
                record = self._read_record_uncached(identifier)
                if record is None:
                    rejections.append(
                        {
                            "identifier": identifier,
                            "code": "task_missing",
                            "message": "Task was not found in this project.",
                        }
                    )
                else:
                    records[identifier] = record
            if rejections:
                raise BatchPreconditionError(rejections)

            for update in updates:
                identifier = str(update["identifier"])
                issue = self._normalize_record(records[identifier])
                issue.project_id = project_id
                observed_revision = issue_authority_version(issue)
                expected_revision = str(update.get("expected_revision") or "")
                expected_status = canonicalize_status(update.get("expected_status"))
                if expected_revision != observed_revision or (
                    expected_status and expected_status != canonicalize_status(issue.state)
                ):
                    rejections.append(
                        {
                            "identifier": identifier,
                            "code": "stale_revision",
                            "message": "Task changed after the board snapshot.",
                            "current_status": canonicalize_status(issue.state),
                            "current_revision": observed_revision,
                        }
                    )
            if rejections:
                raise BatchPreconditionError(rejections)

            batch_id = f"batch-{uuid.uuid4().hex}"
            backups: list[tuple[Path, Path, str]] = []
            written: dict[str, dict[str, Any]] = {}
            now = _now_iso()
            manifest_written = False
            try:
                for update in updates:
                    identifier = str(update["identifier"])
                    record = records[identifier]
                    old_path = Path(record["path"])
                    meta = dict(record["meta"])
                    body = str(record["body"])
                    for key, value in dict(update.get("fields") or {}).items():
                        body = self._apply_field(meta, body, key, value)
                    meta["updated_at"] = now
                    old_status = canonicalize_status(
                        str(record["meta"].get("status") or BACKLOG)
                    )
                    new_status = canonicalize_status(
                        str(meta.get("status") or old_status)
                    )
                    if new_status != old_status:
                        prior_revision = meta.get("oompah.lifecycle_revision", 0)
                        if isinstance(prior_revision, bool) or not isinstance(
                            prior_revision, int
                        ):
                            prior_revision = 0
                        meta["oompah.lifecycle_revision"] = prior_revision + 1
                    meta["oompah.last_batch"] = {
                        "batch_id": batch_id,
                        "actor": actor,
                        "committed_at": now,
                        "operation": dict(operation or {}),
                    }
                    new_path = self._path_for(str(meta["id"]), new_status)
                    backups.append(
                        (old_path, new_path, old_path.read_text(encoding="utf-8"))
                    )
                    written[identifier] = {
                        "path": new_path,
                        "meta": meta,
                        "body": body,
                    }

                results: list[dict[str, str]] = []
                for identifier in identifiers:
                    issue = self._normalize_record(written[identifier])
                    issue.project_id = project_id
                    results.append(
                        {
                            "identifier": identifier,
                            "status": canonicalize_status(issue.state),
                            "revision": issue_authority_version(issue),
                        }
                    )
                receipts[receipt_key] = {
                    "batch_id": batch_id,
                    "request_hash": request_hash,
                    "committed_at": now,
                    "operation": dict(operation or {}),
                    "results": results,
                }
                receipt_existed = self._batch_receipts_path.exists()
                receipt_backup = (
                    self._batch_receipts_path.read_text(encoding="utf-8")
                    if receipt_existed
                    else ""
                )

                manifest = {
                    "schema_version": 1,
                    "phase": "writing",
                    "task_count": len(identifiers),
                    "receipt_existed": receipt_existed,
                    "receipt_content": receipt_backup,
                    "backups": [
                        {
                            "old_path": str(old_path.relative_to(self.tasks_root)),
                            "new_path": str(new_path.relative_to(self.tasks_root)),
                            "content": content,
                        }
                        for old_path, new_path, content in backups
                    ],
                }
                _atomic_write(
                    self._batch_transaction_path,
                    json.dumps(manifest, sort_keys=True),
                )
                manifest_written = True
                _atomic_write(
                    self._batch_receipts_path,
                    yaml.safe_dump(receipts, sort_keys=False, allow_unicode=False),
                )
                for identifier in identifiers:
                    record = written[identifier]
                    old_path, new_path, _content = next(
                        backup for backup in backups if backup[0].stem == identifier
                    )
                    _write_markdown(new_path, record["meta"], record["body"])
                    if old_path != new_path:
                        old_path.unlink(missing_ok=True)
                # Past this durable boundary every member and the receipt are
                # present together. A publish failure has an unknown remote
                # outcome, so a successor must re-drive this exact commit/push
                # instead of restoring files behind a possibly-created commit.
                manifest["phase"] = "publishing"
                _atomic_write(
                    self._batch_transaction_path,
                    json.dumps(manifest, sort_keys=True),
                )
            except BaseException:
                if manifest_written:
                    for old_path, new_path, content in reversed(backups):
                        if new_path != old_path:
                            new_path.unlink(missing_ok=True)
                        _atomic_write(old_path, content)
                    if receipt_existed:
                        _atomic_write(self._batch_receipts_path, receipt_backup)
                    else:
                        self._batch_receipts_path.unlink(missing_ok=True)
                    self._batch_transaction_path.unlink(missing_ok=True)
                raise
            for identifier in identifiers:
                _advance_repo_read_generation(
                    self._repo_lock_key,
                    task_id=identifier,
                )
            self._clear_read_cache_local()
            try:
                self._publish_batch_transaction(len(identifiers))
            except BaseException:
                # The local commit may exist and the remote may have accepted
                # the push even when its response was lost. Preserve the
                # complete transaction and receipt so the same idempotency key
                # can safely finish publication on retry.
                raise
            self._batch_transaction_path.unlink(missing_ok=True)

        self._notify_read_change()
        generation = self.get_state_branch_generation()
        if generation is not None:
            for result in results:
                result["storage_generation"] = generation
        return {"batch_id": batch_id, "replayed": False, "results": results}

    def batch_update_receipt(
        self,
        identifier: str,
        *,
        project_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        """Read one exact durable batch receipt without applying new effects."""

        with self._write_lock:
            recovered_publication = self._recover_batch_manifest(publish=True)
            receipts = self._read_batch_receipts()
            receipt = receipts.get(f"{project_id}:{idempotency_key}")
            if not isinstance(receipt, dict):
                return None
            if receipt.get("request_hash") != request_hash:
                raise BatchIdempotencyConflictError(
                    "Idempotency-Key was already used for a different batch."
                )
            result = {
                "batch_id": str(receipt.get("batch_id") or ""),
                "replayed": True,
                "results": list(receipt.get("results") or []),
            }
            if recovered_publication:
                # The original API call never crossed the tracker return
                # boundary, so its coalesced workflow/scheduler effects still
                # need to be emitted once by the recovering request.
                result["recovered_publication"] = True
            return result

    @property
    def _batch_transaction_path(self) -> Path:
        return self.tasks_root.parent / ".batch-transaction.json"

    @property
    def _batch_receipts_path(self) -> Path:
        return self.tasks_root / "batch-receipts.yml"

    def _read_batch_receipts(self) -> dict[str, Any]:
        path = self._batch_receipts_path
        if not path.exists():
            return {}
        try:
            raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_YAML_SAFE_LOADER)
        except (OSError, yaml.YAMLError) as exc:
            raise TrackerError("Cannot read native batch idempotency receipts") from exc
        if not isinstance(raw, dict):
            raise TrackerError("Native batch idempotency receipts are malformed")
        return {str(key): value for key, value in raw.items()}

    def _publish_batch_transaction(self, task_count: int) -> None:
        """Publish an already materialized all-member batch exactly once."""

        subject = f"Batch update {task_count} oompah tasks"
        if self.state_branch_enabled and self._checkpoint_queue is not None:
            self._commit_and_push_state_branch(subject)
            if self.state_branch_shadow_write:
                self._shadow_write_to_default_branch(f"Shadow {subject.lower()}")
            self.last_checkpoint_at = time.monotonic()
        else:
            self._commit_and_push(subject)

    def _recover_batch_manifest(self, *, publish: bool = False) -> bool:
        """Recover an interrupted batch at its durable transaction phase.

        ``writing`` has no commit authority and is rolled back completely.
        ``publishing`` already contains every member plus its idempotency
        receipt and must be re-driven, never rolled back behind a possibly
        successful local commit or remote push. Read paths may observe that
        coherent local state without performing network I/O; receipt lookups
        and the next writer finish publication before continuing.
        """

        manifest_path = self._batch_transaction_path
        if not manifest_path.exists():
            return False
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            backups = raw.get("backups") if isinstance(raw, dict) else None
            if not isinstance(backups, list) or not backups:
                raise ValueError("manifest has no backups")
            root = self.tasks_root.resolve()
            restored: list[tuple[Path, Path, str]] = []
            for item in backups:
                if not isinstance(item, dict):
                    raise ValueError("backup entry is invalid")
                old_path = (root / str(item.get("old_path") or "")).resolve()
                new_path = (root / str(item.get("new_path") or "")).resolve()
                if root not in old_path.parents or root not in new_path.parents:
                    raise ValueError("backup path escapes task storage")
                content = item.get("content")
                if not isinstance(content, str):
                    raise ValueError("backup content is invalid")
                restored.append((old_path, new_path, content))
            phase = str(raw.get("phase") or "writing")
            if phase == "publishing":
                if not publish:
                    return False
                task_count = raw.get("task_count")
                if not isinstance(task_count, int) or task_count < 1:
                    raise ValueError("publishing manifest has invalid task count")
                self._publish_batch_transaction(task_count)
                manifest_path.unlink(missing_ok=True)
                self._clear_read_cache_local()
                logger.warning(
                    "Completed publication of an interrupted native task batch"
                )
                self._notify_read_change()
                return True
            if phase != "writing":
                raise ValueError(f"manifest has unknown phase {phase!r}")

            for old_path, new_path, content in reversed(restored):
                if new_path != old_path:
                    new_path.unlink(missing_ok=True)
                _atomic_write(old_path, content)
            receipt_content = raw.get("receipt_content")
            if raw.get("receipt_existed") is True:
                if not isinstance(receipt_content, str):
                    raise ValueError("receipt backup is invalid")
                _atomic_write(self._batch_receipts_path, receipt_content)
            else:
                self._batch_receipts_path.unlink(missing_ok=True)
            manifest_path.unlink(missing_ok=True)
            self._clear_read_cache_local()
            logger.warning("Recovered an interrupted native task batch transaction")
            return False
        except Exception as exc:
            raise TrackerError(
                "Cannot recover interrupted native task batch transaction"
            ) from exc

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        status = self._terminal_status()
        fields: dict[str, str] = {"status": status}
        self.update_issue(identifier, **fields)
        if reason:
            self.add_comment(identifier, reason)

    def reopen_issue(self, identifier: str) -> None:
        self.update_issue(identifier, status=self._active_status())

    def archive_issue(self, identifier: str) -> None:
        # TERMINAL-AUDIT-ALLOW OOMPAH-483: low-level tracker persistence
        # implementation for the Archived lifecycle state.
        self.update_issue(identifier, status=ARCHIVED)

    def mark_needs_human(
        self,
        identifier: str,
        comment: str,
        author: str = "oompah",
    ) -> None:
        handoff = validate_needs_human_comment(comment)
        self.update_issue(identifier, status="Needs Human")
        self.add_comment(identifier, handoff, author=author)

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        comment_text = str(text or "").strip()
        if not comment_text:
            raise TrackerError("Comment text is required")
        comment_author = comment_author_field(author, fallback="oompah")
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            body = append_tracker_comment(
                str(rec["body"]),
                text=comment_text,
                author=comment_author,
                created=format_comment_timestamp(),
            )
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, body)
            self._invalidate_after_mutation(task_id=identifier)
            self._commit_and_push(f"Comment on oompah task {meta['id']}")
        return {"author": comment_author, "text": comment_text}

    def add_label(self, identifier: str, label: str) -> None:
        self.update_issue(identifier, **{"add-label": label})

    def remove_label(self, identifier: str, label: str) -> None:
        self.update_issue(identifier, **{"remove-label": label})

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            child = self._read_record_uncached(child_id)
            if not child:
                raise TrackerError(f"Native oompah task not found: {child_id}")
            child_meta = dict(child["meta"])
            child_meta["parent"] = parent_id
            child_meta["updated_at"] = _now_iso()
            _write_markdown(Path(child["path"]), child_meta, str(child["body"]))
            self._add_child_to_parent(parent_id, str(child_meta["id"]))
            self._invalidate_after_mutation()
            self._commit_and_push(f"Link oompah task {child_meta['id']} to parent")

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(blocked_id)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {blocked_id}")
            meta = dict(rec["meta"])
            deps = _dedupe_strings(_string_list(meta.get("blocked_by")) + [blocker_id])
            meta["blocked_by"] = deps
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self._invalidate_after_mutation(task_id=blocked_id)
            self._commit_and_push(f"Add dependency to oompah task {meta['id']}")

    def remove_dependency(self, blocked_id: str, blocker_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(blocked_id)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {blocked_id}")
            meta = dict(rec["meta"])
            blocker_key = str(blocker_id).strip().casefold()
            current = _dedupe_strings(_string_list(meta.get("blocked_by")))
            deps = [dep for dep in current if dep.strip().casefold() != blocker_key]
            if deps == current:
                return
            meta["blocked_by"] = deps
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self._invalidate_after_mutation(task_id=blocked_id)
            self._commit_and_push(f"Remove dependency from oompah task {meta['id']}")

    def add_start_dependency(self, blocked_id: str, blocker_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(blocked_id)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {blocked_id}")
            meta = dict(rec["meta"])
            deps = _dedupe_strings(
                _string_list(
                    meta.get("start_blocked_by")
                    or meta.get("oompah.start_blocked_by")
                )
                + [blocker_id]
            )
            meta["start_blocked_by"] = deps
            meta["oompah.start_blocked_by"] = deps
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self._invalidate_after_mutation(task_id=blocked_id)
            self._commit_and_push(
                f"Add hard-start dependency to oompah task {meta['id']}"
            )

    def remove_start_dependency(self, blocked_id: str, blocker_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(blocked_id)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {blocked_id}")
            meta = dict(rec["meta"])
            blocker_key = str(blocker_id).strip().casefold()
            current = _dedupe_strings(
                _string_list(
                    meta.get("start_blocked_by")
                    or meta.get("oompah.start_blocked_by")
                )
            )
            deps = [dep for dep in current if dep.strip().casefold() != blocker_key]
            if deps == current:
                return
            meta["start_blocked_by"] = deps
            meta["oompah.start_blocked_by"] = deps
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self._invalidate_after_mutation(task_id=blocked_id)
            self._commit_and_push(
                f"Remove hard-start dependency from oompah task {meta['id']}"
            )

    def fetch_attachments(self, identifier: str) -> list[dict]:
        rec = self._read_record(identifier)
        if not rec:
            return []
        entries = rec["meta"].get("oompah.attachments") or []
        return [entry for entry in entries if isinstance(entry, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            meta["oompah.attachments"] = list(attachments)
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self._invalidate_after_mutation(task_id=identifier)
            self._commit_and_push(f"Update attachments for oompah task {meta['id']}")

    def get_metadata(self, identifier: str) -> dict[str, object]:
        rec = self._read_record(identifier)
        if not rec:
            return {}
        meta = rec["meta"]
        result = {
            str(key): value
            for key, value in meta.items()
            if str(key).startswith("oompah.")
        }
        for key in (
            "work_branch",
            "target_branch",
            "review_url",
            "review_number",
            "review_head",
            "merged_at",
        ):
            if key in meta and meta[key] is not None:
                result[f"oompah.{key}"] = meta[key]
        return result

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        if not key.startswith("oompah."):
            raise TrackerError(f"Native metadata key must be oompah-owned: {key}")
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            compat_key = key.removeprefix("oompah.")
            compat_keys = {
                "work_branch",
                "target_branch",
                "review_url",
                "review_number",
                "review_head",
                "merged_at",
            }
            # Review reconciliation calls this method on every poll.  A
            # metadata value that is already present must be a true no-op:
            # changing only ``updated_at`` creates a tracker commit, which in
            # turn invalidates GitHub merge queues for repositories that keep
            # their native tasks on the default branch.
            if meta.get(key) == value and (
                compat_key not in compat_keys or meta.get(compat_key) == value
            ):
                return

            meta[key] = value
            if compat_key in compat_keys:
                meta[compat_key] = value
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self._invalidate_after_mutation(
                task_id=identifier,
                authority_kind=(
                    "terminal_audit" if key == "oompah.terminal_audit" else None
                ),
            )
            self._commit_and_push(f"Update metadata for oompah task {meta['id']}")

    def is_archived(self, issue: Issue) -> bool:
        return canonicalize_status(issue.state) == ARCHIVED

    def get_raw_body(self, identifier: str) -> str | None:
        """Return the full raw body string for a native task, or ``None``."""
        rec = self._read_record(identifier)
        return str(rec["body"]) if rec else None

    def set_raw_body(self, identifier: str, body: str) -> None:
        """Replace the entire body of a native task with *body*.

        Unlike :meth:`update_issue` (which only replaces the ``## Summary``
        section), this method writes the complete new body verbatim.  It is
        used by the intake normalizer to restructure malformed task bodies.
        """
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, body)
            self._invalidate_after_mutation(task_id=identifier)
            self._commit_and_push(f"Normalize native oompah task {meta['id']}")

    def write_and_commit_ledger_file(
        self,
        relative_path: str,
        content: str,
        subject: str,
    ) -> None:
        """Write *content* to *relative_path* and commit it on the default branch.

        This is the supported path for non-task ledger files (such as
        ``.oompah/release-deliveries.yml``) that need to be committed on the
        project's default branch alongside task state changes.  It uses the
        same git infrastructure as task writes: branch validation, atomic
        file write, fetch + ff-only sync before write, and push with retry.

        Args:
            relative_path: Path relative to the project root
                (e.g. ``".oompah/release-deliveries.yml"``).
            content: Full text content of the file.
            subject: Commit message subject line.

        Raises:
            TrackerError: When the current branch is not the default branch,
                the git sync fails, or the commit/push fails.
        """
        full_path = self._root / relative_path
        with self._write_lock:
            self._prepare_default_branch_for_write(task_state=False)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(full_path, content)
            if not self._git_sync_requested() or not self._is_git_repo():
                return
            self._git(["add", relative_path], check=True)
            if (
                self._git(
                    ["diff", "--cached", "--quiet", "--", relative_path],
                    check=False,
                ).returncode
                == 0
            ):
                return  # Nothing staged — file unchanged, no commit needed
            message = (
                f"{subject}\n\n"
                "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
                "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
            )
            self._git(["commit", "-m", message], check=True)
            branch = self.default_branch or self._infer_default_branch() or "main"
            if not self._has_remote("origin"):
                return
            # Retry loop mirrors _commit_and_push: up to _PUSH_MAX_RETRIES total
            # attempts, each preceded by a sync after a rejected push (OOMPAH-265).
            last_push = self._git(["push", "origin", f"HEAD:{branch}"], check=False)
            for attempt in range(1, _PUSH_MAX_RETRIES):
                if last_push.returncode == 0:
                    break
                if attempt > 1:
                    time.sleep(0.1 * (2 ** (attempt - 2)))
                self._sync_from_remote(branch)
                last_push = self._git(["push", "origin", f"HEAD:{branch}"], check=False)
            if last_push.returncode != 0:
                stderr = last_push.stderr.strip() or last_push.stdout.strip()
                raise TrackerError(f"git push origin HEAD:{branch} failed: {stderr}")

    def invalidate_read_cache(
        self,
    ) -> None:
        """Discard this instance's cached reads without claiming a mutation.

        Callers use this boundary to force a fresh observation before making a
        decision.  A refresh is not itself task authority: treating it as one
        makes a long workflow snapshot invalidate itself whenever a fact
        collector, API request, or proof path performs a defensive re-read.
        Native mutation methods use :meth:`_invalidate_after_mutation` so
        sibling tracker instances still observe every actual write.
        """

        with self._write_lock:
            self._clear_read_cache_local()

    def _invalidate_after_mutation(
        self,
        *,
        task_id: str | None = None,
        authority_kind: str | None = None,
    ) -> int:
        """Invalidate every sibling cache and advance task authority."""

        # A task mutation may be observed by another tracker instance for the
        # same repository. Advancing a shared generation prevents that instance
        # from returning a record whose cached path was just moved to another
        # status directory.
        # Reads hold the same repository lock while pairing their records with
        # the dependency-status index.  Advance authority and clear this
        # instance's related caches atomically with respect to that pair so an
        # invalidator cannot leave a reader with records from one generation
        # and an empty status map from the next.
        with self._write_lock:
            generation = _advance_repo_read_generation(
                self._repo_lock_key,
                task_id=task_id,
                authority_kind=authority_kind,
            )
            self._clear_read_cache_local()
        # Mutation invalidation occurs after the write has reached the
        # authoritative worktree and before the mutation is returned to the
        # caller, so server-side snapshots are invalidated synchronously. Keep
        # callbacks outside the repository lock because they may read through
        # this tracker again.
        self._notify_read_change()
        return generation

    def _clear_read_cache_local(self) -> None:
        """Discard this instance's caches without asserting an authority change."""

        with self._read_cache_guard:
            self._read_cache = None
            self._read_cache_by_id = None
            self._read_cache_status_by_id = None
            self._read_cache_generation = None
            self._corrupt_stubs = None

    def get_state_branch_generation(self) -> str | None:
        """Return the exact local state-branch read generation.

        The commit SHA fences durable checkpoint changes.  The shared
        repository read epoch fences direct, not-yet-committed mutations and
        mutations made through a sibling tracker instance.  Combining both
        keeps a cached board/detail response valid only for the exact
        authoritative view from which it was read, including after restart.
        """
        if not self.state_branch_enabled:
            return None
        with self._write_lock:
            self._recover_batch_manifest()
            return self._state_branch_generation_locked()

    def get_publication_revision(self) -> int:
        """Return the process-local task authority revision without Git I/O.

        Publication paths use the durable state-branch generation as an
        external preflight, then compare this revision while holding their
        project mutation fence.  Every native task mutation advances the
        shared repository revision before returning, including mutations made
        through a replacement tracker instance.  The final comparison is
        therefore a constant-time CAS and never runs ``git`` while unrelated
        project control work is blocked.
        """

        return _repo_read_generation(self._repo_lock_key)

    def task_authority_changes_between(
        self,
        expected_generation: str,
        current_generation: str,
    ) -> frozenset[str] | None:
        """Prove the exact task identities changed across two generations.

        Unscoped journal entries and non-task Git changes fail closed. This
        lets reconciliation retry only the affected project while retaining
        already-collected work for every stable project.
        """

        return self._scoped_task_changes_between(
            expected_generation,
            current_generation,
            required_authority_kind=None,
        )

    def terminal_metadata_changes_between(
        self,
        expected_generation: str,
        current_generation: str,
    ) -> frozenset[str] | None:
        """Prove that a generation delta contains only terminal metadata writes."""

        return self._scoped_task_changes_between(
            expected_generation,
            current_generation,
            required_authority_kind="terminal_audit",
        )

    def _scoped_task_changes_between(
        self,
        expected_generation: str,
        current_generation: str,
        *,
        required_authority_kind: str | None,
    ) -> frozenset[str] | None:
        """Prove one journalled task-only generation delta.

        The shared read epoch identifies every local tracker mutation, while
        the Git diff proves that a concurrent sync did not bring unrelated
        task changes into the same commit range.  ``None`` is the fail-closed
        result for an incomplete journal, an unscoped mutation, or any changed
        path outside the exact terminal-audit task set.
        """

        def split_generation(value: str) -> tuple[str, int] | None:
            commit, separator, raw_epoch = str(value or "").rpartition(":")
            if (
                not separator
                or len(commit) != 40
                or any(character not in "0123456789abcdef" for character in commit)
                or not raw_epoch.isdigit()
            ):
                return None
            return commit, int(raw_epoch)

        expected = split_generation(expected_generation)
        current = split_generation(current_generation)
        if expected is None or current is None:
            return None
        expected_commit, expected_epoch = expected
        _current_commit, current_epoch = current
        if current_epoch < expected_epoch:
            return None
        with self._write_lock:
            if self._state_branch_generation_locked() != current_generation:
                return None
            with _repo_write_locks_guard:
                floor = _repo_read_change_floors.get(self._repo_lock_key, 0)
                if expected_epoch < floor:
                    return None
                changes = tuple(
                    (task_id, authority_kind)
                    for epoch, task_id, authority_kind in _repo_read_changes.get(
                        self._repo_lock_key, []
                    )
                    if expected_epoch < epoch <= current_epoch
                )
            if len(changes) != current_epoch - expected_epoch:
                return None
            if any(task_id is None for task_id, _authority_kind in changes):
                return None
            if required_authority_kind is not None and any(
                authority_kind != required_authority_kind
                for _task_id, authority_kind in changes
            ):
                return None
            changed_tasks = frozenset(
                task_id for task_id, _authority_kind in changes if task_id is not None
            )
            result = self._git(
                ["diff", "--name-only", expected_commit, "--"],
                check=False,
                cwd=self._get_state_root(),
            )
            if result.returncode != 0:
                return None
            diff_tasks: set[str] = set()
            task_prefix = f"{TASKS_DIR}/"
            for raw_path in result.stdout.splitlines():
                path = raw_path.strip()
                if (
                    not path.startswith(task_prefix)
                    or not path.endswith(".md")
                ):
                    return None
                diff_tasks.add(Path(path).stem)
            if frozenset(diff_tasks) != changed_tasks:
                return None
            return changed_tasks

    def _state_branch_generation_locked(self) -> str | None:
        """Return the local source generation while the mutation lock is held."""
        if not self.state_branch_enabled:
            return None
        try:
            state_root = self._get_state_root()
            result = self._git(["rev-parse", "HEAD"], check=False, cwd=state_root)
            commit = result.stdout.strip() if result.returncode == 0 else "unavailable"
        except Exception:  # noqa: BLE001 — callers will mark the read stale
            commit = "unavailable"
        if not commit or commit == "unavailable":
            return "unavailable"
        return f"{commit}:{_repo_read_generation(self._repo_lock_key)}"

    def list_corrupt_stubs(self) -> list[dict[str, Any]]:
        """Return the list of corrupt or unreadable task file stubs.

        Each stub is a dict with:

        - ``path``: :class:`~pathlib.Path` to the corrupt file.
        - ``stem``: filename stem without the ``.md`` extension — this is the
          task identifier the file was written for.

        The list is populated as a side effect of :meth:`fetch_all_issues` (or
        any method that calls ``_read_records``).  Call this after any fetch to
        surface corrupt file alerts before dispatching work.
        """
        # Ensure the cache is populated (which also populates _corrupt_stubs).
        self._read_records()
        with self._read_cache_guard:
            stubs = self._corrupt_stubs
        return list(stubs) if stubs is not None else []

    # ------------------------------------------------------------------
    # Import index: maps external GitHub issue IDs to native task IDs.
    # This lightweight index file survives task-file corruption so intake
    # can detect reimport attempts even when the task file is unreadable.
    # ------------------------------------------------------------------

    @property
    def _import_index_path(self) -> Path:
        return self.tasks_root / _IMPORT_INDEX_FILE

    def _read_import_index(self) -> dict[str, str]:
        """Return the ``external_id → task_id`` import index, or ``{}``."""
        path = self._import_index_path
        if not path.exists():
            return {}
        try:
            raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_YAML_SAFE_LOADER)
        except (OSError, yaml.YAMLError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {str(k): str(v) for k, v in raw.items() if k and v}

    def record_external_import(self, external_id: str, task_id: str) -> None:
        """Record that *external_id* has been imported as native task *task_id*.

        The mapping is persisted to the import index file so that even if the
        native task file later becomes corrupt or unreadable, intake can detect
        the prior import and avoid creating a duplicate.
        """
        eid = str(external_id or "").strip()
        tid = str(task_id or "").strip()
        if not eid or not tid:
            return
        with self._write_lock:
            index = self._read_import_index()
            if index.get(eid) == tid:
                return  # Already recorded — nothing to do.
            self._assert_task_writes_allowed()
            index[eid] = tid
            payload = yaml.safe_dump(dict(sorted(index.items())), allow_unicode=False)
            try:
                _atomic_write(self._import_index_path, payload)
            except OSError as exc:
                logger.warning(
                    "github_intake: failed to write import index for %s→%s: %s",
                    eid, tid, exc,
                )

    def find_imported_task_id_for_external(self, external_id: str) -> str | None:
        """Return the task ID previously recorded for *external_id*, or ``None``."""
        eid = str(external_id or "").strip()
        if not eid:
            return None
        return self._read_import_index().get(eid)

    def _apply_field(
        self,
        meta: dict[str, Any],
        body: str,
        key: str,
        value: Any,
    ) -> str:
        key_norm = key.replace("_", "-")
        if key_norm == "status":
            meta["status"] = canonicalize_status(str(value))
        elif key_norm == "title":
            meta["title"] = str(value)
        elif key_norm in ("description", "desc"):
            body = _replace_section(
                body, "Summary", _summary_safe_description(str(value))
            )
        elif key_norm == "priority":
            meta["priority"] = normalize_priority_int(value)
        elif key_norm == "assignee":
            meta["assignee"] = str(value) if value is not None else None
        elif key_norm in ("label", "labels"):
            meta["labels"] = _dedupe_strings(_string_list(value))
        elif key_norm == "add-label":
            meta["labels"] = _dedupe_strings(_string_list(meta.get("labels")) + [value])
        elif key_norm == "remove-label":
            remove = str(value).strip().lower()
            meta["labels"] = [
                label
                for label in _string_list(meta.get("labels"))
                if label.strip().lower() != remove
            ]
        elif key_norm == "parent":
            meta["parent"] = str(value) if value else None
        elif key_norm in ("type", "issue-type"):
            issue_type = str(value or "task").strip().lower()
            meta["type"] = issue_type if issue_type in _ISSUE_TYPES else "task"
        elif key_norm == "target-branch":
            meta["target_branch"] = str(value) if value else None
            meta["oompah.target_branch"] = str(value) if value else None
        elif key_norm == "work-branch":
            meta["work_branch"] = str(value) if value else None
            meta["oompah.work_branch"] = str(value) if value else None
        elif key_norm == "review-url":
            meta["review_url"] = str(value) if value else None
            meta["oompah.review_url"] = str(value) if value else None
        elif key_norm == "review-number":
            meta["review_number"] = str(value) if value else None
            meta["oompah.review_number"] = str(value) if value else None
        elif key_norm == "review-head":
            meta["review_head"] = str(value) if value else None
            meta["oompah.review_head"] = str(value) if value else None
        elif str(key).startswith("oompah."):
            meta[str(key)] = value
            compat_key = str(key).removeprefix("oompah.")
            if compat_key in {
                "work_branch",
                "target_branch",
                "review_url",
                "review_number",
                "review_head",
                "merged_at",
            }:
                meta[compat_key] = value
        else:
            logger.debug("oompah_md update_issue ignoring unsupported field %s", key)
        return body

    def _normalize_record(self, rec: dict[str, Any]) -> Issue:
        meta = rec["meta"]
        identifier = str(meta.get("id") or Path(rec["path"]).stem)
        state = canonicalize_status(str(meta.get("status") or BACKLOG))
        labels = _string_list(meta.get("labels"))
        priority = normalize_priority_int(meta.get("priority"))
        blocked_ids = _string_list(meta.get("blocked_by") or meta.get("dependencies"))
        start_blocked_ids = _string_list(
            meta.get("start_blocked_by") or meta.get("oompah.start_blocked_by")
        )
        created_at = _parse_utc(meta.get("created_at") or meta.get("created_date"))
        updated_at = _parse_utc(meta.get("updated_at") or meta.get("updated_date"))
        closed_at = updated_at if status_key(state) in {
            status_key(s) for s in self.terminal_states + [MERGED, ARCHIVED]
        } else None
        body = str(rec["body"])
        description = _section(body, "Summary")
        issue_type = str(meta.get("type") or "task").strip().lower()
        if issue_type not in _ISSUE_TYPES:
            issue_type = "task"
        attachments = []
        for entry in meta.get("oompah.attachments") or []:
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                attachments.append(entry["path"])
            elif isinstance(entry, str):
                attachments.append(entry)
        external_github = meta.get("oompah.external.github")
        if not isinstance(external_github, dict):
            external_github = {}
        external_number = external_github.get("number")
        return Issue(
            id=identifier,
            identifier=identifier,
            title=str(meta.get("title") or identifier),
            description=description,
            priority=priority,
            state=state,
            lifecycle_revision=(
                meta.get("oompah.lifecycle_revision")
                if isinstance(meta.get("oompah.lifecycle_revision"), int)
                and not isinstance(meta.get("oompah.lifecycle_revision"), bool)
                else None
            ),
            branch_name=_sanitize_identifier(identifier),
            target_branch=_optional_str(
                meta.get("target_branch") or meta.get("oompah.target_branch")
            ),
            backports=meta.get("oompah.backports"),
            backport_of=meta.get("oompah.backport_of"),
            release_pick_metadata_loaded=True,
            issue_type=issue_type,
            parent_id=_optional_str(meta.get("parent") or meta.get("parent_task_id")),
            labels=[label.lower() for label in labels],
            blocked_by=[BlockerRef(id=dep, identifier=dep) for dep in blocked_ids],
            start_blocked_by=[
                BlockerRef(id=dep, identifier=dep) for dep in start_blocked_ids
            ],
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            attachments=attachments,
            intake=meta.get("oompah.intake") if isinstance(meta.get("oompah.intake"), dict) else None,
            duplicate_screening=(
                meta.get("oompah.duplicate_screening")
                if isinstance(meta.get("oompah.duplicate_screening"), dict)
                else None
            ),
            implementation_prerequisite=(
                meta.get("oompah.implementation_prerequisite")
            ),
            implementation_prerequisite_resolution=(
                meta.get("oompah.implementation_prerequisite_resolution")
            ),
            integration=parse_integration_record(meta.get("oompah.integration")),
            epic_rebase_target=(
                meta.get("oompah.epic_rebase_target")
                if isinstance(meta.get("oompah.epic_rebase_target"), dict)
                else None
            ),
            epic_rebase_authority=(
                meta.get("oompah.epic_rebase_authority")
                if isinstance(meta.get("oompah.epic_rebase_authority"), dict)
                else None
            ),
            create_once=(
                meta.get("oompah.create_once")
                if isinstance(meta.get("oompah.create_once"), dict)
                else None
            ),
            assignment_id=_optional_str(
                meta.get("agent_run_id") or meta.get("oompah.agent_run_id")
            ),
            work_branch=_optional_str(
                meta.get("work_branch") or meta.get("oompah.work_branch")
            ),
            review_url=_optional_str(
                meta.get("review_url") or meta.get("oompah.review_url")
            ),
            review_number=_optional_str(
                meta.get("review_number") or meta.get("oompah.review_number")
            ),
            review_head=_optional_str(
                meta.get("review_head") or meta.get("oompah.review_head")
            ),
            merged_at=_optional_str(
                meta.get("merged_at") or meta.get("oompah.merged_at")
            ),
            tracker_kind=TRACKER_KIND,
            tracker_owner=_optional_str(external_github.get("owner")),
            tracker_repo=_optional_str(external_github.get("repo")),
            issue_number=str(external_number) if external_number is not None else None,
            provider_url=_optional_str(external_github.get("url")),
            requestor_login=_optional_str(external_github.get("requestor_login")),
        )

    def _with_dependency_states(
        self,
        issue: Issue,
        states: dict[str, str],
    ) -> Issue:
        """Attach same-generation native status authority to dependency refs.

        A missing target deliberately remains ``None``.  The workflow fact
        collector classifies that as unavailable evidence instead of
        canonicalizing it to Backlog, while ordinary tracker consumers retain
        the unresolved identifier for repair and diagnostics.
        """

        def resolved(ref: BlockerRef) -> BlockerRef:
            identifier = str(ref.identifier or ref.id or "").strip()
            state = states.get(self._lookup_id(identifier)) if identifier else None
            return BlockerRef(id=ref.id, identifier=ref.identifier, state=state)

        issue.blocked_by = [resolved(ref) for ref in issue.blocked_by]
        issue.start_blocked_by = [
            resolved(ref) for ref in issue.start_blocked_by
        ]
        return issue

    def _read_records(self) -> list[dict[str, Any]]:
        # A status transition writes the replacement path then removes the old
        # path.  Keep enumeration and opening each enumerated path inside the
        # repository-wide mutation boundary so a reader observes one coherent
        # generation (before or after that transition), including when a
        # graceful reload has created a second tracker instance.
        with self._write_lock:
            self._recover_batch_manifest()
            generation = _repo_read_generation(self._repo_lock_key)
            with self._read_cache_guard:
                cached = self._read_cache
                cache_generation = self._read_cache_generation
            if cached is not None and cache_generation == generation:
                return cached

            missing_paths: list[Path] = []
            # The lock covers normal writers.  A separate process or a manual
            # filesystem change can still move a file after glob() returns, so
            # retry the whole authoritative status-directory scan before
            # diagnosing an ENOENT as task corruption.
            for attempt in range(2):
                records_by_id: dict[str, dict[str, Any]] = {}
                corrupt_errors: list[tuple[Path, TrackerError]] = []
                paths = (
                    sorted(self.tasks_root.glob("*/*.md"))
                    if self.tasks_root.is_dir()
                    else []
                )
                readable_stems: set[str] = set()
                missing_this_attempt: list[Path] = []
                for index, path in enumerate(paths, start=1):
                    try:
                        meta, body = _read_markdown(path)
                    except TrackerError as exc:
                        if _is_missing_task_file_error(exc):
                            missing_this_attempt.append(path)
                            continue
                        corrupt_errors.append((path, exc))
                        continue
                    readable_stems.add(path.stem)
                    record = {"path": path, "meta": meta, "body": body}
                    identifier = self._lookup_id(str(meta.get("id") or path.stem))
                    previous = records_by_id.get(identifier)
                    if previous is None:
                        records_by_id[identifier] = record
                    else:
                        # A task can be left in two status directories if concurrent
                        # writers race while moving it.  Never expose both copies to
                        # the board or scheduler: prefer the most recently updated
                        # record and leave the obsolete file for an explicit repair.
                        def recency(item: dict[str, Any]) -> tuple[datetime, str]:
                            updated = _parse_timestamp(item["meta"].get("updated_at"))
                            return (
                                updated or datetime.min.replace(tzinfo=timezone.utc),
                                str(item["path"]),
                            )

                        winner, loser = (
                            (record, previous)
                            if recency(record) > recency(previous)
                            else (previous, record)
                        )
                        records_by_id[identifier] = winner
                        logger.warning(
                            "Duplicate native oompah task ID %s at %s and %s; using %s "
                            "and ignoring %s. Repair the stale record before editing this task.",
                            identifier,
                            previous["path"],
                            record["path"],
                            winner["path"],
                            loser["path"],
                        )
                    # LibYAML and task normalization can keep this scheduler
                    # thread runnable for seconds on a large native corpus.
                    # Yield the GIL at a deterministic bounded interval so the
                    # co-resident lifecycle HTTP loop can serve health, state,
                    # and quiesce while a cold authoritative scan is active.
                    if index % _READ_CONTROL_PLANE_YIELD_INTERVAL == 0:
                        time.sleep(0)

                missing_paths.extend(missing_this_attempt)
                if missing_this_attempt and attempt == 0:
                    continue

                # An ENOENT that resolves to a readable copy with the same
                # filename in another canonical status directory was an atomic
                # status-file move, not corruption.  A missing stem after the
                # refresh is a real disappearance and must remain actionable.
                for path in missing_paths:
                    if path.stem not in readable_stems:
                        corrupt_errors.append(
                            (
                                path,
                                TrackerError(
                                    "Native task file disappeared while it was being read"
                                ),
                            )
                        )

                corrupt_stubs: list[dict[str, Any]] = []
                for path, exc in corrupt_errors:
                    logger.warning(
                        "Corrupt native oompah task %s: %s — "
                        "the scheduler will not dispatch this task until it is repaired. "
                        "Restore the file from a backup or git history "
                        "(e.g. `git show HEAD:.oompah/tasks/%s/%s.md > %s`).",
                        path,
                        exc,
                        path.parent.name,
                        path.stem,
                        path,
                    )
                    corrupt_stubs.append({"path": path, "stem": path.stem})

                records = list(records_by_id.values())
                status_by_id = {
                    identifier: canonicalize_status(
                        str(record["meta"].get("status") or BACKLOG)
                    )
                    for identifier, record in records_by_id.items()
                }
                with self._read_cache_guard:
                    self._read_cache = records
                    self._read_cache_by_id = dict(records_by_id)
                    self._read_cache_status_by_id = status_by_id
                    self._read_cache_generation = generation
                    self._corrupt_stubs = corrupt_stubs
                return records

        raise AssertionError("native task read retry loop did not return")

    def _read_record(self, identifier: str) -> dict[str, Any] | None:
        needle = self._lookup_id(identifier)
        records = self._read_records()
        with self._read_cache_guard:
            index = self._read_cache_by_id
            if index is not None:
                return index.get(needle)
        # Invalidation may race after _read_records() returns its coherent
        # snapshot and before the cache guard above.  That snapshot remains a
        # valid linearization point; search it rather than manufacturing a
        # false missing task from the deliberately cleared shared index.
        for record in records:
            task_id = str(
                record["meta"].get("id") or Path(record["path"]).stem
            )
            if self._lookup_id(task_id) == needle:
                return record
        return None

    def _read_record_uncached(self, identifier: str) -> dict[str, Any] | None:
        # Writers already hold the repository mutation lock. They need a
        # fresh local read before applying a change, but this read-side cache
        # clear is not tracker authority and must not advance the shared
        # generation or emit a phantom unscoped mutation.
        self._clear_read_cache_local()
        return self._read_record(identifier)

    def _lookup_id(self, identifier: str) -> str:
        return str(identifier or "").strip().lower()

    def _initial_body(self, description: str | None) -> str:
        summary = _summary_safe_description(description)
        return (
            f"## Summary\n\n{summary}\n\n"
            "## Acceptance Criteria\n\n"
            "- [ ] Define acceptance criteria.\n\n"
            "## Notes\n\n"
        )

    def _path_for(self, identifier: str, status: str) -> Path:
        return self.tasks_root / _status_dir(status) / f"{_safe_id(identifier)}.md"

    def _task_prefix(self) -> str:
        config_path = self.tasks_root / "config.yml"
        if config_path.exists():
            try:
                data = yaml.load(config_path.read_text(encoding="utf-8"), Loader=_YAML_SAFE_LOADER)
            except (OSError, yaml.YAMLError):
                data = {}
            if isinstance(data, dict):
                prefix = str(data.get("task_prefix") or data.get("taskPrefix") or "").strip()
                if prefix:
                    return _safe_id(prefix).upper()
        repo_name = _safe_id(self._root.name).upper()
        return repo_name or DEFAULT_TASK_PREFIX

    def _next_identifier(self) -> str:
        prefix = self._task_prefix()
        max_seen = 0
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.I)
        # Check valid records (parsed front matter).
        for rec in self._read_records():
            match = pattern.match(str(rec["meta"].get("id") or ""))
            if match:
                max_seen = max(max_seen, int(match.group(1)))
        # Also scan ALL .md file stems — including corrupt/unreadable files —
        # so that a corrupted task file cannot cause its ID to be recycled for
        # a brand-new task.  This is the primary guard against the TRICKLE-8
        # failure mode where a zero-byte in-progress file was invisible to the
        # valid-record scan and its ID was reused for a fresh Proposed import.
        if self.tasks_root.is_dir():
            for path in self.tasks_root.glob("*/*.md"):
                stem_match = pattern.match(path.stem)
                if stem_match:
                    max_seen = max(max_seen, int(stem_match.group(1)))
        return f"{prefix}-{max_seen + 1}"

    def _active_status(self) -> str:
        return self.active_states[0] if self.active_states else OPEN

    def _terminal_status(self) -> str:
        return self.terminal_states[0] if self.terminal_states else DONE

    def _add_child_to_parent(self, parent_id: str, child_id: str) -> None:
        parent = self._read_record_uncached(parent_id)
        if not parent:
            return
        meta = dict(parent["meta"])
        children = _dedupe_strings(_string_list(meta.get("children")) + [child_id])
        meta["children"] = children
        meta["updated_at"] = _now_iso()
        _write_markdown(Path(parent["path"]), meta, str(parent["body"]))

    def _git_sync_requested(self) -> bool:
        if not self.git_sync:
            return False
        raw = os.environ.get("OOMPAH_MD_TRACKER_GIT_SYNC", "1").strip().lower()
        return raw not in {"0", "false", "no", "off"}

    # ------------------------------------------------------------------
    # State-branch worktree management
    # ------------------------------------------------------------------

    def _state_worktree_path(self) -> Path:
        """Return the deterministic filesystem path for the state-branch worktree.

        The worktree is placed inside the git common directory (the ``.git``
        directory of the main checkout, which is shared across all worktrees
        of the same repository).  Using the common directory ensures that the
        worktree registration is visible to all git operations on this repo,
        and that the worktree is NOT tracked by the repository itself.

        Branch name slashes are replaced with ``__`` to produce a valid
        directory name; e.g. ``oompah/state/proj-abc`` →
        ``oompah__state__proj-abc``.
        """
        assert self.state_branch_name
        safe_name = self.state_branch_name.replace("/", "__").replace("\\", "__")
        result = self._git(["rev-parse", "--git-common-dir"], check=False)
        if result.returncode == 0:
            git_common_dir = Path(result.stdout.strip())
            if not git_common_dir.is_absolute():
                git_common_dir = (self._root / git_common_dir).resolve()
        else:
            # Not inside a git repo — fall back to a sibling of .git
            git_common_dir = self._root / ".git"
        return git_common_dir / "oompah-state-worktrees" / safe_name

    def _get_state_root(self) -> Path:
        """Return the state-branch worktree path, creating the worktree if needed.

        The first call (when ``_state_root`` is ``None``) checks that the
        configured state branch exists locally or at ``origin``, then creates
        (or reuses) a dedicated git worktree checked out on that branch.
        Subsequent calls return the cached path immediately.

        Raises :class:`TrackerError` if the state branch does not exist.
        Normal reads must NOT auto-create the state branch — that is the
        explicit bootstrap / migration flow's responsibility.
        """
        # Fast path: already initialised.
        with self._state_worktree_lock:
            if self._state_root is not None:
                return self._state_root

            branch_name = self.state_branch_name
            assert branch_name  # guarded by __init__

            # Check that the state branch exists (locally or at origin).
            local_ok = (
                self._git(
                    ["rev-parse", "--verify", branch_name], check=False
                ).returncode == 0
            )
            remote_ok = (
                self._git(
                    ["rev-parse", "--verify", f"refs/remotes/origin/{branch_name}"],
                    check=False,
                ).returncode == 0
            )
            if not local_ok and not remote_ok:
                raise StateBranchMissingError(
                    f"State branch {branch_name!r} does not exist locally or at "
                    f"origin/{branch_name!r}. "
                    f"Run the bootstrap or migration flow to create it before "
                    f"enabling state_branch_enabled=True for this project. "
                    f"Normal tracker reads must not create remote branches."
                )

            wt_path = self._state_worktree_path()

            # Check if a worktree is already registered at this path.
            wt_list = self._git(["worktree", "list", "--porcelain"], check=False)
            registered = set()
            if wt_list.returncode == 0:
                for line in wt_list.stdout.splitlines():
                    if line.startswith("worktree "):
                        registered.add(Path(line.split(" ", 1)[1].strip()).resolve())

            if wt_path.resolve() in registered:
                # Worktree already exists and is registered — use it.
                pass
            else:
                if wt_path.exists():
                    # Path exists but is NOT registered — prune stale metadata
                    # then remove the orphaned directory so we can re-create it.
                    self._git(["worktree", "prune"], check=False)
                    # Check again after prune
                    wt_list2 = self._git(
                        ["worktree", "list", "--porcelain"], check=False
                    )
                    registered2: set[Path] = set()
                    if wt_list2.returncode == 0:
                        for line2 in wt_list2.stdout.splitlines():
                            if line2.startswith("worktree "):
                                registered2.add(
                                    Path(line2.split(" ", 1)[1].strip()).resolve()
                                )
                    if wt_path.resolve() not in registered2:
                        import shutil
                        shutil.rmtree(str(wt_path), ignore_errors=True)
                # Create the worktree.
                wt_path.parent.mkdir(parents=True, exist_ok=True)
                if local_ok:
                    self._git(
                        ["worktree", "add", str(wt_path), branch_name], check=True
                    )
                else:
                    # Create a local tracking branch from the remote.
                    self._git(
                        [
                            "worktree", "add", "--track",
                            "-b", branch_name,
                            str(wt_path),
                            f"origin/{branch_name}",
                        ],
                        check=True,
                    )

            self._state_root = wt_path
            return self._state_root

    def _prepare_state_branch_for_write(self) -> None:
        """Ensure the state-branch worktree is set up and synced from origin.

        Called from :meth:`_prepare_default_branch_for_write` when
        ``state_branch_enabled=True``.  Does NOT check or modify the shared
        code checkout; the worktree isolation guarantees that the two branches
        stay independent.
        """
        # Ensure the worktree is set up (raises TrackerError if branch missing).
        state_root = self._get_state_root()
        branch_name = self.state_branch_name

        # Verify the worktree is on the expected branch.
        current = self._git(
            ["symbolic-ref", "--short", "HEAD"], check=False, cwd=state_root
        )
        if current.returncode == 0 and current.stdout.strip() != branch_name:
            raise TrackerError(
                f"State-branch worktree at {state_root} is not on branch "
                f"{branch_name!r}; got {current.stdout.strip()!r}. "
                f"Remove the worktree directory and let the tracker recreate it."
            )

        # Sync once per tracker configuration generation. Repeating a remote
        # fetch before every buffered mutation serializes network latency under
        # the repository lock and can starve bounded pre-provider evidence
        # writes. A successful checkpoint keeps this single-writer clone
        # current; any unexpected remote advance is handled by the existing
        # push-rejection fetch/rebase path.
        if self._has_remote("origin") and not self._state_branch_write_synced:
            self._sync_state_branch_from_remote()
            self._state_branch_write_synced = True

    def _sync_state_branch_from_remote(self) -> None:
        """Fetch and fast-forward the state branch worktree from origin.

        Uses the same non-destructive recovery strategy as
        :meth:`_sync_from_remote`: prefer ``--ff-only``; fall back to
        ``rebase --autostash``; never use ``reset --hard``.

        Raises :class:`TrackerError` with an actionable message when both
        recovery paths fail.
        """
        branch_name = self.state_branch_name
        assert branch_name
        state_root = self._get_state_root()

        fetch = self._git(["fetch", "origin", branch_name], check=False)
        if fetch.returncode != 0:
            fetch_err = fetch.stderr.strip() or fetch.stdout.strip()
            raise StateBranchFetchError(
                f"Cannot sync state branch {branch_name!r}: "
                f"git fetch origin {branch_name!r} failed: {fetch_err}. "
                f"Remediation: verify network access and remote URL "
                f"(git remote get-url origin)."
            )

        ff = self._git(
            ["merge", "--ff-only", f"origin/{branch_name}"],
            check=False,
            cwd=state_root,
        )
        if ff.returncode == 0:
            return

        # Fast-forward failed — try a non-destructive rebase.
        ff_err = ff.stderr.strip() or ff.stdout.strip()
        rebase = self._git(
            ["rebase", "--autostash", f"origin/{branch_name}"],
            check=False,
            cwd=state_root,
        )
        if rebase.returncode == 0:
            return

        # Both paths failed — abort rebase, preserve worktree, raise.
        self._git(["rebase", "--abort"], check=False, cwd=state_root)
        rebase_err = rebase.stderr.strip() or rebase.stdout.strip()
        raise TrackerError(
            f"Cannot sync state branch {branch_name!r}: "
            f"git merge --ff-only origin/{branch_name} failed: {ff_err}. "
            f"Automatic rebase --autostash origin/{branch_name} also failed: "
            f"{rebase_err}. "
            f"The state-branch worktree was preserved at {state_root}. "
            f"Remediation: resolve the conflict, then run: "
            f"git fetch origin && git rebase --autostash origin/{branch_name}"
        )

    def _commit_and_push_state_branch(self, subject: str) -> None:
        """Commit task mutations to the state-branch worktree and push.

        Runs ``git add`` and ``git commit`` inside the state-branch worktree
        so that commits land only on the state branch and never touch the
        shared code checkout.  Push target is ``origin/<state_branch_name>``.

        On a non-fast-forward push rejection, fetches the remote state branch,
        rebases local commits on top of it (never using ``reset --hard``), and
        retries the push up to ``_push_retry_count`` times with exponential
        backoff (design § 5.5).
        """
        state_root = self._get_state_root()
        branch_name = self.state_branch_name
        assert branch_name

        message = (
            f"{subject}\n\n"
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
        )
        # Even when there is no dirty task file, a predecessor may have
        # committed locally and then lost push authority.  Continue to the push
        # so a successor generation publishes that exact preserved head.
        self._stage_and_commit_state_branch(state_root, message)

        if not self._has_remote("origin"):
            return

        # Push with configurable retry + exponential backoff (design § 5.5).
        last_push_err = ""
        for attempt in range(self._push_retry_count):
            push = self._git(
                ["push", "origin", f"HEAD:{branch_name}"],
                check=False,
                cwd=state_root,
            )
            if push.returncode == 0:
                return

            last_push_err = push.stderr.strip() or push.stdout.strip()
            logger.warning(
                "State-branch push rejected (attempt %d/%d): %s",
                attempt + 1,
                self._push_retry_count,
                last_push_err,
            )

            if attempt < self._push_retry_count - 1:
                # Sync from remote before retry (fetch → rebase --autostash).
                self._sync_state_branch_from_remote()
                # Exponential backoff: base * 2^attempt (ms → s).
                backoff_s = (self._push_retry_backoff_ms * (2 ** attempt)) / 1000.0
                if backoff_s > 0:
                    time.sleep(backoff_s)

        # All retries exhausted — sync one final time and make the last attempt
        # raise TrackerError on failure.
        self._sync_state_branch_from_remote()
        self._git(
            ["push", "origin", f"HEAD:{branch_name}"],
            check=True,
            cwd=state_root,
        )

    def _stage_and_commit_state_branch(self, state_root: Path, message: str) -> bool:
        """Stage and commit state with bounded transient Git-lock recovery.

        Git's own lock files remain authoritative.  A losing writer waits for
        the lock owner and repeats the *complete* transaction, allowing the
        staged-diff check to recognize that the other writer may already have
        committed the same shared index.  Persistent contention and every
        unrelated Git failure remain fail-closed.

        Returns ``True`` when this call created a commit and ``False`` when the
        state worktree had nothing left to commit.
        """
        for attempt in range(_STATE_BRANCH_GIT_LOCK_MAX_ATTEMPTS):
            add_args = ["add", TASKS_DIR]
            add = self._git(add_args, check=False, cwd=state_root)
            if add.returncode != 0:
                detail = add.stderr.strip() or add.stdout.strip()
                error = TrackerError(f"git {' '.join(add_args)} failed: {detail}")
                if not _is_transient_state_branch_git_lock_error(detail):
                    raise error
                if attempt >= _STATE_BRANCH_GIT_LOCK_MAX_ATTEMPTS - 1:
                    raise error

                backoff_s = _STATE_BRANCH_GIT_LOCK_BACKOFF_SECONDS * (2**attempt)
                logger.info(
                    "State-branch Git lock contention; retrying stage/commit "
                    "(attempt %d/%d in %.3fs): %s",
                    attempt + 1,
                    _STATE_BRANCH_GIT_LOCK_MAX_ATTEMPTS,
                    backoff_s,
                    detail,
                )
                time.sleep(backoff_s)
                continue

            diff_args = ["diff", "--cached", "--quiet", "--", TASKS_DIR]
            diff = self._git(diff_args, check=False, cwd=state_root)
            if diff.returncode == 0:
                return False
            if diff.returncode != 1:
                detail = diff.stderr.strip() or diff.stdout.strip()
                raise TrackerError(f"git {' '.join(diff_args)} failed: {detail}")

            commit_args = ["commit", "-m", message]
            commit = self._git(commit_args, check=False, cwd=state_root)
            if commit.returncode == 0:
                return True

            commit_detail = commit.stderr.strip() or commit.stdout.strip()
            commit_error = TrackerError(
                f"git {' '.join(commit_args)} failed: {commit_detail}"
            )
            transient_lock = _is_transient_state_branch_git_lock_error(
                commit_detail
            )
            # A concurrent process can commit the shared index after this
            # transaction proves a staged task diff but before its commit
            # acquires the ref.  Git's human-facing failure output varies with
            # version, locale, hooks, and unrelated untracked files.  Re-read
            # the exact task path in the real index instead of parsing prose.
            probe = self._git(diff_args, check=False, cwd=state_root)
            if probe.returncode not in {0, 1}:
                probe_detail = probe.stderr.strip() or probe.stdout.strip()
                raise TrackerError(
                    "Cannot determine task-index ownership after failed "
                    "state-branch commit: "
                    f"git {' '.join(diff_args)} exited "
                    f"{probe.returncode}: "
                    f"{probe_detail or 'no diagnostic output'}. "
                    "Original commit failure: "
                    f"{commit_detail or 'no diagnostic output'}"
                )
            if probe.returncode == 1:
                # The intended task mutation is still staged.  Preserve every
                # non-lock failure immediately so a hook, repository,
                # identity, or storage error cannot be hidden.  A canonical
                # transient Git lock is the one exception: no competing commit
                # consumed the work, so retry the complete transaction after
                # the existing bounded backoff.
                if not transient_lock:
                    raise commit_error

            # Exit 0 proves that the staged task diff was consumed.  Exit 1 is
            # reachable here only for a canonical transient lock.  In either
            # recoverable case repeat the complete add/diff/commit transaction
            # within the existing bounded retry budget.
            if attempt >= _STATE_BRANCH_GIT_LOCK_MAX_ATTEMPTS - 1:
                raise commit_error
            backoff_s = (
                _STATE_BRANCH_GIT_LOCK_BACKOFF_SECONDS * (2**attempt)
                if transient_lock
                else 0.0
            )
            logger.info(
                "State-branch commit lost transient authority; "
                "rechecking stage/commit (attempt %d/%d%s)",
                attempt + 1,
                _STATE_BRANCH_GIT_LOCK_MAX_ATTEMPTS,
                f" in {backoff_s:.3f}s" if transient_lock else "",
            )
            if transient_lock:
                time.sleep(backoff_s)

        raise AssertionError("state-branch Git lock retry loop did not terminate")

    def _shadow_write_to_default_branch(self, subject: str) -> None:
        """Copy task files from the state-branch worktree to the default branch.

        Used during Stage A migration (``state_branch_shadow_write=True``) to
        maintain a live copy of task state on the default branch so that the
        migration can be rolled back without data loss.

        The copy is a direct file-level copy from the state-branch worktree
        into the main checkout directory.  The main checkout must be on the
        default branch; we sync from origin before committing.

        This method does NOT hold ``_write_lock`` — callers must hold it.
        """
        if not self._git_sync_requested() or not self._is_git_repo():
            return
        # Ensure main checkout is on the default branch and up-to-date.
        branch = self.default_branch or self._infer_default_branch() or "main"
        current = self._git(["symbolic-ref", "--short", "HEAD"], check=False)
        if current.returncode != 0 or current.stdout.strip() != branch:
            logger.warning(
                "Shadow write skipped: main checkout is not on %r (got %r)",
                branch,
                current.stdout.strip() if current.returncode == 0 else "<detached>",
            )
            return

        if self._has_remote("origin"):
            try:
                self._sync_from_remote(branch)
            except TrackerError as exc:
                logger.warning(
                    "Shadow write: sync from remote failed, skipping: %s", exc
                )
                return

        # Copy .oompah/tasks/ from state-branch worktree into main checkout.
        import shutil
        state_root = self._get_state_root()
        src_tasks = state_root / TASKS_DIR
        dst_tasks = self._root / TASKS_DIR
        if src_tasks.is_dir():
            dst_tasks.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(src_tasks), str(dst_tasks), dirs_exist_ok=True)

        # Stage and commit in the main checkout.
        self._git(["add", TASKS_DIR], check=True)
        diff = self._git(
            ["diff", "--cached", "--quiet", "--", TASKS_DIR], check=False
        )
        if diff.returncode == 0:
            return  # Nothing changed — no shadow commit needed.

        message = (
            f"{subject}\n\n"
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
        )
        self._git(["commit", "-m", message], check=True)

        if not self._has_remote("origin"):
            return

        push = self._git(
            ["push", "origin", f"HEAD:{branch}"], check=False
        )
        if push.returncode != 0:
            push_err = push.stderr.strip() or push.stdout.strip()
            logger.warning(
                "Shadow write: push to %r failed (non-fatal): %s", branch, push_err
            )
            # Non-fatal: the primary state-branch write succeeded; the shadow
            # write failure means rollback would need to pull from state branch.

    def _assert_task_writes_allowed(self) -> None:
        """Reject task mutations through an unscoped managed-mode tracker.

        A project with a dedicated state branch must be reached through the
        project-aware tracker factory.  The legacy/global tracker deliberately
        has no state-branch identity, so allowing it to write would put native
        task commits on whichever code checkout happens to be the service
        process working directory.

        Run this check before any task path is resolved or file is changed.
        State-branch trackers are always allowed because their task root is the
        dedicated state worktree.  Explicit legacy/standalone trackers retain
        their historical default-branch behavior.
        """
        if (
            not self.state_branch_enabled
            and not self.allow_default_branch_task_writes
        ):
            raise TrackerError(
                "Refusing an unscoped native task write on the code/default "
                "branch. Managed projects must resolve task mutations through "
                "Orchestrator._tracker_for_project(project_id) so the "
                "project's configured state branch is used."
            )

    def _assert_writer_active(self) -> None:
        """Reject mutations after this tracker generation is superseded."""

        if self._writer_retired.is_set():
            raise TrackerError(
                "Refusing native task mutation through a retired tracker "
                "configuration generation. Resolve the project tracker again "
                "and retry with its current forge credentials."
            )

    def _prepare_default_branch_for_write(self, *, task_state: bool = True) -> None:
        self._assert_writer_active()
        if task_state:
            self._assert_task_writes_allowed()
            self._recover_batch_manifest(publish=True)
        if not self._git_sync_requested() or not self._is_git_repo():
            return
        if self.state_branch_enabled:
            self._prepare_state_branch_for_write()
            return
        branch = self.default_branch or self._infer_default_branch() or "main"
        current = self._git(["symbolic-ref", "--short", "HEAD"], check=True).stdout.strip()
        if current != branch:
            raise TrackerError(
                f"Native oompah task writes must run on default branch {branch!r}; "
                f"current branch is {current!r}"
            )
        if self._has_remote("origin"):
            self._sync_from_remote(branch)

    def _sync_from_remote(self, branch: str) -> None:
        """Fetch and fast-forward the local default branch from origin.

        Prefers a deterministic fetch + ``--ff-only`` merge (safe for clean,
        up-to-date repos).  If the local branch has diverged from origin —
        most commonly because a previous ``_commit_and_push`` committed a task
        update while another writer advanced the default branch — falls back
        to ``git rebase --autostash origin/<branch>`` to place the local
        commits on top of the fetched origin tip without losing unrelated
        working-tree edits.

        The rebase fallback avoids the ``fatal: Cannot rebase onto multiple
        branches`` error that ``git pull --rebase origin <branch>`` can
        produce when git resolves the remote ref ambiguously; specifying
        ``origin/<branch>`` directly is unambiguous after the explicit fetch.

        Raises :class:`TrackerError` with an actionable remediation message
        only when both fast-forward and the non-destructive rebase recovery
        fail.  Never use ``reset --hard`` here: tracker writes must not
        discard local commits or unrelated operator edits.
        """
        fetch = self._git(["fetch", "origin", branch], check=False)
        if fetch.returncode != 0:
            fetch_err = (fetch.stderr.strip() or fetch.stdout.strip())
            raise TrackerError(
                f"Cannot sync native tracker: "
                f"git fetch origin {branch!r} failed: {fetch_err}. "
                f"Remediation: verify network access and remote URL "
                f"(git remote get-url origin)."
            )
        ff = self._git(["merge", "--ff-only", f"origin/{branch}"], check=False)
        if ff.returncode == 0:
            return
        # Fast-forward failed: the local branch has diverged (e.g. a task
        # commit was created but not pushed in a previous operation).  Try
        # rebasing local commits on top of origin so the next push can
        # succeed without creating a merge commit.
        ff_err = ff.stderr.strip() or ff.stdout.strip()
        rebase = self._git(
            ["rebase", "--autostash", f"origin/{branch}"], check=False
        )
        if rebase.returncode == 0:
            return
        # Both recovery paths failed.  Abort any in-progress rebase, but keep
        # the original branch and its working tree intact so an operator can
        # resolve the conflict without reconstructing lost tracker changes.
        self._git(["rebase", "--abort"], check=False)
        rebase_err = rebase.stderr.strip() or rebase.stdout.strip()
        raise TrackerError(
            f"Cannot sync native tracker: "
            f"git merge --ff-only origin/{branch} failed: {ff_err}. "
            f"Automatic rebase --autostash origin/{branch} also failed: {rebase_err}. "
            f"The local branch and working tree were preserved. Remediation: "
            f"resolve the rebase conflict, then run: git fetch origin && "
            f"git rebase --autostash origin/{branch}"
        )

    def _commit_and_push(self, subject: str) -> None:
        if self.state_branch_enabled and self._checkpoint_queue is not None:
            # Checkpoint coalescing mode: buffer the mutation and let the queue
            # decide when to flush (debounce timer, max-delay timer, or mandatory
            # flush).  The file was already written to the state-branch worktree
            # by the caller; we just register the pending count.
            #
            # IMPORTANT: schedule() is called BEFORE the git_sync guard so that
            # pending_mutations is accurate even in test mode (git_sync=False).
            # The actual git commit+push happens in _do_checkpoint_flush(), which
            # is called by the queue at flush time and does not require git_sync.
            self._checkpoint_queue.schedule()
            return
        if not self._git_sync_requested() or not self._is_git_repo():
            return
        if self.state_branch_enabled:
            # State branch enabled but no queue — direct commit (should not
            # normally happen; defensive fallback).
            self._commit_and_push_state_branch(subject)
            return
        self._git(["add", TASKS_DIR], check=True)
        if self._git(["diff", "--cached", "--quiet", "--", TASKS_DIR], check=False).returncode == 0:
            return
        message = (
            f"{subject}\n\n"
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
        )
        self._git(["commit", "-m", message], check=True)
        branch = self.default_branch or self._infer_default_branch() or "main"
        if not self._has_remote("origin"):
            return
        # Retry loop: attempt up to _PUSH_MAX_RETRIES total pushes.  Each rejected
        # push triggers a _sync_from_remote (fetch + ff-only or rebase) before the
        # next attempt, with a short exponential backoff to spread out concurrent
        # writers.  This replaces the previous single-retry path (OOMPAH-235) which
        # was insufficient when three or more writers raced simultaneously (OOMPAH-265).
        last_push = self._git(["push", "origin", f"HEAD:{branch}"], check=False)
        for attempt in range(1, _PUSH_MAX_RETRIES):
            if last_push.returncode == 0:
                return
            # Push was rejected — sync from remote and retry.
            if attempt > 1:
                # Exponential backoff between retries (0.1 s, 0.2 s, …) to reduce
                # thundering-herd contention when many concurrent writers race.
                time.sleep(0.1 * (2 ** (attempt - 2)))
            self._sync_from_remote(branch)
            last_push = self._git(["push", "origin", f"HEAD:{branch}"], check=False)
        if last_push.returncode == 0:
            return
        stderr = last_push.stderr.strip() or last_push.stdout.strip()
        raise TrackerError(f"git push origin HEAD:{branch} failed: {stderr}")

    def _is_git_repo(self) -> bool:
        return self._git(["rev-parse", "--is-inside-work-tree"], check=False).returncode == 0

    def _has_remote(self, name: str) -> bool:
        if name == "origin" and self._canonical_remote_url:
            return True
        return self._git(["remote", "get-url", name], check=False).returncode == 0

    def _infer_default_branch(self) -> str | None:
        result = self._git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], check=False)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        if value.startswith("origin/"):
            return value.split("/", 1)[1]
        return value or None

    def _git(
        self,
        args: list[str],
        *,
        check: bool,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command and return the completed process.

        For network operations (push, fetch, ls-remote), uses the configured
        project access token passed through an ephemeral GIT_ASKPASS environment.
        The token is never added to remote URLs or persisted in git config.

        Args:
            args: git sub-command and flags (without the ``git`` binary itself).
            check: When ``True``, raise :class:`TrackerError` if the command
                exits with a non-zero status.
            cwd: Working directory for the git command.  Defaults to
                ``self._root`` (the main project checkout).  Pass the state-
                branch worktree path to run commands inside that worktree.
        """
        effective_cwd = str(cwd) if cwd is not None else str(self._root)

        # Detect network operations that may need credentials.
        # Only push/fetch/ls-remote require authentication for private repos.
        is_network_op = (
            len(args) > 0
            and args[0] in ("push", "fetch", "ls-remote")
        )
        command_args = list(args)
        if (
            is_network_op
            and self._canonical_remote_url
            and len(command_args) > 1
            and command_args[1] == "origin"
        ):
            # Use the canonical URL as the network operand. Git's config model
            # appends command-scoped remote URLs to a repository's existing
            # values, so remote.origin.url cannot reliably replace a stale
            # first value. A direct credential-free URL is deterministic.
            command_args[1] = self._canonical_remote_url
            if command_args[0] == "fetch" and len(command_args) == 3:
                branch = command_args[2]
                command_args[2] = (
                    f"+refs/heads/{branch}:refs/remotes/origin/{branch}"
                )

        # Run git command, optionally with credential environment for network ops.
        result: subprocess.CompletedProcess[str]
        try:
            if is_network_op and self._canonical_remote_url:
                # Managed state-branch network operations are an authority
                # boundary. Ignore ambient Git control and replace origin only
                # for this child process with the project store's canonical URL.
                # This repairs stale SSH origins without persisting credentials
                # or mutating repository configuration.
                base_env = {
                    key: value
                    for key, value in os.environ.items()
                    if not key.startswith("GIT_")
                    and key not in {"SSH_ASKPASS", "LD_PRELOAD"}
                }
                base_env.update(
                    {
                        "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull,
                        "GIT_TERMINAL_PROMPT": "0",
                        "GIT_SSH_COMMAND": "ssh -F /dev/null -oBatchMode=yes",
                        "GIT_NO_REPLACE_OBJECTS": "1",
                        "GIT_OPTIONAL_LOCKS": "0",
                    }
                )
                config = [
                    ("core.hooksPath", os.devnull),
                    ("credential.helper", ""),
                    ("protocol.ext.allow", "never"),
                    ("core.sshCommand", "ssh -F /dev/null -oBatchMode=yes"),
                ]
                base_env["GIT_CONFIG_COUNT"] = str(len(config))
                for index, (key, value) in enumerate(config):
                    base_env[f"GIT_CONFIG_KEY_{index}"] = key
                    base_env[f"GIT_CONFIG_VALUE_{index}"] = value
                with git_credential_environment(
                    forge_kind=self._forge_kind,
                    access_token=self._access_token,
                    base_env=base_env,
                ) as credential_env:
                    result = subprocess.run(
                        ["git", *command_args],
                        cwd=effective_cwd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        env=credential_env,
                    )
            elif is_network_op and self._access_token:
                # Legacy callers with a credential but no managed canonical
                # remote retain their existing remote-selection behavior.
                with git_credential_environment(
                    forge_kind=self._forge_kind,
                    access_token=self._access_token,
                ) as credential_env:
                    result = subprocess.run(
                        ["git", *command_args],
                        cwd=effective_cwd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        env=credential_env,
                    )
            else:
                # No credentials needed (or no token configured) — use default env
                result = subprocess.run(
                    ["git", *command_args],
                    cwd=effective_cwd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
        except subprocess.TimeoutExpired:
            raise TrackerError(
                f"git {' '.join(args[:2])} timed out after 60s"
            )

        # Redact any token from output to prevent credential leakage.
        if self._access_token:
            result.stdout = redact_git_output(result.stdout, (self._access_token,))
            result.stderr = redact_git_output(result.stderr, (self._access_token,))

        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise TrackerError(f"git {' '.join(args)} failed: {stderr}")
        return result


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_utc(value: Any) -> datetime | None:
    parsed = _parse_timestamp(value)
    if parsed is not None and parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _oompah_md_factory(
    *,
    active_states: list[str],
    terminal_states: list[str],
    cwd: str | None = None,
    default_branch: str | None = None,
    state_branch_enabled: bool = False,
    state_branch_name: str | None = None,
    state_branch_checkpoint_debounce_ms: int = 5000,
    state_branch_checkpoint_max_delay_ms: int = 30000,
    state_branch_push_retry_count: int = 3,
    state_branch_push_retry_backoff_ms: int = 1000,
    state_branch_shadow_write: bool = False,
    allow_default_branch_task_writes: bool = True,
    access_token: str | None = None,
    forge_kind: str = "github",
    canonical_remote_url: str | None = None,
    **kwargs: Any,
) -> OompahMarkdownTracker:
    return OompahMarkdownTracker(
        active_states=active_states,
        terminal_states=terminal_states,
        cwd=cwd,
        default_branch=default_branch,
        state_branch_enabled=state_branch_enabled,
        state_branch_name=state_branch_name,
        state_branch_checkpoint_debounce_ms=state_branch_checkpoint_debounce_ms,
        state_branch_checkpoint_max_delay_ms=state_branch_checkpoint_max_delay_ms,
        state_branch_push_retry_count=state_branch_push_retry_count,
        state_branch_push_retry_backoff_ms=state_branch_push_retry_backoff_ms,
        state_branch_shadow_write=state_branch_shadow_write,
        allow_default_branch_task_writes=allow_default_branch_task_writes,
        access_token=access_token,
        forge_kind=forge_kind,
        canonical_remote_url=canonical_remote_url,
    )
