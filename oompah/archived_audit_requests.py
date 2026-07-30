"""Guarded Archived-audit requests for synchronous maintenance paths."""

import logging
import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from oompah.models import Issue
from oompah.statuses import ARCHIVED, TERMINAL_STATUSES, canonicalize_status
from oompah.terminal_audit import (
    ContributorIdentity,
    RequestState,
    TargetState,
    compute_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadata, TerminalAuditMetadataStore
from oompah.terminal_transition_coordinator import TerminalTransitionCoordinator
from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)


class _LegacyProjectStore:
    """Small lock provider for legacy callers without a ProjectStore."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def project_write_lock(self, _project_id: str) -> Any:
        return self._lock


_LEGACY_PROJECT_STORE = _LegacyProjectStore()


def request_archived_audit(
    issue: Issue,
    tracker: TrackerProtocol,
    project_id: str | None,
    disposition_reason: str,
    project_store: object | None = None,
    *,
    trigger_source: str = "maintenance",
) -> bool:
    """Queue one auditable retirement, never directly archive an issue.

    The disposition is mandatory evidence.  While an Archived audit is
    pending, later maintenance passes coalesce regardless of a changing clock
    value in the reason.  That makes retention bounded and prevents an
    automatic path from hiding unresolved work behind repeated requests.
    """
    reason = str(disposition_reason or "").strip()
    effective_project_id = str(
        project_id or getattr(issue, "project_id", None) or "legacy"
    ).strip()
    if not reason or not effective_project_id:
        logger.warning("Refusing archive audit for %s without disposition evidence", issue.identifier)
        return False
    if canonicalize_status(getattr(issue, "state", "") or "") == ARCHIVED:
        return False

    evidence_fingerprint = compute_evidence_fingerprint(
        requirements_text=reason,
        project_id=effective_project_id,
        task_id=issue.identifier,
    )
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store or _LEGACY_PROJECT_STORE,
    )
    try:
        result = coordinator.request_transition_sync(
            current_issue=issue,
            requested_target=TargetState.ARCHIVED,
            trigger_identity=ContributorIdentity("oompah", trigger_source),
            project_id=effective_project_id,
            evidence_fingerprint=evidence_fingerprint,
            coalesce_pending_target=True,
            ensure_validation_on_coalesce=True,
            queued_comment=(
                f"Queued Archived audit: {reason}. "
                "An auditor will review before the task is retired."
            ),
        )
    except Exception as exc:  # noqa: BLE001 - maintenance must fail closed
        logger.exception(
            "Failed to request archived audit for %s: %s",
            issue.identifier,
            exc,
        )
        return False

    if (
        result.success
        and result.status_staged
        and (not result.coalesced or result.status_repaired)
    ):
        flush_checkpoint = getattr(tracker, "flush_checkpoint", None)
        if callable(flush_checkpoint):
            try:
                flush_checkpoint(reason="queue archived audit")
            except Exception:  # noqa: BLE001 - leave the persisted request retryable
                logger.exception(
                    "Failed to flush queued archive audit for %s", issue.identifier
                )
                return False
        logger.info(
            "Queued Archived audit for %s (audit_id=%s, disposition=%s)",
            issue.identifier,
            result.audit_id,
            reason,
        )
        return True
    return False


def cancel_pending_archived_audit(
    issue: Issue,
    tracker: TrackerProtocol,
    project_id: str | None,
    reason: str,
    project_store: object | None = None,
) -> tuple[bool, str | None]:
    """Cancel a pending automatic archive and return its safe restore state.

    This is intentionally narrow: only pending/in-progress ``Archived``
    requests are cancelled.  The caller owns the tracker status restoration,
    using the returned pre-audit state when it is nonterminal.
    """
    effective_project_id = str(
        project_id or getattr(issue, "project_id", None) or "legacy"
    ).strip()
    if not effective_project_id:
        return False, None

    metadata_store = TerminalAuditMetadataStore(
        tracker,
        project_store or _LEGACY_PROJECT_STORE,
        effective_project_id,
    )
    previous_state: str | None = None
    cancelled = False

    def _cancel(document: TerminalAuditMetadata) -> TerminalAuditMetadata:
        nonlocal cancelled, previous_state
        chain = []
        for record in document.pending_chain:
            if (
                record.target_state == TargetState.ARCHIVED
                and record.request_state
                in (RequestState.PENDING, RequestState.IN_PROGRESS)
            ):
                previous_state = previous_state or record.previous_state
                cancelled = True
                chain.append(
                    replace(
                        record,
                        request_state=RequestState.CANCELLED,
                        updated_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            else:
                chain.append(record)
        return replace(document, pending_chain=chain)

    try:
        metadata_store.update(issue.identifier, _cancel)
    except Exception as exc:  # noqa: BLE001 - external reopen must fail closed
        logger.exception("Failed to cancel archive audit for %s: %s", issue.identifier, exc)
        return False, None

    if cancelled:
        try:
            tracker.add_comment(
                issue.identifier,
                f"Cancelled Archived audit: {reason}",
                author="oompah",
            )
        except Exception:  # noqa: BLE001 - cancellation is already durable
            logger.exception("Failed to post archive-audit cancellation for %s", issue.identifier)

    canonical_previous = canonicalize_status(previous_state or "")
    if not canonical_previous or canonical_previous in TERMINAL_STATUSES:
        previous_state = None
    return cancelled, previous_state
