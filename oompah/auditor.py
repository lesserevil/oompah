"""Contracts and capability boundaries for the reserved completion auditor.

The completion auditor is deliberately a different kind of agent from the
normal coding foci.  It may inspect a worktree and run verification commands,
then submit one structured result to the audit scheduler.  It must never get a
write-capable tool merely because task text asks for one.
"""

from __future__ import annotations

import json
import math
import os
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
AUDITOR_VALIDATION_CONFIGURATION_REASON = "auditor_validation_configuration"
AUDITOR_VALIDATION_DEADLINE_REASON = "auditor_validation_deadline_exceeded"
AUDITOR_UNAPPROVED_VALIDATION_TARGET_REASON = "auditor_unapproved_validation_target"
AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV = (
    "OOMPAH_AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS"
)
DEFAULT_AUDITOR_VALIDATION_TARGETS = (
    "test",
    "test-serial",
    "check-secrets",
)
DEFAULT_AUDITOR_COMMAND_TIMEOUT_SECONDS = 720
_AUDITOR_VALIDATION_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class AuditorValidationTargetBudget:
    """One exact approved Make target and its execution budget."""

    target: str
    deadline_seconds: int
    expected_seconds: int
    deadline_source: str
    expected_source: str


@dataclass(frozen=True)
class AuditorValidationContract:
    """Validated, project-scoped auditor validation policy snapshot."""

    project_id: str
    targets: tuple[AuditorValidationTargetBudget, ...]
    configuration_error: str | None = None

    @property
    def feasible(self) -> bool:
        return self.configuration_error is None

    def budget_for_target(self, target: str) -> AuditorValidationTargetBudget | None:
        return next((item for item in self.targets if item.target == target), None)


def _positive_seconds(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _global_auditor_command_timeout(raw: str | None = None) -> int:
    value = os.environ.get("OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS") if raw is None else raw
    if value is None or not str(value).strip():
        return DEFAULT_AUDITOR_COMMAND_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_AUDITOR_COMMAND_TIMEOUT_SECONDS
    if not math.isfinite(parsed) or parsed <= 0:
        return DEFAULT_AUDITOR_COMMAND_TIMEOUT_SECONDS
    return max(1, int(math.ceil(parsed)))


def _expected_seconds_from_environment(
    raw: str | None = None,
) -> tuple[dict[str, int], str | None]:
    value = (
        os.environ.get(AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV)
        if raw is None
        else raw
    )
    if value is None or not str(value).strip():
        return {}, None
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        return {}, (
            f"{AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV} must be a JSON object: {exc}"
        )
    if not isinstance(decoded, dict):
        return {}, f"{AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV} must be a JSON object"
    normalized: dict[str, int] = {}
    for raw_target, raw_seconds in decoded.items():
        target = str(raw_target).strip()
        if not _AUDITOR_VALIDATION_TARGET_RE.fullmatch(target):
            return {}, (
                f"{AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV} contains unsafe "
                f"target {target!r}"
            )
        try:
            normalized[target] = _positive_seconds(
                raw_seconds,
                field_name=(
                    f"{AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV}[{target!r}]"
                ),
            )
        except ValueError as exc:
            return {}, str(exc)
    return normalized, None


def build_auditor_validation_contract(
    project: Any = None,
    *,
    global_timeout_seconds: int | None = None,
    raw_environment_expected_seconds: str | None = None,
) -> AuditorValidationContract:
    """Build the immutable effective validation contract for one project.

    Explicit targets without expected-duration evidence fail closed. Legacy
    implicit defaults remain compatible by being omitted until observed or
    configured evidence makes them safe to advertise. A shorter deadline is
    always an impossible configuration and blocks launch before persistence.
    """

    project_id = str(getattr(project, "id", "") or "")
    raw_configured_targets = getattr(project, "auditor_validation_targets", None)
    explicitly_configured = bool(raw_configured_targets)
    configured_targets = list(
        raw_configured_targets or DEFAULT_AUDITOR_VALIDATION_TARGETS
    )
    targets: list[str] = []
    seen: set[str] = set()
    errors: list[str] = []
    for raw_target in configured_targets:
        if not isinstance(raw_target, str):
            errors.append("auditor_validation_targets entries must be strings")
            continue
        target = raw_target.strip()
        if not _AUDITOR_VALIDATION_TARGET_RE.fullmatch(target):
            errors.append(f"unsafe auditor validation target {target!r}")
            continue
        if target in seen:
            errors.append(f"duplicate auditor validation target {target!r}")
            continue
        targets.append(target)
        seen.add(target)

    raw_deadlines = getattr(project, "auditor_validation_target_deadlines", {}) or {}
    raw_expected = (
        getattr(project, "auditor_validation_target_expected_seconds", {}) or {}
    )
    raw_observed = (
        getattr(project, "auditor_validation_target_observed_seconds", {}) or {}
    )
    if not isinstance(raw_deadlines, dict):
        errors.append("auditor_validation_target_deadlines must be an object")
        raw_deadlines = {}
    if not isinstance(raw_expected, dict):
        errors.append("auditor_validation_target_expected_seconds must be an object")
        raw_expected = {}
    if not isinstance(raw_observed, dict):
        errors.append("observed auditor validation durations must be an object")
        raw_observed = {}

    deadlines: dict[str, int] = {}
    expected: dict[str, int] = {}
    observed: dict[str, int] = {}
    for field_name, raw_mapping, destination in (
        ("auditor_validation_target_deadlines", raw_deadlines, deadlines),
        ("auditor_validation_target_expected_seconds", raw_expected, expected),
        ("observed auditor validation durations", raw_observed, observed),
    ):
        for raw_target, raw_seconds in raw_mapping.items():
            target = str(raw_target).strip()
            if target not in seen:
                errors.append(f"{field_name} contains unapproved target {target!r}")
                continue
            try:
                destination[target] = _positive_seconds(
                    raw_seconds,
                    field_name=f"{field_name}[{target!r}]",
                )
            except ValueError as exc:
                errors.append(str(exc))

    environment_expected, environment_error = _expected_seconds_from_environment(
        raw_environment_expected_seconds
    )
    if environment_error:
        errors.append(environment_error)

    if global_timeout_seconds is None:
        global_timeout = _global_auditor_command_timeout()
    else:
        try:
            global_timeout = _positive_seconds(
                global_timeout_seconds,
                field_name="global auditor command timeout",
            )
        except ValueError as exc:
            errors.append(str(exc))
            global_timeout = DEFAULT_AUDITOR_COMMAND_TIMEOUT_SECONDS

    budgets: list[AuditorValidationTargetBudget] = []
    for target in targets:
        deadline = deadlines.get(target, global_timeout)
        candidates = [
            ("project", expected.get(target)),
            ("observed", observed.get(target)),
            ("environment", environment_expected.get(target)),
        ]
        expected_source, expected_seconds = max(
            (
                (source, seconds)
                for source, seconds in candidates
                if seconds is not None
            ),
            key=lambda item: item[1],
            default=(None, None),
        )
        if expected_seconds is None:
            if explicitly_configured or target in deadlines or target in expected:
                errors.append(
                    f"project {project_id or '(default)'} target {target!r} has no "
                    "configured or observed expected duration"
                )
            # Legacy default targets are not advertised or executable until
            # duration evidence makes their deadline feasibility knowable.
            continue
        assert expected_source is not None
        budget = AuditorValidationTargetBudget(
            target=target,
            deadline_seconds=deadline,
            expected_seconds=expected_seconds,
            deadline_source="project" if target in deadlines else "global",
            expected_source=expected_source,
        )
        budgets.append(budget)
        if expected_seconds is not None and expected_seconds > deadline:
            errors.append(
                f"project {project_id or '(default)'} target {target!r} "
                f"expected_seconds={expected_seconds} exceeds "
                f"deadline_seconds={deadline} "
                f"(deadline_source={budget.deadline_source}, "
                f"expected_source={budget.expected_source})"
            )

    if project is not None and not budgets and not errors:
        errors.append(
            f"project {project_id or '(unknown)'} has no feasible auditor "
            "validation targets; configure an approved target with a positive "
            "expected duration or provide compatible completed gate evidence"
        )

    return AuditorValidationContract(
        project_id=project_id,
        targets=tuple(budgets),
        configuration_error="; ".join(errors) if errors else None,
    )


def resolve_auditor_validation_budget(
    command: str,
    project: Any = None,
    *,
    global_timeout_seconds: int | None = None,
) -> tuple[AuditorValidationTargetBudget | None, str | None]:
    """Resolve an exact ``make TARGET`` after command policy authorization.

    This function never grants command authority. Callers must first run
    :func:`check_auditor_command` through the ordinary shell policy.
    """

    contract = build_auditor_validation_contract(
        project,
        global_timeout_seconds=global_timeout_seconds,
    )
    if contract.configuration_error:
        return None, contract.configuration_error
    try:
        tokens = shlex.split(str(command or ""), posix=True)
    except ValueError:
        return None, None
    if len(tokens) != 2 or tokens[0] != "make":
        return None, None
    return contract.budget_for_target(tokens[1]), None


def auditor_validation_timeout_message(
    budget: AuditorValidationTargetBudget,
) -> str:
    expected = str(budget.expected_seconds)
    return (
        "Error: auditor validation target "
        f"{budget.target!r} exceeded deadline_seconds={budget.deadline_seconds} "
        f"(expected_seconds={expected}). Do not fall back to a broader or "
        "predictably slower target; submit a configuration/code failure with "
        "this evidence. "
        f"[reason={AUDITOR_VALIDATION_DEADLINE_REASON} target={budget.target} "
        f"deadline_seconds={budget.deadline_seconds} expected_seconds={expected}]"
    )


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

#: Maximum nesting accepted from ``safe_evidence`` before it is flattened to
#: the coordinator's durable scalar evidence contract.
_MAX_SAFE_EVIDENCE_DEPTH = 4

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
    # Bearer values are unsafe even without an assignment delimiter.  Exclude
    # common prose continuations so phrases such as "Bearer syntax" do not
    # become false credential matches.
    r"|Bearer\s+(?!(?:token|tokens|syntax|header|headers|scheme|value|values|credential|credentials|authentication)\b)[A-Za-z0-9_./+\-]{1,}"
    # JWT: three dot-separated Base64url segments (header.payload.signature)
    r"|(?:[A-Za-z0-9\-_]{10,}\.){2}[A-Za-z0-9\-_]{10,}"
    # Explicit Bearer / credential assignment patterns.  Assignment values
    # are rejected even when short: credentials are not required to meet a
    # minimum length before they become unsafe to echo into a tracker.
    r"|authorization\s*[=:]\s*(?:Bearer\s+)?[^\s,;]+"
    r"|(?:Bearer|token|api[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd|secret)\s*[=:]\s*[^\s,;]+"
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

# Only values that make their inertness explicit may be normalized. Complete
# credential-shaped strings are indistinguishable from live credentials and
# therefore fail closed even when surrounding prose calls them examples.
_EXPLICIT_CREDENTIAL_PLACEHOLDER_RE = re.compile(
    r"(?:"
    r"\.\.\."
    r"|\*{2,}"
    r"|x{6,}"
    r"|<(?:redacted|masked|placeholder|example|sample|token|secret|password|passwd|api[_-]?key|value)>"
    r"|\[(?:redacted|masked|placeholder|example|sample)[^\]\r\n]{0,48}\]"
    r"|\b(?:redacted|masked|placeholder|example|sample|dummy|fake)\b"
    r"|\b(?:your|test)[_-]?(?:token|secret|password|passwd|api[_-]?key|key)\b"
    r"|\bnot[_-]?a[_-]?real[_-]?(?:token|secret|password|key)\b"
    r")",
    re.IGNORECASE,
)


class _UnsafeAuditorCredential(ValueError):
    """A credential-shaped result value that cannot be safely normalized."""


def _unsafe_credential_error(field_path: str) -> _UnsafeAuditorCredential:
    """Build non-observable, field-specific retry feedback."""

    if field_path.endswith(" key"):
        correction = (
            "rename it to a neutral evidence label and replace any credential "
            "value with an explicit placeholder such as <redacted>"
        )
    else:
        correction = (
            "replace the value with an explicit placeholder such as <redacted>"
        )
    return _UnsafeAuditorCredential(
        f"auditor result {field_path} contains credential material that cannot "
        f"be safely normalized; {correction} and resubmit"
    )


def _credential_match_is_placeholder(match: re.Match[str], text: str) -> bool:
    """Return whether a credential-pattern match is demonstrably inert."""

    matched_text = match.group(0)
    if _EXPLICIT_CREDENTIAL_PLACEHOLDER_RE.search(matched_text):
        return True
    if matched_text.upper().endswith("EXAMPLE"):
        # AWS publishes an exact inert access-key example with this suffix.
        return True

    # A PEM header is syntax rather than key material when no payload follows
    # it on another line. A header with multiline content remains
    # indistinguishable from a real private key and is rejected.
    if "PRIVATE KEY" in matched_text.upper():
        tail = text[match.end():]
        return bool(re.fullmatch(r"-{0,5}[\"')\].,;:]*\s*", tail))
    return False


def _redact_credential_patterns(text: str, field_name: str) -> tuple[str, list[str]]:
    """Redact credential-like patterns in free-text fields.

    Returns a tuple of (redacted_text, redaction_notes) where redaction_notes
    lists what was redacted for auditor feedback.

    The redaction is deterministic: the same input always produces the same
    output, enabling idempotent resubmission. Redaction uses descriptive markers
    like [REDACTED-github-token] so the auditor can understand what was normalized.
    """
    redactions: list[str] = []

    for match in _RESULT_SECRET_RE.finditer(text):
        if not _credential_match_is_placeholder(match, text):
            raise _unsafe_credential_error(field_name)

    def replace_match(match: re.Match[str]) -> str:
        matched_text = match.group(0)
        matched_lower = matched_text.lower()

        if any(prefix in matched_lower for prefix in ("ghp_", "ghs_", "gho_", "github_pat_")):
            marker = "[REDACTED-github-token]"
            redactions.append(f"{field_name}: GitHub token placeholder")
        elif "glpat-" in matched_lower or "gldt-" in matched_lower:
            marker = "[REDACTED-gitlab-token]"
            redactions.append(f"{field_name}: GitLab token placeholder")
        elif "xox" in matched_lower:
            marker = "[REDACTED-slack-token]"
            redactions.append(f"{field_name}: Slack token placeholder")
        elif "bearer" in matched_lower:
            marker = "[REDACTED-bearer-token]"
            redactions.append(f"{field_name}: Bearer token placeholder")
        elif "sk-" in matched_lower:
            marker = "[REDACTED-api-key]"
            redactions.append(f"{field_name}: API key placeholder")
        elif "akia" in matched_lower:
            marker = "[REDACTED-aws-key]"
            redactions.append(f"{field_name}: AWS credential placeholder")
        elif "begin" in matched_lower and "private key" in matched_lower:
            marker = "[REDACTED-private-key]"
            redactions.append(f"{field_name}: private key header")
        elif any(sep in matched_text for sep in ("=", ":")):
            marker = "[REDACTED-credential]"
            redactions.append(f"{field_name}: credential assignment placeholder")
        else:
            if "." in matched_text and len(matched_text) > 50:
                marker = "[REDACTED-jwt-like]"
                redactions.append(f"{field_name}: JWT-like token placeholder")
            else:
                marker = "[REDACTED-credential-pattern]"
                redactions.append(f"{field_name}: credential placeholder")
        return marker

    redacted = _RESULT_SECRET_RE.sub(replace_match, text)
    return redacted, redactions


def _redact_safe_evidence(
    safe_evidence: Mapping[str, Any],
) -> tuple[dict[str, str], list[str]]:
    """Recursively validate and flatten safe evidence after redaction.

    Complete credential-shaped values fail closed. Explicit placeholders are
    normalized deterministically. Keys are never included in an error until
    they have passed the same credential checks.
    """
    redactions: list[str] = []
    redacted: dict[str, str] = {}

    leaf_count = 0

    def add_leaf(path: str, value: str, field_path: str) -> None:
        nonlocal leaf_count
        leaf_count += 1
        if leaf_count > _MAX_SAFE_EVIDENCE_ENTRIES:
            raise ValueError(
                "safe_evidence exceeds maximum leaf count "
                f"({_MAX_SAFE_EVIDENCE_ENTRIES})"
            )
        redacted_value, value_redactions = _redact_credential_patterns(
            value, f"{field_path} value"
        )
        if len(redacted_value) > _MAX_SAFE_EVIDENCE_VALUE_LENGTH:
            raise ValueError(
                f"{field_path} value exceeds maximum length "
                f"({_MAX_SAFE_EVIDENCE_VALUE_LENGTH} characters)"
            )
        if path in redacted:
            raise ValueError("safe_evidence contains ambiguous nested paths")
        redacted[path] = redacted_value
        redactions.extend(value_redactions)

    def walk(value: Any, path: str, field_path: str, depth: int) -> None:
        if depth > _MAX_SAFE_EVIDENCE_DEPTH:
            raise ValueError(
                f"{field_path} exceeds maximum nesting depth "
                f"({_MAX_SAFE_EVIDENCE_DEPTH})"
            )
        if isinstance(value, str):
            add_leaf(path, value, field_path)
            return
        if isinstance(value, Mapping):
            if len(value) > _MAX_SAFE_EVIDENCE_ENTRIES:
                raise ValueError(
                    f"{field_path} exceeds maximum container item "
                    f"count ({_MAX_SAFE_EVIDENCE_ENTRIES})"
                )
            for index, (key, child) in enumerate(value.items(), start=1):
                entry_field_path = f"{field_path} entry {index}"
                if not isinstance(key, str):
                    raise ValueError(f"{entry_field_path} key must be a string")
                if len(key) > _MAX_SAFE_EVIDENCE_KEY_LENGTH:
                    raise ValueError(
                        f"{entry_field_path} key exceeds maximum length "
                        f"({_MAX_SAFE_EVIDENCE_KEY_LENGTH} characters)"
                    )
                if _RESULT_SECRET_RE.search(key) or _SECRET_KEY_RE.search(key):
                    raise _unsafe_credential_error(f"{entry_field_path} key")
                child_path = f"{path}.{key}" if path else key
                child_field_path = f"{field_path}.{key}"
                if len(child_path) > _MAX_SAFE_EVIDENCE_KEY_LENGTH:
                    raise ValueError(
                        f"{child_field_path} flattened key exceeds "
                        f"maximum length ({_MAX_SAFE_EVIDENCE_KEY_LENGTH} characters)"
                    )
                walk(child, child_path, child_field_path, depth + 1)
            return
        if isinstance(value, list):
            if len(value) > _MAX_SAFE_EVIDENCE_ENTRIES:
                raise ValueError(
                    f"{field_path} exceeds maximum container item "
                    f"count ({_MAX_SAFE_EVIDENCE_ENTRIES})"
                )
            for index, child in enumerate(value):
                walk(
                    child,
                    f"{path}[{index}]",
                    f"{field_path}[{index}]",
                    depth + 1,
                )
            return
        raise ValueError(f"{field_path} must be a string, object, or array")

    walk(safe_evidence, "", "safe_evidence", 0)
    return redacted, redactions


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
    selected_ref: str | None = None
    selected_sha: str | None = None
    landing_revision: str | None = None

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
        if (self.selected_ref is None) != (self.selected_sha is None):
            raise ValueError(
                "auditor target selected_ref and selected_sha must be supplied together"
            )
        if self.selected_ref is not None:
            if not isinstance(self.selected_ref, str) or not isinstance(
                self.selected_sha, str
            ):
                raise ValueError(
                    "auditor target selected_ref and selected_sha must be strings"
                )
            selected_ref = self.selected_ref.strip()
            selected_sha = self.selected_sha.strip().lower()
            if not selected_ref:
                raise ValueError("auditor target selected_ref must be non-empty")
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", selected_sha):
                raise ValueError(
                    "auditor target selected_sha must be a full Git object ID"
                )
            if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", selected_ref):
                if selected_ref.lower() != selected_sha:
                    raise ValueError(
                        "immutable auditor target selected_ref must equal selected_sha"
                    )
            object.__setattr__(self, "selected_ref", selected_ref)
            object.__setattr__(self, "selected_sha", selected_sha)
        if self.landing_revision is not None:
            if not isinstance(self.landing_revision, str):
                raise ValueError(
                    "auditor target landing_revision must be a string or null"
                )
            landing_revision = self.landing_revision.strip().lower()
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", landing_revision):
                raise ValueError(
                    "auditor target landing_revision must be a full Git object ID"
                )
            if self.selected_ref is None:
                raise ValueError(
                    "auditor target landing_revision requires a revision binding"
                )
            object.__setattr__(self, "landing_revision", landing_revision)

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
        if self.selected_ref is not None:
            result["selected_ref"] = self.selected_ref
            result["selected_sha"] = self.selected_sha
        if self.landing_revision is not None:
            result["landing_revision"] = self.landing_revision
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

    def optional_string(key: str) -> str | None:
        value = _target_value(target, key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"auditor target {key} must be a string or null")
        return value.strip() or None

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
        selected_ref=optional_string("selected_ref"),
        selected_sha=optional_string("selected_sha"),
        landing_revision=optional_string("landing_revision"),
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
                        selected_ref=target.selected_ref,
                        selected_sha=target.selected_sha,
                        landing_revision=target.landing_revision,
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


def _safe_evidence_value_schema(depth: int = 1) -> dict[str, Any]:
    """Build the bounded recursive JSON schema for safe-evidence values."""

    string_schema: dict[str, Any] = {
        "type": "string",
        "maxLength": _MAX_SAFE_EVIDENCE_VALUE_LENGTH,
    }
    if depth >= _MAX_SAFE_EVIDENCE_DEPTH:
        return string_schema
    return {
        "anyOf": [
            string_schema,
            {
                "type": "object",
                "maxProperties": _MAX_SAFE_EVIDENCE_ENTRIES,
                "additionalProperties": _safe_evidence_value_schema(depth + 1),
            },
            {
                "type": "array",
                "maxItems": _MAX_SAFE_EVIDENCE_ENTRIES,
                "items": _safe_evidence_value_schema(depth + 1),
            },
        ]
    }


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
                    "maxProperties": _MAX_SAFE_EVIDENCE_ENTRIES,
                    "additionalProperties": _safe_evidence_value_schema(),
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
    - Enforces maximum lengths for ``message`` and each recursively flattened
      ``safe_evidence`` key/value pair to prevent oversized output.
    - Normalizes explicit credential placeholders while rejecting complete
      credential-like values before they can reach coordinator comments.
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
                "Error: invalid auditor result fields; submit only "
                "the fields defined by the submit_audit_result schema"
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
        redacted_message, _ = _redact_credential_patterns(message, "message")
        if len(redacted_message) > _MAX_RESULT_MESSAGE_LENGTH:
            return None, (
                f"Error: auditor result message exceeds maximum length after redaction "
                f"({len(redacted_message)} > {_MAX_RESULT_MESSAGE_LENGTH} characters)"
            )
        message = redacted_message

        # --- Safe evidence size and content checks with redaction ---
        safe_evidence = args.get("safe_evidence")
        if safe_evidence is not None:
            if not isinstance(safe_evidence, Mapping):
                return None, "Error: auditor result safe_evidence must be an object"
            if len(safe_evidence) > _MAX_SAFE_EVIDENCE_ENTRIES:
                return None, (
                    f"Error: auditor result safe_evidence exceeds maximum entry count "
                    f"({len(safe_evidence)} > {_MAX_SAFE_EVIDENCE_ENTRIES})"
                )
            redacted_safe_evidence, _ = _redact_safe_evidence(safe_evidence)
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
            for index, item in enumerate(raw_items):
                if not isinstance(item, str):
                    raise ValueError(f"{field_name} items must be strings")
                if len(item) > _MAX_RESULT_LIST_ITEM_LENGTH:
                    raise ValueError(
                        f"{field_name} item exceeds maximum length "
                        f"({_MAX_RESULT_LIST_ITEM_LENGTH} characters)"
                    )
                # Redact credential-like patterns from questions/instructions
                redacted_item, _ = _redact_credential_patterns(
                    item, f"{field_name}[{index}]"
                )
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
    except _UnsafeAuditorCredential as exc:
        return None, f"Error: {exc}"
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


_AUDITOR_SAFE_REVISION_RE = re.compile(r"^[A-Za-z0-9_./+@=,:^~*-]+$")
_AUDITOR_SAFE_REF_PATTERN_RE = re.compile(r"^[A-Za-z0-9_./+@=,:*-]+$")
_AUDITOR_SAFE_REF_FORMAT_RE = re.compile(r"^[A-Za-z0-9_./+@=,:()%*<> -]+$")


def _auditor_safe_revision(value: str) -> bool:
    return bool(
        value
        and not value.startswith("-")
        and _AUDITOR_SAFE_REVISION_RE.fullmatch(value)
        and not _AUDITOR_PATH_ESCAPE_RE.search(value)
        and not _AUDITOR_SECRET_PATH_RE.search(value)
    )


def _is_safe_git_ls_tree_inspection(tokens: list[str]) -> bool:
    """Recognize bounded, read-only ``git ls-tree`` requests.

    The optional ``--`` separator is validated explicitly. Workspace-relative
    paths are also accepted in Git's unseparated form, while unknown flags and
    unsafe revisions/pathspecs fail closed.
    """

    allowed_flags = {
        "-r",
        "-d",
        "-t",
        "-l",
        "--name-only",
        "--name-status",
        "--object-only",
        "--full-name",
        "--full-tree",
    }
    index = 2
    while index < len(tokens) and tokens[index] in allowed_flags:
        index += 1
    if index >= len(tokens) or not _auditor_safe_revision(tokens[index]):
        return False
    index += 1
    if index == len(tokens):
        return True
    paths = tokens[index + 1 :] if tokens[index] == "--" else tokens[index:]
    return not paths or _auditor_safe_input_paths(paths)


def _is_safe_git_ls_remote_inspection(tokens: list[str]) -> bool:
    """Recognize non-executed, read-only queries of the configured origin."""

    allowed_flags = {"--heads", "--tags", "--refs", "--exit-code", "-h", "-t"}
    index = 2
    while index < len(tokens) and tokens[index] in allowed_flags:
        index += 1
    if index >= len(tokens) or tokens[index] != "origin":
        return False
    patterns = tokens[index + 1 :]
    return all(
        pattern
        and not pattern.startswith("-")
        and _AUDITOR_SAFE_REF_PATTERN_RE.fullmatch(pattern)
        and not _AUDITOR_PATH_ESCAPE_RE.search(pattern)
        and not _AUDITOR_SECRET_PATH_RE.search(pattern)
        for pattern in patterns
    )


def _is_safe_git_for_each_ref_inspection(tokens: list[str]) -> bool:
    """Recognize format-limited local-ref inspection without executing it."""

    index = 2
    while index < len(tokens) and tokens[index].startswith("--format="):
        value = tokens[index].partition("=")[2]
        if not value or not _AUDITOR_SAFE_REF_FORMAT_RE.fullmatch(value):
            return False
        index += 1
    if index + 1 < len(tokens) and tokens[index] == "--format":
        if not _AUDITOR_SAFE_REF_FORMAT_RE.fullmatch(tokens[index + 1]):
            return False
        index += 2
    refs = tokens[index:]
    return bool(refs) and all(
        ref
        and not ref.startswith("-")
        and _AUDITOR_SAFE_REF_PATTERN_RE.fullmatch(ref)
        and not _AUDITOR_PATH_ESCAPE_RE.search(ref)
        and not _AUDITOR_SECRET_PATH_RE.search(ref)
        for ref in refs
    )


def _is_safe_wc_line_count(tokens: list[str]) -> bool:
    return len(tokens) >= 3 and tokens[1] == "-l" and _auditor_safe_input_paths(
        tokens[2:]
    )


def _is_read_only_inspection_command(command: str) -> bool:
    """Recognize safe inspections that the shell contract does not execute."""

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
    if len(tokens) >= 2 and tokens[0].lower() == "git":
        subcommand = tokens[1].lower()
        if subcommand == "ls-tree":
            return _is_safe_git_ls_tree_inspection(tokens)
        if subcommand == "ls-remote":
            return _is_safe_git_ls_remote_inspection(tokens)
        if subcommand == "for-each-ref":
            return _is_safe_git_for_each_ref_inspection(tokens)
    if tokens[0].lower() == "wc":
        return _is_safe_wc_line_count(tokens)
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


def _get_auditor_validation_targets(
    project_id: str | None = None,
    *,
    project: Any = None,
) -> list[str]:
    """Return the list of approved validation targets for an auditor.

    When project_id is provided, looks up the project's auditor_validation_targets
    configuration. Falls back to the default list when:
    - project_id is None
    - the project is not found
    - the project's auditor_validation_targets is empty

    Default targets are: ['test', 'test-serial', 'check-secrets']
    """
    default_targets = list(DEFAULT_AUDITOR_VALIDATION_TARGETS)

    if project is not None:
        raw_targets = list(
            getattr(project, "auditor_validation_targets", None) or default_targets
        )
        contract = build_auditor_validation_contract(project)
        if contract.configuration_error:
            # Let the execution layer return the truthful configuration
            # failure for an otherwise authorized exact target.
            return raw_targets
        return [budget.target for budget in contract.targets]

    if not project_id:
        return default_targets

    try:
        from oompah.projects import ProjectStore
        store = ProjectStore()
        project = store.get(project_id)
        if project and project.auditor_validation_targets:
            return list(project.auditor_validation_targets)
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


def check_auditor_command(
    command: str,
    project_id: str | None = None,
    *,
    project: Any = None,
) -> str | None:
    """Return a denial for commands outside the read/test allowlist.

    Denials are classified as recoverable (contract mismatch) or fatal (security
    violation). Recoverable denials do not consume the auditor's policy budget.

    Security violations checked first (always fatal):
    - Path escapes (absolute paths, parent traversal, /home, etc.)
    - Credential file access (.env, .git/config, private keys, etc.)
    - State-changing mutations (rm, git commit/push, etc.)
    - File redirection to write/append files (>, >>)
    - Process control (eval, xargs, etc.)

    Contract mismatches checked after security:
    - Unapproved Make targets are fatal authority violations
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

    # Safe-but-unsupported inspection forms are recoverable only after the
    # command-wide path and credential fences have run.  Keeping this after
    # the global checks prevents a permissive subcommand recognizer from
    # downgrading a repository escape or secret read to an informational
    # contract mismatch.
    if _is_read_only_inspection_command(normalized):
        return _recoverable_read_only_denial()

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
    validation_targets = _get_auditor_validation_targets(
        project_id,
        project=project,
    )
    command_regex = _build_auditor_command_regex(validation_targets)

    # Special validation for git rev-list: ensure only safe flags are used.
    # This must happen regardless of contract matching because the contract
    # allows "git rev-list" but only with safe flags and operands.
    # Unsupported but read-only flags (like --graph, --pretty) return recoverable
    # errors since they are still inspection operations. Truly dangerous syntax
    # (compound commands, redirection, command substitution) is caught earlier
    # in the mutation and security checks.
    tokens = _auditor_shell_tokens(normalized)
    if tokens and tokens[0].lower() == "make":
        if (
            tokens[0] != "make"
            or len(tokens) != 2
            or tokens[1] not in validation_targets
        ):
            make_targets_str = ", ".join(f"make {t}" for t in validation_targets)
            return AuditorCommandDenial(
                "Error: auditor capability policy permits only exact configured "
                "Make targets; command denied. "
                f"Allowed validation targets: {make_targets_str}. "
                "The command was not executed. "
                f"[reason={AUDITOR_UNAPPROVED_VALIDATION_TARGET_REASON}]",
                reason=AUDITOR_UNAPPROVED_VALIDATION_TARGET_REASON,
            )
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

            # A Makefile target is executable project code. A target outside
            # the server-issued allowlist is an authority violation, even when
            # its name sounds read-only.
            if first_token == "make" and len(tokens) >= 2:
                make_targets_str = ", ".join(f"make {t}" for t in validation_targets)
                return AuditorCommandDenial(
                    "Error: auditor capability policy permits only exact configured "
                    "Make targets; command denied. "
                    f"Allowed validation targets: {make_targets_str}. "
                    "The command was not executed. "
                    f"[reason={AUDITOR_UNAPPROVED_VALIDATION_TARGET_REASON}]",
                    reason=AUDITOR_UNAPPROVED_VALIDATION_TARGET_REASON,
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


def validate_auditor_target_deadlines(
    validation_targets: list[str],
    target_deadlines: dict[str, int],
    target_expected_seconds: dict[str, int] | None = None,
    global_timeout_seconds: int = 720,
) -> str | None:
    """Compatibility wrapper returning the centralized contract error."""

    project = type(
        "AuditorValidationProject",
        (),
        {
            "id": "(validation)",
            "auditor_validation_targets": validation_targets,
            "auditor_validation_target_deadlines": target_deadlines,
            "auditor_validation_target_expected_seconds": (
                target_expected_seconds or {}
            ),
        },
    )()
    return build_auditor_validation_contract(
        project,
        global_timeout_seconds=global_timeout_seconds,
        raw_environment_expected_seconds="{}",
    ).configuration_error


__all__ = [
    "AUDITOR_ALLOWED_TOOLS",
    "AUDITOR_CAPABILITY_POLICY",
    "AUDITOR_FOCUS_NAME",
    "AUDITOR_MUTATING_TOOLS",
    "AUDITOR_READ_ONLY_SYNTAX_REASON",
    "AUDITOR_VALIDATION_CONFIGURATION_REASON",
    "AUDITOR_VALIDATION_DEADLINE_REASON",
    "AUDITOR_VALIDATION_TARGET_EXPECTED_SECONDS_ENV",
    "AUDITOR_UNAPPROVED_VALIDATION_TARGET_REASON",
    "AUDITOR_RESULT_TOOL_NAME",
    "AUDITOR_RESULT_TOOL_SCHEMA",
    "AuditorCommandDenial",
    "AuditorCapabilityPolicy",
    "AuditorTargetContract",
    "AuditorValidationContract",
    "AuditorValidationTargetBudget",
    "_MAX_RESULT_MESSAGE_LENGTH",
    "_MAX_SAFE_EVIDENCE_ENTRIES",
    "_MAX_SAFE_EVIDENCE_KEY_LENGTH",
    "_MAX_SAFE_EVIDENCE_VALUE_LENGTH",
    "_MAX_RESULT_LIST_ITEMS",
    "_MAX_RESULT_LIST_ITEM_LENGTH",
    "_RESULT_SECRET_RE",
    "_SECRET_KEY_RE",
    "auditor_target_contract",
    "auditor_validation_timeout_message",
    "build_auditor_validation_contract",
    "check_auditor_session_target",
    "check_auditor_command",
    "is_recoverable_auditor_command_denial",
    "pending_auditor_target",
    "parse_auditor_result",
    "submit_auditor_result",
    "resolve_auditor_validation_budget",
    "validate_auditor_target_deadlines",
]
