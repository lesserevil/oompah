"""Typed authority for implementation work blocked by an external prerequisite.

Worker handoff text is only a declaration.  It becomes durable authority after
the authenticated task-handoff boundary binds it to one exact live run,
assignment, workflow generation, task revision, worktree head, and agent-profile
configuration revision.  The record is append-once: replacement belongs to a
later explicit resolution compare-and-swap, never to ordinary worker output.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping

if TYPE_CHECKING:
    from oompah.models import Issue


METADATA_KEY = "oompah.implementation_prerequisite"
RESOLUTION_METADATA_KEY = "oompah.implementation_prerequisite_resolution"
SCHEMA_VERSION = 1
RESOLUTION_SCHEMA_VERSION = 1
_STAGING_SCHEMA_VERSION = 1

_PREREQUISITE_RE = re.compile(
    r"External prerequisite: "
    r"(dependency|hardware|platform|credentials|operator-evidence): "
    r"([a-z0-9][a-z0-9._-]{0,63})"
)
_TASK_TRIGGER_RE = re.compile(
    r"Recovery trigger: task:"
    r"([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})/"
    r"([A-Za-z0-9][A-Za-z0-9_.:#-]{0,127})"
)
_PROFILE_TRIGGER_RE = re.compile(
    r"Recovery trigger: profile-capability:"
    r"([a-z0-9][a-z0-9._-]{0,63})"
)
_OPERATOR_TRIGGER_RE = re.compile(
    r"Recovery trigger: operator:"
    r"([a-z0-9][a-z0-9._-]{0,63})"
)
_HEAD_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_FOCUS_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_IDENTITY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:#/-]{0,255}")
_SECRETISH_SUBJECT_RE = re.compile(
    r"(?:sk-|ghp_|github_pat_|glpat-|xox[baprs]-|akia)", re.IGNORECASE
)
_RESERVED_PREFIXES = ("external prerequisite:", "recovery trigger:")


class PrerequisiteKind(str, Enum):
    """Concrete external resource that prevents useful implementation."""

    DEPENDENCY = "dependency"
    HARDWARE = "hardware"
    PLATFORM = "platform"
    CREDENTIALS = "credentials"
    OPERATOR_EVIDENCE = "operator-evidence"


class RecoveryTriggerKind(str, Enum):
    """Named condition that can re-arm implementation."""

    TASK = "task"
    PROFILE_CAPABILITY = "profile-capability"
    OPERATOR = "operator"


class PrerequisiteAdmissionKind(str, Enum):
    """Non-transient admission result reconstructed from durable authority."""

    CAPABLE_PROFILE = "capable-profile"
    BLOCKED_DEPENDENCY = "blocked-dependency"
    BLOCKED_OPERATOR = "blocked-operator"
    BLOCKED_CAPABILITY = "blocked-capability"
    MALFORMED = "malformed"


_ALLOWED_TRIGGER_KIND = {
    PrerequisiteKind.DEPENDENCY: RecoveryTriggerKind.TASK,
    PrerequisiteKind.HARDWARE: RecoveryTriggerKind.PROFILE_CAPABILITY,
    PrerequisiteKind.PLATFORM: RecoveryTriggerKind.PROFILE_CAPABILITY,
    PrerequisiteKind.CREDENTIALS: RecoveryTriggerKind.OPERATOR,
    PrerequisiteKind.OPERATOR_EVIDENCE: RecoveryTriggerKind.OPERATOR,
}


class PrerequisitePersistenceError(RuntimeError):
    """Base class for fail-closed durable prerequisite write failures."""


class PrerequisiteConflictError(PrerequisitePersistenceError):
    """A different immutable prerequisite record already owns the task."""


class MalformedPrerequisiteRecordError(PrerequisitePersistenceError):
    """Existing metadata cannot safely participate in append-once writes."""


class PrerequisiteReadbackError(PrerequisitePersistenceError):
    """The tracker did not return the exact record that was written."""


class PrerequisiteSourceChangedError(PrerequisitePersistenceError):
    """The exact live source changed before the staged append committed."""


class PrerequisiteResolutionConflictError(PrerequisitePersistenceError):
    """A different resolution already owns the immutable prerequisite."""


class MalformedPrerequisiteResolutionError(PrerequisitePersistenceError):
    """Existing resolution metadata cannot safely participate in a CAS."""


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def normalize_execution_capability(value: object) -> str | None:
    """Return one exact lowercase execution-capability slug, or ``None``."""

    if type(value) is not str:
        return None
    candidate = value.strip()
    if candidate != value or _PROFILE_TRIGGER_RE.fullmatch(
        f"Recovery trigger: profile-capability:{candidate}"
    ) is None:
        return None
    return candidate


def canonical_execution_capabilities(values: Iterable[object]) -> tuple[str, ...]:
    """Freeze valid capability slugs into an immutable canonical tuple."""

    return tuple(
        sorted(
            {
                capability
                for value in tuple(values)
                if (capability := normalize_execution_capability(value)) is not None
            }
        )
    )


@dataclass(frozen=True)
class ExecutionProfileCapability:
    """Immutable profile fields that affect capability applicability."""

    name: str
    execution_capabilities: tuple[str, ...]
    issue_types: tuple[str, ...]
    keywords: tuple[str, ...]
    min_priority: int | None
    max_priority: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "execution_capabilities": list(self.execution_capabilities),
            "issue_types": list(self.issue_types),
            "keywords": list(self.keywords),
            "min_priority": self.min_priority,
            "max_priority": self.max_priority,
        }


@dataclass(frozen=True)
class ExecutionProfileSnapshot:
    """Canonical immutable capability authority for one profile-store cut."""

    profiles: tuple[ExecutionProfileCapability, ...]
    revision: str


def freeze_execution_profile_snapshot(
    profiles: Iterable[object],
) -> ExecutionProfileSnapshot:
    """Copy mutable profile objects into a canonical hashed capability cut."""

    # Configured order is selection authority: _match_agent_profile keeps the
    # first profile on equal scores.  Preserve that order in both evaluation
    # and the revision digest rather than sorting profiles by name.
    frozen = tuple(
        ExecutionProfileCapability(
            name=str(getattr(profile, "name", "") or "").strip(),
            execution_capabilities=canonical_execution_capabilities(
                getattr(profile, "execution_capabilities", ()) or ()
            ),
            issue_types=tuple(
                sorted(
                    {
                        str(value).strip()
                        for value in tuple(getattr(profile, "issue_types", ()) or ())
                        if type(value) is str and value.strip()
                    }
                )
            ),
            keywords=tuple(
                sorted(
                    {
                        str(value).strip().casefold()
                        for value in tuple(getattr(profile, "keywords", ()) or ())
                        if type(value) is str and value.strip()
                    }
                )
            ),
            min_priority=(
                getattr(profile, "min_priority", None)
                if type(getattr(profile, "min_priority", None)) is int
                else None
            ),
            max_priority=(
                getattr(profile, "max_priority", None)
                if type(getattr(profile, "max_priority", None)) is int
                else None
            ),
        )
        for profile in tuple(profiles)
        if type(getattr(profile, "name", None)) is str
        and getattr(profile, "name").strip()
    )
    payload = {
        "schema_version": 1,
        "profiles": [profile.to_dict() for profile in frozen],
    }
    return ExecutionProfileSnapshot(profiles=frozen, revision=_sha256(payload))


def select_execution_profile_name(
    snapshot: ExecutionProfileSnapshot,
    issue: object,
    required_capability: object,
) -> str | None:
    """Select the first best applicable profile with the required capability.

    This is the ordinary ``_match_agent_profile`` scoring contract with one
    additional mandatory capability predicate.  A capable but non-applicable
    profile cannot bypass an external blocker.
    """

    capability = normalize_execution_capability(required_capability)
    if capability is None:
        return None
    return select_profile_name(snapshot, issue, required_capability=capability)


def select_profile_name(
    snapshot: ExecutionProfileSnapshot,
    issue: object,
    *,
    required_capability: str | None = None,
) -> str | None:
    """Apply the ordinary profile matcher to an immutable profile cut."""

    issue_type = str(getattr(issue, "issue_type", "") or "")
    text = (
        f"{str(getattr(issue, 'title', '') or '').casefold()} "
        f"{str(getattr(issue, 'description', '') or '').casefold()}"
    )
    priority = getattr(issue, "priority", None)
    if type(priority) is not int:
        priority = 2
    best_name: str | None = None
    best_score = -1
    for profile in snapshot.profiles:
        if (
            required_capability is not None
            and required_capability not in profile.execution_capabilities
        ):
            continue
        score = 0
        if profile.issue_types:
            if issue_type not in profile.issue_types:
                continue
            score += 10
        if profile.keywords:
            matched = sum(1 for keyword in profile.keywords if keyword in text)
            if matched:
                score += matched * 5
            elif not profile.issue_types:
                continue
        if profile.min_priority is not None or profile.max_priority is not None:
            if profile.min_priority is not None and priority < profile.min_priority:
                continue
            if profile.max_priority is not None and priority > profile.max_priority:
                continue
            score += 3
        if score > best_score:
            best_score = score
            best_name = profile.name
    return best_name


@dataclass(frozen=True)
class RecoveryTrigger:
    """Typed recovery condition from a trusted handoff declaration."""

    kind: RecoveryTriggerKind
    value: str
    project_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RecoveryTriggerKind) or type(self.value) is not str:
            raise TypeError("recovery trigger kind and value must be typed strings")
        if self.kind is RecoveryTriggerKind.TASK:
            if type(self.project_id) is not str or _TASK_TRIGGER_RE.fullmatch(
                f"Recovery trigger: task:{self.project_id}/{self.value}"
            ) is None:
                raise ValueError("task recovery trigger must be project-qualified")
        elif self.kind is RecoveryTriggerKind.PROFILE_CAPABILITY:
            if self.project_id is not None or normalize_execution_capability(
                self.value
            ) is None:
                raise ValueError("profile recovery trigger must name one lowercase slug")
        elif (
            self.project_id is not None
            or _OPERATOR_TRIGGER_RE.fullmatch(
                f"Recovery trigger: operator:{self.value}"
            )
            is None
        ):
            raise ValueError("operator recovery trigger must name one lowercase slug")

    def to_dict(self) -> dict[str, str]:
        payload = {"kind": self.kind.value, "value": self.value}
        if self.project_id is not None:
            payload["project_id"] = self.project_id
        return payload

    @classmethod
    def from_raw(cls, raw: object) -> RecoveryTrigger | None:
        if not isinstance(raw, Mapping):
            return None
        kind_raw = raw.get("kind")
        value = raw.get("value")
        project_id = raw.get("project_id")
        if type(kind_raw) is not str or type(value) is not str:
            return None
        try:
            kind = RecoveryTriggerKind(kind_raw)
        except ValueError:
            return None
        expected_keys = {"kind", "value"}
        if kind is RecoveryTriggerKind.TASK:
            expected_keys.add("project_id")
            if type(project_id) is not str:
                return None
        elif project_id is not None or "project_id" in raw:
            return None
        if set(raw) != expected_keys:
            return None
        try:
            return cls(kind=kind, value=value, project_id=project_id)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class ImplementationPrerequisiteDeclaration:
    """Strict structured declaration parsed from trusted handoff text."""

    kind: PrerequisiteKind
    subject: str
    recovery_trigger: RecoveryTrigger

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PrerequisiteKind):
            raise TypeError("prerequisite kind must be typed")
        if (
            type(self.subject) is not str
            or _PROFILE_TRIGGER_RE.fullmatch(
                f"Recovery trigger: profile-capability:{self.subject}"
            )
            is None
            or _SECRETISH_SUBJECT_RE.match(self.subject) is not None
        ):
            raise ValueError("prerequisite subject must be one lowercase safe slug")
        expected = _ALLOWED_TRIGGER_KIND[self.kind]
        if self.recovery_trigger.kind is not expected:
            raise ValueError(
                f"{self.kind.value} prerequisite requires {expected.value} recovery"
            )


def parse_prerequisite_declaration(
    text: object,
) -> ImplementationPrerequisiteDeclaration | None:
    """Parse one exact prerequisite marker pair from trusted handoff text.

    The caller authenticates the comment author and validates the focus header.
    Extra narrative is allowed.  Any malformed, repeated, indented, or
    case-variant reserved-looking line rejects the whole declaration, so prose
    and aliases never become scheduling authority.
    """

    if type(text) is not str:
        return None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    prerequisite_matches: list[re.Match[str]] = []
    trigger_matches: list[RecoveryTrigger] = []
    malformed = False
    for line in lines[1:]:
        # Markdown/indentation cannot hide a second authority marker inside
        # otherwise valid text. Only the raw, column-zero canonical spelling
        # may be accepted.
        folded = line.lstrip(" \t>*-_`#").casefold()
        reserved = next(
            (prefix for prefix in _RESERVED_PREFIXES if folded.startswith(prefix)),
            None,
        )
        if reserved == "external prerequisite:":
            match = _PREREQUISITE_RE.fullmatch(line)
            if match is None:
                malformed = True
            else:
                prerequisite_matches.append(match)
        elif reserved == "recovery trigger:":
            task_match = _TASK_TRIGGER_RE.fullmatch(line)
            profile_match = _PROFILE_TRIGGER_RE.fullmatch(line)
            operator_match = _OPERATOR_TRIGGER_RE.fullmatch(line)
            try:
                if task_match is not None:
                    trigger_matches.append(
                        RecoveryTrigger(
                            RecoveryTriggerKind.TASK,
                            task_match.group(2),
                            project_id=task_match.group(1),
                        )
                    )
                elif profile_match is not None:
                    trigger_matches.append(
                        RecoveryTrigger(
                            RecoveryTriggerKind.PROFILE_CAPABILITY,
                            profile_match.group(1),
                        )
                    )
                elif operator_match is not None:
                    trigger_matches.append(
                        RecoveryTrigger(
                            RecoveryTriggerKind.OPERATOR,
                            operator_match.group(1),
                        )
                    )
                else:
                    malformed = True
            except (TypeError, ValueError):
                malformed = True
    if malformed or len(prerequisite_matches) != 1 or len(trigger_matches) != 1:
        return None
    match = prerequisite_matches[0]
    try:
        return ImplementationPrerequisiteDeclaration(
            kind=PrerequisiteKind(match.group(1)),
            subject=match.group(2),
            recovery_trigger=trigger_matches[0],
        )
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ImplementationPrerequisiteRecord:
    """Immutable durable authority attributed to one exact worker run."""

    record_id: str
    prerequisite_kind: PrerequisiteKind
    subject: str
    recovery_trigger: RecoveryTrigger
    project_id: str
    task_id: str
    task_identifier: str
    source_run_id: str
    source_assignment_id: str
    source_generation: str
    source_focus: str
    source_task_authority: str
    source_head_sha: str
    source_profile_revision: str
    created_at: datetime
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported prerequisite record schema")
        if not isinstance(self.prerequisite_kind, PrerequisiteKind):
            raise TypeError("prerequisite record kind must be typed")
        ImplementationPrerequisiteDeclaration(
            self.prerequisite_kind,
            self.subject,
            self.recovery_trigger,
        )
        string_fields = (
            self.record_id,
            self.project_id,
            self.task_id,
            self.task_identifier,
            self.source_run_id,
            self.source_assignment_id,
            self.source_generation,
            self.source_focus,
            self.source_task_authority,
            self.source_head_sha,
            self.source_profile_revision,
        )
        if any(type(value) is not str or not value or value != value.strip() for value in string_fields):
            raise ValueError("prerequisite authority strings must be non-empty canonical text")
        if _DIGEST_RE.fullmatch(self.record_id) is None:
            raise ValueError("record_id must be a SHA-256 digest")
        if _HEAD_RE.fullmatch(self.source_head_sha) is None:
            raise ValueError("source_head_sha must be an exact lowercase git object id")
        if _DIGEST_RE.fullmatch(self.source_task_authority) is None:
            raise ValueError("source_task_authority must be an exact revision digest")
        if _DIGEST_RE.fullmatch(self.source_profile_revision) is None:
            raise ValueError("source_profile_revision must be an exact revision digest")
        if _FOCUS_RE.fullmatch(self.source_focus) is None:
            raise ValueError("source_focus must be a canonical lowercase slug")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware")
        if self.record_id != _sha256(self.identity_payload()):
            raise ValueError("record_id does not match the immutable payload")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prerequisite_kind": self.prerequisite_kind.value,
            "subject": self.subject,
            "recovery_trigger": self.recovery_trigger.to_dict(),
            "project_id": self.project_id,
            "task_id": self.task_id,
            "task_identifier": self.task_identifier,
            "source_run_id": self.source_run_id,
            "source_assignment_id": self.source_assignment_id,
            "source_generation": self.source_generation,
            "source_focus": self.source_focus,
            "source_task_authority": self.source_task_authority,
            "source_head_sha": self.source_head_sha,
            "source_profile_revision": self.source_profile_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "record_id": self.record_id,
            "created_at": _iso(self.created_at),
        }

    @classmethod
    def from_raw(cls, raw: object) -> ImplementationPrerequisiteRecord | None:
        if not isinstance(raw, Mapping):
            return None
        expected_keys = {
            "schema_version",
            "record_id",
            "prerequisite_kind",
            "subject",
            "recovery_trigger",
            "project_id",
            "task_id",
            "task_identifier",
            "source_run_id",
            "source_assignment_id",
            "source_generation",
            "source_focus",
            "source_task_authority",
            "source_head_sha",
            "source_profile_revision",
            "created_at",
        }
        if set(raw) != expected_keys or type(raw.get("schema_version")) is not int:
            return None
        if raw.get("schema_version") != SCHEMA_VERSION:
            return None
        kind_raw = raw.get("prerequisite_kind")
        subject = raw.get("subject")
        created_raw = raw.get("created_at")
        if type(kind_raw) is not str or type(subject) is not str or type(created_raw) is not str:
            return None
        string_names = expected_keys - {
            "schema_version",
            "prerequisite_kind",
            "recovery_trigger",
            "created_at",
        }
        if any(type(raw.get(name)) is not str for name in string_names):
            return None
        try:
            created_at = datetime.fromisoformat(created_raw)
        except ValueError:
            return None
        if created_at.tzinfo is None or _iso(created_at) != created_raw:
            return None
        trigger = RecoveryTrigger.from_raw(raw.get("recovery_trigger"))
        if trigger is None:
            return None
        try:
            return cls(
                schema_version=SCHEMA_VERSION,
                record_id=raw["record_id"],
                prerequisite_kind=PrerequisiteKind(kind_raw),
                subject=subject,
                recovery_trigger=trigger,
                project_id=raw["project_id"],
                task_id=raw["task_id"],
                task_identifier=raw["task_identifier"],
                source_run_id=raw["source_run_id"],
                source_assignment_id=raw["source_assignment_id"],
                source_generation=raw["source_generation"],
                source_focus=raw["source_focus"],
                source_task_authority=raw["source_task_authority"],
                source_head_sha=raw["source_head_sha"],
                source_profile_revision=raw["source_profile_revision"],
                created_at=created_at,
            )
        except (TypeError, ValueError):
            return None


_CONTINUATION_STATUSES = frozenset(
    {"Open", "In Progress", "In Review", "Ready to Integrate"}
)
_SATISFIED_TRIGGER_TASK_STATUSES = frozenset({"Done", "Merged", "Archived"})


def canonical_resolution_trigger_evidence(
    trigger: RecoveryTrigger,
    raw: object,
) -> dict[str, Any]:
    """Validate evidence proving the record's one named recovery trigger."""

    if not isinstance(trigger, RecoveryTrigger) or not isinstance(raw, Mapping):
        raise TypeError("resolution trigger evidence must be a typed object")
    evidence = dict(raw)
    if trigger.kind is RecoveryTriggerKind.TASK:
        expected_keys = {
            "kind",
            "project_id",
            "task_identifier",
            "status",
            "task_authority",
        }
        if set(evidence) != expected_keys or evidence.get("kind") != "task":
            raise ValueError("task trigger evidence has an invalid shape")
        if (
            evidence.get("project_id") != trigger.project_id
            or evidence.get("task_identifier") != trigger.value
            or evidence.get("status") not in _SATISFIED_TRIGGER_TASK_STATUSES
            or type(evidence.get("task_authority")) is not str
            or _DIGEST_RE.fullmatch(evidence["task_authority"]) is None
        ):
            raise ValueError("task trigger evidence does not prove the named task")
    elif trigger.kind is RecoveryTriggerKind.PROFILE_CAPABILITY:
        expected_keys = {
            "kind",
            "capability",
            "profile_name",
            "profile_revision",
        }
        if (
            set(evidence) != expected_keys
            or evidence.get("kind") != "profile-capability"
            or evidence.get("capability") != trigger.value
            or type(evidence.get("profile_name")) is not str
            or _IDENTITY_RE.fullmatch(evidence["profile_name"]) is None
            or type(evidence.get("profile_revision")) is not str
            or _DIGEST_RE.fullmatch(evidence["profile_revision"]) is None
        ):
            raise ValueError(
                "profile trigger evidence does not prove the named capability"
            )
    else:
        if set(evidence) != {"kind", "action"} or (
            evidence.get("kind") != "operator"
            or evidence.get("action") != trigger.value
        ):
            raise ValueError(
                "operator trigger evidence does not prove the named action"
            )
    try:
        encoded = json.dumps(
            evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        canonical = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("trigger_evidence must be canonical JSON") from exc
    if not isinstance(canonical, dict):  # pragma: no cover - shape proved above
        raise ValueError("trigger_evidence must be an object")
    return canonical


@dataclass(frozen=True)
class PrerequisiteContinuation:
    """Exact phase and repository evidence preserved across a parked wait."""

    resume_status: str
    work_branch: str | None = None
    head_sha: str | None = None
    review_id: str | None = None
    review_head_sha: str | None = None
    pipeline_id: str | None = None
    pipeline_head_sha: str | None = None

    def __post_init__(self) -> None:
        if self.resume_status not in _CONTINUATION_STATUSES:
            raise ValueError("resume_status is not a supported continuation phase")
        for name in ("work_branch", "review_id", "pipeline_id"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not str
                or value != value.strip()
                or _IDENTITY_RE.fullmatch(value) is None
            ):
                raise ValueError(f"{name} must be canonical identity text")
        for name in ("head_sha", "review_head_sha", "pipeline_head_sha"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not str or _HEAD_RE.fullmatch(value) is None
            ):
                raise ValueError(f"{name} must be an exact lowercase git object id")
        if self.review_id is None and self.review_head_sha is not None:
            raise ValueError("review_head_sha requires review_id")
        if self.pipeline_id is None and self.pipeline_head_sha is not None:
            raise ValueError("pipeline_head_sha requires pipeline_id")
        if self.review_id is not None and self.review_head_sha is None:
            raise ValueError("review_id requires review_head_sha")
        if self.pipeline_id is not None and self.pipeline_head_sha is None:
            raise ValueError("pipeline_id requires pipeline_head_sha")
        if self.pipeline_id is not None and self.review_id is None:
            raise ValueError("pipeline identity requires exact review identity")
        exact_heads = {
            value
            for value in (
                self.head_sha,
                self.review_head_sha,
                self.pipeline_head_sha,
            )
            if value is not None
        }
        if len(exact_heads) > 1:
            raise ValueError("continuation evidence must identify one exact head")
        if self.resume_status == "In Review" and self.review_id is None:
            raise ValueError("In Review continuation requires exact review identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "resume_status": self.resume_status,
            "work_branch": self.work_branch,
            "head_sha": self.head_sha,
            "review_id": self.review_id,
            "review_head_sha": self.review_head_sha,
            "pipeline_id": self.pipeline_id,
            "pipeline_head_sha": self.pipeline_head_sha,
        }

    @classmethod
    def from_raw(cls, raw: object) -> PrerequisiteContinuation | None:
        if not isinstance(raw, Mapping) or set(raw) != {
            "resume_status",
            "work_branch",
            "head_sha",
            "review_id",
            "review_head_sha",
            "pipeline_id",
            "pipeline_head_sha",
        }:
            return None
        if type(raw.get("resume_status")) is not str:
            return None
        optional_names = set(raw) - {"resume_status"}
        if any(
            raw.get(name) is not None and type(raw.get(name)) is not str
            for name in optional_names
        ):
            return None
        try:
            return cls(**dict(raw))
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class ImplementationPrerequisiteResolution:
    """Committed owner authority resolving one exact prerequisite record.

    The workflow generation is part of the immutable identity.  A retry may
    replay this receipt, but a replacement job cannot appropriate it and an
    exhausted historical row is never re-armed as new authority.
    """

    resolution_id: str
    record_id: str
    project_id: str
    task_id: str
    task_identifier: str
    source_run_id: str
    source_assignment_id: str
    source_generation: str
    expected_task_authority: str
    workflow_generation: str
    actor: str
    reason: str
    recovery_trigger: RecoveryTrigger
    trigger_evidence: Mapping[str, Any]
    continuation: PrerequisiteContinuation
    resolved_at: datetime
    schema_version: int = RESOLUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESOLUTION_SCHEMA_VERSION:
            raise ValueError("unsupported prerequisite resolution schema")
        string_fields = (
            self.resolution_id,
            self.record_id,
            self.project_id,
            self.task_id,
            self.task_identifier,
            self.source_run_id,
            self.source_assignment_id,
            self.source_generation,
            self.expected_task_authority,
            self.workflow_generation,
            self.actor,
            self.reason,
        )
        if any(
            type(value) is not str or not value or value != value.strip()
            for value in string_fields
        ):
            raise ValueError("resolution authority strings must be canonical text")
        if _DIGEST_RE.fullmatch(self.resolution_id) is None:
            raise ValueError("resolution_id must be a SHA-256 digest")
        if _DIGEST_RE.fullmatch(self.record_id) is None:
            raise ValueError("record_id must be a SHA-256 digest")
        if _DIGEST_RE.fullmatch(self.expected_task_authority) is None:
            raise ValueError("expected_task_authority must be an exact revision digest")
        if not isinstance(self.recovery_trigger, RecoveryTrigger):
            raise TypeError("recovery_trigger must be typed")
        if not isinstance(self.continuation, PrerequisiteContinuation):
            raise TypeError("continuation must be typed")
        canonical_evidence = canonical_resolution_trigger_evidence(
            self.recovery_trigger,
            self.trigger_evidence,
        )
        object.__setattr__(self, "trigger_evidence", canonical_evidence)
        if (
            not isinstance(self.resolved_at, datetime)
            or self.resolved_at.tzinfo is None
            or self.resolved_at.utcoffset() is None
        ):
            raise ValueError("resolved_at must be timezone-aware")
        if self.resolution_id != _sha256(self.identity_payload()):
            raise ValueError("resolution_id does not match the immutable payload")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "task_identifier": self.task_identifier,
            "source_run_id": self.source_run_id,
            "source_assignment_id": self.source_assignment_id,
            "source_generation": self.source_generation,
            "expected_task_authority": self.expected_task_authority,
            "workflow_generation": self.workflow_generation,
            "actor": self.actor,
            "reason": self.reason,
            "recovery_trigger": self.recovery_trigger.to_dict(),
            "trigger_evidence": dict(self.trigger_evidence),
            "continuation": self.continuation.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "resolution_id": self.resolution_id,
            "resolved_at": _iso(self.resolved_at),
        }

    @classmethod
    def from_raw(cls, raw: object) -> ImplementationPrerequisiteResolution | None:
        if not isinstance(raw, Mapping):
            return None
        expected = {
            "schema_version",
            "resolution_id",
            "record_id",
            "project_id",
            "task_id",
            "task_identifier",
            "source_run_id",
            "source_assignment_id",
            "source_generation",
            "expected_task_authority",
            "workflow_generation",
            "actor",
            "reason",
            "recovery_trigger",
            "trigger_evidence",
            "continuation",
            "resolved_at",
        }
        if set(raw) != expected or raw.get("schema_version") != RESOLUTION_SCHEMA_VERSION:
            return None
        string_names = expected - {
            "schema_version",
            "recovery_trigger",
            "trigger_evidence",
            "continuation",
        }
        if any(type(raw.get(name)) is not str for name in string_names):
            return None
        trigger = RecoveryTrigger.from_raw(raw.get("recovery_trigger"))
        continuation = PrerequisiteContinuation.from_raw(raw.get("continuation"))
        if trigger is None or continuation is None:
            return None
        try:
            resolved_at = datetime.fromisoformat(raw["resolved_at"])
        except ValueError:
            return None
        if resolved_at.tzinfo is None or _iso(resolved_at) != raw["resolved_at"]:
            return None
        try:
            return cls(
                **{
                    key: raw[key]
                    for key in expected
                    if key
                    not in {
                        "recovery_trigger",
                        "continuation",
                        "resolved_at",
                    }
                },
                recovery_trigger=trigger,
                continuation=continuation,
                resolved_at=resolved_at,
            )
        except (TypeError, ValueError):
            return None


def new_resolution(
    record: ImplementationPrerequisiteRecord,
    *,
    expected_task_authority: str,
    workflow_generation: str,
    actor: str,
    reason: str,
    trigger_evidence: Mapping[str, Any],
    continuation: PrerequisiteContinuation,
    now: datetime,
) -> ImplementationPrerequisiteResolution:
    """Create a job-bound resolution after its trigger and CAS are fenced."""

    if not isinstance(record, ImplementationPrerequisiteRecord):
        raise TypeError("record must be typed")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    payload = {
        "schema_version": RESOLUTION_SCHEMA_VERSION,
        "record_id": record.record_id,
        "project_id": record.project_id,
        "task_id": record.task_id,
        "task_identifier": record.task_identifier,
        "source_run_id": record.source_run_id,
        "source_assignment_id": record.source_assignment_id,
        "source_generation": record.source_generation,
        "expected_task_authority": expected_task_authority,
        "workflow_generation": workflow_generation,
        "actor": actor,
        "reason": reason,
        "recovery_trigger": record.recovery_trigger.to_dict(),
        "trigger_evidence": dict(trigger_evidence),
        "continuation": continuation.to_dict(),
    }
    return ImplementationPrerequisiteResolution(
        resolution_id=_sha256(payload),
        record_id=record.record_id,
        project_id=record.project_id,
        task_id=record.task_id,
        task_identifier=record.task_identifier,
        source_run_id=record.source_run_id,
        source_assignment_id=record.source_assignment_id,
        source_generation=record.source_generation,
        expected_task_authority=expected_task_authority,
        workflow_generation=workflow_generation,
        actor=actor,
        reason=reason,
        recovery_trigger=record.recovery_trigger,
        trigger_evidence=trigger_evidence,
        continuation=continuation,
        resolved_at=now.astimezone(timezone.utc),
    )


@dataclass(frozen=True)
class PrerequisiteAdmissionDisposition:
    """Typed, jobless-or-capable projection consumed by workflow policy.

    OOMPAH-1262 defines the immutable admission fact.  Later lifecycle work
    may turn blocked dispositions into stable parked ownership, but no blocked
    disposition is a transient retry request.
    """

    kind: PrerequisiteAdmissionKind
    record_id: str | None
    subject: str
    recovery_trigger: RecoveryTrigger | None
    profile_name: str | None = None
    profile_revision: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PrerequisiteAdmissionKind):
            raise TypeError("prerequisite admission kind must be typed")
        if type(self.subject) is not str or not self.subject:
            raise ValueError("prerequisite admission subject is required")
        if self.kind is PrerequisiteAdmissionKind.MALFORMED:
            if any(
                value is not None
                for value in (
                    self.record_id,
                    self.recovery_trigger,
                    self.profile_name,
                    self.profile_revision,
                )
            ):
                raise ValueError("malformed admission cannot grant authority")
            return
        if (
            type(self.record_id) is not str
            or _DIGEST_RE.fullmatch(self.record_id) is None
            or not isinstance(self.recovery_trigger, RecoveryTrigger)
        ):
            raise ValueError("admission must identify one typed durable record")
        capable = self.kind is PrerequisiteAdmissionKind.CAPABLE_PROFILE
        if capable:
            if (
                type(self.profile_name) is not str
                or not self.profile_name.strip()
                or type(self.profile_revision) is not str
                or _DIGEST_RE.fullmatch(self.profile_revision) is None
            ):
                raise ValueError("capable admission requires an exact profile cut")
        elif self.profile_name is not None or self.profile_revision is not None:
            raise ValueError("blocked admission cannot name dispatch authority")

    @property
    def dispatchable(self) -> bool:
        return self.kind is PrerequisiteAdmissionKind.CAPABLE_PROFILE

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "record_id": self.record_id,
            "subject": self.subject,
            "recovery_trigger": (
                self.recovery_trigger.to_dict()
                if self.recovery_trigger is not None
                else None
            ),
            "profile_name": self.profile_name,
            "profile_revision": self.profile_revision,
            "dispatchable": self.dispatchable,
        }


def project_prerequisite_admission(
    issue: object,
    snapshot: ExecutionProfileSnapshot,
) -> PrerequisiteAdmissionDisposition | None:
    """Reconstruct one strict durable prerequisite into admission policy."""

    raw = getattr(issue, "implementation_prerequisite", None)
    if raw is None:
        return None
    record = ImplementationPrerequisiteRecord.from_raw(raw)
    if record is None or (
        record.project_id != str(getattr(issue, "project_id", "") or "")
        or record.task_id != str(getattr(issue, "id", "") or "")
        or record.task_identifier
        != str(getattr(issue, "identifier", "") or "")
    ):
        return PrerequisiteAdmissionDisposition(
            PrerequisiteAdmissionKind.MALFORMED,
            None,
            "invalid-durable-record",
            None,
        )
    resolution_raw = getattr(
        issue, "implementation_prerequisite_resolution", None
    )
    if resolution_raw is not None:
        resolution = ImplementationPrerequisiteResolution.from_raw(resolution_raw)
        if resolution_is_current(record, resolution):
            return None
    trigger = record.recovery_trigger
    if trigger.kind is RecoveryTriggerKind.TASK:
        kind = PrerequisiteAdmissionKind.BLOCKED_DEPENDENCY
    elif trigger.kind is RecoveryTriggerKind.OPERATOR:
        kind = PrerequisiteAdmissionKind.BLOCKED_OPERATOR
    else:
        selected = select_execution_profile_name(snapshot, issue, trigger.value)
        if selected is not None:
            return PrerequisiteAdmissionDisposition(
                PrerequisiteAdmissionKind.CAPABLE_PROFILE,
                record.record_id,
                record.subject,
                trigger,
                profile_name=selected,
                profile_revision=snapshot.revision,
            )
        kind = PrerequisiteAdmissionKind.BLOCKED_CAPABILITY
    return PrerequisiteAdmissionDisposition(
        kind,
        record.record_id,
        record.subject,
        trigger,
    )


def resolution_is_current(
    record: ImplementationPrerequisiteRecord,
    resolution: ImplementationPrerequisiteResolution | None,
) -> bool:
    """Return whether one committed receipt resolves this exact record.

    Staging wrappers, malformed values, and receipts for an older record are
    deliberately false.  This is the shared OOMPAH-1263 parking contract.
    """

    return bool(
        isinstance(record, ImplementationPrerequisiteRecord)
        and isinstance(resolution, ImplementationPrerequisiteResolution)
        and resolution.record_id == record.record_id
        and resolution.project_id == record.project_id
        and resolution.task_id == record.task_id
        and resolution.task_identifier == record.task_identifier
        and resolution.source_run_id == record.source_run_id
        and resolution.source_assignment_id == record.source_assignment_id
        and resolution.source_generation == record.source_generation
        and resolution.recovery_trigger == record.recovery_trigger
    )


def new_record(
    declaration: ImplementationPrerequisiteDeclaration,
    *,
    project_id: str,
    task_id: str,
    task_identifier: str,
    source_run_id: str,
    source_assignment_id: str,
    source_generation: str,
    source_focus: str,
    source_task_authority: str,
    source_head_sha: str,
    source_profile_revision: str,
    now: datetime,
) -> ImplementationPrerequisiteRecord:
    """Create one immutable record after the caller fences source authority."""

    if not isinstance(declaration, ImplementationPrerequisiteDeclaration):
        raise TypeError("declaration must be typed")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "prerequisite_kind": declaration.kind.value,
        "subject": declaration.subject,
        "recovery_trigger": declaration.recovery_trigger.to_dict(),
        "project_id": project_id,
        "task_id": task_id,
        "task_identifier": task_identifier,
        "source_run_id": source_run_id,
        "source_assignment_id": source_assignment_id,
        "source_generation": source_generation,
        "source_focus": source_focus,
        "source_task_authority": source_task_authority,
        "source_head_sha": source_head_sha,
        "source_profile_revision": source_profile_revision,
    }
    return ImplementationPrerequisiteRecord(
        record_id=_sha256(payload),
        prerequisite_kind=declaration.kind,
        subject=declaration.subject,
        recovery_trigger=declaration.recovery_trigger,
        project_id=project_id,
        task_id=task_id,
        task_identifier=task_identifier,
        source_run_id=source_run_id,
        source_assignment_id=source_assignment_id,
        source_generation=source_generation,
        source_focus=source_focus,
        source_task_authority=source_task_authority,
        source_head_sha=source_head_sha,
        source_profile_revision=source_profile_revision,
        created_at=now.astimezone(timezone.utc),
    )


def raw_record_for_issue(issue: Issue) -> object:
    return getattr(issue, "implementation_prerequisite", None)


def raw_resolution_for_issue(issue: Issue) -> object:
    return getattr(issue, "implementation_prerequisite_resolution", None)


def set_issue_record(
    issue: Issue,
    record: object,
) -> None:
    if isinstance(record, ImplementationPrerequisiteRecord):
        issue.implementation_prerequisite = record.to_dict()
    elif isinstance(record, Mapping):
        issue.implementation_prerequisite = dict(record)
    else:
        # Preserve malformed scalar/list values so restart projection can
        # distinguish corruption from true absence and remain fail closed.
        issue.implementation_prerequisite = record


def set_issue_resolution(issue: Issue, resolution: object) -> None:
    if isinstance(resolution, ImplementationPrerequisiteResolution):
        issue.implementation_prerequisite_resolution = resolution.to_dict()
    elif isinstance(resolution, Mapping):
        issue.implementation_prerequisite_resolution = dict(resolution)
    else:
        issue.implementation_prerequisite_resolution = resolution


def load_record(tracker: Any, issue: Issue) -> ImplementationPrerequisiteRecord | None:
    """Load and project a record through the generic tracker metadata API."""

    metadata = tracker.get_metadata(issue.identifier) or {}
    raw = metadata.get(METADATA_KEY)
    set_issue_record(issue, raw)
    return ImplementationPrerequisiteRecord.from_raw(raw)


def load_resolution(
    tracker: Any, issue: Issue
) -> ImplementationPrerequisiteResolution | None:
    """Load a committed resolution through the generic metadata API."""

    metadata = tracker.get_metadata(issue.identifier) or {}
    raw = metadata.get(RESOLUTION_METADATA_KEY)
    set_issue_resolution(issue, raw)
    return ImplementationPrerequisiteResolution.from_raw(raw)


def _read_exact_record(tracker: Any, identifier: str) -> tuple[object, ImplementationPrerequisiteRecord | None]:
    metadata = tracker.get_metadata(identifier) or {}
    raw = metadata.get(METADATA_KEY)
    return raw, ImplementationPrerequisiteRecord.from_raw(raw)


def _read_exact_resolution(
    tracker: Any, identifier: str
) -> tuple[object, ImplementationPrerequisiteResolution | None]:
    metadata = tracker.get_metadata(identifier) or {}
    raw = metadata.get(RESOLUTION_METADATA_KEY)
    return raw, ImplementationPrerequisiteResolution.from_raw(raw)


def save_record(
    tracker: Any,
    issue: Issue,
    record: ImplementationPrerequisiteRecord,
    *,
    lock: AbstractContextManager[Any],
    accept_staged: Callable[[], bool] | None = None,
    finalize_fence: AbstractContextManager[Any] | None = None,
) -> ImplementationPrerequisiteRecord:
    """Append one record and verify exact readback under a caller-owned lock.

    Missing metadata may be created.  An identical record is idempotent.  A
    different or malformed existing value is never overwritten; later owner
    resolution must replace it through its own exact compare-and-swap.
    """

    if not isinstance(record, ImplementationPrerequisiteRecord):
        raise TypeError("record must be typed")
    with lock:
        raw, existing = _read_exact_record(tracker, issue.identifier)
        if raw is not None:
            if existing is None:
                raise MalformedPrerequisiteRecordError(
                    "existing implementation prerequisite metadata is malformed"
                )
            if existing.record_id != record.record_id:
                raise PrerequisiteConflictError(
                    "a different implementation prerequisite already owns the task"
                )
            set_issue_record(issue, existing)
            return existing

        staged = {
            "staging_schema_version": _STAGING_SCHEMA_VERSION,
            "state": "staged",
            "record": record.to_dict(),
        }
        write_error: Exception | None = None
        try:
            tracker.set_metadata_field(issue.identifier, METADATA_KEY, staged)
        except Exception as exc:  # lost responses are verified below
            write_error = exc
        staged_raw, staged_record = _read_exact_record(tracker, issue.identifier)
        if staged_raw != staged or staged_record is not None:
            detail = f" ({type(write_error).__name__})" if write_error else ""
            raise PrerequisiteReadbackError(
                "implementation prerequisite staging readback failed" + detail
            ) from write_error
        # A staged wrapper is deliberately not a valid durable record. Facts
        # and restart recovery reject it, so a crash before the authority
        # fence can only leave fail-closed quarantine, never stale authority.
        fence = finalize_fence or _NullContext()
        with fence:
            if accept_staged is not None and not accept_staged():
                tracker.set_metadata_field(issue.identifier, METADATA_KEY, None)
                cleared_raw, _cleared = _read_exact_record(
                    tracker, issue.identifier
                )
                if cleared_raw is not None:
                    raise PrerequisiteReadbackError(
                        "stale prerequisite staging could not be rolled back"
                    )
                set_issue_record(issue, None)
                raise PrerequisiteSourceChangedError(
                    "implementation prerequisite source changed during staging"
                )
            final_error: Exception | None = None
            try:
                tracker.set_metadata_field(
                    issue.identifier, METADATA_KEY, record.to_dict()
                )
            except Exception as exc:  # exact readback resolves lost responses
                final_error = exc
            readback_raw, readback = _read_exact_record(
                tracker, issue.identifier
            )
            if (
                readback is None
                or readback.record_id != record.record_id
                or readback.to_dict() != record.to_dict()
                or readback_raw != record.to_dict()
            ):
                raise PrerequisiteReadbackError(
                    "implementation prerequisite final readback failed"
                ) from final_error
        set_issue_record(issue, readback)
        return readback


def save_resolution(
    tracker: Any,
    issue: Issue,
    record: ImplementationPrerequisiteRecord,
    resolution: ImplementationPrerequisiteResolution,
    *,
    lock: AbstractContextManager[Any],
    accept_current: Callable[[], bool],
) -> ImplementationPrerequisiteResolution:
    """Commit one exact resolution under record and task-authority CAS.

    ``accept_current`` is evaluated while the caller's bounded owner-control
    lock is held and must compare the freshly projected task authority with
    ``resolution.expected_task_authority``.  The metadata write itself is
    append-once: an identical lost-response retry succeeds, while concurrent
    replacement and malformed history fail closed.
    """

    if not isinstance(record, ImplementationPrerequisiteRecord):
        raise TypeError("record must be typed")
    if not isinstance(resolution, ImplementationPrerequisiteResolution):
        raise TypeError("resolution must be typed")
    if not resolution_is_current(record, resolution):
        raise PrerequisiteSourceChangedError(
            "resolution does not identify the exact prerequisite source"
        )
    if not callable(accept_current):
        raise TypeError("accept_current must be callable")
    with lock:
        raw_record, current_record = _read_exact_record(
            tracker, issue.identifier
        )
        if raw_record is None or current_record is None:
            raise MalformedPrerequisiteRecordError(
                "current implementation prerequisite is absent or malformed"
            )
        if current_record.record_id != record.record_id:
            raise PrerequisiteSourceChangedError(
                "implementation prerequisite changed before resolution"
            )
        raw, existing = _read_exact_resolution(tracker, issue.identifier)
        if raw is not None:
            if existing is None:
                raise MalformedPrerequisiteResolutionError(
                    "existing prerequisite resolution metadata is malformed"
                )
            if existing.resolution_id != resolution.resolution_id:
                raise PrerequisiteResolutionConflictError(
                    "a different prerequisite resolution already owns the task"
                )
            set_issue_resolution(issue, existing)
            return existing
        if not accept_current():
            raise PrerequisiteSourceChangedError(
                "task authority changed before prerequisite resolution"
            )
        write_error: Exception | None = None
        try:
            tracker.set_metadata_field(
                issue.identifier,
                RESOLUTION_METADATA_KEY,
                resolution.to_dict(),
            )
        except Exception as exc:  # exact readback resolves lost responses
            write_error = exc
        readback_raw, readback = _read_exact_resolution(
            tracker, issue.identifier
        )
        if (
            readback is None
            or readback.resolution_id != resolution.resolution_id
            or readback.to_dict() != resolution.to_dict()
            or readback_raw != resolution.to_dict()
        ):
            raise PrerequisiteReadbackError(
                "implementation prerequisite resolution readback failed"
            ) from write_error
        set_issue_resolution(issue, readback)
        return readback


class _NullContext(AbstractContextManager[None]):
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc_info: object) -> None:
        return None
