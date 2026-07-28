"""Worker contributor provenance tracking for oompah (OOMPAH-468).

Persists compact WorkContributor records at successful worker exit so the
audit evidence collector can identify every provider/model that contributed
to a task or epic revision without relying on transient RunningEntry state.

Storage key: ``oompah.work_contributors`` in the issue's tracker metadata.

The record is intentionally minimal — it contains only safe, non-secret
identifiers needed for auditing.  Credentials, prompts, logs, and costs
are explicitly **not** stored here (those are in oompah.task_costs or the
agent log files).

Usage
-----
At worker exit (successful), the orchestrator calls
:func:`merge_contributor_records` to accumulate the new contributor into
the existing list and writes it back via the tracker protocol.

For epic audit evidence, call :func:`collect_epic_contributors` to derive
the union of contributors across the epic's own branch work plus all child
and nested-child task records whose source SHA is contained in the audited
revision.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: Tracker metadata key under which contributor lists are stored.
METADATA_KEY: str = "oompah.work_contributors"

#: Sentinel model names that indicate the model was not resolved to a
#: specific ID — SDK-managed subscription, CLI subprocess default, etc.
_UNKNOWN_MODEL_NAMES: frozenset[str] = frozenset(
    {"", "default", "cli-managed", "cli"}
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WorkContributor:
    """Compact, serialisable record for one successful worker run.

    Fields are intentionally limited to safe, non-secret identifiers.
    No credentials, prompts, cost figures, or log paths are stored.
    """

    run_id: str
    """Unique identifier for this run, derived from the agent log file
    basename without the ``.jsonl`` extension.  Falls back to
    ``<issue-identifier>__<timestamp>`` when no log path is available."""

    provider_id: str | None
    """Opaque provider identifier (e.g. ``prov-abc123``).  Set to the
    string ``"cli"`` for CLI-subprocess workers and ``"acp"`` for ACP
    runs with no explicit provider.  None means unknown."""

    provider_name: str | None
    """Human-readable provider display name (e.g. ``"Anthropic"``).
    Never contains API keys or credentials — this is the operator-chosen
    label from the provider configuration."""

    model_id: str | None
    """Resolved model identifier (e.g. ``"claude-sonnet-4-6"``).
    ``None`` when the model was SDK-managed (ACP subscription default),
    CLI-subprocess managed, or otherwise not resolvable at dispatch time.
    """

    focus: str | None
    """Focus name assigned to this run (e.g. ``"feature"``).  None if
    focus resolution was skipped or unavailable."""

    source_branch: str | None
    """Git branch the run was working on (from the issue's
    ``work_branch`` or ``branch_name`` field).  None if not set."""

    source_sha: str | None
    """Git HEAD SHA in the worker's workspace at the moment of successful
    exit.  Used by epic evidence collection to determine whether this
    contributor's commits are contained in a given audit revision.
    Empty string or None when the git repo was unavailable."""

    completed_at: str
    """ISO-8601 UTC timestamp of when the worker exited successfully."""

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON/YAML tracker metadata.

        Only the fields above are included — no credentials, prompts,
        logs, costs, or token counts.
        """
        return {
            "run_id": self.run_id,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "focus": self.focus,
            "source_branch": self.source_branch,
            "source_sha": self.source_sha,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkContributor":
        """Deserialise from a previously serialised dict.

        Unknown keys are silently ignored so older records survive schema
        additions.  Missing required fields fall back to empty/None.
        """
        return cls(
            run_id=str(d.get("run_id") or ""),
            provider_id=d.get("provider_id") or None,
            provider_name=d.get("provider_name") or None,
            model_id=d.get("model_id") or None,
            focus=d.get("focus") or None,
            source_branch=d.get("source_branch") or None,
            source_sha=d.get("source_sha") or None,
            completed_at=str(d.get("completed_at") or ""),
        )


# ---------------------------------------------------------------------------
# Record management helpers
# ---------------------------------------------------------------------------


def merge_contributor_records(
    existing: dict[str, Any] | None,
    new_contributor: WorkContributor,
) -> dict[str, Any]:
    """Accumulate *new_contributor* into the existing ``oompah.work_contributors`` dict.

    The existing ``runs`` list is preserved in full — prior contributors
    are never discarded here.  Filtering for a specific audit revision
    (e.g. "discard runs whose source_sha is not an ancestor of HEAD") is
    performed at read time by :func:`collect_epic_contributors`.

    :param existing: The current value of ``oompah.work_contributors``
        from the issue's tracker metadata, or ``None`` if not yet set.
    :param new_contributor: The new run record to append.
    :returns: Updated ``oompah.work_contributors`` dict suitable for
        passing directly to ``tracker.set_metadata_field``.
    """
    runs: list[dict[str, Any]] = []
    if existing and isinstance(existing.get("runs"), list):
        runs = list(existing["runs"])
    runs.append(new_contributor.to_dict())
    return {"runs": runs}


def load_contributors(metadata: dict[str, Any]) -> list[WorkContributor]:
    """Load :class:`WorkContributor` records from an issue's metadata dict.

    :param metadata: The dict returned by ``tracker.get_metadata(identifier)``.
    :returns: List of contributors, possibly empty.  Malformed records are
        silently skipped with a debug log entry so a corrupt entry never
        crashes a caller.
    """
    record = metadata.get(METADATA_KEY)
    if not record or not isinstance(record, dict):
        return []
    runs = record.get("runs", [])
    if not isinstance(runs, list):
        return []
    result: list[WorkContributor] = []
    for raw in runs:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(WorkContributor.from_dict(raw))
        except Exception as exc:  # noqa: BLE001
            logger.debug("work_contributors: skipping malformed run record: %s", exc)
    return result


# ---------------------------------------------------------------------------
# Git ancestry helper
# ---------------------------------------------------------------------------


def sha_is_ancestor(sha: str, base_sha: str, repo_path: str) -> bool:
    """Return True when *sha* is an ancestor (or equal to) *base_sha*.

    Uses ``git merge-base --is-ancestor``.  Any error (missing repo,
    unknown ref, timeout) returns ``False`` so callers fail-open.

    :param sha: The candidate commit SHA to check.
    :param base_sha: The reference commit SHA (e.g. the audit revision).
    :param repo_path: Filesystem path to the git repository root.
    """
    if not sha or not base_sha or not repo_path:
        return False
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, base_sha],
            cwd=repo_path,
            capture_output=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug(
            "work_contributors: sha_is_ancestor check failed sha=%s base=%s: %s",
            sha,
            base_sha,
            exc,
        )
        return False


# ---------------------------------------------------------------------------
# Epic contributor union
# ---------------------------------------------------------------------------


def collect_epic_contributors(
    epic_identifier: str,
    audit_sha: str,
    tracker: Any,
    repo_path: str | None = None,
    *,
    _visited: set[str] | None = None,
) -> list[WorkContributor]:
    """Derive the union of contributors for an epic at a given audit revision.

    Aggregates contributors from:

    1. The epic's own ``oompah.work_contributors`` metadata.
    2. All direct children's ``oompah.work_contributors`` metadata.
    3. All nested-child epics' contributors, recursively.

    A contributor is **included** when:

    - ``repo_path`` and ``audit_sha`` are provided and
      ``sha_is_ancestor(contributor.source_sha, audit_sha, repo_path)``
      is True — the contributor's commits are contained in the revision.
    - OR ``contributor.source_sha`` is None/empty (unknown SHA) — include
      conservatively to avoid false negatives.
    - OR ``repo_path`` or ``audit_sha`` is not provided — no filtering.

    Contributors from different tasks are **deduplicated by run_id**:
    the first occurrence wins.

    :param epic_identifier: Issue identifier of the epic (e.g. ``"OOMPAH-458"``).
    :param audit_sha: Git HEAD SHA of the revision being audited.
    :param tracker: A tracker instance implementing
        ``get_metadata(identifier)``, ``fetch_children(epic_id)``, and
        ``fetch_issue_detail(identifier)``.
    :param repo_path: Local path to the git repository for ancestry checks.
        When ``None``, no ancestry filtering is applied.
    :param _visited: Internal cycle guard (do not supply from call sites).
    :returns: Deduplicated list of :class:`WorkContributor` objects for the
        audited revision.
    """
    if _visited is None:
        _visited = set()
    if epic_identifier in _visited:
        return []
    _visited.add(epic_identifier)

    all_contributors: dict[str, WorkContributor] = {}  # run_id → first occurrence

    can_filter = bool(repo_path and audit_sha)

    def _should_include(c: WorkContributor) -> bool:
        if not can_filter:
            return True
        if not c.source_sha:
            # Unknown SHA — include conservatively
            return True
        assert repo_path is not None
        return sha_is_ancestor(c.source_sha, audit_sha, repo_path)

    def _collect_from(identifier: str) -> None:
        try:
            meta = dict(tracker.get_metadata(identifier))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "work_contributors: failed to fetch metadata for %s: %s",
                identifier,
                exc,
            )
            return
        for c in load_contributors(meta):
            if c.run_id and c.run_id not in all_contributors and _should_include(c):
                all_contributors[c.run_id] = c

    # Collect from the epic itself
    _collect_from(epic_identifier)

    # Collect from direct children
    try:
        children = tracker.fetch_children(epic_identifier)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "work_contributors: failed to fetch children for %s: %s",
            epic_identifier,
            exc,
        )
        children = []

    for child in children or []:
        child_id: str | None = None
        if isinstance(child, str):
            child_id = child
        else:
            child_id = getattr(child, "identifier", None) or getattr(child, "id", None)
        if not child_id or child_id in _visited:
            continue

        # Collect this child's own contributors
        _collect_from(child_id)

        # Recurse into nested epics
        child_type = str(getattr(child, "issue_type", "") or "").strip().lower()
        if child_type == "epic":
            nested = collect_epic_contributors(
                child_id,
                audit_sha,
                tracker,
                repo_path=repo_path,
                _visited=_visited,
            )
            for c in nested:
                if c.run_id and c.run_id not in all_contributors:
                    all_contributors[c.run_id] = c

    return list(all_contributors.values())
