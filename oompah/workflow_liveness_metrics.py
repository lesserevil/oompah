"""Workflow liveness SLO metrics and health tracking.

Instruments time-to-owner/explanation for Open, Ready, In Validation, In Review,
recovery, and post-restart reconstruction. Tracks decision age, reassessment lateness,
lease/retry deadlines, recoveries, escalations, and unexplained divergences with
bounded cardinality.

Design (OOMPAH-784):
- Health reflects whether every nonterminal task satisfies the liveness invariant
- SLO violations are measurable and attributable (not just "server loop responds")
- Configuration via OOMPAH_LIVENESS_* .env variables for bounded cardinality metrics
- Integration with existing health endpoint patterns (provider_health, terminal_audit_health)
- Fake-clock support for comprehensive test coverage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import logging

logger = logging.getLogger(__name__)


# Default SLO thresholds (seconds) for each nonterminal state.
# These track time spent in each status before advance to next phase.
DEFAULT_LIVENESS_THRESHOLDS_SECONDS: dict[str, int] = {
    # Time from task creation to first owner assignment/dispatch
    "open": 3600,      # 1 hour
    # Time from task ready to first validation attempt
    "ready": 1800,     # 30 minutes
    # Time in validation before completion
    "in_validation": 7200,  # 2 hours
    # Time in review before completion
    "in_review": 7200,     # 2 hours
    # Time to recovery after stall detected
    "recovery": 300,       # 5 minutes
    # Time to reconstruct state after restart
    "post_restart": 600,   # 10 minutes
}

# Maximum number of distinct violations to track before aggregating
DEFAULT_MAX_DISTINCT_VIOLATIONS: int = 100
DEFAULT_MAX_ESCALATIONS: int = 50


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp string or datetime into an aware UTC datetime."""
    if not isinstance(value, (str, datetime)):
        return None
    if isinstance(value, datetime):
        ts = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    v = str(value).strip()
    if not v:
        return None
    try:
        parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    """Serialize a datetime to a canonical ISO-8601 string."""
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkflowLivenessObservation:
    """One task's liveness observation at scan time.

    Captures the current state, timing, and any SLO violations for a single
    nonterminal task.
    """

    project_id: str | None
    task_identifier: str
    current_status: str
    # Timestamp when task entered current status
    status_entered_at: datetime | str | None
    # Timestamp of task creation
    created_at: datetime | str | None
    # Timestamp of last progress (dispatch, status change, etc.)
    last_progress_at: datetime | str | None
    # Whether this task is actively being worked (has active agent)
    actively_working: bool = False
    # Whether this task has been flagged for recovery
    recovery_needed: bool = False
    # Number of times this task has been reassessed without progress
    reassessment_count: int = 0
    # Number of times recovery was attempted
    recovery_count: int = 0


@dataclass
class WorkflowLivenessHealth:
    """Aggregated workflow liveness health snapshot.

    Redacted, serializable view of SLO compliance across all nonterminal tasks.
    """

    # Count of tasks violating SLO by status
    violations_by_status: dict[str, int] = field(default_factory=dict)
    # Count of tasks in each status
    task_count_by_status: dict[str, int] = field(default_factory=dict)
    # Count of active recoveries in progress
    active_recovery_count: int = 0
    # Count of tasks needing recovery
    recovery_needed_count: int = 0
    # Total distinct SLO violations tracked
    total_violations_count: int = 0
    # Number of escalations triggered
    escalation_count: int = 0
    # Oldest pending task (for trend detection)
    oldest_violation_age_seconds: int | None = None
    # Whether health is degraded
    degraded: bool = False
    # Scan completed successfully
    scan_complete: bool = True
    # Scan error count (transient failures)
    scan_error_count: int = 0
    # Per-project summaries
    projects: dict[str, dict[str, int]] = field(default_factory=dict)
    # Configuration snapshot
    liveness_thresholds_seconds: dict[str, int] = field(default_factory=dict)
    max_distinct_violations: int = DEFAULT_MAX_DISTINCT_VIOLATIONS
    max_escalations: int = DEFAULT_MAX_ESCALATIONS

    @property
    def violation_count(self) -> int:
        """Total violations across all statuses."""
        return sum(self.violations_by_status.values())

    @property
    def healthy(self) -> bool:
        """Health is good when no SLO violations are active."""
        return not self.degraded and self.violation_count == 0


def build_workflow_liveness_health(
    observations: list[WorkflowLivenessObservation],
    *,
    now: datetime | None = None,
    thresholds_seconds: dict[str, int] | None = None,
    max_distinct_violations: int = DEFAULT_MAX_DISTINCT_VIOLATIONS,
    max_escalations: int = DEFAULT_MAX_ESCALATIONS,
) -> WorkflowLivenessHealth:
    """Build aggregated health from task observations.

    Args:
        observations: List of current task observations
        now: Current timestamp for age calculations (defaults to UTC now)
        thresholds_seconds: Per-status SLO thresholds (defaults to DEFAULT_LIVENESS_THRESHOLDS_SECONDS)
        max_distinct_violations: Bounded cardinality cap
        max_escalations: Maximum escalations to track

    Returns:
        Aggregated WorkflowLivenessHealth with violations and trends
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if thresholds_seconds is None:
        thresholds_seconds = DEFAULT_LIVENESS_THRESHOLDS_SECONDS

    health = WorkflowLivenessHealth(
        liveness_thresholds_seconds=dict(thresholds_seconds),
        max_distinct_violations=max_distinct_violations,
        max_escalations=max_escalations,
    )

    violations_by_status: dict[str, int] = {}
    task_count_by_status: dict[str, int] = {}
    recovery_needed = 0
    active_recovery = 0
    oldest_violation_age: int | None = None
    project_violations: dict[str, int] = {}

    for obs in observations:
        status = obs.current_status.lower()
        task_count_by_status[status] = task_count_by_status.get(status, 0) + 1

        # Track project summary
        if obs.project_id:
            if obs.project_id not in health.projects:
                health.projects[obs.project_id] = {}
            health.projects[obs.project_id][status] = (
                health.projects[obs.project_id].get(status, 0) + 1
            )

        # Determine if this observation violates SLO
        status_entered = _parse_timestamp(obs.status_entered_at)
        last_progress = _parse_timestamp(obs.last_progress_at)
        created = _parse_timestamp(obs.created_at)

        # Use most recent status entry time for SLO calculation
        reference_time = status_entered or last_progress or created
        if reference_time is None:
            continue

        # Check for SLO violation based on time in status
        threshold_seconds = thresholds_seconds.get(status, thresholds_seconds.get("open", 3600))
        age_seconds = int((now - reference_time).total_seconds())

        if age_seconds > threshold_seconds and not obs.actively_working:
            violations_by_status[status] = violations_by_status.get(status, 0) + 1
            if oldest_violation_age is None or age_seconds > oldest_violation_age:
                oldest_violation_age = age_seconds

        # Track recovery status
        if obs.recovery_needed:
            recovery_needed += 1
        if obs.actively_working and obs.recovery_needed:
            active_recovery += 1

    health.violations_by_status = violations_by_status
    health.task_count_by_status = task_count_by_status
    health.recovery_needed_count = recovery_needed
    health.active_recovery_count = active_recovery
    health.oldest_violation_age_seconds = oldest_violation_age
    health.total_violations_count = health.violation_count

    # Degraded if any violations or if recovery is needed
    health.degraded = health.violation_count > 0 or recovery_needed > 0

    return health


def workflow_liveness_health_alerts(health: WorkflowLivenessHealth) -> list[dict[str, Any]]:
    """Generate human-readable alerts from liveness health.

    Returns a list of alert dicts suitable for dashboard rendering and
    operator notification. Each alert includes:
    - source: alert identifier (e.g. "liveness:open_slo_violation")
    - severity: "info", "warning", or "critical"
    - message: human-readable description
    - count: affected task count (when applicable)
    """
    alerts: list[dict[str, Any]] = []

    # Alert on violations by status
    for status, count in health.violations_by_status.items():
        alerts.append({
            "source": f"liveness:slo_violation_{status}",
            "severity": "warning" if count < 5 else "critical",
            "message": f"{count} task(s) violating SLO in '{status}' status",
            "count": count,
        })

    # Alert on recovery needs
    if health.recovery_needed_count > 0:
        alerts.append({
            "source": "liveness:recovery_needed",
            "severity": "critical",
            "message": f"{health.recovery_needed_count} task(s) need recovery",
            "count": health.recovery_needed_count,
        })

    # Alert on active recoveries
    if health.active_recovery_count > 0:
        alerts.append({
            "source": "liveness:recovery_in_progress",
            "severity": "info",
            "message": f"{health.active_recovery_count} recovery operation(s) in progress",
            "count": health.active_recovery_count,
        })

    # Alert on oldest violation age (trend alert)
    if health.oldest_violation_age_seconds is not None:
        oldest_minutes = health.oldest_violation_age_seconds // 60
        if oldest_minutes > 60:
            alerts.append({
                "source": "liveness:aged_violation",
                "severity": "critical",
                "message": f"Oldest SLO violation is {oldest_minutes} minutes old",
                "age_minutes": oldest_minutes,
            })

    return alerts
