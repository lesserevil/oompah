from __future__ import annotations

import hashlib
import http.server
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import oompah.quality_gate as quality_gate
from oompah.integration import IntegrationRecord
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import (
    AuditorQualityEvidenceProof,
    BranchQualityGate,
    QualityGateOwner,
    QualityGateResult,
    _SANDBOX_RUN_ROOT,
    _SandboxUnavailable,
    _TrustedRuntimeCorruption,
    _editable_oompah_source,
    _validate_trusted_runtime_source,
)
from oompah.statuses import IN_VALIDATION, OPEN, READY_TO_INTEGRATE
from oompah.terminal_audit import compute_issue_evidence_fingerprint
from oompah.validation_resource_lease import (
    ValidationLeaseOwner,
    ValidationResourceLease,
)


def _safety_head(repo_path):
    """Return the synthetic safety head created by ``_git_repo``."""
    result = subprocess.run(
        ["git", "log", "--format=%H", "--grep=^OOMPAH-652: lifecycle isolation$", "-n", "1"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _passthrough_sandbox(command, _repo_path, _run_root):
    """Inject a launch stub for unit tests that exercise gate mechanics."""
    return ["/bin/sh", "-c", command]


def _gate(state_path, repo_path, **kwargs):
    """Inject a fixture repository's safety head without global environment state."""
    safety_head = _safety_head(repo_path)
    if safety_head:
        kwargs["safety_head"] = safety_head
    kwargs["sandbox_launcher"] = _passthrough_sandbox
    return BranchQualityGate(str(state_path), **kwargs)


def test_exact_gate_reuses_compatible_successful_auditor_evidence(tmp_path):
    repo = _git_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    marker = tmp_path / "executed"
    command = f"touch {shlex.quote(str(marker))}"
    gate = _gate(tmp_path / "quality.json", repo)
    proof = AuditorQualityEvidenceProof(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        workspace_head_sha=head,
        command=command,
        configured_command=command,
        evidence_fingerprint="fingerprint",
        expected_evidence_fingerprint="fingerprint",
        detached_workspace=True,
    )

    assert gate.record_compatible_auditor_pass(proof) is True
    result = gate.run(
        repo_path=str(repo),
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        command=command,
        expected_head_sha=head,
    )

    assert result.status == "passed"
    assert result.cached is True
    assert marker.exists() is False


def test_quality_gate_lookup_returns_persisted_exact_head_duration(tmp_path):
    repo = _git_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    state_path = tmp_path / "quality.json"
    gate = _gate(state_path, repo)
    proof = AuditorQualityEvidenceProof(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        workspace_head_sha=head,
        command="make test",
        configured_command="make test",
        evidence_fingerprint="fingerprint",
        expected_evidence_fingerprint="fingerprint",
        detached_workspace=True,
    )

    assert gate.record_compatible_auditor_pass(proof, duration_seconds=12.5)
    evidence = gate.lookup(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        command="make test",
    )

    assert evidence is not None
    assert evidence.passed is True
    assert evidence.cached is True
    assert evidence.head_sha == head
    assert evidence.duration_seconds == pytest.approx(12.5)
    assert gate.lookup(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha="a" * 40,
        command="make test",
    ) is None
    assert gate.lookup(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        command="make test-serial",
    ) is None

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    only_entry = next(iter(persisted["results"].values()))
    only_entry["work_branch"] = "tampered"
    state_path.write_text(json.dumps(persisted), encoding="utf-8")
    assert gate.lookup(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        command="make test",
    ) is None


def test_quality_gate_lookup_exposes_failed_exact_head_without_reuse(tmp_path):
    repo = _git_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    gate = _gate(tmp_path / "quality.json", repo)

    result = gate.run(
        repo_path=str(repo),
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        command="false",
        expected_head_sha=head,
    )
    evidence = gate.lookup(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        command="false",
    )

    assert result.status == "failed"
    assert evidence is not None
    assert evidence.status == "failed"
    assert evidence.passed is False


def test_waiting_exact_gate_does_not_deadlock_successful_auditor_evidence(
    tmp_path,
):
    repo = _git_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    marker = tmp_path / "executed"
    command = f"touch {shlex.quote(str(marker))}"
    lease = ValidationResourceLease(
        tmp_path / "validation.sqlite3",
        poll_seconds=0.01,
    )
    auditor = lease.acquire(
        ValidationLeaseOwner.auditor(
            project_id="project",
            task_id="audit",
            authority_generation="attempt",
        )
    )
    gate = _gate(
        tmp_path / "quality.json",
        repo,
        validation_lease=lease,
    )
    proof = AuditorQualityEvidenceProof(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha=head,
        workspace_head_sha=head,
        command=command,
        configured_command=command,
        evidence_fingerprint="fingerprint",
        expected_evidence_fingerprint="fingerprint",
        detached_workspace=True,
    )
    gate_results: list[QualityGateResult] = []
    callback_results: list[bool] = []
    gate_thread = threading.Thread(
        target=lambda: gate_results.append(
            gate.run(
                repo_path=str(repo),
                repo_identity="repo",
                target_branch="main",
                work_branch="work",
                command=command,
                expected_head_sha=head,
            )
        )
    )
    callback_thread = threading.Thread(
        target=lambda: callback_results.append(
            gate.record_compatible_auditor_pass(proof)
        )
    )

    gate_thread.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and lease.status().waiter_count != 1:
        time.sleep(0.01)
    assert lease.status().waiter_count == 1
    callback_thread.start()
    callback_thread.join(timeout=1)
    callback_completed_while_lease_held = not callback_thread.is_alive()
    auditor.release()
    callback_thread.join(timeout=3)
    gate_thread.join(timeout=5)

    assert callback_completed_while_lease_held is True
    assert callback_results == [True]
    assert gate_thread.is_alive() is False
    assert gate_results and gate_results[0].passed
    assert gate_results[0].cached is True
    assert marker.exists() is False
    assert lease.status().owner_count == 0
    assert lease.status().waiter_count == 0


@pytest.mark.parametrize(
    "change",
    [
        {"configured_command": "different"},
        {"workspace_head_sha": "b" * 40},
        {"expected_evidence_fingerprint": "different"},
        {"detached_workspace": False},
        {"work_branch": ""},
    ],
)
def test_auditor_evidence_reuse_rejects_incompatible_proof(tmp_path, change):
    proof = AuditorQualityEvidenceProof(
        repo_identity="repo",
        target_branch="main",
        work_branch="work",
        head_sha="a" * 40,
        workspace_head_sha="a" * 40,
        command="make test",
        configured_command="make test",
        evidence_fingerprint="fingerprint",
        expected_evidence_fingerprint="fingerprint",
        detached_workspace=True,
    )
    gate = BranchQualityGate(str(tmp_path / "quality.json"))

    assert gate.record_compatible_auditor_pass(replace(proof, **change)) is False
    assert (tmp_path / "quality.json").exists() is False


def test_orchestrator_records_only_clean_exact_detached_auditor_workspace(tmp_path):
    repo = _git_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    audit_workspace = tmp_path / "audit"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(audit_workspace), head],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path=str(repo),
        test_command_full="make test",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        description="requirements",
        project_id="project",
        branch_name="work",
        target_branch="main",
        integration=IntegrationRecord(
            state="ready",
            task_branch="work",
            base_branch="main",
            head_sha=head,
        ),
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, "project").digest
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orchestrator = object.__new__(Orchestrator)
    orchestrator.project_store = MagicMock()
    orchestrator.project_store.get.return_value = project
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._branch_quality_gate = _gate(
        tmp_path / "quality.json",
        repo,
    )
    target = {
        "audit_id": "audit",
        "task_id": "TASK-1",
        "project_id": "project",
        "target_state": "Done",
        "evidence_fingerprint": fingerprint,
    }

    assert orchestrator.record_auditor_quality_evidence(
        audit_target=target,
        workspace_path=audit_workspace,
        command="make test",
    ) is True

    (audit_workspace / "source.txt").write_text("dirty\n", encoding="utf-8")
    orchestrator._branch_quality_gate = _gate(
        tmp_path / "dirty-quality.json",
        repo,
    )
    assert orchestrator.record_auditor_quality_evidence(
        audit_target=target,
        workspace_path=audit_workspace,
        command="make test",
    ) is False


@pytest.mark.parametrize(
    ("gate_result", "expected_decision"),
    [
        (
            QualityGateResult(
                "passed",
                "a" * 40,
                "make test",
                10.0,
                recorded_at=9_999.0,
            ),
            "reuse_authoritative_gate",
        ),
        (
            QualityGateResult(
                "passed",
                "a" * 40,
                "make test",
                10.0,
                recorded_at=None,
            ),
            "full_gate_required",
        ),
        (
            QualityGateResult(
                "failed",
                "a" * 40,
                "make test",
                10.0,
                recorded_at=9_999.0,
            ),
            "full_gate_required",
        ),
        (
            QualityGateResult(
                "not_configured",
                "a" * 40,
                "make test",
                0.0,
                recorded_at=9_999.0,
            ),
            "full_gate_required",
        ),
        (None, "full_gate_required"),
    ],
)
def test_terminal_audit_quality_gate_bundle_is_fail_closed_for_nonpassing_evidence(
    gate_result,
    expected_decision,
    monkeypatch,
):
    monkeypatch.setattr(time, "time", lambda: 10_000.0)
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path="",
        default_branch="main",
        test_command_full="make test",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        project_id="project",
        state=IN_VALIDATION,
        integration=IntegrationRecord(
            state="ready",
            task_branch="work",
            base_branch="main",
            head_sha="a" * 40,
        ),
    )
    metrics = MagicMock()
    orchestrator = object.__new__(Orchestrator)
    orchestrator._branch_quality_gate = MagicMock()
    orchestrator._branch_quality_gate.lookup.return_value = gate_result
    orchestrator._terminal_audit_metrics = metrics
    orchestrator._quality_gate_branch_head = MagicMock(return_value="a" * 40)
    tracker = MagicMock(fetch_issue_detail=MagicMock(return_value=issue))
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator.config = SimpleNamespace(audit_stale_pending_seconds=3600)
    fingerprint = compute_issue_evidence_fingerprint(issue, "project").digest

    bundle = orchestrator._terminal_audit_quality_gate_evidence(
        issue,
        project,
        SimpleNamespace(
            project_id="project",
            task_id="TASK-1",
            audit_id="audit-1",
            target_state="Done",
            evidence_fingerprint=fingerprint,
        ),
    )

    assert bundle["decision"] == expected_decision
    assert bundle["command"] == "make test"
    assert bundle["accepted_head_sha"] == "a" * 40
    if gate_result is not None:
        assert bundle["duration_seconds"] == gate_result.duration_seconds
    tracker.invalidate_read_cache.assert_called_once_with()
    tracker.fetch_issue_detail.assert_called_once_with("TASK-1")
    metrics.record_quality_gate_decision.assert_called_once()


@pytest.mark.parametrize(
    "recorded_at",
    [None, float("nan"), float("inf"), "invalid", False, 10_001.0],
)
def test_terminal_audit_quality_gate_bundle_rejects_invalid_timestamps(
    recorded_at,
    monkeypatch,
):
    monkeypatch.setattr(time, "time", lambda: 10_000.0)
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path="/managed/repo",
        default_branch="main",
        test_command_full="make test",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        project_id="project",
        state=IN_VALIDATION,
        integration=IntegrationRecord(
            state="ready",
            task_branch="work",
            base_branch="main",
            head_sha="a" * 40,
        ),
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, "project").digest
    orchestrator = object.__new__(Orchestrator)
    orchestrator.config = SimpleNamespace(audit_stale_pending_seconds=60)
    orchestrator._terminal_audit_metrics = MagicMock()
    orchestrator._tracker_for_project = MagicMock(
        return_value=MagicMock(fetch_issue_detail=MagicMock(return_value=issue))
    )
    orchestrator._quality_gate_branch_head = MagicMock(return_value="a" * 40)
    orchestrator._branch_quality_gate = MagicMock()
    orchestrator._branch_quality_gate.lookup.return_value = QualityGateResult(
        "passed",
        "a" * 40,
        "make test",
        recorded_at=recorded_at,
    )

    bundle = orchestrator._terminal_audit_quality_gate_evidence(
        issue,
        project,
        SimpleNamespace(
            project_id="project",
            task_id="TASK-1",
            audit_id="audit-1",
            target_state="Done",
            evidence_fingerprint=fingerprint,
        ),
    )

    assert bundle["decision"] == "full_gate_required"
    assert "timestamp is missing or invalid" in bundle["reason"]


def test_terminal_audit_quality_gate_bundle_reuses_old_current_authority(
    monkeypatch,
):
    monkeypatch.setattr(time, "time", lambda: 10_000.0)
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path="/managed/repo",
        default_branch="main",
        test_command_full="make test",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        project_id="project",
        state=IN_VALIDATION,
        integration=IntegrationRecord(
            state="ready",
            task_branch="work",
            base_branch="main",
            head_sha="a" * 40,
        ),
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, "project").digest
    orchestrator = object.__new__(Orchestrator)
    orchestrator._terminal_audit_metrics = MagicMock()
    orchestrator._tracker_for_project = MagicMock(
        return_value=MagicMock(fetch_issue_detail=MagicMock(return_value=issue))
    )
    orchestrator._quality_gate_branch_head = MagicMock(return_value="a" * 40)
    orchestrator._branch_quality_gate = MagicMock()
    orchestrator._branch_quality_gate.lookup.return_value = QualityGateResult(
        "passed",
        "a" * 40,
        "make test",
        recorded_at=1.0,
    )

    bundle = orchestrator._terminal_audit_quality_gate_evidence(
        issue,
        project,
        SimpleNamespace(
            project_id="project",
            task_id="TASK-1",
            audit_id="audit-1",
            target_state="Done",
            evidence_fingerprint=fingerprint,
        ),
    )

    assert bundle["decision"] == "reuse_authoritative_gate"
    assert bundle["recorded_at"] == 1.0


@pytest.mark.parametrize("stale_surface", ["fingerprint", "branch", "state"])
def test_terminal_audit_quality_gate_bundle_rejects_stale_authority(
    stale_surface,
):
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path="/managed/repo",
        default_branch="main",
        test_command_full="make test",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        project_id="project",
        state=OPEN if stale_surface == "state" else IN_VALIDATION,
        integration=IntegrationRecord(
            state="ready",
            task_branch="work",
            base_branch="main",
            head_sha="a" * 40,
        ),
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, "project").digest
    orchestrator = object.__new__(Orchestrator)
    orchestrator.config = SimpleNamespace(audit_stale_pending_seconds=3600)
    orchestrator._terminal_audit_metrics = MagicMock()
    orchestrator._tracker_for_project = MagicMock(
        return_value=MagicMock(fetch_issue_detail=MagicMock(return_value=issue))
    )
    orchestrator._quality_gate_branch_head = MagicMock(
        return_value=("b" if stale_surface == "branch" else "a") * 40
    )
    orchestrator._branch_quality_gate = MagicMock()
    orchestrator._branch_quality_gate.lookup.return_value = QualityGateResult(
        "passed",
        "a" * 40,
        "make test",
        recorded_at=time.time(),
    )

    bundle = orchestrator._terminal_audit_quality_gate_evidence(
        issue,
        project,
        SimpleNamespace(
            project_id="project",
            task_id="TASK-1",
            audit_id="audit-1",
            target_state="Done",
            evidence_fingerprint=(
                "b" * 64 if stale_surface == "fingerprint" else fingerprint
            ),
        ),
    )

    assert bundle["decision"] == "full_gate_required"
    assert (
        "stale" in bundle["reason"]
        or "no longer names" in bundle["reason"]
        or "no longer In Validation" in bundle["reason"]
    )
    if stale_surface in {"fingerprint", "state"}:
        orchestrator._branch_quality_gate.lookup.assert_not_called()


def test_terminal_audit_quality_gate_bundle_reports_not_configured_explicitly():
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path="/managed/repo",
        default_branch="main",
        test_command_full="",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        project_id="project",
    )
    orchestrator = object.__new__(Orchestrator)
    orchestrator._terminal_audit_metrics = MagicMock()
    orchestrator._branch_quality_gate = MagicMock()

    bundle = orchestrator._terminal_audit_quality_gate_evidence(
        issue,
        project,
        SimpleNamespace(
            project_id="project",
            task_id="TASK-1",
            audit_id="audit-1",
        ),
    )

    assert bundle["decision"] == "not_configured"
    assert bundle["status"] == "not_configured"
    assert bundle["command"] == ""
    orchestrator._branch_quality_gate.lookup.assert_not_called()


def test_reusable_gate_policy_marks_missing_attempt_authority_invalid():
    policy = Orchestrator._auditor_validation_reuse_policy(
        {
            "decision": "reuse_authoritative_gate",
            "command": "make test",
            "accepted_head_sha": "a" * 40,
            "target_branch": "main",
            "work_branch": "work",
        },
        SimpleNamespace(
            project_id="project",
            task_id="TASK-1",
            audit_id="audit-1",
            attempt_id="",
            target_state="Done",
            evidence_fingerprint="f" * 64,
        ),
    )

    assert policy is not None
    assert policy["invalid_authority"] is True
    assert policy["attempt_id"] == ""


@pytest.mark.parametrize(
    ("authority_surface", "expected"),
    [
        ("current", "reuse_authoritative_gate"),
        ("missing_gate", "full_gate_required"),
        ("invalid_timestamp", "full_gate_required"),
        ("status", "stale_authority"),
        ("head", "stale_authority"),
        ("branch", "stale_authority"),
        ("target_fingerprint", "stale_authority"),
        ("live_audit", "stale_authority"),
        ("live_attempt", "stale_authority"),
        ("live_fingerprint", "stale_authority"),
    ],
)
def test_auditor_validation_reuse_authority_rechecks_live_surfaces(
    authority_surface,
    expected,
    monkeypatch,
):
    project = Project(
        id="project",
        name="project",
        repo_url="repo",
        repo_path="/managed/repo",
        default_branch="main",
        test_command_full="make test",
    )
    issue = Issue(
        id="task",
        identifier="TASK-1",
        title="Task",
        project_id="project",
        state=OPEN if authority_surface == "status" else IN_VALIDATION,
        integration=IntegrationRecord(
            state="ready",
            task_branch="work",
            base_branch="main",
            head_sha="a" * 40,
        ),
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, "project").digest
    target = SimpleNamespace(
        project_id="project",
        task_id="TASK-1",
        audit_id="audit-1",
        attempt_id="attempt-1",
        target_state="Done",
        evidence_fingerprint=(
            "b" * 64 if authority_surface == "target_fingerprint" else fingerprint
        ),
    )
    live_target = SimpleNamespace(**vars(target))
    if authority_surface == "live_audit":
        live_target.audit_id = "audit-2"
    elif authority_surface == "live_attempt":
        live_target.attempt_id = "attempt-2"
    elif authority_surface == "live_fingerprint":
        live_target.evidence_fingerprint = "b" * 64

    policy = Orchestrator._auditor_validation_reuse_policy(
        {
            "decision": "reuse_authoritative_gate",
            "command": "make test",
            "accepted_head_sha": "a" * 40,
            "target_branch": "main",
            "work_branch": (
                "other-work" if authority_surface == "branch" else "work"
            ),
        },
        target,
    )
    assert policy is not None
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    tracker.get_metadata.return_value = {"unused": True}
    orchestrator = object.__new__(Orchestrator)
    orchestrator.project_store = MagicMock()
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.project_write_lock.return_value = nullcontext()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._terminal_audit_metrics = MagicMock()
    orchestrator._quality_gate_branch_head = MagicMock(
        return_value=("b" if authority_surface == "head" else "a") * 40
    )
    orchestrator._branch_quality_gate = MagicMock()
    if authority_surface == "missing_gate":
        orchestrator._branch_quality_gate.lookup.return_value = None
    else:
        orchestrator._branch_quality_gate.lookup.return_value = QualityGateResult(
            "passed",
            "a" * 40,
            "make test",
            recorded_at=(
                float("nan")
                if authority_surface == "invalid_timestamp"
                else time.time()
            ),
        )
    monkeypatch.setattr(
        "oompah.orchestrator.pending_auditor_target",
        lambda *_args, **_kwargs: live_target,
    )

    result = orchestrator._auditor_validation_reuse_authority_state(
        issue,
        target,
        policy,
    )

    assert result == expected
    if expected != "stale_authority":
        tracker.get_metadata.assert_called_once_with("TASK-1")


def _git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "lesserevil@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )

    # Create the deployed lifecycle entrypoint before the synthetic safety
    # head, so later candidate commits can be checked against its exact bytes.
    makefile = repo / "Makefile"
    makefile.write_text(
        """
_PYTEST_GATE := $(filter 1 true yes,$(strip $(OOMPAH_PYTEST_GATE)))
ifeq ($(_PYTEST_GATE),)
PID_FILE ?= .oompah.pid
else
PID_FILE := $(OOMPAH_TEST_PID_FILE)
endif
PORT := $(OOMPAH_TEST_SERVER_PORT)
OOMPAH_PYTEST_RUN_ROOT := /tmp/test

.PHONY: test
test:
\t@pytest
""",
        encoding="utf-8",
    )

    # Create initial "safety head" commit (simulating OOMPAH-652).
    initial = repo / "initial.txt"
    initial.write_text("safety head\n", encoding="utf-8")
    subprocess.run(["git", "add", "initial.txt", "Makefile"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "OOMPAH-652: lifecycle isolation"],
        cwd=repo,
        check=True,
    )

    source = repo / "source.txt"
    source.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "Makefile", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "work"], cwd=repo, check=True)

    return repo


def _stale_managed_clone_with_submission(tmp_path):
    """Return a clone made before ``work`` was pushed to its remote."""
    source_root = tmp_path / "source-root"
    source_root.mkdir()
    source = _git_repo(source_root)
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(remote)],
        check=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=source, check=True
    )
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=source, check=True)

    managed = tmp_path / "managed"
    subprocess.run(["git", "clone", "-q", str(remote), str(managed)], check=True)

    (source / "source.txt").write_text("submitted\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=source, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "submitted candidate"],
        cwd=source,
        check=True,
    )
    submitted_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "push", "-q", "origin", "work"], cwd=source, check=True)
    return source, managed, submitted_head


def _submitted_gate_orchestrator(tmp_path, managed, submitted_head, *, branch="work"):
    counter = tmp_path / "counter"
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(managed),
        test_command=f"printf x >> {shlex.quote(str(counter))}",
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        state=READY_TO_INTEGRATE,
        work_branch=branch,
        integration=IntegrationRecord(
            state="ready",
            task_branch=branch,
            head_sha=submitted_head,
        ),
    )
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = [issue]
    tracker.fetch_issue_detail.return_value = issue
    project_store = MagicMock()
    project_store.get.return_value = project
    project_store.worktree_path_for.return_value = str(tmp_path / "missing")
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)
    orch._branch_quality_gate = _gate(tmp_path / "quality.json", managed)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}
    return orch, project, issue, tracker, counter


def _run(gate, repo, command, **overrides):
    args = {
        "repo_path": str(repo),
        "repo_identity": "https://example.test/org/repo",
        "target_branch": "main",
        "work_branch": "work",
        "command": command,
    }
    args.update(overrides)
    return gate.run(**args)


def test_passing_head_is_cached_and_survives_restart(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}"
    state = tmp_path / "quality.json"

    first = _run(_gate(state, repo), repo, command)
    second = _run(_gate(state, repo), repo, command)

    assert first.passed and not first.cached
    assert second.passed and second.cached
    assert counter.read_text(encoding="utf-8") == "x"


@pytest.mark.parametrize(
    "malformed_surface",
    ["malformed_timestamp", "nonfinite_timestamp", "partial_identity"],
)
def test_normal_gate_reruns_instead_of_reusing_malformed_evidence(
    tmp_path,
    malformed_surface,
):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}"
    state = tmp_path / "quality.json"
    gate = _gate(state, repo)

    assert _run(gate, repo, command).passed
    persisted = json.loads(state.read_text(encoding="utf-8"))
    entry = next(iter(persisted["results"].values()))
    if malformed_surface == "malformed_timestamp":
        entry["recorded_at"] = "not-a-number"
    elif malformed_surface == "nonfinite_timestamp":
        entry["recorded_at"] = float("nan")
    else:
        entry.pop("command")
    state.write_text(json.dumps(persisted), encoding="utf-8")

    result = _run(_gate(state, repo), repo, command)

    assert result.passed
    assert result.cached is False
    assert counter.read_text(encoding="utf-8") == "xx"


def test_new_head_command_or_target_invalidates_pass(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    state = tmp_path / "quality.json"
    command = f"printf x >> {shlex.quote(str(counter))}"
    gate = _gate(state, repo)

    assert _run(gate, repo, command).passed
    assert _run(gate, repo, command, target_branch="release/1").passed
    assert _run(gate, repo, f"{command}; true").passed

    (repo / "source.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "change"], cwd=repo, check=True)
    changed = _run(gate, repo, command)

    assert changed.passed and not changed.cached
    assert counter.read_text(encoding="utf-8") == "xxxx"


def test_pre_sanitization_evidence_is_invalidated(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    state = tmp_path / "quality.json"
    command = f"printf x >> {shlex.quote(str(counter))}"
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    legacy_key = hashlib.sha256(
        "\0".join(
            (
                "https://example.test/org/repo",
                "main",
                "work",
                head_sha,
                command,
            )
        ).encode("utf-8")
    ).hexdigest()
    state.write_text(
        json.dumps(
            {
                "version": 1,
                "results": {
                    legacy_key: {
                        "status": "passed",
                        "head_sha": head_sha,
                        "command": command,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = _run(_gate(state, repo), repo, command)

    assert result.passed and not result.cached
    assert counter.read_text(encoding="utf-8") == "x"
    assert json.loads(state.read_text(encoding="utf-8"))["version"] == 2


def test_failure_and_timeout_do_not_create_passing_evidence(tmp_path):
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = _gate(state, repo, timeout_seconds=1)

    failed = _run(gate, repo, "sh -c 'echo broken; exit 7'")
    timed_out = _run(gate, repo, "sleep 2")
    cached_failure = _run(gate, repo, "sh -c 'echo broken; exit 7'")

    assert failed.status == "failed"
    assert "broken" in failed.output_tail
    assert timed_out.status == "timed_out"
    assert cached_failure.status == "failed"
    assert cached_failure.cached
    assert not failed.passed
    assert not timed_out.passed


def test_concurrent_readiness_checks_execute_once(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}; sleep 0.2"
    gate = _gate(tmp_path / "quality.json", repo)
    barrier = threading.Barrier(3)
    results = []

    def worker():
        barrier.wait()
        results.append(_run(gate, repo, command))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert len(results) == 2
    assert all(result.passed for result in results)
    assert sum(result.cached for result in results) == 1
    assert counter.read_text(encoding="utf-8") == "x"


def test_gate_reads_only_its_detached_snapshot_after_task_worktree_changes(tmp_path):
    repo = _git_repo(tmp_path)
    observed = tmp_path / "observed.txt"
    gate = _gate(tmp_path / "quality.json", repo)
    head = _run(gate, repo, "true").head_sha
    command = (
        f"sleep 0.3; cat source.txt > {shlex.quote(str(observed))}"
    )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                command,
                expected_head_sha=head,
                generation="task-generation-1",
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_snapshots:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("quality gate snapshot was not active")

            # Simulate an operator reopening the task and the replacement
            # agent mutating the reusable task worktree.
            (repo / "source.txt").write_text("replacement\n", encoding="utf-8")
            result = future.result(timeout=5)

        assert result.passed
        assert result.head_sha == head
        assert observed.read_text(encoding="utf-8") == "one\n"
        with BranchQualityGate._processes_lock:
            assert BranchQualityGate._active_snapshots == {}
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_gate_rejects_a_worktree_that_is_not_the_recorded_head(tmp_path):
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    first_head = _run(gate, repo, "true").head_sha
    (repo / "source.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=repo, check=True)
    marker = tmp_path / "must-not-run"

    result = _run(
        gate,
        repo,
        f"touch {shlex.quote(str(marker))}",
        expected_head_sha=first_head,
    )

    assert result.status == "stale_head"
    assert not marker.exists()


def test_gate_archives_exact_head_from_unrelated_managed_checkout(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "source.txt").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "candidate"], cwd=repo, check=True
    )
    candidate_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    (repo / "source.txt").write_text("dirty checkout\n", encoding="utf-8")

    result = _run(
        _gate(tmp_path / "quality.json", repo),
        repo,
        "test \"$(cat source.txt)\" = candidate",
        expected_head_sha=candidate_head,
        require_source_head_match=False,
    )

    assert result.passed
    assert result.head_sha == candidate_head


def test_gate_classifies_unavailable_exact_head_as_infrastructure(tmp_path):
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"

    result = _run(
        _gate(tmp_path / "quality.json", repo),
        repo,
        f"touch {shlex.quote(str(marker))}",
        expected_head_sha="a" * 40,
        require_source_head_match=False,
    )

    assert result.status == "infrastructure_error"
    assert "exact commit is unavailable" in result.output_tail
    assert not marker.exists()


def test_generation_cancellation_does_not_stop_a_replacement_head_gate(tmp_path):
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    old_head = _run(gate, repo, "true").head_sha
    old_marker = tmp_path / "old-marker"
    new_marker = tmp_path / "new-marker"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            old_future = pool.submit(
                _run,
                gate,
                repo,
                f"sleep 2; touch {shlex.quote(str(old_marker))}",
                expected_head_sha=old_head,
                generation="old-generation",
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if any(
                        generation == "old-generation"
                        for generation in BranchQualityGate._active_generations.values()
                    ):
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("old quality gate was not active")

            (repo / "source.txt").write_text("new\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "new"], cwd=repo, check=True)
            new_head = _run(gate, repo, "true").head_sha
            new_future = pool.submit(
                _run,
                gate,
                repo,
                f"sleep 0.1; touch {shlex.quote(str(new_marker))}",
                expected_head_sha=new_head,
                generation="new-generation",
            )
            assert BranchQualityGate.cancel_generation("old-generation") == 1
            old_result = old_future.result(timeout=5)
            new_result = new_future.result(timeout=5)

        assert old_result.status == "interrupted"
        assert new_result.passed
        assert not old_marker.exists()
        assert new_marker.exists()
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_exact_owner_cancellation_cannot_stop_an_unrelated_task_gate(tmp_path):
    """A task-scoped cancellation must not match another task's process."""
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    owner_a = QualityGateOwner("project-1", "task-a", head, "shared-generation")
    owner_b = QualityGateOwner("project-1", "task-b", head, "shared-generation")

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                "sleep 30",
                expected_head_sha=head,
                owner=owner_a,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                active = BranchQualityGate.active_state()
                if active:
                    assert active[0]["project_id"] == "project-1"
                    assert active[0]["task_id"] == "task-a"
                    break
                time.sleep(0.01)
            else:
                raise AssertionError("task A quality gate was not active")

            assert BranchQualityGate.cancel_owner(owner_b) == 0
            assert BranchQualityGate.active_state()[0]["task_id"] == "task-a"
            assert (
                BranchQualityGate.cancel_owner(
                    project_id="project-1",
                    task_id="task-a",
                    head_sha=head,
                )
                == 0
            )
            assert BranchQualityGate.cancel_owner(owner_a) == 1
            assert future.result(timeout=5).status == "interrupted"
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_owner_keys.discard(owner_b.key)
            BranchQualityGate._cancelled_owner_order.pop(owner_b.key, None)


def test_quality_gate_rejects_owner_for_a_different_exact_head(tmp_path):
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    owner = QualityGateOwner("project-1", "task-a", "f" * 40, "generation-a")

    result = _run(
        gate,
        repo,
        "touch should-not-run",
        expected_head_sha=head,
        owner=owner,
    )

    assert result.status == "infrastructure_error"
    assert "does not match" in result.output_tail
    with BranchQualityGate._processes_lock:
        assert not BranchQualityGate._active_processes


def test_quality_gate_state_reports_retryable_interrupt_and_clears_on_pass():
    orch = Orchestrator.__new__(Orchestrator)
    orch._quality_gate_outcomes_lock = threading.Lock()
    orch._quality_gate_outcomes = {}
    orch._remember_quality_gate_result(
        "project-1",
        "task-b",
        QualityGateResult(
            status="interrupted",
            head_sha="head-b",
            command="make test",
        ),
    )

    interrupted = orch._quality_gate_state_snapshot()
    assert interrupted["status"] == "interrupted_for_retry"
    assert interrupted["recent"][0]["task_id"] == "task-b"

    orch._remember_quality_gate_result(
        "project-1",
        "task-b",
        QualityGateResult(
            status="passed",
            head_sha="head-b",
            command="make test",
        ),
    )
    assert orch._quality_gate_state_snapshot()["status"] == "idle"
    assert orch._quality_gate_state_snapshot()["recent"] == []


def test_quality_gate_outcomes_are_bounded_and_head_aware():
    orch = Orchestrator.__new__(Orchestrator)
    orch._quality_gate_outcomes_lock = threading.Lock()
    orch._quality_gate_outcomes = {}
    orch._QUALITY_GATE_OUTCOME_LIMIT = 2

    for task_id, head_sha in (
        ("task-a", "head-a"),
        ("task-b", "head-b"),
        ("task-c", "head-c"),
    ):
        orch._remember_quality_gate_result(
            "project-1",
            task_id,
            QualityGateResult(
                status="failed",
                head_sha=head_sha,
                command="make test",
            ),
        )

    assert len(orch._quality_gate_outcomes) == 2
    assert orch._quality_gate_result_for("project-1", "task-a") is None
    assert (
        orch._quality_gate_result_for(
            "project-1",
            "task-c",
            head_sha="different-head",
        )
        is None
    )
    assert orch._quality_gate_result_for(
        "project-1",
        "task-c",
        head_sha="head-c",
    ) is not None


def test_gate_liveness_callback_cancels_only_its_owned_process(tmp_path):
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    current = threading.Event()
    current.set()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                "sleep 60",
                expected_head_sha=head,
                generation="liveness-generation",
                is_current=current.is_set,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_generations:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("liveness quality gate was not active")

            current.clear()
            result = future.result(timeout=5)

        assert result.status == "interrupted"
        assert not (tmp_path / "quality.json").exists()
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_no_command_is_an_explicit_non_blocking_result(tmp_path):
    repo = _git_repo(tmp_path)
    result = _run(
        _gate(tmp_path / "quality.json", repo),
        repo,
        "",
    )

    assert result.status == "not_configured"
    assert result.passed


@pytest.mark.skipif(
    Path("/oompah-gate/home").is_dir(),
    reason=(
        "The inner gate's /oompah-gate/home path is mounted by the outer bwrap "
        "sandbox, so the 'not leaked on host' assertion cannot hold when the test "
        "itself runs inside an outer quality-gate sandbox."
    ),
)
def test_gate_subprocess_isolates_operator_and_tool_state(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    sentinel = tmp_path / "gate-environment"
    monkeypatch.setenv("OOMPAH_SERVER_URL", "http://127.0.0.1:8090")
    monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "operator")
    monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "secret")
    monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", "/secret/path")
    monkeypatch.setenv("QUALITY_GATE_SENTINEL", "operator-only")
    command = (
        'test -z "${OOMPAH_SERVER_URL+x}"'
        ' && test -z "${OOMPAH_TASK_HANDOFF_TOKEN+x}"'
        ' && test -z "${OOMPAH_SERVER_USERNAME+x}"'
        ' && test -z "${OOMPAH_SERVER_PASSWORD+x}"'
        ' && test -z "${OOMPAH_SERVER_PASSWORD_FILE+x}"'
        ' && test -z "${QUALITY_GATE_SENTINEL+x}"'
        f' && printf "%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n" '
        f'"$HOME" "$TMPDIR" "$OOMPAH_TEST_PID_FILE" '
        f'"$OOMPAH_TEST_PID_META_FILE" "$OOMPAH_TEST_SERVER_PORT" '
        f'"$OOMPAH_TEMP_ROOT" "$OOMPAH_PYTEST_TEMP_ROOT" '
        f'> {shlex.quote(str(sentinel))}'
    )

    result = _run(
        _gate(tmp_path / "quality.json", repo),
        repo,
        command,
    )

    assert result.passed
    values = sentinel.read_text(encoding="utf-8").splitlines()
    assert values[0] == "/oompah-gate/home"
    assert values[1] == "/oompah-gate/tmp"
    assert values[2] == "/oompah-gate/lifecycle/.oompah.pid"
    assert values[3] == "/oompah-gate/lifecycle/.oompah.pid.meta"
    assert values[4].isdigit() and values[4] != "8090"
    assert values[5] == "/oompah-gate/tmp"
    assert values[6] == "/oompah-gate/tmp"
    runner_root = Path(os.environ.get("OOMPAH_PYTEST_RUN_ROOT", "/"))
    if runner_root.is_relative_to(_SANDBOX_RUN_ROOT):
        assert Path(values[0]).is_dir(), "outer gate root is not available"
    else:
        assert not Path(values[0]).exists(), "sandbox-visible gate root leaked on host"


def test_preflight_allows_lifecycle_evolution_behind_os_boundary(tmp_path):
    """A rebased candidate may evolve Makefile code without self-approving it."""
    repo = _git_repo(tmp_path)
    sentinel = tmp_path / "replaced-entrypoint-executed"
    (repo / "Makefile").write_text(
        f".PHONY: test\ntest:\n\t@touch {shlex.quote(str(sentinel))}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "replace lifecycle entrypoint"],
        cwd=repo,
        check=True,
    )

    result = _run(_gate(tmp_path / "quality.json", repo), repo, "make test")

    assert result.passed
    assert sentinel.exists(), "legitimate lifecycle evolution did not execute"


def test_snapshot_excludes_host_lifecycle_state_and_preserves_source_worktree(tmp_path):
    """An untracked canonical PID file is absent from the disposable snapshot."""
    repo = _git_repo(tmp_path)
    canonical_pid = repo / ".oompah.pid"
    canonical_pid.write_text("host sentinel\n", encoding="utf-8")

    result = _run(
        _gate(tmp_path / "quality.json", repo),
        repo,
        "test ! -e .oompah.pid && test -f source.txt && printf snapshot-control",
    )

    assert result.passed
    assert "snapshot-control" in result.output_tail
    assert canonical_pid.read_text(encoding="utf-8") == "host sentinel\n"


def test_snapshot_contains_private_exact_head_git_metadata(tmp_path):
    """Revision tests see the exact commit without the operator repository."""
    repo = _git_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    run_root = BranchQualityGate._gate_run_root()
    try:
        snapshot = BranchQualityGate._snapshot_candidate_worktree(
            str(repo), run_root, head
        )
        snapshot_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=snapshot,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=snapshot,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        remotes = subprocess.run(
            ["git", "remote"],
            cwd=snapshot,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        config = (snapshot / ".git" / "config").read_text(encoding="utf-8")

        assert snapshot_head == head
        assert status == ""
        assert remotes == ""
        assert str(repo.resolve()) not in config
        assert not (snapshot / ".git" / "FETCH_HEAD").exists()
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_snapshot_rejects_a_candidate_symlink_to_host_state(tmp_path):
    """Snapshot preparation fails closed rather than preserving an escape link."""
    repo = _git_repo(tmp_path)
    (repo / "host-escape").symlink_to("/etc/passwd")
    subprocess.run(["git", "add", "host-escape"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "host escape link"], cwd=repo, check=True)
    run_root = BranchQualityGate._gate_run_root()
    try:
        with pytest.raises(_SandboxUnavailable, match="unsafe link"):
            BranchQualityGate._snapshot_candidate_worktree(str(repo), run_root)
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_sandbox_command_uses_an_empty_root_and_private_runtime_mounts(
    tmp_path, monkeypatch
):
    """The wrapper never inherits the host root to make a candidate runnable."""
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    run_root = BranchQualityGate._gate_run_root()
    try:
        monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bwrap")
        monkeypatch.setattr(
            quality_gate,
            "_validate_trusted_runtime_source",
            lambda _runtime_prefix, _candidate_snapshot: None,
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda args, **_kwargs: subprocess.CompletedProcess(args, 0),
        )

        command = BranchQualityGate._sandbox_command("true", str(snapshot), run_root)

        pairs = set(zip(command, command[1:]))
        assert ("--tmpfs", "/") in pairs
        assert ("--ro-bind", "/") not in pairs
        assert ("/", "/") not in pairs
        assert ("--bind", str(snapshot)) in pairs
        assert (str(run_root), "/oompah-gate") in pairs
        assert ("--cap-add", "CAP_NET_ADMIN") in pairs
        assert 'ip link set lo up 2>/dev/null || true; exec "$@"' in command
        runtime_prefix = Path(sys.prefix).resolve()
        if runtime_prefix != Path(sys.base_prefix).resolve():
            bind_triples = {
                tuple(command[index : index + 3])
                for index in range(len(command) - 2)
                if command[index] in {"--bind", "--ro-bind"}
            }
            assert (
                "--bind",
                str(snapshot),
                str(runtime_prefix.parent),
            ) in bind_triples
            assert (
                "--ro-bind",
                str(runtime_prefix),
                str(runtime_prefix),
            ) in bind_triples
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_sandbox_command_overlays_writable_uv_sentinels_over_ro_venv(
    tmp_path, monkeypatch
):
    """Sentinel overlays prevent stale-mtime Make rebuilds when uv is absent.

    Git archive stamps all snapshot files with the commit timestamp.  When
    that timestamp is newer than the .uv-setup / .uv-test-setup sentinels
    inside the ro-mounted operator venv, Make tries to run ``uv pip install``
    — which fails because uv is not in the restricted sandbox PATH and the
    venv is mounted read-only.  ``_sandbox_command`` must create writable
    sentinel files in run_root and bind them over the read-only venv so Make
    sees them as current.
    """
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    run_root = BranchQualityGate._gate_run_root()
    try:
        monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bwrap")
        monkeypatch.setattr(
            quality_gate,
            "_validate_trusted_runtime_source",
            lambda _runtime_prefix, _candidate_snapshot: None,
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda args, **_kwargs: subprocess.CompletedProcess(args, 0),
        )

        command = BranchQualityGate._sandbox_command("true", str(snapshot), run_root)

        # Sentinels must be created as writable files in run_root.
        assert (run_root / ".uv-setup").exists(), (
            ".uv-setup sentinel not created in run_root"
        )
        assert (run_root / ".uv-test-setup").exists(), (
            ".uv-test-setup sentinel not created in run_root"
        )

        # Parse --bind flag dst triplets from the flat command list.
        bind_map: dict[str, str] = {}
        for i in range(len(command) - 2):
            if command[i] == "--bind":
                bind_map[command[i + 1]] = command[i + 2]

        # Sentinels must be bound at the venv path inside the snapshot so
        # they override the earlier --ro-bind of the operator venv.
        repo = snapshot.resolve()
        assert bind_map.get(str(run_root / ".uv-setup")) == str(
            repo / ".venv" / ".uv-setup"
        ), ".uv-setup not bound at venv/.uv-setup inside the sandbox"
        assert bind_map.get(str(run_root / ".uv-test-setup")) == str(
            repo / ".venv" / ".uv-test-setup"
        ), ".uv-test-setup not bound at venv/.uv-test-setup inside the sandbox"
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_sandbox_command_binds_operator_venv_at_absolute_path_for_shebang_resolution(
    tmp_path, monkeypatch
):
    """Operator-venv entry-point scripts (e.g. ``oompah``) must be executable.

    Console-script shebangs generated by pip/uv reference the virtualenv's
    absolute path on the host (e.g.
    ``#!/home/operator/.venv/bin/python3``).  The sandbox mounts the venv at
    ``snapshot/.venv`` but does NOT mount the original host path, so the
    kernel cannot resolve the shebang and the script exits 127.

    ``_sandbox_command`` must therefore also bind the operator venv at its
    own absolute host path inside the sandbox so the shebang interpreter is
    accessible.
    """
    import sys

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    run_root = BranchQualityGate._gate_run_root()
    try:
        monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bwrap")
        monkeypatch.setattr(
            quality_gate,
            "_validate_trusted_runtime_source",
            lambda _runtime_prefix, _candidate_snapshot: None,
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda args, **_kwargs: subprocess.CompletedProcess(args, 0),
        )

        command = BranchQualityGate._sandbox_command("true", str(snapshot), run_root)

        # Parse bind (src, dst) pairs from the flat command list.
        bind_pairs: list[tuple[str, str]] = []
        ro_bind_pairs: list[tuple[str, str]] = []
        for i in range(len(command) - 2):
            if command[i] == "--bind":
                bind_pairs.append((command[i + 1], command[i + 2]))
            if command[i] == "--ro-bind":
                ro_bind_pairs.append((command[i + 1], command[i + 2]))

        runtime_prefix_path = Path(sys.prefix).resolve()
        runtime_prefix = str(runtime_prefix_path)
        snapshot_venv = str((snapshot / ".venv").resolve())

        # The operator venv is bound at snapshot/.venv (existing behaviour).
        assert any(src == runtime_prefix and dst == snapshot_venv
                   for src, dst in ro_bind_pairs), (
            f"operator venv not bound at snapshot/.venv: {ro_bind_pairs}"
        )
        # It must ALSO be bound at its own absolute path so that console-script
        # shebangs (which reference that absolute path) resolve in the sandbox.
        if runtime_prefix != snapshot_venv:
            assert any(src == runtime_prefix and dst == runtime_prefix
                       for src, dst in ro_bind_pairs), (
                f"operator venv not bound at its own absolute path for shebang "
                f"resolution.  runtime_prefix={runtime_prefix!r}  "
                f"ro_bind_pairs={ro_bind_pairs!r}"
            )
        if runtime_prefix_path != Path(sys.base_prefix).resolve():
            assert (
                str(snapshot.resolve()),
                str(runtime_prefix_path.parent),
            ) in bind_pairs, (
                "candidate snapshot not projected at the editable runtime's "
                f"source checkout: {bind_pairs!r}"
            )
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_editable_source_mapping_is_read_from_trusted_distribution_metadata(
    tmp_path, monkeypatch
):
    source = tmp_path / "service-checkout"
    source.mkdir()

    class Distribution:
        def read_text(self, filename):
            assert filename == "direct_url.json"
            return json.dumps(
                {"url": source.as_uri(), "dir_info": {"editable": True}}
            )

    monkeypatch.setattr(
        quality_gate.metadata, "distribution", lambda _name: Distribution()
    )

    assert _editable_oompah_source() == source.resolve()


def test_poisoned_editable_source_mapping_is_executor_corruption(tmp_path, monkeypatch):
    runtime = tmp_path / "service" / ".venv"
    candidate = tmp_path / "candidate"
    wrong_worktree = tmp_path / "other-task"
    monkeypatch.setattr(
        quality_gate,
        "_declared_editable_oompah_source",
        lambda: wrong_worktree,
    )

    with pytest.raises(_TrustedRuntimeCorruption, match="expected .*actual"):
        _validate_trusted_runtime_source(runtime, candidate)


def test_gate_reports_poisoned_runtime_without_running_candidate(tmp_path):
    repo = _git_repo(tmp_path)
    marker = tmp_path / "candidate-ran"

    def poisoned_launcher(_command, _repo_path, _run_root):
        raise _TrustedRuntimeCorruption(
            "expected /service or immutable candidate; actual /other-task"
        )

    gate = BranchQualityGate(
        str(tmp_path / "quality.json"),
        safety_head=_safety_head(repo),
        sandbox_launcher=poisoned_launcher,
    )
    result = _run(gate, repo, f"touch {shlex.quote(str(marker))}")

    assert result.status == "infrastructure_error"
    assert "candidate CI was not run" in result.output_tail
    assert not marker.exists()
    assert not (tmp_path / "quality.json").exists()


@pytest.mark.parametrize(
    "metadata_payload",
    [
        {"url": "https://example.test/oompah", "dir_info": {"editable": True}},
        {"url": "file:///missing", "dir_info": {"editable": True}},
        {"url": "file:///tmp/oompah", "dir_info": {"editable": False}},
        {"dir_info": {"editable": True}},
        {"url": "file:///tmp/oompah", "dir_info": []},
        [],
    ],
)
def test_editable_oompah_source_ignores_unusable_metadata(
    metadata_payload, monkeypatch
):
    """Only an existing local editable source is safe to project."""

    class Distribution:
        def read_text(self, _filename):
            return json.dumps(metadata_payload)

    monkeypatch.setattr(
        quality_gate.metadata, "distribution", lambda _name: Distribution()
    )

    assert _editable_oompah_source() is None


def test_sandbox_command_projects_declared_editable_source_to_candidate(
    tmp_path, monkeypatch
):
    """Console scripts import the candidate when the venv points at another worktree."""
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    prior_worktree = tmp_path / "prior-worktree"
    prior_worktree.mkdir()
    run_root = BranchQualityGate._gate_run_root()
    try:
        monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bwrap")
        monkeypatch.setattr(
            quality_gate,
            "_validate_trusted_runtime_source",
            lambda _runtime_prefix, _candidate_snapshot: prior_worktree,
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda args, **_kwargs: subprocess.CompletedProcess(args, 0),
        )
        monkeypatch.setattr(
            quality_gate, "_editable_oompah_source", lambda: prior_worktree
        )

        command = BranchQualityGate._sandbox_command("true", str(snapshot), run_root)

        bind_pairs = [
            (command[index + 1], command[index + 2])
            for index in range(len(command) - 2)
            if command[index] == "--bind"
        ]
        runtime_prefix = Path(sys.prefix).resolve()
        if runtime_prefix != Path(sys.base_prefix).resolve():
            assert (
                str(snapshot.resolve()),
                str(prior_worktree.resolve()),
            ) in bind_pairs
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_default_boundary_blocks_literal_host_pid_and_localhost_attack(tmp_path):
    """A capable sandbox protects a live host sentinel while candidate code runs."""
    repo = _git_repo(tmp_path)
    canonical_pid = repo / ".oompah.pid"
    canonical_pid.write_text("canonical host lifecycle state\n", encoding="utf-8")
    sentinel = subprocess.Popen(["sleep", "60"], start_new_session=True)

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, _format, *_args):
            return

    service = http.server.ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    service_thread = threading.Thread(target=service.serve_forever, daemon=True)
    service_thread.start()
    attack = repo / "attack.sh"
    attack.write_text(
        "#!/bin/sh\n"
        f"if test -e {shlex.quote(str(canonical_pid))}; then\n"
        "  printf 'host-pid-file-reachable\\n'\n"
        "fi\n"
        "if command -v curl >/dev/null 2>&1 && "
        f"curl -fsS --max-time 1 http://127.0.0.1:{service.server_port}/healthz "
        ">/dev/null 2>&1; then\n"
        "  printf 'host-localhost-reachable\\n'\n"
        "fi\n"
        + "if kill -TERM " + str(sentinel.pid) + " 2>/dev/null; then\n"
        "  printf 'host-pid-signalled\\n'\n"
        "fi\n"
        + f"rm -rf {shlex.quote(str(canonical_pid))}\n"
        + "printf 'candidate-control-complete\\n'\n",
        encoding="utf-8",
    )
    attack.chmod(0o755)
    subprocess.run(["git", "add", "attack.sh"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "add hostile candidate test"],
        cwd=repo,
        check=True,
    )

    try:
        gate = BranchQualityGate(
            str(tmp_path / "quality.json"),
            safety_head=_safety_head(repo),
        )
        result = _run(gate, repo, "./attack.sh")

        if result.status == "needs_rebase":
            assert "OS-enforced quality-gate sandbox" in result.output_tail
            assert "candidate-control-complete" not in result.output_tail
        else:
            assert result.status == "passed"
            assert "candidate-control-complete" in result.output_tail
            assert "host-pid-file-reachable" not in result.output_tail
            assert "host-localhost-reachable" not in result.output_tail
            assert "host-pid-signalled" not in result.output_tail
        assert sentinel.poll() is None, "candidate signalled the live host sentinel"
        assert canonical_pid.read_text(encoding="utf-8") == "canonical host lifecycle state\n"
        with urllib.request.urlopen(
            f"http://127.0.0.1:{service.server_port}/healthz", timeout=1
        ) as response:
            assert response.read() == b"ok"
    finally:
        service.shutdown()
        service.server_close()
        sentinel.terminate()
        sentinel.wait(timeout=5)


def test_default_sandbox_keeps_namespace_local_loopback_available(tmp_path):
    """Local HTTP-style tests work after the wrapper brings namespace lo up."""
    repo = _git_repo(tmp_path)
    command = "python3 -c " + shlex.quote(
        "import os, socket, threading; "
        "server = socket.socket(); "
        "server.bind(('127.0.0.1', int(os.environ['OOMPAH_TEST_SERVER_PORT']))); "
        "server.listen(1); "
        "threading.Thread(target=lambda: server.accept()[0].sendall(b'ok'), "
        "daemon=True).start(); "
        "client = socket.create_connection(('127.0.0.1', int(os.environ['OOMPAH_TEST_SERVER_PORT']))); "
        "assert client.recv(2) == b'ok'; print('namespace-loopback-ok')"
    )
    result = _run(
        BranchQualityGate(
            str(tmp_path / "quality.json"), safety_head=_safety_head(repo)
        ),
        repo,
        command,
    )

    if result.status == "needs_rebase":
        assert "OS-enforced quality-gate sandbox" in result.output_tail
    else:
        assert result.status == "passed"
        assert "namespace-loopback-ok" in result.output_tail


def test_default_sandbox_runs_a_normal_make_target_or_fails_before_start(tmp_path):
    """The OS boundary permits an ordinary candidate Make target to gate."""
    repo = _git_repo(tmp_path)
    marker = "normal-make-target-ran"
    (repo / "Makefile").write_text(
        f".PHONY: test\ntest:\n\t@printf '{marker}\\n'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "normal make target"], cwd=repo, check=True)

    result = _run(
        BranchQualityGate(
            str(tmp_path / "quality.json"), safety_head=_safety_head(repo)
        ),
        repo,
        "make test",
    )

    if result.status == "needs_rebase":
        assert "OS-enforced quality-gate sandbox" in result.output_tail
        assert marker not in result.output_tail
    else:
        assert result.status == "passed"
        assert marker in result.output_tail


def test_default_sandbox_uses_project_style_trusted_test_setup(tmp_path):
    """A stale candidate manifest cannot trigger uv inside the gate sandbox."""
    repo = _git_repo(tmp_path)
    marker = "trusted-test-runtime-ran"
    (repo / "Makefile").write_text(
        "VENV := .venv\n"
        "PYTHON := $(VENV)/bin/python\n"
        "_PYTEST_GATE := $(filter 1 true yes,$(strip $(OOMPAH_PYTEST_GATE)))\n"
        "ifeq ($(_PYTEST_GATE),)\n"
        "test-setup:\n"
        "\t@uv pip install -e '.[dev]'\n"
        "else\n"
        "test-setup:\n"
        "\t@test -x $(PYTHON)\n"
        "\t@$(PYTHON) -c 'import pytest, xdist'\n"
        "endif\n"
        ".PHONY: test test-setup\n"
        "test: test-setup\n"
        f"\t@printf '{marker}\\n'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "use trusted gate runtime"],
        cwd=repo,
        check=True,
    )

    result = _run(
        BranchQualityGate(
            str(tmp_path / "quality.json"), safety_head=_safety_head(repo)
        ),
        repo,
        "make test",
    )

    if result.status == "needs_rebase":
        assert "OS-enforced quality-gate sandbox" in result.output_tail
    else:
        assert result.status == "passed"
        assert marker in result.output_tail
        assert "uv" not in result.output_tail


def test_default_sandbox_reaps_owned_descendants_or_fails_before_start(tmp_path):
    """A timeout cannot leave a candidate child outside the wrapper's ownership."""
    repo = _git_repo(tmp_path)
    marker = f"oompah-gate-child-{time.time_ns()}"
    command = "/bin/bash -c " + shlex.quote(f"exec -a {marker} sleep 60")
    result = _run(
        BranchQualityGate(
            str(tmp_path / "quality.json"),
            timeout_seconds=1,
            safety_head=_safety_head(repo),
        ),
        repo,
        command,
    )

    if result.status == "needs_rebase":
        assert "OS-enforced quality-gate sandbox" in result.output_tail
    else:
        assert result.status == "timed_out"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            processes = subprocess.run(
                ["ps", "-eo", "args="], capture_output=True, text=True, check=True
            ).stdout
            if marker not in processes:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("sandbox-owned descendant survived gate cleanup")


def test_orchestrator_resolves_exact_branch_worktree_and_posts_evidence(tmp_path):
    repo = _git_repo(tmp_path)
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
        test_command="true",
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        work_branch="work",
    )
    tracker = MagicMock()
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(repo)
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)
    orch._branch_quality_gate = _gate(tmp_path / "quality.json", repo)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}

    resolved = orch._quality_gate_worktree(project, issue, "work")
    passed = orch._review_quality_gate_passes(
        project,
        issue,
        "work",
        "main",
    )

    assert resolved == str(repo)
    assert passed is True
    assert tracker.add_comment.call_count == 1
    assert "Review creation may proceed" in tracker.add_comment.call_args.args[1]


def test_orchestrator_routes_gate_needs_rebase_to_rebase_repair(tmp_path):
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id="project-1",
        work_branch="work",
    )
    tracker = MagicMock()
    orch = Orchestrator.__new__(Orchestrator)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authorities = {}

    orch._record_quality_gate_failure(
        issue,
        "project-1",
        "work",
        "main",
        QualityGateResult(
            status="needs_rebase",
            head_sha="a" * 40,
            command="make test",
            output_tail="safety prerequisite missing",
        ),
    )

    tracker.update_issue.assert_called_once_with(
        "task-1",
        status="Needs Rebase",
        **{"add-label": "needs-rebase"},
    )
    assert "rebase" in tracker.add_comment.call_args.args[1].lower()


def test_orchestrator_reports_runtime_corruption_without_ci_fix(tmp_path):
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id="project-1",
        work_branch="work",
    )
    tracker = MagicMock()
    orch = Orchestrator.__new__(Orchestrator)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authorities = {}

    orch._record_quality_gate_failure(
        issue,
        "project-1",
        "work",
        "main",
        QualityGateResult(
            status="infrastructure_error",
            head_sha="a" * 40,
            command="make test",
            output_tail="candidate CI was not run",
        ),
    )

    tracker.update_issue.assert_not_called()
    assert "infrastructure action required" in tracker.add_comment.call_args.args[1].lower()
    assert "no candidate ci-fix status" in tracker.add_comment.call_args.args[1].lower()


def test_orchestrator_rejects_checkout_that_is_not_branch_tip(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "work.txt").write_text("work\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "work"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
    )
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(repo)
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)

    assert orch._quality_gate_worktree(project, issue, "work") == ""


def test_orchestrator_gates_remote_head_without_canonical_worktree(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "source.txt").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "candidate"], cwd=repo, check=True
    )
    candidate_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/work", candidate_head],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-D", "work"], cwd=repo, check=True)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}"
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
        test_command=command,
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        work_branch="work",
    )
    tracker = MagicMock()
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(tmp_path / "missing")
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)
    orch._branch_quality_gate = _gate(tmp_path / "quality.json", repo)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}

    assert orch._quality_gate_worktree(project, issue, "work") == ""
    assert orch._review_quality_gate_passes(project, issue, "work", "main")
    assert orch._review_quality_gate_passes(project, issue, "work", "main")

    assert counter.read_text(encoding="utf-8") == "x"
    assert tracker.add_comment.call_count == 1
    assert candidate_head in tracker.add_comment.call_args.args[1]


def test_orchestrator_fetches_accepted_head_into_stale_managed_clone(tmp_path):
    source, managed, submitted_head = _stale_managed_clone_with_submission(tmp_path)
    del source
    orch, project, issue, tracker, counter = _submitted_gate_orchestrator(
        tmp_path,
        managed,
        submitted_head,
    )
    network_git = orch._run_project_network_git
    orch._run_project_network_git = MagicMock(side_effect=network_git)

    assert (
        subprocess.run(
            [
                "git",
                "rev-parse",
                "--verify",
                "--quiet",
                "refs/remotes/origin/work",
            ],
            cwd=managed,
            check=False,
        ).returncode
        != 0
    )
    assert orch._review_quality_gate_passes(project, issue, "work", "main")
    assert orch._review_quality_gate_passes(project, issue, "work", "main")

    assert counter.read_text(encoding="utf-8") == "x"
    assert orch._run_project_network_git.call_count == 1
    assert (
        orch._quality_gate_commit(str(managed), "refs/remotes/origin/work")
        == submitted_head
    )
    assert tracker.update_issue.call_count == 0


def test_orchestrator_does_not_gate_newer_remote_than_accepted_head(tmp_path):
    source, managed, submitted_head = _stale_managed_clone_with_submission(tmp_path)
    (source / "source.txt").write_text("newer\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=source, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "newer candidate"],
        cwd=source,
        check=True,
    )
    newer_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "push", "-q", "origin", "work"], cwd=source, check=True)
    orch, project, issue, tracker, counter = _submitted_gate_orchestrator(
        tmp_path,
        managed,
        submitted_head,
    )

    assert not orch._review_quality_gate_passes(project, issue, "work", "main")

    assert not counter.exists()
    assert (
        orch._quality_gate_commit(str(managed), "refs/remotes/origin/work")
        == newer_head
    )
    tracker.add_comment.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_orchestrator_unavailable_submitted_head_is_infrastructure_only(tmp_path):
    _source, managed, _submitted_head = _stale_managed_clone_with_submission(tmp_path)
    missing_head = "a" * 40
    orch, project, issue, tracker, counter = _submitted_gate_orchestrator(
        tmp_path,
        managed,
        missing_head,
        branch="deleted-work",
    )

    assert not orch._review_quality_gate_passes(
        project,
        issue,
        "deleted-work",
        "main",
    )

    assert not counter.exists()
    tracker.update_issue.assert_not_called()
    comment = tracker.add_comment.call_args.args[1].lower()
    assert "candidate ci was not run" in comment
    assert "could not be fetched" in comment
    assert "no candidate ci-fix status was applied" in comment


def test_orchestrator_missing_review_head_is_infrastructure_not_ci_fix(tmp_path):
    repo = _git_repo(tmp_path)
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
        test_command="true",
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        work_branch="missing",
    )
    tracker = MagicMock()
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(tmp_path / "missing")
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)
    orch._branch_quality_gate = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}

    assert not orch._review_quality_gate_passes(
        project, issue, "missing", "main"
    )

    orch._branch_quality_gate.run.assert_not_called()
    tracker.update_issue.assert_not_called()
    comment = tracker.add_comment.call_args.args[1].lower()
    assert "infrastructure action required" in comment
    assert "candidate ci was not run" in comment


def test_orchestrator_discards_a_pass_when_the_branch_advances_during_gate(tmp_path):
    repo = _git_repo(tmp_path)
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
        test_command="true",
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        work_branch="work",
    )
    tracker = MagicMock()
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(repo)
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authorities = {}
    orch._standalone_delivery_authority_lock = threading.RLock()

    class AdvancingGate:
        def run(self, **kwargs):
            (repo / "source.txt").write_text("replacement\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "replacement"],
                cwd=repo,
                check=True,
            )
            return QualityGateResult(
                status="passed",
                head_sha=kwargs["expected_head_sha"],
                command=kwargs["command"],
            )

    orch._branch_quality_gate = AdvancingGate()

    assert not orch._review_quality_gate_passes(project, issue, "work", "main")
    tracker.add_comment.assert_not_called()


def test_standalone_review_gate_receives_live_delivery_authority(tmp_path):
    """Standalone gates re-read authority until their exact command finishes."""
    repo = _git_repo(tmp_path)
    head = BranchQualityGate._head_sha(str(repo))
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
        test_command="true",
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        state=READY_TO_INTEGRATE,
        work_branch="work",
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    project_store = MagicMock()
    project_store.get.return_value = project

    class RecordingGate:
        def run(self, **kwargs):
            self.kwargs = kwargs
            return QualityGateResult(
                status="passed",
                head_sha=kwargs["expected_head_sha"],
                command=kwargs["command"],
            )

    gate = RecordingGate()
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}
    orch._branch_quality_gate = gate
    orch._quality_gate_worktree = MagicMock(return_value=str(repo))
    orch._quality_gate_branch_head = MagicMock(return_value=head)

    assert orch._review_quality_gate_passes(project, issue, "work", "main")
    is_current = gate.kwargs["is_current"]
    assert callable(is_current)
    assert is_current()

    issue.state = OPEN
    assert not is_current()


def test_quality_gate_cleans_up_active_process_groups(tmp_path):
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = _gate(state, repo)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._active_processes.clear()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run, gate, repo, "sleep 60")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_processes:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("quality gate process was not tracked")

            assert BranchQualityGate.cleanup_active_processes() == 1
            result = future.result(timeout=5)

        assert result.status == "interrupted"
        assert result.cached is False
        assert not state.exists()
        with BranchQualityGate._processes_lock:
            assert BranchQualityGate._active_processes == {}
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_quality_gate_tracks_and_removes_processes_on_completion(tmp_path):
    repo = _git_repo(tmp_path)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._active_processes.clear()
    gate = _gate(tmp_path / "quality.json", repo)
    result = _run(gate, repo, "true")

    assert result.passed
    with BranchQualityGate._processes_lock:
        assert BranchQualityGate._active_processes == {}


def test_quality_gate_cleans_up_on_timeout(tmp_path):
    repo = _git_repo(tmp_path)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._active_processes.clear()
    gate = _gate(tmp_path / "quality.json", repo, timeout_seconds=1)
    result = _run(gate, repo, "sleep 10")

    assert result.status == "timed_out"
    with BranchQualityGate._processes_lock:
        assert BranchQualityGate._active_processes == {}


def test_explicit_retry_re_executes_failed_result(tmp_path):
    """Forced retry should bypass cache for failed results and re-execute."""
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    state = tmp_path / "quality.json"
    gate = _gate(state, repo)

    # First run: fails and is cached
    (repo / "work.txt").write_text("fail\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fail"], cwd=repo, check=True)
    failed = _run(gate, repo, f"echo fail; exit 1")
    assert failed.status == "failed" and not failed.cached

    # Second run: same head, cache hit for failure
    cached_fail = _run(gate, repo, f"echo fail; exit 1")
    assert cached_fail.status == "failed" and cached_fail.cached

    # Third run: forced retry should re-execute (not use cache)
    retry = _run(gate, repo, f"echo fail; exit 1", retry_forced=True)
    assert retry.status == "failed" and not retry.cached


def test_explicit_retry_re_executes_timeout_result(tmp_path):
    """Forced retry should bypass cache for timed_out results and re-execute."""
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = _gate(state, repo, timeout_seconds=1)

    # First run: times out
    timed_out = _run(gate, repo, "sleep 2")
    assert timed_out.status == "timed_out" and not timed_out.cached

    # Second run: same head, cache hit for timeout
    cached_timeout = _run(gate, repo, "sleep 2")
    assert cached_timeout.status == "timed_out" and cached_timeout.cached

    # Third run: forced retry should re-execute (not use cache)
    retry = _run(gate, repo, "sleep 2", retry_forced=True)
    assert retry.status == "timed_out" and not retry.cached


def test_explicit_retry_re_executes_failed_with_non_zero_exit(tmp_path):
    """Forced retry should bypass cache for failed results (non-zero exit) and re-execute."""
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = _gate(state, repo)

    # First run: fails with non-zero exit code
    failed = _run(gate, repo, "sh -c 'echo error; exit 42'")
    assert failed.status == "failed" and not failed.cached

    # Second run: same head, cache hit for failure
    cached_failed = _run(gate, repo, "sh -c 'echo error; exit 42'")
    assert cached_failed.status == "failed" and cached_failed.cached

    # Third run: forced retry should re-execute (not use cache)
    retry = _run(gate, repo, "sh -c 'echo error; exit 42'", retry_forced=True)
    assert retry.status == "failed" and not retry.cached


def test_explicit_retry_preserves_passed_cache(tmp_path):
    """Forced retry should NOT bypass cache for passed results."""
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}"
    state = tmp_path / "quality.json"
    gate = _gate(state, repo)

    # First run: passes and is cached
    first = _run(gate, repo, command)
    assert first.passed and not first.cached

    # Second run: same head, cache hit for pass
    second = _run(gate, repo, command)
    assert second.passed and second.cached
    assert counter.read_text(encoding="utf-8") == "x"

    # Third run: forced retry should still use cache for passed result
    retry = _run(gate, repo, command, retry_forced=True)
    assert retry.passed and retry.cached
    # Counter should not increment (command was not re-executed)
    assert counter.read_text(encoding="utf-8") == "x"


def test_explicit_retry_can_recover_from_transient_failure(tmp_path):
    """When a transient failure is retried with retry_forced, it can pass."""
    repo = _git_repo(tmp_path)
    trigger = tmp_path / "trigger"
    state = tmp_path / "quality.json"
    gate = _gate(state, repo)
    trigger.write_text("fail\n", encoding="utf-8")

    # First run: fails (trigger file exists)
    failed = _run(gate, repo, f"test -f {shlex.quote(str(trigger))} && exit 1 || true")
    assert failed.status == "failed"

    # Second run: same head, cache hit
    cached = _run(gate, repo, f"test -f {shlex.quote(str(trigger))} && exit 1 || true")
    assert cached.cached

    # Remove the failure trigger
    trigger.unlink()

    # Third run: forced retry bypasses cache, re-executes, and passes
    retry = _run(gate, repo, f"test -f {shlex.quote(str(trigger))} && exit 1 || true", retry_forced=True)
    assert retry.status == "passed" and not retry.cached


# ---------------------------------------------------------------------------
# Deterministic pre-spawn barrier tests
# These cover the three live failure windows identified in OOMPAH-657.
# ---------------------------------------------------------------------------


def test_tombstone_set_before_run_stops_gate_at_first_barrier(tmp_path):
    """cancel_generation before run() prevents any snapshot or spawn.

    Barrier 1: The tombstone is checked before snapshot creation. A gate
    cancelled by the tracker transition to Open/rejected before it even
    starts must not create a snapshot or run the command.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))

    # Tombstone the generation before run() is called.  This simulates
    # _retire_inactive_integration_rows cancelling the generation when the
    # tracker moves a task from Ready to Integrate to Open before the gate
    # loop has a chance to spawn the process.
    BranchQualityGate.cancel_generation("pre-spawn-gen")
    try:
        result = _run(
            gate,
            repo,
            f"touch {shlex.quote(str(marker))}",
            expected_head_sha=head,
            generation="pre-spawn-gen",
        )

        assert result.status == "interrupted"
        assert not marker.exists()
        # The tombstone must be cleaned up after the gate exits.
        with BranchQualityGate._processes_lock:
            assert "pre-spawn-gen" not in BranchQualityGate._cancelled_generations
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard("pre-spawn-gen")


def test_is_current_false_before_snapshot_stops_gate_at_barrier_one(tmp_path):
    """is_current() returning False before snapshot creation stops the gate.

    Barrier 1: authority is checked before snapshot creation so the archive
    is never materialised when the task is no longer
    authorised.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))

    result = _run(
        gate,
        repo,
        f"touch {shlex.quote(str(marker))}",
        expected_head_sha=head,
        generation="barrier1-gen",
        # Authority already withdrawn — simulates a Ready-to-Open transition
        # that completes before the gate even acquires the key lock.
        is_current=lambda: False,
    )

    assert result.status == "interrupted"
    assert not marker.exists()
    # No snapshot should have been created.
    with BranchQualityGate._processes_lock:
        assert not BranchQualityGate._active_snapshots


def test_is_current_false_after_snapshot_stops_gate_before_spawn(tmp_path):
    """is_current() returning False after snapshot but before Popen stops gate.

    Barrier 2: authority is rechecked after the snapshot completes and before
    subprocess.Popen() is called,
    closing the window where cancel_generation() arrived during worktree
    creation but found no registered process to kill.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    original_create = BranchQualityGate._snapshot_candidate_worktree

    # Simulate authority being withdrawn mid-snapshot by flipping the
    # authority flag after immutable archive extraction returns.
    authority = threading.Event()
    authority.set()

    def _create_and_revoke(repo_path: str, run_root: Path, head_sha: str = "HEAD"):
        snap = original_create(repo_path, run_root, head_sha)
        # Revoke authority to simulate the Ready-to-Open transition arriving
        # while the worktree was being created.
        authority.clear()
        return snap

    gate._snapshot_candidate_worktree = staticmethod(_create_and_revoke)
    try:
        result = _run(
            gate,
            repo,
            f"touch {shlex.quote(str(marker))}",
            expected_head_sha=head,
            generation="barrier2-gen",
            is_current=authority.is_set,
        )

        assert result.status == "interrupted"
        assert not marker.exists()
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_tombstone_during_snapshot_stops_gate_at_barrier_two(tmp_path):
    """cancel_generation() during snapshot creation stops gate before spawn.

    This covers the same Barrier 2 window as the is_current variant but
    uses the tombstone path: cancel_generation() is called on a thread
    that blocks inside the (mocked) snapshot creation and the gate must
    not proceed to Popen even though it was not yet registered.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    original_create = BranchQualityGate._snapshot_candidate_worktree

    snapshot_started = threading.Event()

    def _slow_create(repo_path: str, run_root: Path, head_sha: str = "HEAD"):
        snapshot_started.set()
        # Block until the test thread has set the tombstone.
        while "tombstone-during-snap" not in BranchQualityGate._cancelled_generations:
            time.sleep(0.01)
        return original_create(repo_path, run_root, head_sha)

    gate._snapshot_candidate_worktree = staticmethod(_slow_create)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                f"touch {shlex.quote(str(marker))}",
                expected_head_sha=head,
                generation="tombstone-during-snap",
            )
            # Wait until the gate is inside the (slow) snapshot creation,
            # then tombstone it to simulate a Ready-to-Open row retirement
            # arriving while the worktree is being materialised.
            assert snapshot_started.wait(timeout=5), "snapshot hook not reached"
            BranchQualityGate.cancel_generation("tombstone-during-snap")
            result = future.result(timeout=10)

        assert result.status == "interrupted"
        assert not marker.exists()
        # Tombstone must be cleaned up.
        with BranchQualityGate._processes_lock:
            assert "tombstone-during-snap" not in BranchQualityGate._cancelled_generations
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard("tombstone-during-snap")


def test_tombstone_set_between_popen_and_registration_stops_gate(tmp_path):
    """cancel_generation() between Popen and registration terminates the process.

    Barrier 3: the gate checks the tombstone under _processes_lock immediately
    after registering the process (the same lock cancel_generation uses), so a
    cancel that races Popen will kill the just-spawned process and return
    interrupted rather than letting the command run to completion.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    original_create = BranchQualityGate._snapshot_candidate_worktree

    snapshot_done = threading.Event()

    def _create_and_signal(repo_path: str, run_root: Path, head_sha: str = "HEAD"):
        snap = original_create(repo_path, run_root, head_sha)
        # Signal that the snapshot is ready; the test thread will tombstone
        # the generation while Popen is being called.  The gate must still
        # detect the cancel via barrier 3 (post-registration check).
        snapshot_done.set()
        return snap

    gate._snapshot_candidate_worktree = staticmethod(_create_and_signal)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                f"sleep 30 && touch {shlex.quote(str(marker))}",
                expected_head_sha=head,
                generation="popen-to-reg-gen",
            )
            # Wait until after snapshot creation, then tombstone to simulate
            # the Popen-to-registration window cancellation.
            assert snapshot_done.wait(timeout=5), "snapshot hook not reached"
            BranchQualityGate.cancel_generation("popen-to-reg-gen")
            result = future.result(timeout=10)

        assert result.status == "interrupted"
        assert not marker.exists()
        with BranchQualityGate._processes_lock:
            assert "popen-to-reg-gen" not in BranchQualityGate._cancelled_generations
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard("popen-to-reg-gen")


def test_cancelled_generation_stays_tombstoned_for_waiting_same_generation(tmp_path):
    """One interrupted caller cannot revive another caller waiting on its key."""
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    head = BranchQualityGate._head_sha(str(repo))
    marker = tmp_path / "must-not-run"
    generation = "shared-generation"
    command = f"sleep 30; touch {shlex.quote(str(marker))}"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(
                _run,
                gate,
                repo,
                command,
                expected_head_sha=head,
                generation=generation,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_generations:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("first quality gate was not active")

            # The second caller registers before it waits on the same
            # evidence key.  Cancelling the generation must fence both
            # callers, rather than allowing the waiter to launch after the
            # first caller's cleanup runs.
            second = pool.submit(
                _run,
                gate,
                repo,
                command,
                expected_head_sha=head,
                generation=generation,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._generation_run_counts.get(generation) == 2:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("second quality gate did not wait on the key")

            assert BranchQualityGate.cancel_generation(generation) == 1
            assert first.result(timeout=10).status == "interrupted"
            assert second.result(timeout=10).status == "interrupted"

        assert not marker.exists()
        with BranchQualityGate._processes_lock:
            assert generation not in BranchQualityGate._cancelled_generations
            assert generation not in BranchQualityGate._generation_run_counts
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard(generation)
            BranchQualityGate._generation_run_counts.pop(generation, None)


def test_single_flight_locks_are_released_after_unique_evidence(tmp_path):
    """Completed evidence keys do not leave an unbounded lock registry."""
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)

    for index in range(20):
        result = _run(gate, repo, f"true # evidence-{index}")
        assert result.passed

    assert gate._key_locks == {}


def test_cancel_before_spawn_tombstones_are_bounded(monkeypatch):
    """Abandoned pre-spawn generations cannot grow process state forever."""
    monkeypatch.setattr(BranchQualityGate, "_MAX_CANCELLED_GENERATIONS", 2)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._cancelled_generations.clear()
        BranchQualityGate._cancelled_generation_order.clear()
        BranchQualityGate._generation_run_counts.clear()
    try:
        for generation in ("oldest", "middle", "newest"):
            BranchQualityGate.cancel_generation(generation)

        with BranchQualityGate._processes_lock:
            assert "oldest" not in BranchQualityGate._cancelled_generations
            assert BranchQualityGate._cancelled_generations == {"middle", "newest"}
    finally:
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.clear()
            BranchQualityGate._cancelled_generation_order.clear()
            BranchQualityGate._generation_run_counts.clear()


def test_snapshot_archive_uses_the_requested_exact_head(tmp_path):
    """The disposable archive is materialised from the submitted head, not HEAD."""
    repo = _git_repo(tmp_path)
    head = BranchQualityGate._head_sha(str(repo))
    (repo / "source.txt").write_text("replacement\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "replacement"], cwd=repo, check=True)
    run_root = BranchQualityGate._gate_run_root()
    try:
        snapshot = BranchQualityGate._snapshot_candidate_worktree(
            str(repo), run_root, head
        )
        assert (snapshot / "source.txt").read_text(encoding="utf-8") == "one\n"
    finally:
        BranchQualityGate._cleanup_gate_run_root(run_root)


def test_preflight_rejects_old_branch_without_oompah652_ancestor(tmp_path):
    """Branches created before OOMPAH-652 commit lack the safety head in ancestry and must rebase."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "lesserevil@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )

    # Create an orphan branch that does not contain OOMPAH-652 commit in ancestry.
    # This simulates an old preserved branch from before the safety commit.
    subprocess.run(["git", "checkout", "--orphan", "old-branch"], cwd=repo, check=True)

    # Create a Makefile without OOMPAH-652 safety head in ancestry
    old_makefile = repo / "Makefile"
    old_makefile.write_text(
        """
.PHONY: test
test:
\t@pytest
PID_FILE ?= .oompah.pid
PORT ?= 8080
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "old makefile"], cwd=repo, check=True)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))

    result = _run(gate, repo, "true")

    assert result.status == "needs_rebase"
    assert "OOMPAH-652" in result.output_tail or "isolation contract" in result.output_tail


def test_preflight_allows_branch_with_oompah652_ancestor(tmp_path):
    """Branches descended from OOMPAH-652 safety head are allowed to execute."""
    repo = _git_repo(tmp_path)
    # _git_repo() already creates the repo as a descendant of OOMPAH-652
    # (by checking out main before creating the work branch)
    gate = _gate(tmp_path / "quality.json", repo)
    counter = tmp_path / "counter"

    result = _run(gate, repo, f"printf x >> {shlex.quote(str(counter))}")

    assert result.passed
    assert counter.read_text(encoding="utf-8") == "x"


def test_preflight_git_ancestry_check_is_primary(tmp_path):
    """
    Git ancestry verification is the primary enforcement mechanism.
    A branch without OOMPAH-652 ancestor is rejected regardless of Makefile state.
    """
    # Create a repo without OOMPAH-652 in ancestry
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "lesserevil@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )

    subprocess.run(["git", "checkout", "--orphan", "orphan-branch"], cwd=repo, check=True)
    
    # No Makefile at all - just create a minimal commit
    source = repo / "source.txt"
    source.write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "first"], cwd=repo, check=True)

    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    result = _run(gate, repo, "true")

    # Should fail on ancestry check, not Makefile check
    assert result.status == "needs_rebase"
    assert "OOMPAH-652" in result.output_tail or "isolation contract" in result.output_tail


def test_spoofed_markers_without_oompah652_ancestor_is_rejected(tmp_path):
    """
    A Makefile containing spoofed OOMPAH-652 marker strings but lacking proper
    git ancestry is rejected at preflight before execution. This proves that
    git ancestry verification (not substring matching) is the enforcement boundary.

    The hostile code never executes—we verify this by checking for sentinel
    side effects that would only occur if the command ran.
    """
    # Create a repo WITHOUT OOMPAH-652 in ancestry (orphan branch)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "lesserevil@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )

    # Create orphan branch simulating an old preserved branch from before OOMPAH-652
    subprocess.run(["git", "checkout", "--orphan", "old-branch"], cwd=repo, check=True)
    # In an orphan branch, the working directory may already be empty or have content.
    # We just need to ensure the branch doesn't descend from safety_head.

    # Create a Makefile with spoofed markers to prove substring matching would fail
    # but WITH hostile code that tries to discover the operator service.
    # If preflight is bypassed, this command WILL create a sentinel file.
    sentinel = tmp_path / "hostile_executed"
    hostile_makefile = repo / "Makefile"
    hostile_makefile.write_text(
        f"""
# Spoofed markers (substring matching would pass)
# OOMPAH_PYTEST_GATE reference in comments
# OOMPAH_TEST_PID_FILE in variable name
# OOMPAH_PYTEST_RUN_ROOT somewhere
# OOMPAH_TEST_SERVER_PORT here

.PHONY: test
test:
\t@touch {shlex.quote(str(sentinel))}
\t@echo "Attempting to discover operator service..."
\t@test -f .oompah.pid && echo "FOUND OPERATOR PID FILE" || true
\t@curl -s http://127.0.0.1:8090/healthz && echo "FOUND OPERATOR SERVICE" || true
\t@if [ -f .oompah.pid ]; then kill -0 $$(cat .oompah.pid) 2>/dev/null && echo "OPERATOR PID ALIVE"; fi || true

PID_FILE = .oompah.pid
PORT = 8080
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "spoofed makefile"], cwd=repo, check=True)
    
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    
    # Try to run the hostile command
    result = _run(gate, repo, "make test")
    
    # Verify branch was rejected at preflight (ancestry check failed)
    assert result.status == "needs_rebase"
    assert "OOMPAH-652" in result.output_tail or "isolation contract" in result.output_tail
    
    # CRITICAL: Verify the hostile code was NEVER executed
    # The sentinel file should NOT exist because the command was rejected before running
    assert not sentinel.exists(), (
        "Hostile code executed! Preflight did not prevent command execution. "
        "This means git ancestry verification is broken."
    )
    # Also verify hostile discovery output doesn't appear
    assert "FOUND OPERATOR" not in result.output_tail
    assert "ATTEMPTING TO DISCOVER" not in result.output_tail.upper()


def test_branch_with_oompah652_ancestor_allows_execution(tmp_path):
    """
    Branches descended from OOMPAH-652 safety head pass the preflight ancestry check
    and are allowed to execute. The git history requirement ensures they contain
    the isolation contract, regardless of what the Makefile says.
    """
    repo = _git_repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", repo)
    sentinel = tmp_path / "executed"

    # Branch is descended from OOMPAH-652 (created via _git_repo which checks out main)
    # Preflight passes ancestry check and command executes
    result = _run(gate, repo, f"touch {shlex.quote(str(sentinel))}")

    assert result.passed
    assert sentinel.exists(), "Command should have executed for OOMPAH-652 descendant"


def test_exact_gate_waits_for_shared_heavyweight_validation_capacity(tmp_path):
    repo = _git_repo(tmp_path)
    lease = ValidationResourceLease(
        tmp_path / "validation.sqlite3",
        poll_seconds=0.01,
    )
    auditor = lease.acquire(
        ValidationLeaseOwner.auditor(
            project_id="project",
            task_id="audit",
            authority_generation="attempt",
        )
    )
    gate = _gate(
        tmp_path / "quality.json",
        repo,
        validation_lease=lease,
    )
    sentinel = tmp_path / "gate-started"
    results: list[QualityGateResult] = []
    thread = threading.Thread(
        target=lambda: results.append(
            _run(gate, repo, f"touch {shlex.quote(str(sentinel))}")
        )
    )
    thread.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and lease.status().waiter_count != 1:
        time.sleep(0.01)

    assert lease.status().waiter_count == 1
    assert not sentinel.exists()
    auditor.release()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert results and results[0].passed
    assert sentinel.exists()
