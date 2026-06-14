"""Intake workflow transition gate for status promotions.

This module provides a **second-layer** authorization check that runs *after*
:func:`oompah.label_auth.is_authorized_status_actor` confirms that the actor
is allowed to touch ``oompah:status:*`` labels at all.

Even an authorized actor cannot bypass the intake workflow:

* **Proposed → Backlog** requires that the issue has passed the readiness
  validator, unless the actor is a project owner who explicitly overrides.

* **Proposed/Backlog → Open** requires project-owner authorization.
  Only a project owner or the oompah bot may make an issue dispatchable.

These gates apply uniformly across GitHub label-webhook events, the dashboard
API (``PATCH /api/v1/issues/{identifier}``), CLI/task APIs, and the polling
reconciliation path.

Design
------
:func:`check_intake_transition` is the public entry point.  Callers pass the
*from* and *to* status, the actor login, the project, and optional readiness /
approval flags. Readiness defaults to ``False`` — the conservative safe
default until intake validation has run.

The function returns a :class:`TransitionGateResult` that callers use to
decide whether to allow or revert the transition and what message to post.

Integration points
------------------
``oompah.server`` — webhook handler (``_handle_webhook_event``):
    After the actor-auth check for ``issues.labeled`` events, call
    :func:`check_intake_transition` with the resolved from-status.  If the
    gate rejects, start the revert thread with the gate message.

``oompah.server`` — PATCH API (``api_update_issue``):
    Before writing the status update, call :func:`check_intake_transition`.
    Return HTTP 403 when the gate rejects.

Polling:
    The ``_untrusted_status_issues`` ledger in ``github_tracker.py`` (from
    PR #270) already prevents dispatch of issues with untrusted status labels.
    When the gate rejects a webhook event the same ledger entry is written, so
    polling cannot promote the issue.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any

# ---------------------------------------------------------------------------
# Gate type constants
# ---------------------------------------------------------------------------

#: Gate applied to ``Proposed`` → ``Backlog`` transitions.
#: Requires readiness, or owner override.
GATE_PROPOSED_TO_BACKLOG = "proposed_to_backlog"

#: Gate applied to any → ``Open`` transitions from ``Proposed`` or ``Backlog``.
#: Requires project-owner authorization.
GATE_TO_OPEN = "to_open"

# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

_PROPOSED_KEY = "proposed"
_BACKLOG_KEY = "backlog"
_OPEN_KEY = "open"


def _status_key(status: str | None) -> str:
    """Normalise a status string for case-insensitive comparison."""
    return (status or "").strip().lower()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class TransitionGateResult:
    """Outcome of a transition gate check.

    Attributes:
        allowed: ``True`` when the transition may proceed.
        gate: Which gate was evaluated (one of the ``GATE_*`` constants), or
              ``None`` when no gate applies to this transition.
        reason: Human-readable explanation of why the transition was rejected
                (or an empty string when *allowed* is ``True``).
        remedy: Actionable guidance posted on the issue when the transition is
                rejected.
        is_owner_override: ``True`` when the transition was allowed because the
                           actor is a project owner overriding the gate.
    """

    allowed: bool
    gate: str | None = None
    reason: str = ""
    remedy: str = ""
    is_owner_override: bool = False


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_transition_gate(
    from_status: str | None,
    to_status: str | None,
) -> str | None:
    """Return the gate type for a status transition, or ``None`` if ungated.

    Only transitions *from* or *through* the intake workflow (``Proposed``,
    ``Backlog``) to more-advanced states are gated.

    Examples::

        >>> get_transition_gate("Proposed", "Backlog")
        'proposed_to_backlog'
        >>> get_transition_gate("Proposed", "Open")
        'to_open'
        >>> get_transition_gate("Backlog", "Open")
        'to_open'
        >>> get_transition_gate("Open", "In Progress")
        None
        >>> get_transition_gate(None, "Backlog")
        None
    """
    from_key = _status_key(from_status)
    to_key = _status_key(to_status)

    if from_key == _PROPOSED_KEY and to_key == _BACKLOG_KEY:
        return GATE_PROPOSED_TO_BACKLOG

    if from_key in (_PROPOSED_KEY, _BACKLOG_KEY) and to_key == _OPEN_KEY:
        return GATE_TO_OPEN

    return None


def is_project_owner(actor_login: str, project: Any) -> bool:
    """Return ``True`` when *actor_login* is a project owner.

    A project owner is:

    1. The ``status_actor_login`` of *project* (case-insensitive).
    2. The ``tracker_owner`` of *project* (case-insensitive, legacy).
    3. Any login in ``project.status_label_authorized_logins`` (case-insensitive).

    The oompah bot login is *not* included here intentionally — bot actions
    are handled separately via the *is_bot* flag in
    :func:`check_intake_transition`.

    Args:
        actor_login: The GitHub login of the actor.
        project: A :class:`~oompah.models.Project` instance or any object
                 with ``status_actor_login``, ``tracker_owner`` and
                 ``status_label_authorized_logins`` attributes.

    Returns:
        ``True`` when the actor is a project owner.
    """
    if not actor_login or project is None:
        return False

    actor_lower = actor_login.strip().lower()

    status_actor_login = getattr(project, "status_actor_login", None)
    if (
        isinstance(status_actor_login, str)
        and status_actor_login.strip().lower() == actor_lower
    ):
        return True

    tracker_owner = getattr(project, "tracker_owner", None)
    if isinstance(tracker_owner, str) and tracker_owner.strip().lower() == actor_lower:
        return True

    authorized = getattr(project, "status_label_authorized_logins", None) or []
    if isinstance(authorized, str) or not isinstance(authorized, Iterable):
        authorized = []
    for login in authorized:
        if isinstance(login, str) and login.strip().lower() == actor_lower:
            return True

    return False


def check_intake_transition(
    from_status: str | None,
    to_status: str | None,
    actor_login: str,
    project: Any,
    *,
    issue_is_ready: bool = False,
    issue_has_requestor_approval: bool = False,
    is_bot: bool = False,
) -> TransitionGateResult:
    """Check whether a status transition may proceed under the intake gate rules.

    This function is the **second-layer** check for sensitive status
    transitions.  It is called *after*
    :func:`~oompah.label_auth.is_authorized_status_actor` has already
    confirmed the actor may touch ``oompah:status:*`` labels at all.

    Gate rules
    ----------
    * **Proposed → Backlog** (``GATE_PROPOSED_TO_BACKLOG``):

      - *Allowed* when ``issue_is_ready=True``.
      - *Allowed* when the actor is a project owner (owner override; recorded
        via :attr:`TransitionGateResult.is_owner_override`).
      - *Allowed* when the oompah bot is the actor (``is_bot=True``).
      - *Rejected* otherwise.

    * **Proposed/Backlog → Open** (``GATE_TO_OPEN``):

      - *Allowed* when the actor is a project owner or the oompah bot.
      - *Rejected* for everyone else.

    * All other transitions are *allowed* unconditionally (no gate applies).

    Args:
        from_status: The issue's status *before* the transition.
        to_status: The target status.
        actor_login: The GitHub login of the actor requesting the transition.
        project: A :class:`~oompah.models.Project` instance providing owner
                 information.
        issue_is_ready: ``True`` when the issue has passed the readiness
                        validator.  Defaults to ``False`` (conservative).
        issue_has_requestor_approval: ``True`` when the requestor has
                                      approved an oompah-created proposal.
                                      Retained for compatibility; ordinary
                                      Proposed → Backlog promotion no longer
                                      requires it.
        is_bot: ``True`` when the actor is the oompah bot.  Bot transitions
                are always trusted.

    Returns:
        A :class:`TransitionGateResult` indicating whether the transition is
        allowed, and if not, why and how to fix it.

    Examples::

        >>> from unittest.mock import MagicMock
        >>> project = MagicMock()
        >>> project.tracker_owner = "alice"
        >>> project.status_label_authorized_logins = []

        # Owner override — always allowed
        >>> check_intake_transition("Proposed", "Backlog", "alice", project).allowed
        True

        # Bot — always allowed
        >>> check_intake_transition("Proposed", "Backlog", "bot", project, is_bot=True).allowed
        True

        # Non-owner without readiness/approval — rejected
        >>> r = check_intake_transition("Proposed", "Backlog", "bob", project)
        >>> r.allowed
        False
        >>> r.gate
        'proposed_to_backlog'

        # Ready non-owner — allowed
        >>> check_intake_transition(
        ...     "Proposed", "Backlog", "bob", project,
        ...     issue_is_ready=True
        ... ).allowed
        True
    """
    gate = get_transition_gate(from_status, to_status)

    if gate is None:
        return TransitionGateResult(allowed=True)

    # Bot transitions are always trusted.
    if is_bot:
        return TransitionGateResult(allowed=True, gate=gate)

    owner = is_project_owner(actor_login, project)

    # -----------------------------------------------------------------------
    # Gate: Proposed → Backlog
    # -----------------------------------------------------------------------
    if gate == GATE_PROPOSED_TO_BACKLOG:
        if issue_is_ready:
            return TransitionGateResult(allowed=True, gate=gate)

        if owner:
            return TransitionGateResult(
                allowed=True,
                gate=gate,
                is_owner_override=True,
                reason=(
                    f"Owner override: @{actor_login} promoted Proposed → Backlog "
                    f"without readiness check."
                ),
            )

        # Rejected: identify which requirements are missing.
        missing: list[str] = []
        if not issue_is_ready:
            missing.append("readiness validation")

        missing_str = " and ".join(missing)
        return TransitionGateResult(
            allowed=False,
            gate=gate,
            reason=(
                f"Proposed → Backlog rejected: missing {missing_str}. "
                f"The issue has not yet passed {missing_str}."
            ),
            remedy=(
                "To promote this issue to Backlog:\n"
                "1. Ensure all required fields are filled in (description, "
                "acceptance criteria, etc.).\n"
                "2. Wait for oompah intake validation to pass.\n"
                "3. A project owner can override by applying the label directly."
            ),
        )

    # -----------------------------------------------------------------------
    # Gate: Proposed/Backlog → Open
    # -----------------------------------------------------------------------
    if gate == GATE_TO_OPEN:
        if owner:
            return TransitionGateResult(allowed=True, gate=gate)

        from_display = (from_status or "current state").title()
        return TransitionGateResult(
            allowed=False,
            gate=gate,
            reason=(
                f"{from_display} → Open rejected: only a project owner may "
                f"promote work to Open (dispatchable)."
            ),
            remedy=(
                "Ask a project owner to promote this issue to Open. "
                "Non-owners cannot make issues dispatchable directly."
            ),
        )

    # Unknown gate type — fail closed (conservative).
    return TransitionGateResult(  # pragma: no cover
        allowed=False,
        gate=gate,
        reason=f"Unknown gate type {gate!r} — transition blocked as a precaution.",
    )


def build_gate_rejection_comment(
    result: TransitionGateResult,
    actor_login: str,
    from_status: str | None,
    to_status: str | None,
) -> str:
    """Build the comment body to post when a transition gate rejects a change.

    Args:
        result: The :class:`TransitionGateResult` from :func:`check_intake_transition`.
        actor_login: The GitHub login of the actor whose change was rejected.
        from_status: The issue's status before the rejected transition.
        to_status: The target status that was rejected.

    Returns:
        A Markdown-formatted comment string.
    """
    from_display = (from_status or "current state").title()
    to_display = (to_status or "target state").title()

    lines = [
        f"⛔ **Intake gate: {from_display} → {to_display} blocked**",
        "",
        f"@{actor_login} attempted to advance this issue from "
        f"*{from_display}* to *{to_display}*, but this transition requires "
        f"additional approval.",
        "",
    ]

    if result.reason:
        lines += [f"**Why:** {result.reason}", ""]

    if result.remedy:
        lines += [f"**Next steps:**\n{result.remedy}", ""]

    return "\n".join(lines)


def build_owner_override_comment(
    actor_login: str,
    from_status: str | None,
    to_status: str | None,
) -> str:
    """Build an audit comment for an owner intake override."""
    from_display = (from_status or "current state").title()
    to_display = (to_status or "target state").title()
    return (
        f"**Intake owner override recorded**\n\n"
        f"@{actor_login} advanced this issue from *{from_display}* "
        f"to *{to_display}* as a project-owner override. "
        "The override is recorded so polling can trust this status."
    )
