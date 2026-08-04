"""Replayable fact corpus for historical stuck-workflow incidents.

The fixtures are intentionally independent of the current orchestrator.  They
describe authoritative input facts, the historical failure condition, and the
expected workflow decision.  Transition, evaluator, durable-job, restart,
liveness, and scale tests can therefore consume the same incidents without
copying one implementation's private state.

Task facts can be materialized through the real native Markdown tracker.  Git
topologies are built with real commit objects and refs.  Only unavailable
forge transport is represented by immutable review/audit evidence fields.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.workflow_contract import (
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_HUMAN,
    OPEN,
    READY_TO_INTEGRATE,
    TaskDisposition,
    WorkflowOwner,
)

CORPUS_VERSION = 1


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset | set):
        return sorted(_thaw(item) for item in value)
    if hasattr(value, "value"):
        return value.value
    return value


@dataclass(frozen=True, slots=True)
class TaskFixture:
    key: str
    title: str
    status: str
    issue_type: str = "task"
    parent: str | None = None
    finish_dependencies: tuple[str, ...] = ()
    hard_start_dependencies: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class GitCommitFixture:
    key: str
    parents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitRefFixture:
    name: str
    commit: str
    present: bool = True


@dataclass(frozen=True, slots=True)
class GitAncestryAssertion:
    ancestor: str
    descendant: str
    expected: bool


@dataclass(frozen=True, slots=True)
class GitTopologyFixture:
    commits: tuple[GitCommitFixture, ...]
    refs: tuple[GitRefFixture, ...]
    assertions: tuple[GitAncestryAssertion, ...]


@dataclass(frozen=True, slots=True)
class HistoricalFailure:
    code: str
    summary: str
    erroneous_status: str | None = None
    erroneous_effects: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExpectedDecision:
    reason_code: str
    disposition: TaskDisposition
    owner: WorkflowOwner
    status_updates: Mapping[str, str]
    durable_jobs: tuple[str, ...] = ()
    alert_severity: str = "none"
    invariants: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_updates", _freeze(self.status_updates))
        object.__setattr__(self, "evidence", _freeze(self.evidence))


@dataclass(frozen=True, slots=True)
class IncidentScenario:
    source_task_id: str
    slug: str
    title: str
    tasks: tuple[TaskFixture, ...]
    before: Mapping[str, Any]
    historical_failure: HistoricalFailure
    expected: ExpectedDecision
    after: Mapping[str, Any]
    git: GitTopologyFixture | None = None
    corpus_version: int = CORPUS_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "before", _freeze(self.before))
        object.__setattr__(self, "after", _freeze(self.after))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible fixture representation."""

        return _thaw(
            {
                "corpus_version": self.corpus_version,
                "source_task_id": self.source_task_id,
                "slug": self.slug,
                "title": self.title,
                "tasks": [
                    {
                        "key": task.key,
                        "title": task.title,
                        "status": task.status,
                        "issue_type": task.issue_type,
                        "parent": task.parent,
                        "finish_dependencies": task.finish_dependencies,
                        "hard_start_dependencies": task.hard_start_dependencies,
                        "metadata": task.metadata,
                    }
                    for task in self.tasks
                ],
                "before": self.before,
                "historical_failure": {
                    "code": self.historical_failure.code,
                    "summary": self.historical_failure.summary,
                    "erroneous_status": self.historical_failure.erroneous_status,
                    "erroneous_effects": self.historical_failure.erroneous_effects,
                },
                "expected": {
                    "reason_code": self.expected.reason_code,
                    "disposition": self.expected.disposition,
                    "owner": self.expected.owner,
                    "status_updates": self.expected.status_updates,
                    "durable_jobs": self.expected.durable_jobs,
                    "alert_severity": self.expected.alert_severity,
                    "invariants": self.expected.invariants,
                    "evidence": self.expected.evidence,
                },
                "after": self.after,
                "git": (
                    None
                    if self.git is None
                    else {
                        "commits": [
                            {"key": commit.key, "parents": commit.parents}
                            for commit in self.git.commits
                        ],
                        "refs": [
                            {
                                "name": ref.name,
                                "commit": ref.commit,
                                "present": ref.present,
                            }
                            for ref in self.git.refs
                        ],
                        "assertions": [
                            {
                                "ancestor": assertion.ancestor,
                                "descendant": assertion.descendant,
                                "expected": assertion.expected,
                            }
                            for assertion in self.git.assertions
                        ],
                    }
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class NativeTrackerReplay:
    tracker: OompahMarkdownTracker
    identifiers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class GitReplay:
    path: Path
    commits: Mapping[str, str]

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        result = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                self.commits.get(ancestor, ancestor),
                self.commits.get(descendant, descendant),
            ],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def ref_exists(self, name: str) -> bool:
        return (
            subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],
                cwd=self.path,
                check=False,
            ).returncode
            == 0
        )


def materialize_native_tracker(
    root: Path, scenario: IncidentScenario
) -> NativeTrackerReplay:
    """Replay scenario hierarchy and dependencies through the native tracker."""

    repo = root / "native"
    repo.mkdir(parents=True)
    tracker = OompahMarkdownTracker(
        active_states=[OPEN, IN_PROGRESS, READY_TO_INTEGRATE, IN_REVIEW, IN_VALIDATION],
        terminal_states=[DONE, MERGED],
        cwd=str(repo),
        default_branch="main",
        git_sync=False,
    )
    identifiers: dict[str, str] = {}
    for task in scenario.tasks:
        if task.parent and task.parent not in identifiers:
            raise ValueError(f"parent {task.parent!r} must precede child {task.key!r}")
        issue = tracker.create_issue(
            title=task.title,
            issue_type=task.issue_type,
            description=f"Historical incident fixture {scenario.source_task_id}/{task.key}",
            initial_status=task.status,
            parent=identifiers.get(task.parent or ""),
        )
        identifiers[task.key] = issue.identifier
        for field_name, value in task.metadata.items():
            tracker.set_metadata_field(issue.identifier, field_name, _thaw(value))
    for task in scenario.tasks:
        task_id = identifiers[task.key]
        for dependency in task.finish_dependencies:
            tracker.add_dependency(task_id, identifiers[dependency])
        for dependency in task.hard_start_dependencies:
            tracker.add_start_dependency(task_id, identifiers[dependency])
    return NativeTrackerReplay(tracker, MappingProxyType(identifiers))


def _git(path: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=path,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Oompah Incident Corpus",
            "GIT_AUTHOR_EMAIL": "incident@example.invalid",
            "GIT_COMMITTER_NAME": "Oompah Incident Corpus",
            "GIT_COMMITTER_EMAIL": "incident@example.invalid",
            "GIT_AUTHOR_DATE": "2026-08-04T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-08-04T00:00:00Z",
        },
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def materialize_git(root: Path, scenario: IncidentScenario) -> GitReplay:
    """Build the scenario's commit DAG and present/deleted branch refs."""

    if scenario.git is None:
        raise ValueError(f"scenario {scenario.source_task_id} has no Git topology")
    repo = root / "git"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    empty_tree = _git(repo, "mktree", input_text="")
    commits: dict[str, str] = {}
    for commit in scenario.git.commits:
        missing = [parent for parent in commit.parents if parent not in commits]
        if missing:
            raise ValueError(f"commit {commit.key!r} has unknown parents {missing!r}")
        args = ["commit-tree", empty_tree]
        for parent in commit.parents:
            args.extend(["-p", commits[parent]])
        sha = _git(repo, *args, input_text=f"{scenario.source_task_id}:{commit.key}\n")
        commits[commit.key] = sha
    for ref in scenario.git.refs:
        if ref.commit not in commits:
            raise ValueError(f"ref {ref.name!r} has unknown commit {ref.commit!r}")
        if ref.present:
            _git(repo, "update-ref", f"refs/heads/{ref.name}", commits[ref.commit])
    return GitReplay(repo, MappingProxyType(commits))


def detect_historical_failure(scenario: IncidentScenario) -> str | None:
    """Recognize the historical bug solely from authoritative before-facts."""

    before = scenario.before
    if scenario.source_task_id == "OOMPAH-562":
        rows = before["integration_rows"]
        blocked = any(
            row["state"] == "ready"
            and row["attempts"] == 0
            and row["dependency_status"] == MERGED
            and not row["dependency_reachable_from_epic"]
            for row in rows
        )
        return (
            scenario.historical_failure.code
            if blocked and not before["repair_job"]
            else None
        )
    if scenario.source_task_id == "OOMPAH-731":
        mismatch = (
            before["maintenance_published"]
            and before["ordinary_child_queue_enqueued"]
            and before["registered_checkout_head"] != before["published_epic_head"]
        )
        return scenario.historical_failure.code if mismatch else None
    if scenario.source_task_id == "OOMPAH-732":
        churn = (
            before["remote_head"] == before["accepted_head"]
            and before["delivery_evidence_before"] == before["delivery_evidence_after"]
            and before["tracker_updated_at_before"]
            != before["tracker_updated_at_after"]
            and before["authority_revoked"]
        )
        return scenario.historical_failure.code if churn else None
    if scenario.source_task_id == "OOMPAH-739":
        false_negative = (
            not before["parent_source_ref_exists"]
            and before["child_merged_audit_passed"]
            and before["parent_merged_audit_passed"]
            and before["parent_merge_commit_on_target"]
            and before["child_demoted"]
        )
        return scenario.historical_failure.code if false_negative else None
    if scenario.source_task_id == "OOMPAH-748":
        cycle = (
            before["child_landed_on_immediate_target"]
            and not before["parent_landed_on_root_target"]
            and before["child_merge_requires_parent_root_landing"]
            and before["parent_close_requires_child_merged"]
        )
        return scenario.historical_failure.code if cycle else None
    if scenario.source_task_id == "OOMPAH-749":
        starvation = (
            before["historical_integrated_rows"] > before["history_batch_budget"]
            and before["historical_replay_precedes_ready_claims"]
            and before["live_ready_attempts"] == 0
            and before["live_ready_lease_owner"] is None
        )
        return scenario.historical_failure.code if starvation else None
    if scenario.source_task_id == "OOMPAH-751":
        poisoning = (
            before["peer_authorized_at_discovery"]
            and not before["peer_authorized_at_send"]
            and before["send_http_status"] == 500
            and before["task_handoff_failure_recorded"]
            and before["worker_exit_status"] == NEEDS_HUMAN
        )
        return scenario.historical_failure.code if poisoning else None
    return None


INCIDENTS: tuple[IncidentScenario, ...] = (
    IncidentScenario(
        source_task_id="OOMPAH-562",
        slug="stale-epic-required-base",
        title="Ready integration rows have no claimable ordering when required code is absent",
        tasks=(
            TaskFixture("epic", "Stale parent epic", IN_PROGRESS, "epic"),
            TaskFixture("dependency", "Already merged prerequisite", MERGED),
            TaskFixture(
                "child",
                "Submitted private child",
                READY_TO_INTEGRATE,
                parent="epic",
                finish_dependencies=("dependency",),
                metadata={
                    "oompah.integration": {
                        "state": "ready",
                        "attempts": 0,
                        "task_branch": "epic-E--task-C",
                        "head_sha": "task-head",
                    }
                },
            ),
        ),
        before={
            "integration_rows": (
                {
                    "task": "child",
                    "state": "ready",
                    "attempts": 0,
                    "dependency_status": MERGED,
                    "dependency_reachable_from_epic": False,
                },
            ),
            "epic_behind_default_by": 26,
            "epic_ahead_of_default_by": 5,
            "repair_job": None,
        },
        historical_failure=HistoricalFailure(
            "historical.integration_required_base_deadlock",
            "claim_next returned no row and observation-only maintenance created no repair owner.",
            erroneous_status=READY_TO_INTEGRATE,
            erroneous_effects=("attempts_remain_zero", "no_owner", "no_reassessment"),
        ),
        expected=ExpectedDecision(
            "integration.required_base_missing",
            TaskDisposition.RETRY_SCHEDULED,
            WorkflowOwner.INTEGRATOR,
            {},
            durable_jobs=("epic_branch_reconciliation",),
            alert_severity="info",
            invariants=(
                "retry_has_wakeup",
                "hard_start_dependencies_gate_ownership",
                "restart_reconstructs_work",
            ),
            evidence={"dependency": "dependency", "target_branch": "epic-E"},
        ),
        after={
            "repair_job_state": "ready",
            "duplicate_repair_jobs": 0,
            "next_reassessment": "bounded",
            "private_head_preserved": True,
        },
        git=GitTopologyFixture(
            commits=(
                GitCommitFixture("base"),
                GitCommitFixture("dependency", ("base",)),
                GitCommitFixture("epic", ("base",)),
                GitCommitFixture("task", ("epic",)),
            ),
            refs=(
                GitRefFixture("main", "dependency"),
                GitRefFixture("epic-E", "epic"),
                GitRefFixture("epic-E--task-C", "task"),
            ),
            assertions=(
                GitAncestryAssertion("dependency", "epic", False),
                GitAncestryAssertion("epic", "task", True),
            ),
        ),
    ),
    IncidentScenario(
        source_task_id="OOMPAH-731",
        slug="direct-maintenance-self-invalidation",
        title="A successful direct epic rebase invalidates its own ordinary child submission",
        tasks=(
            TaskFixture("epic", "Shared epic", IN_PROGRESS, "epic"),
            TaskFixture(
                "maintenance",
                "Rebase epic-E onto main",
                OPEN,
                parent="epic",
                metadata={"oompah.work_branch": "epic-E"},
            ),
        ),
        before={
            "maintenance_published": True,
            "published_old_head": "epic-old",
            "published_epic_head": "epic-rebased",
            "registered_checkout_head": "epic-old",
            "registered_checkout_clean": True,
            "ordinary_child_queue_enqueued": True,
            "force_with_lease_proven": True,
        },
        historical_failure=HistoricalFailure(
            "historical.direct_maintenance_self_invalidated",
            "Ordinary integration compared the preserved pre-rebase checkout to the published ref.",
            erroneous_status=OPEN,
            erroneous_effects=("integration_retry_alert", "duplicate_work_invited"),
        ),
        expected=ExpectedDecision(
            "maintenance.publication_proven",
            TaskDisposition.OWNED,
            WorkflowOwner.AUDITOR,
            {"maintenance": IN_VALIDATION},
            durable_jobs=("terminal_audit_done",),
            invariants=(
                "stale_generation_fenced",
                "terminal_evidence_required",
                "containment_before_rollup",
            ),
            evidence={"old_head": "epic-old", "published_head": "epic-rebased"},
        ),
        after={
            "ordinary_integration_rows": 0,
            "registered_checkout_head": "epic-rebased",
            "terminal_target": DONE,
            "completion_count": 1,
            "old_head_recovery_ref_preserved": True,
        },
        git=GitTopologyFixture(
            commits=(
                GitCommitFixture("base"),
                GitCommitFixture("epic-old", ("base",)),
                GitCommitFixture("main-new", ("base",)),
                GitCommitFixture("epic-rebased", ("main-new",)),
            ),
            refs=(
                GitRefFixture("main", "main-new"),
                GitRefFixture("epic-E", "epic-rebased"),
                GitRefFixture("recovery/epic-E-old", "epic-old"),
            ),
            assertions=(
                GitAncestryAssertion("main-new", "epic-rebased", True),
                GitAncestryAssertion("epic-old", "epic-rebased", False),
            ),
        ),
    ),
    IncidentScenario(
        source_task_id="OOMPAH-732",
        slug="benign-metadata-authority-churn",
        title="Benign tracker timestamps revoke exact-head standalone delivery authority",
        tasks=(
            TaskFixture(
                "standalone",
                "Pushed standalone submission",
                READY_TO_INTEGRATE,
                metadata={
                    "oompah.integration": {
                        "state": "ready",
                        "task_branch": "task-S",
                        "head_sha": "standalone-head",
                    }
                },
            ),
        ),
        before={
            "accepted_head": "standalone-head",
            "remote_head": "standalone-head",
            "delivery_evidence_before": {
                "work_branch": "task-S",
                "head_sha": "standalone-head",
                "target_branch": "main",
            },
            "delivery_evidence_after": {
                "work_branch": "task-S",
                "head_sha": "standalone-head",
                "target_branch": "main",
            },
            "tracker_updated_at_before": "2026-08-03T17:39:00Z",
            "tracker_updated_at_after": "2026-08-03T17:40:00Z",
            "authority_revoked": True,
            "gate_or_review_created": False,
        },
        historical_failure=HistoricalFailure(
            "historical.benign_revision_revoked_delivery",
            "Volatile updated_at bookkeeping participated in the delivery generation fingerprint.",
            erroneous_status=READY_TO_INTEGRATE,
            erroneous_effects=("gate_cancelled", "no_review", "no_alert"),
        ),
        expected=ExpectedDecision(
            "standalone.delivery_eligible",
            TaskDisposition.RETRY_SCHEDULED,
            WorkflowOwner.INTEGRATOR,
            {},
            durable_jobs=("standalone_delivery",),
            invariants=(
                "stale_generation_fenced",
                "retry_has_wakeup",
                "bounded_wait_is_reassessed",
            ),
            evidence={"head_sha": "standalone-head", "target_branch": "main"},
        ),
        after={
            "authority_generation_changed": False,
            "delivery_job_count": 1,
            "shared_queue_independent": True,
            "next_reassessment": "bounded",
        },
    ),
    IncidentScenario(
        source_task_id="OOMPAH-739",
        slug="deleted-source-ref-after-verified-merge",
        title="Deleted historical source refs falsely demote verified nested Merged work",
        tasks=(
            TaskFixture("root", "Root epic", MERGED, "epic"),
            TaskFixture("parent", "Parent epic", MERGED, "epic", parent="root"),
            TaskFixture("child", "Nested child epic", MERGED, "epic", parent="parent"),
        ),
        before={
            "parent_source_ref_exists": False,
            "child_source_ref_exists": False,
            "child_merged_audit_passed": True,
            "parent_merged_audit_passed": True,
            "parent_merge_commit_on_target": True,
            "child_merge_commit_on_parent": True,
            "child_demoted": True,
            "new_review_or_audit_count": 2,
        },
        historical_failure=HistoricalFailure(
            "historical.deleted_ref_false_demotion",
            "Lifecycle enforcement equated an unavailable source ref with absent landing evidence.",
            erroneous_status=DONE,
            erroneous_effects=(
                "terminal_demotion",
                "review_resurrection",
                "audit_resurrection",
            ),
        ),
        expected=ExpectedDecision(
            "terminal.preserve_verified_merged",
            TaskDisposition.TERMINAL,
            WorkflowOwner.NONE,
            {},
            invariants=(
                "terminal_evidence_required",
                "final_states_do_not_auto_reopen",
                "containment_before_rollup",
            ),
            evidence={"audit_target": MERGED, "parent_merge_commit": "parent-on-main"},
        ),
        after={
            "child_status": MERGED,
            "parent_status": MERGED,
            "new_review_or_audit_count": 0,
            "uncertain_forge_result_mutates_status": False,
        },
        git=GitTopologyFixture(
            commits=(
                GitCommitFixture("root-base"),
                GitCommitFixture("child-head", ("root-base",)),
                GitCommitFixture("child-on-parent", ("root-base", "child-head")),
                GitCommitFixture("parent-head", ("child-on-parent",)),
                GitCommitFixture("parent-on-main", ("root-base", "parent-head")),
            ),
            refs=(
                GitRefFixture("main", "parent-on-main"),
                GitRefFixture("epic-parent", "parent-head", present=False),
                GitRefFixture("epic-child", "child-head", present=False),
            ),
            assertions=(
                GitAncestryAssertion("child-head", "parent-on-main", True),
                GitAncestryAssertion("parent-head", "parent-on-main", True),
            ),
        ),
    ),
    IncidentScenario(
        source_task_id="OOMPAH-748",
        slug="nested-immediate-target-cycle",
        title="Nested child Merged and parent close depend cyclically on each other",
        tasks=(
            TaskFixture("parent", "Root parent epic", DONE, "epic"),
            TaskFixture("child", "Nested epic", DONE, "epic", parent="parent"),
        ),
        before={
            "child_landed_on_immediate_target": True,
            "parent_landed_on_root_target": False,
            "child_merged_audit_passed": True,
            "child_merge_requires_parent_root_landing": True,
            "parent_close_requires_child_merged": True,
            "configured_child_target": "epic-parent",
        },
        historical_failure=HistoricalFailure(
            "historical.nested_landing_status_cycle",
            "Child Merged required root landing while root review required child Merged.",
            erroneous_status=DONE,
            erroneous_effects=("parent_review_blocked", "child_terminal_blocked"),
        ),
        expected=ExpectedDecision(
            "terminal.immediate_target_landing_proven",
            TaskDisposition.TERMINAL,
            WorkflowOwner.ROLLUP,
            {"child": MERGED},
            durable_jobs=("parent_rollup_review",),
            invariants=(
                "containment_before_rollup",
                "terminal_evidence_required",
                "restart_reconstructs_work",
            ),
            evidence={"immediate_target": "epic-parent", "child_head": "child-head"},
        ),
        after={
            "child_status": MERGED,
            "parent_root_status": DONE,
            "parent_rollup_unblocked": True,
            "premature_root_merged": False,
        },
        git=GitTopologyFixture(
            commits=(
                GitCommitFixture("main"),
                GitCommitFixture("parent-base", ("main",)),
                GitCommitFixture("child-head", ("parent-base",)),
                GitCommitFixture("child-on-parent", ("parent-base", "child-head")),
            ),
            refs=(
                GitRefFixture("main", "main"),
                GitRefFixture("epic-parent", "child-on-parent"),
                GitRefFixture("epic-child", "child-head", present=False),
            ),
            assertions=(
                GitAncestryAssertion("child-head", "child-on-parent", True),
                GitAncestryAssertion("child-head", "main", False),
            ),
        ),
    ),
    IncidentScenario(
        source_task_id="OOMPAH-749",
        slug="historical-audit-replay-starvation",
        title="Unbounded historical audit replay starves live Ready claims",
        tasks=(
            TaskFixture(
                "live",
                "Live Ready submission",
                READY_TO_INTEGRATE,
                metadata={
                    "oompah.integration": {
                        "state": "ready",
                        "attempts": 0,
                        "head_sha": "live-head",
                    }
                },
            ),
            TaskFixture("history", "Historical integrated task", DONE),
        ),
        before={
            "historical_integrated_rows": 500,
            "history_batch_budget": 32,
            "historical_replay_precedes_ready_claims": True,
            "live_ready_attempts": 0,
            "live_ready_lease_owner": None,
            "service_health": "healthy",
            "restart_count": 1,
        },
        historical_failure=HistoricalFailure(
            "historical.audit_replay_starved_ready_claim",
            "The driver replayed the unbounded integrated history before considering live work.",
            erroneous_status=READY_TO_INTEGRATE,
            erroneous_effects=("attempts_remain_zero", "no_lease", "false_healthy"),
        ),
        expected=ExpectedDecision(
            "integration.live_claim_precedes_history",
            TaskDisposition.OWNED,
            WorkflowOwner.INTEGRATOR,
            {},
            durable_jobs=("integration_attempt", "historical_audit_replay_batch"),
            invariants=(
                "single_active_owner",
                "bounded_wait_is_reassessed",
                "restart_reconstructs_work",
            ),
            evidence={"history_cursor": 0, "history_batch_budget": 32},
        ),
        after={
            "live_ready_attempts": 1,
            "live_ready_lease_owner": "integration-worker",
            "historical_rows_replayed": 32,
            "history_cursor": 32,
            "restart_resumes_cursor": True,
        },
    ),
    IncidentScenario(
        source_task_id="OOMPAH-751",
        slug="advisory-peer-denial-poisoning",
        title="Advisory coordination denial poisons successful task completion",
        tasks=(
            TaskFixture("sender", "Completed sender work", IN_PROGRESS),
            TaskFixture("peer", "Suggested peer", IN_REVIEW),
        ),
        before={
            "peer_authorized_at_discovery": True,
            "peer_authorized_at_send": False,
            "send_http_status": 500,
            "task_handoff_failure_recorded": True,
            "worker_auth_health_degraded": True,
            "own_head_pushed": True,
            "own_submit_permitted": True,
            "worker_exit_status": NEEDS_HUMAN,
        },
        historical_failure=HistoricalFailure(
            "historical.advisory_denial_poisoned_completion",
            "Expected fail-closed peer denial entered the actionable handoff-failure channel.",
            erroneous_status=NEEDS_HUMAN,
            erroneous_effects=(
                "http_500",
                "auth_health_degraded",
                "submission_poisoned",
            ),
        ),
        expected=ExpectedDecision(
            "coordination.policy_denied",
            TaskDisposition.OWNED,
            WorkflowOwner.IMPLEMENTER,
            {},
            alert_severity="info",
            invariants=(
                "stale_generation_fenced",
                "single_active_owner",
                "action_required_is_visible",
            ),
            evidence={"http_status": 403, "policy_result": "coordination_forbidden"},
        ),
        after={
            "send_http_status": 403,
            "response_code": "coordination_forbidden",
            "task_handoff_failure_recorded": False,
            "worker_auth_health_degraded": False,
            "own_submit_permitted": True,
            "worker_exit_status": IN_PROGRESS,
            "durable_message_rows": 0,
        },
    ),
)

INCIDENTS_BY_ID: Mapping[str, IncidentScenario] = MappingProxyType(
    {scenario.source_task_id: scenario for scenario in INCIDENTS}
)


def validate_incident_scenario(scenario: IncidentScenario) -> tuple[str, ...]:
    """Return structural/replay contract violations for one incident."""

    errors: list[str] = []
    if scenario.corpus_version != CORPUS_VERSION:
        errors.append("unsupported corpus version")
    if not scenario.source_task_id or not scenario.slug or not scenario.title:
        errors.append("scenario identity fields are required")
    keys = [task.key for task in scenario.tasks]
    if not keys or len(keys) != len(set(keys)):
        errors.append("task fixture keys must be non-empty and unique")
    seen: set[str] = set()
    for task in scenario.tasks:
        if task.parent and task.parent not in seen:
            errors.append(f"parent {task.parent!r} must precede child {task.key!r}")
        unknown_dependencies = (
            set(task.finish_dependencies) | set(task.hard_start_dependencies)
        ) - set(keys)
        if unknown_dependencies:
            errors.append(f"task {task.key!r} has unknown dependencies")
        seen.add(task.key)
    if not scenario.before or not scenario.after:
        errors.append("before and after facts are required")
    if not scenario.historical_failure.code.startswith("historical."):
        errors.append("historical failure code must use the historical namespace")
    if not scenario.expected.reason_code or not scenario.expected.invariants:
        errors.append("expected decision reason and invariants are required")
    unknown_updates = set(scenario.expected.status_updates) - set(keys)
    if unknown_updates:
        errors.append("expected status updates reference unknown task keys")
    if scenario.expected.alert_severity not in {"none", "info", "warning", "critical"}:
        errors.append("expected alert severity is invalid")
    detected = detect_historical_failure(scenario)
    if detected != scenario.historical_failure.code:
        errors.append("before facts do not reproduce the declared historical failure")
    if scenario.git is not None:
        commit_keys = [commit.key for commit in scenario.git.commits]
        if len(commit_keys) != len(set(commit_keys)):
            errors.append("Git commit fixture keys are not unique")
        known: set[str] = set()
        for commit in scenario.git.commits:
            if set(commit.parents) - known:
                errors.append(f"Git commit {commit.key!r} references a future parent")
            known.add(commit.key)
        for ref in scenario.git.refs:
            if ref.commit not in known:
                errors.append(f"Git ref {ref.name!r} references an unknown commit")
        for assertion in scenario.git.assertions:
            if {assertion.ancestor, assertion.descendant} - known:
                errors.append("Git ancestry assertion references an unknown commit")
    return tuple(errors)


def stable_corpus_json() -> str:
    """Return deterministic JSON for snapshots, hashes, and restart replays."""

    return json.dumps([scenario.to_dict() for scenario in INCIDENTS], sort_keys=True)


_corpus_errors = {
    scenario.source_task_id: validate_incident_scenario(scenario)
    for scenario in INCIDENTS
    if validate_incident_scenario(scenario)
}
if _corpus_errors:
    raise ValueError(f"invalid historical workflow incident corpus: {_corpus_errors!r}")
