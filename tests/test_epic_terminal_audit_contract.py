"""End-to-end terminal-audit contract for shared and nested epics.

The fixture deliberately drives the tracker protocol instead of a live forge.
Native Markdown, GitHub, and GitLab adapters all persist the same audit
document, while the coordinator remains the only component allowed to apply
terminal statuses.  The tests here cover the cross-component edges that are
easy to miss when the individual coordinator and epic-rollup suites are run
in isolation.

The independent-auditor and repair-planner cases are gated until their
blocking task branches are integrated.  Keeping those cases here means the
same contract starts running automatically when the corresponding production
interfaces land; it does not require network access or a second test suite.
"""

from __future__ import annotations

import asyncio
import copy
import subprocess
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.github_tracker import GitHubAuth, GitHubIssueTracker
from oompah.gitlab_tracker import GitLabIssueTracker
from oompah.models import Issue
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import Orchestrator
from oompah.statuses import DONE, IN_VALIDATION, MERGED, OPEN
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_evidence_fingerprint,
)
from oompah.terminal_audit_enforcement import TerminalAuditEnforcement
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import (
    AuditResult,
    TerminalTransitionCoordinator,
)


PROJECT_ID = "project-shared"
EPIC_ID = "EPIC-1"
NESTED_EPIC_ID = "EPIC-2"
TASK_ID = "TASK-1"
EPIC_BRANCH = f"epic-{EPIC_ID}"
NESTED_EPIC_BRANCH = f"epic-{NESTED_EPIC_ID}"


class _LockStore:
    """Thread-safe project lock provider used by the real metadata store."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def project_write_lock(self, project_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(project_id, threading.RLock())


class _GitHubMetadataClient:
    def __init__(self) -> None:
        self.body = "Human-owned issue body"

    def request(self, method: str, _path: str, **_kwargs):
        assert method == "GET"
        return {"body": self.body}, object()

    def patch(self, _path: str, *, json: dict[str, str]) -> None:
        self.body = json["body"]


class _GitLabMetadataClient:
    def __init__(self) -> None:
        self.description = "Human-owned issue description"

    def request(self, method: str, _path: str, **kwargs):
        if method == "PUT":
            self.description = kwargs["json"]["description"]
        return {"description": self.description, "labels": []}, object()


@pytest.fixture(params=["native", "github", "gitlab"])
def lifecycle_tracker(request: pytest.FixtureRequest, tmp_path):
    """Real tracker adapters backed by deterministic local transports."""

    if request.param == "native":
        root = tmp_path / "native"
        root.mkdir()
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=False,
        )
        identifier = tracker.create_issue("Shared epic terminal audit").identifier
    elif request.param == "github":
        tracker = GitHubIssueTracker(
            owner="example-org",
            repo="tasks",
            active_states=[OPEN],
            terminal_states=[DONE],
            auth=GitHubAuth(pat="test-token"),
        )
        tracker._client = _GitHubMetadataClient()  # type: ignore[assignment]
        identifier = "example-org/tasks#1"
    else:
        try:
            tracker = GitLabIssueTracker(
                project="group/project",
                active_states=[OPEN],
                terminal_states=[DONE],
                client=_GitLabMetadataClient(),
            )
        except (ImportError, ModuleNotFoundError) as exc:
            pytest.skip(f"recovered GitLab adapter is unavailable: {exc}")
        identifier = "group/project#1"

    # TerminalTransitionCoordinator calls these protocol methods after the
    # metadata CAS.  Recording them keeps the adapter contract observable
    # without asking an external forge to mutate anything.
    tracker.update_issue = MagicMock()  # type: ignore[method-assign]
    tracker.add_comment = MagicMock(return_value={})  # type: ignore[method-assign]
    # These adapter-contract tests supply the complete normalized Issue that
    # owns the expected fingerprint.  Live-detail refresh is covered by the
    # coordinator regression suite; the local forge doubles intentionally do
    # not implement that separate transport contract.
    tracker.fetch_issue_detail = None  # type: ignore[method-assign]
    return tracker, identifier


def _issue(identifier: str = TASK_ID, *, state: str = OPEN, issue_type: str = "task") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Audit {identifier}",
        description="Shared epic audit requirements.",
        state=state,
        issue_type=issue_type,
        project_id=PROJECT_ID,
        branch_name=EPIC_BRANCH,
        work_branch=EPIC_BRANCH,
    )


def _contributors() -> tuple[ContributorIdentity, ...]:
    return (
        ContributorIdentity("provider-a/model-a", "model"),
        ContributorIdentity("provider-b/model-b", "model"),
        ContributorIdentity("provider-c/model-c", "model"),
    )


def _evidence(
    task_id: str = TASK_ID,
    *,
    source_branch: str = EPIC_BRANCH,
    target_branch: str = "main",
    child_audit_digests: tuple[str, ...] = (),
    contributors: tuple[ContributorIdentity, ...] | None = None,
) -> EvidenceFingerprint:
    return compute_evidence_fingerprint(
        requirements_text="Shared epic audit requirements.",
        project_id=PROJECT_ID,
        task_id=task_id,
        source_branch=source_branch,
        source_sha="child-sha",
        target_branch=target_branch,
        target_sha="target-sha",
        review_id="review-7",
        review_state="merged",
        child_audit_digests=child_audit_digests,
        contributors=contributors if contributors is not None else _contributors(),
    )


def _coordinator(tracker) -> TerminalTransitionCoordinator:
    return TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=_LockStore(),
        post_comments=True,
    )


@pytest.fixture(autouse=True)
def deterministic_audit_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep audit record timestamps stable while exercising race paths."""

    monkeypatch.setattr(
        "oompah.terminal_transition_coordinator._now_iso8601",
        lambda: "2026-07-29T00:00:00+00:00",
    )


def _run(coro):
    return asyncio.run(coro)


def _pass_result(record: TerminalAuditRecord, attempt_id: str) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.PASS,
        message="Deterministic audit passed; required tests and landing evidence are present.",
        attempt_id=attempt_id,
    )


def _records(tracker, identifier: str) -> list[TerminalAuditRecord]:
    store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
    return list(store.read(identifier).pending_chain)


def test_shared_nested_evidence_requires_every_contributor_and_child_audit() -> None:
    """A rollup fingerprint changes if any contributor or nested audit changes."""

    contributors = _contributors()
    nested = _evidence(
        NESTED_EPIC_ID,
        source_branch=NESTED_EPIC_BRANCH,
        target_branch=EPIC_BRANCH,
        contributors=contributors[:2],
    )
    full = _evidence(
        EPIC_ID,
        source_branch=EPIC_BRANCH,
        target_branch="main",
        child_audit_digests=(nested.digest,),
        contributors=contributors,
    )

    # Input ordering is not significant, but omitting any contributor or the
    # nested chain digest must invalidate the rollup evidence.
    reordered = _evidence(
        EPIC_ID,
        child_audit_digests=(nested.digest,),
        contributors=tuple(reversed(contributors)),
    )
    assert reordered == full
    for index in range(len(contributors)):
        assert _evidence(
            EPIC_ID,
            child_audit_digests=(nested.digest,),
            contributors=contributors[:index] + contributors[index + 1 :],
        ) != full
    assert _evidence(EPIC_ID, child_audit_digests=()) != full
    assert _evidence(EPIC_ID, child_audit_digests=("changed-child-audit",)) != full


def test_nested_rollup_requires_merged_nested_epic_and_blocks_in_validation_child() -> None:
    """Nested epics use Merged evidence; In Validation remains nonterminal."""

    gate = MagicMock()
    gate._epic_branch_for_issue.return_value = EPIC_BRANCH
    gate._child_landing_evidence_block_reason.return_value = None
    top = _issue(EPIC_ID, issue_type="epic")
    leaf = _issue("LEAF-1", state=DONE)
    nested = _issue(NESTED_EPIC_ID, state=MERGED, issue_type="epic")

    assert (
        Orchestrator._epic_rollup_children_block_reason(
            gate, top, [leaf, nested]
        )
        is None
    )
    blocked = Orchestrator._epic_rollup_children_block_reason(
        gate,
        top,
        [leaf, _issue("AUDIT-1", state=IN_VALIDATION)],
    )
    assert blocked is not None
    assert "AUDIT-1" in blocked
    assert IN_VALIDATION in blocked


def test_shared_child_landing_evidence_uses_local_and_remote_bare_refs(tmp_path) -> None:
    """A child commit contained by the shared epic branch is valid evidence."""

    repo = tmp_path / "managed-repo"
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
    subprocess.run(
        ["git", "init", "--quiet", "-b", "main", str(repo)], check=True
    )

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Audit Contract")
    (repo / "README").write_text("base\n", encoding="utf-8")
    git("add", "README")
    git("commit", "--quiet", "-m", "base")
    git("branch", EPIC_BRANCH)
    git("checkout", "--quiet", "-b", "child-1")
    (repo / "child.txt").write_text("child\n", encoding="utf-8")
    git("add", "child.txt")
    git("commit", "--quiet", "-m", "child")
    git("checkout", "--quiet", EPIC_BRANCH)
    git("merge", "--quiet", "--ff-only", "child-1")
    git("remote", "add", "origin", str(remote))
    git("push", "--quiet", "--all", "origin")

    project_store = MagicMock()
    project_store.get.return_value = SimpleNamespace(repo_path=str(repo))
    harness = SimpleNamespace(
        project_store=project_store,
        _resolve_git_branch_refs=Orchestrator._resolve_git_branch_refs,
    )
    epic = _issue(EPIC_ID, issue_type="epic")
    child = _issue("child-1", state=DONE)
    child.work_branch = "child-1"

    reason = Orchestrator._child_landing_evidence_block_reason(
        harness,
        epic,
        child,
        expected_work_branch=EPIC_BRANCH,
        container_branches=(EPIC_BRANCH,),
    )
    assert reason is None


@pytest.mark.parametrize("target", [TargetState.DONE, TargetState.MERGED])
def test_done_and_merged_audits_follow_shared_branch_chain(lifecycle_tracker, target) -> None:
    """The same terminal contract applies to every supported tracker adapter."""

    tracker, identifier = lifecycle_tracker
    issue = _issue(identifier, state=OPEN, issue_type="epic")
    fingerprint = _evidence(
        identifier,
        source_branch=NESTED_EPIC_BRANCH if target is TargetState.MERGED else EPIC_BRANCH,
        target_branch=EPIC_BRANCH if target is TargetState.MERGED else "main",
        child_audit_digests=("nested-audit-pass",) if target is TargetState.MERGED else (),
    )
    coordinator = _coordinator(tracker)

    staged = _run(
        coordinator.request_transition(
            issue,
            target,
            ContributorIdentity("rollup-trigger", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.success
    records = _records(tracker, identifier)
    expected_targets = (
        [TargetState.DONE]
        if target is TargetState.DONE
        else [TargetState.DONE, TargetState.MERGED]
    )
    assert [record.target_state for record in records] == expected_targets
    assert all(record.evidence_fingerprint == fingerprint for record in records)
    assert any(call.kwargs.get("status") == IN_VALIDATION for call in tracker.update_issue.call_args_list)

    if target is TargetState.DONE:
        outcome = _run(
            coordinator.apply_audit_result(
                replace_issue(issue, state=IN_VALIDATION),
                _pass_result(records[0], "done-attempt"),
                PROJECT_ID,
            )
        )
        assert outcome.applied_status == DONE
        assert tracker.update_issue.call_args_list[-1].kwargs["status"] == DONE
        return

    done_outcome = _run(
        coordinator.apply_audit_result(
            replace_issue(issue, state=IN_VALIDATION),
            _pass_result(records[0], "done-attempt"),
            PROJECT_ID,
        )
    )
    assert done_outcome.applied_status == IN_VALIDATION
    merged_records = _records(tracker, identifier)
    merged_outcome = _run(
        coordinator.apply_audit_result(
            replace_issue(issue, state=IN_VALIDATION),
            _pass_result(merged_records[1], "merged-attempt"),
            PROJECT_ID,
        )
    )
    assert merged_outcome.applied_status == MERGED
    assert tracker.update_issue.call_args_list[-1].kwargs["status"] == MERGED


def replace_issue(issue: Issue, **changes: str) -> Issue:
    """Copy an Issue without relying on a tracker refresh during an audit."""

    values = copy.copy(issue)
    for key, value in changes.items():
        setattr(values, key, value)
    return values


def test_evidence_change_during_audit_cannot_apply_stale_result(lifecycle_tracker) -> None:
    tracker, identifier = lifecycle_tracker
    coordinator = _coordinator(tracker)
    issue = _issue(identifier)
    first = _evidence(identifier, source_branch=EPIC_BRANCH)
    second = _evidence(identifier, source_branch=f"{EPIC_BRANCH}-changed")

    staged = _run(
        coordinator.request_transition(
            issue, TargetState.DONE, ContributorIdentity("webhook", "github"), PROJECT_ID, first
        )
    )
    old_record = _records(tracker, identifier)[0]
    refreshed = _run(
        coordinator.request_transition(
            replace_issue(issue, state=IN_VALIDATION),
            TargetState.DONE,
            ContributorIdentity("poller", "oompah"),
            PROJECT_ID,
            second,
        )
    )
    assert refreshed.superseded_audit_id == staged.audit_id
    assert len(_records(tracker, identifier)) == 2

    stale = _run(
        coordinator.apply_audit_result(
            replace_issue(issue, state=IN_VALIDATION),
            _pass_result(old_record, "stale-attempt"),
            PROJECT_ID,
        )
    )
    assert not stale.success
    assert stale.reason is not None
    assert not any(call.kwargs.get("status") == DONE for call in tracker.update_issue.call_args_list)


def test_duplicate_webhook_and_polling_signals_are_idempotent(lifecycle_tracker) -> None:
    tracker, identifier = lifecycle_tracker
    coordinator = _coordinator(tracker)
    issue = _issue(identifier)
    fingerprint = _evidence(identifier)

    async def stage_duplicates():
        return await asyncio.gather(
            *(
                coordinator.request_transition(
                    issue,
                    TargetState.DONE,
                    ContributorIdentity(source, source),
                    PROJECT_ID,
                    fingerprint,
                )
                for source in ("webhook", "poller")
            )
        )

    staged = _run(stage_duplicates())
    assert len(_records(tracker, identifier)) == 1
    assert {result.audit_id for result in staged} == {staged[0].audit_id}
    assert sum(result.coalesced for result in staged) == 1

    record = _records(tracker, identifier)[0]
    result = _pass_result(record, "merge-signal-attempt")
    async def apply_duplicates():
        return await asyncio.gather(
            coordinator.apply_audit_result(
                replace_issue(issue, state=IN_VALIDATION), result, PROJECT_ID
            ),
            coordinator.apply_audit_result(
                replace_issue(issue, state=IN_VALIDATION), result, PROJECT_ID
            ),
        )

    outcomes = _run(apply_duplicates())
    assert all(outcome.success for outcome in outcomes)
    assert sum(outcome.idempotent for outcome in outcomes) == 1
    assert sum(call.kwargs.get("status") == DONE for call in tracker.update_issue.call_args_list) == 1


def test_restart_recovers_running_audit_without_making_a_new_attempt(tmp_path) -> None:
    issue = _issue(state=IN_VALIDATION)
    fingerprint = _evidence(issue.identifier)
    attempt = AuditAttempt(
        attempt_id="running-attempt",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        created_at="2026-07-29T00:00:00+00:00",
    )
    record = TerminalAuditRecord(
        audit_id="running-audit",
        project_id=PROJECT_ID,
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )

    class RecoveryTracker:
        def __init__(self):
            self.issues = [issue]
            self.metadata = {METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()}

        def fetch_all_issues(self):
            return list(self.issues)

        def get_metadata(self, _identifier):
            return copy.deepcopy(self.metadata)

        def set_metadata_field(self, _identifier, key, value):
            self.metadata[key] = copy.deepcopy(value)

    tracker = RecoveryTracker()
    enforcement = TerminalAuditEnforcement(
        state_path=str(tmp_path / "service-state.json"),
        terminal_states=[DONE],
        project_store=_LockStore(),
    )
    first = enforcement.recover_pending_audits([(PROJECT_ID, tracker)])
    second = enforcement.recover_pending_audits([(PROJECT_ID, tracker)])

    assert len(first) == len(second) == 1
    assert first[0].audit_id == second[0].audit_id == record.audit_id
    assert first[0].attempt_ids == second[0].attempt_ids == [attempt.attempt_id]


def test_authorized_owner_override_is_recorded_and_terminal(lifecycle_tracker) -> None:
    tracker, identifier = lifecycle_tracker
    coordinator = _coordinator(tracker)
    issue = _issue(identifier)
    fingerprint = _evidence(identifier)
    owner = ContributorIdentity("project-owner", "github")
    project = SimpleNamespace(
        tracker_owner="project-owner",
        status_actor_login=None,
        status_label_authorized_logins=["project-owner"],
    )

    result = _run(
        coordinator.override_transition(
            issue,
            TargetState.DONE,
            owner,
            PROJECT_ID,
            fingerprint,
            "Emergency owner-approved terminal transition.",
            project,
        )
    )
    assert result.success
    assert result.applied_status == DONE
    assert tracker.update_issue.call_args_list[-1].kwargs["status"] == DONE
    metadata = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID).read(identifier)
    overrides = metadata.unknown_fields["oompah.terminal_override_records"]
    assert len(overrides) == 1
    assert overrides[0]["authorized_by"]["identity"] == owner.identity


def test_no_independent_candidate_is_actionable_when_auditor_branch_is_available():
    """Exercise the multi-contributor exclusion once OOMPAH-470 is integrated."""

    selector_module = pytest.importorskip(
        "oompah.auditor_candidate_selector",
        reason="independent auditor selector is supplied by the blocked auditor tasks",
    )
    from oompah.models import ModelProvider
    from oompah.roles import Candidate, Role
    from oompah.work_contributors import WorkContributor

    providers = {
        f"provider-{name}": ModelProvider(
            id=f"provider-{name}",
            name=f"Provider {name}",
            base_url="https://provider.test/v1",
            models=[f"model-{name}"],
            default_model=f"model-{name}",
            mode="api",
            api_key="test-key",
        )
        for name in ("a", "b", "c", "independent")
    }
    candidates = [
        Candidate("provider-a", "model-a"),
        Candidate("provider-b", "model-b"),
        Candidate("provider-c", "model-c"),
        Candidate("provider-independent", "model-independent"),
    ]
    role = Role(
        name="auditor",
        strategy="priority",
        candidates=candidates,
        updated_at=datetime.now(timezone.utc),
    )
    role_store = MagicMock()
    role_store.get.side_effect = lambda name: role if name in {"auditor", "default"} else None
    provider_store = MagicMock()
    provider_store.get.side_effect = providers.get
    selector = selector_module.AuditorCandidateSelector(role_store, provider_store)
    contributors = [
        WorkContributor(
            run_id=f"run-{name}",
            provider_id=f"provider-{name}",
            provider_name=f"Provider {name}",
            model_id=f"model-{name}",
            focus="feature",
            source_branch=f"epic/OOMPAH-460-{name}",
            source_sha="a" * 40,
            completed_at="2026-07-29T00:00:00+00:00",
        )
        for name in ("a", "b", "c")
    ]

    selected, reason = selector.select_candidates(contributors)
    assert reason is None
    assert [(candidate.provider_id, candidate.model) for candidate in selected] == [
        ("provider-independent", "model-independent")
    ]

    contributor_only_role = Role(
        name="auditor",
        strategy="priority",
        candidates=candidates[:3],
        updated_at=datetime.now(timezone.utc),
    )
    role_store.get.side_effect = lambda name: (
        contributor_only_role if name in {"auditor", "default"} else None
    )
    no_candidate, no_candidate_reason = selector.select_candidates(contributors)
    assert no_candidate == []
    assert no_candidate_reason is not None
    assert no_candidate_reason.reason == "all_are_contributors"


@pytest.mark.xfail(
    strict=False,
    reason="repair-planner lifecycle is supplied by blocked OOMPAH-482",
)
def test_failed_epic_audit_reopens_and_claims_one_repair_planner_run(tmp_path):
    """Contract placeholder for the persisted audit:repair-needed claim."""

    # OOMPAH-482 adds this dispatch behavior to the epic planner.  Keep the
    # assertion explicit so an integrated branch cannot silently regress to
    # ordinary already-planned epic dispatch or duplicate repair claims.
    orch = Orchestrator(
        workflow_path="WORKFLOW.md",
        project_store=MagicMock(),
        state_path=str(tmp_path / "state.json"),
    )
    epic = _issue(EPIC_ID, state=OPEN, issue_type="epic")
    epic.labels = ["audit:repair-needed"]
    orch._fetch_epic_children = MagicMock(return_value=[_issue("CHILD-1", state=DONE)])
    assert orch._should_dispatch_epic(epic) is True
