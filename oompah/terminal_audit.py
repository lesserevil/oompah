"""Tracker-neutral records for auditing terminal task transitions.

The terminal-audit coordinator stores these records in tracker metadata, but
the records deliberately know nothing about a tracker.  The only evidence
that participates in an :class:`EvidenceFingerprint` is the explicit,
machine-readable evidence accepted by :meth:`EvidenceFingerprint.from_evidence`.
In particular, credentials, diffs, and auditor/model prose are not fields in
the fingerprint payload.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar


CURRENT_VERSION = 1
"""Current serialized terminal-audit record version."""


class TargetState(str, Enum):
    """Terminal lifecycle state requested by an audit."""

    DONE = "Done"
    MERGED = "Merged"
    ARCHIVED = "Archived"

    @classmethod
    def from_raw(cls, raw: Any) -> "TargetState":
        return _parse_enum(cls, raw)


class RequestState(str, Enum):
    """Lifecycle of a durable terminal-audit request."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"

    @classmethod
    def from_raw(cls, raw: Any) -> "RequestState":
        return _parse_enum(cls, raw)


class Verdict(str, Enum):
    """Machine-readable result of an audit attempt."""

    PASS = "pass"
    FAIL = "fail"
    NEEDS_HUMAN = "needs_human"
    ERROR = "error"

    # Descriptive aliases make the result pleasant to consume without
    # creating additional serialized values.
    PASSED = "pass"
    FAILED = "fail"

    @classmethod
    def from_raw(cls, raw: Any) -> "Verdict":
        return _parse_enum(cls, raw)


class FailureClassification(str, Enum):
    """Reason an audit did not produce a passing terminal result."""

    INCOMPLETE = "incomplete"
    MISSING_TESTS = "missing_tests"
    UNPUSHED = "unpushed"
    MISSING_EVIDENCE = "missing_evidence"
    CI_FAILURE = "ci_failure"
    CONFLICT = "conflict"
    OUT_OF_DATE = "out_of_date"
    HEALTHY_UNMERGED_REVIEW = "healthy_unmerged_review"
    AMBIGUOUS_REQUIREMENTS = "ambiguous_requirements"
    EXTERNAL_CAPABILITY = "external_capability"
    NO_AUDITOR = "no_auditor"
    UNSAFE_ARCHIVE = "unsafe_archive"
    MALFORMED_RESULT = "malformed_result"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    POLICY_INCOMPATIBILITY = "policy_incompatibility"

    @classmethod
    def from_raw(cls, raw: Any) -> "FailureClassification":
        return _parse_enum(cls, raw)


# Common names used by coordinator callers are kept as aliases, while the
# serialized vocabulary remains owned by the canonical types above.
AuditVerdict = Verdict
TerminalState = TargetState


_EnumT = TypeVar("_EnumT", bound=Enum)


def _parse_enum(enum_type: type[_EnumT], raw: Any) -> _EnumT:
    """Parse an enum value and reject missing, malformed, and unknown values."""

    if isinstance(raw, enum_type):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        valid = ", ".join(member.value for member in enum_type)
        raise ValueError(
            f"{enum_type.__name__} must be a non-empty string; expected one of: {valid}"
        )
    normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
    for member in enum_type:
        if str(member.value).lower() == normalized:
            return member
    valid = ", ".join(member.value for member in enum_type)
    raise ValueError(
        f"Unknown {enum_type.__name__} {raw!r}; expected one of: {valid}"
    )


def _require_mapping(raw: Any, type_name: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{type_name} must be a mapping, got {type(raw).__name__}")
    return raw


def _read_version(raw: Mapping[str, Any], type_name: str) -> int:
    version = raw.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError(
            f"{type_name} requires integer version {CURRENT_VERSION}; got {version!r}"
        )
    if version != CURRENT_VERSION:
        raise ValueError(
            f"Unsupported {type_name} version {version!r}; expected {CURRENT_VERSION}"
        )
    return version


def _required_string(raw: Mapping[str, Any], key: str, type_name: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{type_name} requires non-empty string field {key!r}")
    return value


def _optional_string(raw: Mapping[str, Any], key: str, type_name: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{type_name} optional field {key!r} must be a string or null")
    return value


def _optional_non_negative_int(
    raw: Mapping[str, Any], key: str, type_name: str
) -> int:
    value = raw.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"{type_name} optional field {key!r} must be a non-negative integer"
        )
    return value


def _normalize_text(value: str | None) -> str:
    """Normalize text without changing case-sensitive identifiers."""

    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"evidence values must be strings, got {type(value).__name__}")
    return " ".join(unicodedata.normalize("NFKC", value).split())


@dataclass(frozen=True)
class ContributorIdentity:
    """A stable, non-secret identity associated with the audited change.

    ``identity`` is intentionally opaque: callers may use a forge login, a
    git identity, or another stable identifier.  It must not contain access
    tokens or credentials.  ``source`` distinguishes namespaces such as
    ``github`` and ``git`` when the same identity string can occur in both.
    """

    identity: str
    source: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise ValueError("ContributorIdentity.identity must be non-empty")
        if self.source is not None and not isinstance(self.source, str):
            raise TypeError("ContributorIdentity.source must be a string or null")

    @property
    def name(self) -> str:
        """Compatibility/readability alias for callers using git terminology."""

        return self.identity

    @property
    def login(self) -> str:
        """Compatibility/readability alias for forge-backed identities."""

        return self.identity

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"version": CURRENT_VERSION, "identity": self.identity}
        if self.source is not None:
            result["source"] = self.source
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ContributorIdentity":
        data = _require_mapping(raw, cls.__name__)
        _read_version(data, cls.__name__)
        return cls(
            identity=_required_string(data, "identity", cls.__name__),
            source=_optional_string(data, "source", cls.__name__),
        )


@dataclass(frozen=True)
class EvidenceFingerprint:
    """Versioned SHA-256 digest of the accepted terminal-audit evidence."""

    digest: str
    algorithm: str = "sha256"

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("EvidenceFingerprint.algorithm must be 'sha256'")
        if (
            not isinstance(self.digest, str)
            or len(self.digest) != hashlib.sha256().digest_size * 2
            or any(character not in "0123456789abcdef" for character in self.digest)
        ):
            raise ValueError("EvidenceFingerprint.digest must be a lowercase SHA-256 hex digest")

    @property
    def value(self) -> str:
        """Alias for code that calls the fingerprint value rather than digest."""

        return self.digest

    @property
    def sha256(self) -> str:
        return self.digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CURRENT_VERSION,
            "algorithm": self.algorithm,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvidenceFingerprint":
        data = _require_mapping(raw, cls.__name__)
        _read_version(data, cls.__name__)
        algorithm = data.get("algorithm", "sha256")
        if not isinstance(algorithm, str):
            raise ValueError("EvidenceFingerprint.algorithm must be a string")
        return cls(
            digest=_required_string(data, "digest", cls.__name__),
            algorithm=algorithm,
        )

    @classmethod
    def from_evidence(
        cls,
        requirements_text: str,
        project_id: str,
        task_id: str,
        source_branch: str = "",
        source_sha: str = "",
        target_branch: str = "",
        target_sha: str = "",
        review_id: str = "",
        review_state: str = "",
        child_audit_digests: Iterable[str] = (),
        contributors: Iterable[ContributorIdentity | str] = (),
        *,
        child_audit_digest: str | None = None,
    ) -> "EvidenceFingerprint":
        """Build a deterministic digest from the permitted evidence fields.

        Contributor identities and child-audit digests are sorted before
        hashing, so their input order does not affect the result.  A single
        ``child_audit_digest`` is accepted as a convenience for the common
        no-chain case; when supplied it is included alongside the iterable.
        """

        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")

        child_digests = [_normalize_text(value) for value in child_audit_digests]
        if child_audit_digest is not None:
            child_digests.append(_normalize_text(child_audit_digest))

        normalized_contributors: list[dict[str, str]] = []
        for contributor in contributors:
            if isinstance(contributor, str):
                contributor = ContributorIdentity(contributor)
            if not isinstance(contributor, ContributorIdentity):
                raise TypeError(
                    "contributors must contain ContributorIdentity instances or strings"
                )
            normalized_contributors.append({
                "identity": _normalize_text(contributor.identity),
                "source": _normalize_text(contributor.source),
            })

        payload = {
            "format": "oompah-terminal-audit-evidence-v1",
            "requirements": _normalize_text(requirements_text),
            "project_id": _normalize_text(project_id),
            "task_id": _normalize_text(task_id),
            "source_branch": _normalize_text(source_branch),
            "source_sha": _normalize_text(source_sha),
            "target_branch": _normalize_text(target_branch),
            "target_sha": _normalize_text(target_sha),
            "review_id": _normalize_text(review_id),
            "review_state": _normalize_text(review_state),
            "child_audit_digests": sorted(child_digests),
            "contributors": sorted(
                normalized_contributors,
                key=lambda item: (item["source"], item["identity"]),
            ),
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return cls(hashlib.sha256(encoded).hexdigest())

    # ``build`` and ``compute`` are intentionally small aliases for callers
    # that prefer those names for a derived value.
    build = from_evidence
    compute = from_evidence


def compute_evidence_fingerprint(
    requirements_text: str,
    project_id: str,
    task_id: str,
    source_branch: str = "",
    source_sha: str = "",
    target_branch: str = "",
    target_sha: str = "",
    review_id: str = "",
    review_state: str = "",
    child_audit_digests: Iterable[str] = (),
    contributors: Iterable[ContributorIdentity | str] = (),
    *,
    child_audit_digest: str | None = None,
) -> EvidenceFingerprint:
    """Functional facade for :meth:`EvidenceFingerprint.from_evidence`."""

    return EvidenceFingerprint.from_evidence(
        requirements_text,
        project_id,
        task_id,
        source_branch,
        source_sha,
        target_branch,
        target_sha,
        review_id,
        review_state,
        child_audit_digests,
        contributors,
        child_audit_digest=child_audit_digest,
    )


def compute_issue_evidence_fingerprint(
    issue: Any,
    project_id: str,
) -> EvidenceFingerprint:
    """Build the canonical, auditor-independent fingerprint for a normalized tracker issue.

    This is the ONLY function that should be used to compute evidence fingerprints
    for terminal audit requests, API owner overrides, ACP owner overrides, and
    restart recovery.  All code paths that need a fingerprint must use this function
    to ensure consistent, canonical computation across the entire system.

    The fingerprint includes only task evidence (requirements, branch/SHA, review state,
    contributors, child audits) and explicitly excludes auditor-specific data
    (auditor identity, model, provider, execution timeline).  This ensures that
    the fingerprint remains stable across auditor retries and auditor selection
    changes.

    Terminal-transition entry points and restart recovery must derive evidence
    from exactly the same fields.  Native Markdown issues expose immutable git
    revision evidence through their persisted integration record rather than
    ad-hoc ``source_sha``/``target_sha`` attributes, so those values are used
    as fallbacks when present.

    Parameters
    ----------
    issue : Any
        A tracker issue object with optional properties:
        - description: task requirements text
        - identifier, id: task identifier
        - source_branch, work_branch, branch_name: source branch (with fallback to integration.task_branch)
        - source_sha: source commit SHA (with fallback to integration.head_sha)
        - target_branch: target branch (with fallback to integration.base_branch)
        - target_sha: target commit SHA (with fallback to integration.integrated_sha, integration.base_sha)
        - review_id, review_number: review identifier
        - review_state: review lifecycle state
        - contributors: list of ContributorIdentity or strings
        - child_audit_digests: list of child audit fingerprint digests
        - integration: optional integration record with task_branch, head_sha, base_branch, integrated_sha, base_sha
    project_id : str
        The managed project ID that owns this issue.

    Returns
    -------
    EvidenceFingerprint
        A deterministic SHA-256 digest representing the task evidence.
        Same inputs always produce the same digest (canonical).
        Different evidence produces a different digest (sensitive).

    See Also
    --------
    compute_evidence_fingerprint : Lower-level function accepting explicit fields
    """

    integration = getattr(issue, "integration", None)
    contributors = getattr(issue, "contributors", ()) or ()
    if isinstance(contributors, str):
        contributors = (contributors,)
    child_digests = getattr(issue, "child_audit_digests", ()) or ()
    if isinstance(child_digests, str):
        child_digests = (child_digests,)

    integrated_sha = str(getattr(integration, "integrated_sha", None) or "")
    integration_state = str(getattr(integration, "state", None) or "").lower()
    integrated_branch = str(getattr(integration, "base_branch", None) or "")
    if integration_state == "integrated" and integrated_sha:
        # A landed task is audited at the exact integrated commit.  The
        # integration staging path and API recovery/override paths must not
        # fall back to the submitted private head or a mutable task branch.
        source_branch = integrated_branch
        source_sha = integrated_sha
        target_branch = integrated_branch
        target_sha = integrated_sha
        if not contributors and getattr(integration, "task_branch", None):
            contributors = (
                ContributorIdentity(
                    identity=str(integration.task_branch),
                    source="git-branch",
                ),
            )
    else:
        source_branch = str(
            getattr(issue, "source_branch", None)
            or getattr(issue, "work_branch", None)
            or getattr(integration, "task_branch", None)
            or getattr(issue, "branch_name", None)
            or ""
        )
        source_sha = str(
            getattr(issue, "source_sha", None)
            or getattr(integration, "head_sha", None)
            or ""
        )
        target_branch = str(
            getattr(issue, "target_branch", None)
            or getattr(integration, "base_branch", None)
            or ""
        )
        target_sha = str(
            getattr(issue, "target_sha", None)
            or integrated_sha
            or getattr(integration, "base_sha", None)
            or ""
        )

    return compute_evidence_fingerprint(
        requirements_text=str(getattr(issue, "description", None) or ""),
        project_id=str(project_id),
        task_id=str(
            getattr(issue, "identifier", None)
            or getattr(issue, "id", None)
            or ""
        ),
        source_branch=source_branch,
        source_sha=source_sha,
        target_branch=target_branch,
        target_sha=target_sha,
        review_id=str(
            getattr(issue, "review_id", None)
            or getattr(issue, "review_number", None)
            or ""
        ),
        review_state=str(getattr(issue, "review_state", None) or ""),
        child_audit_digests=child_digests,
        contributors=contributors,
    )


@dataclass
class AuditAttempt:
    """One auditor execution associated with a terminal-audit request."""

    attempt_id: str
    target_state: TargetState
    evidence_fingerprint: EvidenceFingerprint
    request_state: RequestState = RequestState.PENDING
    verdict: Verdict | None = None
    failure_classification: FailureClassification | None = None
    requested_by: ContributorIdentity | None = None
    created_at: str | None = None
    completed_at: str | None = None
    # Dispatch metadata is optional so records written by older coordinators
    # remain readable.  These fields deliberately live on the existing
    # attempt record: the attempt identity is the idempotency boundary used by
    # both the scheduler and the result coordinator.
    provider_id: str | None = None
    model: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    failure_reason: str | None = None
    candidate_rotation_count: int = 0
    branch_key: str | None = None
    session_id: str | None = None
    next_retry_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, str) or not self.attempt_id.strip():
            raise ValueError("AuditAttempt.attempt_id must be non-empty")
        self.target_state = TargetState.from_raw(self.target_state)
        self.request_state = RequestState.from_raw(self.request_state)
        if not isinstance(self.evidence_fingerprint, EvidenceFingerprint):
            raise TypeError("AuditAttempt.evidence_fingerprint must be an EvidenceFingerprint")
        if self.verdict is not None:
            self.verdict = Verdict.from_raw(self.verdict)
        if self.failure_classification is not None:
            self.failure_classification = FailureClassification.from_raw(
                self.failure_classification
            )
        if self.requested_by is not None and not isinstance(
            self.requested_by, ContributorIdentity
        ):
            raise TypeError("AuditAttempt.requested_by must be ContributorIdentity or null")
        for name in (
            "provider_id", "model", "started_at", "ended_at", "failure_reason",
            "branch_key", "session_id", "next_retry_at",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"AuditAttempt.{name} must be a string or null")
        if (
            isinstance(self.candidate_rotation_count, bool)
            or not isinstance(self.candidate_rotation_count, int)
            or self.candidate_rotation_count < 0
        ):
            raise ValueError(
                "AuditAttempt.candidate_rotation_count must be a non-negative integer"
            )

    @property
    def id(self) -> str:
        return self.attempt_id

    @property
    def fingerprint(self) -> EvidenceFingerprint:
        return self.evidence_fingerprint

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": CURRENT_VERSION,
            "attempt_id": self.attempt_id,
            "target_state": self.target_state.value,
            "request_state": self.request_state.value,
            "evidence_fingerprint": self.evidence_fingerprint.to_dict(),
        }
        if self.verdict is not None:
            result["verdict"] = self.verdict.value
        if self.failure_classification is not None:
            result["failure_classification"] = self.failure_classification.value
        if self.requested_by is not None:
            result["requested_by"] = self.requested_by.to_dict()
        if self.created_at is not None:
            result["created_at"] = self.created_at
        if self.completed_at is not None:
            result["completed_at"] = self.completed_at
        for key in (
            "provider_id", "model", "started_at", "ended_at", "failure_reason",
            "branch_key", "session_id", "next_retry_at",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.candidate_rotation_count:
            result["candidate_rotation_count"] = self.candidate_rotation_count
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AuditAttempt":
        data = _require_mapping(raw, cls.__name__)
        _read_version(data, cls.__name__)
        fingerprint = data.get("evidence_fingerprint")
        if fingerprint is None:
            raise ValueError("AuditAttempt requires 'evidence_fingerprint'")
        requested_by = data.get("requested_by")
        return cls(
            attempt_id=_required_string(data, "attempt_id", cls.__name__),
            target_state=TargetState.from_raw(data.get("target_state")),
            evidence_fingerprint=EvidenceFingerprint.from_dict(fingerprint),
            request_state=RequestState.from_raw(data.get("request_state")),
            verdict=(Verdict.from_raw(data["verdict"]) if "verdict" in data else None),
            failure_classification=(
                FailureClassification.from_raw(data["failure_classification"])
                if "failure_classification" in data
                else None
            ),
            requested_by=(
                ContributorIdentity.from_dict(requested_by)
                if requested_by is not None
                else None
            ),
            created_at=_optional_string(data, "created_at", cls.__name__),
            completed_at=_optional_string(data, "completed_at", cls.__name__),
            provider_id=_optional_string(data, "provider_id", cls.__name__),
            model=_optional_string(data, "model", cls.__name__),
            started_at=_optional_string(data, "started_at", cls.__name__),
            ended_at=_optional_string(data, "ended_at", cls.__name__),
            failure_reason=_optional_string(data, "failure_reason", cls.__name__),
            candidate_rotation_count=_optional_non_negative_int(
                data, "candidate_rotation_count", cls.__name__
            ),
            branch_key=_optional_string(data, "branch_key", cls.__name__),
            session_id=_optional_string(data, "session_id", cls.__name__),
            next_retry_at=_optional_string(data, "next_retry_at", cls.__name__),
        )


@dataclass
class TerminalAuditRecord:
    """Durable request and bounded attempt history for one terminal target."""

    audit_id: str
    project_id: str
    task_id: str
    target_state: TargetState
    evidence_fingerprint: EvidenceFingerprint
    request_state: RequestState = RequestState.PENDING
    attempts: list[AuditAttempt] = field(default_factory=list)
    requested_by: ContributorIdentity | None = None
    previous_state: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        for name in ("audit_id", "project_id", "task_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"TerminalAuditRecord.{name} must be non-empty")
        self.target_state = TargetState.from_raw(self.target_state)
        self.request_state = RequestState.from_raw(self.request_state)
        if not isinstance(self.evidence_fingerprint, EvidenceFingerprint):
            raise TypeError(
                "TerminalAuditRecord.evidence_fingerprint must be an EvidenceFingerprint"
            )
        if not isinstance(self.attempts, list) or not all(
            isinstance(attempt, AuditAttempt) for attempt in self.attempts
        ):
            raise TypeError("TerminalAuditRecord.attempts must be a list of AuditAttempt")
        if self.requested_by is not None and not isinstance(
            self.requested_by, ContributorIdentity
        ):
            raise TypeError(
                "TerminalAuditRecord.requested_by must be ContributorIdentity or null"
            )

    @property
    def id(self) -> str:
        return self.audit_id

    @property
    def target(self) -> TargetState:
        return self.target_state

    @property
    def fingerprint(self) -> EvidenceFingerprint:
        return self.evidence_fingerprint

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": CURRENT_VERSION,
            "audit_id": self.audit_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "target_state": self.target_state.value,
            "request_state": self.request_state.value,
            "evidence_fingerprint": self.evidence_fingerprint.to_dict(),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }
        if self.requested_by is not None:
            result["requested_by"] = self.requested_by.to_dict()
        if self.previous_state is not None:
            result["previous_state"] = self.previous_state
        if self.created_at is not None:
            result["created_at"] = self.created_at
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TerminalAuditRecord":
        data = _require_mapping(raw, cls.__name__)
        _read_version(data, cls.__name__)
        fingerprint = data.get("evidence_fingerprint")
        if fingerprint is None:
            raise ValueError("TerminalAuditRecord requires 'evidence_fingerprint'")
        raw_attempts = data.get("attempts", [])
        if not isinstance(raw_attempts, list):
            raise ValueError("TerminalAuditRecord optional field 'attempts' must be a list")
        requested_by = data.get("requested_by")
        return cls(
            audit_id=_required_string(data, "audit_id", cls.__name__),
            project_id=_required_string(data, "project_id", cls.__name__),
            task_id=_required_string(data, "task_id", cls.__name__),
            target_state=TargetState.from_raw(data.get("target_state")),
            evidence_fingerprint=EvidenceFingerprint.from_dict(fingerprint),
            request_state=RequestState.from_raw(data.get("request_state")),
            attempts=[AuditAttempt.from_dict(attempt) for attempt in raw_attempts],
            requested_by=(
                ContributorIdentity.from_dict(requested_by)
                if requested_by is not None
                else None
            ),
            previous_state=_optional_string(data, "previous_state", cls.__name__),
            created_at=_optional_string(data, "created_at", cls.__name__),
            updated_at=_optional_string(data, "updated_at", cls.__name__),
        )


@dataclass(frozen=True)
class OverrideRecord:
    """Durable record of an explicit coordinator override by a project owner.

    An override bypasses the normal audit process when authorized by a verified
    project owner.  The reason field is mandatory and non-empty, and the
    evidence fingerprint is validated to match the current state at override time.
    """

    override_id: str
    project_id: str
    task_id: str
    target_state: TargetState
    evidence_fingerprint: EvidenceFingerprint
    authorized_by: ContributorIdentity
    reason: str
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.override_id, str) or not self.override_id.strip():
            raise ValueError("OverrideRecord.override_id must be non-empty")
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("OverrideRecord.project_id must be non-empty")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("OverrideRecord.task_id must be non-empty")
        object.__setattr__(self, "target_state", TargetState.from_raw(self.target_state))
        if not isinstance(self.evidence_fingerprint, EvidenceFingerprint):
            raise TypeError(
                "OverrideRecord.evidence_fingerprint must be an EvidenceFingerprint"
            )
        if not isinstance(self.authorized_by, ContributorIdentity):
            raise TypeError("OverrideRecord.authorized_by must be a ContributorIdentity")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("OverrideRecord.reason must be a non-empty string")

    @property
    def id(self) -> str:
        return self.override_id

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": CURRENT_VERSION,
            "override_id": self.override_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "target_state": self.target_state.value,
            "evidence_fingerprint": self.evidence_fingerprint.to_dict(),
            "authorized_by": self.authorized_by.to_dict(),
            "reason": self.reason,
        }
        if self.created_at is not None:
            result["created_at"] = self.created_at
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverrideRecord":
        data = _require_mapping(raw, cls.__name__)
        _read_version(data, cls.__name__)
        fingerprint = data.get("evidence_fingerprint")
        if fingerprint is None:
            raise ValueError("OverrideRecord requires 'evidence_fingerprint'")
        authorized_by = data.get("authorized_by")
        if authorized_by is None:
            raise ValueError("OverrideRecord requires 'authorized_by'")
        return cls(
            override_id=_required_string(data, "override_id", cls.__name__),
            project_id=_required_string(data, "project_id", cls.__name__),
            task_id=_required_string(data, "task_id", cls.__name__),
            target_state=TargetState.from_raw(data.get("target_state")),
            evidence_fingerprint=EvidenceFingerprint.from_dict(fingerprint),
            authorized_by=ContributorIdentity.from_dict(authorized_by),
            reason=_required_string(data, "reason", cls.__name__),
            created_at=_optional_string(data, "created_at", cls.__name__),
        )


AuditRecord = TerminalAuditRecord


__all__ = [
    "CURRENT_VERSION",
    "AuditAttempt",
    "AuditRecord",
    "AuditVerdict",
    "ContributorIdentity",
    "EvidenceFingerprint",
    "FailureClassification",
    "OverrideRecord",
    "RequestState",
    "TargetState",
    "TerminalAuditRecord",
    "TerminalState",
    "Verdict",
    "compute_evidence_fingerprint",
    "compute_issue_evidence_fingerprint",
]
