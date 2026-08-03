"""Structured, redacted presentation facts for the dashboard.

Producers in the service intentionally keep their domain-specific state in
their own snapshots.  This module is the small presentation boundary between
that state and the global operator warning surface.  It gives every emitted
fact the same actionability vocabulary while retaining producer-specific
diagnostics for task detail views.

The normalizer is deliberately tolerant of legacy alert dictionaries.  That
matters during rolling upgrades and also lets OOMPAH-735's integration retry
classifier remain the sole owner of recovery decisions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from oompah.alert_safety import (
    ALERT_ACTION_MAX_LENGTH,
    ALERT_EXPLANATION_MAX_LENGTH,
    ALERT_SOURCE_MAX_LENGTH,
    ALERT_SUMMARY_MAX_LENGTH,
    ALERT_TITLE_MAX_LENGTH,
    bounded_text,
    sanitize_alert,
)
from oompah.secrets import redact_sensitive_data

CONTRACT_VERSION = 1

_SEVERITY_RANK = {
    "info": 0,
    "warning": 1,
    "error": 2,
    "critical": 3,
}
_SEVERITY_ALIASES = {
    "debug": "info",
    "notice": "info",
    "warn": "warning",
    "err": "error",
    "fatal": "critical",
}
_RECOVERED_STATES = frozenset({"recovered", "resolved", "passed", "healthy"})
_HISTORY_STATES = frozenset({"historical", "history", "cleared", "idle"})
_RECOVERING_STATES = frozenset(
    {
        "active_repair",
        "awaiting_repair",
        "scheduled_retry",
        "retrying",
        "running",
        "in_progress",
        "recovering",
        "interrupted_for_retry",
    }
)


def _text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return default


def _compact(value: Any, *, limit: int) -> str:
    """Return bounded, single-line text after secret redaction."""

    safe = redact_sensitive_data(_text(value))
    return bounded_text(safe, limit)


def _severity(raw: Mapping[str, Any]) -> str:
    value = _text(raw.get("severity") or raw.get("level"), default="warning").lower()
    value = _SEVERITY_ALIASES.get(value, value)
    return value if value in _SEVERITY_RANK else "warning"


def _explicit_bool(raw: Mapping[str, Any], key: str) -> bool | None:
    value = raw.get(key)
    return value if isinstance(value, bool) else None


def _raw_recovery_state(raw: Mapping[str, Any]) -> str:
    for key in ("recovery_state", "lifecycle_state", "lifecycle", "state"):
        value = _text(raw.get(key)).strip().lower()
        if value:
            return value
    return ""


def _action_required(raw: Mapping[str, Any], severity: str, recovery: str) -> bool:
    explicit = _explicit_bool(raw, "action_required")
    if explicit is not None:
        return explicit
    active = _explicit_bool(raw, "active")
    if active is False:
        return False
    status = _text(raw.get("status")).strip().lower()
    if status in _RECOVERED_STATES | _HISTORY_STATES:
        return False
    source = _text(raw.get("source")).lower()
    if source.startswith("repo_hygiene") and raw.get("is_healthy") is True:
        return False
    if source.startswith("quality_gate") and status in {
        "running",
        "passed",
        "not_configured",
        "interrupted",
    }:
        return False
    if recovery in _RECOVERED_STATES | _HISTORY_STATES | _RECOVERING_STATES:
        return recovery not in _RECOVERED_STATES | _HISTORY_STATES | _RECOVERING_STATES
    return severity != "info"


def _status(raw: Mapping[str, Any], action_required: bool, recovery: str) -> str:
    explicit = _text(raw.get("presentation_status") or raw.get("alert_status")).lower()
    if explicit in {"active", "recovering", "recovered", "historical", "informational"}:
        return explicit
    raw_status = _text(raw.get("status")).strip().lower()
    if raw_status in _RECOVERED_STATES:
        return "recovered"
    if raw_status in _HISTORY_STATES:
        return "historical"
    if recovery in _RECOVERED_STATES:
        return "recovered"
    if recovery in _HISTORY_STATES:
        return "historical"
    if recovery in _RECOVERING_STATES:
        return "recovering"
    if action_required:
        return "active"
    return "informational"


def _stable_id(raw: Mapping[str, Any], summary: str) -> str:
    """Return a source-owned identity, with a deterministic legacy fallback."""

    for key in ("stable_id", "alert_id", "identity", "id", "source"):
        value = _compact(raw.get(key), limit=256)
        if value:
            return value
    basis = json.dumps(
        {
            "summary": summary,
            "detail": _compact(raw.get("detail") or raw.get("explanation"), limit=512),
            "remediation": _compact(raw.get("remediation") or raw.get("action"), limit=512),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "dashboard:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def normalize_alert(raw_alert: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one legacy or structured alert into the dashboard contract.

    Domain fields are copied after recursive secret redaction.  Thus retry
    attempts, task identifiers, branch heads, and health metrics remain
    available to task-local consumers without making the global presentation
    schema depend on any one producer.
    """

    # Apply the transcript-aware safety projection before deriving the
    # dashboard fact.  This is intentionally repeated by callers at producer,
    # snapshot, and API/WebSocket boundaries: cached data and rolling-upgrade
    # payloads must not be able to reintroduce a raw subprocess transcript.
    safe_raw = sanitize_alert(raw_alert)
    if not isinstance(safe_raw, dict):  # pragma: no cover - defensive boundary
        safe_raw = {}
    summary = _compact(
        safe_raw.get("summary")
        or safe_raw.get("title")
        or safe_raw.get("message")
        or safe_raw.get("source"),
        limit=ALERT_SUMMARY_MAX_LENGTH,
    ) or "Oompah dashboard condition"
    detail = _compact(
        safe_raw.get("detail") or safe_raw.get("explanation"),
        limit=ALERT_EXPLANATION_MAX_LENGTH,
    )
    remediation = _compact(
        safe_raw.get("remediation") or safe_raw.get("action"),
        limit=ALERT_ACTION_MAX_LENGTH,
    )
    severity = _severity(safe_raw)
    recovery = _raw_recovery_state(safe_raw)
    action_required = _action_required(safe_raw, severity, recovery)
    status = _status(safe_raw, action_required, recovery)
    if not recovery:
        recovery = "operator_action_required" if action_required else "informational"
    stable_id = _stable_id(safe_raw, summary)

    result = dict(safe_raw)
    result.update(
        {
            "contract_version": CONTRACT_VERSION,
            "id": stable_id,
            "alert_id": stable_id,
            "identity": stable_id,
            "stable_identity": stable_id,
            "stable_id": stable_id,
            "source": _compact(
                safe_raw.get("source"), limit=ALERT_SOURCE_MAX_LENGTH
            ) or stable_id,
            "action_required": action_required,
            "severity": severity,
            # ``level`` remains for older dashboard clients and API consumers.
            "level": severity,
            "recovery_state": recovery,
            "lifecycle_state": status,
            "lifecycle": status,
            "status": status,
            "active": status not in {"recovered", "historical", "informational"},
            "is_active": status not in {"recovered", "historical", "informational"},
            "recovered": status == "recovered",
            "is_recovered": status == "recovered",
            "summary": summary,
            "compact_summary": summary,
            "title": _compact(
                safe_raw.get("title"), limit=ALERT_TITLE_MAX_LENGTH
            ) or summary,
            # ``message``/``action`` are compatibility aliases.  New clients
            # should consume summary/remediation without parsing prose.
            "message": summary,
            "detail": detail,
            "sanitized_detail": detail,
            "remediation": remediation,
            "action": remediation,
        }
    )
    return result


def normalize_alerts(alerts: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize and deduplicate facts at the state-snapshot boundary.

    Producers use their stable ``source`` identity, so a condition emitted by
    both a durable health registry and an on-demand builder collapses to one
    row.  If equivalent rows disagree, the row with the highest current
    severity wins; ties prefer an actionable active row and then preserve the
    first producer order for deterministic output.
    """

    selected: dict[str, dict[str, Any]] = {}
    for raw in alerts:
        if not isinstance(raw, Mapping):
            continue
        fact = normalize_alert(raw)
        key = str(fact["stable_id"])
        current = selected.get(key)
        if current is None:
            selected[key] = fact
            continue
        current_rank = _SEVERITY_RANK.get(str(current.get("severity")), 0)
        candidate_rank = _SEVERITY_RANK.get(str(fact.get("severity")), 0)
        current_key = (
            current_rank,
            bool(current.get("action_required")),
            bool(current.get("active")),
        )
        candidate_key = (
            candidate_rank,
            bool(fact.get("action_required")),
            bool(fact.get("active")),
        )
        if candidate_key > current_key:
            # Carry producer diagnostics forward when the winning producer
            # used the same source but omitted a domain-specific field.
            for field, value in current.items():
                fact.setdefault(field, value)
            selected[key] = fact
        else:
            for field, value in fact.items():
                current.setdefault(field, value)
    return list(selected.values())


# Descriptive aliases keep call sites readable and provide a stable import for
# API/snapshot tests without exposing implementation details.
build_dashboard_alerts = normalize_alerts
normalize_dashboard_alert = normalize_alert
normalize_dashboard_alerts = normalize_alerts


__all__ = [
    "CONTRACT_VERSION",
    "build_dashboard_alerts",
    "normalize_alert",
    "normalize_alerts",
    "normalize_dashboard_alert",
    "normalize_dashboard_alerts",
]
