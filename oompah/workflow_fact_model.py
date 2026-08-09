"""Pure immutable evidence models consumed by workflow evaluators.

This module has no tracker, Git, SQLite, subprocess, or orchestrator imports.
I/O collectors live in :mod:`oompah.workflow_facts`, which re-exports these
models for backwards compatibility.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

WORKFLOW_FACTS_SCHEMA_VERSION = 1
LANDING_FACT_SCHEMA_VERSION = 1
_GIT_REVISION_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _thaw(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _required_text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_time(value: object, name: str) -> datetime:
    raw = _required_text(value, name)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _render_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("fact timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat()


def _now_iso() -> str:
    return _render_time(datetime.now(timezone.utc))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(key): _freeze(item)
                for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            }
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _render_time(value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple | list):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset | set):
        return sorted((_thaw(item) for item in value), key=repr)
    if isinstance(value, Enum):
        return value.value
    return value


class FactDomain(str, Enum):
    """Required evidence domains in one task snapshot."""

    TASK = "task"
    DEPENDENCIES = "dependencies"
    CONTAINMENT = "containment"
    INTEGRATION = "integration"
    TERMINAL_AUDIT = "terminal_audit"
    REVIEW_CI = "review_ci"
    LANDING = "landing"
    IMPLEMENTATION_AUTHORITY = "implementation_authority"
    DUPLICATE_INVESTIGATION = "duplicate_investigation"
    RETRY_BUDGET = "retry_budget"
    CONFIG = "config"


REQUIRED_FACT_DOMAINS = frozenset(FactDomain)


class FactState(str, Enum):
    """Knowledge quality of an observation."""

    KNOWN = "known"
    MISSING = "missing"
    STALE = "stale"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class FactObservation:
    """One immutable domain observation with a semantic revision."""

    domain: FactDomain | str
    state: FactState | str
    value: Any
    observed_at: str
    source: str
    error_code: str | None = None
    revision: str | None = None
    schema_version: int = WORKFLOW_FACTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", FactDomain(self.domain))
        object.__setattr__(self, "state", FactState(self.state))
        object.__setattr__(
            self,
            "observed_at",
            _render_time(_parse_time(self.observed_at, "observed_at")),
        )
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        error_code = _optional_text(self.error_code)
        object.__setattr__(self, "error_code", error_code)
        if self.schema_version != WORKFLOW_FACTS_SCHEMA_VERSION:
            raise ValueError("unsupported fact observation schema_version")
        frozen = _freeze(self.value)
        object.__setattr__(self, "value", frozen)
        if self.state is FactState.MISSING and frozen is not None:
            raise ValueError("missing facts cannot carry a value")
        if self.state in {FactState.KNOWN, FactState.STALE} and frozen is None:
            raise ValueError("known and stale facts require a value")
        if self.state is FactState.ERROR and not error_code:
            raise ValueError("error facts require error_code")
        if self.state is not FactState.ERROR and error_code:
            raise ValueError("error_code is only valid for error facts")
        expected = self.compute_revision()
        if self.revision is not None and str(self.revision) != expected:
            raise ValueError("fact observation revision does not match its content")
        object.__setattr__(self, "revision", expected)

    def compute_revision(self) -> str:
        """Hash semantic evidence, excluding observation time."""

        return _digest(
            {
                "schema_version": self.schema_version,
                "domain": self.domain.value,
                "state": self.state.value,
                "value": self.value,
                "source": self.source,
                "error_code": self.error_code,
            }
        )

    @classmethod
    def known(
        cls,
        domain: FactDomain,
        value: Any,
        *,
        observed_at: str,
        source: str,
    ) -> "FactObservation":
        return cls(domain, FactState.KNOWN, value, observed_at, source)

    @classmethod
    def missing(
        cls,
        domain: FactDomain,
        *,
        observed_at: str,
        source: str,
    ) -> "FactObservation":
        return cls(domain, FactState.MISSING, None, observed_at, source)

    @classmethod
    def stale(
        cls,
        domain: FactDomain,
        value: Any,
        *,
        observed_at: str,
        source: str,
    ) -> "FactObservation":
        return cls(domain, FactState.STALE, value, observed_at, source)

    @classmethod
    def error(
        cls,
        domain: FactDomain,
        *,
        observed_at: str,
        source: str,
        error_code: str,
    ) -> "FactObservation":
        return cls(
            domain,
            FactState.ERROR,
            None,
            observed_at,
            source,
            error_code=error_code,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "domain": self.domain.value,
            "state": self.state.value,
            "value": _thaw(self.value),
            "observed_at": self.observed_at,
            "source": self.source,
            "error_code": self.error_code,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FactObservation":
        if not isinstance(raw, Mapping):
            raise ValueError("fact observation must be an object")
        return cls(**dict(raw))


class LandingState(str, Enum):
    """Whether one exact revision is known to have landed on one target."""

    LANDED = "landed"
    NOT_LANDED = "not_landed"
    UNKNOWN = "unknown"


class LandingProofKind(str, Enum):
    """Known proof mechanisms; future string values remain serializable."""

    GIT_ANCESTRY = "git_ancestry"
    MERGE_COMMIT = "merge_commit"
    PATCH_ID = "patch_id"
    FORGE_MERGE = "forge_merge"
    TERMINAL_AUDIT = "terminal_audit"
    NOT_ANCESTOR = "not_ancestor"
    SOURCE_UNAVAILABLE = "source_unavailable"
    TARGET_UNAVAILABLE = "target_unavailable"
    OBSERVATION_ERROR = "observation_error"
    UNOBSERVED = "unobserved"


@dataclass(frozen=True, slots=True)
class LandingFact:
    """First-class landing evidence independent of parent lifecycle status."""

    source: str
    target: str
    revision: str | None
    proof: Mapping[str, Any]
    observed_at: str
    project_id: str
    evidence_revision: str | None = None
    state: LandingState | str = LandingState.UNKNOWN
    durable: bool = False
    error_code: str | None = None
    schema_version: int = LANDING_FACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "target", _required_text(self.target, "target"))
        object.__setattr__(
            self, "project_id", _required_text(self.project_id, "project_id")
        )
        object.__setattr__(self, "revision", _optional_text(self.revision))
        object.__setattr__(self, "state", LandingState(self.state))
        object.__setattr__(
            self,
            "observed_at",
            _render_time(_parse_time(self.observed_at, "observed_at")),
        )
        if self.schema_version != LANDING_FACT_SCHEMA_VERSION:
            raise ValueError("unsupported landing fact schema_version")
        proof = _freeze(self.proof)
        if not isinstance(proof, Mapping):
            raise ValueError("landing proof must be an object")
        kind = _optional_text(proof.get("kind"))
        if not kind:
            raise ValueError("landing proof requires kind")
        object.__setattr__(self, "proof", proof)
        error_code = _optional_text(self.error_code)
        object.__setattr__(self, "error_code", error_code)
        if error_code and self.state is not LandingState.UNKNOWN:
            raise ValueError("landing errors must have unknown state")
        if self.durable and self.state is not LandingState.LANDED:
            raise ValueError("only positive landing proof can be durable")
        expected = self.compute_evidence_revision()
        if self.evidence_revision is not None and self.evidence_revision != expected:
            raise ValueError("landing evidence_revision does not match its content")
        object.__setattr__(self, "evidence_revision", expected)

    def compute_evidence_revision(self) -> str:
        """Hash semantic proof, excluding observation time."""

        return _digest(
            {
                "schema_version": self.schema_version,
                "source": self.source,
                "target": self.target,
                "project_id": self.project_id,
                "revision": self.revision,
                "state": self.state.value,
                "proof": self.proof,
                "durable": self.durable,
                "error_code": self.error_code,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "target": self.target,
            "project_id": self.project_id,
            "revision": self.revision,
            "proof": _thaw(self.proof),
            "observed_at": self.observed_at,
            "evidence_revision": self.evidence_revision,
            "state": self.state.value,
            "durable": self.durable,
            "error_code": self.error_code,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LandingFact":
        if not isinstance(raw, Mapping):
            raise ValueError("landing fact must be an object")
        return cls(**dict(raw))


@dataclass(frozen=True, slots=True)
class CollectedValue:
    """Provider value with its own observation time and staleness bound."""

    value: Any
    observed_at: str
    source: str
    stale_after_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed_at",
            _render_time(_parse_time(self.observed_at, "observed_at")),
        )
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        if self.stale_after_seconds is not None and self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")


@dataclass(frozen=True, slots=True)
class LandingRequest:
    source: str
    target: str
    revision: str | None = None
    prior: LandingFact | None = None
    prefer_live_source: bool = False
    authoritative_target: bool = False
    trusted_target_revision: str | None = None

    def __post_init__(self) -> None:
        for name in ("source", "target"):
            value = _required_text(getattr(self, name), name)
            if value.startswith("-") or any(
                character in value for character in "\x00\r\n"
            ):
                raise ValueError(f"{name} is not a safe Git ref")
            object.__setattr__(self, name, value)
        revision = _optional_text(self.revision)
        if revision is not None and not _GIT_REVISION_RE.fullmatch(revision):
            raise ValueError("landing revision must be a hexadecimal Git object id")
        object.__setattr__(self, "revision", revision.lower() if revision else None)
        target_revision = _optional_text(self.trusted_target_revision)
        if target_revision is not None and not _GIT_REVISION_RE.fullmatch(
            target_revision
        ):
            raise ValueError(
                "trusted target revision must be a hexadecimal Git object id"
            )
        object.__setattr__(
            self,
            "trusted_target_revision",
            target_revision.lower() if target_revision else None,
        )
        if self.prior is not None and not isinstance(self.prior, LandingFact):
            raise TypeError("prior must be a LandingFact")


@dataclass(frozen=True, slots=True)
class WorkflowFacts:
    """Complete immutable evidence snapshot consumed by task evaluation."""

    project_id: str
    task_id: str
    collected_at: str
    observations: Mapping[FactDomain | str, FactObservation]
    landings: tuple[LandingFact, ...] = ()
    facts_version: str | None = None
    schema_version: int = WORKFLOW_FACTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "project_id", _required_text(self.project_id, "project_id")
        )
        object.__setattr__(self, "task_id", _required_text(self.task_id, "task_id"))
        object.__setattr__(
            self,
            "collected_at",
            _render_time(_parse_time(self.collected_at, "collected_at")),
        )
        if self.schema_version != WORKFLOW_FACTS_SCHEMA_VERSION:
            raise ValueError("unsupported WorkflowFacts schema_version")
        normalized: dict[FactDomain, FactObservation] = {}
        for raw_domain, observation in self.observations.items():
            domain = FactDomain(raw_domain)
            if not isinstance(observation, FactObservation):
                raise TypeError("observations must contain FactObservation values")
            if observation.domain is not domain:
                raise ValueError("observation key does not match its domain")
            normalized[domain] = observation
        missing = REQUIRED_FACT_DOMAINS - set(normalized)
        extra = set(normalized) - REQUIRED_FACT_DOMAINS
        if missing or extra:
            raise ValueError(
                f"WorkflowFacts domains mismatch: missing={sorted(item.value for item in missing)!r}, "
                f"extra={sorted(item.value for item in extra)!r}"
            )
        object.__setattr__(
            self,
            "observations",
            MappingProxyType(
                dict(sorted(normalized.items(), key=lambda item: item[0].value))
            ),
        )
        landings = tuple(self.landings)
        if any(not isinstance(item, LandingFact) for item in landings):
            raise TypeError("landings must contain LandingFact values")
        if any(item.project_id != self.project_id for item in landings):
            raise ValueError("landing facts must belong to the WorkflowFacts project")
        object.__setattr__(
            self,
            "landings",
            tuple(
                sorted(
                    landings,
                    key=lambda item: (item.source, item.target, item.revision or ""),
                )
            ),
        )
        landing_observation = normalized[FactDomain.LANDING]
        expected_landing_revisions = [item.evidence_revision for item in self.landings]
        if landing_observation.state is FactState.KNOWN:
            if not isinstance(landing_observation.value, Mapping):
                raise ValueError("known landing observation must be an object")
            observed_revisions = list(
                landing_observation.value.get("evidence_revisions", ())
            )
            if observed_revisions != expected_landing_revisions:
                raise ValueError(
                    "landing observation does not match first-class landings"
                )
        elif self.landings:
            raise ValueError("first-class landings require a known landing observation")
        expected = self.compute_facts_version()
        if self.facts_version is not None and self.facts_version != expected:
            raise ValueError("facts_version does not match observations")
        object.__setattr__(self, "facts_version", expected)

    def compute_facts_version(self) -> str:
        """Hash semantic evidence revisions, excluding collection time."""

        return _digest(
            {
                "schema_version": self.schema_version,
                "project_id": self.project_id,
                "task_id": self.task_id,
                "observations": {
                    domain.value: observation.revision
                    for domain, observation in self.observations.items()
                },
                "landings": [item.evidence_revision for item in self.landings],
            }
        )

    def fact(self, domain: FactDomain | str) -> FactObservation:
        return self.observations[FactDomain(domain)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "collected_at": self.collected_at,
            "facts_version": self.facts_version,
            "observations": {
                domain.value: observation.to_dict()
                for domain, observation in self.observations.items()
            },
            "landings": [item.to_dict() for item in self.landings],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WorkflowFacts":
        if not isinstance(raw, Mapping):
            raise ValueError("WorkflowFacts must be an object")
        observations = raw.get("observations")
        landings = raw.get("landings", [])
        if not isinstance(observations, Mapping) or not isinstance(landings, list):
            raise ValueError("WorkflowFacts observations/landings have invalid shape")
        return cls(
            project_id=raw.get("project_id"),
            task_id=raw.get("task_id"),
            collected_at=raw.get("collected_at"),
            facts_version=raw.get("facts_version"),
            schema_version=raw.get("schema_version", WORKFLOW_FACTS_SCHEMA_VERSION),
            observations={
                FactDomain(domain): FactObservation.from_dict(value)
                for domain, value in observations.items()
            },
            landings=tuple(LandingFact.from_dict(value) for value in landings),
        )

    def stable_json(self) -> str:
        return _canonical_json(self.to_dict())
