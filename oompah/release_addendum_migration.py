"""Idempotent migration from legacy ``oompah.release_addendums`` task metadata
into the project-owned ``.oompah/release-deliveries.yml`` delivery ledger
(OOMPAH-194).

Overview
--------

``oompah.release_addendums`` is task-owned metadata: each source task or epic
stores its own list of :class:`~oompah.release_addendum_schema.ReleaseAddendum`
entries.  The new delivery ledger (``.oompah/release-deliveries.yml``) is a
single project-wide file managed by
:class:`~oompah.release_delivery_store.ReleaseDeliveryStore`.

This module copies every existing addendum to the ledger as a
:class:`~oompah.release_delivery_store.ReleaseDelivery` record, setting
``migrated_from`` to the legacy addendum ID so that
:class:`~oompah.release_delivery_adapter.DualReadDeliveryAdapter` can
de-duplicate across both sources.

Idempotency
-----------

Before processing each addendum the migration reads the current set of
``migrated_from`` values in the ledger.  Any addendum whose ID is already
present is silently skipped (``skipped_duplicate``).  Re-running the migration
after a partial first run or a process restart is therefore safe.

SHA validation
--------------

The delivery ledger requires that every ``source_commits`` entry is a valid
full 40-character lower-case hex SHA.  Legacy addendums may contain sentinel
strings introduced by the OOMPAH-183 migration (``"migration-pending"``,
``"migration-no-commits"``) instead of real SHAs.  These addendums cannot be
stored in the ledger without corrupting the ledger schema, so they are
reported as ``skipped_malformed`` and skipped.  Other structural validation
errors in legacy addendum records are handled the same way: each bad record
is logged and counted, and the remaining valid records are migrated normally.

Source kind
-----------

The :class:`~oompah.release_delivery_store.SourceKind` is inferred from the
source issue's ``issue_type`` field:

* ``"epic"`` → :attr:`~oompah.release_delivery_store.SourceKind.EPIC`
* anything else (``"task"``, ``"chore"``, etc.) → :attr:`~oompah.release_delivery_store.SourceKind.TASK`

The source identifier is the issue's ``identifier`` attribute.

Delivery ID
-----------

Each migrated record receives a fresh ``rd_<uuid-hex>`` ID that is unique
within the ledger.  The legacy addendum ID is stored in ``migrated_from``.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from oompah.release_addendum_schema import (
    ReleaseAddendum,
    parse_addendums,
)
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
)

if TYPE_CHECKING:
    from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SHA validation helper (inline, avoids circular import)
# ---------------------------------------------------------------------------

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

#: Sentinel strings introduced by OOMPAH-183 for addendums that lacked commit
#: evidence at migration time.  Records containing only these values are
#: reported and skipped rather than stored in the ledger with invalid SHAs.
_OOMPAH_183_SENTINELS: frozenset[str] = frozenset({
    "migration-pending",
    "migration-no-commits",
})


def _all_commits_valid(commits: list[str]) -> bool:
    """Return True when every entry in *commits* is a valid 40-char hex SHA.

    Args:
        commits: List of commit strings to validate.

    Returns:
        True when every element passes the full-SHA regex check.
    """
    return all(_FULL_SHA_RE.match(c) for c in commits)


def _make_delivery_id() -> str:
    """Return a fresh unique delivery ID of the form ``rd_<uuid-hex>``.

    Returns:
        New delivery ID string.
    """
    return f"rd_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Migration result
# ---------------------------------------------------------------------------


@dataclass
class AddendumMigrationResult:
    """Summary of one migration pass from addendums to the delivery ledger.

    Attributes:
        issues_scanned: Number of issues examined (those that had at least one
            ``oompah.release_addendums`` entry).
        migrated: Number of addendum entries successfully copied to the ledger.
        skipped_duplicate: Number of addendum entries already present in the
            ledger (by ``migrated_from`` match); these are left unchanged.
        skipped_malformed: Number of addendum entries that failed schema
            validation (e.g. invalid SHA commits, missing required fields) and
            were not migrated.
        errors: Number of unexpected errors (ledger write failures, tracker
            read failures) that prevented individual entries from migrating.
    """

    issues_scanned: int = 0
    migrated: int = 0
    skipped_duplicate: int = 0
    skipped_malformed: int = 0
    errors: int = 0

    @property
    def changed(self) -> bool:
        """Return True when any records were written to the ledger."""
        return self.migrated > 0


# ---------------------------------------------------------------------------
# Core conversion helper
# ---------------------------------------------------------------------------


def build_delivery_from_addendum(
    addendum: ReleaseAddendum,
    source_identifier: str,
    source_kind: SourceKind,
    project_id: str,
    *,
    delivery_id: str | None = None,
) -> ReleaseDelivery:
    """Build a :class:`~oompah.release_delivery_store.ReleaseDelivery` from a
    legacy :class:`~oompah.release_addendum_schema.ReleaseAddendum`.

    All execution evidence fields from the addendum (``pr_url``,
    ``result_commits``, ``error``, ``claimed_by``, ``lease_expires_at``,
    ``started_at``, ``completed_at``, ``work_branch``) are preserved
    byte-for-byte where the delivery schema permits.

    Args:
        addendum: Source legacy addendum to convert.
        source_identifier: Identifier of the source task or epic
            (e.g. ``"FOO-10"``).
        source_kind: Whether the source is a task or epic.
        project_id: Project that owns the new delivery record.
        delivery_id: Optional explicit delivery ID (used in tests for
            determinism); defaults to a fresh ``rd_<uuid-hex>``.

    Returns:
        New :class:`~oompah.release_delivery_store.ReleaseDelivery` record
        with ``migrated_from`` set to ``addendum.id``.

    Raises:
        ValueError: When ``addendum.commits`` contains entries that are not
            valid 40-character hex SHAs (including OOMPAH-183 sentinel
            strings).  Callers should catch this and skip the addendum.
    """
    # Validate every commit SHA before writing to the ledger.
    invalid = [c for c in addendum.commits if not _FULL_SHA_RE.match(c)]
    if invalid:
        sentinel_hint = ""
        if any(c in _OOMPAH_183_SENTINELS for c in invalid):
            sentinel_hint = (
                " (contains OOMPAH-183 sentinel values; the entry had no real"
                " commit data at migration time)"
            )
        raise ValueError(
            f"Addendum {addendum.id!r} has invalid source_commits "
            f"{invalid!r}{sentinel_hint}"
        )

    return ReleaseDelivery(
        id=delivery_id if delivery_id is not None else _make_delivery_id(),
        project_id=project_id,
        source_branch=addendum.source_branch,
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=list(addendum.commits),
        target_branch=addendum.target_branch,
        # --- Mutable lifecycle fields ---
        status=addendum.status,
        queued_at=addendum.queued_at,
        claimed_by=addendum.claimed_by,
        lease_expires_at=addendum.lease_expires_at,
        started_at=addendum.started_at,
        completed_at=addendum.completed_at,
        work_branch=addendum.work_branch,
        pr_url=addendum.pr_url,
        pr_number=None,  # ReleaseAddendum does not carry pr_number
        result_commits=list(addendum.result_commits),
        error=addendum.error,
        migrated_from=addendum.id,
    )


# ---------------------------------------------------------------------------
# Per-source-issue migration
# ---------------------------------------------------------------------------


def _infer_source_kind(issue_type: str) -> SourceKind:
    """Return the :class:`~oompah.release_delivery_store.SourceKind` for a
    source issue's ``issue_type`` string.

    Args:
        issue_type: Issue type string (e.g. ``"task"``, ``"epic"``).

    Returns:
        :attr:`~oompah.release_delivery_store.SourceKind.EPIC` when
        *issue_type* is ``"epic"`` (case-insensitive); otherwise
        :attr:`~oompah.release_delivery_store.SourceKind.TASK`.
    """
    return (
        SourceKind.EPIC
        if str(issue_type or "").strip().lower() == "epic"
        else SourceKind.TASK
    )


# ---------------------------------------------------------------------------
# Full-project migration
# ---------------------------------------------------------------------------


def run_addendum_migration(
    tracker: "TrackerProtocol",
    store: ReleaseDeliveryStore,
    project_id: str,
    *,
    now: str | None = None,
) -> AddendumMigrationResult:
    """Run one idempotent migration pass over all issues in the tracker.

    Scans every issue (including terminal items) for ``oompah.release_addendums``
    metadata.  For each addendum not already present in the ledger (identified
    by ``migrated_from``), a :class:`~oompah.release_delivery_store.ReleaseDelivery`
    is created and appended to the store.

    The migration is safe to re-run:

    * Addendums whose ID is already in ``migrated_from`` of any ledger entry
      are skipped without touching the ledger.
    * A ledger that was only partially migrated (e.g. due to a process restart)
      will have its remaining entries filled in on the next run.
    * When no new records are written, the ledger file is not modified and no
      commit is produced.

    Args:
        tracker: Tracker implementation for the project.
        store: :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
            backed by the project's ledger.
        project_id: Project identifier (used when creating new delivery records
            and as a defensive ownership check).
        now: Unused; reserved for future timestamp overrides.  Pass ``None``.

    Returns:
        :class:`AddendumMigrationResult` summarising all changes made.
    """
    result = AddendumMigrationResult()

    # -----------------------------------------------------------------------
    # 1. Read current ledger to determine already-migrated addendum IDs.
    #    We track locally in a set so we can skip duplicates across issues
    #    without re-reading the ledger for every single addendum.
    # -----------------------------------------------------------------------
    try:
        ledger = store.read_ledger()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "release_addendum_migration: cannot read ledger: %s — "
            "migration aborted",
            exc,
        )
        result.errors += 1
        return result

    already_migrated: set[str] = {
        d.migrated_from
        for d in ledger.deliveries
        if d.migrated_from
    }

    # -----------------------------------------------------------------------
    # 2. Scan all issues (including terminal).
    # -----------------------------------------------------------------------
    try:
        all_issues = tracker.fetch_all_issues()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "release_addendum_migration: fetch_all_issues failed: %s — "
            "migration aborted",
            exc,
        )
        result.errors += 1
        return result

    for issue in all_issues:
        # Retrieve metadata; skip issues that have no addendums.
        try:
            meta = tracker.get_metadata(issue.identifier)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_addendum_migration: get_metadata failed for %s: %s",
                issue.identifier,
                exc,
            )
            continue

        raw_addendums = meta.get("oompah.release_addendums")
        if not raw_addendums:
            continue

        # Parse the addendum list; each malformed entry is counted and skipped.
        addendums: list[ReleaseAddendum] = []
        if isinstance(raw_addendums, list):
            raw_list: list[Any] = raw_addendums
        elif isinstance(raw_addendums, dict):
            raw_list = [raw_addendums]
        else:
            logger.warning(
                "release_addendum_migration: %s has unexpected "
                "oompah.release_addendums type %s; skipping",
                issue.identifier,
                type(raw_addendums).__name__,
            )
            result.skipped_malformed += 1
            continue

        for entry in raw_list:
            try:
                addendums.append(ReleaseAddendum.from_raw(entry))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "release_addendum_migration: malformed addendum entry on "
                    "%s: %s — skipping this entry",
                    issue.identifier,
                    exc,
                )
                result.skipped_malformed += 1

        if not addendums:
            continue

        result.issues_scanned += 1
        source_kind = _infer_source_kind(issue.issue_type)

        for addendum in addendums:
            # ---------------------------------------------------------------
            # 3. Idempotency check: skip already-migrated addendums.
            # ---------------------------------------------------------------
            if addendum.id in already_migrated:
                result.skipped_duplicate += 1
                logger.debug(
                    "release_addendum_migration: %s addendum %r already in "
                    "ledger — skipping",
                    issue.identifier,
                    addendum.id,
                )
                continue

            # ---------------------------------------------------------------
            # 4. Build and append the delivery.
            # ---------------------------------------------------------------
            try:
                delivery = build_delivery_from_addendum(
                    addendum,
                    issue.identifier,
                    source_kind,
                    project_id,
                )
            except ValueError as exc:
                logger.warning(
                    "release_addendum_migration: cannot convert addendum %r on "
                    "%s: %s — skipping",
                    addendum.id,
                    issue.identifier,
                    exc,
                )
                result.skipped_malformed += 1
                continue

            try:
                store.append(delivery)
                already_migrated.add(addendum.id)
                result.migrated += 1
                logger.info(
                    "release_addendum_migration: migrated %s addendum %r → "
                    "ledger delivery %r",
                    issue.identifier,
                    addendum.id,
                    delivery.id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "release_addendum_migration: failed to append delivery for "
                    "%s addendum %r: %s",
                    issue.identifier,
                    addendum.id,
                    exc,
                )
                result.errors += 1

    logger.info(
        "release_addendum_migration: pass complete — "
        "issues_scanned=%d migrated=%d skipped_duplicate=%d "
        "skipped_malformed=%d errors=%d",
        result.issues_scanned,
        result.migrated,
        result.skipped_duplicate,
        result.skipped_malformed,
        result.errors,
    )
    return result
