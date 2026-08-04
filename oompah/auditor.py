"""Contracts and capability boundaries for the reserved completion auditor.

The completion auditor is deliberately a different kind of agent from the
normal coding foci.  It may inspect a worktree and run verification commands,
then submit one structured result to the audit scheduler.  It must never get a
write-capable tool merely because task text asks for one.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from oompah.terminal_audit import (
    EvidenceFingerprint,
    FailureClassification,
    TargetState,
    Verdict,
)
from oompah.terminal_transition_coordinator import AuditResult


AUDITOR_FOCUS_NAME = "auditor"
AUDITOR_RESULT_TOOL_NAME = "submit_audit_result"

# A rejected shell pipeline is still a safe validation response: the command
# did not run, and the auditor can split the inspection into the dedicated
# search/read tools or separate run_command calls.  Keep this marker stable so
# every backend can preserve the distinction when it forwards the response as
# plain text.
AUDITOR_READ_ONLY_SYNTAX_REASON = "auditor_read_only_shell_syntax"


class AuditorCommandDenial(str):
    """String-compatible auditor command denial with recovery metadata."""

    recoverable: bool
    reason: str

    def __new__(
        cls,
        message: str,
        *,
        recoverable: bool = False,
        reason: str = "auditor_command_denied",
    ) -> "AuditorCommandDenial":
        result = super().__new__(cls, message)
        result.recoverable = recoverable
        result.reason = reason
        return result


def is_recoverable_auditor_command_denial(value: str | None) -> bool:
    """Return whether a denied command can be retried without retiring an audit.

    The marker fallback keeps this safe across backend adapters that coerce the
    string subclass to a plain ``str`` while passing tool output around.
    """

    return bool(
        isinstance(value, AuditorCommandDenial) and value.recoverable
    ) or AUDITOR_READ_ONLY_SYNTAX_REASON in str(value or "")

# These names are shared by all agent backends.  ``run_command`` is retained
# as a single tool so auditors can use the project's configured test command;
# the command itself is checked by ``check_auditor_command`` below.
AUDITOR_ALLOWED_TOOLS = frozenset(
    {
        "read_file",
        "list_files",
        "search_files",
        "read_command_output",
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

#: Maximum number of optional questions or instructions in one result.
_MAX_RESULT_LIST_ITEMS = 5

#: Maximum length of one optional question or instruction.
_MAX_RESULT_LIST_ITEM_LENGTH = 512

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
    # Bearer values are unsafe even without an assignment delimiter.
    r"|Bearer\s+[A-Za-z0-9_./+\-]{1,}"
    # JWT: three dot-separated Base64url segments (header.payload.signature)
    r"|(?:[A-Za-z0-9\-_]{10,}\.){2}[A-Za-z0-9\-_]{10,}"
    # Explicit Bearer / credential assignment patterns.  Assignment values
    # are rejected even when short: credentials are not required to meet a
    # minimum length before they become unsafe to echo into a tracker.
    r"|(?:Bearer|token|api[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd|secret|authorization)\s*[=:]\s*[^\s,;]+"
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


def _redact_credential_patterns(text: str, field_name: str) -> tuple[str, list[str]]:
    """Redact credential-like patterns in free-text fields.
    
    Returns a tuple of (redacted_text, redaction_notes) where redaction_notes
    lists what was redacted for auditor feedback.
    
    The redaction is deterministic: the same input always produces the same
    output, enabling idempotent resubmission. Redaction uses descriptive markers
    like [REDACTED-github-token] so the auditor can understand what was normalized.
    """
    redactions: list[str] = []
    
    def replace_match(match):
        matched_text = match.group(0)
        
        # Identify the type of credential pattern matched for better feedback
        if "ghp_" in matched_text or "ghs_" in matched_text or "gho_" in matched_text or "github_pat_" in matched_text:
            marker = "[REDACTED-github-token]"
            redactions.append(f"{field_name}: GitHub token example")
        elif "glpat-" in matched_text or "gldt-" in matched_text:
            marker = "[REDACTED-gitlab-token]"
            redactions.append(f"{field_name}: GitLab token example")
        elif "xox" in matched_text:
            marker = "[REDACTED-slack-token]"
            redactions.append(f"{field_name}: Slack token example")
        elif "sk-" in matched_text:
            marker = "[REDACTED-api-key]"
            redactions.append(f"{field_name}: API key example")
        elif "AKIA" in matched_text:
            marker = "[REDACTED-aws-key]"
            redactions.append(f"{field_name}: AWS credential example")
        elif "BEGIN" in matched_text and "PRIVATE KEY" in matched_text:
            marker = "[REDACTED-private-key]"
            redactions.append(f"{field_name}: Private key header example")
        elif "Bearer" in matched_text or matched_text.startswith("Bearer "):
            marker = "[REDACTED-bearer-token]"
            redactions.append(f"{field_name}: Bearer token example")
        elif any(sep in matched_text for sep in ("=", ":")):
            marker = "[REDACTED-credential]"
            # Try to extract the key name for more context
            for sep in ("=", ":"):
                if sep in matched_text:
                    key_part = matched_text.split(sep)[0].strip().lower()
                    if key_part:
                        redactions.append(f"{field_name}: credential-like assignment (key: {key_part})")
                    break
        else:
            # JWT or other pattern
            if "." in matched_text and len(matched_text) > 50:
                marker = "[REDACTED-jwt-like]"
                redactions.append(f"{field_name}: JWT-like token example")
            else:
                marker = "[REDACTED-credential-pattern]"
                redactions.append(f"{field_name}: credential pattern example")
        
        return marker
    
    redacted = _RESULT_SECRET_RE.sub(replace_match, text)
    return redacted, redactions


def _redact_safe_evidence(
    safe_evidence: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Redact credential-like keys and values in safe_evidence.
    
    Returns (redacted_evidence_dict, redaction_notes). Keys matching secret
    patterns are replaced with redacted keys. Values matching secret patterns
    are replaced with redaction markers.
    """
    redactions: list[str] = []
    redacted: dict[str, str] = {}
    
    for key, value in safe_evidence.items():
        key_str = str(key)
        value_str = str(value)
        
        # Check if the key is credential-like
        if _SECRET_KEY_RE.search(key_str):
            # Replace the key with a redacted version
            redacted_key = "[REDACTED-credential-key]"
            redacted[redacted_key] = value_str
            redactions.append(f"safe_evidence: credential-like key ({key_str!r}) was redacted")
            continue
        
        # Check if the value contains credential-like patterns and redact it
        if _RESULT_SECRET_RE.search(value_str):
            redacted_value, value_redactions = _redact_credential_patterns(value_str, f"safe_evidence[{key_str!r}]")
            redacted[key_str] = redacted_value
            redactions.extend(value_redactions)
        else:
            redacted[key_str] = value_str
    
    return redacted, redactions


def _check_safe_evidence_for_secrets(
    safe_evidence: Mapping[str, str],
) -> str | None:
    """Return an error string if any key or value appears credential-like.

    Returns ``None`` when the mapping is clean. Free-text message, question,
    and instruction fields use the same pattern check through their parser.
    
    This function is deprecated; use _redact_safe_evidence instead for
    better UX that redacts inert examples rather than rejecting them.
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


def _check_result_text_for_secrets(value: str, field_name: str) -> str | None:
    """Reject credential-like content in a free-text result field."""

    if _RESULT_SECRET_RE.search(value):
        return (
            f"Error: auditor result {field_name} contains a value that matches "
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
            request_state = str(item.get("request_state") or "pending").strip().lower()
            if request_state not in {"pending", "in_progress"}:
                continue
            # The scheduler persists the attempt on the record before launch.
            # Echo the active attempt identity, not a stale completed attempt.
            active_attempt_id = None
            attempts = item.get("attempts")
            if isinstance(attempts, list):
                for raw_attempt in reversed(attempts):
                    if not isinstance(raw_attempt, Mapping):
                        continue
                    if str(raw_attempt.get("request_state") or "").lower() == "in_progress":
                        active_attempt_id = str(raw_attempt.get("attempt_id") or "").strip() or None
                        break
            try:
                target = auditor_target_contract(item, task_id=task_id, project_id=project_id)
                if active_attempt_id and target.attempt_id != active_attempt_id:
                    target = AuditorTargetContract(
                        audit_id=target.audit_id,
                        task_id=target.task_id,
                        project_id=target.project_id,
                        target_state=target.target_state,
                        evidence_fingerprint=target.evidence_fingerprint,
                        attempt_id=active_attempt_id,
                        previous_state=target.previous_state,
                    )
                return target
            except ValueError:
                continue
    return None


def check_auditor_session_target(policy: Any, target: Any) -> str | None:
    """Verify that a server-issued auditor policy owns *target*.

    Tool catalogs are also constructible outside the orchestrator (for
    tests and backend adapters), so the catalog boundary must repeat the
    server-side ownership check instead of relying on prompt instructions.
    """

    if policy is None or getattr(policy, "read_only", False) is not True:
        return "Error: submit_audit_result is restricted to an auditor session"
    if getattr(policy, "auditor_session", False) is not True:
        return "Error: submit_audit_result is restricted to an auditor session"
    try:
        contract = (
            target
            if isinstance(target, AuditorTargetContract)
            else auditor_target_contract(target)
        )
    except (TypeError, ValueError):
        return "Error: auditor session has no valid target contract"

    task_identifier = getattr(policy, "task_identifier", None)
    if task_identifier and str(task_identifier) != contract.task_id:
        return "Error: auditor session does not own the requested task"
    project_id = getattr(policy, "project_id", None)
    if project_id and str(project_id) != contract.project_id:
        return "Error: auditor session does not own the requested project"
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
                    "enum": ["pass", "fail", "needs_human"],
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
                "questions": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": _MAX_RESULT_LIST_ITEM_LENGTH},
                    "maxItems": _MAX_RESULT_LIST_ITEMS,
                },
                "instructions": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": _MAX_RESULT_LIST_ITEM_LENGTH},
                    "maxItems": _MAX_RESULT_LIST_ITEMS,
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
        "questions": list(result.questions),
        "instructions": list(result.instructions),
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
    - Detects credential-like patterns in free-text and ``safe_evidence``
      fields to prevent the auditor from exfiltrating secrets through
      coordinator comments.
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
            "questions",
            "instructions",
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

        # --- Message size limit and credential redaction ---
        message = args.get("message")
        if not isinstance(message, str):
            return None, "Error: auditor result message must be a string"
        if len(message) > _MAX_RESULT_MESSAGE_LENGTH:
            return None, (
                f"Error: auditor result message exceeds maximum length "
                f"({len(message)} > {_MAX_RESULT_MESSAGE_LENGTH} characters)"
            )
        # Redact credential-like patterns from the message
        redacted_message, message_redactions = _redact_credential_patterns(message, "message")
        if len(redacted_message) > _MAX_RESULT_MESSAGE_LENGTH:
            return None, (
                f"Error: auditor result message exceeds maximum length after redaction "
                f"({len(redacted_message)} > {_MAX_RESULT_MESSAGE_LENGTH} characters)"
            )
        message = redacted_message

        # --- Safe evidence size and content checks with redaction ---
        safe_evidence = args.get("safe_evidence")
        safe_evidence_redactions: list[str] = []
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
            # Redact credential-like keys and values
            redacted_safe_evidence, safe_evidence_redactions = _redact_safe_evidence(safe_evidence)
            
            # Validate redacted evidence
            for ev_key, ev_val in redacted_safe_evidence.items():
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
            safe_evidence = redacted_safe_evidence

        def _parse_result_list(field_name: str) -> tuple[str, ...]:
            raw_items = args.get(field_name)
            if raw_items is None:
                return ()
            if not isinstance(raw_items, list):
                raise ValueError(f"{field_name} must be an array")
            if len(raw_items) > _MAX_RESULT_LIST_ITEMS:
                raise ValueError(
                    f"{field_name} exceeds maximum item count "
                    f"({_MAX_RESULT_LIST_ITEMS})"
                )
            items: list[str] = []
            for item in raw_items:
                if not isinstance(item, str):
                    raise ValueError(f"{field_name} items must be strings")
                if len(item) > _MAX_RESULT_LIST_ITEM_LENGTH:
                    raise ValueError(
                        f"{field_name} item exceeds maximum length "
                        f"({_MAX_RESULT_LIST_ITEM_LENGTH} characters)"
                    )
                # Redact credential-like patterns from questions/instructions
                redacted_item, _ = _redact_credential_patterns(item, field_name)
                if len(redacted_item) > _MAX_RESULT_LIST_ITEM_LENGTH:
                    raise ValueError(
                        f"{field_name} item exceeds maximum length after redaction "
                        f"({_MAX_RESULT_LIST_ITEM_LENGTH} characters)"
                    )
                items.append(redacted_item)
            return tuple(items)

        questions = _parse_result_list("questions")
        instructions = _parse_result_list("instructions")

        verdict = Verdict.from_raw(args["verdict"])
        if verdict == Verdict.ERROR:
            raise ValueError(
                "auditor result verdict must be PASS, FAIL, or NEEDS_HUMAN"
            )
        failure_classification = (
            FailureClassification.from_raw(args["failure_classification"])
            if args.get("failure_classification")
            else None
        )
        if verdict == Verdict.FAIL and failure_classification is None:
            raise ValueError("FAIL verdict requires a failure_classification")

        result = AuditResult(
            audit_id=contract.audit_id,
            target_state=TargetState.from_raw(args["target_state"]),
            evidence_fingerprint=EvidenceFingerprint(
                str(args["evidence_fingerprint"])
            ),
            verdict=verdict,
            failure_classification=failure_classification,
            message=message,
            safe_evidence=dict(safe_evidence) if safe_evidence is not None else None,
            # Identity is server-authenticated by the session/policy and is
            # deliberately not accepted as model-controlled payload data.
            auditor=None,
            attempt_id=supplied_attempt or None,
            questions=questions,
            instructions=instructions,
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
    as a synchronous callable. It must be supplied by the orchestrator when
    dispatching an auditor session; without it submission fails closed.

    The tool returns a JSON object with ``accepted=true`` on success.  On
    coordinator rejection or scheduler failure the returned string starts with
    ``"Error:"`` so the agent sees the denial inline.
    """

    result, error = parse_auditor_result(args, target)
    if error is not None or result is None:
        return error or "Error: invalid auditor result"
    if handler is None:
        # Validation without a coordinator callback is not submission. A
        # false success here would let a detached or misconfigured auditor
        # stop after producing a verdict that was never applied.
        return "Error: audit scheduler is unavailable; result was not submitted"
    try:
        outcome = handler(result)
    except Exception:
        # Do not echo exception text: tracker/provider failures can contain
        # credentials, request bodies, or internal paths.
        return "Error: audit scheduler rejected result"
    if outcome is not None:
        if isinstance(outcome, str):
            return outcome
        if isinstance(outcome, Mapping) and outcome.get("accepted") is False:
            return "Error: audit scheduler rejected result"
        return json.dumps(outcome, default=str)
    return json.dumps({"accepted": True, "result": _result_payload(result)})


# Structured git subcommand capability table for safe read-only operations.
# Each entry maps a git subcommand to its allowed options and operand patterns.
#
# This table enables systematic expansion of git inspection commands without
# requiring one-off regex pattern fixes. Subcommands not in this table must use
# the fallback regex pattern.
_GIT_SUBCOMMAND_CAPABILITIES = {
    # Read-only information queries (no state change)
    "status": {"safe_flags": {"--porcelain", "-s"}, "needs_validation": False},
    "diff": {"safe_flags": {"--cached", "--staged"}, "needs_validation": False},
    "log": {"safe_flags": {"--oneline", "--format", "-p", "--name-only", "--stat"}, "needs_validation": False},
    "show": {"safe_flags": {}, "needs_validation": False},
    "rev-parse": {"safe_flags": {}, "needs_validation": False},
    "ls-files": {"safe_flags": {}, "needs_validation": False},
    "branch": {"safe_flags": {"-a", "--all", "-r", "--remotes", "-v", "--verbose"}, "needs_validation": False},
    "describe": {"safe_flags": {}, "needs_validation": False},
    "whatchanged": {"safe_flags": {}, "needs_validation": False},
    "merge-base": {"safe_flags": {}, "needs_validation": False},
    # Rev-list requires more careful validation of operands and flags
    "rev-list": {
        "safe_flags": {
            "--left-right",      # Show left/right markers in asymmetric ranges
            "--count",          # Count commits instead of listing them
            "--reverse",        # Reverse the commit order
            "--graph",          # Show ASCII graph
            "--pretty",         # Control commit message format
            "--abbrev-commit",  # Show abbreviated hashes
            "--oneline",        # Short format
            "--format",         # Custom format string
            "--stat",           # Show file statistics
            "--name-only",      # Show only changed filenames
            "--name-status",    # Show changed filenames with status
            "-p",               # Show diff
        },
        "needs_validation": True  # Rev-list needs operand validation
    },
}


def _is_safe_git_rev_list_command(command: str) -> bool:
    """Validate git rev-list as a safe read-only inspection command.
    
    Returns True if the command is a git rev-list with only read-only flags
    and valid revision/range operands (no shell escapes or redirects).
    """
    tokens = _auditor_shell_tokens(command)
    if not tokens or len(tokens) < 2:
        return False
    
    # Check that the first token is "git" and second is "rev-list"
    if tokens[0].lower() != "git" or tokens[1].lower() != "rev-list":
        return False
    
    # Extract flags and operands
    flags = set()
    operands = []
    i = 2
    while i < len(tokens):
        token = tokens[i]
        # Flags start with - or --
        if token.startswith("-"):
            # Handle flags that take values (e.g., --format=<string>)
            if "=" in token:
                flag_part = token.split("=", 1)[0]
                flags.add(flag_part.lower())
            else:
                flags.add(token.lower())
            # If this flag takes a separate argument, consume it
            if token.lower() in {"--format", "--pretty"} and "=" not in token:
                i += 1
                if i < len(tokens):
                    i += 1
                    continue
        else:
            # Non-flag tokens are operands (revision specs or ranges)
            operands.append(token)
        i += 1
    
    # Check that all flags are in the allowed set
    allowed_flags = _GIT_SUBCOMMAND_CAPABILITIES.get("rev-list", {}).get("safe_flags", set())
    for flag in flags:
        # Allow flags to appear in various forms (--flag, -f, --flag=value)
        base_flag = flag.rstrip("=")
        if not any(base_flag == af or base_flag in af for af in allowed_flags):
            return False
    
    # Validate operands are safe revision specs (no shell escapes)
    for operand in operands:
        # Valid revision specs look like:
        # - commit hashes: abc123, abc123^, abc123~5
        # - branch names: main, origin/main
        # - ranges: main..develop, origin/main...origin/develop
        # - refs: HEAD, @, etc.
        # Invalid: paths with / leading to escapes, command substitutions, etc.
        if not _AUDITOR_SAFE_PATH_TOKEN_RE.fullmatch(operand):
            # Try more permissive patterns for revision specs
            # Allow special characters used in git ranges and refs
            if not re.match(r"^[A-Za-z0-9_./+@=,:\-^~*]+$", operand):
                return False
    
    return True


# Commands whose purpose is inspection or verification.  The allowlist is
# intentionally conservative; a completion auditor can report that it could
# not inspect something rather than receiving a shell with write authority.
_AUDITOR_COMMAND_RE = re.compile(
    r"^(?:"
    r"(?:pwd|ls|find|head|tail|cat|file|stat|readlink|rg|grep|git\s+"
    r"(?:status|diff|log|show|rev-parse|ls-files|branch|describe|whatchanged|merge-base|rev-list))"
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
    r"tag|clean|apply|update-ref|branch\s+(?:-(?:d|D|m|M)|--(?:delete|move|copy)))(?=\s|$)|"
    r"(?:bash|sh|zsh|fish|"
    r"env|eval|xargs|system|getline)\b)|(?:>>?|<<?)|[;&|`]"
    r"|(?:\$)|(?:\s--(?:fix|delete)(?:\s|=|$)|\s--output(?:=|\s|$)|"
    r"\s-(?:delete|exec(?:dir)?|ok(?:dir)?)(?:\s|$))"
    r")",
    re.IGNORECASE,
)

# The broad historical regex above is retained as a defense-in-depth assertion
# that compound shell syntax is never executed.  These narrower expressions
# distinguish a harmless-but-unsupported read-only pipeline from a command
# that must consume the fatal policy-denial budget.
_AUDITOR_STATE_CHANGE_RE = re.compile(
    r"(?:\b(?:rm|mv|cp|mkdir|rmdir|touch|tee|install|truncate|chmod|chown|"
    r"sed\s+(?:-[^-\s]*i|--in-place)|perl\s+-i|git\s+(?:add|commit|push|"
    r"pull|fetch|checkout|switch|reset|restore|rebase|merge|cherry-pick|"
    r"tag|clean|apply|update-ref|branch\s+(?:-(?:d|D|m|M)|--(?:delete|move|copy)))(?=\s|$)|"
    r"(?:bash|sh|zsh|fish|env|eval|xargs|system|getline)\b)"
    r"|(?:`|\$)"
    r"|(?:\s--(?:fix|delete)(?:\s|=|$)|\s--output(?:=|\s|$)|"
    r"\s-(?:delete|exec(?:dir)?|ok(?:dir)?)(?:\s|$)))",
    re.IGNORECASE,
)
_AUDITOR_FILE_REDIRECTION_RE = re.compile(
    # ``2>&1`` only merges stderr into stdout and is safe to classify as an
    # unsupported read-only compound command.  All other redirection remains
    # a fatal denial, including input and append/output redirection.
    r"(?:>>?|<<)(?!\s*&\s*1)",
    re.IGNORECASE,
)
_AUDITOR_COMPOUND_RE = re.compile(r"[;&|]", re.IGNORECASE)

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

# ``awk`` and ``sed`` are useful for bounded source inspection, but their
# language/options are broad enough that adding them to the general command
# allowlist would accidentally admit writes, process control, or shell
# escapes. Recognize only the two print-only forms auditors commonly use:
# numeric NR ranges in awk and numeric-address ``p`` commands in sed.
_AWK_READ_ONLY_PROGRAM_RE = re.compile(
    r"^NR\s*>=\s*[0-9]+\s*&&\s*NR\s*<=\s*[0-9]+"
    r"(?:\s*\{\s*print\s*\})?$",
    re.IGNORECASE,
)
_SED_PRINT_ONLY_SCRIPT_RE = re.compile(
    r"^(?:[0-9]+(?:,[0-9]+)?)?p$",
    re.IGNORECASE,
)
_AUDITOR_SAFE_PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./+@=,:-]+$")


def _auditor_shell_tokens(command: str) -> list[str] | None:
    """Tokenize a candidate inspection command without executing shell syntax."""

    if "\n" in command or "\r" in command:
        # Newlines are shell command separators even though shlex treats them
        # as ordinary whitespace in this mode.
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        # Unclosed quotes and malformed shell escapes are not read-only forms.
        return None


def _auditor_safe_input_paths(paths: list[str]) -> bool:
    """Return whether all candidate input paths are safe worktree-relative names."""

    if not paths:
        return False
    for path in paths:
        if (
            path == "-"
            or path.startswith("-")
            or not _AUDITOR_SAFE_PATH_TOKEN_RE.fullmatch(path)
            or _AUDITOR_PATH_ESCAPE_RE.search(path)
            or _AUDITOR_SECRET_PATH_RE.search(path)
        ):
            return False
    return True


def _is_read_only_inspection_command(command: str) -> bool:
    """Recognize narrowly safe, unsupported awk/sed/git inspection commands."""

    tokens = _auditor_shell_tokens(command)
    if not tokens:
        return False
    if tokens[0].lower() == "awk" and len(tokens) >= 3:
        return bool(
            _AWK_READ_ONLY_PROGRAM_RE.fullmatch(tokens[1])
            and _auditor_safe_input_paths(tokens[2:])
        )
    if (
        tokens[0].lower() == "sed"
        and len(tokens) >= 4
        and tokens[1] == "-n"
    ):
        return bool(
            _SED_PRINT_ONLY_SCRIPT_RE.fullmatch(tokens[2])
            and _auditor_safe_input_paths(tokens[3:])
        )
    # Check for safe git rev-list inspection commands
    if len(tokens) >= 2 and tokens[0].lower() == "git" and tokens[1].lower() == "rev-list":
        # If the command passes validation, it's a supported command (not just read-only)
        # so return False so it doesn't get the "recoverable" marker
        return False
    return False


def _recoverable_read_only_denial() -> AuditorCommandDenial:
    """Build the stable validation response for safe-but-unsupported syntax."""

    return AuditorCommandDenial(
        "Error: auditor capability policy rejected unsupported read-only shell "
        "syntax; run each inspection separately or use search_files and bounded "
        "read_file calls. The command was not executed. "
        f"[reason={AUDITOR_READ_ONLY_SYNTAX_REASON}]",
        recoverable=True,
        reason=AUDITOR_READ_ONLY_SYNTAX_REASON,
    )


def _get_auditor_validation_targets(project_id: str | None = None) -> list[str]:
    """Return the list of approved validation targets for an auditor.
    
    When project_id is provided, looks up the project's auditor_validation_targets
    configuration. Falls back to the default list when:
    - project_id is None
    - the project is not found
    - the project's auditor_validation_targets is empty
    
    Default targets are: ['test', 'test-serial', 'check-secrets']
    """
    default_targets = ["test", "test-serial", "check-secrets"]
    
    if not project_id:
        return default_targets
    
    try:
        from oompah.projects import ProjectStore
        store = ProjectStore()
        project = store.get(project_id)
        if project and project.auditor_validation_targets:
            return project.auditor_validation_targets
    except Exception:
        # If we can't load the project, fall back to defaults
        pass
    
    return default_targets


def _build_auditor_command_regex(validation_targets: list[str] | None = None) -> re.Pattern:
    """Build a compiled regex for auditor command validation.
    
    Generates a regex that allows:
    - Read-only file/git inspection commands (pwd, ls, grep, git status, etc.)
    - Python testing with pytest/unittest
    - Make targets from the provided validation_targets list
    - Other safe tools like ruff, mypy, black --check, npm test, etc.
    - oompah task view
    
    When validation_targets is None, uses the default list.
    """
    if validation_targets is None:
        validation_targets = _get_auditor_validation_targets()
    
    # Escape each target for use in regex (they should be simple alphanumeric-dash)
    make_targets = "|".join(re.escape(target) for target in validation_targets)
    
    pattern_str = (
        r"^(?:"
        r"(?:pwd|ls|find|head|tail|cat|file|stat|readlink|rg|grep|git\s+"
        r"(?:status|diff|log|show|rev-parse|ls-files|branch|describe|whatchanged|merge-base|rev-list))\b.*$"
        r"|(?:pytest|py\.test|python(?:\d+(?:\.\d+)?)?\s+-m\s+"
        r"(?:pytest|unittest|compileall))\b.*$"
        # Make targets: must match exactly with no trailing word/dash characters.
        # After the target, only whitespace or end-of-string are allowed.
        rf"|(?:make\s+(?:{make_targets})(?:\s|$))"
        r"|(?:ruff|mypy|black\s+--check|npm\s+test|pnpm\s+test|yarn\s+test)\b.*$"
        r"|(?:oompah\s+task\s+view)\b.*$"
        r")"
    )
    
    return re.compile(pattern_str, re.IGNORECASE)


def check_auditor_command(command: str, project_id: str | None = None) -> str | None:
    """Return a denial for commands outside the read/test allowlist.
    
    Denials are classified as recoverable (contract mismatch) or fatal (security
    violation). Recoverable denials do not consume the auditor's policy budget.
    
    Security violations checked first (always fatal):
    - Path escapes (absolute paths, parent traversal, /home, etc.)
    - Credential file access (.env, .git/config, private keys, etc.)
    - State-changing mutations (rm, git commit/push, etc.)
    - File redirection to write/append files (>, >>)
    - Process control (eval, xargs, etc.)
    
    Contract mismatches checked after security (recoverable if read-only):
    - Commands outside the project's validation contract
    - Compound read-only syntax (pipes, semicolons) without mutations
    
    Parameters
    ----------
    command : str
        The shell command to validate.
    project_id : str | None
        Optional project ID to look up project-specific validation targets.
        When None, uses the default allowlist.
    """

    normalized = str(command or "").strip()
    
    # Early return for read-only inspection commands recognized as supported
    if _is_read_only_inspection_command(normalized):
        return _recoverable_read_only_denial()
    
    # Security checks: HIGH-SEVERITY violations always fatal, checked first
    # before contract validation to prevent bypassing security via contract mismatches.
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
    
    # Check for state-changing mutations and dangerous constructs that must be
    # denied regardless of contract configuration
    if _AUDITOR_COMMAND_MUTATION_RE.search(normalized):
        has_state_change = _AUDITOR_STATE_CHANGE_RE.search(normalized)
        has_file_redirection = _AUDITOR_FILE_REDIRECTION_RE.search(normalized)
        has_compound = _AUDITOR_COMPOUND_RE.search(normalized)
        
        # If it's a compound read-only shell pipeline without state changes or
        # file redirection, it's unsupported syntax but not a security violation.
        # This will be fatal or recoverable depending on contract matching below.
        if has_compound and not has_state_change and not has_file_redirection:
            # Don't return yet; check contract below and handle accordingly
            pass
        else:
            # Actual mutation, file redirection, or process control: always fatal
            return AuditorCommandDenial(
                "Error: read-only auditor capability policy denied a mutating or "
                "compound shell command; auditors cannot edit, commit, push, merge, "
                "or change state",
                reason="auditor_mutating_shell_command",
            )
    
    # Build the contract regex based on project configuration
    command_regex = _build_auditor_command_regex(
        _get_auditor_validation_targets(project_id)
    )
    
    # Special validation for git rev-list: ensure only safe flags are used.
    # This must happen regardless of contract matching because the contract
    # allows "git rev-list" but only with safe flags and operands.
    # Unsupported but read-only flags (like --graph, --pretty) return recoverable
    # errors since they are still inspection operations. Truly dangerous syntax
    # (compound commands, redirection, command substitution) is caught earlier
    # in the mutation and security checks.
    tokens = _auditor_shell_tokens(normalized)
    if tokens and len(tokens) >= 2 and tokens[0].lower() == "git" and tokens[1].lower() == "rev-list":
        if not _is_safe_git_rev_list_command(normalized):
            # git rev-list with unsupported flags: recoverable (still read-only)
            return _recoverable_read_only_denial()
    
    # Contract validation: check if command matches the project's validation targets
    if not normalized or not command_regex.fullmatch(normalized):
        # Command is outside the validation contract.
        # Only return recoverable for specific safe patterns to avoid passing through
        # dangerous constructs that the mutation regex might miss (e.g., system() inside
        # awk strings). For everything else, return fatal.
        
        tokens = _auditor_shell_tokens(normalized)
        if tokens:
            first_token = tokens[0].lower()
            
            # make <target> commands are recoverable outside contract (typically non-mutating by convention)
            if first_token == "make" and len(tokens) >= 2:
                # make target command outside contract: recoverable
                validation_targets = _get_auditor_validation_targets(project_id)
                make_targets_str = ", ".join(f"make {t}" for t in validation_targets)
                return AuditorCommandDenial(
                    "Error: auditor capability policy permits only read-only repository "
                    "inspection and configured test commands; command denied. "
                    f"Allowed validation targets: {make_targets_str}. "
                    "Alternatively, use search_files and bounded read_file for inspection. "
                    "The command was not executed. "
                    f"[reason={AUDITOR_READ_ONLY_SYNTAX_REASON}]",
                    recoverable=True,
                    reason=AUDITOR_READ_ONLY_SYNTAX_REASON,
                )
            
            # Compound read-only pipeline outside contract: recoverable, suggest splitting
            if _AUDITOR_COMPOUND_RE.search(normalized):
                return AuditorCommandDenial(
                    "Error: auditor capability policy rejected unsupported read-only "
                    "shell syntax; run each inspection separately or use search_files "
                    "and bounded read_file calls. The command was not executed. "
                    f"[reason={AUDITOR_READ_ONLY_SYNTAX_REASON}]",
                    recoverable=True,
                    reason=AUDITOR_READ_ONLY_SYNTAX_REASON,
                )
        
        # For everything else outside the contract: deny with fatal
        # (conservative approach to avoid passing through dangerous constructs)
        return (
            "Error: auditor capability policy permits only read-only repository "
            "inspection and configured test commands; command denied"
        )
    
    # Command matches contract: check for unsupported read-only syntax
    # (This is the same check as before, but only for contract-matching commands)
    if _AUDITOR_COMMAND_MUTATION_RE.search(normalized):
        if (
            _AUDITOR_COMPOUND_RE.search(normalized)
            and not _AUDITOR_STATE_CHANGE_RE.search(normalized)
            and not _AUDITOR_FILE_REDIRECTION_RE.search(normalized)
        ):
            return AuditorCommandDenial(
                "Error: auditor capability policy rejected unsupported read-only "
                "shell syntax; run each inspection separately or use search_files "
                "and bounded read_file calls. The command was not executed. "
                f"[reason={AUDITOR_READ_ONLY_SYNTAX_REASON}]",
                recoverable=True,
                reason=AUDITOR_READ_ONLY_SYNTAX_REASON,
            )
    
    return None


__all__ = [
    "AUDITOR_ALLOWED_TOOLS",
    "AUDITOR_CAPABILITY_POLICY",
    "AUDITOR_FOCUS_NAME",
    "AUDITOR_MUTATING_TOOLS",
    "AUDITOR_READ_ONLY_SYNTAX_REASON",
    "AUDITOR_RESULT_TOOL_NAME",
    "AUDITOR_RESULT_TOOL_SCHEMA",
    "AuditorCommandDenial",
    "AuditorCapabilityPolicy",
    "AuditorTargetContract",
    "_MAX_RESULT_MESSAGE_LENGTH",
    "_MAX_SAFE_EVIDENCE_ENTRIES",
    "_MAX_SAFE_EVIDENCE_KEY_LENGTH",
    "_MAX_SAFE_EVIDENCE_VALUE_LENGTH",
    "_MAX_RESULT_LIST_ITEMS",
    "_MAX_RESULT_LIST_ITEM_LENGTH",
    "_RESULT_SECRET_RE",
    "_SECRET_KEY_RE",
    "auditor_target_contract",
    "check_auditor_session_target",
    "check_auditor_command",
    "is_recoverable_auditor_command_denial",
    "pending_auditor_target",
    "parse_auditor_result",
    "submit_auditor_result",
]
