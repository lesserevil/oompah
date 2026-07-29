"""Contracts and capability boundaries for the reserved completion auditor.

The completion auditor is deliberately a different kind of agent from the
normal coding foci.  It may inspect a worktree and run verification commands,
then submit one structured result to the audit scheduler.  It must never get a
write-capable tool merely because task text asks for one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    TargetState,
    Verdict,
)
from oompah.terminal_transition_coordinator import AuditResult


AUDITOR_FOCUS_NAME = "auditor"
AUDITOR_RESULT_TOOL_NAME = "submit_audit_result"

# These names are shared by all agent backends.  ``run_command`` is retained
# as a single tool so auditors can use the project's configured test command;
# the command itself is checked by ``check_auditor_command`` below.
AUDITOR_ALLOWED_TOOLS = frozenset(
    {
        "read_file",
        "list_files",
        "search_files",
        "run_command",
        AUDITOR_RESULT_TOOL_NAME,
    }
)
AUDITOR_MUTATING_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "attach_image",
        "list_projects",
        "get_project",
        "get_project_by_id",
        "update_project",
        "update_project_by_id",
    }
)

# ---------------------------------------------------------------------------
# Payload size limits (enforced server-side on every submission path)
# ---------------------------------------------------------------------------

#: Maximum character length for the human-readable audit message.
#: Prevents oversized output that could embed model artifacts or injection
#: attempts in a comment posted by the coordinator.
_MAX_RESULT_MESSAGE_LENGTH = 4000

#: Maximum number of key/value pairs in the safe_evidence mapping.
_MAX_SAFE_EVIDENCE_ENTRIES = 20

#: Maximum character length for a single safe_evidence key.
_MAX_SAFE_EVIDENCE_KEY_LENGTH = 128

#: Maximum character length for a single safe_evidence value.
#: Values exceeding this limit could silently carry credential material
#: or multi-line injections into the coordinator comment.
_MAX_SAFE_EVIDENCE_VALUE_LENGTH = 512

# ---------------------------------------------------------------------------
# Credential / secret field detection
# ---------------------------------------------------------------------------

# Detects common credential value patterns inside free-text fields.
# The auditor must not be able to exfiltrate secrets by embedding them in the
# ``message`` or ``safe_evidence`` fields, which the coordinator may include
# verbatim in tracker comments.
#
# Patterns covered:
#   - Common token prefixes (ghp_, ghs_, gho_, glpat-, xox[bap]-, sk-...)
#   - JWT structure (three Base64url sections separated by dots)
#   - Private-key PEM headers (BEGIN RSA/EC/DSA/OPENSSH PRIVATE KEY)
#   - OAuth / Bearer tokens (long alphanumeric strings after "Bearer ")
#
# The patterns are intentionally conservative: a false positive is far less
# damaging than silently forwarding a credential into a tracker comment.
_RESULT_SECRET_RE = re.compile(
    r"(?:"
    # GitHub personal access / installation tokens
    r"ghp_[A-Za-z0-9]{20,}"
    r"|ghs_[A-Za-z0-9]{20,}"
    r"|gho_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{36,}"
    # GitLab personal / pipeline / deploy tokens
    r"|glpat-[A-Za-z0-9\-_]{20,}"
    r"|gldt-[A-Za-z0-9\-_]{20,}"
    # Slack tokens
    r"|xox[bap]-[0-9A-Za-z\-]{20,}"
    # OpenAI / Anthropic style bearer tokens
    r"|sk-[A-Za-z0-9\-_]{20,}"
    # AWS access key
    r"|AKIA[0-9A-Z]{16}"
    # PEM private-key headers
    r"|-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY"
    # JWT: three dot-separated Base64url segments (header.payload.signature)
    r"|(?:[A-Za-z0-9\-_]{10,}\.){2}[A-Za-z0-9\-_]{10,}"
    # Explicit Bearer / token assignment patterns with long values
    r"|(?:Bearer|token|api[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|client[_-]?secret)\s*[=:]\s*[A-Za-z0-9\-_./+]{20,}"
    r")",
    re.IGNORECASE,
)

# Key names in safe_evidence that suggest the caller is attempting to include
# sensitive data (regardless of the value content).  Matches the sensitive
# substring anywhere in the key, including compound names like ``auth_token``
# or ``api_key_id``.
_SECRET_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|apikey|credential"
    r"|private[_-]?key|access[_-]?key|access[_-]?token|refresh[_-]?token"
    r"|auth[_-]?token|bearer|client[_-]?secret|certificate|passphrase)",
    re.IGNORECASE,
)


def _check_safe_evidence_for_secrets(
    safe_evidence: Mapping[str, str],
) -> str | None:
    """Return an error string if any key or value appears credential-like.

    Returns ``None`` when the mapping is clean.  The check is applied only to
    ``safe_evidence``; the ``message`` field is covered by a separate size
    limit (4 000 chars) which already caps the damage vector there.
    """
    for key, value in safe_evidence.items():
        if _SECRET_KEY_RE.search(str(key)):
            return (
                "Error: auditor result safe_evidence contains a credential-like key "
                f"({key!r}); remove it before submitting"
            )
        if _RESULT_SECRET_RE.search(str(value)):
            return (
                "Error: auditor result safe_evidence contains a value that matches "
                "a known credential pattern; remove it before submitting"
            )
    return None


@dataclass(frozen=True)
class AuditorCapabilityPolicy:
    """Immutable server-issued tool policy for an auditor session."""

    allowed_tools: frozenset[str] = field(default_factory=lambda: AUDITOR_ALLOWED_TOOLS)
    read_only: bool = True

    def allows(self, tool_name: str) -> bool:
        # Keep the canonical auditor allowlist as a hard ceiling. A malformed
        # or overly broad caller-supplied set must not turn this policy into a
        # write-capable session.
        return (
            self.read_only
            and tool_name in self.allowed_tools
            and tool_name in AUDITOR_ALLOWED_TOOLS
        )


AUDITOR_CAPABILITY_POLICY = AuditorCapabilityPolicy()


@dataclass(frozen=True)
class AuditorTargetContract:
    """The trusted, target-specific input an auditor is required to echo."""

    audit_id: str
    task_id: str
    project_id: str
    target_state: str
    evidence_fingerprint: str
    attempt_id: str | None = None
    previous_state: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("audit_id", "task_id", "project_id", "evidence_fingerprint"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"auditor target requires non-empty {field_name}")
        # Validate the values that are later echoed into the result contract.
        # The scheduler record is trusted input, but rejecting malformed data
        # here prevents a bad record from becoming a misleading prompt.
        TargetState.from_raw(self.target_state)
        EvidenceFingerprint(self.evidence_fingerprint)
        if self.attempt_id is not None and not isinstance(self.attempt_id, str):
            raise ValueError("auditor target attempt_id must be a string or null")

    @property
    def requested_target(self) -> str:
        """Compatibility name used by the scheduler's request vocabulary."""

        return self.target_state

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "audit_id": self.audit_id,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "requested_target": self.requested_target,
            "target_state": self.target_state,
            "evidence_fingerprint": self.evidence_fingerprint,
        }
        if self.attempt_id:
            result["attempt_id"] = self.attempt_id
        if self.previous_state is not None:
            result["previous_state"] = self.previous_state
        return result


def _target_value(target: Any, key: str, *aliases: str) -> Any:
    if isinstance(target, Mapping):
        for candidate in (key, *aliases):
            if candidate in target:
                return target[candidate]
        return None
    for candidate in (key, *aliases):
        value = getattr(target, candidate, None)
        if value is not None:
            return value
    return None


def auditor_target_contract(target: Any, *, task_id: str = "", project_id: str = "") -> AuditorTargetContract:
    """Normalize a scheduler record or mapping into the prompt contract."""

    def required(key: str, *aliases: str) -> str:
        value = _target_value(target, key, *aliases)
        if isinstance(value, Mapping):
            value = value.get("digest", value.get("value", value))
        if hasattr(value, "digest"):
            value = value.digest
        if hasattr(value, "value"):
            value = value.value
        value = str(value or "").strip()
        if not value:
            raise ValueError(f"auditor target requires {key}")
        return value

    # Durable scheduler records already carry their canonical tracker and
    # project identities. Explicit arguments are fallbacks for lightweight
    # test/request objects, never replacements for those identities.
    record_task_id = _target_value(target, "task_id", "issue_id")
    record_project_id = _target_value(target, "project_id")
    return AuditorTargetContract(
        audit_id=required("audit_id"),
        task_id=(
            required("task_id", "issue_id")
            if record_task_id is not None
            else str(task_id or "").strip()
        ),
        project_id=(
            required("project_id")
            if record_project_id is not None
            else str(project_id or "").strip()
        ),
        target_state=required("target_state", "requested_target", "target"),
        evidence_fingerprint=required("evidence_fingerprint", "fingerprint"),
        attempt_id=(
            str(_target_value(target, "attempt_id") or "").strip() or None
        ),
        previous_state=(
            str(_target_value(target, "previous_state") or "").strip() or None
        ),
    )


def pending_auditor_target(
    metadata: Mapping[str, Any] | None,
    *,
    task_id: str,
    project_id: str,
) -> AuditorTargetContract | None:
    """Extract the first durable pending audit target from task metadata.

    A missing or malformed record returns ``None``.  The scheduler remains
    the source of truth; this helper never creates an audit request.
    """

    raw = (metadata or {}).get("oompah.terminal_audit")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, Mapping):
        return None
    chain = raw.get("pending_chain")
    if not isinstance(chain, list):
        return None
    for item in chain:
        if isinstance(item, Mapping):
            try:
                return auditor_target_contract(item, task_id=task_id, project_id=project_id)
            except ValueError:
                continue
    return None


AUDITOR_RESULT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": AUDITOR_RESULT_TOOL_NAME,
        "description": (
            "Submit the completion auditor's structured verdict to the audit "
            "scheduler. This is the only stateful operation available to the "
            "auditor; it does not edit the repository or directly change task state."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "audit_id": {"type": "string"},
                "target_state": {
                    "type": "string",
                    "enum": ["Done", "Merged", "Archived"],
                },
                "evidence_fingerprint": {"type": "string"},
                "verdict": {
                    "type": "string",
                    "enum": ["pass", "fail", "needs_human", "error"],
                },
                "failure_classification": {
                    "type": ["string", "null"],
                    "enum": [
                        item.value for item in FailureClassification
                    ] + [None],
                },
                "message": {"type": "string"},
                "safe_evidence": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "auditor": {
                    "type": ["string", "null"],
                },
                "attempt_id": {"type": ["string", "null"]},
            },
            "required": [
                "audit_id",
                "target_state",
                "evidence_fingerprint",
                "verdict",
                "message",
            ],
            "additionalProperties": False,
        },
    },
}


def _result_payload(result: AuditResult) -> dict[str, Any]:
    return {
        "audit_id": result.audit_id,
        "target_state": result.target_state.value,
        "evidence_fingerprint": result.evidence_fingerprint.digest,
        "verdict": result.verdict.value,
        "failure_classification": (
            result.failure_classification.value
            if result.failure_classification is not None
            else None
        ),
        "message": result.message,
        "safe_evidence": dict(result.safe_evidence or {}),
        "auditor": result.auditor.to_dict() if result.auditor else None,
        "attempt_id": result.attempt_id,
    }


def parse_auditor_result(
    args: Mapping[str, Any],
    target: AuditorTargetContract | Mapping[str, Any] | Any,
) -> tuple[AuditResult | None, str | None]:
    """Validate a model tool payload against the trusted target contract.

    All validation is server-side and fails closed: each check is applied
    before any result object is constructed, and a single failure returns
    ``(None, error_message)`` without side effects.

    Security checks applied beyond schema validation:
    - Rejects unknown fields (prevents status injection via extra keys).
    - Rejects ``audit_id``, ``target_state``, or ``evidence_fingerprint``
      that do not match the session's trusted :class:`AuditorTargetContract`.
    - Enforces maximum lengths for ``message`` and each ``safe_evidence``
      key/value pair to prevent oversized output.
    - Detects credential-like patterns in ``safe_evidence`` keys and values
      to prevent the auditor from exfiltrating secrets through coordinator
      comments.
    """

    if not isinstance(args, Mapping):
        return None, "Error: auditor result payload must be an object"

    try:
        allowed_keys = {
            "audit_id",
            "target_state",
            "evidence_fingerprint",
            "verdict",
            "failure_classification",
            "message",
            "safe_evidence",
            "auditor",
            "attempt_id",
        }
        unexpected = set(args) - allowed_keys
        if unexpected:
            return None, (
                "Error: invalid auditor result fields: "
                + ", ".join(sorted(str(key) for key in unexpected))
            )
        contract = (
            target
            if isinstance(target, AuditorTargetContract)
            else auditor_target_contract(target)
        )

        # --- Compare-and-set: echoed identity fields must match the contract ---
        for key in ("audit_id", "target_state", "evidence_fingerprint"):
            supplied_raw = args.get(key)
            if not isinstance(supplied_raw, str):
                return None, f"Error: auditor result {key} must be a string"
            supplied = supplied_raw.strip()
            expected = str(getattr(contract, key))
            if supplied != expected:
                return None, f"Error: auditor result {key} does not match the requested target"

        supplied_attempt_raw = args.get("attempt_id")
        if supplied_attempt_raw is not None and not isinstance(supplied_attempt_raw, str):
            return None, "Error: auditor result attempt_id must be a string or null"
        supplied_attempt = (supplied_attempt_raw or "").strip()
        if supplied_attempt != (contract.attempt_id or ""):
            return None, "Error: auditor result attempt_id does not match the requested target"

        # --- Message size limit ---
        message = args.get("message")
        if not isinstance(message, str):
            return None, "Error: auditor result message must be a string"
        if len(message) > _MAX_RESULT_MESSAGE_LENGTH:
            return None, (
                f"Error: auditor result message exceeds maximum length "
                f"({len(message)} > {_MAX_RESULT_MESSAGE_LENGTH} characters)"
            )

        # --- Safe evidence size and content checks ---
        safe_evidence = args.get("safe_evidence")
        if safe_evidence is not None:
            if not isinstance(safe_evidence, Mapping):
                return None, "Error: auditor result safe_evidence must be an object"
            if any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in safe_evidence.items()
            ):
                return None, "Error: auditor result safe_evidence values must be strings"
            if len(safe_evidence) > _MAX_SAFE_EVIDENCE_ENTRIES:
                return None, (
                    f"Error: auditor result safe_evidence exceeds maximum entry count "
                    f"({len(safe_evidence)} > {_MAX_SAFE_EVIDENCE_ENTRIES})"
                )
            for ev_key, ev_val in safe_evidence.items():
                if len(str(ev_key)) > _MAX_SAFE_EVIDENCE_KEY_LENGTH:
                    return None, (
                        f"Error: auditor result safe_evidence key {ev_key!r} exceeds "
                        f"maximum length ({_MAX_SAFE_EVIDENCE_KEY_LENGTH} characters)"
                    )
                if len(str(ev_val)) > _MAX_SAFE_EVIDENCE_VALUE_LENGTH:
                    return None, (
                        f"Error: auditor result safe_evidence value for key {ev_key!r} "
                        f"exceeds maximum length ({_MAX_SAFE_EVIDENCE_VALUE_LENGTH} characters)"
                    )
            # Reject credential-like keys and values to prevent exfiltration
            secret_error = _check_safe_evidence_for_secrets(safe_evidence)
            if secret_error is not None:
                return None, secret_error

        auditor = args.get("auditor")
        if auditor is not None and not isinstance(auditor, str):
            return None, "Error: auditor result auditor must be a string or null"

        result = AuditResult(
            audit_id=contract.audit_id,
            target_state=TargetState.from_raw(args["target_state"]),
            evidence_fingerprint=EvidenceFingerprint(
                str(args["evidence_fingerprint"])
            ),
            verdict=Verdict.from_raw(args["verdict"]),
            failure_classification=(
                FailureClassification.from_raw(args["failure_classification"])
                if args.get("failure_classification")
                else None
            ),
            message=message,
            safe_evidence=dict(safe_evidence) if safe_evidence is not None else None,
            auditor=(
                ContributorIdentity(auditor)
                if auditor
                else None
            ),
            attempt_id=supplied_attempt or None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"Error: invalid auditor result: {exc}"
    return result, None


def submit_auditor_result(
    args: Mapping[str, Any],
    target: AuditorTargetContract | Mapping[str, Any] | Any,
    handler: Callable[[AuditResult], Any] | None = None,
) -> str:
    """Validate and optionally forward a result to the audit scheduler.

    The ``handler`` is the coordinator's ``apply_audit_result`` method wrapped
    as a synchronous callable.  It must be supplied by the orchestrator when
    dispatching an auditor session; without it the result is validated but not
    applied.

    The tool returns a JSON object with ``accepted=true`` on success.  On
    coordinator rejection or scheduler failure the returned string starts with
    ``"Error:"`` so the agent sees the denial inline.
    """

    result, error = parse_auditor_result(args, target)
    if error is not None or result is None:
        return error or "Error: invalid auditor result"
    if handler is not None:
        try:
            outcome = handler(result)
        except Exception as exc:
            return f"Error: audit scheduler rejected result: {exc}"
        if outcome is not None:
            if isinstance(outcome, str):
                return outcome
            return json.dumps(outcome, default=str)
    return json.dumps({"accepted": True, "result": _result_payload(result)})


# Commands whose purpose is inspection or verification.  The allowlist is
# intentionally conservative; a completion auditor can report that it could
# not inspect something rather than receiving a shell with write authority.
_AUDITOR_COMMAND_RE = re.compile(
    r"^(?:"
    r"(?:pwd|ls|find|head|tail|cat|file|stat|readlink|rg|grep|git\s+"
    r"(?:status|diff|log|show|rev-parse|ls-files|branch|describe|whatchanged))"
    r"|(?:pytest|py\.test|python(?:\d+(?:\.\d+)?)?\s+-m\s+"
    r"(?:pytest|unittest|compileall))"
    r"|(?:make\s+(?:test|test-serial|check-secrets))"
    r"|(?:ruff|mypy|black\s+--check|npm\s+test|pnpm\s+test|yarn\s+test)"
    r"|(?:oompah\s+task\s+view)"
    r")\b.*$",
    re.IGNORECASE,
)
_AUDITOR_COMMAND_MUTATION_RE = re.compile(
    r"(?:\b(?:rm|mv|cp|mkdir|rmdir|touch|tee|install|truncate|chmod|chown|"
    r"sed\s+(?:-[^-\s]*i|--in-place)|perl\s+-i|git\s+(?:add|commit|push|"
    r"pull|fetch|checkout|switch|reset|restore|rebase|merge|cherry-pick|"
    r"tag|clean|apply|update-ref|branch\s+(?:-(?:d|D|m|M)|--(?:delete|move|copy)))|(?:bash|sh|zsh|fish|"
    r"env|eval|xargs)\b)|(?:>>?|<<?)|[;&|`]"
    r"|(?:\$)|(?:\s--(?:fix|delete)(?:\s|=|$)|\s--output(?:=|\s|$)|"
    r"\s-(?:delete|exec(?:dir)?|ok(?:dir)?)(?:\s|$))"
    r")",
    re.IGNORECASE,
)

# The normal run-command helper only rejects a leading ``cd`` outside the
# worktree. An auditor's shell is narrower: absolute paths, parent traversal,
# and credential-like files are outside repository/test authority and could
# expose server or operator data through an otherwise read-only command.
_AUDITOR_PATH_ESCAPE_RE = re.compile(
    r"(?:^|[\s=:'\"])(?:~|/(?:[^\s'\"]*)|\.\.(?:[/\\]|$))"
    r"|(?:^|[\s=:'\"/])\.\.(?:[/\\]|$)",
    re.IGNORECASE,
)
_AUDITOR_SECRET_PATH_RE = re.compile(
    r"(?:^|[\s/'\"])(?:\.env(?:\.[^\s/'\"]+)?|\.git/config|"
    r"(?:id_(?:rsa|dsa|ecdsa|ed25519)|known_hosts)|credentials(?:\.json)?|"
    r"[^\s/'\"]+\.(?:pem|key|p12|pfx|netrc))(?=$|[\s/'\"])",
    re.IGNORECASE,
)


def check_auditor_command(command: str) -> str | None:
    """Return a denial for commands outside the read/test allowlist."""

    normalized = str(command or "").strip()
    if not normalized or not _AUDITOR_COMMAND_RE.fullmatch(normalized):
        return (
            "Error: auditor capability policy permits only read-only repository "
            "inspection and configured test commands; command denied"
        )
    if _AUDITOR_PATH_ESCAPE_RE.search(normalized):
        return (
            "Error: auditor capability policy denied a path outside the "
            "repository worktree"
        )
    if _AUDITOR_SECRET_PATH_RE.search(normalized):
        return (
            "Error: auditor capability policy denied access to a credential-like "
            "file"
        )
    if _AUDITOR_COMMAND_MUTATION_RE.search(normalized):
        return (
            "Error: auditor capability policy denied a mutating or compound "
            "shell command; auditors cannot edit, commit, push, merge, or change state"
        )
    return None


__all__ = [
    "AUDITOR_ALLOWED_TOOLS",
    "AUDITOR_CAPABILITY_POLICY",
    "AUDITOR_FOCUS_NAME",
    "AUDITOR_MUTATING_TOOLS",
    "AUDITOR_RESULT_TOOL_NAME",
    "AUDITOR_RESULT_TOOL_SCHEMA",
    "AuditorCapabilityPolicy",
    "AuditorTargetContract",
    "_MAX_RESULT_MESSAGE_LENGTH",
    "_MAX_SAFE_EVIDENCE_ENTRIES",
    "_MAX_SAFE_EVIDENCE_KEY_LENGTH",
    "_MAX_SAFE_EVIDENCE_VALUE_LENGTH",
    "_RESULT_SECRET_RE",
    "_SECRET_KEY_RE",
    "auditor_target_contract",
    "check_auditor_command",
    "pending_auditor_target",
    "parse_auditor_result",
    "submit_auditor_result",
]
