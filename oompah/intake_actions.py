"""Permission checks and audit comments for GitHub issue intake actions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from oompah.label_auth import is_authorized_status_actor
from oompah.statuses import PROPOSED, canonicalize_status

REQUESTOR_APPROVE = "requestor_approve"
REQUEST_CHANGES = "request_changes"
OVERRIDE_READINESS = "override_readiness"
PROMOTE_TO_BACKLOG = "promote_to_backlog"

KNOWN_ACTIONS = frozenset(
    {
        REQUESTOR_APPROVE,
        REQUEST_CHANGES,
        OVERRIDE_READINESS,
        PROMOTE_TO_BACKLOG,
    }
)

_ACTION_ALIASES = {
    "approve-scope": REQUESTOR_APPROVE,
    "approve_scope": REQUESTOR_APPROVE,
    "requestor-approve": REQUESTOR_APPROVE,
    "requestor_approve": REQUESTOR_APPROVE,
    "requester-approve": REQUESTOR_APPROVE,
    "requester_approve": REQUESTOR_APPROVE,
    "request-changes": REQUEST_CHANGES,
    "request_changes": REQUEST_CHANGES,
    "override-readiness": OVERRIDE_READINESS,
    "override_readiness": OVERRIDE_READINESS,
    "promote-to-backlog": PROMOTE_TO_BACKLOG,
    "promote_to_backlog": PROMOTE_TO_BACKLOG,
}

_MARKER_PREFIX = "<!-- oompah:intake-action "
_MARKER_SUFFIX = " -->"


@dataclass(frozen=True)
class IntakePermission:
    """Decision for an actor attempting an intake action."""

    allowed: bool
    code: str = ""
    message: str = ""


def normalize_action(action: str | None) -> str | None:
    """Return the canonical intake action name, if *action* is known."""

    key = str(action or "").strip().lower().replace(" ", "-")
    return _ACTION_ALIASES.get(key)


def normalize_login(login: str | None) -> str:
    """Normalize a GitHub login for case-insensitive comparisons."""

    return str(login or "").strip().lower()


def issue_requestor_login(issue: Any) -> str:
    """Return the requestor login carried by a normalized issue, if present."""

    for attr in ("requestor_login", "reporter", "author"):
        value = getattr(issue, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_issue_requestor(actor_login: str | None, issue: Any) -> bool:
    """Return true when *actor_login* is the issue creator/requestor."""

    actor = normalize_login(actor_login)
    requestor = normalize_login(issue_requestor_login(issue))
    return bool(actor and requestor and actor == requestor)


def is_project_owner(actor_login: str | None, project: Any) -> bool:
    """Return true when *actor_login* can perform owner-only status actions."""

    return is_authorized_status_actor(str(actor_login or ""), project)


def is_proposed_issue(issue: Any) -> bool:
    """Return true when an issue is currently in the Proposed intake state."""

    return canonicalize_status(getattr(issue, "state", "")) == PROPOSED


def check_permission(
    action: str,
    actor_login: str | None,
    issue: Any,
    project: Any,
) -> IntakePermission:
    """Check whether *actor_login* may perform *action* on *issue*."""

    if action not in KNOWN_ACTIONS:
        return IntakePermission(False, "unknown_action", "Unknown intake action")

    actor = str(actor_login or "").strip()
    if not actor:
        return IntakePermission(False, "actor_required", "actor is required")

    if not is_proposed_issue(issue):
        return IntakePermission(
            False,
            "invalid_state",
            "Intake actions are only available for Proposed issues",
        )

    if action == REQUESTOR_APPROVE:
        if is_issue_requestor(actor, issue):
            return IntakePermission(True)
        return IntakePermission(
            False,
            "not_requestor",
            "Only the issue requestor can approve the proposed scope",
        )

    if is_project_owner(actor, project):
        return IntakePermission(True)

    return IntakePermission(
        False,
        "owner_required",
        "Only a project owner can perform this intake action",
    )


def action_permissions(issue: Any, project: Any, actor_login: str | None) -> dict[str, bool]:
    """Return all action booleans for *actor_login* on *issue*."""

    return {
        "can_requestor_approve": check_permission(
            REQUESTOR_APPROVE, actor_login, issue, project
        ).allowed,
        "can_request_changes": check_permission(
            REQUEST_CHANGES, actor_login, issue, project
        ).allowed,
        "can_override_readiness": check_permission(
            OVERRIDE_READINESS, actor_login, issue, project
        ).allowed,
        "can_promote_to_backlog": check_permission(
            PROMOTE_TO_BACKLOG, actor_login, issue, project
        ).allowed,
    }


def audit_marker(action: str, actor_login: str) -> str:
    """Return a machine-readable intake audit marker comment."""

    payload = {"action": action, "actor": str(actor_login or "").strip()}
    return _MARKER_PREFIX + json.dumps(payload, sort_keys=True) + _MARKER_SUFFIX


def build_audit_comment(
    action: str,
    actor_login: str,
    issue: Any,
    *,
    message: str | None = None,
) -> str:
    """Build the Markdown audit comment for a completed intake action."""

    actor = str(actor_login or "").strip()
    requestor = issue_requestor_login(issue)
    note = str(message or "").strip()

    lines = [audit_marker(action, actor)]
    if action == REQUESTOR_APPROVE:
        lines += [
            "",
            "Intake action: requestor scope approval",
            "",
            f"@{actor} approved the proposed scope for this issue.",
        ]
    elif action == REQUEST_CHANGES:
        lines += [
            "",
            "Intake action: changes requested",
            "",
            f"@{actor} requested changes before this issue moves to Backlog.",
        ]
    elif action == OVERRIDE_READINESS:
        lines += [
            "",
            "Intake action: readiness override",
            "",
            f"@{actor} recorded an owner readiness override for this issue.",
        ]
    elif action == PROMOTE_TO_BACKLOG:
        lines += [
            "",
            "Intake action: promoted to Backlog",
            "",
            f"@{actor} promoted this Proposed issue to Backlog.",
        ]
        if requestor:
            lines.append(f"Requestor: @{requestor}.")
    else:  # pragma: no cover - callers validate action first
        lines += ["", f"Intake action: {action}", "", f"Actor: @{actor}."]

    if note:
        lines += ["", note]

    return "\n".join(lines)


def parse_audit_marker(text: str | None) -> dict[str, str] | None:
    """Parse the first intake audit marker from comment text."""

    body = str(text or "")
    start = body.find(_MARKER_PREFIX)
    if start < 0:
        return None
    start += len(_MARKER_PREFIX)
    end = body.find(_MARKER_SUFFIX, start)
    if end < 0:
        return None
    try:
        payload = json.loads(body[start:end].strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    action = normalize_action(str(payload.get("action") or ""))
    actor = str(payload.get("actor") or "").strip()
    if not action or not actor:
        return None
    return {"action": action, "actor": actor}
