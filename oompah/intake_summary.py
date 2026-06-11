"""Dashboard-facing intake readiness summaries.

The persisted intake schema is stored as the ``intake`` key in oompah-owned
issue metadata.  This module converts that raw metadata into a stable, compact
JSON shape for board cards and issue details.
"""

from __future__ import annotations

from typing import Any

from oompah.statuses import PROPOSED, canonicalize_status


_STATE_LABELS = {
    "missing-info": "Missing info",
    "awaiting-requestor-approval": "Awaiting requestor",
    "awaiting-owner-review": "Awaiting owner",
    "ready-for-backlog": "Ready for Backlog",
}


def _normal_value(value: Any, default: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    return text or default


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _next_action(
    state: str,
    *,
    missing_fields: list[str],
    scope: str,
    last_validator_result: str | None,
) -> str:
    if state == "missing-info":
        return "Requestor needs to add: " + ", ".join(missing_fields) + "."
    if state == "awaiting-requestor-approval":
        return "Requestor must approve the proposed scope, or an owner must override."
    if state == "ready-for-backlog":
        return "Move this issue to Backlog."
    if scope == "needs_decomposition":
        return "Owner needs to review or complete decomposition before Backlog."
    if last_validator_result != "pass":
        return "Owner needs to run or review intake validation."
    return "Owner review is required before this issue can move to Backlog."


def _card_text(
    state: str,
    *,
    missing_fields: list[str],
    owner_override: bool,
    decomposition_status: str,
) -> str:
    if state == "missing-info":
        return ", ".join(missing_fields[:2]) + (" +" if len(missing_fields) > 2 else "")
    if state == "awaiting-requestor-approval":
        return "scope approval needed"
    if state == "ready-for-backlog":
        return "promote when ready"
    if owner_override:
        return "override recorded"
    if decomposition_status not in {"", "not_needed"}:
        return f"decomposition {decomposition_status.replace('_', ' ')}"
    return "validation review"


def build_intake_summary(
    raw: Any,
    *,
    issue_state: str | None = None,
) -> dict[str, Any] | None:
    """Return a UI-ready intake summary for an issue.

    ``None`` is returned for non-Proposed issues that do not carry intake
    metadata.  Proposed issues get a default "awaiting owner review" summary
    even before the validator has written metadata, so the detail pane still
    explains the current intake state.
    """
    is_proposed = canonicalize_status(issue_state) == PROPOSED
    if not isinstance(raw, dict):
        if not is_proposed:
            return None
        raw = {}

    missing_fields = _string_list(raw.get("missing_fields"))
    scope = _normal_value(raw.get("scope"), "unknown")
    requestor_approved = bool(raw.get("requestor_approved", False))
    owner_override = bool(raw.get("owner_override", False))
    decomposition_status = _normal_value(
        raw.get("decomposition_status"),
        "not_needed",
    )
    last_validator_result = _optional_string(raw.get("last_validator_result"))
    if last_validator_result is not None:
        last_validator_result = last_validator_result.lower()

    ready_for_backlog = (
        not missing_fields
        and scope != "needs_decomposition"
        and (requestor_approved or owner_override)
        and last_validator_result == "pass"
    )

    if missing_fields:
        state = "missing-info"
    elif ready_for_backlog:
        state = "ready-for-backlog"
    elif (
        scope != "needs_decomposition"
        and last_validator_result == "pass"
        and not (requestor_approved or owner_override)
    ):
        state = "awaiting-requestor-approval"
    else:
        state = "awaiting-owner-review"

    return {
        "state": state,
        "label": _STATE_LABELS[state],
        "next_action": _next_action(
            state,
            missing_fields=missing_fields,
            scope=scope,
            last_validator_result=last_validator_result,
        ),
        "card_text": _card_text(
            state,
            missing_fields=missing_fields,
            owner_override=owner_override,
            decomposition_status=decomposition_status,
        ),
        "ready_for_backlog": ready_for_backlog,
        "missing_fields": missing_fields,
        "scope": scope,
        "requestor_approval_state": (
            "approved" if requestor_approved else "awaiting"
        ),
        "requestor_approved": requestor_approved,
        "requestor_actor": _optional_string(raw.get("requestor_actor")),
        "requestor_approved_at": _optional_string(raw.get("requestor_approved_at")),
        "owner_override_state": "active" if owner_override else "none",
        "owner_override": owner_override,
        "owner_actor": _optional_string(raw.get("owner_actor")),
        "owner_override_at": _optional_string(raw.get("owner_override_at")),
        "decomposition_state": decomposition_status,
        "decomposition_status": decomposition_status,
        "last_validator_result": last_validator_result,
        "last_validated_at": _optional_string(raw.get("last_validated_at")),
    }
