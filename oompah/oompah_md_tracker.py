"""Native oompah Markdown task tracker.

Stores canonical task state under ``.oompah/tasks`` in the managed repository.
The running oompah service is the intended writer; humans can inspect the files
directly on the project's default branch.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from oompah.checkpoint_queue import CheckpointQueue
from oompah.models import BlockerRef, Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    OPEN,
    PROPOSED,
    canonicalize_status,
    is_terminal_status,
    status_key,
)
from oompah.tracker import (
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
)

logger = logging.getLogger(__name__)

TRACKER_KIND = "oompah_md"

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
        return _repo_write_locks[repo_path]
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
    "decomposed": "decomposed",
    "duplicate candidate": "duplicate-candidate",
    "done": "done",
    "merged": "merged",
    "archived": "archived",
}
_ISSUE_TYPES = frozenset({"bug", "feature", "task", "epic", "chore"})

# Maximum number of push attempts in _commit_and_push and write_and_commit_ledger_file.
# Each failed push is followed by a _sync_from_remote + short backoff before the next
# attempt, so 3 total attempts means 2 sync+retry cycles.  Under concurrent writers
# this dramatically reduces the probability of all attempts failing (OOMPAH-265).
_PUSH_MAX_RETRIES = 3


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
        # Shared per-repo lock — all tracker instances for the same git repo
        # serialize through this lock, even across graceful reloads where
        # reload_config() clears the tracker cache and creates a new instance
        # while an in-flight write still holds the old instance's lock.
        self._write_lock = _repo_write_lock(str(self._root))
        self._read_cache: list[dict[str, Any]] | None = None
        self._corrupt_stubs: list[dict[str, Any]] | None = None
        self._read_cache_guard = threading.Lock()
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
        # Invoke the post-checkpoint callback outside the write lock to avoid
        # deadlocks when the callback tries to read tracker state.
        if callable(self._on_checkpoint_flushed):
            try:
                self._on_checkpoint_flushed()
            except Exception:  # noqa: BLE001 — callback failures must not abort the flush
                logger.exception("Error in _on_checkpoint_flushed callback")

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
            if canonicalize_status(state) != PROPOSED
        }
        issues = [
            issue
            for issue in self.fetch_all_issues()
            if status_key(issue.state) in active and issue.state != PROPOSED
        ]
        return _sort_issues_for_dispatch(issues)

    def fetch_in_progress_issues(self) -> list[Issue]:
        """Fetch tasks currently in In Progress state for orphan cleanup."""
        return self.fetch_issues_by_states([IN_PROGRESS])

    def fetch_all_issues(self) -> list[Issue]:
        return [self._normalize_record(rec) for rec in self._read_records()]

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return self.fetch_all_issues()

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        rec = self._read_record(identifier)
        return self._normalize_record(rec) if rec else None

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
        issues = []
        for issue_id in issue_ids:
            issue = self.fetch_issue_detail(issue_id)
            if issue:
                issues.append(issue)
        return issues

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
                "labels": effective_labels,
                "assignee": None,
                "created_at": now,
                "updated_at": now,
                "work_branch": None,
                "target_branch": None,
                "review_url": None,
                "review_number": None,
                "merged_at": None,
            }
            body = self._initial_body(description)
            path = self._path_for(identifier, status)
            _write_markdown(path, meta, body)
            if parent:
                self._add_child_to_parent(parent, identifier)
            self.invalidate_read_cache()
            self._commit_and_push(f"Create oompah task {identifier}")
        created = self.fetch_issue_detail(identifier)
        if not created:
            raise TrackerError(f"Created native oompah task disappeared: {identifier}")
        return created

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
            new_path = self._path_for(str(meta["id"]), new_status)
            _write_markdown(new_path, meta, body)
            if new_path != path and path.exists():
                try:
                    path.unlink()
                except OSError as exc:
                    raise TrackerError(f"Cannot remove moved native task {path}: {exc}") from exc
            self.invalidate_read_cache()
            self._commit_and_push(f"Update oompah task {meta['id']}")
        # Mandatory flush for terminal/In Review transitions (design § 5.3).
        # Called OUTSIDE _write_lock to avoid nested-lock deadlock with
        # CheckpointQueue._lock, which is acquired inside flush().
        if self._checkpoint_queue is not None and new_status != old_status:
            self._maybe_mandatory_flush(new_status)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        status = self._terminal_status()
        fields: dict[str, str] = {"status": status}
        self.update_issue(identifier, **fields)
        if reason:
            self.add_comment(identifier, reason)

    def reopen_issue(self, identifier: str) -> None:
        self.update_issue(identifier, status=self._active_status())

    def archive_issue(self, identifier: str) -> None:
        self.update_issue(identifier, status=ARCHIVED)

    def mark_needs_human(
        self,
        identifier: str,
        comment: str,
        author: str = "oompah",
    ) -> None:
        self.update_issue(identifier, status="Needs Human")
        self.add_comment(identifier, comment, author=author)

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
            self.invalidate_read_cache()
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
            self.invalidate_read_cache()
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
            self.invalidate_read_cache()
            self._commit_and_push(f"Add dependency to oompah task {meta['id']}")

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
            self.invalidate_read_cache()
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
            self.invalidate_read_cache()
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
            self.invalidate_read_cache()
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
            self._prepare_default_branch_for_write()
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

    def invalidate_read_cache(self) -> None:
        with self._read_cache_guard:
            self._read_cache = None
            self._corrupt_stubs = None

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
            body = _replace_section(body, "Summary", str(value))
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
        elif str(key).startswith("oompah."):
            meta[str(key)] = value
            compat_key = str(key).removeprefix("oompah.")
            if compat_key in {
                "work_branch",
                "target_branch",
                "review_url",
                "review_number",
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
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            attachments=attachments,
            intake=meta.get("oompah.intake") if isinstance(meta.get("oompah.intake"), dict) else None,
            work_branch=_optional_str(
                meta.get("work_branch") or meta.get("oompah.work_branch")
            ),
            review_url=_optional_str(
                meta.get("review_url") or meta.get("oompah.review_url")
            ),
            review_number=_optional_str(
                meta.get("review_number") or meta.get("oompah.review_number")
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

    def _read_records(self) -> list[dict[str, Any]]:
        with self._read_cache_guard:
            cached = self._read_cache
        if cached is not None:
            return cached
        records_by_id: dict[str, dict[str, Any]] = {}
        corrupt_stubs: list[dict[str, Any]] = []
        if self.tasks_root.is_dir():
            for path in sorted(self.tasks_root.glob("*/*.md")):
                try:
                    meta, body = _read_markdown(path)
                except TrackerError as exc:
                    logger.warning(
                        "Corrupt native oompah task %s: %s — "
                        "the scheduler will not dispatch this task until it is repaired. "
                        "Restore the file from a backup or git history "
                        "(e.g. `git show HEAD:.oompah/tasks/%s/%s.md > %s`).",
                        path, exc,
                        path.parent.name, path.stem, path,
                    )
                    corrupt_stubs.append({"path": path, "stem": path.stem})
                    continue
                record = {"path": path, "meta": meta, "body": body}
                identifier = self._lookup_id(str(meta.get("id") or path.stem))
                previous = records_by_id.get(identifier)
                if previous is None:
                    records_by_id[identifier] = record
                    continue

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

                winner, loser = (record, previous) if recency(record) > recency(previous) else (previous, record)
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
        records = list(records_by_id.values())
        with self._read_cache_guard:
            self._read_cache = records
            self._corrupt_stubs = corrupt_stubs
        return records

    def _read_record(self, identifier: str) -> dict[str, Any] | None:
        needle = self._lookup_id(identifier)
        for rec in self._read_records():
            task_id = str(rec["meta"].get("id") or Path(rec["path"]).stem)
            if self._lookup_id(task_id) == needle:
                return rec
        return None

    def _read_record_uncached(self, identifier: str) -> dict[str, Any] | None:
        self.invalidate_read_cache()
        return self._read_record(identifier)

    def _lookup_id(self, identifier: str) -> str:
        return str(identifier or "").strip().lower()

    def _initial_body(self, description: str | None) -> str:
        summary = (description or "").strip()
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

        # Sync from origin if available.
        if self._has_remote("origin"):
            self._sync_state_branch_from_remote()

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

        self._git(["add", TASKS_DIR], check=True, cwd=state_root)
        diff = self._git(
            ["diff", "--cached", "--quiet", "--", TASKS_DIR],
            check=False,
            cwd=state_root,
        )
        if diff.returncode == 0:
            return  # Nothing to commit.

        message = (
            f"{subject}\n\n"
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
        )
        self._git(["commit", "-m", message], check=True, cwd=state_root)

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

    def _prepare_default_branch_for_write(self) -> None:
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

        Args:
            args: git sub-command and flags (without the ``git`` binary itself).
            check: When ``True``, raise :class:`TrackerError` if the command
                exits with a non-zero status.
            cwd: Working directory for the git command.  Defaults to
                ``self._root`` (the main project checkout).  Pass the state-
                branch worktree path to run commands inside that worktree.
        """
        effective_cwd = str(cwd) if cwd is not None else str(self._root)
        result = subprocess.run(
            ["git", *args],
            cwd=effective_cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
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
    )
