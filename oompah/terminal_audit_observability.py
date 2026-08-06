"""Metrics and actionable health signals for terminal-audit work.

The audit records remain the source of truth for lifecycle decisions.  This
module deliberately keeps only small, non-sensitive identities and timestamps
so the dashboard can answer two operational questions without inspecting
tracker metadata: is validation making progress, and which audit needs an
operator?
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from threading import RLock
from typing import Any

from oompah.validation_resource_lease import is_focused_validation_command


logger = logging.getLogger(__name__)

METRICS_STATE_KEY = "terminal_audit_metrics"
METRICS_STATE_VERSION = 1

COUNTER_NAMES = (
    "passed",
    "failed",
    "retried",
    "stale_discarded",
    "overridden",
    "grandfathered",
    "no_independent_candidate",
)

VALIDATION_COUNTER_NAMES = (
    "authoritative_gate_reused",
    "full_gate_required",
    "focused_supplemental_commands",
    "auditor_full_suite_runs",
    "validation_commands_started",
    "validation_commands_completed",
    "validation_commands_failed",
    "validation_commands_timed_out",
    "reused_gate_validation_denied",
    "reused_gate_distinct_mode_allowed",
    "reused_gate_became_required",
)


def utc_now() -> datetime:
    """Return an aware UTC clock value; callers may inject a deterministic clock."""

    return datetime.now(timezone.utc)


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        value = utc_now()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("audit timestamp must be a non-empty string or datetime")
    return value


def _parse_timestamp(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _identity(project_id: Any, task_id: Any, audit_id: Any) -> tuple[str, str, str]:
    values = (project_id, task_id, audit_id)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("project_id, task_id, and audit_id must be non-empty strings")
    return tuple(value.strip() for value in values)  # type: ignore[return-value]


def _identity_dict(key: tuple[str, str, str]) -> dict[str, str]:
    return {"project_id": key[0], "task_id": key[1], "audit_id": key[2]}


def _synchronized(method):
    """Serialize metric updates from the scheduler and async API loops."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


@dataclass(frozen=True)
class AuditAlertCondition:
    """One actionable condition keyed at project/task/audit granularity."""

    kind: str
    project_id: str
    task_id: str
    audit_id: str
    message: str
    action: str
    level: str = "error"

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.kind, self.project_id, self.task_id, self.audit_id)

    @property
    def source(self) -> str:
        kind, project_id, task_id, audit_id = self.key
        return f"terminal_audit:{kind}:{project_id}:{task_id}:{audit_id}"

    def to_alert(self) -> dict[str, str]:
        return {
            "level": self.level,
            "source": self.source,
            "title": "Terminal audit requires attention",
            "message": self.message,
            "action": self.action,
        }


class TerminalAuditAlertRegistry:
    """Deduplicate terminal-audit alerts and remove recovered conditions."""

    def __init__(self) -> None:
        self._conditions: dict[tuple[str, str, str, str], AuditAlertCondition] = {}

    @property
    def conditions(self) -> tuple[AuditAlertCondition, ...]:
        return tuple(self._conditions.values())

    def sync(self, conditions: Iterable[AuditAlertCondition]) -> list[dict[str, str]]:
        desired = {condition.key: condition for condition in conditions}
        self._conditions = desired
        return [condition.to_alert() for condition in desired.values()]

    def add(self, condition: AuditAlertCondition) -> dict[str, str]:
        self._conditions[condition.key] = condition
        return condition.to_alert()

    def clear(
        self,
        project_id: str,
        task_id: str,
        audit_id: str,
        *,
        kind: str | None = None,
    ) -> None:
        self._conditions = {
            key: value
            for key, value in self._conditions.items()
            if not (
                key[1] == project_id
                and key[2] == task_id
                and key[3] == audit_id
                and (kind is None or key[0] == kind)
            )
        }


class TerminalAuditMetrics:
    """Durable audit counters/gauges with a deterministic clock seam.

    ``queued`` and ``running`` are gauges.  The remaining named lifecycle
    values are monotonic counters, except ``grandfathered`` and
    ``no_independent_candidate`` which are counted once per audit identity.
    ``queued_total`` is included alongside the queue gauge for throughput
    dashboards that need the number of requests ever admitted.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = utc_now,
        load_state: Callable[[], Mapping[str, Any]] | None = None,
        save_state: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.clock = clock
        self._lock = RLock()
        self._load_state = load_state
        self._save_state = save_state
        self._counters = {name: 0 for name in COUNTER_NAMES}
        self._validation_counters = {
            name: 0 for name in VALIDATION_COUNTER_NAMES
        }
        self._queued_total = 0
        self._project_counters: dict[str, dict[str, int]] = {}
        self._queued: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._running: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._seen: dict[str, set[tuple[str, str, str]]] = {
            name: set()
            for name in (
                "stale_discarded",
                "grandfathered",
                "no_independent_candidate",
            )
        }
        self._no_candidate: dict[tuple[str, str, str], str] = {}
        self._last_successful_audit_at: str | None = None
        self._last_validation_decision: dict[str, Any] | None = None
        self._last_validation_command: dict[str, Any] | None = None
        self._last_validation_reuse_policy: dict[str, Any] | None = None
        self._validation_reuse_policy_invocations: dict[str, dict[str, str]] = {}
        self._validation_commands_in_flight: dict[str, dict[str, Any]] = {}
        self._completed_validation_invocations: set[str] = set()
        self.persistence_corrupt = False
        self.persistence_error: str | None = None
        self._restore()

    def _root(self) -> Mapping[str, Any]:
        if self._load_state is None:
            return {}
        raw = self._load_state()
        if not isinstance(raw, Mapping):
            raise ValueError("service state root must be a mapping")
        return raw

    def _restore(self) -> None:
        try:
            raw = self._root().get(METRICS_STATE_KEY)
            if raw is None:
                return
            if not isinstance(raw, Mapping) or raw.get("version") != METRICS_STATE_VERSION:
                raise ValueError("unsupported terminal-audit metrics version")
            counters = raw.get("counters", {})
            if not isinstance(counters, Mapping):
                raise ValueError("terminal-audit metrics counters must be a mapping")
            for name in COUNTER_NAMES:
                value = counters.get(name, 0)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"invalid terminal-audit metric counter: {name}")
                self._counters[name] = value
            queued_total = raw.get("queued_total", 0)
            if isinstance(queued_total, bool) or not isinstance(queued_total, int) or queued_total < 0:
                raise ValueError("invalid terminal-audit queued_total")
            self._queued_total = queued_total
            raw_projects = raw.get("project_counters", {})
            if not isinstance(raw_projects, Mapping):
                raise ValueError("terminal-audit project counters must be a mapping")
            for project_id, values in raw_projects.items():
                if not isinstance(project_id, str) or not isinstance(values, Mapping):
                    raise ValueError("invalid terminal-audit project counter")
                project = {
                    name: 0
                    for name in (
                        *COUNTER_NAMES,
                        *VALIDATION_COUNTER_NAMES,
                        "queued_total",
                    )
                }
                for name, value in values.items():
                    if (
                        name not in project
                        or isinstance(value, bool)
                        or not isinstance(value, int)
                        or value < 0
                    ):
                        raise ValueError("invalid terminal-audit project counter value")
                    project[name] = value
                self._project_counters[project_id] = project
            self._queued = self._decode_entries(raw.get("queued", []))
            self._running = self._decode_entries(raw.get("running", []))
            for name in self._seen:
                values = raw.get("seen", {}).get(name, []) if isinstance(raw.get("seen"), Mapping) else []
                if not isinstance(values, list):
                    raise ValueError(f"invalid terminal-audit seen set: {name}")
                if not all(isinstance(item, Mapping) for item in values):
                    raise ValueError(f"invalid terminal-audit seen item: {name}")
                self._seen[name] = {
                    _identity(item.get("project_id"), item.get("task_id"), item.get("audit_id"))
                    for item in values
                }
            raw_no_candidate = raw.get("no_candidate", [])
            if not isinstance(raw_no_candidate, list):
                raise ValueError("invalid terminal-audit no-candidate entries")
            for item in raw_no_candidate:
                if not isinstance(item, Mapping) or not isinstance(item.get("reason", ""), str):
                    raise ValueError("invalid terminal-audit no-candidate entry")
                key = _identity(item.get("project_id"), item.get("task_id"), item.get("audit_id"))
                self._no_candidate[key] = item.get("reason", "no eligible candidate")
            last_success = raw.get("last_successful_audit_at")
            if last_success is not None:
                if not isinstance(last_success, str) or _parse_timestamp(last_success) is None:
                    raise ValueError("invalid terminal-audit last successful timestamp")
                self._last_successful_audit_at = last_success
            validation = raw.get("validation", {})
            if validation is not None:
                if not isinstance(validation, Mapping):
                    raise ValueError("invalid terminal-audit validation metrics")
                validation_counters = validation.get("counters", {})
                if not isinstance(validation_counters, Mapping):
                    raise ValueError("invalid terminal-audit validation counters")
                for name in VALIDATION_COUNTER_NAMES:
                    value = validation_counters.get(name, 0)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or value < 0
                    ):
                        raise ValueError(
                            f"invalid terminal-audit validation counter: {name}"
                        )
                    self._validation_counters[name] = value
                for field_name, destination in (
                    ("last_decision", "_last_validation_decision"),
                    ("last_command", "_last_validation_command"),
                    ("last_reuse_policy", "_last_validation_reuse_policy"),
                ):
                    value = validation.get(field_name)
                    if value is not None and not isinstance(value, Mapping):
                        raise ValueError(
                            f"invalid terminal-audit validation {field_name}"
                        )
                    setattr(self, destination, dict(value) if value is not None else None)
                policy_invocations = validation.get("reuse_policy_invocations", {})
                if not isinstance(policy_invocations, Mapping):
                    raise ValueError(
                        "invalid terminal-audit validation reuse-policy invocations"
                    )
                for invocation_id, value in policy_invocations.items():
                    if (
                        not isinstance(invocation_id, str)
                        or not invocation_id.strip()
                        or not isinstance(value, Mapping)
                    ):
                        raise ValueError(
                            "invalid terminal-audit validation reuse-policy invocation"
                        )
                    row = {str(name): str(item) for name, item in value.items()}
                    _identity(
                        row.get("project_id"),
                        row.get("task_id"),
                        row.get("audit_id"),
                    )
                    if not row.get("attempt_id") or not row.get("decision"):
                        raise ValueError(
                            "incomplete terminal-audit validation reuse-policy invocation"
                        )
                    self._validation_reuse_policy_invocations[invocation_id] = row
                in_flight = validation.get("in_flight", {})
                if not isinstance(in_flight, Mapping):
                    raise ValueError("invalid terminal-audit validation in-flight map")
                for invocation_id, value in in_flight.items():
                    if (
                        not isinstance(invocation_id, str)
                        or not invocation_id.strip()
                        or not isinstance(value, Mapping)
                    ):
                        raise ValueError(
                            "invalid terminal-audit validation in-flight entry"
                        )
                    row = dict(value)
                    _identity(
                        row.get("project_id"),
                        row.get("task_id"),
                        row.get("audit_id"),
                    )
                    category = row.get("category")
                    if category not in {
                        "auditor_full_suite_runs",
                        "focused_supplemental_commands",
                    }:
                        raise ValueError(
                            "invalid terminal-audit validation in-flight category"
                        )
                    self._validation_commands_in_flight[invocation_id] = row
                completed = validation.get("completed_invocations", [])
                if (
                    not isinstance(completed, list)
                    or not all(
                        isinstance(value, str) and value.strip()
                        for value in completed
                    )
                ):
                    raise ValueError(
                        "invalid terminal-audit completed validation invocations"
                    )
                self._completed_validation_invocations = set(completed)
        except Exception as exc:  # fail closed; never overwrite an unknown state document
            self.persistence_corrupt = True
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            logger.error("terminal-audit metrics persistence is corrupt: %s", exc)

    @staticmethod
    def _decode_entries(raw: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
        if not isinstance(raw, list):
            raise ValueError("terminal-audit metric entries must be a list")
        result: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("terminal-audit metric entry must be a mapping")
            key = _identity(item.get("project_id"), item.get("task_id"), item.get("audit_id"))
            queued_at = item.get("queued_at")
            if queued_at is not None and _parse_timestamp(queued_at) is None:
                raise ValueError("invalid terminal-audit queue timestamp")
            attempts = item.get("attempts", 0)
            if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
                raise ValueError("invalid terminal-audit attempt count")
            result[key] = {"queued_at": queued_at, "attempts": attempts}
        return result

    def _persist(self) -> None:
        if self.persistence_corrupt or self._save_state is None:
            return
        payload = {
            "version": METRICS_STATE_VERSION,
            "counters": dict(self._counters),
            "queued_total": self._queued_total,
            "project_counters": copy.deepcopy(self._project_counters),
            "queued": [dict(_identity_dict(key), **value) for key, value in self._queued.items()],
            "running": [dict(_identity_dict(key), **value) for key, value in self._running.items()],
            "seen": {
                name: [_identity_dict(key) for key in sorted(values)]
                for name, values in self._seen.items()
            },
            "no_candidate": [
                dict(_identity_dict(key), reason=reason)
                for key, reason in self._no_candidate.items()
            ],
            "last_successful_audit_at": self._last_successful_audit_at,
            "validation": {
                "counters": dict(self._validation_counters),
                "last_decision": copy.deepcopy(self._last_validation_decision),
                "last_command": copy.deepcopy(self._last_validation_command),
                "last_reuse_policy": copy.deepcopy(
                    self._last_validation_reuse_policy
                ),
                "reuse_policy_invocations": copy.deepcopy(
                    self._validation_reuse_policy_invocations
                ),
                "in_flight": copy.deepcopy(self._validation_commands_in_flight),
                "completed_invocations": sorted(
                    self._completed_validation_invocations
                ),
            },
        }
        try:
            self._save_state({METRICS_STATE_KEY: payload})
        except Exception as exc:  # metrics must not break the audit lane
            logger.warning("failed to persist terminal-audit metrics: %s", exc)

    def _entry(
        self,
        key: tuple[str, str, str],
        value: datetime | str | None,
        attempts: int,
    ) -> dict[str, Any]:
        del key  # the identity is stored by the surrounding mapping
        return {
            "queued_at": _timestamp(value if value is not None else self.clock()),
            "attempts": max(0, int(attempts)),
        }

    def _project(self, project_id: str) -> dict[str, int]:
        return self._project_counters.setdefault(
            project_id,
            {
                name: 0
                for name in (
                    *COUNTER_NAMES,
                    *VALIDATION_COUNTER_NAMES,
                    "queued_total",
                )
            },
        )

    def _increment(self, name: str, key: tuple[str, str, str]) -> None:
        self._counters[name] += 1
        self._project(key[0])[name] += 1

    def _increment_validation(self, name: str, project_id: str) -> None:
        self._validation_counters[name] += 1
        project = self._project(project_id)
        project[name] = project.get(name, 0) + 1

    @_synchronized
    def record_quality_gate_decision(
        self,
        project_id: str,
        task_id: str,
        audit_id: str,
        *,
        decision: str,
        result: str,
        head_sha: str = "",
        command: str = "",
        duration_seconds: float | None = None,
    ) -> None:
        """Persist the dispatch decision made from exact-head gate evidence."""

        key = _identity(project_id, task_id, audit_id)
        decision = str(decision or "").strip()
        if decision == "reuse_authoritative_gate":
            self._increment_validation("authoritative_gate_reused", key[0])
        elif decision == "full_gate_required":
            self._increment_validation("full_gate_required", key[0])
        self._last_validation_decision = {
            **_identity_dict(key),
            "decision": decision,
            "result": str(result or "").strip(),
            "head_sha": str(head_sha or "").strip().lower(),
            "command": str(command or "").strip(),
            "duration_seconds": duration_seconds,
            "recorded_at": _timestamp(self.clock()),
        }
        self._persist()

    @_synchronized
    def record_auditor_validation_command(
        self,
        project_id: str,
        task_id: str,
        audit_id: str,
        *,
        command: str,
        configured_command: str,
        duration_seconds: float = 0.0,
        succeeded: bool = True,
        phase: str = "completed",
        outcome: str = "",
        invocation_id: str = "",
    ) -> None:
        """Persist one auditor validation lifecycle observation.

        New callers report ``started`` and ``completed`` with a stable
        invocation id.  The default completed-only form remains compatible
        with older callers and is counted as one complete invocation.
        """

        key = _identity(project_id, task_id, audit_id)
        command = str(command or "").strip()
        phase = str(phase or "").strip().casefold()
        if phase not in {"started", "completed"}:
            raise ValueError("validation command phase must be started or completed")
        invocation_id = str(invocation_id or "").strip()
        category = (
            "focused_supplemental_commands"
            if is_focused_validation_command(command)
            else "auditor_full_suite_runs"
        )
        prior = self._validation_commands_in_flight.get(invocation_id)
        if invocation_id and invocation_id in self._completed_validation_invocations:
            return
        if prior is not None and (
            tuple(prior.get(name) for name in ("project_id", "task_id", "audit_id"))
            != key
            or prior.get("command") != command
        ):
            raise ValueError("validation invocation identity changed in flight")
        if phase == "started":
            if not invocation_id:
                raise ValueError("started validation command requires invocation_id")
            if prior is None:
                self._increment_validation(category, key[0])
                self._increment_validation("validation_commands_started", key[0])
                self._validation_commands_in_flight[invocation_id] = {
                    **_identity_dict(key),
                    "category": category,
                    "command": command,
                    "started_at": _timestamp(self.clock()),
                }
            elif prior.get("category") != category:
                raise ValueError("validation invocation identity changed in flight")
            normalized_outcome = "running"
        else:
            if prior is None:
                # Completed-only callers predate lifecycle observations. Count
                # their one report as both initiation and completion.
                self._increment_validation(category, key[0])
                self._increment_validation("validation_commands_started", key[0])
            else:
                category = str(prior["category"])
                self._validation_commands_in_flight.pop(invocation_id, None)
            self._increment_validation("validation_commands_completed", key[0])
            normalized_outcome = str(outcome or "").strip().casefold()
            if not normalized_outcome:
                normalized_outcome = "passed" if succeeded else "failed"
            if normalized_outcome == "timed_out":
                self._increment_validation("validation_commands_timed_out", key[0])
            elif not succeeded:
                self._increment_validation("validation_commands_failed", key[0])
            if invocation_id:
                self._completed_validation_invocations.add(invocation_id)
                if len(self._completed_validation_invocations) > 512:
                    self._completed_validation_invocations = set(
                        sorted(self._completed_validation_invocations)[-512:]
                    )
        self._last_validation_command = {
            **_identity_dict(key),
            "category": category,
            "command": command,
            "phase": phase,
            "outcome": normalized_outcome,
            "invocation_id": invocation_id,
            "succeeded": bool(succeeded),
            "duration_seconds": max(float(duration_seconds or 0), 0.0),
            "recorded_at": _timestamp(self.clock()),
        }
        self._persist()

    @_synchronized
    def record_validation_reuse_policy(
        self,
        project_id: str,
        task_id: str,
        audit_id: str,
        *,
        attempt_id: str,
        invocation_id: str,
        command: str,
        decision: str,
        justification: str = "",
    ) -> None:
        """Persist one tool-layer decision for previously reusable gate proof."""

        key = _identity(project_id, task_id, audit_id)
        invocation_id = str(invocation_id or "").strip()
        if not invocation_id:
            raise ValueError("validation reuse policy requires invocation_id")
        attempt_id = str(attempt_id or "").strip()
        if not attempt_id:
            raise ValueError("validation reuse policy requires attempt_id")
        decision = str(decision or "").strip().casefold()
        if decision == "allowed_distinct_mode":
            counter = "reused_gate_distinct_mode_allowed"
        elif decision == "allowed_gate_now_required":
            counter = "reused_gate_became_required"
        elif decision.startswith("denied_"):
            counter = "reused_gate_validation_denied"
        else:
            raise ValueError("unsupported validation reuse policy decision")
        invocation = {
            **_identity_dict(key),
            "attempt_id": attempt_id,
            "command": str(command or "").strip(),
            "decision": decision,
            "justification": str(justification or ""),
        }
        prior = self._validation_reuse_policy_invocations.get(invocation_id)
        if prior is not None:
            if prior != invocation:
                raise ValueError(
                    "validation reuse policy invocation identity collision"
                )
            return
        self._increment_validation(counter, key[0])
        self._last_validation_reuse_policy = {
            **_identity_dict(key),
            "attempt_id": attempt_id,
            "invocation_id": invocation_id,
            "command": invocation["command"],
            "decision": decision,
            "justification": invocation["justification"],
            "recorded_at": _timestamp(self.clock()),
        }
        self._validation_reuse_policy_invocations[invocation_id] = invocation
        if len(self._validation_reuse_policy_invocations) > 512:
            oldest = next(iter(self._validation_reuse_policy_invocations))
            self._validation_reuse_policy_invocations.pop(oldest, None)
        self._persist()

    @_synchronized
    def record_queued(
        self,
        project_id: str,
        task_id: str,
        audit_id: str,
        *,
        queued_at: datetime | str | None = None,
        attempts: int = 0,
    ) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._no_candidate.pop(key, None)
        entry = self._queued.get(key) or self._running.pop(key, None)
        if entry is None:
            self._queued_total += 1
            self._project(key[0])["queued_total"] += 1
            entry = self._entry(key, queued_at, attempts)
        self._queued[key] = entry
        self._queued[key]["attempts"] = max(entry["attempts"], attempts)
        self._persist()

    @_synchronized
    def record_running(self, project_id: str, task_id: str, audit_id: str, *, attempts: int = 0) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._no_candidate.pop(key, None)
        if key in self._running:
            self._running[key]["attempts"] = max(self._running[key].get("attempts", 0), attempts)
            self._persist()
            return
        entry = self._queued.pop(key, None) or self._entry(key, None, attempts)
        entry["attempts"] = max(entry.get("attempts", 0), attempts)
        self._running[key] = entry
        self._persist()

    @_synchronized
    def discard_missing_running(self, live_keys: Iterable[tuple[str, str, str]]) -> None:
        """Count auditor launches no longer owned by a live worker as stale."""

        live = set(live_keys)
        for key in tuple(self._running):
            if key not in live:
                self._finish(key)
                self._count_once("stale_discarded", key)
        self._persist()

    def _finish(self, key: tuple[str, str, str]) -> None:
        self._queued.pop(key, None)
        self._running.pop(key, None)
        self._no_candidate.pop(key, None)

    def _count_once(self, name: str, key: tuple[str, str, str]) -> None:
        if key not in self._seen[name]:
            self._seen[name].add(key)
            self._increment(name, key)

    @_synchronized
    def record_passed(self, project_id: str, task_id: str, audit_id: str, *, completed_at: datetime | str | None = None) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._finish(key)
        self._increment("passed", key)
        self._last_successful_audit_at = _timestamp(completed_at)
        self._persist()

    @_synchronized
    def record_failed(self, project_id: str, task_id: str, audit_id: str) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._finish(key)
        self._increment("failed", key)
        self._persist()

    @_synchronized
    def record_retried(self, project_id: str, task_id: str, audit_id: str, *, attempts: int | None = None) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._no_candidate.pop(key, None)
        self._increment("retried", key)
        entry = self._running.pop(key, None) or self._queued.get(key) or self._entry(key, None, 0)
        entry["attempts"] = max(entry.get("attempts", 0) + 1, attempts or 0)
        self._queued[key] = entry
        self._persist()

    @_synchronized
    def record_stale_discarded(self, project_id: str, task_id: str, audit_id: str) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._finish(key)
        self._count_once("stale_discarded", key)
        self._persist()

    @_synchronized
    def record_overridden(self, project_id: str, task_id: str, audit_id: str) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._finish(key)
        self._increment("overridden", key)
        self._persist()

    @_synchronized
    def record_grandfathered(self, project_id: str, task_id: str, audit_id: str) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._count_once("grandfathered", key)
        self._persist()

    @_synchronized
    def record_no_independent_candidate(self, project_id: str, task_id: str, audit_id: str) -> None:
        key = _identity(project_id, task_id, audit_id)
        self._finish(key)
        self._count_once("no_independent_candidate", key)
        self._no_candidate[key] = "no eligible independent auditor candidate"
        self._persist()

    @_synchronized
    def clear_actionable_alert(self, project_id: str, task_id: str, audit_id: str) -> None:
        """Forget a no-candidate condition after an operator fixes it."""

        key = _identity(project_id, task_id, audit_id)
        self._no_candidate.pop(key, None)
        self._persist()

    @_synchronized
    def sync_pending(self, entries: Iterable[Any]) -> None:
        """Mirror only live, metadata-backed audit records.

        Enforcement persistence is a restart cache; it is not evidence that a
        task can still be dispatched.  Callers normally provide a reconciled
        set, but filtering here as well prevents a stale cache row from
        resurrecting a completed, superseded, or overridden queue gauge.
        """

        observed: set[tuple[str, str, str]] = set()
        for entry in entries:
            project_id = getattr(entry, "project_id", None)
            task_id = getattr(entry, "task_id", None)
            audit_id = getattr(entry, "audit_id", None)
            if project_id is None and isinstance(entry, Mapping):
                project_id, task_id, audit_id = (entry.get(name) for name in ("project_id", "task_id", "audit_id"))
            record = getattr(entry, "record", None)
            if record is None and isinstance(entry, Mapping):
                record = entry.get("record")
            request_state = getattr(record, "request_state", None)
            if request_state is None and isinstance(record, Mapping):
                request_state = record.get("request_state")
            request_state = str(getattr(request_state, "value", request_state))
            if request_state not in {"pending", "in_progress"}:
                continue
            record_project_id = getattr(record, "project_id", project_id)
            record_task_id = getattr(record, "task_id", task_id)
            record_audit_id = getattr(record, "audit_id", audit_id)
            if isinstance(record, Mapping):
                record_project_id = record.get("project_id", record_project_id)
                record_task_id = record.get("task_id", record_task_id)
                record_audit_id = record.get("audit_id", record_audit_id)
            key = _identity(project_id, task_id, audit_id)
            if (record_project_id, record_task_id, record_audit_id) != key:
                continue
            observed.add(key)
            if request_state == "in_progress":
                self.record_running(*key, attempts=len(getattr(record, "attempts", ()) or ()))
            else:
                self.record_queued(*key, attempts=len(getattr(record, "attempts", ()) or ()))
        for key in set(self._queued) | set(self._running):
            if key not in observed:
                self._finish(key)
        self._persist()

    @_synchronized
    def snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or self.clock()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        queue_times = [(_parse_timestamp(item.get("queued_at")), key) for key, item in self._queued.items()]
        queue_times = [(value, key) for value, key in queue_times if value is not None]
        oldest = min(queue_times, default=(None, None), key=lambda pair: pair[0] or current)
        oldest_at, oldest_key = oldest
        age = max(0.0, (current - oldest_at).total_seconds()) if oldest_at else 0.0
        projects: dict[str, dict[str, int]] = copy.deepcopy(self._project_counters)
        for project_id, task_id, audit_id in set(self._queued) | set(self._running):
            project = projects.setdefault(
                project_id,
                {
                    name: 0
                    for name in (
                        *COUNTER_NAMES,
                        *VALIDATION_COUNTER_NAMES,
                        "queued_total",
                    )
                },
            )
            project.setdefault("queued", 0)
            project.setdefault("running", 0)
            if (project_id, task_id, audit_id) in self._queued:
                project["queued"] += 1
            if (project_id, task_id, audit_id) in self._running:
                project["running"] += 1
        result: dict[str, Any] = {
            "queued": len(self._queued),
            "running": len(self._running),
            "queued_total": self._queued_total,
            **self._counters,
            "oldest_queue_age_seconds": round(age, 3),
            "oldest_queue_age": round(age, 3),
            "oldest_queued_at": oldest_at.isoformat() if oldest_at else None,
            "oldest_queue_project_id": oldest_key[0] if oldest_key else None,
            "oldest_queue_task_id": oldest_key[1] if oldest_key else None,
            "oldest_queue_audit_id": oldest_key[2] if oldest_key else None,
            "last_successful_audit_at": self._last_successful_audit_at,
            "last_successful_audit_time": self._last_successful_audit_at,
            "last_successful_audit": self._last_successful_audit_at,
            **self._validation_counters,
            "validation": {
                "counters": dict(self._validation_counters),
                "last_decision": copy.deepcopy(self._last_validation_decision),
                "last_command": copy.deepcopy(self._last_validation_command),
                "last_reuse_policy": copy.deepcopy(
                    self._last_validation_reuse_policy
                ),
                "reuse_policy_invocations": copy.deepcopy(
                    self._validation_reuse_policy_invocations
                ),
                "in_flight": copy.deepcopy(self._validation_commands_in_flight),
                "completed_invocations": sorted(
                    self._completed_validation_invocations
                ),
            },
            "persistence_corrupt": self.persistence_corrupt,
            "persistence_error": self.persistence_error,
            "projects": projects,
            "by_project": projects,
        }
        for name in (
            "queued",
            "running",
            *COUNTER_NAMES,
            *VALIDATION_COUNTER_NAMES,
        ):
            result[f"{name}_count"] = result[name]
        return copy.deepcopy(result)

    @_synchronized
    def pending_entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(_identity_dict(key), **value) for key, value in self._queued.items())

    @_synchronized
    def lifecycle_keys(self) -> tuple[tuple[str, str, str], ...]:
        """Return all identities that may need durable-state reconciliation."""

        return tuple(
            sorted(set(self._queued) | set(self._running) | set(self._no_candidate))
        )


# Readable compatibility names for callers that refer to this boundary as an
# audit metrics/observability store rather than by its concrete class name.
AuditMetrics = TerminalAuditMetrics
TerminalAuditObservability = TerminalAuditMetrics


def threshold_conditions(
    metrics: TerminalAuditMetrics,
    *,
    max_attempts: int,
    max_age_seconds: float,
) -> list[AuditAlertCondition]:
    """Build only actionable threshold/corruption conditions."""

    conditions: list[AuditAlertCondition] = []
    now = metrics.clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if metrics.persistence_corrupt:
        conditions.append(
            AuditAlertCondition(
                "persistence_corrupt", "service", "terminal-audit", "state",
                "Terminal-audit metrics persistence is corrupt; queue health cannot be trusted.",
                "Repair or restore the service state file, then restart oompah.",
            )
        )
    for (project_id, task_id, audit_id), reason in metrics._no_candidate.items():
        conditions.append(
            AuditAlertCondition(
                "no_independent_candidate",
                project_id,
                task_id,
                audit_id,
                f"No independent auditor candidate is available ({reason}).",
                "Configure a healthy auditor provider/model independent of the task contributors, then retry the audit.",
            )
        )
    for entry in metrics.pending_entries():
        queued_at = _parse_timestamp(entry.get("queued_at"))
        age = (now - queued_at).total_seconds() if queued_at else 0.0
        attempts = int(entry.get("attempts", 0))
        if attempts >= max_attempts:
            conditions.append(
                AuditAlertCondition(
                    "attempt_threshold", entry["project_id"], entry["task_id"], entry["audit_id"],
                    f"Audit has reached the configured attempt threshold ({attempts}/{max_attempts}).",
                    "Review the audit record and add or repair an independent auditor before retrying.",
                )
            )
        elif age >= max_age_seconds:
            conditions.append(
                AuditAlertCondition(
                    "age_threshold", entry["project_id"], entry["task_id"], entry["audit_id"],
                    f"Audit has been queued for {age:.0f}s, beyond the configured {max_age_seconds:.0f}s age threshold.",
                    "Check auditor health and queue capacity, then retry the audit.",
                )
            )
    return conditions


__all__ = [
    "AuditAlertCondition",
    "AuditMetrics",
    "COUNTER_NAMES",
    "VALIDATION_COUNTER_NAMES",
    "METRICS_STATE_KEY",
    "METRICS_STATE_VERSION",
    "TerminalAuditAlertRegistry",
    "TerminalAuditMetrics",
    "TerminalAuditObservability",
    "threshold_conditions",
    "utc_now",
]
