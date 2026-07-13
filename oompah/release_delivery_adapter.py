"""Dual-read adapter that combines the project-owned release delivery ledger with
legacy ``oompah.release_addendums`` task metadata (OOMPAH-194).

During the migration window both data sources coexist.  This adapter provides
a single de-duplicated :class:`~oompah.release_delivery_store.ReleaseDelivery`
view so callers do not need to know whether a given delivery has already been
migrated to the ledger.

De-duplication
--------------

A ledger record with ``migrated_from`` set to a legacy addendum ID acts as the
authoritative version of that delivery.  The legacy addendum with the same ID
is suppressed from the combined result — the ledger record takes precedence.

Legacy addendums that have NOT yet been migrated (i.e. their ``id`` does not
match any ``migrated_from`` value in the ledger) appear in the result as
synthetic :class:`~oompah.release_delivery_store.ReleaseDelivery` objects.
Their ID is set to ``legacy:<addendum-id>`` and their
``migrated_from`` is set to the addendum ID so callers can identify them.

Source kind for legacy records
-------------------------------

When converting a legacy addendum on-the-fly the adapter infers
:class:`~oompah.release_delivery_store.SourceKind` from the source issue's
``issue_type``.  If the issue cannot be fetched from the tracker the kind
defaults to :attr:`~oompah.release_delivery_store.SourceKind.TASK`.

Usage
-----

::

    from oompah.release_delivery_adapter import DualReadDeliveryAdapter
    from oompah.release_delivery_store import ReleaseDeliveryStore

    store = ReleaseDeliveryStore(project_root, project_id, git_writer=tracker)
    adapter = DualReadDeliveryAdapter(store, tracker, project_id)

    # Get all deliveries for a source task or epic:
    deliveries = adapter.list_deliveries_for_source("FOO-10")

    # Get all deliveries in the project (ledger + non-migrated legacy):
    all_deliveries = adapter.list_all_deliveries()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from oompah.release_addendum_schema import ReleaseAddendum, parse_addendums
from oompah.release_delivery_store import (
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
)

if TYPE_CHECKING:
    from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversion helper (legacy addendum → synthetic delivery)
# ---------------------------------------------------------------------------


def _addendum_to_delivery(
    addendum: ReleaseAddendum,
    source_identifier: str,
    source_kind: SourceKind,
    project_id: str,
) -> ReleaseDelivery:
    """Convert a legacy :class:`~oompah.release_addendum_schema.ReleaseAddendum`
    to a synthetic :class:`~oompah.release_delivery_store.ReleaseDelivery`.

    The returned record is **not** stored in the ledger — it is a transient,
    read-only representation of the legacy data.

    The ``id`` is set to ``legacy:<addendum.id>`` so callers can distinguish
    synthetic records from real ledger entries.  ``migrated_from`` is set to
    the addendum ID to support de-duplication.

    Args:
        addendum: Legacy addendum to convert.
        source_identifier: Source task or epic identifier.
        source_kind: Whether the source is a task or epic.
        project_id: Project that owns the delivery.

    Returns:
        Synthetic :class:`~oompah.release_delivery_store.ReleaseDelivery`.
    """
    return ReleaseDelivery(
        id=f"legacy:{addendum.id}",
        project_id=project_id,
        source_branch=addendum.source_branch,
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=list(addendum.commits),
        target_branch=addendum.target_branch,
        status=addendum.status,
        queued_at=addendum.queued_at,
        claimed_by=addendum.claimed_by,
        lease_expires_at=addendum.lease_expires_at,
        started_at=addendum.started_at,
        completed_at=addendum.completed_at,
        work_branch=addendum.work_branch,
        pr_url=addendum.pr_url,
        pr_number=None,
        result_commits=list(addendum.result_commits),
        error=addendum.error,
        migrated_from=addendum.id,
    )


def _infer_source_kind(issue_type: str | None) -> SourceKind:
    """Return the :class:`~oompah.release_delivery_store.SourceKind` for *issue_type*.

    Args:
        issue_type: Issue type string (``"task"``, ``"epic"``, etc.) or
            ``None``.

    Returns:
        :attr:`~oompah.release_delivery_store.SourceKind.EPIC` when
        *issue_type* equals ``"epic"`` (case-insensitive); otherwise
        :attr:`~oompah.release_delivery_store.SourceKind.TASK`.
    """
    return (
        SourceKind.EPIC
        if str(issue_type or "").strip().lower() == "epic"
        else SourceKind.TASK
    )


def _parse_legacy_addendums_safe(
    raw: Any,
    identifier: str,
) -> list[ReleaseAddendum]:
    """Parse ``oompah.release_addendums`` metadata, silently dropping malformed entries.

    Args:
        raw: Raw metadata value (list, dict, or ``None``).
        identifier: Source identifier for logging context.

    Returns:
        List of successfully parsed :class:`~oompah.release_addendum_schema.ReleaseAddendum`
        objects.  Malformed entries are logged and omitted.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        logger.debug(
            "release_delivery_adapter: unexpected addendums type %s on %s",
            type(raw).__name__,
            identifier,
        )
        return []
    addendums: list[ReleaseAddendum] = []
    for entry in raw:
        try:
            addendums.append(ReleaseAddendum.from_raw(entry))
        except (ValueError, TypeError) as exc:
            logger.debug(
                "release_delivery_adapter: malformed addendum on %s: %s — omitting",
                identifier,
                exc,
            )
    return addendums


# ---------------------------------------------------------------------------
# DualReadDeliveryAdapter
# ---------------------------------------------------------------------------


class DualReadDeliveryAdapter:
    """Combines the project-owned release delivery ledger with legacy
    ``oompah.release_addendums`` task metadata into a single de-duplicated view.

    During the migration window (after the migration has been *deployed* but
    before every legacy addendum has been *migrated*), both data sources may
    contain records for the same source task or epic.  This adapter hides that
    complexity from callers:

    * Ledger entries with ``migrated_from`` set shadow the corresponding legacy
      addendum — callers see the ledger record (the authoritative copy) rather
      than the legacy one.
    * Legacy addendums not yet in the ledger are surfaced as synthetic
      :class:`~oompah.release_delivery_store.ReleaseDelivery` objects.

    After the migration is complete and the compatibility window has elapsed,
    this adapter can be replaced by direct calls to
    :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`.

    Args:
        store: Store backed by the project's ledger file.
        tracker: Tracker implementation used to fetch task metadata.
        project_id: Project identifier (used when converting legacy addendums
            to synthetic delivery records).
    """

    def __init__(
        self,
        store: ReleaseDeliveryStore,
        tracker: "TrackerProtocol",
        project_id: str,
    ) -> None:
        self._store = store
        self._tracker = tracker
        self._project_id = str(project_id or "").strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_deliveries_for_source(
        self,
        source_identifier: str,
    ) -> list[ReleaseDelivery]:
        """Return all deliveries for *source_identifier*, de-duplicated across
        the ledger and legacy task metadata.

        Ledger entries are always returned as-is.  Legacy addendums not yet
        present in the ledger (i.e. their ``id`` does not match any
        ``migrated_from`` value among the ledger entries for this source) are
        included as synthetic records.

        The result preserves all execution evidence and is ordered ledger
        entries first, then non-migrated legacy entries in addendum list order.

        Args:
            source_identifier: Source task or epic identifier
                (e.g. ``"FOO-10"``).

        Returns:
            De-duplicated list of :class:`~oompah.release_delivery_store.ReleaseDelivery`
            objects.  May be empty.

        Raises:
            :class:`~oompah.release_delivery_store.LedgerParseError`:
                When the ledger file is malformed.
        """
        # 1. Ledger entries for this source.
        ledger_entries = self._store.lookup_by_source_identifier(source_identifier)

        # 2. Build the set of already-migrated addendum IDs.
        migrated_from_set: set[str] = {
            e.migrated_from for e in ledger_entries if e.migrated_from
        }

        # 3. Fetch and parse legacy addendums.
        legacy_addendums = self._fetch_legacy_addendums(source_identifier)

        # 4. Infer source kind for synthetic records.
        source_kind = self._fetch_source_kind(source_identifier)

        # 5. Build the combined result: ledger first, then non-migrated legacy.
        result: list[ReleaseDelivery] = list(ledger_entries)
        for addendum in legacy_addendums:
            if addendum.id in migrated_from_set:
                # This addendum is already represented in the ledger; skip it.
                continue
            synthetic = _addendum_to_delivery(
                addendum,
                source_identifier,
                source_kind,
                self._project_id,
            )
            result.append(synthetic)

        return result

    def list_all_deliveries(self) -> list[ReleaseDelivery]:
        """Return all deliveries in the project, de-duplicated across the ledger
        and all legacy source-task metadata.

        This is the project-wide union of:

        * All records in the ledger.
        * For every issue that has ``oompah.release_addendums`` metadata,
          any addendum not already represented in the ledger (identified by
          ``migrated_from``).

        Ledger records appear first (in ledger order), followed by non-migrated
        legacy records.

        Returns:
            De-duplicated list of
            :class:`~oompah.release_delivery_store.ReleaseDelivery` objects.

        Raises:
            :class:`~oompah.release_delivery_store.LedgerParseError`:
                When the ledger file is malformed.
        """
        # 1. All ledger entries.
        ledger = self._store.read_ledger()
        ledger_entries = list(ledger.deliveries)

        # 2. Build global migrated_from set.
        migrated_from_set: set[str] = {
            e.migrated_from for e in ledger_entries if e.migrated_from
        }

        # 3. Scan all issues.
        try:
            all_issues = self._tracker.fetch_all_issues()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "release_delivery_adapter: fetch_all_issues failed: %s — "
                "returning ledger-only view",
                exc,
            )
            return ledger_entries

        result: list[ReleaseDelivery] = list(ledger_entries)
        for issue in all_issues:
            legacy_addendums = self._fetch_legacy_addendums(issue.identifier)
            if not legacy_addendums:
                continue
            source_kind = _infer_source_kind(issue.issue_type)
            for addendum in legacy_addendums:
                if addendum.id in migrated_from_set:
                    continue
                synthetic = _addendum_to_delivery(
                    addendum,
                    issue.identifier,
                    source_kind,
                    self._project_id,
                )
                result.append(synthetic)
                # Track locally so we don't add the same addendum twice if it
                # appears on multiple issues (should not happen, but be safe).
                migrated_from_set.add(addendum.id)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_legacy_addendums(
        self,
        identifier: str,
    ) -> list[ReleaseAddendum]:
        """Return the legacy addendums for *identifier* from task metadata.

        Returns an empty list on any error.

        Args:
            identifier: Source task or epic identifier.

        Returns:
            Parsed legacy addendum list (may be empty).
        """
        try:
            meta = self._tracker.get_metadata(identifier)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_delivery_adapter: get_metadata failed for %s: %s",
                identifier,
                exc,
            )
            return []
        raw = meta.get("oompah.release_addendums")
        return _parse_legacy_addendums_safe(raw, identifier)

    def _fetch_source_kind(self, identifier: str) -> SourceKind:
        """Return the source kind for *identifier* by fetching the issue.

        Defaults to :attr:`~oompah.release_delivery_store.SourceKind.TASK`
        when the issue cannot be retrieved.

        Args:
            identifier: Source task or epic identifier.

        Returns:
            Inferred :class:`~oompah.release_delivery_store.SourceKind`.
        """
        try:
            issue = self._tracker.fetch_issue_detail(identifier)
            if issue is not None:
                return _infer_source_kind(issue.issue_type)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "release_delivery_adapter: fetch_issue_detail failed for %s: %s",
                identifier,
                exc,
            )
        return SourceKind.TASK
