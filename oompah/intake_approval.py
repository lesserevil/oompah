"""Requestor approval detection for the oompah intake workflow.

Defines the explicit approval action for proposed GitHub issues.  Only the
original requestor, an authorized project owner, or the oompah bot may approve
an intake proposal.  Ambiguous positive-sounding comments are deliberately
ignored — only the explicit ``/oompah approve`` command counts.

Approval is tied to a specific proposal *fingerprint* (a stable hash of the
issue body at approval time).  Material edits to the issue body invalidate a
prior approval; the requestor or an owner must re-approve the updated proposal.

Design decisions
----------------
- The command token is ``/oompah approve`` (case-insensitive) on its own line or
  at the start of a comment.  Surrounding whitespace is stripped.  Additional
  text on the same line after the command is allowed and ignored (e.g.
  ``/oompah approve LGTM``).
- Authorization is checked against: (1) the oompah bot login, (2) the original
  requestor (issue opener), (3) ``project.tracker_owner``, and (4) entries in
  ``project.status_label_authorized_logins``.
- The *proposal fingerprint* is a SHA-256 digest of the normalized issue body
  text (stripped of surrounding whitespace) so that cosmetic whitespace changes
  do not trigger re-approval.

Usage::

    from oompah.intake_approval import (
        IntakeApproval,
        is_approval_command,
        is_authorized_approver,
        build_intake_approval,
        compute_proposal_fingerprint,
        is_approval_stale,
    )

    if is_approval_command(comment_body):
        approval = build_intake_approval(
            actor=comment_author,
            requestor=issue_opener,
            proposal_fingerprint=compute_proposal_fingerprint(issue_body),
            project=project,
        )
        if approval is None:
            # actor is not authorized — ignore
            ...
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # avoid circular imports at module level

from oompah.label_auth import get_bot_login

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The exact slash-command token that triggers an intake approval.
#: Matched case-insensitively.
_APPROVE_TOKEN = "/oompah approve"

#: Compiled pattern: ``/oompah approve`` at the start of a line (or the start
#: of the full text), optionally followed by anything on the same line.
_APPROVE_RE = re.compile(
    r"(?:^|\n)\s*/oompah\s+approve(?:\s|$)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class IntakeApproval:
    """Recorded approval of an intake proposal.

    Attributes:
        actor: GitHub login of the person who approved.
        approved_at: ISO-8601 UTC timestamp of approval.
        proposal_fingerprint: SHA-256 hex digest of the issue body at the time
            of approval.  A mismatch with the current body fingerprint means
            the approval is stale and must be re-issued.
        is_owner_override: ``True`` when the approver is an authorized project
            owner acting on behalf of the original requestor.  ``False`` when
            the approver is the requestor themselves (or the oompah bot).
    """

    actor: str
    approved_at: str
    proposal_fingerprint: str
    is_owner_override: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON storage."""
        return {
            "actor": self.actor,
            "approved_at": self.approved_at,
            "proposal_fingerprint": self.proposal_fingerprint,
            "is_owner_override": self.is_owner_override,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntakeApproval":
        """Deserialize from a plain dict (e.g. from JSON metadata)."""
        return cls(
            actor=str(d.get("actor", "")),
            approved_at=str(d.get("approved_at", "")),
            proposal_fingerprint=str(d.get("proposal_fingerprint", "")),
            is_owner_override=bool(d.get("is_owner_override", False)),
        )


# ---------------------------------------------------------------------------
# Comment parsing
# ---------------------------------------------------------------------------


def is_approval_command(body: str) -> bool:
    """Return ``True`` when *body* contains an explicit ``/oompah approve`` command.

    The match is case-insensitive and requires ``/oompah approve`` to appear
    either at the start of the text or immediately after a newline, optionally
    preceded by whitespace.  This deliberately excludes:

    - Comments that only say "looks good", "LGTM", "approved", ":+1:", etc.
    - Comments where ``/oompah approve`` appears in the middle of a sentence.

    Args:
        body: The raw text of a GitHub issue comment.

    Returns:
        ``True`` when the comment is an explicit approval command.

    Examples::

        >>> is_approval_command("/oompah approve")
        True
        >>> is_approval_command("/OOMPAH APPROVE")
        True
        >>> is_approval_command("Looks good, /oompah approve")
        False  # not at the start of the text or a line
        >>> is_approval_command("LGTM")
        False
    """
    if not body:
        return False
    return bool(_APPROVE_RE.search(body))


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def is_authorized_approver(
    actor_login: str,
    requestor_login: str,
    project: Any,
) -> tuple[bool, bool]:
    """Return whether *actor_login* is authorized to approve an intake proposal.

    Authorization rules (in priority order):

    1. The oompah bot (``get_bot_login()``) is always authorized.
    2. The original requestor (``requestor_login``) is always authorized.
    3. ``project.tracker_owner`` (case-insensitive) is authorized as an owner
       override.
    4. Any login in ``project.status_label_authorized_logins`` is authorized
       as an owner override.

    Args:
        actor_login: GitHub login of the user attempting to approve.
        requestor_login: GitHub login of the original issue reporter.
        project: A :class:`~oompah.models.Project` instance (or any object
            with ``tracker_owner`` and ``status_label_authorized_logins``
            attributes).  May be ``None``; if so, only the bot and requestor
            are checked.

    Returns:
        A ``(is_authorized, is_owner_override)`` tuple.  ``is_authorized``
        is ``True`` when the actor is allowed to approve.
        ``is_owner_override`` is ``True`` when the actor is a project owner
        rather than the requestor themselves (or the bot).
    """
    if not actor_login:
        return False, False

    actor_lower = actor_login.strip().lower()
    requestor_lower = (requestor_login or "").strip().lower()

    # Bot is always authorized, not an override.
    if actor_lower == get_bot_login().strip().lower():
        return True, False

    # Original requestor is authorized, not an override.
    if requestor_lower and actor_lower == requestor_lower:
        return True, False

    # Project owner checks — authorized, but counts as an override.
    if project is not None:
        tracker_owner = getattr(project, "tracker_owner", None)
        if (
            isinstance(tracker_owner, str)
            and tracker_owner.strip().lower() == actor_lower
        ):
            return True, True

        authorized = getattr(project, "status_label_authorized_logins", None) or []
        for login in authorized:
            if isinstance(login, str) and login.strip().lower() == actor_lower:
                return True, True

    return False, False


# ---------------------------------------------------------------------------
# Fingerprinting and staleness
# ---------------------------------------------------------------------------


def compute_proposal_fingerprint(body: str) -> str:
    """Return a stable SHA-256 fingerprint of *body*.

    The fingerprint is computed over the *normalized* body (stripped of
    leading/trailing whitespace) so that purely cosmetic edits (adding a
    trailing newline) do not invalidate a prior approval.

    Args:
        body: Issue body text (the description/proposal to fingerprint).

    Returns:
        A 64-character lowercase hex string (SHA-256 digest).
    """
    normalized = (body or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_approval_stale(approval: IntakeApproval, current_fingerprint: str) -> bool:
    """Return ``True`` when *approval* no longer matches *current_fingerprint*.

    A stale approval means the issue body was materially edited after the
    approval was recorded.  The requestor or an authorized owner must
    re-approve the updated proposal.

    Args:
        approval: A previously-recorded :class:`IntakeApproval`.
        current_fingerprint: The current :func:`compute_proposal_fingerprint`
            of the issue body.

    Returns:
        ``True`` when ``approval.proposal_fingerprint != current_fingerprint``.
    """
    return approval.proposal_fingerprint != current_fingerprint


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_intake_approval(
    actor: str,
    requestor: str,
    proposal_fingerprint: str,
    project: Any,
    *,
    approved_at: str | None = None,
) -> IntakeApproval | None:
    """Create an :class:`IntakeApproval` if *actor* is authorized to approve.

    This is the primary entry point for recording an approval.  Pass the
    comment author as *actor*, the issue opener as *requestor*, and the current
    :func:`compute_proposal_fingerprint` of the issue body as
    *proposal_fingerprint*.

    Args:
        actor: GitHub login of the user attempting to approve.
        requestor: GitHub login of the original issue reporter.
        proposal_fingerprint: SHA-256 hex digest of the current issue body.
        project: A :class:`~oompah.models.Project` instance (or compatible
            object).  May be ``None``.
        approved_at: Optional ISO-8601 timestamp override.  When ``None``,
            the current UTC time is used.

    Returns:
        An :class:`IntakeApproval` when the actor is authorized, ``None``
        otherwise.
    """
    authorized, is_owner_override = is_authorized_approver(actor, requestor, project)
    if not authorized:
        return None

    timestamp = approved_at or datetime.now(timezone.utc).isoformat()
    return IntakeApproval(
        actor=actor,
        approved_at=timestamp,
        proposal_fingerprint=proposal_fingerprint,
        is_owner_override=is_owner_override,
    )
