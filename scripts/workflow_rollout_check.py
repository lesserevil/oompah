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


def evaluate_snapshot(snapshot: Mapping[str, Any]) -> CanaryResult:
    """Evaluate one production state sample without trusting display text."""

    failures: list[str] = []
    health = snapshot.get("health")
    if not isinstance(health, Mapping) or health.get("status") != "healthy":
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
        if not isinstance(leases, Mapping) or int(leases.get("expired", 0)):
            failures.append("expired durable workflow leases remain")
        if isinstance(states, Mapping) and int(states.get("exhausted", 0)):
            failures.append("exhausted durable workflow jobs remain")

    shadow = snapshot.get("workflow_shadow")
    if not isinstance(shadow, Mapping):
        failures.append("workflow shadow diagnostics are unavailable")
    elif shadow.get("mode") != "off":
        if (
            isinstance(runtime, Mapping)
            and runtime.get("mode") == "shadow"
            and shadow.get("last_evaluated_at") is None
        ):
            failures.append("workflow shadow has not completed a sample")
        if int(shadow.get("divergence_count", 0)):
            failures.append("workflow shadow has unresolved divergences")

    return CanaryResult(not failures, tuple(failures))


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
    try:
        while True:
            result = evaluate_snapshot(_read_snapshot())
            samples += 1
            if not result.healthy:
                print("Workflow rollout canary failed:", file=sys.stderr)
                for failure in result.failures:
                    print(f"- {failure}", file=sys.stderr)
                return 1
            if time.monotonic() >= deadline:
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
