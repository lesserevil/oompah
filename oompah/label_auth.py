"""Authorization model for ``oompah:status:*`` label transitions on GitHub issues.

GitHub does not lock individual labels, so any user with the repository's
``Triage`` role (or higher) can apply an ``oompah:status:open`` label and
make an issue dispatchable without project-owner approval.  This module
provides the authority check that oompah uses before trusting a label-change
event.

Design
------
An ``oompah:status:*`` label change is **authorized** when the actor is:

1. The oompah bot itself (the GitHub identity that oompah uses to authenticate
   API calls).  Bot identity is read from the ``OOMPAH_BOT_LOGIN`` environment
   variable; the default is ``"oompah"``.

2. The project's GitHub tracker owner, when configured.  This covers common
   deployments where oompah writes labels through the repository owner's PAT
   and GitHub reports the label actor as that owner login.

3. A project owner listed in
   :attr:`~oompah.models.Project.status_label_authorized_logins`.  This list
   defaults to empty.

The bot-identity check is the primary guard for normal lifecycle transitions
(claim → In Progress, merge → Merged, etc.).  The project-owner allowlist
covers cases where a human operator needs to manually advance an issue.

Sensitive transitions
---------------------
Not all status changes are equally sensitive.  Moving an issue from
``Proposed`` or ``Backlog`` to ``Open`` (or any other dispatchable status)
directly makes it eligible for agent dispatch.  That class of transition
requires authorization.  Status changes to non-dispatchable states (e.g.
``In Progress`` → ``Done``) are always performed by oompah itself in normal
operation, so the same authorization model still applies but the risk is lower.

For simplicity this module flags **all** ``oompah:status:*`` label changes as
requiring authorization, with the following carve-out: status changes
performed by oompah itself are implicitly trusted because ``get_bot_login()``
matches the actor.

Usage::

    from oompah.label_auth import (
        get_bot_login,
        is_status_label,
        is_authorized_status_actor,
        label_name_to_status,
    )

    if is_status_label(label_name):
        if not is_authorized_status_actor(actor_login, project):
            # revert + audit trail
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # avoid circular import of Project at module level

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Prefix shared by all oompah status labels.
STATUS_LABEL_PREFIX = "oompah:status:"

#: Environment variable that holds the GitHub login used by the oompah bot.
#: Defaults to ``"oompah"``.  Set ``OOMPAH_BOT_LOGIN`` in your environment
#: when running oompah under a different GitHub App or PAT identity.
_BOT_LOGIN_ENV = "OOMPAH_BOT_LOGIN"
_DEFAULT_BOT_LOGIN = "oompah"

# Mapping from ``oompah:status:<slug>`` → canonical status name (lower-case slug
# as used in oompah's label convention).  This intentionally mirrors the
# ``_STATUS_LABEL_PREFIX``/``_label_to_status`` logic in ``github_tracker.py``.
_SLUG_TO_STATUS: dict[str, str] = {
    "backlog": "Backlog",
    "open": "Open",
    "in-progress": "In Progress",
    "needs-answer": "Needs Answer",
    "needs-human": "Needs Human",
    "needs-ci-fix": "Needs CI Fix",
    "needs-rebase": "Needs Rebase",
    "in-review": "In Review",
    "decomposed": "Decomposed",
    "duplicate-candidate": "Duplicate Candidate",
    "done": "Done",
    "merged": "Merged",
    "archived": "Archived",
    "proposed": "Proposed",
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_bot_login() -> str:
    """Return the GitHub login used by the oompah bot.

    Reads ``OOMPAH_BOT_LOGIN`` from the environment; defaults to
    ``"oompah"``.  The comparison is case-insensitive so that
    ``"Oompah"`` and ``"oompah"`` are treated as the same identity.
    """
    return os.environ.get(_BOT_LOGIN_ENV, _DEFAULT_BOT_LOGIN) or _DEFAULT_BOT_LOGIN


def is_status_label(label_name: str) -> bool:
    """Return ``True`` when *label_name* is an ``oompah:status:*`` label."""
    return bool(label_name) and label_name.startswith(STATUS_LABEL_PREFIX)


def label_name_to_status(label_name: str) -> str | None:
    """Convert an ``oompah:status:<slug>`` label name to a status string.

    Returns ``None`` when *label_name* is not a recognised status label.

    Examples::

        >>> label_name_to_status("oompah:status:open")
        'Open'
        >>> label_name_to_status("oompah:status:in-progress")
        'In Progress'
        >>> label_name_to_status("bug")
        None
    """
    if not is_status_label(label_name):
        return None
    slug = label_name[len(STATUS_LABEL_PREFIX):]
    return _SLUG_TO_STATUS.get(slug)


def _status_to_label_name(status: str) -> str:
    """Convert a canonical status string to an ``oompah:status:<slug>`` label name.

    This is the inverse of :func:`label_name_to_status`.  Used when reverting
    label changes or fetching issue events for validation.

    Examples::

        >>> _status_to_label_name("Open")
        'oompah:status:open'
        >>> _status_to_label_name("In Progress")
        'oompah:status:in-progress'

    Raises:
        ValueError: When *status* is not a recognised canonical status.
    """
    # Build the reverse mapping lazily.
    _STATUS_TO_SLUG = {v: k for k, v in _SLUG_TO_STATUS.items()}
    slug = _STATUS_TO_SLUG.get(status)
    if slug is None:
        raise ValueError(f"Unknown status {status!r} — cannot convert to label name")
    return f"{STATUS_LABEL_PREFIX}{slug}"


def is_authorized_status_actor(actor_login: str, project: Any) -> bool:
    """Return ``True`` when *actor_login* is authorized to change status labels.

    Authorization requires the actor to be one of:

    1. The oompah bot (``get_bot_login()``, case-insensitive comparison).
    2. ``project.tracker_owner`` (case-insensitive), when configured.
    3. A login in ``project.status_label_authorized_logins`` (case-insensitive).

    When *project* is ``None`` or has no ``status_label_authorized_logins``
    attribute, only the bot login is trusted.

    Args:
        actor_login: The GitHub login of the user who changed the label.
        project: A :class:`~oompah.models.Project` instance or any object
                 with a ``status_label_authorized_logins`` attribute.

    Returns:
        ``True`` when the actor is authorized, ``False`` otherwise.
    """
    if not actor_login:
        return False

    actor_lower = actor_login.strip().lower()

    # Bot is always authorized.
    if actor_lower == get_bot_login().strip().lower():
        return True

    # Check per-project owner allowlist.
    if project is not None:
        tracker_owner = getattr(project, "tracker_owner", None)
        if (
            isinstance(tracker_owner, str)
            and tracker_owner.strip().lower() == actor_lower
        ):
            return True

        authorized = getattr(project, "status_label_authorized_logins", None) or []
        for login in authorized:
            if isinstance(login, str) and login.strip().lower() == actor_lower:
                return True

    return False
