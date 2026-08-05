"""Immutable, project-scoped evidence for workflow decisions.

Workflow progression must distinguish an observed negative from unavailable,
stale, or failed evidence.  This module normalizes each evidence domain into a
versioned :class:`FactObservation`, gives landing/containment proof a first-
class durable representation, and composes the observations into one stable
``WorkflowFacts`` revision suitable for pure evaluation and compare-and-swap
transition intents.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from oompah.models import BlockerRef, Issue
from oompah.statuses import canonicalize_status
from oompah.tracker import TrackerProtocol


@runtime_checkable
class IntegrationQueueProtocol(Protocol):
    """Narrow queue-store surface needed for integration fact overlay.

    Any object with this interface may be passed as ``integration_queue``
    to :class:`WorkflowFactCollector`.  This keeps the collector decoupled
    from the concrete ``IntegrationQueueStore`` implementation.
    """

    def get(self, project_id: str, task_id: str) -> Any | None:
        """Return one queue row or None if the task is not queued."""
        ...

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


def _git_error_code(stderr: str) -> str:
    text = stderr.lower()
    if "not a git repository" in text or "repository unavailable" in text:
        return "git_repository_unavailable"
    if "permission denied" in text:
        return "git_permission_denied"
    return "git_observation_failed"


class GitLandingCollector:
    """Collect target-specific landing facts from real Git evidence."""

    def __init__(
        self,
        repo_path: str | os.PathLike[str],
        *,
        project_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.project_id = _required_text(project_id, "project_id")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["git", *args]
        try:
            return subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return subprocess.CompletedProcess(
                command,
                128,
                stdout="",
                stderr=f"git repository unavailable: {type(exc).__name__}",
            )

    def _resolve(self, ref: str) -> tuple[str | None, str | None]:
        candidates = (ref, f"refs/heads/{ref}", f"refs/remotes/origin/{ref}")
        last_error = ""
        for candidate in candidates:
            result = self._run("rev-parse", "--verify", f"{candidate}^{{commit}}")
            if result.returncode == 0:
                return result.stdout.strip().lower(), None
            last_error = result.stderr
        return None, _git_error_code(last_error)

    @staticmethod
    def _matching_prior(
        prior: LandingFact | None,
        *,
        source: str,
        target: str,
        revision: str | None,
        project_id: str,
    ) -> LandingFact | None:
        if (
            prior
            and prior.state is LandingState.LANDED
            and prior.durable
            and prior.source == source
            and prior.target == target
            and prior.project_id == project_id
            and (revision is None or prior.revision == revision)
        ):
            return prior
        return None

    def collect(self, request: LandingRequest) -> LandingFact:
        observed_at = _render_time(self._clock())
        source = _required_text(request.source, "source")
        target = _required_text(request.target, "target")
        requested_revision = _optional_text(request.revision)
        if requested_revision:
            source_result = self._run(
                "cat-file", "-e", f"{requested_revision}^{{commit}}"
            )
            source_revision = (
                requested_revision.lower() if source_result.returncode == 0 else None
            )
            source_error = _git_error_code(source_result.stderr)
        else:
            source_revision, source_error = self._resolve(source)
        target_revision, target_error = self._resolve(target)
        prior = self._matching_prior(
            request.prior,
            source=source,
            target=target,
            revision=requested_revision,
            project_id=self.project_id,
        )

        # A matching durable positive is historical evidence, not a cache of
        # the current ref layout.  Preserve it even if either ref disappeared
        # or the target was later rewritten; current containment can be a
        # separate observation, but terminal landing must not be erased.
        if prior is not None:
            return LandingFact(
                source,
                target,
                prior.revision,
                prior.proof,
                observed_at,
                self.project_id,
                state=LandingState.LANDED,
                durable=True,
            )

        if source_revision is None:
            return LandingFact(
                source,
                target,
                requested_revision,
                {"kind": LandingProofKind.SOURCE_UNAVAILABLE.value},
                observed_at,
                self.project_id,
                state=LandingState.UNKNOWN,
                error_code=source_error,
            )
        if target_revision is None:
            return LandingFact(
                source,
                target,
                source_revision,
                {"kind": LandingProofKind.TARGET_UNAVAILABLE.value},
                observed_at,
                self.project_id,
                state=LandingState.UNKNOWN,
                error_code=target_error,
            )

        result = self._run(
            "merge-base", "--is-ancestor", source_revision, target_revision
        )
        proof_base = {
            "source_sha": source_revision,
            "target_sha": target_revision,
        }
        if result.returncode == 0:
            return LandingFact(
                source,
                target,
                source_revision,
                {"kind": LandingProofKind.GIT_ANCESTRY.value, **proof_base},
                observed_at,
                self.project_id,
                state=LandingState.LANDED,
                durable=True,
            )
        if result.returncode == 1:
            return LandingFact(
                source,
                target,
                source_revision,
                {"kind": LandingProofKind.NOT_ANCESTOR.value, **proof_base},
                observed_at,
                self.project_id,
                state=LandingState.NOT_LANDED,
            )
        return LandingFact(
            source,
            target,
            source_revision,
            {"kind": LandingProofKind.OBSERVATION_ERROR.value, **proof_base},
            observed_at,
            self.project_id,
            state=LandingState.UNKNOWN,
            error_code=_git_error_code(result.stderr),
        )


FactSource = Callable[[Issue], FactObservation | CollectedValue | Any]


def _blocker_value(blocker: BlockerRef) -> dict[str, Any]:
    return {
        "id": _optional_text(blocker.id),
        "identifier": _optional_text(blocker.identifier),
        "status": canonicalize_status(blocker.state) if blocker.state else None,
    }


def _integration_value(issue: Issue) -> Any:
    integration = issue.integration
    if integration is None:
        return None
    if hasattr(integration, "to_dict"):
        return integration.to_dict()
    if isinstance(integration, Mapping):
        return dict(integration)
    return {
        key: getattr(integration, key, None)
        for key in (
            "version",
            "state",
            "attempts",
            "task_branch",
            "base_branch",
            "head_sha",
            "base_sha",
            "submitted_at",
        )
    }


def _task_value(issue: Issue) -> dict[str, Any]:
    return {
        "id": issue.id,
        "identifier": issue.identifier,
        "status": canonicalize_status(issue.state),
        "issue_type": issue.issue_type,
        "parent_id": issue.parent_id,
        "project_id": issue.project_id,
        "work_branch": issue.work_branch,
        "target_branch": issue.target_branch,
        "assignment_id": issue.assignment_id,
        "head_sha": issue.head_sha,
    }


class WorkflowFactCollector:
    """Collect one complete project-scoped snapshot without false empties."""

    _EXTERNAL_DOMAINS = (
        FactDomain.TERMINAL_AUDIT,
        FactDomain.REVIEW_CI,
        FactDomain.IMPLEMENTATION_AUTHORITY,
        FactDomain.RETRY_BUDGET,
        FactDomain.CONFIG,
    )

    def __init__(
        self,
        *,
        project_id: str,
        tracker: TrackerProtocol,
        sources: Mapping[FactDomain | str, FactSource] | None = None,
        landing_collector: GitLandingCollector | None = None,
        integration_queue: IntegrationQueueProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.project_id = _required_text(project_id, "project_id")
        self.tracker = tracker
        self.sources = {
            FactDomain(domain): source for domain, source in (sources or {}).items()
        }
        forbidden = set(self.sources) & {
            FactDomain.TASK,
            FactDomain.DEPENDENCIES,
            FactDomain.CONTAINMENT,
            FactDomain.INTEGRATION,
            FactDomain.LANDING,
        }
        if forbidden:
            raise ValueError(
                f"built-in fact domains cannot be overridden: {sorted(item.value for item in forbidden)!r}"
            )
        self.landing_collector = landing_collector
        if (
            landing_collector is not None
            and landing_collector.project_id != self.project_id
        ):
            raise ValueError("landing collector project does not match fact collector")
        self.integration_queue = integration_queue
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> tuple[datetime, str]:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("workflow fact collector clock must be timezone-aware")
        return now.astimezone(timezone.utc), _render_time(now)

    def _source_observation(
        self,
        domain: FactDomain,
        issue: Issue,
        *,
        now: datetime,
        now_iso: str,
    ) -> FactObservation:
        source = self.sources.get(domain)
        if source is None:
            return FactObservation.missing(
                domain, observed_at=now_iso, source=f"{domain.value}:unconfigured"
            )
        try:
            raw = source(issue)
        except Exception as exc:  # noqa: BLE001 - evidence boundary
            return FactObservation.error(
                domain,
                observed_at=now_iso,
                source=f"{domain.value}:collector",
                error_code=f"{domain.value}_{type(exc).__name__.lower()}",
            )
        if isinstance(raw, FactObservation):
            if raw.domain is not domain:
                return FactObservation.error(
                    domain,
                    observed_at=now_iso,
                    source=f"{domain.value}:collector",
                    error_code="collector_domain_mismatch",
                )
            return raw
        if raw is None:
            return FactObservation.missing(
                domain, observed_at=now_iso, source=f"{domain.value}:collector"
            )
        if isinstance(raw, CollectedValue):
            observed = _parse_time(raw.observed_at, "observed_at")
            stale = (
                raw.stale_after_seconds is not None
                and (now - observed).total_seconds() > raw.stale_after_seconds
            )
            constructor = FactObservation.stale if stale else FactObservation.known
            return constructor(
                domain,
                raw.value,
                observed_at=raw.observed_at,
                source=raw.source,
            )
        return FactObservation.known(
            domain,
            raw,
            observed_at=now_iso,
            source=f"{domain.value}:collector",
        )

    def _all_error(
        self,
        task_id: str,
        *,
        now_iso: str,
        error_code: str,
    ) -> WorkflowFacts:
        observations = {
            domain: FactObservation.error(
                domain,
                observed_at=now_iso,
                source="tracker",
                error_code=error_code,
            )
            for domain in REQUIRED_FACT_DOMAINS
        }
        return WorkflowFacts(
            self.project_id,
            task_id,
            now_iso,
            observations,
        )

    def _overlay_integration_queue(
        self,
        tracker_value: dict[str, Any] | None,
        issue: Issue,
        now_iso: str,
    ) -> dict[str, Any] | None:
        """Overlay durable IntegrationQueueStore state onto tracker integration.

        The tracker's integration record can lag the queue when a worker has
        claimed the item (state=integrating) or the gate returned a definitive
        block (state=blocked) but the tracker has not yet been updated.  The
        overlay makes the controller see the authoritative durable state so it
        does not schedule a duplicate integration_attempt while one is already
        active, and does not retry a definitively blocked head.

        The overlay is fenced to the exact tracker head.  A queue row that was
        recorded against an older head (H1) MUST NOT block or suppress the
        integration attempt required for a newer head (H2): only rows whose
        ``head_sha`` matches the current tracker head are treated as authoritative
        for the current generation.  This preserves same-generation retry and
        newer-head semantics required by OOMPAH-838 and the pre-landing audit.

        When the queue row is fenced to the current head and carries a
        ``retry_forced`` marker, the flag is propagated into the integration
        fact so ``_integration_decision`` can permit the intended
        same-generation retry through an otherwise blocked gate.

        When the queue holds a valid ``integrating`` lease but the tracker
        still shows ``ready``/``queued``, the overlay emits the
        ``live_claim_precedes_history`` flag so live work outranks historical
        audit replay in the decision evaluator.
        """
        if self.integration_queue is None:
            return tracker_value
        try:
            queue_row = self.integration_queue.get(self.project_id, issue.identifier)
        except Exception:  # noqa: BLE001 - queue evidence boundary
            # A read error must not suppress valid tracker evidence.
            return tracker_value
        if queue_row is None:
            return tracker_value

        # Exact-head fence.  The current tracker head is the authority.  Any
        # queue row that predates this head is stale and must not overlay.
        # ``tracker_head`` may be None when the tracker integration record has
        # no head recorded yet; in that case we still allow the overlay so the
        # first live claim can be represented, but only when the queue row
        # matches the issue's own head (or the issue also has no head).
        tracker_head = None
        if isinstance(tracker_value, dict):
            tracker_head = tracker_value.get("head_sha")
        issue_head = getattr(issue, "head_sha", None)
        queue_head = getattr(queue_row, "head_sha", None)
        authoritative_head = tracker_head or issue_head
        if authoritative_head and queue_head and str(queue_head) != str(authoritative_head):
            # Stale queue row for an older head.  Ignore.
            return tracker_value
        if authoritative_head and not queue_head:
            # Ambiguous queue row without a head recorded; treat as stale
            # rather than let it suppress the current head's work.
            return tracker_value

        # Merge queue durable state into the tracker value.  Start from the
        # tracker dict and overlay only the fields that the queue uniquely owns.
        base: dict[str, Any] = dict(tracker_value) if tracker_value is not None else {}
        queue_state = str(getattr(queue_row, "state", None) or "").strip()
        retry_forced = bool(getattr(queue_row, "retry_forced", False))
        prior_tracker_state = None
        if isinstance(tracker_value, dict):
            prior = tracker_value.get("state")
            prior_tracker_state = str(prior).strip() if prior else None

        lease_expires_at_raw = getattr(queue_row, "lease_expires_at", None)
        lease_owner_raw = getattr(queue_row, "lease_owner", None)
        lease_expires_dt: datetime | None = None
        if lease_expires_at_raw is not None:
            try:
                lease_expires_dt = datetime.fromtimestamp(
                    float(lease_expires_at_raw), tz=timezone.utc
                )
            except (TypeError, ValueError, OSError, OverflowError):
                lease_expires_dt = None

        if queue_state in ("integrating", "blocked"):
            base["state"] = queue_state
        if queue_state == "integrating":
            if lease_expires_dt is not None:
                base["lease_expires_at"] = _render_time(lease_expires_dt)
            if lease_owner_raw:
                base["lease_owner"] = str(lease_owner_raw)
            # Emit live_claim_precedes_history when the durable queue shows a
            # valid live lease but the tracker still holds a historical
            # ``ready``/``queued`` view.  The decision evaluator uses this
            # flag to keep the live claim ahead of unbounded historical
            # audit replay.
            live_lease_valid = (
                lease_expires_dt is not None
                and lease_expires_dt > self._clock()
                and bool(lease_owner_raw)
            )
            if live_lease_valid and prior_tracker_state in {
                "ready",
                "queued",
                None,
                "",
            }:
                base["live_claim_precedes_history"] = True
        if queue_state == "blocked":
            last_error = getattr(queue_row, "last_error", None)
            if last_error:
                base["last_error"] = str(last_error)
            if retry_forced:
                # Explicit same-generation retry authority.  Preserve the
                # blocked state (so audit trails match) but signal that the
                # controller may still enqueue an integration attempt.
                base["retry_forced"] = True
        # Propagate retry_forced regardless of state so downstream can see
        # explicit repair authority carried into the fact.
        if retry_forced and "retry_forced" not in base:
            base["retry_forced"] = True
        return base

    def collect(
        self,
        task_id: str,
        *,
        landing_requests: Sequence[LandingRequest] = (),
    ) -> WorkflowFacts:
        task_id = _required_text(task_id, "task_id")
        now, now_iso = self._now()
        try:
            issue = self.tracker.fetch_issue_detail(task_id)
        except Exception as exc:  # noqa: BLE001 - tracker evidence boundary
            return self._all_error(
                task_id,
                now_iso=now_iso,
                error_code=f"tracker_{type(exc).__name__.lower()}",
            )
        if issue is None:
            observations = {
                domain: FactObservation.missing(
                    domain, observed_at=now_iso, source="tracker"
                )
                for domain in REQUIRED_FACT_DOMAINS
            }
            return WorkflowFacts(self.project_id, task_id, now_iso, observations)
        if issue.project_id and str(issue.project_id) != self.project_id:
            return self._all_error(
                task_id,
                now_iso=now_iso,
                error_code="project_scope_mismatch",
            )

        observations: dict[FactDomain, FactObservation] = {
            FactDomain.TASK: FactObservation.known(
                FactDomain.TASK,
                _task_value(issue),
                observed_at=now_iso,
                source="tracker",
            ),
            FactDomain.DEPENDENCIES: FactObservation.known(
                FactDomain.DEPENDENCIES,
                {
                    "finish": sorted(
                        [_blocker_value(item) for item in issue.blocked_by],
                        key=lambda item: item["identifier"] or item["id"] or "",
                    ),
                    "hard_start": sorted(
                        [_blocker_value(item) for item in issue.start_blocked_by],
                        key=lambda item: item["identifier"] or item["id"] or "",
                    ),
                },
                observed_at=now_iso,
                source="tracker",
            ),
        }
        try:
            children = self.tracker.fetch_children(issue.identifier)
        except Exception as exc:  # noqa: BLE001 - tracker evidence boundary
            observations[FactDomain.CONTAINMENT] = FactObservation.error(
                FactDomain.CONTAINMENT,
                observed_at=now_iso,
                source="tracker",
                error_code=f"children_{type(exc).__name__.lower()}",
            )
        else:
            observations[FactDomain.CONTAINMENT] = FactObservation.known(
                FactDomain.CONTAINMENT,
                {
                    "parent_id": issue.parent_id,
                    "children": sorted(
                        [
                            {
                                "identifier": child.identifier,
                                "status": canonicalize_status(child.state),
                                "issue_type": child.issue_type,
                            }
                            for child in children
                            if not child.project_id
                            or str(child.project_id) == self.project_id
                        ],
                        key=lambda item: item["identifier"],
                    ),
                },
                observed_at=now_iso,
                source="tracker",
            )
        integration = _integration_value(issue)
        integration = self._overlay_integration_queue(
            integration, issue, now_iso
        )
        observations[FactDomain.INTEGRATION] = (
            FactObservation.known(
                FactDomain.INTEGRATION,
                integration,
                observed_at=now_iso,
                source="tracker",
            )
            if integration is not None
            else FactObservation.missing(
                FactDomain.INTEGRATION, observed_at=now_iso, source="tracker"
            )
        )
        for domain in self._EXTERNAL_DOMAINS:
            observations[domain] = self._source_observation(
                domain, issue, now=now, now_iso=now_iso
            )

        landings: tuple[LandingFact, ...] = ()
        if landing_requests and self.landing_collector is None:
            observations[FactDomain.LANDING] = FactObservation.error(
                FactDomain.LANDING,
                observed_at=now_iso,
                source="git",
                error_code="landing_collector_unavailable",
            )
        elif landing_requests:
            try:
                collected = tuple(
                    self.landing_collector.collect(request)
                    for request in landing_requests
                )
            except Exception as exc:  # noqa: BLE001 - landing evidence boundary
                observations[FactDomain.LANDING] = FactObservation.error(
                    FactDomain.LANDING,
                    observed_at=now_iso,
                    source="git",
                    error_code=f"landing_{type(exc).__name__.lower()}",
                )
            else:
                observations[FactDomain.LANDING] = FactObservation.known(
                    FactDomain.LANDING,
                    {
                        "evidence_revisions": [
                            item.evidence_revision
                            for item in sorted(
                                collected,
                                key=lambda item: (
                                    item.source,
                                    item.target,
                                    item.revision or "",
                                ),
                            )
                        ]
                    },
                    observed_at=now_iso,
                    source="git",
                )
                landings = collected
        else:
            observations[FactDomain.LANDING] = FactObservation.missing(
                FactDomain.LANDING, observed_at=now_iso, source="git"
            )

        return WorkflowFacts(
            self.project_id,
            task_id,
            now_iso,
            observations,
            landings=landings,
        )
