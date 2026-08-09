from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from oompah.workflow_soak import (
    WorkflowSoakProfile,
    build_workload,
    run_workflow_soak,
)


def _ci_profile() -> WorkflowSoakProfile:
    return WorkflowSoakProfile(
        name="test-ci",
        task_count=104,
        project_count=4,
        decision_limit=31,
        batch_size=24,
        max_cycles=100,
    )


def test_workload_is_deterministic_nested_and_cross_project() -> None:
    profile = _ci_profile()

    first = build_workload(profile)
    second = build_workload(profile)

    assert first == second
    assert len(first) == 104
    assert len({task.task_id for task in first}) == 104
    assert {task.project_id for task in first} == {
        "soak-project-01",
        "soak-project-02",
        "soak-project-03",
        "soak-project-04",
    }
    assert sum(task.issue_type == "epic" for task in first) == 8
    assert sum(
        task.issue_type == "epic" and bool(task.parent_id) for task in first
    ) == 4
    by_id = {task.task_id: task for task in first}
    assert sum(
        by_id[dependency].project_id != task.project_id
        for task in first
        for dependency in task.dependencies
    ) == 3
    assert {task.action for task in first} >= {
        "implementation_recovery",
        "review_merge",
        "terminal_audit",
        "integration_attempt",
        "branch_prune",
        "rollup_reconciliation",
    }


def test_ci_soak_qualifies_liveness_recovery_parity_and_resources(tmp_path) -> None:
    profile = _ci_profile()

    report = run_workflow_soak(
        profile,
        database_path=tmp_path / "workflow-soak.sqlite3",
    )

    assert report.task_count == 104
    assert report.terminal_recoverable_tasks == 103
    assert report.expected_escalations == 1
    assert report.unexplained_tasks == ()
    assert report.transient_failures >= 8
    assert report.restart_recoveries == 1
    assert report.max_queue_age_seconds <= profile.max_task_latency_seconds
    assert report.max_task_latency_seconds <= profile.max_task_latency_seconds
    assert report.contended_fairness_repeats == 0
    assert report.projection_checks >= 104
    assert report.projection_mismatches == 0
    assert report.actionable_alerts == 1
    assert report.sqlite_bytes <= report.sqlite_limit_bytes
    assert report.peak_memory_bytes <= report.peak_memory_limit_bytes
    assert report.cross_project_dependencies == 3
    assert report.nested_epics == 4
    assert report.branch_prunes > 0


def test_profile_rejects_non_soak_and_unbounded_settings() -> None:
    with pytest.raises(ValueError, match="at least 100"):
        WorkflowSoakProfile(
            name="too-small",
            task_count=99,
            project_count=3,
            decision_limit=20,
            batch_size=20,
            max_cycles=20,
        )
    with pytest.raises(ValueError, match="decision_limit"):
        WorkflowSoakProfile(
            name="unbounded",
            task_count=100,
            project_count=4,
            decision_limit=1001,
            batch_size=20,
            max_cycles=20,
        )


def test_profile_loads_documented_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OOMPAH_WORKFLOW_SOAK_TASK_COUNT", "140")
    monkeypatch.setenv("OOMPAH_WORKFLOW_SOAK_PROJECT_COUNT", "5")
    monkeypatch.setenv("OOMPAH_WORKFLOW_SOAK_BATCH_SIZE", "28")

    profile = WorkflowSoakProfile.from_env("ci")

    assert profile.task_count == 140
    assert profile.project_count == 5
    assert profile.batch_size == 28


def test_ci_command_emits_qualification_report(tmp_path) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("OOMPAH_WORKFLOW_SOAK_")
    }

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/workflow_soak.py",
            "--profile",
            "ci",
            "--env-file",
            str(tmp_path / "absent.env"),
        ],
        cwd=os.fspath(Path(__file__).parents[1]),
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    report = json.loads(completed.stdout)
    assert report["profile"] == "ci"
    assert report["task_count"] == 120
    assert report["terminal_recoverable_tasks"] == 119
    assert report["expected_escalations"] == 1
