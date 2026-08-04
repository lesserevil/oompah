"""No-mutation shadow evaluation and structured divergence diagnostics."""

from __future__ import annotations

import hashlib
import json
import threading
from copy import deepcopy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from oompah.models import Issue
from oompah.secrets import redact_sensitive_data
from oompah.statuses import canonicalize_status
from oompah.work_decision import PermittedAction, WorkDecision, evaluate_task
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_facts import WorkflowFacts


WORKFLOW_ENGINE_MODES = frozenset({"off", "shadow", "enforce"})
DEFAULT_DIAGNOSTIC_LIMIT = 100
MAX_DIAGNOSTIC_LIMIT = 1000
DEFAULT_MAX_DIAGNOSTIC_BYTES = 64 * 1024
_MAX_STRING_LENGTH = 2048
_MAX_SEQUENCE_ITEMS = 100
_MAX_MAPPING_ITEMS = 200
_DIAGNOSTIC_SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "private_key",
    "credential",
)


def normalize_workflow_engine_mode(value: object) -> str:
    mode = str(value or "off").strip().lower()
    if mode not in WORKFLOW_ENGINE_MODES:
        raise ValueError(
            "workflow engine mode must be one of: "
            + ", ".join(sorted(WORKFLOW_ENGINE_MODES))
        )
    return mode


def _required_text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_limit(limit: int) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    value = int(limit)
    if value < 1 or value > MAX_DIAGNOSTIC_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_DIAGNOSTIC_LIMIT}")
    return value


def _bounded_value(value: Any, depth: int = 0) -> Any:
    if depth >= 8:
        return "[truncated-depth]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda item: str(item[0]))
        result = {}
        for key, item in items[:_MAX_MAPPING_ITEMS]:
            normalized_key = str(key)[:128]
            if any(
                marker in normalized_key.lower()
                for marker in _DIAGNOSTIC_SECRET_KEY_PARTS
            ):
                result[normalized_key] = "[REDACTED]"
            else:
                result[normalized_key] = _bounded_value(item, depth + 1)
        if len(items) > _MAX_MAPPING_ITEMS:
            result["_truncated_items"] = len(items) - _MAX_MAPPING_ITEMS
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        result = [
            _bounded_value(item, depth + 1)
            for item in list(value)[:_MAX_SEQUENCE_ITEMS]
        ]
        if len(value) > _MAX_SEQUENCE_ITEMS:
            result.append({"_truncated_items": len(value) - _MAX_SEQUENCE_ITEMS})
        return result
    return str(value)[:_MAX_STRING_LENGTH]


def _safe_diagnostic(value: Mapping[str, Any], max_bytes: int) -> dict[str, Any]:
    bounded = _bounded_value(value)
    redacted = redact_sensitive_data(bounded)
    if not isinstance(redacted, dict):
        return {"error": "diagnostic redaction failed closed"}
    encoded = _canonical_json(redacted)
    if len(encoded.encode()) <= max_bytes:
        return redacted
    return {
        "truncated": True,
        "size_bytes": len(encoded.encode()),
        "identity": {
            key: redacted.get(key)
            for key in (
                "project_id",
                "task_id",
                "facts_version",
                "decision_revision",
                "snapshot_generation",
            )
            if key in redacted
        },
    }


class ShadowComparisonState(str, Enum):
    ALIGNED = "aligned"
    DIVERGED = "diverged"


@dataclass(frozen=True, slots=True)
class LegacyWorkflowProjection:
    """One assertion made by a legacy workflow consumer."""

    consumer: str
    status: str | None = None
    disposition: TaskDisposition | str | None = None
    owner: WorkflowOwner | str | None = None
    reason_code: str | None = None
    permitted_actions: tuple[PermittedAction | str, ...] | None = None
    recommended_status: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "consumer", _required_text(self.consumer, "consumer"))
        if self.status is not None:
            object.__setattr__(self, "status", canonicalize_status(self.status))
        if self.disposition is not None:
            object.__setattr__(self, "disposition", TaskDisposition(self.disposition))
        if self.owner is not None:
            object.__setattr__(self, "owner", WorkflowOwner(self.owner))
        if self.reason_code is not None:
            object.__setattr__(
                self, "reason_code", _required_text(self.reason_code, "reason_code")
            )
        if self.permitted_actions is not None:
            object.__setattr__(
                self,
                "permitted_actions",
                tuple(
                    sorted(
                        {PermittedAction(action) for action in self.permitted_actions},
                        key=lambda action: action.value,
                    )
                ),
            )
        if self.recommended_status is not None:
            object.__setattr__(
                self,
                "recommended_status",
                canonicalize_status(self.recommended_status),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "consumer": self.consumer,
            "status": self.status,
            "disposition": self.disposition.value if self.disposition else None,
            "owner": self.owner.value if self.owner else None,
            "reason_code": self.reason_code,
            "permitted_actions": (
                [action.value for action in self.permitted_actions]
                if self.permitted_actions is not None
                else None
            ),
            "recommended_status": self.recommended_status,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDivergence:
    fingerprint: str
    project_id: str
    task_id: str
    mismatches: Mapping[str, Mapping[str, Mapping[str, Any]]]
    first_observed_at: str
    last_observed_at: str
    observation_count: int
    snapshot_generation: int
    facts_version: str
    decision_revision: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "mismatches": {
                consumer: {field: dict(values) for field, values in fields.items()}
                for consumer, fields in self.mismatches.items()
            },
            "first_observed_at": self.first_observed_at,
            "last_observed_at": self.last_observed_at,
            "observation_count": self.observation_count,
            "snapshot_generation": self.snapshot_generation,
            "facts_version": self.facts_version,
            "decision_revision": self.decision_revision,
        }


@dataclass(frozen=True, slots=True)
class ShadowEvaluationResult:
    accepted: bool
    changed: bool
    state: ShadowComparisonState | None
    diagnostic: Mapping[str, Any] | None
    reason: str


@dataclass(slots=True)
class _DiagnosticRecord:
    generation: int
    diagnostic: dict[str, Any]
    state: ShadowComparisonState
    divergence: WorkflowDivergence | None


class WorkflowShadowEvaluator:
    """Thread-safe no-side-effect comparison registry for production soak."""

    def __init__(
        self,
        *,
        mode: str = "off",
        evaluator: Callable[..., WorkDecision] = evaluate_task,
        max_diagnostic_bytes: int = DEFAULT_MAX_DIAGNOSTIC_BYTES,
    ) -> None:
        self._mode = normalize_workflow_engine_mode(mode)
        self._evaluator = evaluator
        if max_diagnostic_bytes < 1024:
            raise ValueError("max_diagnostic_bytes must be at least 1024")
        self.max_diagnostic_bytes = int(max_diagnostic_bytes)
        self._lock = threading.RLock()
        self._records: dict[tuple[str, str], _DiagnosticRecord] = {}
        self._listeners: list[Callable[[Mapping[str, Any]], None]] = []
        self._evaluated_count = 0
        self._stale_rejected_count = 0
        self._resolved_count = 0
        self._last_evaluated_at: str | None = None

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str) -> None:
        normalized = normalize_workflow_engine_mode(mode)
        with self._lock:
            self._mode = normalized

    def add_listener(self, listener: Callable[[Mapping[str, Any]], None]) -> None:
        if not callable(listener):
            raise TypeError("listener must be callable")
        with self._lock:
            self._listeners.append(listener)

    @staticmethod
    def _mismatches(
        decision: WorkDecision,
        projections: Sequence[LegacyWorkflowProjection],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        decision_values = {
            "status": decision.status,
            "disposition": decision.disposition.value,
            "owner": decision.responsible_owner.value,
            "reason_code": decision.reason_code,
            "permitted_actions": [
                action.value for action in decision.permitted_actions
            ],
            "recommended_status": decision.recommended_status,
        }
        for projection in projections:
            legacy_values = projection.to_dict()
            fields: dict[str, dict[str, Any]] = {}
            for field_name, decision_value in decision_values.items():
                legacy_value = legacy_values[field_name]
                if legacy_value is not None and legacy_value != decision_value:
                    fields[field_name] = {
                        "legacy": legacy_value,
                        "decision": decision_value,
                    }
            if fields:
                result[projection.consumer] = fields
        return result

    def evaluate(
        self,
        task: Issue | Mapping[str, Any],
        facts: WorkflowFacts,
        projections: Sequence[LegacyWorkflowProjection],
        *,
        snapshot_generation: int,
        now: datetime | None = None,
    ) -> ShadowEvaluationResult:
        """Evaluate and compare without invoking any mutation-capable object."""

        if isinstance(snapshot_generation, bool) or snapshot_generation < 0:
            raise ValueError("snapshot_generation must be a nonnegative integer")
        generation = int(snapshot_generation)
        with self._lock:
            if self._mode == "off":
                return ShadowEvaluationResult(
                    False, False, None, None, "workflow shadow evaluation is off"
                )
        decision = self._evaluator(task, facts, now=now)
        legacy = tuple(projections)
        if any(not isinstance(item, LegacyWorkflowProjection) for item in legacy):
            raise TypeError("projections must contain LegacyWorkflowProjection values")
        mismatches = self._mismatches(decision, legacy)
        state = (
            ShadowComparisonState.DIVERGED
            if mismatches
            else ShadowComparisonState.ALIGNED
        )
        observed_at = _now_iso()
        key = (facts.project_id, facts.task_id)
        listeners: tuple[Callable[[Mapping[str, Any]], None], ...] = ()
        with self._lock:
            previous = self._records.get(key)
            if previous is not None and generation < previous.generation:
                self._stale_rejected_count += 1
                return ShadowEvaluationResult(
                    False,
                    False,
                    previous.state,
                    dict(previous.diagnostic),
                    "stale snapshot generation rejected",
                )

            divergence: WorkflowDivergence | None = None
            if mismatches:
                fingerprint = _digest(
                    {
                        "project_id": facts.project_id,
                        "task_id": facts.task_id,
                        "mismatches": mismatches,
                    }
                )
                prior_divergence = previous.divergence if previous else None
                if prior_divergence and prior_divergence.fingerprint == fingerprint:
                    first = prior_divergence.first_observed_at
                    count = prior_divergence.observation_count + 1
                else:
                    first = observed_at
                    count = 1
                divergence = WorkflowDivergence(
                    fingerprint=fingerprint,
                    project_id=facts.project_id,
                    task_id=facts.task_id,
                    mismatches=mismatches,
                    first_observed_at=first,
                    last_observed_at=observed_at,
                    observation_count=count,
                    snapshot_generation=generation,
                    facts_version=facts.facts_version,
                    decision_revision=decision.decision_revision,
                )
            elif previous and previous.divergence is not None:
                self._resolved_count += 1

            raw_diagnostic = {
                "project_id": facts.project_id,
                "task_id": facts.task_id,
                "snapshot_generation": generation,
                "evaluated_at": observed_at,
                "state": state.value,
                "facts_version": facts.facts_version,
                "decision_revision": decision.decision_revision,
                "facts": facts.to_dict(),
                "decision": decision.to_dict(),
                "legacy": [item.to_dict() for item in legacy],
                "divergence": divergence.to_dict() if divergence else None,
            }
            diagnostic = _safe_diagnostic(raw_diagnostic, self.max_diagnostic_bytes)
            semantic_before = (
                (
                    previous.state.value,
                    previous.divergence.fingerprint if previous.divergence else None,
                )
                if previous
                else None
            )
            semantic_after = (
                state.value,
                divergence.fingerprint if divergence else None,
            )
            changed = semantic_before != semantic_after
            self._records[key] = _DiagnosticRecord(
                generation, diagnostic, state, divergence
            )
            self._evaluated_count += 1
            self._last_evaluated_at = observed_at
            if changed:
                listeners = tuple(self._listeners)
            summary = self._summary_locked()
        for listener in listeners:
            try:
                listener(summary)
            except Exception:
                pass
        return ShadowEvaluationResult(
            True,
            changed,
            state,
            dict(diagnostic),
            "shadow comparison recorded",
        )

    def diagnostic(self, project_id: str, task_id: str) -> dict[str, Any] | None:
        key = (
            _required_text(project_id, "project_id"),
            _required_text(task_id, "task_id"),
        )
        with self._lock:
            record = self._records.get(key)
            return deepcopy(record.diagnostic) if record else None

    def diagnostics(
        self,
        *,
        project_id: str | None = None,
        divergent_only: bool = False,
        limit: int = DEFAULT_DIAGNOSTIC_LIMIT,
    ) -> tuple[dict[str, Any], ...]:
        bounded = _bounded_limit(limit)
        with self._lock:
            records = [
                (key, record)
                for key, record in self._records.items()
                if (project_id is None or key[0] == project_id)
                and (not divergent_only or record.divergence is not None)
            ]
            records.sort(key=lambda item: item[0])
            return tuple(deepcopy(record.diagnostic) for _, record in records[:bounded])

    def _summary_locked(self) -> dict[str, Any]:
        per_consumer: dict[str, int] = {}
        divergent = 0
        for record in self._records.values():
            if record.divergence is None:
                continue
            divergent += 1
            for consumer in record.divergence.mismatches:
                per_consumer[consumer] = per_consumer.get(consumer, 0) + 1
        return {
            "mode": self._mode,
            "evaluated_count": self._evaluated_count,
            "tracked_task_count": len(self._records),
            "divergence_count": divergent,
            "resolved_count": self._resolved_count,
            "stale_rejected_count": self._stale_rejected_count,
            "last_evaluated_at": self._last_evaluated_at,
            "divergences_by_consumer": dict(sorted(per_consumer.items())),
        }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return self._summary_locked()
