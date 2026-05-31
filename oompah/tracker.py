"""Issue tracker client using beads (bd) for oompah."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

from oompah.models import BlockerRef, Issue

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_identifier(identifier: str) -> str:
    """Replace any character not in [A-Za-z0-9._-] with underscore.

    This mirrors the branch-name sanitization done in projects.py so that
    the normalized Issue.branch_name matches the actual git worktree branch.
    """
    return _SAFE_CHARS.sub("_", identifier)


logger = logging.getLogger(__name__)

# Default status for newly created issues.  Beads CLI defaults to "open",
# but oompah wants new issues to land in the backlog ("deferred") so they
# are triaged before the orchestrator picks them up.
DEFAULT_INITIAL_STATUS = "deferred"

# How long to short-circuit ``_run_bd`` after we discover a project's beads
# DB is missing. Without this, every poll tick spends 5+ subprocess calls
# (~150ms each) hitting the same "no beads database found" failure.
_MISSING_DB_TTL_SECONDS = 60.0

# Safety-net TTL for the Dolt-unavailable cache. 60s matches the missing-DB
# cache so they share the same sampling cadence; the server is typically
# healthy again within one full-sync interval.
_DOLT_UNAVAILABLE_TTL_SECONDS = 60.0

# Default subprocess timeout for ``bd`` commands. Beads is backed by Dolt
# and a fresh sql-server start, a large issues table, or contention can push
# even simple ``bd list`` calls past 30s. The previous 30s default surfaced
# as auto-filed "[backend:tracker] bd command timed out" bug beads on every
# slow tick (see oompah-zlz_2-3xm). 60s gives Dolt time to respond before we
# treat the call as failed; override via OOMPAH_BD_TIMEOUT_SECONDS.
_DEFAULT_BD_TIMEOUT_SECONDS = 60.0
_DEFAULT_BACKLOG_TIMEOUT_SECONDS = 60.0

_BACKLOG_PRIORITY_TO_INT = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "normal": 2,
    "low": 3,
    "backlog": 4,
}
_INT_TO_BACKLOG_PRIORITY = {
    0: "high",
    1: "high",
    2: "medium",
    3: "low",
    4: "low",
}


def _resolve_bd_timeout() -> float:
    """Read the bd subprocess timeout from env, falling back to the default.

    Resolved at call time (not import time) so tests and live config
    changes are respected without restarting the process.
    """
    raw = os.environ.get("OOMPAH_BD_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return _DEFAULT_BD_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid OOMPAH_BD_TIMEOUT_SECONDS=%r — using default %ss",
            raw,
            _DEFAULT_BD_TIMEOUT_SECONDS,
        )
        return _DEFAULT_BD_TIMEOUT_SECONDS
    if value <= 0:
        logger.warning(
            "OOMPAH_BD_TIMEOUT_SECONDS=%r must be > 0 — using default %ss",
            raw,
            _DEFAULT_BD_TIMEOUT_SECONDS,
        )
        return _DEFAULT_BD_TIMEOUT_SECONDS
    return value


def _resolve_backlog_timeout() -> float:
    """Read the Backlog.md subprocess timeout from env."""
    raw = os.environ.get("OOMPAH_BACKLOG_MD_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return _DEFAULT_BACKLOG_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid OOMPAH_BACKLOG_MD_TIMEOUT_SECONDS=%r — using default %ss",
            raw, _DEFAULT_BACKLOG_TIMEOUT_SECONDS,
        )
        return _DEFAULT_BACKLOG_TIMEOUT_SECONDS
    if value <= 0:
        logger.warning(
            "OOMPAH_BACKLOG_MD_TIMEOUT_SECONDS=%r must be > 0 — using default %ss",
            raw, _DEFAULT_BACKLOG_TIMEOUT_SECONDS,
        )
        return _DEFAULT_BACKLOG_TIMEOUT_SECONDS
    return value


def _sort_issues_for_dispatch(issues: list[Issue]) -> list[Issue]:
    """Sort issues by priority, creation time, and identifier."""
    def sort_key(issue: Issue):
        pri = issue.priority if issue.priority is not None else 999
        created = issue.created_at or datetime.max.replace(tzinfo=timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (pri, created, issue.identifier)

    return sorted(issues, key=sort_key)


class TrackerError(Exception):
    """Raised when tracker operations fail."""


class TrackerNotConfiguredError(TrackerError):
    """Raised when the project's tracker store is missing or uninitialized.

    For BeadsTracker this means ``bd`` ran successfully but reported
    "no beads database found" in the configured workspace. The condition
    is environmental (someone needs to ``bd init`` or remove the project)
    rather than a transient failure, so callers should treat it as a
    persistent state and back off rather than retry every tick.
    """


class TrackerTimeoutError(TrackerError):
    """Raised when a ``bd`` subprocess exceeds its timeout.

    Treated as transient/environmental (busy DB, slow disk, large dump)
    rather than a bug in the codebase. Callers should log at WARNING and
    let the next poll tick retry; the error_watcher only escalates ERROR
    records into fresh bug beads, so demoting the level here prevents the
    flood of duplicate "bd command timed out" beads we used to see.
    """


class TrackerDoltUnavailableError(TrackerError):
    """Raised when the Dolt SQL server is unreachable, failed to start, or the expected database is missing.

    This covers the transient case where ``bd``'s auto-started Dolt server
    either fails to bind a port or doesn't become ready within the health-
    check timeout (typically 10s). On the next poll tick the server may
    already be up and responding normally — treating it as a real bug
    that warrants auto-filed beads causes duplicate noise in the queue.

    This also covers the case where the server IS reachable but serving
    a different data directory than expected (e.g. after a branch switch)
    so database "X" is not found on the server. The server is healthy but
    the expected database is absent — same transient recovery path.

    The error messages from ``bd`` look like::

        failed to open database: Dolt server unreachable at 127.0.0.1:0
        and auto-start failed: server started (PID N) but not accepting
        connections on port M: timeout after 10s waiting for server at
        127.0.0.1:M

        failed to open database: database "oompah" not found on Dolt
        server at 127.0.0.1:41749

    Callers should log at WARNING and let the next poll tick retry.
    See oompah-zlz_2-tjyj, oompah-zlz_2-yvur.
    """


class BeadsTracker:
    """Issue tracker client backed by the bd (beads) CLI."""

    def __init__(
        self,
        active_states: list[str],
        terminal_states: list[str],
        cwd: str | None = None,
    ):
        self.active_states = [s.strip().lower() for s in active_states]
        self.terminal_states = [s.strip().lower() for s in terminal_states]
        self.cwd = cwd
        # Last-known fingerprint for change detection.
        # None means "never polled" — first call to has_changed() always
        # returns True.
        self._last_fingerprint: str | None = None
        # When ``bd`` reports the workspace has no beads DB we set this
        # to monotonic_time + TTL so subsequent calls short-circuit
        # without spawning subprocesses (and without spamming logs).
        self._missing_db_until: float = 0.0
        # When ``bd`` fails because the Dolt SQL server is unreachable
        # or failed to start (transient startup/port-binding failure),
        # we set this to monotonic_time + TTL so subsequent calls
        # short-circuit without hammering an already-strained server.
        self._dolt_unavailable_until: float = 0.0

    def fetch_candidate_issues(self) -> list[Issue]:
        """Fetch issues in active states, sorted for dispatch.

        Uses a single ``bd list --status=<comma-list> --limit=0 --json``
        call to retrieve every issue in any of the configured active
        states. The comma-separated ``--status`` form has been supported
        by ``bd`` since well before 1.0; ``--limit=0`` disables the
        default 50-issue cap so projects with large backlogs aren't
        silently truncated.

        Previously this method looped per-status and, on any
        ``TrackerError``, fell back to ``bd list --json`` (no filter,
        no ``--limit``). That fallback returned the entire database and
        ran once per active status, which under dolt-sql-server
        contention regularly tripped the 30s subprocess timeout
        (see oompah-zlz_2-k5a). The fallback was load-bearing only for
        legacy bd builds that didn't recognise ``--status``; modern bd
        does, so we drop it and propagate errors directly.
        """
        if not self.active_states:
            return []

        status_filter = ",".join(self.active_states)
        try:
            raw_list = self._run_bd(
                [
                    "list",
                    # ``--all`` is needed alongside ``--status=`` because
                    # ``bd list --status=open`` (without --all) applies an
                    # additional hooked/worktree-aware filter that hides
                    # issues with an active local worktree under
                    # ``.oompah/worktrees/``. We need the full set of
                    # active issues for dispatch. See oompah-zlz_2-???
                    # for the upstream bd bug (oompah-zlz_2-7q55).
                    "--all",
                    f"--status={status_filter}",
                    "--limit=0",
                    "--json",
                ]
            )
        except TrackerNotConfiguredError:
            # Already logged at WARNING in _run_bd; bubble up so the
            # caller skips this project's dispatch for the tick.
            raise
        except TrackerTimeoutError as exc:
            # Transient/environmental (busy DB, slow disk, large dump) —
            # log at WARNING so the error_watcher does NOT auto-file a
            # duplicate bug bead every poll tick. Re-raise so the
            # orchestrator skips this project for the tick.
            logger.warning("Failed to fetch candidates: %s", exc)
            raise
        except TrackerDoltUnavailableError as exc:
            # Transient: Dolt server is down/unavailable.  Log at WARNING
            # so the error_watcher does NOT auto-file a duplicate bead
            # every poll tick.  Re-raise so the orchestrator skips this
            # project for the tick.
            logger.warning("Failed to fetch candidates: %s", exc)
            raise
        except TrackerError as exc:
            logger.error(
                "Failed to fetch candidates: %s",
                exc,
                extra={"error_class": "bd_failed"},
            )
            raise

        issues: list[Issue] = []
        seen_ids: set[str] = set()
        if isinstance(raw_list, list):
            for raw in raw_list:
                issue = self._normalize_issue(raw)
                if issue.id in seen_ids:
                    continue
                state_norm = issue.state.strip().lower()
                if state_norm in self.active_states:
                    issues.append(issue)
                    seen_ids.add(issue.id)

        return _sort_issues_for_dispatch(issues)

    def fetch_all_issues(self) -> list[Issue]:
        """Fetch all issues regardless of state."""
        # Try --all first (single call), fall back to per-status queries
        try:
            result = self._run_bd(["list", "--all", "--json"])
            if isinstance(result, list) and result:
                seen: set[str] = set()
                issues: list[Issue] = []
                for raw in result:
                    issue = self._normalize_issue(raw)
                    if issue.id not in seen:
                        issues.append(issue)
                        seen.add(issue.id)
                return issues
        except TrackerError:
            pass

        # Fallback: query per status
        all_raw: list[dict] = []
        for status_filter in [None, "closed", "deferred", "blocked", "pinned"]:
            try:
                args = ["list", "--json"]
                if status_filter:
                    args = ["list", f"--status={status_filter}", "--json"]
                result = self._run_bd(args)
                if isinstance(result, list):
                    all_raw.extend(result)
            except TrackerError:
                pass

        seen = set()
        issues = []
        for raw in all_raw:
            issue = self._normalize_issue(raw)
            if issue.id not in seen:
                issues.append(issue)
                seen.add(issue.id)
        return issues

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
        """Create a new issue via bd create and return the normalized Issue.

        Args:
            title: Issue title.
            issue_type: Issue type (task, bug, feature, etc.).
            description: Optional description.
            priority: Optional priority (0-4).
            initial_status: Starting status for the issue. Defaults to
                ``DEFAULT_INITIAL_STATUS`` ("deferred" / backlog).
                Pass a different value (e.g. "open") to bypass the
                backlog, which is used by workflows like merge-conflict
                resolution that need immediate dispatch.
            labels: Optional list of labels to attach at creation. Passed
                as a single comma-separated --labels argument to bd create.
            parent: Optional parent issue ID to create the new issue as a
                hierarchical child of (passed as --parent). Useful for
                filing sibling/follow-up beads under an existing epic.
        """
        args = ["create", f"--title={title}", f"--type={issue_type}", "--json"]
        if description:
            args.append(f"--description={description}")
        if priority is not None:
            args.append(f"--priority={priority}")
        if labels:
            args.append(f"--labels={','.join(labels)}")
        if parent:
            args.append(f"--parent={parent}")
        raw = self._run_bd(args)
        if isinstance(raw, dict):
            issue = self._normalize_issue(raw)
            # Move the issue to the desired initial status.
            # bd create defaults to "open"; if we want something else
            # (typically "deferred" for backlog), update it now.
            target_status = initial_status or DEFAULT_INITIAL_STATUS
            if issue.state.strip().lower() != target_status.strip().lower():
                self.update_issue(issue.identifier, status=target_status)
                issue.state = target_status
            return issue
        raise TrackerError("Unexpected response from bd create")

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Add a comment to an issue."""
        raw = self._run_bd(
            [
                "comments",
                "add",
                identifier,
                text,
                f"--author={author}",
                "--json",
            ]
        )
        if isinstance(raw, dict):
            return raw
        return {}

    def fetch_memories(self) -> dict[str, str]:
        """Fetch all stored memories from beads.

        Returns a dict of {key: insight} pairs.
        """
        try:
            raw = self._run_bd(["memories", "--json"])
            if isinstance(raw, dict):
                return raw
        except TrackerError:
            pass
        return {}

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Fetch all comments for an issue."""
        try:
            raw = self._run_bd(["comments", identifier, "--json"])
            if isinstance(raw, list):
                return raw
        except TrackerError:
            pass
        return []

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Link a child issue to a parent epic."""
        self._run_bd(["dep", "add", child_id, parent_id, "--type", "parent-child"])

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Add a blocks/blocked-by dependency between two issues."""
        self._run_bd(["dep", "add", blocked_id, blocker_id])

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Fetch a single issue with full detail including parent info."""
        try:
            raw = self._run_bd(["show", identifier, "--json"])
            if isinstance(raw, list) and raw:
                return self._normalize_issue(raw[0])
            if isinstance(raw, dict):
                return self._normalize_issue(raw)
        except TrackerError:
            pass
        return None

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Fetch children of an epic."""
        try:
            raw = self._run_bd(["show", epic_id, "--children", "--json"])
            if isinstance(raw, dict):
                # Returns {epic_id: [children...]}
                children_raw = raw.get(epic_id, [])
                return [self._normalize_issue(r) for r in children_raw]
            if isinstance(raw, list):
                return [self._normalize_issue(r) for r in raw]
        except TrackerError:
            pass
        return []

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Fetch all issues with parent info from bd show --json (parallel)."""
        all_issues = self.fetch_all_issues()
        if not all_issues:
            return []

        def _enrich_one(issue: Issue) -> Issue:
            try:
                raw = self._run_bd(["show", issue.id, "--json"])
                if isinstance(raw, list) and raw:
                    return self._normalize_issue(raw[0])
                if isinstance(raw, dict):
                    return self._normalize_issue(raw)
            except TrackerError:
                pass
            return issue

        with ThreadPoolExecutor(max_workers=min(len(all_issues), 4)) as pool:
            return list(pool.map(_enrich_one, all_issues))

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update an issue's fields via bd update."""
        args = ["update", identifier]
        for key, value in fields.items():
            args.append(f"--{key}={value}")
        self._run_bd(args)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Close an issue via bd close.

        Also removes the asking_question label if present, since closed
        issues cannot ask questions.

        Args:
            identifier: bead identifier (e.g. ``oompah-zlz_2-0nc``).
            reason: optional close reason string passed to ``bd close
                --reason``.  Used by the error_watcher to record
                "retry succeeded; transient" on auto-closed beads.
        """
        args = ["close", identifier]
        if reason:
            args.extend(["--reason", reason])
        self._run_bd(args)
        self.remove_label(identifier, "asking_question")

    def reopen_issue(self, identifier: str) -> None:
        """Reopen a closed issue by setting status to open."""
        self._run_bd(["update", identifier, "--status=open"])

    def add_label(self, identifier: str, label: str) -> None:
        """Add a label to an issue."""
        self._run_bd(["label", "add", identifier, label])

    def remove_label(self, identifier: str, label: str) -> None:
        """Remove a label from an issue."""
        try:
            self._run_bd(["label", "remove", identifier, label])
        except TrackerError:
            pass  # label may not exist

    def fetch_attachments(self, identifier: str) -> list[dict]:
        """Return the rich attachment records stored on an issue.

        Reads ``metadata["oompah.attachments"]`` from ``bd show <id>``.
        Each entry is a dict with at least ``path`` plus optional
        ``mime``/``mime_type``, ``size``, ``generated``, ``added_by``,
        ``added_at``, ``turn``, ``caption``. Returns an empty list when
        the issue has no attachments.
        """
        try:
            raw = self._run_bd(["show", identifier, "--json"])
        except TrackerError as exc:
            logger.warning("fetch_attachments failed for %s: %s", identifier, exc)
            return []
        rec = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(rec, dict):
            return []
        meta = rec.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (ValueError, TypeError):
                return []
        if not isinstance(meta, dict):
            return []
        entries = meta.get("oompah.attachments") or []
        return [e for e in entries if isinstance(e, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace the issue's ``oompah.attachments`` metadata.

        ``attachments`` is a list of attachment-record dicts (the canonical
        form is the output of :meth:`oompah.attachments.Attachment.to_dict`).
        Other metadata keys on the issue are preserved.

        When ``project_root`` is provided, also updates a sidecar manifest
        at ``<project_root>/.oompah/attachments/<identifier>/manifest.json``
        so the dashboard can render thumbnails without round-tripping
        through bd.
        """
        # Read existing metadata first so we don't clobber unrelated keys.
        try:
            raw = self._run_bd(["show", identifier, "--json"])
        except TrackerError:
            raw = None
        meta: dict = {}
        rec = raw[0] if isinstance(raw, list) and raw else raw
        if isinstance(rec, dict):
            existing = rec.get("metadata") or {}
            if isinstance(existing, str):
                try:
                    existing = json.loads(existing)
                except (ValueError, TypeError):
                    existing = {}
            if isinstance(existing, dict):
                meta = dict(existing)
        meta["oompah.attachments"] = list(attachments)
        try:
            self._run_bd(["update", identifier, "--metadata", json.dumps(meta)])
        except TrackerError as exc:
            logger.warning("set_attachments failed for %s: %s", identifier, exc)
            raise

        if project_root:
            self._write_attachments_manifest(project_root, identifier, attachments)

    @staticmethod
    def _write_attachments_manifest(
        project_root: str,
        identifier: str,
        attachments: list[dict],
    ) -> None:
        """Write the dashboard sidecar manifest. Best-effort — failures
        are logged, not raised."""
        import os
        from oompah.attachments import ATTACHMENTS_SUBDIR

        d = os.path.join(project_root, ATTACHMENTS_SUBDIR, identifier)
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(list(attachments), f, indent=2)
        except OSError as exc:
            logger.warning(
                "manifest write failed for %s in %s: %s",
                identifier,
                project_root,
                exc,
            )

    def archive_issue(self, identifier: str) -> None:
        """Mark an issue as archived via set-state dimension."""
        self._run_bd(
            [
                "set-state",
                identifier,
                "archive=yes",
                "--reason",
                "Auto-archived after 7 days closed",
            ]
        )

    def is_archived(self, issue: Issue) -> bool:
        """Check if an issue has the archive:yes label."""
        return "archive:yes" in issue.labels

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Fetch issues in specified states (used for terminal cleanup)."""
        if not state_names:
            return []

        normalized = {s.strip().lower() for s in state_names}
        try:
            raw_list = self._run_bd(["list", "--all", "--json"])
        except TrackerNotConfiguredError:
            # Already logged at WARNING in _run_bd's first hit; keep quiet
            # while the missing-DB cache holds. Behavior unchanged: callers
            # see the empty-set semantics implied by the raise.
            raise
        except TrackerError as exc:
            logger.warning("Failed to fetch issues by states: %s", exc)
            raise

        issues = []
        if isinstance(raw_list, list):
            for raw in raw_list:
                issue = self._normalize_issue(raw)
                if issue.state.strip().lower() in normalized:
                    issues.append(issue)

        return issues

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        """Fetch current state for specific issue IDs (parallel)."""
        if not issue_ids:
            return []

        def _fetch_one(issue_id: str) -> Issue | None:
            try:
                raw = self._run_bd(["show", issue_id, "--json"])
                if isinstance(raw, list) and raw:
                    return self._normalize_issue(raw[0])
                if isinstance(raw, dict):
                    return self._normalize_issue(raw)
            except TrackerError as exc:
                logger.warning(
                    "Failed to fetch issue state issue_id=%s error=%s",
                    issue_id,
                    exc,
                )
            return None

        issues: list[Issue] = []
        with ThreadPoolExecutor(max_workers=min(len(issue_ids), 4)) as pool:
            futures = {pool.submit(_fetch_one, iid): iid for iid in issue_ids}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    issues.append(result)
        return issues

    # ------------------------------------------------------------------
    # Change detection
    # ------------------------------------------------------------------

    def working_set_fingerprint(self) -> str:
        """Return a lightweight fingerprint of the tracker's current state.

        The fingerprint changes whenever the issue database is modified.
        Two strategies are tried in order:

        1. **Dolt commit hash** (``bd vc status --json``): If the tracker
           is backed by Dolt, the commit hash of the working set changes on
           every write.  This is the cheapest possible check — a single
           subprocess call returning ~50 bytes of JSON.

        2. **Status summary** (``bd status --json --no-activity``): Falls
           back to hashing the issue count summary.  This is still much
           cheaper than ``bd list`` but can miss changes that don't alter
           aggregate counts (e.g., editing a title).

        Returns a hex-digest string.  Raises ``TrackerError`` if neither
        strategy produces a usable result.
        """
        # Strategy 1: Dolt commit hash (ideal — exact change detection)
        try:
            raw = self._run_bd(["vc", "status", "--json"])
            if isinstance(raw, dict) and raw.get("commit"):
                # Include branch so switching branches is detected
                branch = raw.get("branch", "")
                commit = raw["commit"]
                return f"dolt:{branch}:{commit}"
        except TrackerError:
            logger.debug("Dolt vc status unavailable — falling back to status summary")

        # Strategy 2: Status summary hash (approximate change detection)
        try:
            raw = self._run_bd(["status", "--json", "--no-activity"])
            if isinstance(raw, dict):
                # Deterministic JSON serialization → hash
                canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
                digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
                return f"summary:{digest}"
        except TrackerError:
            pass

        raise TrackerError("Unable to compute working set fingerprint")

    def has_changed(self) -> bool:
        """Check if the working set has changed since the last call.

        Returns ``True`` if:
        - This is the first call (no prior fingerprint).
        - The fingerprint could not be computed (fail-open).
        - The fingerprint differs from the last-known value.

        Returns ``False`` only when the fingerprint matches the last-known
        value, meaning no tracker writes have occurred since the previous
        poll.

        This method is designed for use in the orchestrator's poll loop:
        call it before ``fetch_candidate_issues()`` to skip expensive
        fetches when nothing has changed.
        """
        try:
            current = self.working_set_fingerprint()
        except TrackerError:
            # Fail-open: if we can't determine the fingerprint, assume
            # something changed so the caller does the full fetch.
            logger.debug("Fingerprint unavailable — assuming changed")
            return True

        if self._last_fingerprint is None:
            # First poll — always consider changed
            self._last_fingerprint = current
            return True

        if current != self._last_fingerprint:
            logger.debug(
                "Working set changed old=%s new=%s",
                self._last_fingerprint,
                current,
            )
            self._last_fingerprint = current
            return True

        logger.debug("Working set unchanged fingerprint=%s", current)
        return False

    def reset_fingerprint(self) -> None:
        """Reset the stored fingerprint, forcing the next has_changed() to return True.

        Useful when the orchestrator wants to force a full refresh (e.g.,
        after a manual refresh request or on startup).
        """
        self._last_fingerprint = None

    @property
    def last_fingerprint(self) -> str | None:
        """The last-known fingerprint, or None if never polled."""
        return self._last_fingerprint

    def _run_bd(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
    ) -> dict | list:
        """Run a bd command and parse JSON output.

        Args:
            args: Arguments to pass after ``bd``.
            timeout: Subprocess timeout in seconds. When ``None`` (the
                default), the value is resolved via
                :func:`_resolve_bd_timeout` — which reads
                ``OOMPAH_BD_TIMEOUT_SECONDS`` and falls back to
                :data:`_DEFAULT_BD_TIMEOUT_SECONDS` (60s). Pass an
                explicit value for known-heavy commands.
        """
        # Short-circuit if a recent call already proved the DB is missing.
        if self._missing_db_until and time.monotonic() < self._missing_db_until:
            raise TrackerNotConfiguredError(
                f"bd workspace at {self.cwd!r} has no beads database "
                f"(cached for {int(self._missing_db_until - time.monotonic())}s)"
            )
        # Short-circuit if a recent call already proved the Dolt server
        # is down/unavailable (transient startup failure). Same TTL as the
        # missing-DB cache so both environmental conditions share a single
        # sampling cadence.
        if (
            self._dolt_unavailable_until
            and time.monotonic() < self._dolt_unavailable_until
        ):
            raise TrackerDoltUnavailableError(
                f"bd workspace at {self.cwd!r} has unavailable Dolt server "
                f"(cached for {int(self._dolt_unavailable_until - time.monotonic())}s)"
            )
        cmd = ["bd"] + args
        # Explicit per-call timeout wins; otherwise honour the env-var
        # (OOMPAH_BD_TIMEOUT_SECONDS) so operators can tune for slow
        # dolt-sql-server setups without code changes.
        effective_timeout = timeout if timeout is not None else _resolve_bd_timeout()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=self.cwd,
            )
        except FileNotFoundError:
            raise TrackerError("bd command not found. Is beads installed?")
        except subprocess.TimeoutExpired:
            # Use a dedicated subclass so the orchestrator and
            # fetch_candidate_issues can distinguish a transient slow-DB
            # condition from genuine tracker failures. The error_watcher
            # only auto-files beads at ERROR level; this stays at WARNING
            # to avoid a feedback loop of duplicate "bd list timed out"
            # bug beads on every slow tick.
            raise TrackerTimeoutError(f"bd command timed out: {' '.join(cmd)}")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # The most common environmental failure is a missing DB —
            # raise the specific subclass so callers can downgrade
            # log level and (importantly) not auto-file fresh bug beads
            # via the error_watcher, which only listens at ERROR.
            if "no beads database found" in stderr.lower():
                # Log once per TTL window: only when we transition from
                # "responsive" into the missing-DB cache. Subsequent calls
                # short-circuit silently above.
                logger.warning(
                    "bd workspace at %r has no beads database — "
                    "skipping for %ds. Run `bd init` there or remove the project.",
                    self.cwd,
                    int(_MISSING_DB_TTL_SECONDS),
                )
                self._missing_db_until = time.monotonic() + _MISSING_DB_TTL_SECONDS
                raise TrackerNotConfiguredError(
                    f"bd workspace at {self.cwd!r} has no beads database: "
                    f"{stderr.splitlines()[0] if stderr else ''}"
                )
            # Detect the transient "Dolt server unreachable" / auto-start
            # failure pattern.  This means the Dolt SQL server either
            # failed to bind a port or didn't become ready within the
            # health-check timeout.  On the next tick it may already be
            # up; we treat it as transient (WARNING logging, TTL cache)
            # rather than a bug that auto-files beads every poll tick.
            # See oompah-zlz_2-tjyj.
            stderr_lower = stderr.lower()
            # Also check for "database not found on Dolt server" — the
            # server is reachable but the expected DB is absent (e.g.
            # after a branch switch with mismatched data-dir). Same
            # recovery path (operator re-bootstraps or server switches
            # data-dir). Cached so we don't file duplicate beads every
            # tick during the window. See oompah-zlz_2-yvur.
            dolt_unavailable = (
                ("dolt server" in stderr_lower and "unreachable" in stderr_lower)
                or ("dolt server" in stderr_lower and "auto-start failed" in stderr_lower)
                or ("database" in stderr_lower and "not found on Dolt server" in stderr_lower)
            )
            if dolt_unavailable:
                logger.warning(
                    "bd workspace at %r has Dolt server unavailable "
                    "(transient startup/port-binding/database-missing failure) — "
                    "skipping for %ds. Server may recover automatically; "
                    "run 'bd bootstrap' if this persists (branch-switch or "
                    "stale server data-dir); "
                    "to start manually: bd dolt start; "
                    "to disable auto-start: set dolt.auto-start: false "
                    "in .beads/config.yaml",
                    self.cwd,
                    int(_DOLT_UNAVAILABLE_TTL_SECONDS),
                )
                self._dolt_unavailable_until = (
                    time.monotonic() + _DOLT_UNAVAILABLE_TTL_SECONDS
                )
                raise TrackerDoltUnavailableError(
                    f"bd workspace at {self.cwd!r} has unavailable Dolt server: "
                    f"{stderr.splitlines()[0] if stderr else ''}"
                )
            raise TrackerError(
                f"bd command failed (exit {result.returncode}): {stderr}"
            )

        # Successful call — reset the missing-DB cache in case someone
        # just ran ``bd init`` to fix the workspace.
        self._missing_db_until = 0.0
        # Also reset the Dolt-unavailable cache: if a prior call failed
        # with auto-start failure and the server is now up, we want the
        # next tick to succeed rather than keeping the short-circuit live.
        self._dolt_unavailable_until = 0.0

        stdout = result.stdout.strip()
        if not stdout:
            return []

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            # Non-JSON output (e.g. "✓ Updated issue: ...") — return empty
            # This is normal for write commands (update, close, label, etc.)
            return []

    def _normalize_issue(self, raw: dict) -> Issue:
        """Normalize a raw beads issue dict to the Issue model."""
        # Handle various beads field names
        issue_id = str(raw.get("id", raw.get("issue_id", "")))
        identifier = str(raw.get("identifier", raw.get("id", "")))
        title = str(raw.get("title", ""))
        description = raw.get("description")
        state = str(raw.get("status", raw.get("state", "open")))

        # Priority: beads uses 0-4 integers
        priority = raw.get("priority")
        if priority is not None:
            try:
                priority = int(priority)
            except (ValueError, TypeError):
                priority = None

        # Labels
        labels_raw = raw.get("labels", [])
        if isinstance(labels_raw, list):
            labels = [str(l).lower() for l in labels_raw]
        else:
            labels = []

        # Blocked by + parent (from discovered-from deps)
        blocked_by: list[BlockerRef] = []
        parent_id = raw.get("parent")  # bd list --json includes this for parent-child deps
        blockers_raw = raw.get("blocked_by", raw.get("dependencies", []))
        if isinstance(blockers_raw, list):
            for b in blockers_raw:
                if isinstance(b, dict):
                    # Skip parent-child relationships — they aren't blockers
                    dep_type = b.get("type") or b.get("dependency_type") or ""
                    if dep_type == "parent-child":
                        continue
                    # discovered-from dependencies indicate parent-child hierarchy
                    # (used by Rodgers for epic->task breakdown per AGENTS.md)
                    if dep_type == "discovered-from":
                        # Extract parent from discovered-from dependency
                        # bd list uses depends_on_id; bd show uses id/identifier
                        parent_id = (
                            b.get("depends_on_id") or b.get("id") or b.get("identifier")
                        )
                        continue
                    # bd list uses depends_on_id; bd show uses id/identifier
                    blocker_id = (
                        b.get("depends_on_id") or b.get("id") or b.get("identifier")
                    )
                    # Use the explicit identifier if available, fall back to id
                    blocker_identifier = b.get("identifier") or blocker_id
                    blocked_by.append(
                        BlockerRef(
                            id=blocker_id,
                            identifier=blocker_identifier,
                            state=b.get("state") or b.get("status"),
                        )
                    )
                elif isinstance(b, str):
                    blocked_by.append(BlockerRef(id=b, identifier=b))

        # Timestamps
        created_at = _parse_timestamp(raw.get("created_at"))
        updated_at = _parse_timestamp(raw.get("updated_at"))
        closed_at = _parse_timestamp(raw.get("closed_at"))

        issue_type = str(raw.get("issue_type", raw.get("type", "task")))

        # Multimodal attachments — beads stores the rich record in
        # metadata["oompah.attachments"] (a list of objects with path/mime/
        # size/...). Issue.attachments holds just the paths so callers
        # that only need to dispatch don't have to parse the metadata.
        attachments_paths: list[str] = []
        meta = raw.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (ValueError, TypeError):
                meta = {}
        if isinstance(meta, dict):
            entries = meta.get("oompah.attachments") or []
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and isinstance(e.get("path"), str):
                        attachments_paths.append(e["path"])
                    elif isinstance(e, str):
                        attachments_paths.append(e)

        return Issue(
            id=issue_id,
            identifier=identifier,
            title=title,
            description=description,
            priority=priority,
            state=state,
            issue_type=issue_type,
            parent_id=parent_id,
            # When branch_name is not present in bd output, derive it from the
            # identifier. This matches the branch name that projects.py uses when
            # creating the git worktree, so the WORKFLOW.md prompt renders
            # the actual branch instead of empty backticks.
            branch_name=raw.get("branch_name") or _sanitize_identifier(identifier),
            # Target branch for this issue's work. Defaults to project's default_branch
            # if not explicitly set in the bead metadata.
            target_branch=raw.get("target_branch"),
            url=raw.get("url"),
            labels=labels,
            blocked_by=blocked_by,
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            attachments=attachments_paths,
        )


class BacklogMdTracker:
    """Issue tracker client backed by Backlog.md task files and CLI writes."""

    def __init__(
        self,
        active_states: list[str],
        terminal_states: list[str],
        cwd: str | None = None,
        backlog_dir: str | None = None,
    ):
        self.active_states = [s.strip().lower() for s in active_states]
        self.terminal_states = [s.strip().lower() for s in terminal_states]
        self.cwd = cwd
        self._root = Path(cwd or os.getcwd()).resolve()
        self._configured_backlog_dir = backlog_dir
        self._last_fingerprint: str | None = None

    def fetch_candidate_issues(self) -> list[Issue]:
        """Fetch tasks in active states, sorted for dispatch."""
        if not self.active_states:
            return []
        issues = [
            issue for issue in self._read_all_tasks(include_completed=False)
            if issue.state.strip().lower() in self.active_states
        ]
        return _sort_issues_for_dispatch(issues)

    def fetch_all_issues(self) -> list[Issue]:
        """Fetch all Backlog.md tasks from active and completed folders."""
        return self._read_all_tasks(include_completed=True)

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Backlog.md task files already contain the details we need."""
        return self.fetch_all_issues()

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
        """Create a Backlog.md task and return the normalized Issue."""
        args = ["task", "create", title, "--plain"]
        if description:
            args.extend(["--description", description])
        status = self._create_status(initial_status)
        if status:
            args.extend(["--status", status])
        priority_name = _backlog_priority_name(priority)
        if priority_name:
            args.extend(["--priority", priority_name])
        effective_labels = list(labels or [])
        if issue_type and issue_type != "task" and issue_type not in effective_labels:
            effective_labels.append(issue_type)
        if effective_labels:
            args.extend(["--labels", ",".join(effective_labels)])
        if parent:
            args.extend(["--parent", parent])
        output = self._run_backlog(args)
        identifier = _parse_backlog_plain_identifier(output)
        if identifier:
            issue = self.fetch_issue_detail(identifier)
            if issue:
                return issue
        created = self._find_task_by_title(title)
        if created:
            return created
        raise TrackerError("Unexpected response from backlog task create")

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Append a comment to a Backlog.md task."""
        self._run_backlog([
            "task", "edit", identifier,
            "--comment", text,
            "--comment-author", author,
            "--plain",
        ])
        return {"author": author, "text": text}

    def fetch_memories(self) -> dict[str, str]:
        """Backlog.md has no memories equivalent."""
        return {}

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Fetch comments parsed from the task markdown file."""
        rec = self._read_task_record(identifier)
        if not rec:
            return []
        return _parse_backlog_comments(rec["body"])

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Backlog.md parent links are set through the parent flag at creation."""
        self.update_issue(child_id, parent=parent_id)

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Set the task dependency list to include blocker_id."""
        issue = self.fetch_issue_detail(blocked_id)
        existing = [b.identifier or b.id for b in (issue.blocked_by if issue else [])]
        deps = [d for d in existing if d]
        if blocker_id not in deps:
            deps.append(blocker_id)
        self._run_backlog([
            "task", "edit", blocked_id,
            "--depends-on", ",".join(deps),
            "--plain",
        ])

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Fetch a single task with full details."""
        rec = self._read_task_record(identifier)
        if not rec:
            return None
        return self._normalize_task(rec)

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Fetch child tasks that reference the given parent id."""
        needle = self._normalize_lookup_id(epic_id)
        children = []
        for rec in self._read_task_records(include_completed=True):
            parent = rec["meta"].get("parent") or rec["meta"].get("parent_task_id")
            if parent and self._normalize_lookup_id(str(parent)) == needle:
                children.append(self._normalize_task(rec))
        return _sort_issues_for_dispatch(children)

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update common Backlog.md task fields."""
        args = ["task", "edit", identifier, "--plain"]
        handled = False
        for key, value in fields.items():
            key_norm = key.replace("_", "-")
            if key_norm == "status":
                args.extend(["--status", str(value)])
                handled = True
            elif key_norm == "title":
                args.extend(["--title", str(value)])
                handled = True
            elif key_norm in ("description", "desc"):
                args.extend(["--description", str(value)])
                handled = True
            elif key_norm == "priority":
                pri = _backlog_priority_name(value)
                if pri:
                    args.extend(["--priority", pri])
                    handled = True
            elif key_norm in ("assignee", "labels", "label", "parent"):
                if key_norm == "parent":
                    self._set_frontmatter_field(identifier, "parent", str(value))
                    continue
                flag = {
                    "label": "--label",
                    "labels": "--label",
                }.get(key_norm, f"--{key_norm}")
                args.extend([flag, str(value)])
                handled = True
            else:
                logger.debug(
                    "Backlog.md update_issue ignoring unsupported field %s", key,
                )
        if handled:
            self._run_backlog(args)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Move a Backlog.md task to the configured terminal status."""
        status = self._terminal_status()
        self._run_backlog([
            "task", "edit", identifier,
            "--status", status,
            "--plain",
        ])
        if reason:
            self.add_comment(identifier, reason)
        self.remove_label(identifier, "asking_question")

    def reopen_issue(self, identifier: str) -> None:
        """Move a task back to the first configured active status."""
        self._run_backlog([
            "task", "edit", identifier,
            "--status", self._active_status(),
            "--plain",
        ])

    def add_label(self, identifier: str, label: str) -> None:
        self._run_backlog([
            "task", "edit", identifier, "--add-label", label, "--plain",
        ])

    def remove_label(self, identifier: str, label: str) -> None:
        try:
            self._run_backlog([
                "task", "edit", identifier, "--remove-label", label, "--plain",
            ])
        except TrackerError:
            pass

    def fetch_attachments(self, identifier: str) -> list[dict]:
        """Return rich attachment records from task front matter."""
        rec = self._read_task_record(identifier)
        if not rec:
            return []
        meta = rec["meta"]
        entries = (
            meta.get("oompah.attachments")
            or meta.get("oompah_attachments")
            or []
        )
        return [e for e in entries if isinstance(e, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace the task's ``oompah.attachments`` front-matter metadata."""
        path = self._task_path_for(identifier)
        if not path:
            raise TrackerError(f"Backlog.md task not found: {identifier}")
        meta, body = _read_markdown_frontmatter(path)
        meta["oompah.attachments"] = list(attachments)
        _write_markdown_frontmatter(path, meta, body)
        if project_root:
            BeadsTracker._write_attachments_manifest(
                project_root, identifier, attachments,
            )

    def archive_issue(self, identifier: str) -> None:
        self._run_backlog(["task", "archive", identifier])

    def is_archived(self, issue: Issue) -> bool:
        return "archive:yes" in issue.labels or "archived" in issue.labels

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        if not state_names:
            return []
        normalized = {s.strip().lower() for s in state_names}
        return [
            issue for issue in self._read_all_tasks(include_completed=True)
            if issue.state.strip().lower() in normalized
        ]

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        issues = []
        for issue_id in issue_ids:
            issue = self.fetch_issue_detail(issue_id)
            if issue:
                issues.append(issue)
        return issues

    def working_set_fingerprint(self) -> str:
        """Hash Backlog.md config and task-file contents."""
        backlog_dir = self._backlog_dir()
        files = []
        for candidate in [
            self._root / "backlog.config.yml",
            backlog_dir / "config.yml",
        ]:
            if candidate.exists():
                files.append(candidate)
        files.extend(self._task_files(include_completed=True))
        if not files:
            raise TrackerError("Unable to compute Backlog.md working set fingerprint")
        digest = hashlib.sha256()
        for path in sorted(files):
            rel = path.relative_to(self._root) if path.is_relative_to(self._root) else path
            digest.update(str(rel).encode())
            digest.update(b"\0")
            try:
                digest.update(path.read_bytes())
            except OSError as exc:
                raise TrackerError(f"Failed to read Backlog.md file {path}: {exc}")
            digest.update(b"\0")
        return f"backlog:{digest.hexdigest()[:16]}"

    def has_changed(self) -> bool:
        try:
            current = self.working_set_fingerprint()
        except TrackerError:
            logger.debug("Backlog.md fingerprint unavailable — assuming changed")
            return True
        if self._last_fingerprint is None:
            self._last_fingerprint = current
            return True
        if current != self._last_fingerprint:
            self._last_fingerprint = current
            return True
        return False

    def reset_fingerprint(self) -> None:
        self._last_fingerprint = None

    @property
    def last_fingerprint(self) -> str | None:
        return self._last_fingerprint

    def _read_all_tasks(self, *, include_completed: bool) -> list[Issue]:
        return [
            self._normalize_task(rec)
            for rec in self._read_task_records(include_completed=include_completed)
        ]

    def _read_task_records(self, *, include_completed: bool) -> list[dict]:
        records = []
        for path in self._task_files(include_completed=include_completed):
            try:
                meta, body = _read_markdown_frontmatter(path)
            except TrackerError as exc:
                logger.warning("Skipping invalid Backlog.md task %s: %s", path, exc)
                continue
            records.append({"path": path, "meta": meta, "body": body})
        return records

    def _read_task_record(self, identifier: str) -> dict | None:
        path = self._task_path_for(identifier)
        if not path:
            return None
        meta, body = _read_markdown_frontmatter(path)
        return {"path": path, "meta": meta, "body": body}

    def _find_task_by_title(self, title: str) -> Issue | None:
        for issue in self.fetch_all_issues():
            if issue.title == title:
                return issue
        return None

    def _set_frontmatter_field(self, identifier: str, key: str, value) -> None:
        path = self._task_path_for(identifier)
        if not path:
            raise TrackerError(f"Backlog.md task not found: {identifier}")
        meta, body = _read_markdown_frontmatter(path)
        meta[key] = value
        _write_markdown_frontmatter(path, meta, body)

    def _normalize_task(self, rec: dict) -> Issue:
        meta = rec["meta"]
        body = rec["body"]
        path = rec["path"]
        identifier = str(meta.get("id") or _id_from_task_path(path, self._task_prefix()))
        title = str(meta.get("title") or identifier)
        state = str(meta.get("status") or self._default_status())
        labels = _string_list(meta.get("labels"))
        priority = _backlog_priority_int(meta.get("priority"))
        dependencies = _string_list(meta.get("dependencies"))
        blocked_by = [
            BlockerRef(id=dep, identifier=dep)
            for dep in dependencies
        ]
        created_at = _parse_backlog_timestamp(meta.get("created_date"))
        updated_at = _parse_backlog_timestamp(meta.get("updated_date"))
        terminal = state.strip().lower() in self.terminal_states
        closed_at = updated_at if terminal else None
        parent_id = meta.get("parent") or meta.get("parent_task_id")
        attachments = []
        entries = (
            meta.get("oompah.attachments")
            or meta.get("oompah_attachments")
            or []
        )
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                    attachments.append(entry["path"])
                elif isinstance(entry, str):
                    attachments.append(entry)
        issue_type = str(meta.get("type") or _issue_type_from_labels(labels))
        return Issue(
            id=identifier,
            identifier=identifier,
            title=title,
            description=_extract_backlog_section(body, "DESCRIPTION"),
            priority=priority,
            state=state,
            branch_name=_sanitize_identifier(identifier),
            issue_type=issue_type,
            parent_id=str(parent_id) if parent_id else None,
            labels=[label.lower() for label in labels],
            blocked_by=blocked_by,
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            attachments=attachments,
        )

    def _task_path_for(self, identifier: str) -> Path | None:
        needle = self._normalize_lookup_id(identifier)
        for path in self._task_files(include_completed=True):
            try:
                meta, _body = _read_markdown_frontmatter(path)
            except TrackerError:
                continue
            task_id = str(meta.get("id") or _id_from_task_path(path, self._task_prefix()))
            if self._normalize_lookup_id(task_id) == needle:
                return path
        return None

    def _task_files(self, *, include_completed: bool) -> list[Path]:
        backlog_dir = self._backlog_dir()
        dirs = [backlog_dir / "tasks"]
        if include_completed:
            dirs.append(backlog_dir / "completed")
        files: list[Path] = []
        for directory in dirs:
            if directory.is_dir():
                files.extend(directory.glob("*.md"))
        return sorted(files)

    def _backlog_dir(self) -> Path:
        configured = (
            self._configured_backlog_dir
            or os.environ.get("OOMPAH_BACKLOG_MD_DIR")
            or os.environ.get("OOMPAH_BACKLOG_DIR")
        )
        if configured:
            path = Path(configured)
            if not path.is_absolute():
                path = self._root / path
            if path.exists():
                return path.resolve()
            raise TrackerNotConfiguredError(
                f"Backlog.md directory not found: {path}"
            )

        root_config = self._root / "backlog.config.yml"
        if root_config.exists():
            config = _read_yaml_file(root_config)
            directory = config.get("backlog_directory")
            if directory:
                path = self._root / str(directory)
                if path.exists():
                    return path.resolve()

        for name in ("backlog", ".backlog"):
            path = self._root / name
            if (path / "config.yml").exists() or (path / "tasks").exists():
                return path.resolve()

        raise TrackerNotConfiguredError(
            f"No Backlog.md project found in {self._root}. Run `backlog init`."
        )

    def _config(self) -> dict:
        backlog_dir = self._backlog_dir()
        for path in (self._root / "backlog.config.yml", backlog_dir / "config.yml"):
            if path.exists():
                return _read_yaml_file(path)
        return {}

    def _task_prefix(self) -> str:
        return str(self._config().get("task_prefix") or "task")

    def _default_status(self) -> str:
        return str(self._config().get("default_status") or "To Do")

    def _active_status(self) -> str:
        if self.active_states:
            return self._status_with_config_case(self.active_states[0])
        return self._default_status()

    def _terminal_status(self) -> str:
        if self.terminal_states:
            return self._status_with_config_case(self.terminal_states[0])
        return "Done"

    def _create_status(self, initial_status: str | None) -> str:
        if initial_status and initial_status.strip().lower() != DEFAULT_INITIAL_STATUS:
            return self._status_with_config_case(initial_status)
        return self._default_status()

    def _status_with_config_case(self, status: str) -> str:
        needle = status.strip().lower()
        statuses = self._config().get("statuses") or []
        if isinstance(statuses, list):
            for configured in statuses:
                if str(configured).strip().lower() == needle:
                    return str(configured)
        if needle == DEFAULT_INITIAL_STATUS:
            return self._default_status()
        return status

    def _normalize_lookup_id(self, identifier: str) -> str:
        value = str(identifier).strip()
        if value.isdigit():
            value = f"{self._task_prefix()}-{value}"
        return value.lower()

    def _run_backlog(
        self, args: list[str], *, timeout: float | None = None,
    ) -> str:
        """Run a backlog command and return stdout."""
        if shutil.which("backlog") is None:
            raise TrackerError("backlog command not found. Is Backlog.md installed?")
        cmd = ["backlog"] + args
        effective_timeout = (
            timeout if timeout is not None else _resolve_backlog_timeout()
        )
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(self._root),
            )
        except FileNotFoundError:
            raise TrackerError("backlog command not found. Is Backlog.md installed?")
        except subprocess.TimeoutExpired:
            raise TrackerTimeoutError(
                f"backlog command timed out: {' '.join(cmd)}"
            )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            if "no backlog.md project found" in stderr.lower():
                raise TrackerNotConfiguredError(stderr)
            raise TrackerError(
                f"backlog command failed (exit {result.returncode}): {stderr}"
            )
        return result.stdout


def _read_yaml_file(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TrackerError(f"Cannot read {path}: {exc}")
    except yaml.YAMLError as exc:
        raise TrackerError(f"Cannot parse YAML {path}: {exc}")
    return data if isinstance(data, dict) else {}


def _read_markdown_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot read {path}: {exc}")
    if not content.startswith("---\n"):
        raise TrackerError(f"Missing YAML front matter in {path}")
    end = content.find("\n---", 4)
    if end == -1:
        raise TrackerError(f"Unterminated YAML front matter in {path}")
    frontmatter = content[4:end]
    body_start = end + len("\n---")
    if content[body_start:body_start + 1] == "\n":
        body_start += 1
    try:
        meta = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        raise TrackerError(f"Cannot parse task metadata {path}: {exc}")
    if not isinstance(meta, dict):
        meta = {}
    return meta, content[body_start:]


def _write_markdown_frontmatter(path: Path, meta: dict, body: str) -> None:
    payload = yaml.safe_dump(meta, sort_keys=False, allow_unicode=False)
    try:
        path.write_text(f"---\n{payload}---\n{body}", encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot write {path}: {exc}")


def _extract_backlog_section(body: str, section: str) -> str | None:
    begin = f"<!-- SECTION:{section}:BEGIN -->"
    end = f"<!-- SECTION:{section}:END -->"
    start = body.find(begin)
    if start == -1:
        return None
    start += len(begin)
    stop = body.find(end, start)
    if stop == -1:
        return None
    return body[start:stop].strip() or None


def _parse_backlog_comments(body: str) -> list[dict]:
    comments: list[dict] = []
    pattern = re.compile(
        r"<!-- COMMENT:BEGIN -->\n(.*?)\n<!-- COMMENT:END -->",
        re.DOTALL,
    )
    for match in pattern.finditer(body):
        block = match.group(1)
        header, _, text = block.partition("\n\n")
        fields: dict[str, str] = {}
        for line in header.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        comments.append({
            "id": fields.get("index"),
            "author": fields.get("author"),
            "created_at": fields.get("created"),
            "text": text.strip(),
        })
    return comments


def _parse_backlog_plain_identifier(output: str) -> str | None:
    match = re.search(r"\bTask\s+([A-Za-z]+-\d+(?:\.\d+)*)\s+-", output)
    if match:
        return match.group(1)
    match = re.search(r"/(?:task|Task)-(\d+(?:\.\d+)*)\s+-", output)
    if match:
        return f"TASK-{match.group(1)}"
    return None


def _id_from_task_path(path: Path, prefix: str) -> str:
    match = re.match(rf"{re.escape(prefix)}-(\d+(?:\.\d+)*)\b", path.stem, re.I)
    if match:
        return f"{prefix.upper()}-{match.group(1)}"
    return path.stem


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _backlog_priority_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return _BACKLOG_PRIORITY_TO_INT.get(str(value).strip().lower())


def _backlog_priority_name(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return _INT_TO_BACKLOG_PRIORITY.get(value)
    raw = str(value).strip().lower()
    if raw.isdigit():
        return _INT_TO_BACKLOG_PRIORITY.get(int(raw))
    if raw in _BACKLOG_PRIORITY_TO_INT:
        return "medium" if raw == "normal" else raw
    return None


def _parse_backlog_timestamp(value) -> datetime | None:
    dt = _parse_timestamp(value)
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _issue_type_from_labels(labels: list[str]) -> str:
    for label in labels:
        lower = label.lower()
        if lower in {"bug", "feature", "task", "epic", "chore"}:
            return lower
    return "task"


def _parse_timestamp(value) -> datetime | None:
    """Parse an ISO-8601 timestamp string."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value)
        # Handle various ISO formats
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
