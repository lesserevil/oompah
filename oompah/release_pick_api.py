"""Release-pick task detail API helpers (TASK-456.1, TASK-456.4).

Provides helper functions to read and update release-pick metadata for a
task, validate target branches, and return normalized results consumed by
the HTTP API endpoints in ``server.py``.

The public API consists of:

* :func:`get_release_pick_detail` — reads and normalises the
  ``oompah.backports`` / ``oompah.backport_of`` frontmatter fields from a
  task into a dictionary suitable for JSON serialisation.

* :func:`update_release_pick_entry` — merges a single ``BackportEntry``
  update into the task's ``oompah.backports`` frontmatter after validating
  each target branch against the project's configured branch patterns.

* :func:`update_release_picks_bulk` — merges a list of backport-entry
  updates into the task's ``oompah.backports`` frontmatter after validating
  all target branches.

* :func:`get_epic_release_pick_matrix` — builds a child-by-target-branch
  matrix showing per-child release-pick status for an epic.  Each row is a
  child task; columns are all unique target branches seen across the epic's
  children.

* :func:`apply_release_picks_to_all_children` — applies a set of target
  branches to every child of an epic in one operation.  Individual children
  can be excluded (``skip_children``) — excluded children receive a
  ``skipped`` entry for each branch rather than a ``waiting`` entry.

All functions are intentionally stateless with respect to the HTTP layer —
they accept tracker / project objects and raise plain :class:`ValueError` on
bad input so callers (server endpoints) can translate errors into appropriate
HTTP responses.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from oompah.release_pick_schema import (
    BackportEntry,
    BackportOf,
    ReleasePick,
    backports_to_raw,
    parse_backport_of,
    parse_backports,
)
from oompah.release_pick_validation import (
    ReleaseBranchValidationResult,
    validate_backports_list,
)

logger = logging.getLogger(__name__)

# Regex to extract a numeric PR ID from a GitHub PR URL.
# e.g. "https://github.com/org/repo/pull/42" → "42"
_PR_ID_RE = re.compile(r"/pull/(\d+)(?:[/?#]|$)")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_pr_id(pr_url: str | None) -> str | None:
    """Extract a numeric pull-request ID from a GitHub PR URL.

    Returns the ID as a *string* (e.g. ``"42"``) to avoid integer overflow on
    very large PR numbers and to remain consistent with how other identifiers are
    represented in the API.  Returns ``None`` when *pr_url* is absent or does
    not contain a recognisable PR number.

    Args:
        pr_url: A GitHub pull-request URL, or ``None``.

    Returns:
        The pull-request ID string, or ``None``.
    """
    if not pr_url:
        return None
    m = _PR_ID_RE.search(str(pr_url))
    return m.group(1) if m else None


def _normalise_entry(
    entry: BackportEntry,
    validation: ReleaseBranchValidationResult | None = None,
) -> dict[str, Any]:
    """Serialise a :class:`BackportEntry` to a JSON-serialisable dict.

    Includes derived fields:

    * ``pr_id`` — numeric PR ID extracted from ``pr_url`` (string, or
      ``None`` when ``pr_url`` is absent/unrecognisable).
    * ``is_valid`` — ``True`` when the branch passed validation (or when
      validation was not attempted); ``False`` otherwise.
    * ``validation_error`` — human-readable error string from branch
      validation, or ``None`` when valid.

    Args:
        entry: The :class:`BackportEntry` to normalise.
        validation: Optional validation result for this entry's branch.

    Returns:
        A dict ready for JSON serialisation.
    """
    is_valid = validation.valid if validation is not None else True
    validation_error = (
        validation.error if validation is not None and not validation.valid else None
    )
    return {
        "branch": entry.branch,
        "status": entry.status.value,
        "task_id": entry.task_id,
        "pr_url": entry.pr_url,
        "pr_id": _extract_pr_id(entry.pr_url),
        "is_valid": is_valid,
        "validation_error": validation_error,
    }


def _build_result(
    identifier: str,
    entries: list[BackportEntry],
    backport_of: BackportOf | None,
    *,
    project: Any | None = None,
) -> dict[str, Any]:
    """Build a normalised release-pick detail dict from in-memory objects.

    Unlike :func:`get_release_pick_detail` this function does not read
    from the tracker; it works directly with already-parsed objects.
    Used by write paths (``update_release_pick_entry``,
    ``update_release_picks_bulk``) to avoid a second tracker read after
    a write.

    Args:
        identifier: Task identifier string.
        entries: Current list of :class:`BackportEntry` objects.
        backport_of: Optional :class:`BackportOf` for this task.
        project: Optional project for branch validation.

    Returns:
        JSON-serialisable dict in the same shape as
        :func:`get_release_pick_detail`.
    """
    validation_by_branch: dict[str, ReleaseBranchValidationResult] = {}
    if project is not None and entries:
        branch_names = [e.branch for e in entries]
        results = validate_backports_list(branch_names, project)
        for result in results:
            if result.target_branch:
                validation_by_branch[result.target_branch] = result

    normalised_entries = [
        _normalise_entry(entry, validation_by_branch.get(entry.branch))
        for entry in entries
    ]

    backport_of_dict: dict[str, Any] | None = None
    if backport_of is not None:
        backport_of_dict = {
            "source": backport_of.source,
            "status": backport_of.status.value,
        }

    return {
        "identifier": identifier,
        "backports": normalised_entries,
        "backport_of": backport_of_dict,
    }


# ---------------------------------------------------------------------------
# Public API — read
# ---------------------------------------------------------------------------


def get_release_pick_detail(
    tracker: Any,
    identifier: str,
    *,
    project: Any | None = None,
) -> dict[str, Any]:
    """Read and normalise release-pick metadata for a task.

    Reads the ``oompah.backports`` and ``oompah.backport_of`` frontmatter
    fields via *tracker*, parses them using the typed schema helpers, and
    returns a normalised dict including derived fields (``pr_id``,
    ``is_valid``, ``validation_error`` per entry).

    When *project* is provided the backport target branches are also
    validated against the project's configured branch patterns so each
    entry in the returned list carries accurate ``is_valid`` /
    ``validation_error`` fields.  Without a project the validation fields
    default to ``True`` / ``None``.

    Args:
        tracker: Tracker adapter for the project that owns the task.
        identifier: The task identifier (e.g. ``"TASK-123"``).
        project: Optional :class:`~oompah.models.Project` for branch
            validation.  When ``None``, branch validation is skipped and
            all entries report ``is_valid=True``.

    Returns:
        A JSON-serialisable dict::

            {
                "identifier": "TASK-123",
                "backports": [
                    {
                        "branch": "release/1.0",
                        "status": "pr_open",
                        "task_id": "TASK-123.1",
                        "pr_url": "https://github.com/org/repo/pull/42",
                        "pr_id": "42",
                        "is_valid": true,
                        "validation_error": null
                    }
                ],
                "backport_of": {
                    "source": "TASK-100",
                    "status": "pr_open"
                }
            }

        ``backports`` is an empty list when there are no entries.
        ``backport_of`` is ``null`` / ``None`` when the field is absent.

    Raises:
        ValueError: When *identifier* is empty/None.
    """
    if not identifier:
        raise ValueError("identifier must not be empty")

    meta = tracker.get_metadata(identifier) or {}
    raw_backports = meta.get("oompah.backports")
    raw_backport_of = meta.get("oompah.backport_of")

    entries: list[BackportEntry] = parse_backports(raw_backports)
    backport_of: BackportOf | None = parse_backport_of(raw_backport_of)

    return _build_result(identifier, entries, backport_of, project=project)


# ---------------------------------------------------------------------------
# Public API — write
# ---------------------------------------------------------------------------


def update_release_pick_entry(
    tracker: Any,
    identifier: str,
    *,
    branch: str,
    status: str | ReleasePick | None = None,
    task_id: str | None = None,
    pr_url: str | None = None,
    project: Any | None = None,
    allow_new: bool = True,
) -> dict[str, Any]:
    """Merge a single backport-entry update into a task's release-pick metadata.

    Reads the current ``oompah.backports`` list from *tracker*, locates (or
    creates) an entry for *branch*, applies the supplied field updates, writes
    the updated list back to the tracker, and returns the updated
    release-pick detail.

    Branch validation is performed before writing when *project* is provided.
    When the branch fails validation an exception is raised and no write occurs.

    Args:
        tracker: Tracker adapter for the project that owns the task.
        identifier: The task identifier (e.g. ``"TASK-123"``).
        branch: The target branch name for the entry to update/create.
        status: New lifecycle status value.  Accepts a raw string (parsed via
            :meth:`~ReleasePick.from_raw`) or a :class:`ReleasePick` instance.
            When ``None`` the existing status is preserved; for new entries the
            default ``waiting`` status is used.
        task_id: The child task identifier to record (e.g. ``"TASK-123.1"``).
            ``None`` leaves the existing value unchanged.
        pr_url: The PR URL to record.  ``None`` leaves the existing value
            unchanged.
        project: Optional :class:`~oompah.models.Project` for branch
            validation.  When provided, the *branch* must match a configured
            pattern (and must not be the source-only default branch unless an
            allow label is present on the task).
        allow_new: When ``True`` (default) a new entry is created when
            *branch* does not already exist.  Set to ``False`` to restrict
            updates to existing entries only.

    Returns:
        The updated release-pick detail dict for *identifier* (same shape as
        :func:`get_release_pick_detail`).

    Raises:
        ValueError: When *branch* is empty, when *allow_new=False* and no
            matching entry exists, or when branch validation fails.
    """
    branch = (branch or "").strip()
    if not branch:
        raise ValueError("branch must not be empty")

    # Validate the branch against the project before touching the tracker
    if project is not None:
        validation_results = validate_backports_list([branch], project)
        if validation_results:
            v = validation_results[0]
            if not v.valid:
                raise ValueError(
                    f"Branch validation failed for '{branch}': {v.error}"
                )

    # Read current state once (both backports and backport_of)
    meta = tracker.get_metadata(identifier) or {}
    raw_backports = meta.get("oompah.backports")
    raw_backport_of = meta.get("oompah.backport_of")

    entries: list[BackportEntry] = parse_backports(raw_backports)
    backport_of: BackportOf | None = parse_backport_of(raw_backport_of)

    # Find existing entry or create new
    existing_idx: int | None = None
    for i, entry in enumerate(entries):
        if entry.branch == branch:
            existing_idx = i
            break

    if existing_idx is None:
        if not allow_new:
            raise ValueError(
                f"No existing backport entry found for branch '{branch}' on "
                f"task {identifier!r}. To create a new entry, pass allow_new=True."
            )
        new_entry = BackportEntry(
            branch=branch,
            status=ReleasePick.from_raw(status) if status is not None else ReleasePick.WAITING,
            task_id=task_id,
            pr_url=pr_url,
        )
        entries.append(new_entry)
    else:
        existing = entries[existing_idx]
        if status is not None:
            existing.status = ReleasePick.from_raw(status)
        if task_id is not None:
            existing.task_id = task_id
        if pr_url is not None:
            existing.pr_url = pr_url

    # Write updated list back
    raw_updated = backports_to_raw(entries)
    tracker.set_metadata_field(identifier, "oompah.backports", raw_updated)

    # Build the response from in-memory state (no second tracker read needed)
    return _build_result(identifier, entries, backport_of, project=project)


def update_release_picks_bulk(  # noqa: WPS231
    tracker: Any,
    identifier: str,
    *,
    backports: list[dict[str, Any]],
    project: Any | None = None,
) -> dict[str, Any]:
    """Replace or merge a list of backport entries into a task's release-pick metadata.

    Each entry in *backports* must have at least a ``"branch"`` key.
    Optional keys are ``"status"``, ``"task_id"``, and ``"pr_url"``.

    When *project* is provided, ALL target branches are validated before any
    write occurs.  If any branch fails validation a :class:`ValueError` is
    raised with a summary of all failures and no write occurs.

    For each supplied branch the function finds the matching existing entry
    (if any) and applies updates; new entries are appended.

    Args:
        tracker: Tracker adapter for the project that owns the task.
        identifier: The task identifier.
        backports: List of dicts each with ``"branch"`` and optional
            ``"status"``, ``"task_id"``, ``"pr_url"`` keys.
        project: Optional :class:`~oompah.models.Project` for branch
            validation.

    Returns:
        The updated release-pick detail dict for *identifier* (same shape as
        :func:`get_release_pick_detail`).

    Raises:
        ValueError: When any branch is empty/invalid, or when branch
            validation fails for any entry.
    """
    if not backports:
        raise ValueError("backports list must not be empty")

    # Validate all branch names first (before any reads or writes)
    branch_names: list[str] = []
    for item in backports:
        b = str(item.get("branch") or "").strip()
        if not b:
            raise ValueError(
                f"Each backports entry must have a non-empty 'branch' key; "
                f"got: {item!r}"
            )
        branch_names.append(b)

    if project is not None:
        validation_results = validate_backports_list(branch_names, project)
        failures = [v for v in validation_results if not v.valid]
        if failures:
            errors = "; ".join(
                f"'{v.target_branch}': {v.error}" for v in failures
            )
            raise ValueError(f"Branch validation failed: {errors}")

    # Read current state once
    meta = tracker.get_metadata(identifier) or {}
    raw_backports = meta.get("oompah.backports")
    raw_backport_of = meta.get("oompah.backport_of")

    entries: list[BackportEntry] = parse_backports(raw_backports)
    backport_of: BackportOf | None = parse_backport_of(raw_backport_of)

    # Build a lookup dict and merged entry list
    entries_by_branch: dict[str, BackportEntry] = {e.branch: e for e in entries}

    for item, branch in zip(backports, branch_names):
        status_raw = item.get("status")
        task_id_raw = item.get("task_id")
        pr_url_raw = item.get("pr_url")

        if branch in entries_by_branch:
            existing = entries_by_branch[branch]
            if status_raw is not None:
                existing.status = ReleasePick.from_raw(status_raw)
            if task_id_raw is not None:
                existing.task_id = str(task_id_raw) if task_id_raw else None
            if pr_url_raw is not None:
                existing.pr_url = str(pr_url_raw) if pr_url_raw else None
        else:
            new_entry = BackportEntry(
                branch=branch,
                status=ReleasePick.from_raw(status_raw) if status_raw is not None else ReleasePick.WAITING,
                task_id=str(task_id_raw) if task_id_raw else None,
                pr_url=str(pr_url_raw) if pr_url_raw else None,
            )
            entries_by_branch[branch] = new_entry
            entries.append(new_entry)

    # Write updated list back
    raw_updated = backports_to_raw(entries)
    tracker.set_metadata_field(identifier, "oompah.backports", raw_updated)

    # Build the response from in-memory state (no second tracker read needed)
    return _build_result(identifier, entries, backport_of, project=project)


# ---------------------------------------------------------------------------
# Public API — epic matrix
# ---------------------------------------------------------------------------


def get_epic_release_pick_matrix(
    tracker: Any,
    epic_identifier: str,
    *,
    project: Any | None = None,
) -> dict[str, Any]:
    """Build a child-by-target-branch matrix for an epic.

    Fetches all child tasks of *epic_identifier*, reads their release-pick
    metadata, and returns a matrix where each row is a child task and each
    column is a unique target branch seen anywhere in the epic.

    Args:
        tracker: Tracker adapter for the project that owns the task.
        epic_identifier: The identifier of the parent epic task.
        project: Optional :class:`~oompah.models.Project` for branch
            validation.  When provided each entry's ``is_valid`` /
            ``validation_error`` fields are populated.

    Returns:
        A JSON-serialisable dict::

            {
                "epic_identifier": "TASK-456",
                "branches": ["release/1.0", "release/2.0"],
                "rows": [
                    {
                        "identifier": "TASK-456.1",
                        "title": "...",
                        "state": "done",
                        "entries": {
                            "release/1.0": {
                                "branch": "release/1.0",
                                "status": "merged",
                                "task_id": null,
                                "pr_url": null,
                                "pr_id": null,
                                "is_valid": true,
                                "validation_error": null
                            },
                            "release/2.0": null
                        }
                    }
                ]
            }

        ``entries`` maps each known branch to a normalised entry dict (same
        shape as an entry in :func:`get_release_pick_detail`) or ``null``
        when the child has no entry for that branch.  ``branches`` is
        sorted alphabetically.

    Raises:
        ValueError: When *epic_identifier* is empty/None.
    """
    if not epic_identifier:
        raise ValueError("epic_identifier must not be empty")

    children = tracker.fetch_children(epic_identifier)

    # Collect all unique branches across all children and per-child entry maps
    all_branches: set[str] = set()
    child_data: list[dict[str, Any]] = []

    for child in children:
        meta = tracker.get_metadata(child.identifier) or {}
        raw_backports = meta.get("oompah.backports")
        entries: list[BackportEntry] = parse_backports(raw_backports)

        # Validate branches when a project is available
        validation_by_branch: dict[str, ReleaseBranchValidationResult] = {}
        if project is not None and entries:
            branch_names = [e.branch for e in entries]
            results = validate_backports_list(branch_names, project)
            for result in results:
                if result.target_branch:
                    validation_by_branch[result.target_branch] = result

        entries_by_branch: dict[str, dict[str, Any]] = {
            entry.branch: _normalise_entry(entry, validation_by_branch.get(entry.branch))
            for entry in entries
        }
        for branch in entries_by_branch:
            all_branches.add(branch)

        child_data.append(
            {
                "identifier": child.identifier,
                "title": child.title,
                "state": child.state,
                "_entries_by_branch": entries_by_branch,
            }
        )

    sorted_branches = sorted(all_branches)

    # Build the final rows — fill missing entries with None
    rows: list[dict[str, Any]] = []
    for item in child_data:
        entries_by_branch = item.pop("_entries_by_branch")
        item["entries"] = {
            branch: entries_by_branch.get(branch)
            for branch in sorted_branches
        }
        rows.append(item)

    return {
        "epic_identifier": epic_identifier,
        "branches": sorted_branches,
        "rows": rows,
    }


def apply_release_picks_to_all_children(
    tracker: Any,
    epic_identifier: str,
    *,
    branches: list[str],
    skip_children: list[str] | None = None,
    project: Any | None = None,
) -> dict[str, Any]:
    """Apply a set of target branches to every child of an epic.

    For each child of *epic_identifier*:

    * Children **not** in *skip_children* receive a ``waiting`` entry for
      each branch (or preserve their existing entry if one already exists).
    * Children **in** *skip_children* receive a ``skipped`` entry for each
      branch so they are visible in the matrix but excluded from automation.

    Branch validation is performed before any writes.  If any branch fails
    validation a :class:`ValueError` is raised and no writes occur.

    Args:
        tracker: Tracker adapter for the project that owns the task.
        epic_identifier: The identifier of the parent epic task.
        branches: List of target branch names to apply.
        skip_children: Optional list of child identifiers to mark as
            ``skipped`` instead of ``waiting``.  ``None`` or empty means
            no children are skipped.
        project: Optional :class:`~oompah.models.Project` for branch
            validation.

    Returns:
        The updated epic release-pick matrix (same shape as
        :func:`get_epic_release_pick_matrix`).

    Raises:
        ValueError: When *epic_identifier* or *branches* is empty, or
            when branch validation fails.
    """
    if not epic_identifier:
        raise ValueError("epic_identifier must not be empty")
    if not branches:
        raise ValueError("branches list must not be empty")

    # Validate all branch names
    clean_branches: list[str] = []
    for b in branches:
        b = (b or "").strip()
        if not b:
            raise ValueError("Each branch name must be non-empty")
        clean_branches.append(b)

    if project is not None:
        validation_results = validate_backports_list(clean_branches, project)
        failures = [v for v in validation_results if not v.valid]
        if failures:
            errors = "; ".join(
                f"'{v.target_branch}': {v.error}" for v in failures
            )
            raise ValueError(f"Branch validation failed: {errors}")

    skip_set: set[str] = set(skip_children or [])

    children = tracker.fetch_children(epic_identifier)

    for child in children:
        meta = tracker.get_metadata(child.identifier) or {}
        raw_backports = meta.get("oompah.backports")
        entries: list[BackportEntry] = parse_backports(raw_backports)
        entries_by_branch: dict[str, BackportEntry] = {e.branch: e for e in entries}

        is_skipped = child.identifier in skip_set
        desired_status = ReleasePick.SKIPPED if is_skipped else ReleasePick.WAITING

        changed = False
        for branch in clean_branches:
            if branch not in entries_by_branch:
                entries.append(BackportEntry(branch=branch, status=desired_status))
                changed = True
            elif is_skipped and entries_by_branch[branch].status != ReleasePick.SKIPPED:
                # Mark existing entry as skipped when the child is excluded
                entries_by_branch[branch].status = ReleasePick.SKIPPED
                changed = True

        if changed:
            raw_updated = backports_to_raw(entries)
            tracker.set_metadata_field(child.identifier, "oompah.backports", raw_updated)

    # Return the updated matrix
    return get_epic_release_pick_matrix(tracker, epic_identifier, project=project)
