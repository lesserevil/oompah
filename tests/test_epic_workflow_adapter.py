"""Production effect and event wiring for the durable epic workflow."""

import asyncio
import copy
import logging
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.epic_workflow import EPIC_ACTIONS, EpicAction, EpicWorkflowController
from oompah.epic_workflow_adapter import (
    EpicWorkflowEventRouter,
    OrchestratorEpicWorkflowEffects,
    build_epic_workflow_handlers,
)
from oompah.integration import IntegrationRecord
from oompah.models import EpicRebaseState, Issue
from oompah.orchestrator import Orchestrator
from oompah.review_capacity import ReviewCapacityReservation
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_PROGRESS,
    IN_VALIDATION,
    MERGED,
    NEEDS_REBASE,
    OPEN,
)
from oompah.task_transition_service import (
    TransitionDisposition,
    TransitionOutcome,
    issue_authority_version,
)
from oompah.workflow_facts import FactDomain, FactState, LandingFact, LandingState
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_runtime import WorkflowRuntime, WorkflowRuntimeError
from oompah.workflow_worker import WorkflowActionError, WorkflowActionSuperseded


def epic(identifier="TOP", *, project_id="project-1", parent_id=None):
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="epic adapter fixture",
        state=IN_PROGRESS,
        issue_type="epic",
        project_id=project_id,
        parent_id=parent_id,
        work_branch=f"epic-{identifier}",
    )


def containment_facts(identifier="TOP", target="main", children=(), landings=()):
    facts = MagicMock()
    facts.landings = tuple(landings)
    facts.facts_version = "facts-fixture"

    def fact(domain):
        if FactDomain(domain) is FactDomain.CONTAINMENT:
            return SimpleNamespace(
                state=FactState.KNOWN,
                value={
                    "epic_branch": f"epic-{identifier}",
                    "target_branch": target,
                    "children": list(children),
                },
            )
        return SimpleNamespace(state=FactState.KNOWN, value={})

    facts.fact.side_effect = fact
    return facts


def rebase_facts(identifier="MID", target="epic-TOP", head="a" * 40):
    return containment_facts(
        identifier,
        target=target,
        landings=(
            LandingFact(
                f"epic-{identifier}",
                target,
                head,
                {"kind": "not_ancestor", "source_sha": head},
                "2026-08-05T00:00:00+00:00",
                "project-1",
                state=LandingState.NOT_LANDED,
            ),
        ),
    )


def effect_fixture(issue):
    project = SimpleNamespace(
        id=issue.project_id,
        repo_url="https://github.com/owner/repo.git",
        repo_path="/repo",
        access_token=None,
    )
    tracker = MagicMock()
    store = MagicMock()
    store.get.return_value = project
    orchestrator = MagicMock()
    orchestrator.project_store = store
    orchestrator._tracker_for_project.return_value = tracker
    orchestrator._epic_branch_for_issue.return_value = f"epic-{issue.identifier}"
    orchestrator._resolve_epic_target_branch.return_value = (
        f"epic-{issue.parent_id}" if issue.parent_id else "main"
    )
    tracker.fetch_issue_detail.return_value = issue
    tracker.get_metadata.return_value = {
        "oompah.workflow_idempotency_key": "existing-repair"
    }
    orchestrator._get_epic_rebase_state.return_value = EpicRebaseState.REBASING
    orchestrator._epic_rebase_state_entry.return_value = SimpleNamespace(
        project_id=issue.project_id,
        target_branch=f"epic-{issue.parent_id}" if issue.parent_id else "main",
        target_parent_id=issue.parent_id,
        target_resolution="authoritative_parent",
    )
    orchestrator._run_project_network_git.return_value = SimpleNamespace(
        returncode=0,
        stdout=f"{'a' * 40}\trefs/heads/epic-{issue.identifier}\n",
        stderr="",
    )
    return (
        OrchestratorEpicWorkflowEffects(orchestrator, project_id=issue.project_id),
        orchestrator,
        tracker,
    )


def test_review_verification_rejects_head_race():
    issue = epic()
    facts = containment_facts()
    effects, _orchestrator, _tracker = effect_fixture(issue)
    review = SimpleNamespace(
        id="42",
        url="https://example.invalid/42",
        state="open",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha="b" * 40,
    )
    provider = MagicMock()
    provider.find_pr_for_branch.return_value = review
    provider.get_branch_head_sha.return_value = "b" * 40

    with (
        patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider),
        pytest.raises(WorkflowActionError) as exc_info,
    ):
        effects.verify_epic_effect(
            EpicAction.ROLLUP_REVIEW_CREATION,
            issue,
            facts,
            {},
            {"source_head": "a" * 40},
        )

    assert exc_info.value.category is WorkflowFailureCategory.STALE_EVIDENCE


def test_review_observation_rejects_live_branch_advanced_past_review_head():
    issue = epic()
    facts = containment_facts()
    effects, _orchestrator, _tracker = effect_fixture(issue)
    provider = MagicMock()
    provider.find_pr_for_branch.return_value = SimpleNamespace(
        id="42",
        state="merged",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha="a" * 40,
    )
    provider.get_branch_head_sha.return_value = "b" * 40

    with patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider):
        observed = effects.inspect_epic_effect(
            EpicAction.TERMINAL_VALIDATION,
            issue,
            facts,
            {"review_id": "42", "merged": True},
        )

    assert observed is None


def test_review_verification_rejects_stale_nested_parent_target():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, _orchestrator, _tracker = effect_fixture(issue)
    provider = MagicMock()
    provider.find_pr_for_branch.return_value = SimpleNamespace(
        id="42",
        url="https://example.invalid/42",
        state="open",
        source_branch="epic-MID",
        target_branch="main",
        head_sha="a" * 40,
    )
    provider.get_branch_head_sha.return_value = "a" * 40

    with patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider):
        observed = effects.verify_epic_effect(
            EpicAction.ROLLUP_REVIEW_CREATION,
            issue,
            facts,
            {},
            {"source_head": "a" * 40},
        )

    assert observed is None


def test_terminal_validation_rejects_superseded_review_identity():
    issue = epic()
    facts = containment_facts()
    effects, _orchestrator, _tracker = effect_fixture(issue)
    provider = MagicMock()
    provider.find_pr_for_branch.return_value = SimpleNamespace(
        id="43",
        state="merged",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha="a" * 40,
    )
    provider.get_branch_head_sha.return_value = "a" * 40

    with (
        patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider),
        pytest.raises(WorkflowActionSuperseded, match="identity changed"),
    ):
        effects.inspect_epic_effect(
            EpicAction.TERMINAL_VALIDATION,
            issue,
            facts,
            {"review_id": "42", "merged": True},
        )


def _landed_auto_close_fixture(*, target="main", head="a" * 40):
    issue = epic()
    issue.state = DONE
    facts = containment_facts(
        target=target,
        landings=(
            LandingFact(
                "epic-TOP",
                target,
                head,
                {
                    "kind": "complete_patch_equivalence",
                    "source_sha": head,
                },
                "2026-08-09T00:00:00+00:00",
                "project-1",
                state=LandingState.LANDED,
            ),
        ),
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_children.return_value = []
    return issue, facts, effects, orchestrator


@pytest.mark.asyncio
@pytest.mark.parametrize("native_project_shape", (False, True))
async def test_auto_close_retires_exact_landed_review_and_capacity(
    native_project_shape,
):
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    if native_project_shape:
        native_issue = copy.copy(issue)
        native_issue.project_id = None
        tracker = orchestrator._tracker_for_project.return_value
        tracker.fetch_issue_detail.return_value = native_issue
    review = SimpleNamespace(
        id="748",
        state="open",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha=None,
    )
    reservation = ReviewCapacityReservation(
        reservation_id="legacy-748",
        project_id="project-1",
        task_id="TOP",
        source_branch="epic-TOP",
        target_branch="main",
        review_id="748",
        acquired_at=1.0,
        lease_expires_at=None,
    )
    provider = MagicMock()
    provider.list_open_reviews.side_effect = ([review], [])
    provider.get_branch_head_sha.return_value = "a" * 40
    provider.get_review.return_value = SimpleNamespace(
        id="748",
        state="open",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha="a" * 40,
    )
    provider.close_review.return_value = (True, "closed")
    orchestrator.review_capacity_store.active.side_effect = ([reservation], [])
    orchestrator.review_capacity_store.adopt.return_value = reservation

    with patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider):
        receipt = await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-748",
        )

    assert receipt["review_retired"] is True
    assert receipt["source_head"] == "a" * 40
    provider.close_review.assert_called_once_with("owner/repo", "748")
    provider.get_review.assert_called_once_with("owner/repo", "748")
    orchestrator.review_capacity_store.adopt.assert_called_once_with(
        project_id="project-1",
        task_id="TOP",
        source_branch="epic-TOP",
        target_branch="main",
        review_id="748",
        reservation_id="legacy-748",
        authority_generation=issue_authority_version(issue),
        head_sha="a" * 40,
    )
    orchestrator.release_review_capacity.assert_called_once_with(
        "project-1",
        "748",
    )
    orchestrator._release_review_capacity.assert_called_once_with(
        "project-1",
        reservation_id="legacy-748",
    )


def _mutate_fresh_epic_authority(issue, mutation):
    current = copy.deepcopy(issue)
    if mutation == "project":
        current.project_id = "project-2"
    elif mutation == "parent":
        current.parent_id = "OTHER"
    elif mutation == "status":
        current.state = IN_PROGRESS
    elif mutation == "branch":
        current.work_branch = "epic-replacement"
    elif mutation == "integration":
        current.integration = IntegrationRecord(
            state="ready",
            mode="queue",
            task_branch="epic-TOP",
            base_branch="main",
            head_sha="b" * 40,
        )
    elif mutation == "evidence":
        current.description = "changed terminal requirements"
    return current


@pytest.mark.parametrize(
    "mutation",
    ("project", "parent", "status", "branch", "integration", "evidence"),
)
def test_fresh_epic_authority_rejects_changed_mutation_authority(mutation):
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    orchestrator._tracker_for_project.return_value.fetch_issue_detail.return_value = (
        _mutate_fresh_epic_authority(issue, mutation)
    )

    with pytest.raises(WorkflowActionSuperseded, match="authority changed"):
        effects._fresh_epic_authority(issue, facts)


def test_fresh_epic_authority_fails_closed_when_issue_disappears():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    tracker = orchestrator._tracker_for_project.return_value
    tracker.fetch_issue_detail.return_value = None

    with pytest.raises(WorkflowActionError) as exc_info:
        effects._fresh_epic_authority(issue, facts)

    assert exc_info.value.category is WorkflowFailureCategory.TRANSIENT


@pytest.mark.asyncio
async def test_auto_close_restart_releases_exact_head_bound_reservation():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    reservation = ReviewCapacityReservation(
        reservation_id="restart-748",
        project_id="project-1",
        task_id="TOP",
        source_branch="epic-TOP",
        target_branch="main",
        review_id="748",
        acquired_at=1.0,
        lease_expires_at=None,
        authority_generation="pre-close-authority",
        head_sha="a" * 40,
    )
    provider = MagicMock()
    provider.list_open_reviews.side_effect = ([], [])
    provider.get_branch_head_sha.return_value = "a" * 40
    orchestrator.review_capacity_store.active.side_effect = ([reservation], [])

    with patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider):
        receipt = await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-restart",
        )

    assert receipt["review_retired"] is True
    provider.close_review.assert_not_called()
    orchestrator._release_review_capacity.assert_called_once_with(
        "project-1",
        reservation_id="restart-748",
    )


@pytest.mark.asyncio
async def test_auto_close_restart_verifies_legacy_reservation_review_identity():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    reservation = ReviewCapacityReservation(
        reservation_id="legacy-closed-748",
        project_id="project-1",
        task_id="TOP",
        source_branch="epic-TOP",
        target_branch="main",
        review_id="748",
        acquired_at=1.0,
        lease_expires_at=None,
    )
    provider = MagicMock()
    provider.list_open_reviews.side_effect = ([], [])
    provider.get_branch_head_sha.return_value = "a" * 40
    provider.get_review.return_value = SimpleNamespace(
        id="748",
        state="closed",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha="a" * 40,
    )
    orchestrator.review_capacity_store.active.side_effect = ([reservation], [])

    with patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider):
        receipt = await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-legacy-restart",
        )

    assert receipt["review_retired"] is True
    provider.get_review.assert_called_once_with("owner/repo", "748")
    orchestrator._release_review_capacity.assert_called_once_with(
        "project-1",
        reservation_id="legacy-closed-748",
    )


@pytest.mark.asyncio
async def test_auto_close_preserves_wrong_target_review_and_capacity():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    provider = MagicMock()
    provider.list_open_reviews.return_value = [
        SimpleNamespace(
            id="748",
            state="open",
            source_branch="epic-TOP",
            target_branch="release/other",
            head_sha="a" * 40,
        )
    ]
    provider.get_branch_head_sha.return_value = "a" * 40

    with (
        patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider),
        pytest.raises(WorkflowActionError) as exc_info,
    ):
        await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-wrong-target",
        )

    assert exc_info.value.category is WorkflowFailureCategory.STALE_EVIDENCE
    provider.close_review.assert_not_called()
    orchestrator.release_review_capacity.assert_not_called()
    orchestrator._release_review_capacity.assert_not_called()


@pytest.mark.asyncio
async def test_auto_close_preserves_conflicting_capacity_route():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    provider = MagicMock()
    provider.list_open_reviews.return_value = [
        SimpleNamespace(
            id="748",
            state="open",
            source_branch="epic-TOP",
            target_branch="main",
            head_sha="a" * 40,
        )
    ]
    provider.get_branch_head_sha.return_value = "a" * 40
    orchestrator.review_capacity_store.active.return_value = [
        ReviewCapacityReservation(
            reservation_id="wrong-route-748",
            project_id="project-1",
            task_id="TOP",
            source_branch="epic-TOP",
            target_branch="release/other",
            review_id="748",
            acquired_at=1.0,
            lease_expires_at=None,
            head_sha="a" * 40,
        )
    ]

    with (
        patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider),
        pytest.raises(WorkflowActionError) as exc_info,
    ):
        await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-conflicting-capacity",
        )

    assert exc_info.value.category is WorkflowFailureCategory.STALE_EVIDENCE
    provider.close_review.assert_not_called()
    orchestrator.review_capacity_store.adopt.assert_not_called()
    orchestrator.release_review_capacity.assert_not_called()
    orchestrator._release_review_capacity.assert_not_called()


@pytest.mark.asyncio
async def test_auto_close_rejects_advanced_source_before_review_retirement():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    provider = MagicMock()
    provider.list_open_reviews.return_value = []
    provider.get_branch_head_sha.return_value = "b" * 40

    with (
        patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider),
        pytest.raises(WorkflowActionSuperseded, match="source advanced"),
    ):
        await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-advanced",
        )

    provider.close_review.assert_not_called()
    orchestrator.release_review_capacity.assert_not_called()


@pytest.mark.asyncio
async def test_auto_close_fails_closed_when_live_forge_state_is_unavailable():
    issue, facts, effects, orchestrator = _landed_auto_close_fixture()
    provider = MagicMock()
    provider.list_open_reviews.return_value = []
    provider.last_open_reviews_fetch_ok = False

    with (
        patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider),
        pytest.raises(WorkflowActionError) as exc_info,
    ):
        await effects.apply_epic_effect(
            EpicAction.AUTO_CLOSE,
            issue,
            facts,
            {},
            idempotency_key="auto-close-forge-down",
        )

    assert exc_info.value.category is WorkflowFailureCategory.TRANSPORT
    provider.close_review.assert_not_called()
    orchestrator.release_review_capacity.assert_not_called()


@pytest.mark.asyncio
async def test_review_creation_rejects_mutation_time_reparent():
    issue = epic("MID", parent_id="TOP")
    stale = copy.copy(issue)
    stale.parent_id = "OTHER"
    landing = LandingFact(
        "epic-MID",
        "epic-TOP",
        "a" * 40,
        {"kind": "git_ancestry", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.NOT_LANDED,
    )
    facts = containment_facts("MID", target="epic-TOP", landings=(landing,))
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = stale

    with pytest.raises(WorkflowActionSuperseded, match="authority changed"):
        await effects.apply_epic_effect(
            EpicAction.ROLLUP_REVIEW_CREATION,
            issue,
            facts,
            {},
            idempotency_key="review-reparented",
        )

    orchestrator._open_one_epic_main_pr.assert_not_called()


@pytest.mark.asyncio
async def test_review_creation_rejects_child_added_after_effect_snapshot():
    issue = epic()
    added = Issue(
        id="LATE",
        identifier="LATE",
        title="late child",
        description="fixture",
        state=IN_PROGRESS,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="late-child",
    )
    landing = LandingFact(
        "epic-TOP",
        "main",
        "a" * 40,
        {"kind": "not_ancestor", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.NOT_LANDED,
    )
    facts = containment_facts(landings=(landing,))
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_children.return_value = [added]

    with pytest.raises(WorkflowActionSuperseded, match="containment changed"):
        await effects.apply_epic_effect(
            EpicAction.ROLLUP_REVIEW_CREATION,
            issue,
            facts,
            {},
            idempotency_key="review-before-late-child",
        )

    orchestrator._open_one_epic_main_pr.assert_not_called()


def test_review_creation_holds_project_fence_through_forge_mutation():
    issue = epic()
    facts = containment_facts(children=())
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_children.return_value = []
    project_lock = threading.RLock()
    orchestrator.project_store.project_write_lock.return_value = project_lock
    entered_creation = threading.Event()
    competing_mutation_acquired = threading.Event()

    def competing_mutation():
        assert entered_creation.wait(timeout=2)
        with project_lock:
            competing_mutation_acquired.set()

    competitor = threading.Thread(target=competing_mutation)
    competitor.start()

    def create_review(*_args, **_kwargs):
        entered_creation.set()
        assert not competing_mutation_acquired.wait(timeout=0.05)
        return 1

    orchestrator._open_one_epic_main_pr.side_effect = create_review
    assert effects._open_review_under_authority(
        issue,
        facts,
        "a" * 40,
    ) == 1
    competitor.join(timeout=2)

    assert competing_mutation_acquired.is_set()


def test_review_creation_supersedes_retained_child_revoked_under_project_fence():
    issue = epic()
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="b" * 40,
    )
    authority = issue_authority_version(child)
    child_fact = {
        "identifier": child.identifier,
        "status": DONE,
        "parent_id": issue.identifier,
        "maintenance": False,
        "requires_landing": True,
        "landing_source": child.work_branch,
        "landing_target": "epic-TOP",
        "revision": child.head_sha,
        "authority_version": authority,
        "retained_terminal_provenance": {
            "schema_version": 1,
            "kind": "owner_terminal_provenance",
            "project_id": "project-1",
            "parent_id": issue.identifier,
            "task_id": child.identifier,
            "status": DONE,
            "landing_source": child.work_branch,
            "landing_target": "epic-TOP",
            "revision": child.head_sha,
            "authority_version": authority,
            "marker_version": 1,
            "provenance_authority_generation": 0,
            "authorized_by": "owner",
            "actor_source": "api",
        },
    }
    facts = containment_facts(children=(child_fact,))
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_children.return_value = [child]
    orchestrator._provenance_suppression_status.return_value = SimpleNamespace(
        malformed=False,
        suppressed=True,
        marker=SimpleNamespace(
            version=1,
            suppressed=True,
            authority_generation=0,
            actor=SimpleNamespace(identity="owner", source="api"),
        ),
    )
    orchestrator._open_one_epic_main_pr.return_value = 1

    assert effects._open_review_under_authority(issue, facts, "a" * 40) == 1

    orchestrator._provenance_suppression_status.reset_mock()
    orchestrator._open_one_epic_main_pr.reset_mock()
    orchestrator._provenance_suppression_status.return_value = SimpleNamespace(
        malformed=False,
        suppressed=False,
        marker=SimpleNamespace(
            version=1,
            suppressed=False,
            authority_generation=1,
            actor=SimpleNamespace(identity="owner", source="api"),
        ),
    )

    with pytest.raises(WorkflowActionSuperseded, match="provenance changed"):
        effects._open_review_under_authority(issue, facts, "a" * 40)

    orchestrator._provenance_suppression_status.assert_called_once_with(
        child,
        "project-1",
        tracker,
    )
    orchestrator._open_one_epic_main_pr.assert_not_called()


def test_review_effect_requires_durable_exact_metadata_before_observed():
    issue = epic()
    facts = containment_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    provider = MagicMock()
    provider.find_pr_for_branch.return_value = SimpleNamespace(
        id="42",
        url="https://example.invalid/42",
        state="open",
        source_branch="epic-TOP",
        target_branch="main",
        head_sha="a" * 40,
    )
    provider.get_branch_head_sha.return_value = "a" * 40

    with patch("oompah.epic_workflow_adapter.detect_provider", return_value=provider):
        assert (
            effects.inspect_epic_effect(
                EpicAction.ROLLUP_REVIEW_CREATION, issue, facts, {}
            )
            is None
        )
        issue.review_number = "42"
        issue.review_url = "https://example.invalid/42"
        issue.work_branch = "epic-TOP"
        issue.target_branch = "main"
        issue.review_head = "a" * 40
        observed = effects.inspect_epic_effect(
            EpicAction.ROLLUP_REVIEW_CREATION, issue, facts, {}
        )

    assert observed is not None
    assert observed["source_head"] == "a" * 40
    orchestrator._write_review_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_helper_apply_is_idempotent_and_uses_immediate_parent_target():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-MID onto epic-TOP",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="epic-TOP",
    )
    helper_created = False

    def fetch_children(_identifier):
        return [helper] if helper_created else []

    def create_helper(*_args):
        nonlocal helper_created
        helper_created = True
        return helper

    tracker.fetch_children.side_effect = fetch_children
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.side_effect = lambda candidate: (
        candidate.target_branch
    )
    orchestrator._file_rebase_task.side_effect = create_helper

    first = await effects.apply_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
        idempotency_key="repair-1",
    )
    second = await effects.apply_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
        idempotency_key="repair-1",
    )

    assert first["helper_id"] == second["helper_id"] == "REBASE-1"
    orchestrator._file_rebase_task.assert_called_once_with(
        tracker, issue, "epic-MID", "epic-TOP"
    )
    tracker.set_metadata_field.assert_called_with(
        "REBASE-1", "oompah.workflow_idempotency_key", "repair-1"
    )


@pytest.mark.asyncio
async def test_rebase_apply_returns_atomic_identity_before_children_refresh():
    """A successful create is receipted before the child index catches up."""
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-MID onto epic-TOP",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="epic-TOP",
    )
    tracker.fetch_children.return_value = []
    orchestrator._file_rebase_task.return_value = helper

    receipt = await effects.apply_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
        idempotency_key="repair-read-lag",
    )

    assert receipt == {
        "effect": EpicAction.REBASE_REPAIR.value,
        "helper_id": "REBASE-1",
        "workflow_idempotency_key": "repair-read-lag",
        "source_branch": "epic-MID",
        "target_branch": "epic-TOP",
    }
    assert tracker.fetch_children.call_count == 2
    assert all(call.args == ("MID",) for call in tracker.fetch_children.call_args_list)
    tracker.set_metadata_field.assert_called_once_with(
        "REBASE-1", "oompah.workflow_idempotency_key", "repair-read-lag"
    )


@pytest.mark.asyncio
async def test_rebase_replay_repairs_all_bookkeeping_after_helper_creation_crash():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-MID onto epic-TOP",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="epic-TOP",
    )
    tracker.fetch_children.return_value = [helper]
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.return_value = "epic-TOP"
    durable = {"state": None, "entry": None, "workflow_key": None}
    tracker.get_metadata.side_effect = lambda _identifier: (
        {"oompah.workflow_idempotency_key": durable["workflow_key"]}
        if durable["workflow_key"]
        else {}
    )

    def set_metadata(_identifier, _key, value):
        durable["workflow_key"] = value

    tracker.set_metadata_field.side_effect = set_metadata
    orchestrator._get_epic_rebase_state.side_effect = (
        lambda *_args, **_kwargs: durable["state"]
    )
    orchestrator._epic_rebase_state_entry.side_effect = (
        lambda *_args, **_kwargs: durable["entry"]
    )

    def set_state(*_args, **_kwargs):
        durable["state"] = EpicRebaseState.REBASING
        durable["entry"] = SimpleNamespace(
            project_id="project-1",
            target_branch=None,
            target_parent_id=None,
            target_resolution="",
        )

    def record_target(*_args, **_kwargs):
        durable["entry"].target_branch = "epic-TOP"
        durable["entry"].target_parent_id = "TOP"
        durable["entry"].target_resolution = "authoritative_parent"

    orchestrator._set_epic_rebase_state.side_effect = set_state
    orchestrator._record_epic_rebase_target.side_effect = record_target

    assert effects.inspect_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
    ) is None

    receipt = await effects.apply_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
        idempotency_key="repair-after-crash",
    )

    assert receipt["helper_id"] == "REBASE-1"
    orchestrator._file_rebase_task.assert_not_called()
    tracker.set_metadata_field.assert_called_once_with(
        "REBASE-1",
        "oompah.workflow_idempotency_key",
        "repair-after-crash",
    )
    assert durable["entry"].target_branch == "epic-TOP"


def test_rebase_verification_is_bound_to_exact_receipt_helper_and_workflow_key():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    helper = Issue(
        id="REBASE-1",
        identifier="REBASE-1",
        title="Rebase epic-MID onto epic-TOP",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="epic-TOP",
    )
    tracker.fetch_issue_detail.return_value = helper
    tracker.get_metadata.return_value = {
        "oompah.workflow_idempotency_key": "repair-exact"
    }
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.return_value = "epic-TOP"
    receipt = {
        "helper_id": helper.identifier,
        "workflow_idempotency_key": "repair-exact",
        "source_branch": "epic-MID",
        "target_branch": "epic-TOP",
    }

    assert effects.verify_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
        receipt,
    ) == {"effect": EpicAction.REBASE_REPAIR.value, **receipt}

    tracker.get_metadata.return_value = {
        "oompah.workflow_idempotency_key": "replacement-repair"
    }
    assert (
        effects.verify_epic_effect(
            EpicAction.REBASE_REPAIR,
            issue,
            facts,
            {"target_branch": "epic-TOP"},
            receipt,
        )
        is None
    )


@pytest.mark.asyncio
async def test_rebase_creation_rejects_live_source_head_race():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts(head="a" * 40)
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_children.return_value = []
    orchestrator._run_project_network_git.return_value = SimpleNamespace(
        returncode=0,
        stdout=f"{'b' * 40}\trefs/heads/epic-MID\n",
        stderr="",
    )

    with pytest.raises(WorkflowActionSuperseded, match="source head changed"):
        await effects.apply_epic_effect(
            EpicAction.REBASE_REPAIR,
            issue,
            facts,
            {"target_branch": "epic-TOP"},
            idempotency_key="repair-head-race",
        )

    orchestrator._file_rebase_task.assert_not_called()


def test_rebase_observation_is_pure_for_wrong_target_helper():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    wrong = Issue(
        id="REBASE-OLD",
        identifier="REBASE-OLD",
        title="Rebase epic-MID onto main",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="main",
    )
    tracker.fetch_children.return_value = [wrong]
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.return_value = "main"

    observed = effects.inspect_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
    )

    assert observed is None
    tracker.update_issue.assert_not_called()
    orchestrator._find_active_epic_rebase_sibling.assert_not_called()
    orchestrator._supersede_wrong_epic_rebase_helper.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_apply_retires_wrong_target_through_transition_service():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    wrong = Issue(
        id="REBASE-OLD",
        identifier="REBASE-OLD",
        title="Rebase epic-MID onto main",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="main",
    )
    created = Issue(
        id="REBASE-NEW",
        identifier="REBASE-NEW",
        title="Rebase epic-MID onto epic-TOP",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="epic-TOP",
    )
    tracker.fetch_children.side_effect = [[wrong], [], [created]]
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.side_effect = lambda candidate: (
        candidate.target_branch
    )
    orchestrator._file_rebase_task.return_value = created
    transition_service = MagicMock()
    transition_service.execute = MagicMock()

    async def execute(intent):
        transition_service.intent = intent
        return TransitionOutcome(
            transition_id="retire-1",
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=TransitionDisposition.STAGED,
            reason_code="transition.terminal_staged",
            observed_status=IN_VALIDATION,
            observed_version=intent.expected_version,
            requested_status=intent.requested_status,
            applied_status=IN_VALIDATION,
        )

    transition_service.execute.side_effect = execute
    effects.transition_service = transition_service

    receipt = await effects.apply_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {
            "target_branch": "epic-TOP",
            "evidence_revision": "facts-2",
        },
        idempotency_key="repair-2",
        originating_job="workflow-job-2",
        evidence_generation="rebase-generation-2",
    )

    assert receipt["helper_id"] == "REBASE-NEW"
    assert transition_service.intent.task_id == "REBASE-OLD"
    assert transition_service.intent.requested_status == "Archived"
    assert transition_service.intent.reason_code == "epic.rebase_target_superseded"
    assert transition_service.intent.originating_job == "workflow-job-2"
    assert transition_service.intent.evidence_generation == "rebase-generation-2"
    assert transition_service.intent.precondition_revision == facts.facts_version
    tracker.update_issue.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_apply_retires_duplicate_and_wrong_target_helpers():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)

    def helper(identifier, target):
        return Issue(
            id=identifier,
            identifier=identifier,
            title=f"Rebase epic-MID onto {target}",
            description="fixture",
            state=NEEDS_REBASE,
            issue_type="task",
            project_id="project-1",
            parent_id="MID",
            target_branch=target,
        )

    keeper = helper("REBASE-1", "epic-TOP")
    duplicate = helper("REBASE-2", "epic-TOP")
    wrong = helper("REBASE-OLD", "main")
    active_helpers = [keeper, duplicate, wrong]
    tracker.fetch_children.side_effect = lambda _identifier: list(active_helpers)
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.side_effect = lambda candidate: (
        candidate.target_branch
    )
    transition_service = MagicMock()

    async def execute(intent):
        active_helpers[:] = [
            candidate
            for candidate in active_helpers
            if candidate.identifier != intent.task_id
        ]
        return TransitionOutcome(
            transition_id=f"retire-{intent.task_id}",
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=TransitionDisposition.STAGED,
            reason_code="transition.terminal_staged",
            observed_status=IN_VALIDATION,
            observed_version=intent.expected_version,
            requested_status=intent.requested_status,
            applied_status=IN_VALIDATION,
        )

    transition_service.execute.side_effect = execute
    effects.transition_service = transition_service

    receipt = await effects.apply_epic_effect(
        EpicAction.REBASE_REPAIR,
        issue,
        facts,
        {"target_branch": "epic-TOP"},
        idempotency_key="repair-deduplicate",
    )

    assert receipt["helper_id"] == "REBASE-1"
    assert {
        call.args[0].task_id for call in transition_service.execute.call_args_list
    } == {"REBASE-2", "REBASE-OLD"}
    orchestrator._file_rebase_task.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_retirement_precondition_race_supersedes_the_job():
    issue = epic("MID", parent_id="TOP")
    facts = rebase_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    wrong = Issue(
        id="REBASE-OLD",
        identifier="REBASE-OLD",
        title="Rebase epic-MID onto main",
        description="fixture",
        state=NEEDS_REBASE,
        issue_type="task",
        project_id="project-1",
        parent_id="MID",
        target_branch="main",
    )
    tracker.fetch_children.return_value = [wrong]
    orchestrator._is_epic_rebase_task.return_value = True
    orchestrator._epic_rebase_helper_target.return_value = "main"
    transition_service = MagicMock()
    transition_service.execute = AsyncMock(
        return_value=TransitionOutcome(
            transition_id="retire-stale",
            project_id="project-1",
            task_id=wrong.identifier,
            disposition=TransitionDisposition.REJECTED,
            reason_code="transition.stale_precondition",
            observed_status=NEEDS_REBASE,
            observed_version=issue_authority_version(wrong),
            requested_status="Archived",
        )
    )
    effects.transition_service = transition_service

    with pytest.raises(
        WorkflowActionSuperseded,
        match="retirement authority changed",
    ):
        await effects.apply_epic_effect(
            EpicAction.REBASE_REPAIR,
            issue,
            facts,
            {"target_branch": "epic-TOP"},
            idempotency_key="repair-stale-retirement",
        )

    orchestrator._file_rebase_task.assert_not_called()


@pytest.mark.asyncio
async def test_timeout_cannot_overlap_the_same_external_mutation():
    issue = epic()
    landing = LandingFact(
        "epic-TOP",
        "main",
        "a" * 40,
        {"kind": "git_ancestry", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    facts = containment_facts(landings=(landing,))
    effects, orchestrator, _tracker = effect_fixture(issue)
    release = threading.Event()
    calls = 0

    def blocking_open(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        assert release.wait(timeout=1.0)

    orchestrator._open_one_epic_main_pr.side_effect = blocking_open
    effects._review_evidence = MagicMock(
        return_value={
            "effect": EpicAction.ROLLUP_REVIEW_CREATION.value,
            "review_id": "42",
            "source_branch": "epic-TOP",
            "target_branch": "main",
            "source_head": "a" * 40,
        }
    )
    effects._persist_review_metadata = MagicMock()
    first = asyncio.create_task(
        asyncio.wait_for(
            effects.apply_epic_effect(
                EpicAction.ROLLUP_REVIEW_CREATION,
                issue,
                facts,
                {},
                idempotency_key="review-1",
            ),
            timeout=0.01,
        )
    )
    await asyncio.sleep(0.03)
    with pytest.raises(asyncio.TimeoutError):
        await first
    drain = asyncio.create_task(effects.drain_mutations(timeout_seconds=0.5))
    await asyncio.sleep(0)
    assert not drain.done()
    second = asyncio.create_task(
        effects.apply_epic_effect(
            EpicAction.ROLLUP_REVIEW_CREATION,
            issue,
            facts,
            {},
            idempotency_key="review-1",
        )
    )
    asyncio.get_running_loop().call_later(0.03, release.set)

    second_receipt = await second

    assert await drain is True
    await asyncio.sleep(0)
    assert effects.pending_mutation_count == 0
    assert second_receipt["source_head"] == "a" * 40
    assert calls == 1


def test_handler_factory_covers_every_epic_action_for_exact_project():
    controller = MagicMock()
    binding = SimpleNamespace(
        project_id="project-1",
        tracker=MagicMock(),
        epic_controller=controller,
        transition_service=MagicMock(),
    )
    handlers = build_epic_workflow_handlers(MagicMock(), binding)

    assert set(handlers) == EPIC_ACTIONS
    assert len({id(handler) for handler in handlers.values()}) == 1


@pytest.mark.asyncio
async def test_epic_handler_exposes_effect_mutation_drain():
    binding = SimpleNamespace(
        project_id="project-1",
        tracker=MagicMock(),
        epic_controller=MagicMock(),
        transition_service=MagicMock(),
    )
    handler = next(iter(build_epic_workflow_handlers(MagicMock(), binding).values()))

    assert handler.pending_mutation_count == 0
    assert await handler.drain_mutations(timeout_seconds=1) is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("child_head", "fact_revision"),
    (("a" * 40, "a" * 40), (None, None)),
    ids=("live-child-head", "pruned-child-head"),
)
async def test_terminal_cleanup_returns_exact_child_evidence(
    tmp_path,
    child_head,
    fact_revision,
):
    issue = epic()
    issue.state = MERGED
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=MERGED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        integration=SimpleNamespace(task_branch="epic-TOP--task-CHILD"),
        head_sha=child_head,
    )
    facts = containment_facts(
        children=(
            {
                "identifier": "CHILD",
                "status": MERGED,
                "parent_id": "TOP",
                "revision": fact_revision,
                "authority_version": issue_authority_version(child),
                "maintenance": False,
                "landing_source": "epic-TOP--task-CHILD",
                "landing_target": "epic-TOP",
            },
        ),
        landings=(
            LandingFact(
                "epic-TOP--task-CHILD",
                "epic-TOP",
                "a" * 40,
                {"kind": "git_ancestry", "source_sha": "a" * 40},
                "2026-08-05T00:00:00+00:00",
                "project-1",
                state=LandingState.LANDED,
                durable=True,
            ),
            LandingFact(
                "epic-TOP",
                "main",
                "b" * 40,
                {"kind": "git_ancestry", "source_sha": "b" * 40},
                "2026-08-05T00:00:00+00:00",
                "project-1",
                state=LandingState.LANDED,
                durable=True,
            ),
        ),
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [child, issue, child, issue, child]
    tracker.fetch_children.return_value = [child]
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )
    orchestrator.project_store.worktree_path_for.return_value = str(
        tmp_path / "missing-child"
    )
    orchestrator.project_store.epic_worktree_path_for.return_value = str(
        tmp_path / "missing-epic"
    )
    orchestrator.project_store._ref_exists.return_value = False
    orchestrator.project_store.cleanup_terminal_issue.return_value = (True, None)
    orchestrator._run_project_network_git.return_value = SimpleNamespace(
        returncode=0, stdout=""
    )
    rebase_state = {"value": "stale"}
    orchestrator._get_epic_rebase_state.side_effect = lambda _identifier, **_kwargs: (
        rebase_state["value"]
    )

    def clear_state(*_args, **_kwargs):
        rebase_state["value"] = None

    orchestrator._clear_epic_rebase_state.side_effect = clear_state

    receipt = await effects.apply_epic_effect(
        EpicAction.CLEANUP,
        issue,
        facts,
        {},
        idempotency_key="cleanup-1",
    )

    assert receipt["cleanup_complete"] is True
    assert receipt["children_cleaned"] == ["CHILD"]
    orchestrator.project_store.delete_epic_child_branch.assert_called_once_with(
        "project-1",
        "TOP",
        "CHILD",
        expected_head_sha="a" * 40,
        require_target_branch=True,
    )
    orchestrator.project_store.cleanup_terminal_issue.assert_called_once_with(
        "project-1",
        "TOP",
        branch_name="epic-TOP",
        is_epic=True,
        target_branch="main",
        review_head="b" * 40,
        merge_commit_sha=None,
        require_target_branch=True,
        expected_head_sha="b" * 40,
    )


def test_archived_child_cleanup_does_not_require_parent_landing():
    issue = epic()
    issue.state = ARCHIVED
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=ARCHIVED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    facts = containment_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [issue, child]

    effects._delete_cleanup_child(issue, facts, child, "a" * 40)

    orchestrator.project_store.delete_epic_child_branch.assert_called_once_with(
        "project-1",
        "TOP",
        "CHILD",
        expected_head_sha="a" * 40,
        require_target_branch=False,
    )


def test_native_blank_project_child_cleanup_uses_bound_scope():
    issue = epic()
    issue.state = ARCHIVED
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=ARCHIVED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    native_issue = copy.copy(issue)
    native_issue.project_id = None
    native_child = copy.copy(child)
    native_child.project_id = None
    facts = containment_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [native_issue, native_child]

    effects._delete_cleanup_child(issue, facts, child, "a" * 40)

    orchestrator.project_store.delete_epic_child_branch.assert_called_once_with(
        "project-1",
        "TOP",
        "CHILD",
        expected_head_sha="a" * 40,
        require_target_branch=False,
    )


def test_child_cleanup_rejects_conflicting_nonempty_project():
    issue = epic()
    issue.state = ARCHIVED
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=ARCHIVED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    conflicting = copy.copy(child)
    conflicting.project_id = "project-2"
    facts = containment_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [issue, conflicting]

    with pytest.raises(WorkflowActionSuperseded, match="before branch deletion"):
        effects._delete_cleanup_child(issue, facts, child, "a" * 40)

    orchestrator.project_store.delete_epic_child_branch.assert_not_called()


def test_child_cleanup_uses_submission_compatible_lock_order():
    issue = epic()
    issue.state = ARCHIVED
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=ARCHIVED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    facts = containment_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [issue, child]
    held: list[str] = []

    class OrderedLock:
        def __init__(self, name):
            self.name = name

        def sync(self):
            return self

        def __enter__(self):
            held.append(self.name)
            return self

        def __exit__(self, *_args):
            assert held.pop() == self.name

    issue_locks = {
        "TOP": OrderedLock("epic"),
        "CHILD": OrderedLock("child"),
    }
    orchestrator.issue_transition_lock.side_effect = issue_locks.__getitem__
    orchestrator.project_store.project_write_lock.return_value = OrderedLock(
        "project"
    )

    def delete(*_args, **_kwargs):
        assert held == ["epic", "child", "project"]

    orchestrator.project_store.delete_epic_child_branch.side_effect = delete

    effects._delete_cleanup_child(issue, facts, child, "a" * 40)

    assert held == []


def test_archived_epic_cleanup_does_not_require_target_landing():
    issue = epic()
    issue.state = ARCHIVED
    facts = containment_facts()
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    orchestrator.project_store.cleanup_terminal_issue.return_value = (True, None)

    effects._cleanup_primary_under_authority(
        issue,
        facts,
        source="epic-TOP",
        target="main",
        expected_head="a" * 40,
        merge_commit_sha="b" * 40,
    )

    orchestrator.project_store.cleanup_terminal_issue.assert_called_once_with(
        "project-1",
        "TOP",
        branch_name="epic-TOP",
        is_epic=True,
        target_branch=None,
        review_head=None,
        merge_commit_sha=None,
        require_target_branch=False,
        expected_head_sha="a" * 40,
    )


def test_primary_cleanup_rejects_child_added_after_effect_snapshot():
    issue = epic()
    issue.state = ARCHIVED
    added = Issue(
        id="LATE",
        identifier="LATE",
        title="late child",
        description="fixture",
        state=IN_PROGRESS,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-LATE",
    )
    facts = containment_facts(children=())
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_children.return_value = [added]

    with pytest.raises(WorkflowActionSuperseded, match="containment changed"):
        effects._cleanup_primary_under_authority(
            issue,
            facts,
            source="epic-TOP",
            target="main",
            expected_head="a" * 40,
            merge_commit_sha=None,
        )

    orchestrator.project_store.cleanup_terminal_issue.assert_not_called()


def test_primary_cleanup_rejects_active_child_in_fresh_snapshot():
    issue = epic()
    issue.state = ARCHIVED
    child = Issue(
        id="ACTIVE",
        identifier="ACTIVE",
        title="active child",
        description="fixture",
        state=IN_PROGRESS,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-ACTIVE",
    )
    facts = containment_facts(
        children=(
            {
                "identifier": child.identifier,
                "status": child.state,
                "authority_version": issue_authority_version(child),
            },
        )
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_children.return_value = [child]

    with pytest.raises(WorkflowActionSuperseded, match="is active"):
        effects._cleanup_primary_under_authority(
            issue,
            facts,
            source="epic-TOP",
            target="main",
            expected_head="a" * 40,
            merge_commit_sha=None,
        )

    orchestrator.project_store.cleanup_terminal_issue.assert_not_called()


def test_primary_cleanup_holds_project_fence_through_branch_deletion():
    issue = epic()
    issue.state = ARCHIVED
    facts = containment_facts(children=())
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_children.return_value = []
    project_lock = threading.RLock()
    orchestrator.project_store.project_write_lock.return_value = project_lock
    entered_cleanup = threading.Event()
    competing_mutation_acquired = threading.Event()

    def competing_mutation():
        assert entered_cleanup.wait(timeout=2)
        with project_lock:
            competing_mutation_acquired.set()

    competitor = threading.Thread(target=competing_mutation)
    competitor.start()

    def cleanup(*_args, **_kwargs):
        entered_cleanup.set()
        assert not competing_mutation_acquired.wait(timeout=0.05)
        return True, None

    orchestrator.project_store.cleanup_terminal_issue.side_effect = cleanup
    effects._cleanup_primary_under_authority(
        issue,
        facts,
        source="epic-TOP",
        target="main",
        expected_head="a" * 40,
        merge_commit_sha=None,
    )
    competitor.join(timeout=2)

    assert competing_mutation_acquired.is_set()


def test_cleanup_selects_done_shared_child_only_with_exact_landing():
    issue = epic()
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        integration=SimpleNamespace(task_branch="epic-TOP--task-CHILD"),
        head_sha="a" * 40,
    )
    landing = LandingFact(
        "epic-TOP--task-CHILD",
        "epic-TOP",
        "a" * 40,
        {"kind": "git_ancestry", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    child_fact = {
        "identifier": "CHILD",
        "status": DONE,
        "parent_id": "TOP",
        "maintenance": False,
        "landing_source": "epic-TOP--task-CHILD",
        "landing_target": "epic-TOP",
        "revision": "a" * 40,
        "authority_version": issue_authority_version(child),
    }
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = child
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )

    selected = effects._cleanup_children(
        issue,
        containment_facts(children=(child_fact,), landings=(landing,)),
    )

    assert selected == ((child, "epic-TOP--task-CHILD", "a" * 40),)


def test_cleanup_uses_canonical_landing_after_child_head_is_pruned():
    issue = epic()
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        integration=SimpleNamespace(task_branch="epic-TOP--task-CHILD"),
        head_sha=None,
    )
    landing = LandingFact(
        "epic-TOP--task-CHILD",
        "epic-TOP",
        "a" * 40,
        {"kind": "patch_id", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    child_fact = {
        "identifier": "CHILD",
        "status": DONE,
        "parent_id": "TOP",
        "maintenance": False,
        "landing_source": "epic-TOP--task-CHILD",
        "landing_target": "epic-TOP",
        "revision": None,
        "authority_version": issue_authority_version(child),
    }
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = child
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )

    selected = effects._cleanup_children(
        issue,
        containment_facts(children=(child_fact,), landings=(landing,)),
    )

    assert selected == ((child, "epic-TOP--task-CHILD", "a" * 40),)


def test_cleanup_rejects_landing_that_conflicts_with_live_child_head():
    issue = epic()
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        integration=SimpleNamespace(task_branch="epic-TOP--task-CHILD"),
        head_sha="a" * 40,
    )
    conflicting = LandingFact(
        "epic-TOP--task-CHILD",
        "epic-TOP",
        "b" * 40,
        {"kind": "git_ancestry", "source_sha": "b" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = child
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )

    with pytest.raises(WorkflowActionError, match="no exact landing proof"):
        effects._cleanup_children(
            issue,
            containment_facts(
                children=(
                    {
                        "identifier": "CHILD",
                        "status": DONE,
                        "parent_id": "TOP",
                        "maintenance": False,
                        "landing_source": "epic-TOP--task-CHILD",
                        "landing_target": "epic-TOP",
                        "revision": "a" * 40,
                        "authority_version": issue_authority_version(child),
                    },
                ),
                landings=(conflicting,),
            ),
        )


def test_cleanup_fails_closed_for_done_child_without_landing():
    issue = epic()
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        integration=SimpleNamespace(task_branch="epic-TOP--task-CHILD"),
        head_sha="a" * 40,
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = child
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )

    with pytest.raises(WorkflowActionError, match="no exact landing proof"):
        effects._cleanup_children(
            issue,
            containment_facts(
                children=(
                    {
                        "identifier": "CHILD",
                        "status": DONE,
                        "parent_id": "TOP",
                        "maintenance": False,
                        "landing_source": "epic-TOP--task-CHILD",
                        "landing_target": "epic-TOP",
                        "revision": "a" * 40,
                        "authority_version": issue_authority_version(child),
                    },
                )
            ),
        )


def test_retained_child_waiver_is_never_cleanup_or_branch_deletion_authority():
    issue = epic()
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=DONE,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    authority = issue_authority_version(child)
    child_fact = {
        "identifier": child.identifier,
        "status": DONE,
        "parent_id": issue.identifier,
        "maintenance": False,
        "requires_landing": True,
        "landing_source": child.work_branch,
        "landing_target": "epic-TOP",
        "revision": child.head_sha,
        "authority_version": authority,
        "retained_terminal_provenance": {
            "schema_version": 1,
            "kind": "owner_terminal_provenance",
            "project_id": "project-1",
            "parent_id": issue.identifier,
            "task_id": child.identifier,
            "status": DONE,
            "landing_source": child.work_branch,
            "landing_target": "epic-TOP",
            "revision": child.head_sha,
            "authority_version": authority,
            "marker_version": 1,
            "provenance_authority_generation": 0,
            "authorized_by": "owner",
            "actor_source": "api",
        },
    }
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = child

    selected = effects._cleanup_children(
        issue,
        containment_facts(children=(child_fact,)),
    )

    assert selected == ()
    orchestrator.project_store.delete_epic_child_branch.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_supersedes_when_child_reopens_after_containment_snapshot():
    issue = epic()
    issue.state = ARCHIVED
    original = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=MERGED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    original_authority = issue_authority_version(original)
    reopened = copy.copy(original)
    reopened.state = IN_PROGRESS
    facts = containment_facts(
        children=(
            {
                "identifier": "CHILD",
                "status": MERGED,
                "parent_id": "TOP",
                "revision": "a" * 40,
                "authority_version": original_authority,
                "maintenance": True,
            },
        )
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [original, issue, reopened]
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )

    with pytest.raises(WorkflowActionSuperseded, match="before branch deletion"):
        await effects.apply_epic_effect(
            EpicAction.CLEANUP,
            issue,
            facts,
            {},
            idempotency_key="cleanup-stale",
        )

    orchestrator.project_store.delete_epic_child_branch.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_rechecks_epic_before_deleting_terminal_child():
    issue = epic()
    issue.state = MERGED
    child = Issue(
        id="CHILD",
        identifier="CHILD",
        title="child",
        description="fixture",
        state=MERGED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
        work_branch="epic-TOP--task-CHILD",
        head_sha="a" * 40,
    )
    reopened = copy.copy(issue)
    reopened.state = IN_PROGRESS
    facts = containment_facts(
        children=(
            {
                "identifier": "CHILD",
                "status": MERGED,
                "parent_id": "TOP",
                "revision": "a" * 40,
                "authority_version": issue_authority_version(child),
                "maintenance": True,
            },
        ),
        landings=(
            LandingFact(
                "epic-TOP",
                "main",
                "b" * 40,
                {"kind": "git_ancestry", "source_sha": "b" * 40},
                "2026-08-05T00:00:00+00:00",
                "project-1",
                state=LandingState.LANDED,
                durable=True,
            ),
        ),
    )
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.side_effect = [child, reopened]
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-TOP--task-CHILD"
    )

    with pytest.raises(WorkflowActionSuperseded, match="authority changed"):
        await effects.apply_epic_effect(
            EpicAction.CLEANUP,
            issue,
            facts,
            {},
            idempotency_key="cleanup-epic-reopened-before-child",
        )

    orchestrator.project_store.delete_epic_child_branch.assert_not_called()
    orchestrator.project_store.cleanup_terminal_issue.assert_not_called()


@pytest.mark.asyncio
async def test_merged_epic_cleanup_requires_exact_own_landing_before_children():
    issue = epic()
    issue.state = MERGED
    effects, orchestrator, _tracker = effect_fixture(issue)

    with pytest.raises(WorkflowActionSuperseded, match="target landing authority"):
        await effects.apply_epic_effect(
            EpicAction.CLEANUP,
            issue,
            containment_facts(),
            {},
            idempotency_key="cleanup-without-own-landing",
        )

    orchestrator.project_store.delete_epic_child_branch.assert_not_called()
    orchestrator.project_store.cleanup_terminal_issue.assert_not_called()

    issue.state = IN_PROGRESS
    landed = LandingFact(
        "epic-TOP",
        "main",
        "a" * 40,
        {"kind": "git_ancestry", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    with pytest.raises(WorkflowActionSuperseded, match="no longer terminal"):
        await effects.apply_epic_effect(
            EpicAction.CLEANUP,
            issue,
            containment_facts(landings=(landed,)),
            {},
            idempotency_key="cleanup-reopened-with-old-landing",
        )

    orchestrator.project_store.delete_epic_child_branch.assert_not_called()
    orchestrator.project_store.cleanup_terminal_issue.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_supersedes_when_epic_reopens_before_primary_delete():
    issue = epic()
    issue.state = MERGED
    reopened = copy.copy(issue)
    reopened.state = IN_PROGRESS
    own_landing = LandingFact(
        "epic-TOP",
        "main",
        "a" * 40,
        {"kind": "git_ancestry", "source_sha": "a" * 40},
        "2026-08-05T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    facts = containment_facts(landings=(own_landing,))
    effects, orchestrator, tracker = effect_fixture(issue)
    tracker.fetch_issue_detail.return_value = reopened

    with pytest.raises(WorkflowActionSuperseded, match="authority changed"):
        await effects.apply_epic_effect(
            EpicAction.CLEANUP,
            issue,
            facts,
            {},
            idempotency_key="cleanup-reopened-epic",
        )

    orchestrator.project_store.cleanup_terminal_issue.assert_not_called()


def test_real_orchestrator_factory_exposes_only_installed_domain_adapters():
    orchestrator = object.__new__(Orchestrator)
    # Exercise the O837-only installation seam. The composed OOMPAH-804 tree
    # also installs O834, whose production builder deliberately requires the
    # live workflow store and has its own composition coverage.
    orchestrator._implementation_workflow_action_handlers = None
    binding = SimpleNamespace(
        project_id="project-1",
        tracker=MagicMock(),
        implementation_controller=MagicMock(),
        review_controller=MagicMock(),
        integration_controller=MagicMock(),
        epic_controller=MagicMock(),
        terminal_audit_workflow=MagicMock(),
        transition_service=MagicMock(),
    )

    handlers = Orchestrator.workflow_action_handler_factory(
        orchestrator, binding
    )

    assert set(handlers) == EPIC_ACTIONS
    with pytest.raises(WorkflowRuntimeError, match="total project-routed"):
        WorkflowRuntime(
            project_bindings={"project-1": binding},
            store=MagicMock(),
            journals={},
            mode="enforce",
            handlers=handlers,
        )


@pytest.mark.asyncio
async def test_orchestrator_store_shutdown_rejects_pending_workflow_mutation():
    orchestrator = SimpleNamespace(
        workflow_runtime=SimpleNamespace(pending_operation_count=1),
        _drain_scheduled_terminations=AsyncMock(),
        _restart_recovery_task=None,
    )

    with pytest.raises(RuntimeError, match="refusing to close lifecycle stores"):
        await Orchestrator._drain_background_work(orchestrator)


@pytest.mark.asyncio
async def test_orchestrator_stop_retains_runtime_after_initial_drain_budget():
    runtime = SimpleNamespace(
        drain=AsyncMock(return_value=False),
        close=MagicMock(),
    )
    orchestrator = SimpleNamespace(
        _stopping=False,
        _quiesced=False,
        _provider_admission_lock=threading.RLock(),
        _provider_admission_generation=0,
        _termination_scheduling_closed=False,
        _mark_running_auditors_for_lifecycle_retirement_locked=MagicMock(),
        workflow_runtime=runtime,
        _drain_scheduled_terminations=AsyncMock(),
        _running_items_snapshot=lambda: (),
        _notify_observers=MagicMock(),
        _drain_background_work=AsyncMock(),
    )

    stopped = await Orchestrator.stop(orchestrator)

    assert stopped is False
    retirement = (
        orchestrator._mark_running_auditors_for_lifecycle_retirement_locked
    )
    retirement.assert_called_once_with(
        reason="scheduler_pause",
        error="graceful shutdown interrupted auditor before verdict",
    )
    runtime.drain.assert_awaited_once_with(timeout_seconds=10.0)
    orchestrator._drain_background_work.assert_not_awaited()
    runtime.close.assert_not_called()


class Tracker:
    def __init__(self, issues):
        self.issues = {issue.identifier: issue for issue in issues}

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_event_router_is_inert_outside_enforce_mode(mode):
    tracker = MagicMock()
    controller = MagicMock()
    controller.scheduler = MagicMock()
    runtime = SimpleNamespace(
        mode=mode,
        enforce=False,
        project_bindings={
            "project-1": SimpleNamespace(
                tracker=tracker,
                epic_controller=controller,
            )
        },
    )
    orchestrator = SimpleNamespace(request_refresh=MagicMock())
    router = EpicWorkflowEventRouter(orchestrator, runtime)

    with patch("oompah.epic_workflow_adapter.EpicWorkflowController") as ephemeral:
        router.on_issue_changed(
            "issue_state_changed",
            {"project_id": "project-1", "identifier": "TOP"},
        )
        router.on_agent_finished(
            "agent_finished",
            {"project_id": "project-1", "identifier": "TOP"},
        )
        router.on_forge_event(
            "forge_webhook_received",
            {"project_id": "project-1", "source_branch": "epic-TOP"},
        )
        router.on_rebase_requested(
            "epic_rebase_requested",
            {
                "project_id": "project-1",
                "identifier": "TOP",
                "target_branch": "main",
            },
        )
        assert router.schedule_restart().result(timeout=1.0) == 0
        router.drain_events(timeout=1.0)

    tracker.fetch_issue_detail.assert_not_called()
    controller.schedule_action.assert_not_called()
    ephemeral.assert_not_called()
    orchestrator.request_refresh.assert_not_called()
    router.close()


def test_rebase_event_uses_target_and_epic_authority_not_observation_revision():
    top = epic("TOP")
    tracker = Tracker([top])
    controller = MagicMock()
    controller.scheduler = MagicMock()
    binding = SimpleNamespace(tracker=tracker, epic_controller=controller)
    runtime = SimpleNamespace(
        enforce=True,
        project_bindings={"project-1": binding},
    )
    orchestrator = SimpleNamespace(
        request_refresh=MagicMock(),
        _request_workflow_batch_continuation=MagicMock(return_value=True),
    )
    router = EpicWorkflowEventRouter(orchestrator, runtime)
    decision = SimpleNamespace(
        durable_jobs=(EpicAction.REBASE_REPAIR.value,),
        reason_code="epic.rebase_required",
        evidence_revision="event-observation-revision",
    )
    facts = containment_facts(
        "TOP",
        target="main",
        landings=(
            LandingFact(
                "epic-TOP",
                "main",
                "a" * 40,
                {"kind": "not_ancestor"},
                "2026-08-13T00:00:00+00:00",
                "project-1",
                state=LandingState.NOT_LANDED,
            ),
        ),
    )

    with patch(
        "oompah.epic_workflow_adapter.EpicWorkflowController"
    ) as ephemeral_controller:
        ephemeral_controller.return_value.evaluate.return_value = SimpleNamespace(
            tasks=(SimpleNamespace(decision=decision, facts=facts),)
        )
        router.on_rebase_requested(
            "epic_rebase_requested",
            {
                "project_id": "project-1",
                "identifier": "TOP",
                "target_branch": "main",
                "source": "nested-dispatch-topology",
            },
        )
        router.drain_events(timeout=1.0)

    controller.schedule_action.assert_called_once()
    call = controller.schedule_action.call_args
    assert call.kwargs["action"] is EpicAction.REBASE_REPAIR
    assert call.kwargs["expected_evidence_revision"] is None
    assert call.kwargs["expected_head_sha"] == "a" * 40
    assert call.kwargs["payload"] == {
        "event_source": "epic-rebase-requested",
        "source_branch": "epic-TOP",
        "source_head": "a" * 40,
        "target_branch": "main",
        "request_source": "nested-dispatch-topology",
        "evidence_revision": "event-observation-revision",
        "revalidation_contract": "target-source-head-immutable-helper-v4",
    }
    assert call.kwargs["generation"].startswith("epic-event:")
    controller.scheduler.wake.assert_called_once_with("epic-rebase-requested")
    router.close()


def test_restart_cleanup_counts_created_jobs_and_replays_across_worker_ids(
    tmp_path, caplog
):
    landed = epic("LANDED")
    landed.state = MERGED
    landed.head_sha = "a" * 40
    historical = epic("HISTORICAL")
    historical.state = ARCHIVED
    historical.head_sha = "b" * 40
    tracker = MagicMock()
    tracker.fetch_all_issues_enriched.return_value = [landed, historical]
    collector = MagicMock()
    collector.project_id = "project-1"
    controller = EpicWorkflowController(
        collector=collector,
        store=WorkflowJobStore(str(tmp_path / "restart-jobs.sqlite3")),
    )
    historical_job = controller.schedule_action(
        task_id=historical.identifier,
        action=EpicAction.CLEANUP,
        generation="historical-cleanup",
        expected_head_sha=historical.head_sha,
    )
    historical_claim = controller.store.claim_next(
        lease_owner="historical-worker",
        lease_seconds=30,
        project_id="project-1",
        task_id=historical.identifier,
    )
    assert historical_claim is not None
    controller.store.complete(
        historical_job.job_id,
        historical_claim.lease_token,
    )
    historical.head_sha = None
    binding = SimpleNamespace(tracker=tracker, epic_controller=controller)
    runtime = SimpleNamespace(
        enforce=True,
        worker=SimpleNamespace(worker_id="runtime-owner-one"),
        project_bindings={"project-1": binding},
    )
    orchestrator = SimpleNamespace(request_refresh=MagicMock())
    router = EpicWorkflowEventRouter(orchestrator, runtime)

    with caplog.at_level(logging.INFO):
        first = router._schedule_restart()
        same_owner_replay = router._schedule_restart()
        router.close()
        restarted = EpicWorkflowEventRouter(
            orchestrator,
            SimpleNamespace(
                enforce=True,
                worker=SimpleNamespace(worker_id="runtime-owner-two"),
                project_bindings={"project-1": binding},
            ),
        )
        changed_owner_replay = restarted._schedule_restart()

    assert (first, same_owner_replay, changed_owner_replay) == (1, 0, 0)
    cleanup_jobs = controller.store.list_jobs(
        project_id="project-1",
        actions=(EpicAction.CLEANUP.value,),
        limit=100,
    )
    assert len(cleanup_jobs) == 2
    landed_jobs = [job for job in cleanup_jobs if job.task_id == "LANDED"]
    assert len(landed_jobs) == 1
    assert landed_jobs[0].state is WorkflowJobState.QUEUED
    assert "restart_owner" not in landed_jobs[0].payload
    collector.collect.assert_not_called()
    assert not [
        record
        for record in caplog.records
        if record.levelno >= logging.WARNING
        and "exact source generation is unavailable" in record.getMessage()
    ]
    summaries = [
        record
        for record in caplog.records
        if "Epic restart cleanup seed summary" in record.getMessage()
    ]
    assert len(summaries) == 3
    assert all(record.levelno == logging.INFO for record in summaries)
    assert all("historical_completed=1" in record.getMessage() for record in summaries)
    assert all("actionable_uncertain=0" in record.getMessage() for record in summaries)
    assert all("HISTORICAL" in record.getMessage() for record in summaries)
    restarted.close()
    controller.store.close()


def test_restart_cleanup_retains_retry_and_warns_for_exhausted_or_missing(
    tmp_path, caplog
):
    retrying = epic("RETRYING")
    retrying.state = MERGED
    retrying.head_sha = "c" * 40
    exhausted = epic("EXHAUSTED")
    exhausted.state = ARCHIVED
    exhausted.head_sha = "d" * 40
    missing = epic("MISSING")
    missing.state = ARCHIVED
    historical = epic("HISTORICAL")
    historical.state = ARCHIVED
    historical.head_sha = "e" * 40
    collector = MagicMock()
    collector.project_id = "project-1"
    store = WorkflowJobStore(str(tmp_path / "uncertain-cleanup.sqlite3"))
    controller = EpicWorkflowController(collector=collector, store=store)
    for issue, retryable in ((retrying, True), (exhausted, False)):
        controller.schedule_action(
            task_id=issue.identifier,
            action=EpicAction.CLEANUP,
            generation=f"cleanup-{issue.identifier.lower()}",
            expected_head_sha=issue.head_sha,
        )
        claimed = store.claim_next(
            lease_owner=f"worker-{issue.identifier.lower()}",
            lease_seconds=30,
            project_id="project-1",
            task_id=issue.identifier,
        )
        assert claimed is not None
        failed = store.fail(
            claimed.job_id,
            claimed.lease_token,
            category=WorkflowFailureCategory.TRANSPORT,
            error="cleanup unavailable",
            retryable=retryable,
            retry_delay_seconds=60,
        )
        assert failed.state is (
            WorkflowJobState.RETRY_WAIT
            if retryable
            else WorkflowJobState.EXHAUSTED
        )
        issue.head_sha = None
    historical_job = controller.schedule_action(
        task_id=historical.identifier,
        action=EpicAction.CLEANUP,
        generation="cleanup-historical",
        expected_head_sha=historical.head_sha,
    )
    historical_claim = store.claim_next(
        lease_owner="worker-historical",
        lease_seconds=30,
        project_id="project-1",
        task_id=historical.identifier,
    )
    assert historical_claim is not None
    store.complete(historical_job.job_id, historical_claim.lease_token)
    historical.head_sha = None
    tracker = MagicMock()
    tracker.fetch_all_issues_enriched.return_value = [
        retrying,
        exhausted,
        missing,
        historical,
    ]
    binding = SimpleNamespace(tracker=tracker, epic_controller=controller)
    router = EpicWorkflowEventRouter(
        SimpleNamespace(request_refresh=MagicMock()),
        SimpleNamespace(
            enforce=True,
            worker=SimpleNamespace(worker_id="new-runtime-owner"),
            project_bindings={"project-1": binding},
        ),
    )

    with caplog.at_level(logging.INFO):
        scheduled = router._schedule_restart()

    assert scheduled == 0
    assert len(store.list_jobs(project_id="project-1", limit=100)) == 3
    collector.collect.assert_not_called()
    summaries = [
        record
        for record in caplog.records
        if "Epic restart cleanup seed summary" in record.getMessage()
    ]
    assert len(summaries) == 1
    assert summaries[0].levelno == logging.WARNING
    assert "historical_completed=1" in summaries[0].getMessage()
    assert "actionable_uncertain=2" in summaries[0].getMessage()
    assert "HISTORICAL" in summaries[0].getMessage()
    assert "EXHAUSTED(exhausted)" in summaries[0].getMessage()
    assert "MISSING(no_evidence)" in summaries[0].getMessage()
    assert "RETRYING" not in summaries[0].getMessage()
    router.close()
    store.close()


def test_live_cleanup_without_exact_generation_remains_actionable(caplog):
    historical = epic("HISTORICAL")
    historical.state = ARCHIVED
    controller = MagicMock()
    controller.collector.collect.return_value = containment_facts("HISTORICAL")
    controller.scheduler = MagicMock()
    binding = SimpleNamespace(tracker=MagicMock(), epic_controller=controller)
    runtime = SimpleNamespace(enforce=True, project_bindings={"project-1": binding})
    router = EpicWorkflowEventRouter(
        SimpleNamespace(request_refresh=MagicMock()), runtime
    )

    with caplog.at_level(logging.WARNING):
        scheduled = router._schedule(
            binding,
            historical,
            EpicAction.CLEANUP,
            source="issue-state-changed",
        )

    assert scheduled is False
    assert [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "exact source generation is unavailable" in record.getMessage()
    ]
    controller.schedule_action.assert_not_called()
    router.close()


def test_event_router_never_wakes_same_identifier_in_another_project():
    parent_one = epic("TOP", project_id="project-1")
    child_one = Issue(
        id="TASK",
        identifier="TASK",
        title="child",
        description="fixture",
        state=MERGED,
        issue_type="task",
        project_id="project-1",
        parent_id="TOP",
    )
    parent_two = epic("TOP", project_id="project-2")
    child_two = Issue(
        id="TASK",
        identifier="TASK",
        title="child",
        description="fixture",
        state=MERGED,
        issue_type="task",
        project_id="project-2",
        parent_id="TOP",
    )
    controller_one = MagicMock()
    controller_one.scheduler = MagicMock()
    controller_two = MagicMock()
    controller_two.scheduler = MagicMock()
    bindings = {
        "project-1": SimpleNamespace(
            tracker=Tracker([parent_one, child_one]),
            epic_controller=controller_one,
        ),
        "project-2": SimpleNamespace(
            tracker=Tracker([parent_two, child_two]),
            epic_controller=controller_two,
        ),
    }
    runtime = SimpleNamespace(enforce=True, project_bindings=bindings)
    orchestrator = SimpleNamespace(
        request_refresh=MagicMock(),
        _request_workflow_batch_continuation=MagicMock(return_value=True),
    )
    router = EpicWorkflowEventRouter(orchestrator, runtime)
    decision = SimpleNamespace(
        durable_jobs=(EpicAction.ROLLUP_REVIEW_CREATION.value,),
        reason_code="rollup.children_complete",
        evidence_revision="evidence-1",
    )
    with patch(
        "oompah.epic_workflow_adapter.EpicWorkflowController"
    ) as ephemeral_controller:
        ephemeral_controller.return_value.evaluate.return_value = SimpleNamespace(
            tasks=(SimpleNamespace(decision=decision),)
        )
        router.on_issue_changed(
            "issue_state_changed",
            {"project_id": "project-1", "identifier": "TASK"},
        )
        router.drain_events(timeout=1.0)

    assert controller_one.schedule_action.call_count == 3
    assert {
        call.kwargs["action"] for call in controller_one.schedule_action.call_args_list
    } == {
        EpicAction.READINESS,
        EpicAction.TARGET_RESOLUTION,
        EpicAction.ROLLUP_REVIEW_CREATION,
    }
    review_call = next(
        call
        for call in controller_one.schedule_action.call_args_list
        if call.kwargs["action"] is EpicAction.ROLLUP_REVIEW_CREATION
    )
    assert review_call.kwargs["expected_evidence_revision"] == "evidence-1"
    controller_two.schedule_action.assert_not_called()
    assert (
        orchestrator._request_workflow_batch_continuation.call_count == 3
    )
    assert {
        call.kwargs["reason"]
        for call in (
            orchestrator._request_workflow_batch_continuation.call_args_list
        )
    } == {"epic_workflow_event:issue-state-changed"}
    orchestrator.request_refresh.assert_not_called()
    router.close()


def test_event_router_coalesces_batch_members_to_one_parent_rollup():
    parent = epic("TOP")
    first = Issue(
        id="FIRST",
        identifier="FIRST",
        title="First",
        state=OPEN,
        issue_type="task",
        parent_id="TOP",
        project_id="project-1",
    )
    second = Issue(
        id="SECOND",
        identifier="SECOND",
        title="Second",
        state=OPEN,
        issue_type="task",
        parent_id="TOP",
        project_id="project-1",
    )
    tracker = Tracker([parent, first, second])
    controller = MagicMock()
    controller.scheduler = MagicMock()
    runtime = SimpleNamespace(
        enforce=True,
        project_bindings={
            "project-1": SimpleNamespace(
                tracker=tracker,
                epic_controller=controller,
            )
        },
    )
    orchestrator = SimpleNamespace(
        request_refresh=MagicMock(),
        _request_workflow_batch_continuation=MagicMock(return_value=True),
    )
    router = EpicWorkflowEventRouter(orchestrator, runtime)
    with patch(
        "oompah.epic_workflow_adapter.EpicWorkflowController"
    ) as ephemeral_controller:
        ephemeral_controller.return_value.evaluate.return_value = SimpleNamespace(
            tasks=()
        )
        router.on_issue_changed(
            "issue_state_changed",
            {
                "project_id": "project-1",
                "identifiers": ["FIRST", "SECOND"],
                "change": "batch-updated",
                "batch_id": "batch-1",
            },
        )
        router.drain_events(timeout=1.0)

    assert controller.schedule_action.call_count == 2
    assert {
        call.kwargs["action"] for call in controller.schedule_action.call_args_list
    } == {EpicAction.READINESS, EpicAction.TARGET_RESOLUTION}
    for call in controller.schedule_action.call_args_list:
        assert call.kwargs["payload"]["trigger_identifiers"] == ["FIRST", "SECOND"]
        assert call.kwargs["payload"]["batch_id"] == "batch-1"
    assert orchestrator._request_workflow_batch_continuation.call_count == 2
    router.close()


def test_event_router_offloads_tracker_work_and_preserves_delivery_order():
    parent = epic("TOP")
    children = [
        Issue(
            id=identifier,
            identifier=identifier,
            title=identifier,
            description="fixture",
            state=DONE,
            issue_type="task",
            project_id="project-1",
            parent_id="TOP",
        )
        for identifier in ("FIRST", "SECOND")
    ]
    issues = {item.identifier: item for item in (parent, *children)}
    observations = []

    class RecordingTracker:
        def fetch_issue_detail(self, identifier):
            observations.append((identifier, threading.get_ident()))
            return issues.get(identifier)

    controller = MagicMock()
    controller.scheduler = MagicMock()
    runtime = SimpleNamespace(
        enforce=True,
        project_bindings={
            "project-1": SimpleNamespace(
                tracker=RecordingTracker(), epic_controller=controller
            )
        },
    )
    orchestrator = SimpleNamespace(request_refresh=MagicMock())
    router = EpicWorkflowEventRouter(orchestrator, runtime)
    caller_thread = threading.get_ident()
    with patch(
        "oompah.epic_workflow_adapter.EpicWorkflowController"
    ) as ephemeral_controller:
        ephemeral_controller.return_value.evaluate.return_value = SimpleNamespace(
            tasks=()
        )
        router.on_issue_changed(
            "issue_state_changed",
            {"project_id": "project-1", "identifier": "FIRST"},
        )
        router.on_issue_changed(
            "issue_state_changed",
            {"project_id": "project-1", "identifier": "SECOND"},
        )
        router.drain_events(timeout=1.0)

    assert [identifier for identifier, _thread in observations] == [
        "FIRST",
        "TOP",
        "SECOND",
        "TOP",
    ]
    assert all(thread_id != caller_thread for _identifier, thread_id in observations)
    router.close()
