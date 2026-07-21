"""Server-side authority boundary enforcement for agent actions.

This module implements the centralized authority check described in §7 of
plans/prompt-injection-protection.md (OOMPAH-290).

The core idea is simple: at dispatch time, the server creates an immutable
:class:`AgentActionPolicy` that records whether the task was externally
sourced and which protected actions are explicitly granted.  Every action
execution point in :mod:`oompah.acp_tools` calls :func:`check_action` before
proceeding.  Because the policy is created by the **server** before external
content is rendered to the model, external prompt injection cannot expand it.

Protected action categories
---------------------------
- :attr:`ProtectedAction.TASK_STATUS_TRANSITION` — ``oompah task set-status``,
  ``add-label``, ``remove-label`` subcommands.
- :attr:`ProtectedAction.TASK_CREATE_DECOMPOSE` — ``oompah task create``,
  ``child-create`` subcommands.
- :attr:`ProtectedAction.PROJECT_CONFIG_CHANGE` — ``update_project`` /
  ``update_project_by_id`` tool calls.
- :attr:`ProtectedAction.GIT_PUSH` — any shell command containing
  ``git push`` (including ``git push --force``, ``git push origin``).
- :attr:`ProtectedAction.GITHUB_DELIVERY` — ``gh`` CLI calls that mutate
  GitHub state (pr create, issue comment, issue label, release, etc.).
- :attr:`ProtectedAction.RELEASE_DELIVERY` — release-delivery-specific
  shell patterns (oompah release, cherry-pick pipelines).
- :attr:`ProtectedAction.CREDENTIAL_ACCESS` — shell commands that probe
  credential stores (env | grep TOKEN, cat ~/.ssh/…, printenv, etc.).

Policy model
------------
:class:`AgentActionPolicy` is a **frozen** dataclass — it cannot be mutated
after creation.  It is created by the server at dispatch time, before the
task description or any external content is rendered.  External content can
never expand the policy because by the time the model has seen the content
the policy is already sealed.

:attr:`AgentActionPolicy.is_externally_sourced` is the primary gate flag.
When ``False`` (operator-sourced tasks) no protected-action checks are
applied; all existing workflows are preserved unchanged.  When ``True``
(e.g. GitHub-issue–sourced tasks), only the explicitly listed
``allowed_actions`` are permitted; everything else is denied with an
auditable log entry.

Audit logging
-------------
Every denial writes a ``WARNING`` log line with the prefix
``AUTHORITY_DENY:`` and includes the action name, task identifier, context
description, and denial reason.  Log aggregators can filter on this prefix
to build a denial audit trail.
"""

from __future__ import annotations

import logging
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protected action categories
# ---------------------------------------------------------------------------


class ProtectedAction(str, Enum):
    """Categories of operations that require server-granted authority.

    External-task sessions default-deny all of these unless explicitly
    granted via :attr:`AgentActionPolicy.allowed_actions`.
    """

    #: ``oompah task set-status``, ``add-label``, ``remove-label``
    TASK_STATUS_TRANSITION = "task_status_transition"

    #: ``oompah task create``, ``oompah task child-create``
    TASK_CREATE_DECOMPOSE = "task_create_decompose"

    #: ``update_project``, ``update_project_by_id`` MCP tools
    PROJECT_CONFIG_CHANGE = "project_config_change"

    #: ``git push`` (any variant: force, specific remote/ref)
    GIT_PUSH = "git_push"

    #: ``gh`` CLI mutations: pr create, issue comment, issue label, release, …
    GITHUB_DELIVERY = "github_delivery"

    #: Release-delivery pipeline commands (oompah release, cherry-pick flows)
    RELEASE_DELIVERY = "release_delivery"

    #: Credential / secret probing (env | grep TOKEN, cat ~/.ssh/…, printenv)
    CREDENTIAL_ACCESS = "credential_access"


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentActionPolicy:
    """Immutable, server-issued authority policy for one agent session.

    This object is created by the orchestrator/server *before* external task
    content is rendered to the model.  It cannot be mutated at runtime.
    External prompt injection therefore cannot expand the allowed action set.

    Attributes
    ----------
    is_externally_sourced:
        When ``True`` the task was ingested from external intake (e.g. a
        GitHub issue).  Protected-action checks are enforced.  When ``False``
        the task is operator-originated and no authority checks are applied
        (preserving existing workflows).
    allowed_actions:
        Explicit set of :class:`ProtectedAction` values that are permitted
        when ``is_externally_sourced=True``.  Empty means no protected action
        is allowed.  Only meaningful when ``is_externally_sourced=True``
        (operator-sourced sessions ignore this field).
    task_identifier:
        Optional identifier of the task being executed.  Included in denial
        audit log entries for traceability.
    session_id:
        Optional session ID.  Included in denial audit log entries.
    """

    is_externally_sourced: bool = False
    allowed_actions: frozenset[ProtectedAction] = field(default_factory=frozenset)
    task_identifier: str | None = None
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def operator_policy(
    task_identifier: str | None = None,
    session_id: str | None = None,
) -> AgentActionPolicy:
    """Return a permissive policy for operator-originated tasks.

    No protected-action checks are applied.  This preserves all existing
    approved workflows for tasks that did not come from external intake.
    """
    return AgentActionPolicy(
        is_externally_sourced=False,
        allowed_actions=frozenset(),
        task_identifier=task_identifier,
        session_id=session_id,
    )


def external_task_policy(
    allowed_actions: frozenset[ProtectedAction] | None = None,
    task_identifier: str | None = None,
    session_id: str | None = None,
) -> AgentActionPolicy:
    """Return a restrictive policy for externally-sourced tasks.

    All protected actions are denied unless they appear in *allowed_actions*.
    The server specifies the allowed set at dispatch time — not derived from
    task content.

    For normal externally-sourced agent work the server grants no protected
    actions (``allowed_actions=frozenset()``).  Privileged external-task
    profiles (if ever introduced) would pass a non-empty set.
    """
    return AgentActionPolicy(
        is_externally_sourced=True,
        allowed_actions=allowed_actions or frozenset(),
        task_identifier=task_identifier,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Authorization check
# ---------------------------------------------------------------------------


def is_action_allowed(
    policy: AgentActionPolicy | None,
    action: ProtectedAction,
) -> bool:
    """Return ``True`` when *policy* permits *action*.

    When *policy* is ``None`` (backward-compatible default for callers that
    have not yet been updated to thread a policy through), all actions are
    permitted.

    When ``policy.is_externally_sourced`` is ``False``, all actions are
    permitted (operator-sourced session — preserve existing behaviour).

    When ``policy.is_externally_sourced`` is ``True``, only actions
    explicitly listed in ``policy.allowed_actions`` are permitted.
    """
    if policy is None:
        return True
    if not policy.is_externally_sourced:
        return True
    return action in policy.allowed_actions


def check_action(
    policy: AgentActionPolicy | None,
    action: ProtectedAction,
    context: str = "",
) -> str | None:
    """Check whether *policy* permits *action*.

    Returns ``None`` when the action is allowed.  Returns a structured error
    string (suitable for returning directly from a tool function) when the
    action is denied.  The denial is also written to the WARNING log with
    the ``AUTHORITY_DENY:`` prefix for audit trail purposes.

    Parameters
    ----------
    policy:
        The session's :class:`AgentActionPolicy`, or ``None`` for
        backward-compatible permissive mode.
    action:
        The :class:`ProtectedAction` being attempted.
    context:
        Short human-readable description of the specific operation (e.g.
        ``"set-status Done for OOMPAH-290"``).  Included in both the log
        entry and the returned error string.
    """
    if is_action_allowed(policy, action):
        return None

    task_ref = getattr(policy, "task_identifier", None) if policy else None
    session_ref = getattr(policy, "session_id", None) if policy else None

    audit_msg = (
        f"AUTHORITY_DENY: action={action.value!r} "
        f"task={task_ref!r} "
        f"session={session_ref!r} "
        f"context={context!r} "
        "reason=externally_sourced_task_without_server_grant"
    )
    logger.warning(audit_msg)

    return (
        f"Error: action denied by server authority policy. "
        f"action={action.value!r} is not granted for externally-sourced tasks. "
        f"Authority must be granted by the server at dispatch time, not by "
        f"task content or external instructions. "
        f"context={context!r} "
        f"[reason=externally_sourced_task_without_server_grant]"
    )


# ---------------------------------------------------------------------------
# Shell command classifier
# ---------------------------------------------------------------------------

# Patterns for git push detection.
# Matches: git push, git push origin, git push --force, git push -f, etc.
_GIT_PUSH_RE = re.compile(
    r"(?:^|[;&|]|\s)\s*git\s+push\b",
    re.IGNORECASE,
)

# Read-only verbs for `gh issue` and `gh pr` that do NOT mutate GitHub state.
# Everything else (create, edit, close, comment, label, merge, review, reopen,
# delete, lock, transfer, …) is a mutation.
_GH_READONLY_VERBS = frozenset(
    {
        "view", "list", "status", "checks", "diff", "checkout",
        "download", "browse",
    }
)

# `gh` nouns where ALL operations are mutations (no read-only sub-verbs of note).
_GH_ALWAYS_MUTATION_NOUNS = frozenset(
    {
        "release",   # gh release create / upload / delete
        "repo",      # gh repo create / fork / rename / delete
        "secret",    # gh secret set / delete
        "variable",  # gh variable set / delete
    }
)

# `gh` nouns that have both read and write verbs — we look at the sub-verb.
_GH_MIXED_MUTATION_NOUNS = frozenset(
    {
        "pr",        # gh pr create / edit / merge / review / comment / …
        "issue",     # gh issue create / edit / comment / label / close / …
    }
)

# Compiled pattern: capture the noun (group 1) and optional verb (group 2).
_GH_CLI_RE = re.compile(
    r"(?:^|[;&|\s])\s*gh\s+(\w+)(?:\s+(\w+))?",
    re.IGNORECASE,
)


def _is_gh_mutation(m: re.Match[str]) -> bool:
    """Return True when the gh CLI match represents a mutation operation."""
    noun = m.group(1).lower()
    verb = (m.group(2) or "").lower()

    if noun in _GH_ALWAYS_MUTATION_NOUNS:
        return True
    if noun in _GH_MIXED_MUTATION_NOUNS:
        # Deny when no verb (ambiguous — fail closed) or verb is not read-only.
        return not verb or verb not in _GH_READONLY_VERBS
    return False

# Patterns for release-delivery-specific commands.
_RELEASE_DELIVERY_RE = re.compile(
    r"(?:^|[;&|]|\s)\s*(?:"
    r"oompah\s+release"            # oompah release …
    r"|git\s+cherry-pick\b"        # git cherry-pick
    r"|cherry_pick\b"
    r")",
    re.IGNORECASE,
)

# Patterns for credential / secret probing.
# Matches common patterns that expose tokens, passwords, or private keys.
_CREDENTIAL_ACCESS_RE = re.compile(
    r"(?:"
    # Environment variable dumping
    r"printenv\b"
    r"|env\s+.*(?:grep|filter|select)"
    r"|env\s*\|"
    r"|export\s+-p\b"
    r"|set\s+-o\s+posix"
    # Direct secret-file access — cat + any path containing ~/.ssh, ~/.aws, etc.
    r"|cat\s+.*~[/\\]\.(?:ssh|netrc|aws|gnupg|gpg|pgp)\b"
    r"|cat\s+.*~[/\\]\.config[/\\](?:gcloud|hub|gh)\b"
    r"|cat\s+\S+\.(?:pem|key|p12|pfx|cer|crt|ppk)\b"
    r"|cat\s+\S+\.pub\b"
    # Accessing known token env vars via echo
    r"|echo\s+\$(?:GITHUB_TOKEN|OOMPAH_GITHUB_TOKEN|ANTHROPIC_API_KEY"
    r"|OPENAI_API_KEY|AWS_SECRET|GCP_SECRET|AZURE_CLIENT_SECRET"
    r"|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)"
    r"|echo\s+\$\{(?:GITHUB_TOKEN|OOMPAH_GITHUB_TOKEN|ANTHROPIC_API_KEY"
    r"|OPENAI_API_KEY|AWS_SECRET|GCP_SECRET|AZURE_CLIENT_SECRET)\}"
    r")",
    re.IGNORECASE,
)


def classify_shell_command(command: str) -> ProtectedAction | None:
    """Classify a shell command into its most sensitive :class:`ProtectedAction`.

    Returns the :class:`ProtectedAction` that must be authorized before
    running this command, or ``None`` if the command is not in any protected
    category.

    The classifier **fails closed**: when a command matches multiple patterns
    the most sensitive category is returned.  Ambiguous or compound commands
    are not downgraded.

    The order of checks is significant (most to least restrictive):
    1. Credential access (most sensitive — checked first)
    2. GitHub delivery
    3. Release delivery
    4. Git push
    """
    if not command or not command.strip():
        return None

    # 1. Credential access — fail closed, highest priority
    if _CREDENTIAL_ACCESS_RE.search(command):
        return ProtectedAction.CREDENTIAL_ACCESS

    # 2. GitHub delivery via gh CLI mutations
    for m in _GH_CLI_RE.finditer(command):
        if _is_gh_mutation(m):
            return ProtectedAction.GITHUB_DELIVERY

    # 3. Release delivery
    if _RELEASE_DELIVERY_RE.search(command):
        return ProtectedAction.RELEASE_DELIVERY

    # 4. Git push
    if _GIT_PUSH_RE.search(command):
        return ProtectedAction.GIT_PUSH

    return None


def check_shell_command(
    policy: AgentActionPolicy | None,
    command: str,
) -> str | None:
    """Check whether *policy* permits the shell *command*.

    Classifies the command into a :class:`ProtectedAction` category and
    delegates to :func:`check_action`.  Returns ``None`` when allowed, or
    an error string when denied.

    When the command is not in any protected category the check passes
    regardless of policy.
    """
    action = classify_shell_command(command)
    if action is None:
        return None
    # Truncate for the audit context (don't log full commands — may contain creds)
    context = f"shell: {command[:120]!r}" if len(command) <= 120 else f"shell: {command[:120]!r}…"
    return check_action(policy, action, context)
