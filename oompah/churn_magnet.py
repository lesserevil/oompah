"""Churn-magnet analyzer: tracks which files cause the most merge conflicts.

Pure functions + JSON-backed store. The store persists per-project rolling-window
conflict counters to ``.oompah/churn_magnets.json``.

Design follows the yolo_watchdog.py pattern (pure state-passing functions) and the
agent_profile_store.py pattern (threading.Lock + file-backed JSON persistence).

See oompah-zlz_2-rxwe.1 for the full design.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Default path for the churn-magnet persistence file.
DEFAULT_CHURN_MAGNETS_PATH = ".oompah/churn_magnets.json"

#: Default maximum files to return from top-N query.
DEFAULT_TOP_N = 10

#: Default rolling-window size in number of conflicts. Records older than this
#: many per-file conflict events may be pruned on load and periodically.
DEFAULT_WINDOW_SIZE = 200


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChurnRecord:
    """One conflict event for a specific file.

    Attributes:
        project_id: Owning project ID.
        file_path: Repo-relative path of the conflicted file.
        timestamp: Unix timestamp of the event.
        review_id: PR/MR id during which the conflict was detected.
    """

    project_id: str
    file_path: str
    timestamp: float
    review_id: str


@dataclass
class ProjectChurnState:
    """Accumulated conflict state for one project.

    Attributes:
        project_id: Project identifier (matches key in the parent store).
        conflict_history: Chronological list of ChurnRecords (rolling window).
        file_counts: Pre-aggregated per-file conflict counts.
        total_conflicts: Total conflict events in the window.
        last_updated: Unix timestamp of the most recent update.
    """

    project_id: str
    conflict_history: list[ChurnRecord] = field(default_factory=list)
    # file_counts: path → count for fast top-N queries
    file_counts: dict[str, int] = field(default_factory=dict)
    total_conflicts: int = 0
    last_updated: float = 0.0

    def add_conflict(self, record: ChurnRecord) -> None:
        """Add a conflict record and update aggregates."""
        self.conflict_history.append(record)
        self.file_counts[record.file_path] = (
            self.file_counts.get(record.file_path, 0) + 1
        )
        self.total_conflicts += 1
        self.last_updated = record.timestamp

    def top_files(self, n: int = DEFAULT_TOP_N) -> list[tuple[str, int]]:
        """Return the top ``n`` files by conflict count, descending."""
        sorted_files = sorted(
            self.file_counts.items(),
            key=lambda kv: (-kv[1], kv[0]),  # descending count, alpha tie-break
        )
        return sorted_files[:n]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def run_git_merge_tree(
    repo_path: str,
    base_branch: str,
    head_branch: str,
    *,
    timeout_s: int = 30,
) -> tuple[list[str], str | None]:
    """Detect conflicted files by simulating a merge of ``head_branch`` into ``base_branch``.

    Uses ``git merge-base`` to find the merge base, then ``git merge-tree`` to
    perform a virtual merge without touching the working tree or index.

    Returns ``(conflicted_files, error_msg)``. ``conflicted_files`` is empty
    when there are no conflicts or on error. ``error_msg`` is non-None only
    when the subprocess failed (git not installed, path not a repo, etc.)

    Conflict detection heuristics (git 2.38+):
    - Lines starting with ``<<<<<<< <branch1>`` indicate the start of a
      conflict hunks in the output tree object listing.
    - The ``git merge-tree --write-tree`` output for each file with conflict
      markers contains ``<<<<<<< <oid>`` line.  We parse the full output
      looking for these markers followed by the file path on a subsequent line.

    Simpler alternative (used as fallback): run ``git merge-tree base head1 head2``
    and look for ``both modified`` / ``both added`` substrings in the output.
    GitLab MR merges use this format.

    Returns:
        A tuple of (list of conflicted file paths, error message or None).
    """
    if not repo_path or not os.path.isdir(repo_path):
        return [], f"repo_path {repo_path!r} is not a directory"

    if not base_branch or not head_branch:
        return [], "base_branch and head_branch must be non-empty"

    # Normalize: resolve symbolic refs and branch names to actual commit SHAs
    # so merge-tree gets stable refs even when branch names shadow each other in
    # different namespaces.
    try:
        base_sha = _resolve_ref(repo_path, base_branch)
        head_sha = _resolve_ref(repo_path, head_branch)
    except Exception as exc:
        return [], f"failed to resolve branches: {exc}"

    if not base_sha or not head_sha:
        return [], f"could not resolve one or both branch names: base={base_branch!r} head={head_branch!r}"

    # Find merge base
    try:
        result = subprocess.run(
            ["git", "merge-base", base_sha, head_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        merge_base = result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        # No common ancestor (unrelated histories) — merge-tree still works,
        # it just produces more conflicts. Use empty base.
        logger.debug(
            "git merge-base returned non-zero for %s/%s vs %s: %s",
            repo_path,
            base_branch,
            head_branch,
            exc.stderr.strip(),
        )
        merge_base = base_sha  # use base's tree as synthetic base
    except subprocess.TimeoutExpired:
        return [], "git merge-base timed out"
    except FileNotFoundError:
        return [], "git not found in PATH"

    # Run merge-tree with write-tree mode (git >= 2.38)
    # Format: merge-tree <base> <branch1> <branch2>
    try:
        result = subprocess.run(
            ["git", "merge-tree", merge_base, base_sha, head_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,  # we process conflicts regardless of return code
        )
        raw_output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return [], "git merge-tree timed out"
    except FileNotFoundError:
        return [], "git not found in PATH"
    except Exception as exc:
        return [], f"git merge-tree raised: {exc}"

    # Parse conflicted files from merge-tree output
    conflicted_files = _parse_merge_tree_conflicts(raw_output)
    return conflicted_files, None


def _resolve_ref(repo_path: str, ref: str) -> str:
    """Resolve a branch or tag name to its commit SHA."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        # Try origin/<branch> as a fallback for local-only refs that were pushed
        for prefixes in ("origin/", "heads/"):
            if ref.startswith(prefixes):
                continue
            candidate = f"origin/{ref}"
            r = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        raise ValueError(f"ref {ref!r} not found in {repo_path}")
    return result.stdout.strip()


def _looks_like_path(s: str) -> bool:
    """Heuristic: does this string look like a file path rather than content?"""
    # File paths typically contain / or a dot (extension), or start with ./
    if "/" in s or "." in s:
        return True
    # Single-word paths without extensions are ambiguous but possible
    # (e.g., "Makefile", "LICENSE", "README")
    # Be conservative — skip lines that look like content
    return False


_CONFLICT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # GitLab-style merge output: "both modified: <path>" / "both added: <path>"
    re.compile(r"^both (?:modified|added):\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    # Git merge-tree conflict marker: "<<<<<<< <oid>" followed by path on separate line
    # e.g. "<<<<<<< 7d12...abcde\nREADME.md"
    re.compile(r"^<<<<<<<\s+\S+\s*\n(.+)$", re.MULTILINE),
    # Generic conflict pattern: file appears between <<<<  and  >>>>
    re.compile(r"^(.+)$", re.MULTILINE),
)


# Patterns that indicate a conflicted file in git merge-tree output.
# "added in both", "modified in both", "deleted in both", etc.
# The file path appears on the next indented line as:
#   our    100644 <sha> <filepath>
#   their  100644 <sha> <filepath>
_CONFLICT_HEADER_RE = re.compile(
    r"^(?:added|modified|deleted|content|mode)\s+in\s+both\s*$",
    re.IGNORECASE,
)
# Also handle GitLab-style: "both modified: path" / "both added: path"
_GITLAB_STYLE_RE = re.compile(
    r"^both\s+(?:modified|added):\s*(.+)$",
    re.IGNORECASE,
)
# Parse "our/theirs  <mode> <sha> <filepath>" lines
_OUR_THEIRS_RE = re.compile(
    r"^\s*(?:our|their)\s+\d+\s+[0-9a-f]+\s+(.+)$",
)


def _parse_merge_tree_conflicts(output: str) -> list[str]:
    """Parse conflicted file paths from git merge-tree output.

    Returns a deduplicated list of repo-relative file paths that had conflicts.
    """
    if not output:
        return []
    lines = output.splitlines()
    files: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        lower = line.lower()

        # GitLab-style: "both modified: path" or "both added: path"
        m = _GITLAB_STYLE_RE.match(line)
        if m:
            path = m.group(1).strip()
            if path and path not in files:
                files.append(path)
            i += 1
            continue

        # git merge-tree "added in both" / "changed in both" / "deleted in both" /
        # "content in both" blocks list the file on the next indented lines like:
        #   our    100644 <sha> path/to/file
        #   their  100644 <sha> path/to/file
        if lower in ("added in both", "changed in both", "deleted in both",
                      "content in both", "added in both versions"):
            # Look ahead for "our" / "their" lines that carry the file path
            i += 1
            while i < len(lines):
                ahead = lines[i].strip()
                # Stop at next section header, diff markers, or empty line
                if (
                    not ahead
                    or ahead.lower() in (
                        "added in both", "changed in both",
                        "deleted in both", "content in both",
                        "added in both versions",
                    )
                    or ahead.startswith("@@")
                    or "<<" in ahead
                    or ahead == "======="
                    or ">>" in ahead
                ):
                    break
                # "our    mode sha path" / "their  mode sha path"
                if ahead.startswith("our") or ahead.startswith("their"):
                    parts = ahead.split()
                    if len(parts) >= 4:
                        fpath = parts[-1]
                        if fpath not in files:
                            files.append(fpath)
                i += 1
            continue


        # Conflict marker: line starts with <<<<<<< (variant spelling)
        if "<<<<<<" in line or lower.startswith("<<<<"):
            # The next non-empty line is typically the file path
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line:
                    # Skip oid/ref lines that often follow <<<<<<<
                    if re.match(r"^[0-9a-f]{40}\s", next_line):
                        # OID line — might be followed by path
                        pass
                    elif re.match(r"^[0-9a-f]{7,}$", next_line):
                        # Short OID — skip
                        pass
                    elif next_line.startswith("+") or next_line.startswith("-"):
                        # Diff hunk content line — skip
                        pass
                    elif next_line in ("=======", ">>>>>>>", "<<<<<<<"):
                        # Marker lines — skip
                        pass
                    elif next_line.lower() in ("changed in both versions",):
                        pass  # skip marker lines
                    elif _looks_like_path(next_line):
                        # Looks like a file path
                        if next_line not in files:
                            files.append(next_line)
                    # else: skip ambiguous lines (could be file content)
                    break
                i += 1
            i += 1
            continue

        i += 1

    return files


# ---------------------------------------------------------------------------
# JSON-backed store
# ---------------------------------------------------------------------------


class ChurnMagnetStore:
    """File-backed store for per-project conflict counters.

    Persists rolling-window conflict records to ``.oompah/churn_magnets.json``.
    Thread-safe: all read/write operations are guarded by an internal lock.

    Data shape::

        {
          "<project_id>": {
            "conflict_history": [
              {"project_id": "...", "file_path": "...", "timestamp": float, "review_id": "..."},
              ...
            ],
            "file_counts": {"path/to/file": 5, ...},
            "total_conflicts": int,
            "last_updated": float,
          },
          ...
        }
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        window_size: int = DEFAULT_WINDOW_SIZE,
    ):
        """Open (or create) the store at ``path``."""
        self.path = path or DEFAULT_CHURN_MAGNETS_PATH
        self._window_size = window_size
        self._lock = threading.Lock()
        # In-memory snapshot: project_id → ProjectChurnState
        self._projects: dict[str, ProjectChurnState] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load persisted state from JSON file."""
        if not os.path.exists(self.path):
            self._projects = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._projects = {}
            if isinstance(data, dict):
                for pid, entry in data.items():
                    if not isinstance(entry, dict):
                        continue
                    state = ProjectChurnState(
                        project_id=str(pid),
                        file_counts=entry.get("file_counts") or {},
                        total_conflicts=int(entry.get("total_conflicts") or 0),
                        last_updated=float(entry.get("last_updated") or 0),
                    )
                    history = entry.get("conflict_history") or []
                    if isinstance(history, list):
                        for rec in history:
                            if isinstance(rec, dict):
                                try:
                                    state.conflict_history.append(
                                        ChurnRecord(
                                            project_id=str(rec.get("project_id", pid)),
                                            file_path=str(rec.get("file_path", "")),
                                            timestamp=float(rec.get("timestamp", 0)),
                                            review_id=str(rec.get("review_id", "")),
                                        )
                                    )
                                except (ValueError, TypeError):
                                    continue
                    # Prune history to window size
                    if len(state.conflict_history) > self._window_size:
                        state.conflict_history = state.conflict_history[-self._window_size :]
                    self._projects[pid] = state
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load churn magnets from %s: %s", self.path, exc
            )
            self._projects = {}

    def _save(self) -> None:
        """Persist in-memory state to JSON file."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        out: dict[str, Any] = {}
        for pid, state in self._projects.items():
            out[pid] = {
                "conflict_history": [
                    {
                        "project_id": r.project_id,
                        "file_path": r.file_path,
                        "timestamp": r.timestamp,
                        "review_id": r.review_id,
                    }
                    for r in state.conflict_history
                ],
                "file_counts": dict(state.file_counts),
                "total_conflicts": state.total_conflicts,
                "last_updated": state.last_updated,
            }
        with open(self.path, "w") as f:
            json.dump(out, f, indent=2)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def list_projects(self) -> list[str]:
        """Return all project IDs that have churn data."""
        with self._lock:
            return list(self._projects.keys())

    def get_churn_state(self, project_id: str) -> ProjectChurnState | None:
        """Return the churn state for one project, or None if no data."""
        with self._lock:
            return self._projects.get(project_id)

    def get_top_files(self, project_id: str, n: int = DEFAULT_TOP_N) -> list[tuple[str, int]]:
        """Return top ``n`` files by conflict count for one project.

        Returns a list of (file_path, conflict_count) tuples ordered
        by descending count. Returns an empty list if the project has
        no conflict data.
        """
        with self._lock:
            state = self._projects.get(project_id)
            if state is None:
                return []
            return state.top_files(n)

    def get_all_top_files(
        self, n: int = DEFAULT_TOP_N
    ) -> dict[str, list[tuple[str, int]]]:
        """Return top ``n`` files per project across all tracked projects.

        Returns a dict of project_id → [(file, count), ...].
        """
        with self._lock:
            return {pid: s.top_files(n) for pid, s in self._projects.items()}

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record_conflict(
        self,
        project_id: str,
        file_path: str,
        review_id: str,
        timestamp: float | None = None,
    ) -> None:
        """Record one conflict event for a file in one project.

        Thread-safe. Persists to disk before returning.
        """
        ts = timestamp if timestamp is not None else _now()
        record = ChurnRecord(
            project_id=project_id,
            file_path=file_path,
            timestamp=ts,
            review_id=str(review_id),
        )
        with self._lock:
            if project_id not in self._projects:
                self._projects[project_id] = ProjectChurnState(project_id=project_id)
            self._projects[project_id].add_conflict(record)
            # Prune if history exceeds window size
            history = self._projects[project_id].conflict_history
            if len(history) > self._window_size:
                # Rebuild file_counts from the pruned tail
                recent = history[-self._window_size :]
                self._projects[project_id].conflict_history = list(recent)
                counts: dict[str, int] = {}
                for rec in recent:
                    counts[rec.file_path] = counts.get(rec.file_path, 0) + 1
                self._projects[project_id].file_counts = counts
            self._save()

    def record_conflicts(
        self,
        project_id: str,
        file_paths: list[str],
        review_id: str,
        timestamp: float | None = None,
    ) -> int:
        """Record multiple conflict events across file paths in one project.

        Returns the number of files recorded (len(file_paths) after dedup).
        """
        ts = timestamp if timestamp is not None else _now()
        deduped = list(dict.fromkeys(file_paths))  # preserve order, dedup
        with self._lock:
            if project_id not in self._projects:
                self._projects[project_id] = ProjectChurnState(project_id=project_id)
            for fp in deduped:
                record = ChurnRecord(
                    project_id=project_id,
                    file_path=fp,
                    timestamp=ts,
                    review_id=str(review_id),
                )
                self._projects[project_id].add_conflict(record)
            # Prune check
            history = self._projects[project_id].conflict_history
            if len(history) > self._window_size:
                recent = history[-self._window_size :]
                self._projects[project_id].conflict_history = list(recent)
                counts: dict[str, int] = {}
                for rec in recent:
                    counts[rec.file_path] = counts.get(rec.file_path, 0) + 1
                self._projects[project_id].file_counts = counts
            self._save()
        return len(deduped)

    def clear_project(self, project_id: str) -> bool:
        """Clear all churn data for one project.

        Returns True iff a record was removed.
        """
        with self._lock:
            if project_id not in self._projects:
                return False
            del self._projects[project_id]
            self._save()
        return True

    def clear_window(self, project_id: str, keep_last: int = 0) -> int:
        """Prune history to keep only the most recent ``keep_last`` records.

        Used by callers that want to enforce an aggressive rolling window
        (e.g. drop everything older than 30 days even before the
        ``window_size`` cap would trigger).

        Returns the number of records pruned.
        """
        with self._lock:
            state = self._projects.get(project_id)
            if state is None:
                return 0
            if keep_last >= len(state.conflict_history):
                return 0
            pruned = len(state.conflict_history) - keep_last
            if keep_last > 0:
                history = state.conflict_history[-keep_last:]
                state.conflict_history = list(history)
                counts: dict[str, int] = {}
                for rec in history:
                    counts[rec.file_path] = counts.get(rec.file_path, 0) + 1
                state.file_counts = counts
            else:
                state.conflict_history = []
                state.file_counts = {}
                state.total_conflicts = 0
            self._save()
            return pruned


# ---------------------------------------------------------------------------
# Module-level singleton and helpers
# ---------------------------------------------------------------------------

_store: ChurnMagnetStore | None = None
_store_lock = threading.Lock()


def _now() -> float:
    """Return current Unix timestamp (monotonic for caller use)."""
    import time
    return time.time()


def get_store(path: str | None = None) -> ChurnMagnetStore:
    """Return the module-level store singleton.

    Creates the store on first call. Subsequent calls return the same
    instance regardless of ``path`` (path is ignored after the first call).
    """
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ChurnMagnetStore(path=path or DEFAULT_CHURN_MAGNETS_PATH)
        return _store


def detect_conflicted_files(
    repo_path: str,
    base_branch: str,
    head_branch: str,
) -> list[str]:
    """Convenience wrapper: run merge-tree and return conflicted file paths.

    Returns an empty list on error (error is logged at WARNING).
    """
    files, err = run_git_merge_tree(repo_path, base_branch, head_branch)
    if err:
        logger.warning("detect_conflicted_files failed: %s", err)
    return files


def record_conflicts_for_project(
    project_id: str,
    repo_path: str,
    base_branch: str,
    head_branch: str,
    review_id: str,
) -> int:
    """Detect conflicts via merge-tree and record all conflicted files.

    Returns the number of files recorded (0 on error). Calls
    ``detect_conflicted_files`` and ``ChurnMagnetStore.record_conflicts``.
    """
    files = detect_conflicted_files(repo_path, base_branch, head_branch)
    if not files:
        return 0
    store = get_store()
    count = store.record_conflicts(
        project_id,
        files,
        review_id,
    )
    logger.info(
        "Churn magnet: recorded %d conflicted file(s) for project %s MR #%s: %s",
        count,
        project_id,
        review_id,
        ", ".join(files[:5]) + (" ..." if len(files) > 5 else ""),
    )
    return count