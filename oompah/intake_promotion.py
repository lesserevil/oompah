"""Promotion helpers for the Proposed -> Backlog intake transition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from oompah.intake_approval import build_intake_approval, compute_proposal_fingerprint
from oompah.intake_schema import (
    DecompositionStatus,
    IntakeReadiness,
    IntakeScopeKind,
    ValidatorResult,
    intake_to_raw,
    parse_intake_metadata,
)
from oompah.statuses import BACKLOG, PROPOSED, canonicalize_status


@dataclass(frozen=True)
class IntakePromotionResult:
    """Result of a Proposed -> Backlog promotion attempt."""

    promoted: bool
    reason: str
    audit_comment: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_readiness(tracker: Any, identifier: str) -> IntakeReadiness:
    meta = tracker.get_metadata(identifier)
    return parse_intake_metadata(meta.get("oompah.intake") or meta.get("intake"))


def _save_readiness(
    tracker: Any,
    identifier: str,
    readiness: IntakeReadiness,
) -> None:
    tracker.set_metadata_field(identifier, "oompah.intake", intake_to_raw(readiness))


def record_intake_approval(
    tracker: Any,
    identifier: str,
    *,
    issue_description: str,
    actor: str,
    requestor: str,
    project: Any,
    approved_at: str | None = None,
) -> IntakeReadiness | None:
    """Record a requestor approval or owner override in intake metadata.

    Returns the updated readiness metadata when *actor* is authorized to approve
    the proposal. Returns ``None`` for non-requestors/non-owners.
    """
    approval = build_intake_approval(
        actor=actor,
        requestor=requestor,
        proposal_fingerprint=compute_proposal_fingerprint(issue_description),
        project=project,
        approved_at=approved_at,
    )
    if approval is None:
        return None

    readiness = _load_readiness(tracker, identifier)
    if approval.is_owner_override:
        readiness.owner_override = True
        readiness.owner_override_at = approval.approved_at
        readiness.owner_actor = approval.actor
    else:
        readiness.requestor_approved = True
        readiness.requestor_approved_at = approval.approved_at
        readiness.requestor_actor = approval.actor

    if (
        readiness.scope == IntakeScopeKind.NEEDS_DECOMPOSITION
        and readiness.decomposition_status == DecompositionStatus.PROPOSED
    ):
        readiness.decomposition_status = DecompositionStatus.ACCEPTED

    _save_readiness(tracker, identifier, readiness)
    return readiness


def apply_owner_override(
    tracker: Any,
    identifier: str,
    *,
    actor: str,
    overridden_at: str | None = None,
) -> IntakeReadiness:
    """Persist an explicit owner override before promotion."""
    readiness = _load_readiness(tracker, identifier)
    readiness.owner_override = True
    readiness.owner_override_at = overridden_at or _now_iso()
    readiness.owner_actor = actor
    _save_readiness(tracker, identifier, readiness)
    return readiness


def _promotion_reason(readiness: IntakeReadiness) -> str | None:
    if readiness.owner_override:
        return "owner_override"
    if readiness.is_ready:
        return "validator_passed"
    return None


def _blocked_reason(readiness: IntakeReadiness) -> str:
    missing: list[str] = []
    if readiness.missing_fields:
        missing.append("missing_fields=" + ",".join(readiness.missing_fields))
    if not readiness.is_ready:
        missing.append("readiness=false")
    return "; ".join(missing) or "promotion gates not satisfied"


def build_promotion_audit_comment(
    readiness: IntakeReadiness,
    *,
    reason: str,
) -> str:
    """Build the audit comment for a successful intake promotion."""
    if reason == "owner_override":
        actor = readiness.owner_actor or "project owner"
        detail = f"owner override by @{actor}"
    elif reason == "validator_passed":
        detail = "intake validation passed"
    else:
        actor = readiness.requestor_actor or "requestor"
        detail = f"readiness passed and requestor approval by @{actor}"

    return (
        "Intake promotion: moved this issue from Proposed to Backlog.\n\n"
        f"Reason: {detail}.\n"
        f"- readiness: {'true' if readiness.is_ready else 'false'}\n"
        f"- requestor_approved: {'true' if readiness.requestor_approved else 'false'}\n"
        f"- owner_override: {'true' if readiness.owner_override else 'false'}\n\n"
        "Backlog is not dispatchable. A project owner must move this issue to "
        "Open when it is ready for agent dispatch."
    )


def build_promotion_blocked_comment(
    readiness: IntakeReadiness,
    *,
    reason: str,
    requestor: str | None = None,
) -> str:
    """Build an explanatory comment when approval is recorded but promotion is blocked."""

    actor = str(requestor or "").strip()
    prefix = f"@{actor}, " if actor else ""
    remaining: list[str] = []

    if readiness.missing_fields:
        remaining.append("missing fields: " + ", ".join(readiness.missing_fields))
    if readiness.scope == IntakeScopeKind.NEEDS_DECOMPOSITION:
        remaining.append("scope still requires decomposition before Backlog")
    if readiness.last_validator_result is None:
        remaining.append("readiness validation has not passed yet")
    elif readiness.last_validator_result != ValidatorResult.PASS:
        remaining.append("latest readiness validation did not pass")
    lines = [
        f"{prefix}intake approval has been recorded, but this issue is still Proposed.",
        "",
        "Promotion to Backlog is blocked because intake readiness is incomplete.",
        "",
        f"Reason: {reason}.",
        f"- readiness: {'true' if readiness.is_ready else 'false'}",
        f"- requestor_approved: {'true' if readiness.requestor_approved else 'false'}",
        f"- owner_override: {'true' if readiness.owner_override else 'false'}",
    ]
    if remaining:
        lines += ["", "Remaining requirements:"]
        lines += [f"- {item}" for item in remaining]
    lines += [
        "",
        "Once those items are resolved, oompah can move this issue to Backlog.",
    ]
    return "\n".join(lines)


def promote_proposed_issue_to_backlog(
    tracker: Any,
    identifier: str,
    *,
    current_status: str | None,
    owner_override_actor: str | None = None,
    author: str = "oompah",
    post_audit_comment: bool = True,
) -> IntakePromotionResult:
    """Promote an issue from Proposed to Backlog when intake gates allow it."""
    if canonicalize_status(current_status) != PROPOSED:
        return IntakePromotionResult(
            promoted=False,
            reason=f"issue is {current_status or 'unknown'}, not Proposed",
        )

    if owner_override_actor:
        readiness = apply_owner_override(
            tracker,
            identifier,
            actor=owner_override_actor,
        )
    else:
        readiness = _load_readiness(tracker, identifier)

    reason = _promotion_reason(readiness)
    if reason is None:
        return IntakePromotionResult(
            promoted=False,
            reason=_blocked_reason(readiness),
        )

    tracker.update_issue(identifier, status=BACKLOG)
    audit_comment = build_promotion_audit_comment(readiness, reason=reason)
    if post_audit_comment:
        tracker.add_comment(identifier, audit_comment, author=author)
    return IntakePromotionResult(
        promoted=True,
        reason=reason,
        audit_comment=audit_comment if post_audit_comment else None,
    )
