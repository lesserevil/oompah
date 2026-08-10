#!/usr/bin/env python3
"""Fail-closed canary/soak check for the durable workflow rollout."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from oompah.client_auth import (
    CredentialError,
    load_client_environment,
    resolve_client_credentials,
    sanitize_server_url,
)
from oompah.workflow_shadow import WORKFLOW_DOMAIN_NAMES


@dataclass(frozen=True, slots=True)
class CanaryResult:
    healthy: bool
    failures: tuple[str, ...]
    provisional: bool = False


_TERMINAL_AUDIT_DEGRADATION_COUNTS = (
    "launch_failure_count",
    "transport_failure_count",
    "policy_incompatibility_count",
    "configuration_error_count",
    "finalization_failure_count",
    "stale_pending_count",
    "stale_in_validation_count",
    "retry_exhausted_count",
    "transport_retry_pending_count",
    "quarantined_count",
)


def _is_exact_zero(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _is_expected_audit_continuation(
    snapshot: Mapping[str, Any],
    health: Mapping[str, Any],
) -> bool:
    """Return whether bounded audit scanning is the only degraded fact.

    A partial terminal-audit scan is not authoritative health.  It is safe for
    the multi-sample canary to wait through that state only when every
    machine-readable companion fact proves that the durable cursor is the sole
    reason aggregate health is degraded.  Missing or malformed evidence fails
    closed instead of being inferred from alert display text.
    """

    if health.get("status") != "degraded":
        return False
    audit = health.get("terminal_audit")
    if not isinstance(audit, Mapping):
        return False
    if (
        audit.get("scan_complete") is not False
        or audit.get("degraded") is not True
        or not _is_exact_zero(audit.get("scan_error_count"))
        or not all(
            _is_exact_zero(audit.get(field))
            for field in _TERMINAL_AUDIT_DEGRADATION_COUNTS
        )
    ):
        return False

    validation = health.get("validation_resources")
    if not isinstance(validation, Mapping) or validation.get("status") not in {
        "idle",
        "busy",
    }:
        return False
    health_jobs = health.get("workflow_jobs")
    if not isinstance(health_jobs, Mapping) or not _is_exact_zero(
        health_jobs.get("quarantined")
    ):
        return False
    liveness = health.get("workflow_liveness")
    if (
        not isinstance(liveness, Mapping)
        or liveness.get("enabled") is not True
        or liveness.get("status") != "healthy"
        or liveness.get("degraded") is not False
        or liveness.get("scan_complete") is not True
    ):
        return False
    audit_metrics = snapshot.get("audits")
    if (
        not isinstance(audit_metrics, Mapping)
        or audit_metrics.get("candidate_scan_complete") is not False
        or audit_metrics.get("budget_deferred") is not True
        or audit_metrics.get("continuation_requested") is not True
        or not _is_exact_zero(audit_metrics.get("health_scan_error_count"))
    ):
        return False

    alerts = snapshot.get("global_alerts")
    jobs = snapshot.get("workflow_jobs")
    if alerts != [] or not isinstance(jobs, Mapping):
        return False
    leases = jobs.get("leases")
    current_states = jobs.get("current_states")
    return bool(
        isinstance(leases, Mapping)
        and _is_exact_zero(leases.get("expired"))
        and _is_exact_zero(leases.get("quarantined"))
        and isinstance(current_states, Mapping)
        and _is_exact_zero(current_states.get("exhausted"))
    )


def evaluate_snapshot(snapshot: Mapping[str, Any]) -> CanaryResult:
    """Evaluate one production state sample without trusting display text."""

    failures: list[str] = []
    provisional = False
    health = snapshot.get("health")
    if not isinstance(health, Mapping):
        failures.append("service health is not healthy")
    elif health.get("status") == "healthy":
        audit = health.get("terminal_audit")
        if not isinstance(audit, Mapping) or audit.get("scan_complete") is not True:
            failures.append("terminal-audit health coverage is not complete")
    elif _is_expected_audit_continuation(snapshot, health):
        provisional = True
    else:
        failures.append("service health is not healthy")
    alerts = snapshot.get("global_alerts")
    if not isinstance(alerts, list):
        failures.append("actionable alert projection is unavailable")
    elif alerts:
        failures.append(f"{len(alerts)} operator-actionable alert(s) remain")

    runtime = snapshot.get("workflow_runtime")
    if not isinstance(runtime, Mapping) or runtime.get("started") is not True:
        failures.append("durable workflow runtime is not started")
    else:
        modes = runtime.get("domain_modes")
        if not isinstance(modes, Mapping) or set(modes) != set(
            WORKFLOW_DOMAIN_NAMES
        ):
            failures.append("workflow domain mode projection is incomplete")
        elif any(str(modes[domain]) == "off" for domain in WORKFLOW_DOMAIN_NAMES):
            failures.append("one or more workflow domains remain off")
        if runtime.get("binding_topology_current") is not True:
            failures.append("workflow project binding topology is stale")
        rollout = runtime.get("rollout")
        if not isinstance(rollout, list) or len(rollout) != len(
            WORKFLOW_DOMAIN_NAMES
        ):
            failures.append("persisted workflow rollout evidence is incomplete")
        else:
            for row in rollout:
                if not isinstance(row, Mapping):
                    failures.append("persisted workflow rollout row is invalid")
                    continue
                failure_at = row.get("last_failure_at")
                success_at = row.get("last_success_at")
                if failure_at is not None and (
                    success_at is None or float(failure_at) >= float(success_at)
                ):
                    failures.append(
                        f"{row.get('domain', 'unknown')}: latest shadow sweep failed"
                    )
        gate = runtime.get("rollout_gate")
        if not isinstance(gate, Mapping) or gate.get("all_domains_ready") is not True:
            failures.append("persisted workflow rollout gate is not qualified")

    jobs = snapshot.get("workflow_jobs")
    if not isinstance(jobs, Mapping):
        failures.append("workflow job health is unavailable")
    else:
        leases = jobs.get("leases")
        states = jobs.get("states")
        current_states = jobs.get("current_states")
        if not isinstance(leases, Mapping) or int(leases.get("expired", 0)):
            failures.append("expired durable workflow leases remain")
        if isinstance(leases, Mapping) and int(leases.get("quarantined", 0)):
            failures.append("quarantined durable workflow calls remain")
        exhausted_states = (
            current_states if isinstance(current_states, Mapping) else states
        )
        if isinstance(exhausted_states, Mapping) and int(
            exhausted_states.get("exhausted", 0)
        ):
            failures.append("exhausted durable workflow jobs remain")

    if failures:
        provisional = False
    return CanaryResult(
        healthy=not failures and not provisional,
        failures=tuple(failures),
        provisional=provisional,
    )


def _read_snapshot() -> dict[str, Any]:
    base = sanitize_server_url(
        os.environ.get("OOMPAH_SERVER_URL", "http://127.0.0.1:8080")
    ) or "http://127.0.0.1:8080"
    request = urllib.request.Request(f"{base}/api/v1/state", method="GET")
    credentials = resolve_client_credentials()
    if credentials is not None:
        username, password = credentials
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("state response is not a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    load_client_environment(include_server_url=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=int(os.environ.get("OOMPAH_WORKFLOW_CANARY_DURATION_SECONDS", "300")),
    )
    parser.add_argument(
        "--sample-interval-seconds",
        type=int,
        default=int(
            os.environ.get("OOMPAH_WORKFLOW_CANARY_SAMPLE_INTERVAL_SECONDS", "10")
        ),
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    duration = 0 if args.once else max(args.duration_seconds, 1)
    interval = max(args.sample_interval_seconds, 1)
    deadline = time.monotonic() + duration
    samples = 0
    complete_healthy_samples = 0
    try:
        while True:
            result = evaluate_snapshot(_read_snapshot())
            samples += 1
            if result.healthy:
                complete_healthy_samples += 1
            elif not result.provisional:
                print("Workflow rollout canary failed:", file=sys.stderr)
                for failure in result.failures:
                    print(f"- {failure}", file=sys.stderr)
                return 1
            if time.monotonic() >= deadline:
                if complete_healthy_samples == 0:
                    print("Workflow rollout canary failed:", file=sys.stderr)
                    print(
                        "- terminal-audit health did not complete during "
                        "the canary window",
                        file=sys.stderr,
                    )
                    return 1
                break
            time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    except (CredentialError, OSError, ValueError, urllib.error.URLError) as exc:
        print(
            f"Workflow rollout canary could not read a valid state sample: "
            f"{type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    print(f"Workflow rollout canary passed ({samples} sample(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
