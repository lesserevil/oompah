"""Safe health aggregation for the terminal-audit dispatch lane.

This module deliberately consumes durable audit records rather than provider
or model messages.  It is used by the scheduler and API snapshot paths so an
operator can tell the difference between a healthy empty queue, a growing
backlog, and an auditor transport that cannot launch, without exposing the
underlying exception text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from oompah.terminal_audit import (
    AuditAttempt,
    FailureClassification,
    RequestState,
    TerminalAuditRecord,
)


DEFAULT_STALE_AFTER_SECONDS: int = 3600
HEALTH_ALERT_PREFIX: str = "terminal_audit_health:"


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp string into an aware UTC datetime."""
    if not isinstance(value, (str, datetime)):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    v = value.strip()
    if not v:
        return None
    try:
        parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _timestamp(value: datetime) -> str:
    """Serialize a datetime to a canonical ISO-8601 string."""
    return value.astimezone(timezone.utc).isoformat()


def _record_created_at(record: TerminalAuditRecord) -> datetime | None:
    """Return the oldest trustworthy timestamp for a pending request."""
    candidates: list[datetime] = []
    for attr in (record.created_at, record.updated_at):
        parsed = _parse_timestamp(attr)
        if parsed is not None:
            candidates.append(parsed)
    for attempt in record.attempts:
        for value in (attempt.started_at, attempt.created_at):
            parsed = _parse_timestamp(value)
            if parsed is not None:
                candidates.append(parsed)
    return min(candidates) if candidates else None


@dataclass(frozen=True)
class AuditHealthObservation:
    """One successful scan observation.

    ``record`` is ``None`` for an ``In Validation`` task with no usable
    pending audit metadata.  The latter is intentionally retained as a
    separate stale-validation signal instead of being silently treated as an
    empty queue.
    """

    project_id: str | None
    issue_identifier: str
    issue_created_at: datetime | str | None
    record: TerminalAuditRecord | None
    quarantined: bool = False
    # Durable result/intent failures are tracked separately from provider
    # transport and local auditor-policy failures.  A non-zero value means a
    # verdict was produced (or the finalization boundary was exhausted) but
    # the authoritative terminal status has not been acknowledged yet.
    finalization_failure_count: int = 0


@dataclass
class TerminalAuditHealth:
    """Redacted, serializable terminal-audit service health."""

    pending_count: int = 0
    in_progress_count: int = 0
    oldest_pending_at: str | None = None
    oldest_pending_age_seconds: int | None = None
    stale_pending_count: int = 0
    stale_in_validation_count: int = 0
    launch_failure_count: int = 0
    transport_failure_count: int = 0
    policy_incompatibility_count: int = 0
    finalization_failure_count: int = 0
    retry_exhausted_count: int = 0
    quarantined_count: int = 0
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS
    scan_complete: bool = True
    scan_error_count: int = 0
    projects: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def failure_count(self) -> int:
        return (
            self.launch_failure_count
            + self.transport_failure_count
            + self.policy_incompatibility_count
            + self.finalization_failure_count
        )

    @property
    def degraded(self) -> bool:
        return bool(
            self.launch_failure_count
            or self.transport_failure_count
            or self.policy_incompatibility_count
            or self.finalization_failure_count
            or self.stale_pending_count
            or self.stale_in_validation_count
            or self.retry_exhausted_count
            or self.quarantined_count
            or not self.scan_complete
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "pending_count": self.pending_count,
            "in_progress_count": self.in_progress_count,
            "oldest_pending_at": self.oldest_pending_at,
            "oldest_pending_age_seconds": self.oldest_pending_age_seconds,
            "stale_pending_count": self.stale_pending_count,
            "stale_in_validation_count": self.stale_in_validation_count,
            "launch_failure_count": self.launch_failure_count,
            "transport_failure_count": self.transport_failure_count,
            "policy_incompatibility_count": self.policy_incompatibility_count,
            "finalization_failure_count": self.finalization_failure_count,
            "failure_count": self.failure_count,
            "retry_exhausted_count": self.retry_exhausted_count,
            "quarantined_count": self.quarantined_count,
            "stale_after_seconds": self.stale_after_seconds,
            "scan_complete": self.scan_complete,
            "scan_error_count": self.scan_error_count,
            "degraded": self.degraded,
            "projects": {
                key: dict(value) for key, value in self.projects.items()
            },
        }
        return result

    @classmethod
    def from_dict(cls, raw: Any) -> "TerminalAuditHealth":
        """Load only the numeric/timestamp health fields from persisted state."""
        if not isinstance(raw, dict):
            return cls()
        integer_fields = (
            "pending_count",
            "in_progress_count",
            "oldest_pending_age_seconds",
            "stale_pending_count",
            "stale_in_validation_count",
            "launch_failure_count",
            "transport_failure_count",
            "policy_incompatibility_count",
            "finalization_failure_count",
            "retry_exhausted_count",
            "quarantined_count",
            "stale_after_seconds",
            "scan_error_count",
        )
        values: dict[str, Any] = {}
        for name in integer_fields:
            value = raw.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                values[name] = value
        oldest = raw.get("oldest_pending_age_seconds")
        if oldest is None:
            values["oldest_pending_at"] = raw.get("oldest_pending_at")
        values["scan_complete"] = bool(raw.get("scan_complete", True))
        projects_raw = raw.get("projects", {})
        projects: dict[str, dict[str, int]] = {}
        if isinstance(projects_raw, dict):
            for project, counts in projects_raw.items():
                if isinstance(counts, dict):
                    projects[str(project)] = {
                        str(key): int(value)
                        for key, value in counts.items()
                        if isinstance(value, int)
                    }
        values["projects"] = projects
        return cls(**values)


# Phrases that indicate launch-level (infrastructure-layer) failures in a
# persisted attempt's failure_reason.  These are intentionally narrow to
# avoid false-positives from task-level errors.  We classify without
# returning the text.
_LAUNCH_PHRASES: tuple[str, ...] = (
    "launch",
    "startup",
    "failed to start",
    "cli path",
    "not installed",
    "extension not available",
)

_TRANSPORT_PHRASES: tuple[str, ...] = (
    "transport",
    "connection",
    "timeout",
    "timed out",
    "rate limit",
    "provider",
    "network",
    "session",
    "crash",
    "abandoned",
    "no live worker",
)


def _failure_kind(attempt: AuditAttempt) -> str | None:
    """Classify a persisted failure without returning its reason."""
    reason = attempt.failure_reason or ""
    low = reason.lower()
    classification = attempt.failure_classification
    if classification == FailureClassification.NO_AUDITOR:
        return None
    if classification == FailureClassification.INFRASTRUCTURE_ERROR:
        return "transport"
    if classification == FailureClassification.POLICY_INCOMPATIBILITY:
        return "policy"
    if classification == FailureClassification.FINALIZATION_FAILURE:
        return "finalization"
    if any(phrase in low for phrase in _LAUNCH_PHRASES):
        return "launch"
    if any(phrase in low for phrase in _TRANSPORT_PHRASES):
        return "transport"
    return None


def _as_observation(value: Any) -> AuditHealthObservation:
    """Coerce a raw value to an AuditHealthObservation."""
    if isinstance(value, AuditHealthObservation):
        return value
    if isinstance(value, TerminalAuditRecord):
        raise TypeError("audit health observations must contain audit records")
    raise TypeError("audit health observations must contain audit records")


def build_terminal_audit_health(
    observations: Iterable[AuditHealthObservation | TerminalAuditRecord],
    now: datetime | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    max_attempts: int = 3,
    scan_complete: bool = True,
    scan_error_count: int = 0,
) -> TerminalAuditHealth:
    """Build current health from a successful or partially successful scan."""

    if stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds must be positive")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    pending = 0
    in_progress = 0
    stale_pending = 0
    stale_validation = 0
    launch_failures = 0
    transport_failures = 0
    policy_incompatibilities = 0
    finalization_failures = 0
    exhausted = 0
    quarantined = 0
    oldest: datetime | None = None
    projects: dict[str, dict[str, int]] = {}

    def increment(project: str | None, key: str, amount: int = 1) -> None:
        counts = projects.setdefault(str(project or ""), {})
        counts[key] = counts.get(key, 0) + amount

    for raw_observation in observations:
        if isinstance(raw_observation, TerminalAuditRecord):
            # Raw record — treat as a bare pending observation with no issue metadata
            record: TerminalAuditRecord | None = raw_observation
            observation = AuditHealthObservation(
                project_id=record.project_id,
                issue_identifier=record.task_id,
                issue_created_at=None,
                record=record,
            )
        else:
            observation = raw_observation
            record = observation.record

        if observation.finalization_failure_count:
            count = max(0, int(observation.finalization_failure_count))
            finalization_failures += count
            increment(
                observation.project_id,
                "finalization_failure_count",
                count,
            )

        if observation.quarantined:
            quarantined += 1
            increment(observation.project_id, "quarantined_count")
            continue

        if record is None:
            # In Validation task with no usable metadata — stale validation signal
            if observation.finalization_failure_count:
                # A completed verdict waiting for status acknowledgement is a
                # finalization failure, not missing audit metadata.
                continue
            issue_ts = _parse_timestamp(observation.issue_created_at)
            if issue_ts is not None:
                age = (current_time - issue_ts).total_seconds()
                if age >= stale_after_seconds:
                    stale_validation += 1
                    increment(observation.project_id, "stale_in_validation_count")
            else:
                stale_validation += 1
                increment(observation.project_id, "stale_in_validation_count")
            continue

        # Record-level counters
        if record.request_state == RequestState.IN_PROGRESS:
            in_progress += 1
            increment(observation.project_id, "in_progress_count")
        elif record.request_state == RequestState.PENDING:
            pending += 1
            increment(observation.project_id, "pending_count")

        # Age tracking — use the record's own timestamp if available
        record_ts = _record_created_at(record)
        issue_ts = _parse_timestamp(observation.issue_created_at)
        ts = record_ts or issue_ts
        if ts is not None:
            age_s = (current_time - ts).total_seconds()
            if age_s >= stale_after_seconds:
                stale_pending += 1
                increment(observation.project_id, "stale_pending_count")
            oldest = min(oldest, ts) if oldest is not None else ts

        # Failure classification — only count unresolved failures.
        #
        # A record in RequestState.IN_PROGRESS has an active auditor attempt
        # currently running; prior failures in that record are being recovered
        # automatically and must NOT surface as actionable alerts.  This
        # prevents stale transport/launch failures from appearing to describe
        # a task that is already retrying (or a later, unrelated task).
        #
        # Once the active attempt ends (record returns to PENDING), any
        # failures are counted again because operator attention may be needed.
        #
        # Retry exhaustion is also guarded: if the last attempt is still
        # IN_PROGRESS it has not yet failed, so the retry budget is not yet
        # consumed from an operator perspective.
        if record.request_state == RequestState.PENDING:
            attempts_used = len(record.attempts)
            if attempts_used >= max_attempts:
                exhausted += 1
                increment(observation.project_id, "retry_exhausted_count")

            for attempt in record.attempts:
                if attempt.request_state != RequestState.PENDING:
                    continue
                if not attempt.ended_at:
                    continue
                kind = _failure_kind(attempt)
                if kind == "launch":
                    launch_failures += 1
                    increment(observation.project_id, "launch_failure_count")
                elif kind == "transport":
                    transport_failures += 1
                    increment(observation.project_id, "transport_failure_count")
                elif kind == "policy":
                    policy_incompatibilities += 1
                    increment(observation.project_id, "policy_incompatibility_count")
                elif kind == "finalization":
                    finalization_failures += 1
                    increment(observation.project_id, "finalization_failure_count")

    oldest_at: str | None = _timestamp(oldest) if oldest is not None else None
    oldest_age: int | None = (
        int((current_time - oldest).total_seconds()) if oldest is not None else None
    )

    return TerminalAuditHealth(
        pending_count=pending,
        in_progress_count=in_progress,
        oldest_pending_at=oldest_at,
        oldest_pending_age_seconds=oldest_age,
        stale_pending_count=stale_pending,
        stale_in_validation_count=stale_validation,
        launch_failure_count=launch_failures,
        transport_failure_count=transport_failures,
        policy_incompatibility_count=policy_incompatibilities,
        finalization_failure_count=finalization_failures,
        retry_exhausted_count=exhausted,
        quarantined_count=quarantined,
        stale_after_seconds=stale_after_seconds,
        scan_complete=scan_complete,
        scan_error_count=scan_error_count,
        projects=projects,
    )


def terminal_audit_health_alerts(
    health: TerminalAuditHealth,
) -> list[dict[str, Any]]:
    """Return stable, redacted alerts for the current health facts."""

    alerts: list[dict[str, Any]] = []

    def add(
        source: str,
        level: str,
        title: str,
        detail: str,
        action: str,
    ) -> None:
        alerts.append(
            {
                "level": level,
                "severity": level,
                "source": HEALTH_ALERT_PREFIX + source,
                "stable_id": HEALTH_ALERT_PREFIX + source,
                "action_required": True,
                "recovery_state": "active",
                "lifecycle_state": "active",
                "status": "active",
                "active": True,
                "recovered": False,
                "summary": title,
                "title": title,
                "message": title,
                "detail": detail,
                "remediation": action,
                "action": action,
            }
        )

    if health.launch_failure_count or health.transport_failure_count:
        add(
            "launch_failures",
            "error",
            "Terminal-audit auditor launches are failing",
            (
                f"{health.launch_failure_count} launch failure(s) and "
                f"{health.transport_failure_count} transport failure(s) are "
                "recorded for pending audits."
            ),
            "Restore an available auditor transport; retries will continue automatically.",
        )

    if health.policy_incompatibility_count:
        add(
            "policy_incompatibility",
            "error",
            "Terminal-audit tool policy is incompatible with auditor commands",
            (
                f"{health.policy_incompatibility_count} auditor attempt(s) were "
                "stopped by the local read-only tool policy."
            ),
            "Update the auditor tool catalog or prompt contract; this is not a provider transport outage.",
        )

    if health.finalization_failure_count:
        add(
            "finalization_failures",
            "error",
            "Terminal-audit verdict finalization is incomplete",
            (
                f"{health.finalization_failure_count} terminal-audit verdict(s) "
                "are waiting for durable status finalization."
            ),
            (
                "Restore tracker writes or restart audit enforcement; do not "
                "infer an outcome from a comment alone."
            ),
        )

    if health.retry_exhausted_count:
        add(
            "retry_exhausted",
            "error",
            "Terminal-audit retries are exhausted",
            (
                f"{health.retry_exhausted_count} pending audit(s) have used all "
                "configured auditor attempts."
            ),
            "Add a healthy independent auditor or route the affected records to operator review.",
        )

    age = health.oldest_pending_age_seconds
    if age is not None and age > 0 and health.stale_pending_count > 0:
        add(
            "backlog_age",
            "warning",
            "Terminal-audit backlog is stale",
            (
                f"The oldest pending audit is {age}s old across "
                f"{health.pending_count} pending audit(s)."
            ),
            "Increase auditor capacity or investigate the pending audit queue.",
        )

    if health.stale_in_validation_count:
        add(
            "stale_validation",
            "warning",
            "In Validation records are stale",
            (
                f"{health.stale_in_validation_count} record(s) have remained "
                "In Validation beyond the health threshold."
            ),
            "Check the audit queue and recover or requeue the affected records.",
        )

    if not health.scan_complete:
        add(
            "scan",
            "warning",
            "Terminal-audit health scan is incomplete",
            "Current audit health could not be fully confirmed.",
            "Restore tracker access before treating the queue as healthy.",
        )

    if health.quarantined_count:
        add(
            "metadata_quarantine",
            "error",
            "Terminal-audit metadata is quarantined",
            f"{health.quarantined_count} audit record(s) require operator attention.",
            "Repair the quarantined metadata before resuming terminal transitions.",
        )

    return alerts


__all__ = [
    "AuditHealthObservation",
    "DEFAULT_STALE_AFTER_SECONDS",
    "HEALTH_ALERT_PREFIX",
    "TerminalAuditHealth",
    "build_terminal_audit_health",
    "terminal_audit_health_alerts",
]
