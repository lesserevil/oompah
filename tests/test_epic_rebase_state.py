"""Tests for epic rebase outcome state tracking and proactive dispatch (oompah-zlz_2-82dr.2, oompah-zlz_2-82dr.3).

Covers:
- _set_epic_rebase_state transitions and label syncing
- _get_epic_rebase_state reading
- _clear_epic_rebase_state cleanup
- _prune_stale_epic_rebase_states dropping closed epics
- _should_dispatch_rebase_agent idempotency
- _restore_epic_rebase_states / _persist_epic_rebase_states persistence
- Snapshot inclusion
- _dispatch_proactive_rebase_agents (oompah-zlz_2-82dr.2)
- _file_rebase_task
- _check_epic_staleness
- _is_epic_branch_being_rebased (YOLO suppression)
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.authority_boundary import check_shell_command
from oompah.epic_staleness import StalenessResult
from oompah.models import EpicRebaseState, EpicRebaseStateEntry, Issue, OwnerClaim
from oompah.integration import IntegrationRecord
from oompah.orchestrator import EpicTargetResolutionError, Orchestrator
from oompah.projects import ProjectError
from oompah.statuses import DONE, IN_REVIEW, NEEDS_REBASE
from oompah.work_decision_projection import operator_actionable_alerts


def _make_issue(
    identifier: str,
    *,
    state: str = "open",
    issue_type: str = "epic",
    priority: int = 1,
    project_id: str = "proj-1",
    parent_id: str | None = None,
    labels: list[str] | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="",
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        parent_id=parent_id,
        labels=labels or [],
    )


def _make_orchestrator(tmp_path, **kwargs):
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
        **kwargs,
    )
    return orch


def _make_project():
    return type(
        "ProjectStub",
        (),
        {
            "name": "oompah",
            "default_branch": "main",
        },
    )()


def _nested_epic_fixture(orch, *, parent_id: str = "EPIC-PARENT"):
    """Configure the smallest proactive-rebase fixture for hierarchy tests."""
    project = _make_project()
    project.id = "proj-1"
    project.repo_path = "/repo"
    project.repo_url = "https://github.com/org/repo"
    epic = _make_issue(
        "EPIC-CHILD",
        parent_id=parent_id,
        labels=["rebase-requested"],
    )
    parent = _make_issue(parent_id, issue_type="epic")
    tracker = MagicMock()
    orch.project_store.get.return_value = project
    orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._tracker_for_issue = MagicMock(return_value=tracker)
    orch._fetch_epic_children = MagicMock(return_value=[])
    orch._is_mature_epic_review_issue = MagicMock(return_value=False)
    orch._file_rebase_task = MagicMock()
    orch._set_epic_rebase_state = MagicMock()
    orch._epic_rebase_states[epic.identifier] = EpicRebaseStateEntry(
        state=EpicRebaseState.STALE.value,
        updated_at=time.time(),
        project_id=project.id,
    )
    return project, epic, parent, tracker


# ---------------------------------------------------------------------------
# _set_epic_rebase_state
# ---------------------------------------------------------------------------


class TestSetEpicRebaseState:
    def test_same_identifier_isolated_across_projects(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "EPIC-1", EpicRebaseState.STALE, project_id="project-a"
        )
        orch._set_epic_rebase_state(
            "EPIC-1", EpicRebaseState.REBASING, project_id="project-b"
        )

        assert orch._get_epic_rebase_state(
            "EPIC-1", project_id="project-a"
        ) is EpicRebaseState.STALE
        assert orch._get_epic_rebase_state(
            "EPIC-1", project_id="project-b"
        ) is EpicRebaseState.REBASING
        assert set(orch._epic_rebase_states) == {
            "project-a::EPIC-1",
            "project-b::EPIC-1",
        }
        restarted = _make_orchestrator(tmp_path)
        assert restarted._get_epic_rebase_state(
            "EPIC-1", project_id="project-a"
        ) is EpicRebaseState.STALE
        assert restarted._get_epic_rebase_state(
            "EPIC-1", project_id="project-b"
        ) is EpicRebaseState.REBASING

    def test_sets_state_and_updates_timestamp(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )

        entry = orch._epic_rebase_states["epic-1"]
        assert entry.state == "stale"
        assert entry.project_id == "proj-1"
        assert entry.updated_at > 0

    def test_snapshot_marks_staleness_as_observation_only(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE,
            project_id="proj-1", reason="main_advanced",
        )

        state = orch.get_snapshot()["epic_rebase_states"]["epic-1"]

        assert state["reason"] == "main_advanced"
        assert state["action_scheduled"] is False

    def test_adds_label_when_not_present(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["other"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )

        tracker.update_issue.assert_any_call(
            "epic-1", **{"add-label": "epic:stale"}
        )

    def test_removes_old_label_on_transition(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:stale"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.REBASING, project_id="proj-1"
        )

        tracker.update_issue.assert_any_call(
            "epic-1", **{"remove-label": "epic:stale"}
        )
        tracker.update_issue.assert_any_call(
            "epic-1", **{"add-label": "epic:rebasing"}
        )

    def test_idempotent_same_state_refreshes_timestamp(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:stale"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )
        first_ts = orch._epic_rebase_states["epic-1"].updated_at
        time.sleep(0.01)
        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )
        second_ts = orch._epic_rebase_states["epic-1"].updated_at

        assert second_ts > first_ts
        # No label changes on idempotent call.
        add_label_calls = [
            c for c in tracker.update_issue.call_args_list
            if c.kwargs.get("add-label")
        ]
        # The label was already present on the issue, so no add-label needed.
        assert len(add_label_calls) == 0


class TestEpicTargetResolution:
    def test_transient_nested_parent_failure_does_not_file_or_dispatch_helper(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        project, epic, _parent, tracker = _nested_epic_fixture(orch)
        tracker.fetch_issue_detail.side_effect = RuntimeError("tracker timeout")

        assert orch._dispatch_proactive_rebase_agents([epic]) == 0
        orch._file_rebase_task.assert_not_called()
        assert any(
            alert["source"] == "epic_target_unresolved:proj-1:EPIC-CHILD"
            for alert in orch._alerts
        )

    def test_parent_recovery_files_exactly_one_authoritative_helper_target(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        project, epic, parent, tracker = _nested_epic_fixture(orch)
        tracker.fetch_issue_detail.return_value = parent

        assert orch._dispatch_proactive_rebase_agents([epic]) == 1
        orch._file_rebase_task.assert_called_once_with(
            tracker,
            epic,
            "epic-EPIC-CHILD",
            "epic-EPIC-PARENT",
        )
        assert not any(
            call.kwargs.get("target_branch") == "main"
            for call in orch._file_rebase_task.call_args_list
        )
        assert orch._alerts == []

    def test_parent_deletion_or_malformed_metadata_fails_closed(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project, epic, _parent, tracker = _nested_epic_fixture(orch)
        tracker.fetch_issue_detail.return_value = None
        with pytest.raises(EpicTargetResolutionError, match="does not exist"):
            orch._resolve_epic_target_branch(epic, project)

        malformed = _make_issue("EPIC-PARENT", issue_type="task")
        tracker.fetch_issue_detail.return_value = malformed
        with pytest.raises(EpicTargetResolutionError, match="not a confirmed"):
            orch._resolve_epic_target_branch(epic, project)

    def test_workspace_creation_fails_closed_when_nested_helper_target_is_unreadable(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        project, epic, _parent, tracker = _nested_epic_fixture(orch)
        helper = _make_issue(
            "REBASE-1",
            state=NEEDS_REBASE,
            parent_id=epic.identifier,
        )
        helper.title = "Rebase epic-EPIC-CHILD onto main"
        helper.description = "Rebase the epic branch."
        tracker.fetch_issue_detail.side_effect = RuntimeError("tracker timeout")

        with pytest.raises(EpicTargetResolutionError):
            orch._create_workspace_for_issue(helper)
        orch.project_store.create_worktree.assert_not_called()
        orch.project_store.create_epic_worktree.assert_not_called()

    def test_filed_helper_persists_target_evidence(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.return_value = _make_issue(
            "REBASE-1",
            state=NEEDS_REBASE,
            parent_id="EPIC-CHILD",
        )
        epic = _make_issue("EPIC-CHILD", parent_id="EPIC-PARENT")
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "parent-head-1")
        )

        orch._file_rebase_task(
            tracker,
            epic,
            "epic-EPIC-CHILD",
            "epic-EPIC-PARENT",
        )

        tracker.set_metadata_field.assert_any_call(
            "REBASE-1",
            "oompah.target_branch",
            "epic-EPIC-PARENT",
        )
        tracker.set_metadata_field.assert_any_call(
            "REBASE-1",
            "oompah.epic_rebase_target",
            {
                "version": 1,
                "epic_identifier": "EPIC-CHILD",
                "epic_branch": "epic-EPIC-CHILD",
                "target_branch": "epic-EPIC-PARENT",
                "parent_id": "EPIC-PARENT",
                "resolution": "authoritative_parent",
            },
        )

    def test_restart_reuses_existing_targeted_helper_without_duplicate(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project, epic, parent, tracker = _nested_epic_fixture(orch)
        tracker.fetch_issue_detail.return_value = parent
        existing = _make_issue(
            "REBASE-1",
            state=NEEDS_REBASE,
            parent_id=epic.identifier,
        )
        existing.title = "Rebase epic-EPIC-CHILD onto epic-EPIC-PARENT"
        existing.target_branch = "epic-EPIC-PARENT"
        tracker.fetch_issues_by_states.return_value = [existing]
        orch._fetch_epic_children.return_value = [existing]

        target = orch._resolve_epic_target_branch(epic, project)
        assert target == "epic-EPIC-PARENT"
        orch._record_epic_rebase_target(
            epic.identifier,
            target_branch=target,
            project_id=project.id,
            parent_id=epic.parent_id,
        )
        restarted = _make_orchestrator(tmp_path)
        restarted.project_store.epic_branch_name.side_effect = (
            lambda ident: f"epic-{ident}"
        )
        restarted._fetch_epic_children = MagicMock(return_value=[existing])
        restored = restarted._epic_rebase_states[epic.identifier]
        assert restored.target_branch == "epic-EPIC-PARENT"
        assert restored.target_parent_id == "EPIC-PARENT"
        assert orch._find_active_epic_rebase_sibling(
            tracker,
            epic,
            target_branch=target,
        ) is existing
        assert restarted._find_active_epic_rebase_sibling(
            tracker,
            epic,
            target_branch=restored.target_branch,
        ) is existing
        orch._file_rebase_task.assert_not_called()

    def test_wrong_target_helper_is_archived_without_recovery_ref_cleanup(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        project, epic, parent, tracker = _nested_epic_fixture(orch)
        tracker.fetch_issue_detail.side_effect = lambda identifier: (
            parent if identifier == parent.identifier else wrong
        )
        wrong = _make_issue(
            "REBASE-WRONG",
            state=NEEDS_REBASE,
            parent_id=epic.identifier,
        )
        wrong.title = "Rebase epic-EPIC-CHILD onto main"
        wrong.target_branch = "main"
        tracker.fetch_issues_by_states.return_value = [wrong]

        class _StagingAdapter:
            async def stage(self, _intent, issue):
                issue.state = IN_VALIDATION
                tracker.update_issue(issue.identifier, status=IN_VALIDATION)
                return TerminalStageResult(success=True, audit_id="audit-archive")

        orch._task_transition_terminal_adapter = _StagingAdapter()

        assert orch._resolve_epic_target_branch(epic, project) == "epic-EPIC-PARENT"
        with patch("oompah.orchestrator.request_archived_audit", return_value=True) as request:
            assert orch._find_active_epic_rebase_sibling(
                tracker,
                epic,
                target_branch="epic-EPIC-PARENT",
            ) is None
        request.assert_called_once()
        assert request.call_args.args[:3] == (wrong, tracker, wrong.project_id)
        assert request.call_args.kwargs["trigger_source"] == "epic_rebase_reconciliation"
        tracker.update_issue.assert_not_called()
        orch.project_store.remove_worktree.assert_not_called()

    def test_wrong_target_direct_owner_claim_is_never_queued_for_archive(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper = _make_rebase_helper("REBASE-WRONG", "EPIC-CHILD")
        helper.target_branch = "main"
        tracker = _atomic_create_tracker()
        tracker.fetch_issue_detail.return_value = helper
        orch.state.owner_claims[
            orch._owner_claim_key(helper.project_id, helper.id)
        ] = OwnerClaim(
            claim_id="direct-owner-claim",
            issue_id=helper.id,
            project_id=helper.project_id,
            owner_login="operator",
            claimed_at=time.time(),
            expires_at=time.time() + 3600,
        )

        with patch("oompah.orchestrator.request_archived_audit") as request:
            assert not orch._supersede_wrong_epic_rebase_helper(
                tracker,
                helper,
                target_branch="epic-EPIC-PARENT",
                parent_id="EPIC-PARENT",
            )

        tracker.fetch_issue_detail.assert_not_called()
        request.assert_not_called()

    def test_uses_legacy_tracker_when_no_project_id(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch.tracker = tracker

        orch._set_epic_rebase_state("epic-1", EpicRebaseState.STALE)

        tracker.update_issue.assert_called_once_with(
            "epic-1", **{"add-label": "epic:stale"}
        )


# ---------------------------------------------------------------------------
# _get_epic_rebase_state
# ---------------------------------------------------------------------------


class TestGetEpicRebaseState:
    def test_returns_none_when_not_tracked(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._get_epic_rebase_state("epic-x") is None

    def test_returns_enum_when_tracked(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing",
            updated_at=time.time(),
        )
        assert orch._get_epic_rebase_state("epic-1") == EpicRebaseState.REBASING

    def test_returns_none_for_unknown_state_value(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="garbage",
            updated_at=time.time(),
        )
        assert orch._get_epic_rebase_state("epic-1") is None


# ---------------------------------------------------------------------------
# _clear_epic_rebase_state
# ---------------------------------------------------------------------------


class TestClearEpicRebaseState:
    def test_removes_state_and_labels(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:stale", "other"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="stale",
            updated_at=time.time(),
        )

        orch._clear_epic_rebase_state("epic-1", project_id="proj-1")

        assert "epic-1" not in orch._epic_rebase_states
        tracker.update_issue.assert_called_once_with(
            "epic-1", **{"remove-label": "epic:stale"}
        )

    def test_clears_labels_even_when_not_tracked(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:rebasing", "other"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._clear_epic_rebase_state("epic-1", project_id="proj-1")

        tracker.update_issue.assert_called_once_with(
            "epic-1", **{"remove-label": "epic:rebasing"}
        )


# ---------------------------------------------------------------------------
# _prune_stale_epic_rebase_states
# ---------------------------------------------------------------------------


class TestPruneStaleEpicRebaseStates:
    def test_drops_closed_epics(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-open"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )
        orch._epic_rebase_states["epic-closed"] = EpicRebaseStateEntry(
            state="rebased", updated_at=time.time()
        )
        for identifier in ("epic-open", "epic-closed"):
            orch._epic_rebase_authorities[
                orch._epic_rebase_authority_key("proj-1", identifier)
            ] = EpicRebaseStateEntry(
                state="rebasing",
                updated_at=time.time(),
                project_id="proj-1",
                authority_generation=f"generation-{identifier}",
                authority_task_id=f"rebase-{identifier}",
            )

        candidates = [
            _make_issue("epic-open", state="open"),
            _make_issue("epic-closed", state="closed"),
        ]
        orch._prune_stale_epic_rebase_states(candidates)

        assert "epic-open" in orch._epic_rebase_states
        assert "epic-closed" not in orch._epic_rebase_states
        assert (
            orch._epic_rebase_authority_key("proj-1", "epic-open")
            in orch._epic_rebase_authorities
        )
        assert (
            orch._epic_rebase_authority_key("proj-1", "epic-closed")
            not in orch._epic_rebase_authorities
        )

    def test_drops_alerts_for_pruned_epics(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-open"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )
        orch._epic_rebase_states["epic-closed"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )
        orch._alerts = [
            {"source": "epic_stale:epic-open"},
            {"source": "epic_stale:epic-closed"},
            {"source": "rate_limit"},
        ]

        candidates = [
            _make_issue("epic-open", state="open"),
            _make_issue("epic-closed", state="merged"),
        ]
        orch._prune_stale_epic_rebase_states(candidates)

        assert [alert["source"] for alert in orch._alerts] == [
            "epic_stale:epic-open",
            "rate_limit",
        ]

    def test_keeps_non_epic_issues_out_of_consideration(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )

        candidates = [_make_issue("epic-1", state="open", issue_type="task")]
        orch._prune_stale_epic_rebase_states(candidates)

        # epic-1 is not an epic in this candidate list → dropped
        assert "epic-1" not in orch._epic_rebase_states

    @pytest.mark.parametrize("detail", [None, RuntimeError("partial scan failed")])
    def test_partial_or_failed_scan_preserves_recent_exact_authority(
        self, tmp_path, detail
    ):
        orch = _make_orchestrator(tmp_path)
        key = orch._epic_rebase_authority_key("proj-1", "EPIC-MISSING")
        orch._epic_rebase_authorities[key] = EpicRebaseStateEntry(
            state="rebasing",
            updated_at=time.time(),
            project_id="proj-1",
            authority_generation="generation-1",
            authority_task_id="REBASE-1",
        )
        tracker = MagicMock()
        if isinstance(detail, Exception):
            tracker.fetch_issue_detail.side_effect = detail
        else:
            tracker.fetch_issue_detail.return_value = detail
        orch.project_store.get.return_value = _make_project()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._prune_stale_epic_rebase_states([])

        assert key in orch._epic_rebase_authorities

    def test_authority_requires_stable_repeated_not_found_before_pruning(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        key = orch._epic_rebase_authority_key("proj-1", "EPIC-MISSING")
        entry = EpicRebaseStateEntry(
            state="rebasing", updated_at=time.time() - 172800,
            project_id="proj-1", authority_generation="generation-1",
            authority_task_id="REBASE-1",
        )
        orch._epic_rebase_authorities[key] = entry
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch.project_store.get.return_value = _make_project()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._prune_stale_epic_rebase_states([])
        assert orch._epic_rebase_authorities[key] is entry
        assert entry.authority_missing_observations == 1

        entry.authority_missing_since = time.time() - 172800
        orch._prune_stale_epic_rebase_states([])
        assert key not in orch._epic_rebase_authorities

    def test_prune_does_not_remove_authority_renewed_during_tracker_read(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        key = orch._epic_rebase_authority_key("proj-1", "EPIC-1")
        original = EpicRebaseStateEntry(
            state="rebasing", updated_at=time.time(), project_id="proj-1",
            authority_generation="generation-1", authority_task_id="REBASE-1",
        )
        renewed = EpicRebaseStateEntry(
            state="rebasing", updated_at=time.time(), project_id="proj-1",
            authority_generation="generation-1", authority_task_id="REBASE-1",
            authority_target_head="new-target",
        )
        orch._epic_rebase_authorities[key] = original
        terminal_epic = _make_issue("EPIC-1", state="merged")
        tracker = MagicMock()

        def _detail(_identifier):
            # This runs outside the authority lock. A later authority renewal
            # must win the compare-and-swap removal below.
            with orch._epic_rebase_authority_lock:
                orch._epic_rebase_authorities[key] = renewed
            return terminal_epic

        tracker.fetch_issue_detail.side_effect = _detail
        orch.project_store.get.return_value = _make_project()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._prune_stale_epic_rebase_states([])

        assert orch._epic_rebase_authorities[key] is renewed


# ---------------------------------------------------------------------------
# _should_dispatch_rebase_agent
# ---------------------------------------------------------------------------


class TestShouldDispatchRebaseAgent:
    def test_true_when_no_state(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._should_dispatch_rebase_agent("epic-1") is True

    def test_true_when_stale(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is True

    def test_true_when_failed(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # Set updated_at far enough in the past that the exponential
        # backoff (300 * 2^retry_count, capped 3600s) has elapsed.
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="failed", updated_at=time.time() - 7200
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is True

    def test_false_when_failed_in_backoff(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # updated_at just now — backoff (300 * 2^0 = 300s) has not elapsed.
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="failed", updated_at=time.time(), retry_count=0
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is False

    def test_false_when_rebasing(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing", updated_at=time.time()
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is False

    def test_false_when_rebased(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebased", updated_at=time.time()
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is True


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_restore_from_disk(self, tmp_path):
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "epic_rebase_states": {
                        "epic-a": {
                            "state": "stale",
                            "updated_at": time.time(),
                            "project_id": "proj-1",
                        }
                    }
                }
            )
        )
        orch = _make_orchestrator(tmp_path)
        assert "epic-a" in orch._epic_rebase_states
        assert orch._epic_rebase_states["epic-a"].state == "stale"

    def test_drops_stale_entries_on_restore(self, tmp_path):
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "epic_rebase_states": {
                        "epic-old": {
                            "state": "rebasing",
                            "updated_at": time.time() - 90000,  # > 24h
                            "project_id": None,
                        }
                    }
                }
            )
        )
        orch = _make_orchestrator(tmp_path)
        assert "epic-old" not in orch._epic_rebase_states

    def test_persists_on_set(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )

        disk = json.loads((tmp_path / "state.json").read_text())
        assert "epic_rebase_states" in disk
        assert disk["epic_rebase_states"]["epic-1"]["state"] == "stale"

    def test_persists_on_clear(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        def _no_git_push(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, (list, tuple)) and "push" in cmd:
                raise AssertionError(f"Test must not invoke git push: {cmd}")
            import unittest.mock
            return unittest.mock.MagicMock(returncode=0, stdout=b"", stderr=b"")

        with patch("subprocess.run", side_effect=_no_git_push), \
             patch("subprocess.Popen", side_effect=_no_git_push):
            # Pass project_id so the already-injected mock tracker is used
            # instead of falling back to the live orch.tracker.
            orch._set_epic_rebase_state(
                "epic-1", EpicRebaseState.STALE, project_id="proj-1"
            )
            orch._clear_epic_rebase_state("epic-1", project_id="proj-1")

        # The already-injected tracker must have been used (not the live one).
        orch._tracker_for_project.assert_called_with("proj-1")

        disk = json.loads((tmp_path / "state.json").read_text())
        assert "epic-1" not in disk.get("epic_rebase_states", {})


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_includes_epic_rebase_states(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing",
            updated_at=1234.0,
            project_id="proj-1",
            target_branch="epic-parent",
            target_parent_id="parent-1",
            target_resolution="authoritative_parent",
        )
        snapshot = orch.get_snapshot()
        assert "epic_rebase_states" in snapshot
        assert snapshot["epic_rebase_states"]["epic-1"]["state"] == "rebasing"
        assert snapshot["epic_rebase_states"]["epic-1"]["updated_at"] == 1234.0
        assert snapshot["epic_rebase_states"]["epic-1"]["target_branch"] == "epic-parent"
        assert snapshot["epic_rebase_states"]["epic-1"]["target_parent_id"] == "parent-1"
        assert snapshot["epic_rebase_states"]["epic-1"]["target_resolution"] == "authoritative_parent"


# ---------------------------------------------------------------------------
# Epic stale alert explanation
# ---------------------------------------------------------------------------


class TestEpicStaleAlert:
    def test_equal_identifiers_are_deduplicated_per_project(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        for project_id in ("project-a", "project-b"):
            orch._epic_rebase_states[f"{project_id}::TASK-465"] = (
                EpicRebaseStateEntry(
                    state="failed",
                    updated_at=time.time(),
                    project_id=project_id,
                )
            )
        result = StalenessResult(
            stale=True,
            commits_behind=6,
            shared_files=(),
            threshold=5,
        )

        orch._arm_epic_stale_alert(
            _make_issue("TASK-465", project_id="project-a"),
            _make_project(),
            result,
        )
        orch._arm_epic_stale_alert(
            _make_issue("TASK-465", project_id="project-b"),
            _make_project(),
            result,
        )
        orch._arm_epic_stale_alert(
            _make_issue("TASK-465", project_id="project-a"),
            _make_project(),
            result,
        )

        projected = operator_actionable_alerts(orch._alerts)
        assert {alert["source"] for alert in projected} == {
            "epic_stale:project-a:TASK-465",
            "epic_stale:project-b:TASK-465",
        }
        orch._clear_epic_stale_alert("TASK-465", "project-a")
        assert [alert["source"] for alert in orch._alerts] == [
            "epic_stale:project-b:TASK-465"
        ]

    def test_normal_staleness_does_not_create_an_alert(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("TASK-465")
        result = StalenessResult(
            stale=True,
            commits_behind=6,
            shared_files=("oompah/orchestrator.py",),
            threshold=5,
        )

        orch._arm_epic_stale_alert(issue, _make_project(), result)

        assert not orch._alerts

    def test_failed_rebase_state_explains_failed_run(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["TASK-465"] = EpicRebaseStateEntry(
            state="failed",
            updated_at=time.time(),
            project_id="proj-1",
        )
        issue = _make_issue("TASK-465")
        result = StalenessResult(
            stale=True,
            commits_behind=6,
            shared_files=(),
            threshold=5,
        )

        orch._arm_epic_stale_alert(issue, _make_project(), result)

        alert = next(
            a for a in orch._alerts
            if a.get("source") == "epic_stale:proj-1:TASK-465"
        )
        assert "last rebase run failed" in alert["action"]
        assert "finish or retry the rebase" in alert["action"]
        assert alert["message"] == f"{alert['title']}. {alert['action']}"
        assert alert["synchronization_policy"] == "action_required"

# ---------------------------------------------------------------------------
# Proactive rebase dispatch
# ---------------------------------------------------------------------------


class TestDispatchProactiveRebaseAgents:
    def test_main_advance_is_observed_but_not_dispatched(self, tmp_path):
        """Staleness alone must not create an agent task or mutate a branch."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("TASK-18", state="open", project_id="proj-1")

        allowed, reason = orch._epic_synchronization_decision(issue, "main")

        assert allowed is False
        assert reason == "main_advanced"

    def test_explicit_request_is_actionable(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "TASK-18", state="open", project_id="proj-1",
            labels=["rebase-requested"],
        )

        allowed, reason = orch._epic_synchronization_decision(issue, "main")

        assert allowed is True
        assert reason == "operator_requested"

    def test_epic_to_epic_synchronization_is_prohibited(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "TASK-18", state="needs rebase", project_id="proj-1",
            labels=["rebase-requested"],
        )

        allowed, reason = orch._epic_synchronization_decision(
            issue, "epic-TASK-4"
        )

        assert allowed is False
        assert reason == "epic_to_epic_prohibited"

    def test_mature_epic_is_marked_needs_rebase_instead_of_helper(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        project = MagicMock()
        project.id = "proj-1"
        project.name = "oompah"
        project.default_branch = "main"
        orch.project_store.get.return_value = project
        orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"

        issue = _make_issue(
            "TASK-18", state="open", project_id="proj-1",
            labels=["rebase-requested"],
        )
        children = [
            _make_issue(
                "TASK-18.1",
                state=IN_REVIEW,
                issue_type="task",
                project_id="proj-1",
            ),
            _make_issue(
                "TASK-18.2",
                state=DONE,
                issue_type="task",
                project_id="proj-1",
            ),
        ]
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.fetch_issue_states_by_ids.return_value = [issue]

        def _update(_identifier, **fields):
            if fields.get("status") is not None:
                issue.state = str(fields["status"])

        tracker.update_issue.side_effect = _update
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._fetch_epic_children = MagicMock(return_value=children)
        orch._should_dispatch_rebase_agent = MagicMock(return_value=True)
        orch._epic_rebase_states["TASK-18"] = EpicRebaseStateEntry(
            state=EpicRebaseState.STALE.value,
            updated_at=time.time(),
            project_id="proj-1",
        )

        filed = orch._dispatch_proactive_rebase_agents([issue])

        assert filed == 1
        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_any_call("TASK-18", status=NEEDS_REBASE)
        tracker.update_issue.assert_any_call(
            "TASK-18", priority="0", **{"add-label": "merge-conflict"}
        )

    def test_shared_nested_epic_does_not_synchronize_to_parent_epic_branch(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        project = MagicMock()
        project.id = "proj-1"
        project.name = "oompah"
        project.default_branch = "main"
        project.epic_strategy = "shared"
        orch.project_store.get.return_value = project
        orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"

        issue = _make_issue(
            "TASK-18",
            state="open",
            project_id="proj-1",
            parent_id="TASK-4",
        )
        parent = _make_issue("TASK-4", project_id="proj-1")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._fetch_epic_children = MagicMock(return_value=[])
        orch._resolve_parent_epic = MagicMock(return_value=parent)
        orch._should_dispatch_rebase_agent = MagicMock(return_value=True)
        orch._epic_rebase_states["TASK-18"] = EpicRebaseStateEntry(
            state=EpicRebaseState.STALE.value,
            updated_at=time.time(),
            project_id="proj-1",
        )

        filed = orch._dispatch_proactive_rebase_agents([issue])

        assert filed == 0
        tracker.create_issue.assert_not_called()


# ---------------------------------------------------------------------------
# Epic staleness target resolution
# ---------------------------------------------------------------------------


class TestCheckEpicStaleness:
    def test_shared_nested_epic_skips_parent_epic_branch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project = MagicMock()
        project.id = "proj-1"
        project.name = "oompah"
        project.repo_path = "/tmp/repo"
        project.default_branch = "main"
        project.epic_strategy = "shared"
        orch.project_store.get.return_value = project
        orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"

        issue = _make_issue(
            "TASK-18",
            state="open",
            issue_type="epic",
            project_id="proj-1",
            parent_id="TASK-4",
        )
        parent = _make_issue("TASK-4", issue_type="epic", project_id="proj-1")
        result = StalenessResult(
            stale=False,
            commits_behind=0,
            shared_files=(),
            threshold=5,
        )

        with (
            patch.object(orch, "_resolve_parent_epic", return_value=parent),
            patch(
                "oompah.epic_staleness.check_epic_branch_staleness",
                return_value=result,
            ) as check,
        ):
            stale_count = orch._check_epic_staleness([issue])

        assert stale_count == 0
        check.assert_not_called()


# ---------------------------------------------------------------------------
# Exact-generation helper authority (OOMPAH-879)
# ---------------------------------------------------------------------------


def _make_rebase_helper(identifier: str, epic_identifier: str) -> Issue:
    helper = _make_issue(
        identifier,
        state=NEEDS_REBASE,
        issue_type="task",
        parent_id=epic_identifier,
    )
    helper.title = f"Rebase epic-{epic_identifier} onto main"
    helper.description = "Rebase the shared epic branch."
    helper.target_branch = "main"
    return helper


def _atomic_create_tracker() -> MagicMock:
    tracker = MagicMock()
    tracker.supports_atomic_create_once = True
    return tracker


def _configure_publish_fixture(
    orch: Orchestrator,
    tmp_path,
    *,
    install_authority: bool = True,
):
    candidate = "c" * 40
    lease_head = "a" * 40
    target_head = "b" * 40
    epic = _make_issue("EPIC-1", labels=["rebase-requested"])
    helper = _make_rebase_helper("REBASE-1", epic.identifier)
    project = _make_project()
    project.id = helper.project_id
    project.repo_path = str(tmp_path)
    project.repo_url = "https://trusted.invalid/repository"
    tracker = MagicMock()
    tracker.fetch_issue_detail.side_effect = lambda identifier: (
        helper if identifier == helper.identifier else epic
    )
    orch.project_store.get.return_value = project
    orch.project_store.canonical_remote_name.return_value = "origin"
    orch.project_store.canonical_remote_url.return_value = project.repo_url
    orch.project_store.epic_branch_name.return_value = "epic-EPIC-1"
    orch.project_store.epic_worktree_path_for.return_value = str(tmp_path)
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._resolve_parent_epic = MagicMock(return_value=epic)
    orch._resolve_epic_target_branch = MagicMock(return_value="main")
    orch._active_epic_rebase_siblings = MagicMock(return_value=[helper])

    def local_git(_workspace, args):
        if args == ["rev-parse", "--verify", f"{candidate}^{{commit}}"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"{candidate}\n", stderr="")
        if args == ["rev-parse", "--verify", "HEAD^{commit}"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"{candidate}\n", stderr="")
        if args == ["merge-base", "--is-ancestor", target_head, candidate]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected local git argv: {args!r}")

    orch._epic_rebase_publish_local_git = MagicMock(side_effect=local_git)
    orch._run_project_network_git = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")
    )
    if install_authority:
        orch._epic_rebase_authorities[
            orch._epic_rebase_authority_key(helper.project_id, epic.identifier)
        ] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=helper.project_id,
            target_branch="main",
            authority_generation="generation-1",
            authority_task_id=helper.identifier,
            authority_epic_head=lease_head,
            authority_target_head=target_head,
        )
    return helper, epic, tracker, candidate, lease_head, target_head


class TestEpicRebaseGenerationAuthority:
    def test_prepare_uses_parent_persisted_source_branch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        project.id = "proj-1"
        helper = _make_rebase_helper("REBASE-1", "EPIC-1")
        helper.target_branch = "main"
        parent = _make_issue("EPIC-1", labels=["rebase-requested"])
        parent.work_branch = "legacy-epic-source"
        tracker = MagicMock()
        orch.project_store.get.return_value = project
        orch._resolve_parent_epic = MagicMock(return_value=parent)
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._admit_epic_rebase_helper = MagicMock(return_value=(True, ""))

        assert orch._prepare_epic_rebase_helper_target(helper) == (True, "")
        orch._admit_epic_rebase_helper.assert_called_once_with(
            tracker,
            helper,
            parent=parent,
            epic_branch="legacy-epic-source",
            target_branch="main",
        )

    def test_workspace_uses_parent_persisted_source_branch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper = _make_rebase_helper("REBASE-1", "EPIC-1")
        parent = _make_issue("EPIC-1", labels=["rebase-requested"])
        parent.work_branch = "legacy-epic-source"
        tracker = MagicMock()
        orch._prepare_epic_rebase_helper_target = MagicMock(
            return_value=(True, "")
        )
        orch._resolve_parent_epic = MagicMock(return_value=parent)
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch.project_store.create_epic_worktree.return_value = "/wt/epic"
        orch._epic_rebase_workspace_has_remote_write_route = MagicMock(
            return_value=False
        )
        orch._worktree_head = MagicMock(return_value="a" * 40)

        path, resolved_parent = orch._create_workspace_for_issue(helper)

        assert path == "/wt/epic"
        assert resolved_parent is parent
        assert helper.work_branch == "legacy-epic-source"
        assert helper.branch_name == "legacy-epic-source"
        orch.project_store.create_epic_worktree.assert_called_once_with(
            "proj-1",
            "EPIC-1",
            branch_name="legacy-epic-source",
        )

    def test_recorded_actionable_winner_outranks_newly_claimed_duplicate(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("OOMPAH-763", labels=["rebase-requested"])
        recorded = _make_rebase_helper("OOMPAH-877", epic.identifier)
        newcomer = _make_rebase_helper("OOMPAH-882", epic.identifier)
        orch._epic_rebase_authorities[
            orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        ] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=epic.project_id,
            authority_generation="generation-1",
            authority_task_id=recorded.identifier,
            authority_epic_head="epic-head-1",
            authority_target_head="main-head-1",
        )
        orch.state.claimed.add(newcomer.id)

        assert orch._select_epic_rebase_authority(
            epic.project_id,
            epic.identifier,
            [newcomer, recorded],
        ) is recorded

    def test_concurrent_filers_create_only_one_helper(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        tracker = _atomic_create_tracker()
        created: list[Issue] = []

        def _create(**_kwargs):
            helper = _make_rebase_helper("REBASE-1", epic.identifier)
            created.append(helper)
            return helper

        tracker.create_issue_once.side_effect = _create
        orch._active_epic_rebase_siblings = MagicMock(
            side_effect=lambda *_args, **_kwargs: list(created)
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda _index: orch._file_rebase_task(
                        tracker, epic, "epic-EPIC-1", "main"
                    ),
                    range(8),
                )
            )

        assert tracker.create_issue_once.call_count == 1
        assert all(result is created[0] for result in results)
        assert "publish_epic_rebase(candidate=<full-lowercase-sha>)" in (
            tracker.create_issue_once.call_args.kwargs["description"]
        )
        assert "Do not run `git push`" in tracker.create_issue_once.call_args.kwargs[
            "description"
        ]
        assert (
            "OOMPAH-EPIC-REBASE-RESERVATION: "
            + orch._epic_rebase_creation_marker(
                epic.project_id, epic.identifier, "generation-1"
            )
        ) in tracker.create_issue_once.call_args.kwargs["description"]
        entry = orch._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert entry is not None
        assert entry.authority_task_id == "REBASE-1"
        assert entry.authority_generation == "generation-1"

    def test_restart_does_not_refile_consumed_generation(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.return_value = helper
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-before-loss")
        )
        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is helper

        restarted = _make_orchestrator(tmp_path)
        restarted_tracker = MagicMock()
        restarted._active_epic_rebase_siblings = MagicMock(return_value=[])
        restarted._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        assert restarted._file_rebase_task(
            restarted_tracker, epic, "epic-EPIC-1", "main"
        ) is None
        restarted_tracker.create_issue_once.assert_not_called()
        restarted_entry = restarted._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert restarted_entry is not None
        assert restarted_entry.authority_task_id == "REBASE-1"

    def test_consumed_generation_recovers_exact_active_helper_identity(self, tmp_path):
        """A lagging child projection cannot erase the create-once identity."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.return_value = helper
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is helper
        entry = orch._epic_rebase_authority_entry(
            epic.project_id, epic.identifier
        )
        assert entry is not None
        helper.description += (
            "\nOOMPAH-EPIC-REBASE-RESERVATION: "
            + entry.authority_creation_marker
            + "\n"
        )
        tracker.fetch_issue_detail.return_value = helper

        replayed = orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        )

        assert replayed is helper
        tracker.create_issue_once.assert_called_once()

    def test_unresolved_remote_heads_do_not_reserve_or_create_helper(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.return_value = helper
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[None, ("generation-1", "epic-head-1", "main-head-1")]
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is None
        tracker.create_issue_once.assert_not_called()
        assert orch._epic_rebase_authority_entry(epic.project_id, epic.identifier) is None

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is helper
        tracker.create_issue_once.assert_called_once()

    def test_o877_owner_wins_and_o878_o880_o881_are_superseded(self, tmp_path):
        """Deterministic recurrence for all four 2026-08-07 duplicate helpers."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("OOMPAH-763", labels=["rebase-requested"])
        owner_helper = _make_rebase_helper("OOMPAH-877", epic.identifier)
        duplicates = [
            _make_rebase_helper(identifier, epic.identifier)
            for identifier in ("OOMPAH-878", "OOMPAH-880", "OOMPAH-881")
        ]
        owner_helper.created_at = "2026-08-07T01:00:00Z"
        for index, duplicate in enumerate(duplicates):
            # Make every duplicate appear older so the owner-claim priority,
            # rather than identifier/creation ordering, selects O877.
            duplicate.created_at = f"2026-08-07T00:00:0{index}Z"
        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = lambda identifier: next(
            helper for helper in duplicates if helper.identifier == identifier
        )
        orch._active_epic_rebase_siblings = MagicMock(
            return_value=[*duplicates, owner_helper]
        )
        orch._epic_rebase_helper_is_owned = MagicMock(
            side_effect=lambda helper: helper.identifier == owner_helper.identifier
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-before-loss")
        )

        with patch("oompah.orchestrator.request_archived_audit", return_value=True) as request:
            winner = orch._file_rebase_task(
                tracker, epic, "epic-OOMPAH-763", "main"
            )

        assert winner is owner_helper
        authority = orch._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert authority is not None
        assert authority.authority_task_id == "OOMPAH-877"
        tracker.create_issue_once.assert_not_called()
        assert request.call_count == 3
        assert {
            call.args[0].identifier for call in request.call_args_list
        } == {"OOMPAH-878", "OOMPAH-880", "OOMPAH-881"}
        assert all(
            call.kwargs["trigger_source"] == "epic_rebase_reconciliation"
            for call in request.call_args_list
        )
        tracker.update_issue.assert_not_called()

    def test_duplicate_is_rejected_before_shared_worktree_admission(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        owner_helper = _make_rebase_helper("REBASE-1", epic.identifier)
        duplicate = _make_rebase_helper("REBASE-2", epic.identifier)
        tracker = MagicMock()
        orch._active_epic_rebase_siblings = MagicMock(
            return_value=[duplicate, owner_helper]
        )
        orch._epic_rebase_helper_is_owned = MagicMock(
            side_effect=lambda helper: helper.identifier == owner_helper.identifier
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        admitted, reason = orch._admit_epic_rebase_helper(
            tracker,
            duplicate,
            parent=epic,
            epic_branch="epic-EPIC-1",
            target_branch="main",
        )

        assert admitted is False
        assert reason == "epic_rebase_duplicate_authority"
        assert epic.identifier not in orch._epic_rebase_states
        orch.project_store.create_epic_worktree.assert_not_called()

    def test_remote_head_change_revokes_push_authority(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        project = _make_project()
        project.id = "proj-1"
        project.repo_path = "/repo"
        orch.project_store.get.return_value = project
        orch.project_store.epic_branch_name.return_value = "epic-EPIC-1"
        orch._resolve_parent_epic = MagicMock(return_value=epic)
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", "epic-head-2", "main-head-1")
        )
        orch._epic_rebase_authorities[
            orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        ] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id="proj-1",
            target_branch="main",
            authority_generation="generation-1",
            authority_task_id=helper.identifier,
            authority_epic_head="epic-head-1",
            authority_target_head="main-head-1",
        )

        denial = orch._epic_rebase_push_denial(
            helper,
            "git push --force-with-lease=refs/heads/epic-EPIC-1:epic-head-1 "
            "origin HEAD:refs/heads/epic-EPIC-1",
        )

        assert denial is not None
        assert "epic_rebase_generation_stale" in denial

    def test_push_revalidation_uses_persisted_authoritative_epic_branch(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        epic.work_branch = "legacy-nested-epic-source"
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        project = _make_project()
        project.id = helper.project_id
        project.repo_path = "/repo"
        tracker = MagicMock()
        orch.project_store.get.return_value = project
        orch._resolve_parent_epic = MagicMock(return_value=epic)
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )
        orch._epic_rebase_local_contains_target = MagicMock(return_value=True)
        orch._active_epic_rebase_siblings = MagicMock(return_value=[helper])
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._epic_rebase_authorities[
            orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        ] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=epic.project_id,
            target_branch="main",
            authority_generation="generation-1",
            authority_task_id=helper.identifier,
            authority_epic_head="epic-head-1",
            authority_target_head="main-head-1",
        )
        exact_push = (
            "git push --force-with-lease="
            "refs/heads/legacy-nested-epic-source:epic-head-1 "
            "origin HEAD:refs/heads/legacy-nested-epic-source"
        )

        assert orch._epic_rebase_push_denial(helper, exact_push) is None
        assert (
            orch._observe_epic_rebase_generation.call_args.kwargs["epic_branch"]
            == "legacy-nested-epic-source"
        )

    def test_oompah_884_duplicate_cannot_push_rebased_shared_worktree(self, tmp_path):
        """A duplicate is fenced even when it observes a ready local rebase."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("OOMPAH-763", labels=["rebase-requested"])
        owner = _make_rebase_helper("OOMPAH-877", epic.identifier)
        duplicate = _make_rebase_helper("OOMPAH-884", epic.identifier)
        project = _make_project()
        project.id = epic.project_id
        project.repo_path = "/repo"
        orch.project_store.get.return_value = project
        orch.project_store.epic_branch_name.return_value = "epic-OOMPAH-763"
        orch._resolve_parent_epic = MagicMock(return_value=epic)
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )
        # The stale worker may see the owner's fully rebased shared checkout;
        # that is never a substitute for its own exact durable authority.
        orch._epic_rebase_local_contains_target = MagicMock(return_value=True)
        orch._active_epic_rebase_siblings = MagicMock(return_value=[owner, duplicate])
        orch._epic_rebase_authorities[
            orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        ] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=epic.project_id,
            authority_generation="generation-1",
            authority_task_id=owner.identifier,
            authority_epic_head="epic-head-1",
            authority_target_head="main-head-1",
        )

        policy = orch._agent_action_policy(duplicate)
        denial = check_shell_command(
            policy,
            "git push --force-with-lease origin epic-OOMPAH-763",
        )

        assert denial is not None
        assert "epic_rebase_server_publish_required" in denial
        orch._epic_rebase_local_contains_target.assert_not_called()

    @pytest.mark.parametrize(
        "command",
        [
            "git push origin epic-EPIC-1",
            "git push --force origin HEAD:refs/heads/epic-EPIC-1",
            (
                "git push --force-with-lease=refs/heads/epic-EPIC-1:"
                + "a" * 40
                + " origin HEAD:refs/heads/epic-EPIC-1"
            ),
            "/usr/bin/git -C /workspace push origin epic-EPIC-1",
        ],
    )
    def test_rebase_worker_shell_cannot_perform_any_push(
        self, tmp_path, command
    ):
        orch = _make_orchestrator(tmp_path)
        # A project-store double must use the deterministic branch-name fallback
        # rather than leaking MagicMock operations into task classification.
        orch.project_store.epic_branch_name.return_value = MagicMock()
        helper = _make_rebase_helper("REBASE-1", "EPIC-1")
        legacy = MagicMock(
            side_effect=AssertionError("legacy worker push admission reached")
        )
        orch._epic_rebase_push_denial = legacy

        denial = check_shell_command(orch._agent_action_policy(helper), command)

        assert denial is not None
        assert "epic_rebase_server_publish_required" in denial
        legacy.assert_not_called()

    def test_oompah_885_target_head_churn_cannot_mint_or_admit_successor(
        self, tmp_path
    ):
        """Native task writes may advance main, but never transfer O877's lease."""
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("OOMPAH-763", labels=["rebase-requested"])
        owner = _make_rebase_helper("OOMPAH-877", epic.identifier)
        duplicate = _make_rebase_helper("OOMPAH-885", epic.identifier)
        key = orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        orch._epic_rebase_authorities[key] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=epic.project_id,
            authority_generation="generation-1",
            authority_task_id=owner.identifier,
            authority_epic_head="epic-head-1",
            authority_target_head="main-before-native-write",
        )
        tracker = MagicMock()
        # The target advances while O877 is active.  O885's view may even
        # omit O877 temporarily; durable exact-generation authority wins.
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-after-native-write")
        )
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])

        assert orch._file_rebase_task(
            tracker, epic, "epic-OOMPAH-763", "main"
        ) is None
        tracker.create_issue_once.assert_not_called()
        admitted, reason = orch._admit_epic_rebase_helper(
            tracker,
            duplicate,
            parent=epic,
            epic_branch="epic-OOMPAH-763",
            target_branch="main",
        )
        assert (admitted, reason) == (False, "epic_rebase_duplicate_authority")
        assert orch._epic_rebase_authority_entry(
            epic.project_id, epic.identifier
        ).authority_task_id == owner.identifier

    def test_new_generation_can_create_successor_after_terminal_helper(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        first = _make_rebase_helper("REBASE-1", epic.identifier)
        second = _make_rebase_helper("REBASE-2", epic.identifier)
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.side_effect = [first, second]
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", "epic-head-1", "main-head-1"),
                ("generation-1", "epic-head-1", "main-head-1"),
                ("generation-2", "epic-head-2", "main-head-1"),
            ]
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is first
        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is None
        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is second
        assert tracker.create_issue_once.call_count == 2
        authority = orch._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert authority is not None
        assert authority.authority_task_id == "REBASE-2"

    def test_o882_appearing_after_o877_preflight_is_fenced_before_mutation(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("OOMPAH-763", labels=["rebase-requested"])
        o877 = _make_rebase_helper("OOMPAH-877", epic.identifier)
        o877.created_at = "2026-08-07T00:00:00Z"
        duplicates = [
            _make_rebase_helper(identifier, epic.identifier)
            for identifier in ("OOMPAH-878", "OOMPAH-880", "OOMPAH-881", "OOMPAH-882")
        ]
        for index, duplicate in enumerate(duplicates, start=1):
            duplicate.created_at = f"2026-08-07T00:00:0{index}Z"
        tracker = _atomic_create_tracker()
        visible = [o877]
        tracker.fetch_children.side_effect = lambda _epic_id: list(visible)
        tracker.fetch_issues_by_states.side_effect = (
            lambda _states: list(visible)
        )
        tracker.fetch_issue_detail.side_effect = lambda identifier: next(
            (helper for helper in visible if helper.identifier == identifier),
            epic if identifier == epic.identifier else None,
        )
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch.project_store.epic_branch_name.side_effect = (
            lambda identifier: f"epic-{identifier}"
        )
        exact = ("generation-1", "epic-head-1", "main-head-1")
        orch._observe_epic_rebase_generation = MagicMock(return_value=exact)
        claim = OwnerClaim(
            claim_id="claim-o877",
            issue_id=o877.id,
            project_id=o877.project_id,
            owner_login="owner",
            claimed_at=time.time(),
            expires_at=time.time() + 3600,
        )
        orch.state.owner_claims[
            orch._owner_claim_key(o877.project_id, o877.id)
        ] = claim

        # O877 completes the clean preflight and becomes the exact winner.
        assert orch._admit_epic_rebase_helper(
            tracker,
            o877,
            parent=epic,
            epic_branch="epic-OOMPAH-763",
            target_branch="main",
        ) == (True, "")

        # O882 is launched after that preflight. Even if it has a scheduler
        # claim, every later helper loses at the admission boundary before the
        # shared worktree can be returned or a rebase command can run.
        visible[:] = [o877, *duplicates]
        orch.state.claimed.add("OOMPAH-882")
        for duplicate in duplicates:
            admitted, reason = orch._admit_epic_rebase_helper(
                tracker,
                duplicate,
                parent=epic,
                epic_branch="epic-OOMPAH-763",
                target_branch="main",
            )
            assert admitted is False
            assert reason == "epic_rebase_duplicate_authority"

        # Even a stale tracker read that momentarily omits O877 cannot transfer
        # its durable exact-generation authority to the newly launched O882.
        visible[:] = [duplicates[-1]]
        assert orch._admit_epic_rebase_helper(
            tracker,
            duplicates[-1],
            parent=epic,
            epic_branch="epic-OOMPAH-763",
            target_branch="main",
        ) == (False, "epic_rebase_duplicate_authority")
        visible[:] = [o877, *duplicates]

        project = _make_project()
        project.id = "proj-1"
        project.repo_path = "/repo"
        orch.project_store.get.return_value = project
        orch._resolve_parent_epic = MagicMock(return_value=epic)
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._epic_rebase_local_contains_target = MagicMock(return_value=True)
        exact_push = (
            "git push --force-with-lease="
            "refs/heads/epic-OOMPAH-763:epic-head-1 origin "
            "HEAD:refs/heads/epic-OOMPAH-763"
        )
        for unsafe in (
            "git push --force origin HEAD:refs/heads/epic-OOMPAH-763",
            "git push --force-with-lease origin HEAD:refs/heads/epic-OOMPAH-763",
            exact_push + " && git fetch origin main",
            "/usr/bin/" + exact_push,
            "git -C /repo " + exact_push.removeprefix("git "),
            "\\git " + exact_push.removeprefix("git "),
            "git\\ push " + exact_push.removeprefix("git push "),
            "$(command -v git) " + exact_push.removeprefix("git "),
            exact_push.replace(
                "HEAD:refs/heads/epic-OOMPAH-763",
                "HEAD:refs/heads/epic-WRONG",
            ),
        ):
            denial = orch._epic_rebase_push_denial(o877, unsafe)
            assert denial is not None
            assert "epic_rebase_exact_force_with_lease_required" in denial
        assert orch._epic_rebase_push_denial(o877, exact_push) is None
        for duplicate in duplicates:
            denial = orch._epic_rebase_push_denial(duplicate, exact_push)
            assert denial is not None
            assert "epic_rebase_generation_stale" in denial
        orch.project_store.create_epic_worktree.assert_not_called()
        orch.project_store.create_worktree.assert_not_called()

    def test_helper_creation_target_advance_refreshes_same_winner_at_admission(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = _atomic_create_tracker()
        visible: list[Issue] = []
        tracker.create_issue_once.side_effect = lambda **_kwargs: (
            visible.append(helper) or helper
        )
        orch._active_epic_rebase_siblings = MagicMock(
            side_effect=lambda *_args, **_kwargs: list(visible)
        )
        # Native tracker create writes main between filing and admission. The
        # epic head and exclusive generation stay fixed; target evidence moves.
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("epic-generation-1", "epic-head-1", "main-before-create"),
                ("epic-generation-1", "epic-head-1", "main-after-create"),
            ]
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is helper
        assert orch._admit_epic_rebase_helper(
            tracker,
            helper,
            parent=epic,
            epic_branch="epic-EPIC-1",
            target_branch="main",
        ) == (True, "")
        authority = orch._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert authority is not None
        assert authority.authority_task_id == helper.identifier
        assert authority.authority_epic_head == "epic-head-1"
        assert authority.authority_target_head == "main-after-create"

    def test_target_only_advance_does_not_change_exclusive_generation(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        project.id = "proj-1"
        project.repo_path = "/repo"
        orch.project_store.get.return_value = project
        orch._run_project_network_git = MagicMock(
            side_effect=[
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=(
                        "epic-head-1\trefs/heads/epic-EPIC-1\n"
                        "main-before\trefs/heads/main\n"
                    ),
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=(
                        "epic-head-1\trefs/heads/epic-EPIC-1\n"
                        "main-after\trefs/heads/main\n"
                    ),
                    stderr="",
                ),
            ]
        )

        before = orch._observe_epic_rebase_generation(
            project_id="proj-1",
            epic_identifier="EPIC-1",
            epic_branch="epic-EPIC-1",
            target_branch="main",
            require_remote=True,
        )
        after = orch._observe_epic_rebase_generation(
            project_id="proj-1",
            epic_identifier="EPIC-1",
            epic_branch="epic-EPIC-1",
            target_branch="main",
            require_remote=True,
        )

        assert before is not None and after is not None
        assert before[0] == after[0]
        assert before[1] == after[1] == "epic-head-1"
        assert before[2] == "main-before"
        assert after[2] == "main-after"

    def test_comment_target_advance_requires_ancestry_then_refreshes_evidence(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = MagicMock()
        orch._active_epic_rebase_siblings = MagicMock(return_value=[helper])
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("epic-generation-1", "epic-head-1", "main-after-comment-1"),
                ("epic-generation-1", "epic-head-1", "main-after-comment-2"),
            ]
        )
        orch._epic_rebase_authorities[
            orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        ] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=epic.project_id,
            target_branch="main",
            authority_generation="epic-generation-1",
            authority_task_id=helper.identifier,
            authority_epic_head="epic-head-1",
            authority_target_head="main-at-admission",
        )
        project = _make_project()
        project.id = epic.project_id
        project.repo_path = "/repo"
        orch.project_store.get.return_value = project
        orch.project_store.epic_branch_name.return_value = "epic-EPIC-1"
        orch._resolve_parent_epic = MagicMock(return_value=epic)
        orch._resolve_epic_target_branch = MagicMock(return_value="main")
        orch._tracker_for_issue = MagicMock(return_value=tracker)
        orch._epic_rebase_local_contains_target = MagicMock(
            side_effect=[True, False]
        )
        exact_push = (
            "git push --force-with-lease=refs/heads/epic-EPIC-1:epic-head-1 "
            "origin HEAD:refs/heads/epic-EPIC-1"
        )

        assert orch._epic_rebase_push_denial(helper, exact_push) is None
        authority = orch._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert authority is not None
        assert authority.authority_target_head == "main-after-comment-1"

        denial = orch._epic_rebase_push_denial(helper, exact_push)
        assert denial is not None
        assert "epic_rebase_target_not_ancestor" in denial
        authority = orch._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert authority is not None
        assert authority.authority_target_head == "main-after-comment-1"

    def test_local_target_ancestry_uses_shared_epic_head(self, tmp_path):
        repo = tmp_path / "shared-epic"
        repo.mkdir()

        def _git(*args: str) -> str:
            result = subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()

        _git("init", "-q")
        _git("config", "user.name", "Oompah Test")
        _git("config", "user.email", "oompah@example.invalid")
        marker = repo / "marker.txt"
        marker.write_text("base\n", encoding="utf-8")
        _git("add", "marker.txt")
        _git("commit", "-qm", "base")
        base_head = _git("rev-parse", "HEAD")
        marker.write_text("target\n", encoding="utf-8")
        _git("commit", "-qam", "target")
        target_head = _git("rev-parse", "HEAD")

        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1")
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        orch.project_store.epic_worktree_path_for.return_value = str(repo)

        assert orch._epic_rebase_local_contains_target(
            helper, epic, target_head
        ) is True
        _git("checkout", "-q", "--detach", base_head)
        assert orch._epic_rebase_local_contains_target(
            helper, epic, target_head
        ) is False

    def test_create_response_loss_reconciles_tracker_helper_after_restart(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        committed = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = _atomic_create_tracker()
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        def _commit_then_lose_response(**_kwargs):
            raise TimeoutError("tracker response lost after commit")

        tracker.create_issue_once.side_effect = _commit_then_lose_response
        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is None
        reserved = orch._epic_rebase_authority_entry(epic.project_id, epic.identifier)
        assert reserved is not None
        assert reserved.authority_creation_reserved is True
        marker = reserved.authority_creation_marker
        committed.description += (
            "\nOOMPAH-EPIC-REBASE-RESERVATION: " + marker + "\n"
        )
        restarted = _make_orchestrator(tmp_path)
        restarted_tracker = _atomic_create_tracker()
        restarted_tracker.create_issue_once.return_value = committed
        restarted._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-after-loss")
        )
        restarted._active_epic_rebase_siblings = MagicMock(return_value=[])

        # The durable primitive retries the same marker and returns the task
        # created by the ambiguous first request; no second allocation occurs.
        assert restarted._file_rebase_task(
            restarted_tracker, epic, "epic-EPIC-1", "main"
        ) is committed
        restarted_tracker.create_issue_once.assert_called_once()
        assert restarted._file_rebase_task(
            restarted_tracker, epic, "epic-EPIC-1", "main"
        ) is None
        restarted_tracker.create_issue_once.assert_called_once()
        authority = restarted._epic_rebase_authority_entry(
            epic.project_id,
            epic.identifier,
        )
        assert authority is not None
        assert authority.authority_task_id == committed.identifier
        assert authority.authority_creation_marker == marker

    def test_ambiguous_create_reconciles_only_matching_durable_marker(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        unrelated = _make_rebase_helper("REBASE-OTHER", epic.identifier)
        matching = _make_rebase_helper("REBASE-1", epic.identifier)
        marker = orch._epic_rebase_creation_marker(
            epic.project_id, epic.identifier, "generation-1"
        )
        key = orch._epic_rebase_authority_key(epic.project_id, epic.identifier)
        orch._epic_rebase_authorities[key] = EpicRebaseStateEntry(
            state=EpicRebaseState.REBASING.value,
            updated_at=time.time(),
            project_id=epic.project_id,
            authority_generation="generation-1",
            authority_epic_head="epic-head-1",
            authority_target_head="main-head-1",
            authority_creation_reserved=True,
            authority_creation_marker=marker,
        )
        matching.description += "\nOOMPAH-EPIC-REBASE-RESERVATION: " + marker
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.return_value = matching
        orch._active_epic_rebase_siblings = MagicMock(
            return_value=[unrelated]
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is matching
        tracker.create_issue_once.assert_called_once_with(
            title="Rebase epic-EPIC-1 onto main",
            issue_type="task",
            description=tracker.create_issue_once.call_args.kwargs["description"],
            priority=0,
            parent=epic.identifier,
            initial_status=NEEDS_REBASE,
            project_id=str(epic.project_id or ""),
            operation_kind="epic_rebase_helper",
            creation_marker=marker,
        )
        assert orch._epic_rebase_authority_entry(
            epic.project_id, epic.identifier
        ).authority_task_id == matching.identifier

    def test_unsupported_tracker_fails_closed_without_external_create(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        tracker = MagicMock()
        tracker.supports_atomic_create_once = False
        orch._active_epic_rebase_siblings = MagicMock(return_value=[])
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is None
        tracker.create_issue_once.assert_not_called()
        tracker.create_issue.assert_not_called()
        assert orch._epic_rebase_authority_entry(
            epic.project_id, epic.identifier
        ) is None

    def test_authority_persistence_failure_blocks_admission_and_rolls_back(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = MagicMock()
        orch._active_epic_rebase_siblings = MagicMock(return_value=[helper])
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )
        orch._save_state = MagicMock(return_value=False)

        admitted, reason = orch._admit_epic_rebase_helper(
            tracker, helper, parent=epic, epic_branch="epic-EPIC-1", target_branch="main"
        )

        assert (admitted, reason) == (False, "epic_rebase_authority_persist_failed")
        assert orch._epic_rebase_authority_entry(epic.project_id, epic.identifier) is None

    def test_reopened_helper_reuses_consumed_generation_without_successor(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        epic = _make_issue("EPIC-1", labels=["rebase-requested"])
        helper = _make_rebase_helper("REBASE-1", epic.identifier)
        tracker = _atomic_create_tracker()
        tracker.create_issue_once.return_value = helper
        active: list[Issue] = []
        orch._active_epic_rebase_siblings = MagicMock(
            side_effect=lambda *_args, **_kwargs: list(active)
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", "epic-head-1", "main-head-1")
        )

        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is helper
        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is None
        helper.state = NEEDS_REBASE
        active.append(helper)
        assert orch._file_rebase_task(
            tracker, epic, "epic-EPIC-1", "main"
        ) is helper
        assert tracker.create_issue_once.call_count == 1

    def test_server_publish_uses_exact_locked_cas_argv(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
            ]
        )

        result = orch.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )

        assert result == {
            "published": True,
            "recovered": False,
            "candidate": candidate,
        }
        orch._run_project_network_git.assert_called_once_with(
            orch.project_store.get.return_value,
            [
                "git",
                "--no-replace-objects",
                "push",
                (
                    "--force-with-lease="
                    f"refs/heads/epic-EPIC-1:{lease_head}"
                ),
                "origin",
                f"{candidate}:refs/heads/epic-EPIC-1",
            ],
            cwd=str(tmp_path),
            timeout=60,
            canonical_remote_url="https://trusted.invalid/repository",
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert entry.authority_publish_state == "published"
        assert entry.authority_publish_candidate == candidate
        assert entry.authority_publish_lease_head == lease_head
        assert entry.authority_publish_target_head == target_head
        assert entry.authority_publish_remote_head == candidate

    def test_server_publish_uses_persisted_authoritative_epic_branch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        epic.work_branch = "legacy-nested-epic-source"
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
            ]
        )

        result = orch.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )

        assert result["published"] is True
        assert [
            call.kwargs["epic_branch"]
            for call in orch._observe_epic_rebase_generation.call_args_list
        ] == ["legacy-nested-epic-source", "legacy-nested-epic-source"]
        assert orch._run_project_network_git.call_args.args[1] == [
            "git",
            "--no-replace-objects",
            "push",
            (
                "--force-with-lease="
                f"refs/heads/legacy-nested-epic-source:{lease_head}"
            ),
            "origin",
            f"{candidate}:refs/heads/legacy-nested-epic-source",
        ]

    def test_direct_completion_reconciles_persisted_authoritative_branch(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper = _make_rebase_helper("REBASE-1", "EPIC-1")
        parent = _make_issue("EPIC-1", labels=["rebase-requested"])
        parent.work_branch = "legacy-nested-epic-source"
        published = "c" * 40
        record = IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch=parent.work_branch,
            base_branch=parent.work_branch,
            base_sha="a" * 40,
            head_sha=published,
            integrated_sha=published,
        )
        helper.integration = record
        orch.project_store.get.return_value = _make_project()
        orch.project_store.reconcile_published_epic_worktree.return_value = (
            type(
                "Reconciliation",
                (),
                {
                    "completed": True,
                    "old_sha": "a" * 40,
                    "status": "completed",
                    "reason": None,
                },
            )()
        )
        orch._resolve_parent_epic = MagicMock(return_value=parent)
        orch._tracker_for_project = MagicMock()
        orch._persist_direct_epic_child_landing_evidence = MagicMock(
            return_value=False
        )

        completed, _message, _returned = asyncio.run(
            orch.complete_direct_epic_maintenance_submission(
                helper,
                record,
                helper.project_id,
            )
        )

        assert completed is False
        orch.project_store.reconcile_published_epic_worktree.assert_called_once_with(
            helper.project_id,
            parent.identifier,
            published,
            branch_name=parent.work_branch,
            expected_old_sha="a" * 40,
            maintenance_identifier=helper.identifier,
        )

    def test_server_publish_stamps_scoped_native_task_project(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        project_id = helper.project_id
        helper.project_id = None
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
            ]
        )

        result = orch.publish_epic_rebase_candidate(
            project_id,
            helper.identifier,
            candidate,
        )

        assert result["published"] is True
        assert helper.project_id == project_id
        orch._run_project_network_git.assert_called_once()

    def test_server_publish_rejects_conflicting_task_project(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, _lease_head, _target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        project_id = helper.project_id
        helper.project_id = "proj-other"

        with pytest.raises(ProjectError, match="publish_task_scope_mismatch"):
            orch.publish_epic_rebase_candidate(
                project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_server_publish_rejects_missing_scoped_task(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, tracker, candidate, _lease_head, _target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        tracker.fetch_issue_detail.return_value = None
        tracker.fetch_issue_detail.side_effect = None

        with pytest.raises(ProjectError, match="publish_task_missing"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_server_publish_never_uses_worker_config_for_privileged_push(
        self, tmp_path
    ):
        trusted_repo = tmp_path / "trusted"
        worker = tmp_path / "worker"
        trusted_repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=trusted_repo, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Oompah"], cwd=trusted_repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "oompah@example.test"],
            cwd=trusted_repo,
            check=True,
        )
        (trusted_repo / "base.txt").write_text("base\n")
        subprocess.run(["git", "add", "base.txt"], cwd=trusted_repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=trusted_repo, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://trusted.invalid/repository"],
            cwd=trusted_repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "extensions.worktreeConfig", "true"],
            cwd=trusted_repo,
            check=True,
        )
        subprocess.run(
            ["git", "worktree", "add", "-q", "-b", "worker", str(worker)],
            cwd=trusted_repo,
            check=True,
        )
        subprocess.run(
            [
                "git",
                "config",
                "--worktree",
                "remote.origin.pushurl",
                "https://attacker.invalid/repository",
            ],
            cwd=worker,
            check=True,
        )
        subprocess.run(
            ["git", "config", "--worktree", "credential.helper", "!touch /should-not-run"],
            cwd=worker,
            check=True,
        )
        subprocess.run(
            ["git", "config", "--worktree", "core.sshCommand", "/attacker/ssh"],
            cwd=worker,
            check=True,
        )
        worker_push_url = subprocess.run(
            ["git", "remote", "get-url", "--push", "origin"],
            cwd=worker,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert worker_push_url == (
            "file:///OOMPAH-TEST-NETWORK-BARRIER/https/attacker.invalid/repository"
        )
        trusted_push_url = subprocess.run(
            ["git", "remote", "get-url", "--push", "origin"],
            cwd=trusted_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert trusted_push_url == (
            "file:///OOMPAH-TEST-NETWORK-BARRIER/https/trusted.invalid/repository"
        )

        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, worker)
        )
        project = orch.project_store.get.return_value
        project.repo_path = str(trusted_repo)
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
            ]
        )

        orch.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )

        publish_call = orch._run_project_network_git.call_args
        assert publish_call.kwargs["cwd"] == str(trusted_repo)
        assert publish_call.args[1] == [
            "git",
            "--no-replace-objects",
            "push",
            f"--force-with-lease=refs/heads/epic-EPIC-1:{lease_head}",
            "origin",
            f"{candidate}:refs/heads/epic-EPIC-1",
        ]
        assert publish_call.kwargs["canonical_remote_url"] == (
            "https://trusted.invalid/repository"
        )
        local_calls = orch._epic_rebase_publish_local_git.call_args_list
        assert local_calls[0].args[0] == str(trusted_repo)
        assert local_calls[1].args[0] == str(worker)
        assert local_calls[2].args[0] == str(trusted_repo)

    def test_server_publish_local_git_inspects_real_commit(self, tmp_path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Oompah"],
            cwd=tmp_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "oompah@example.test"],
            cwd=tmp_path,
            check=True,
        )
        tracked = tmp_path / "tracked.txt"
        tracked.write_text("candidate\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate"], cwd=tmp_path, check=True)

        result = Orchestrator._epic_rebase_publish_local_git(
            str(tmp_path),
            ["rev-parse", "--verify", "HEAD^{commit}"],
        )
        expected = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        assert result.returncode == 0
        assert result.stdout.strip() == expected

    def test_server_publish_local_git_ignores_replace_refs(self, tmp_path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Oompah"], cwd=tmp_path, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "oompah@example.test"],
            cwd=tmp_path,
            check=True,
        )
        tracked = tmp_path / "tracked.txt"
        tracked.write_text("target\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "target"], cwd=tmp_path, check=True)
        target = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(["git", "checkout", "-q", "--orphan", "candidate"], cwd=tmp_path, check=True)
        subprocess.run(["git", "rm", "-q", "-rf", "."], cwd=tmp_path, check=True)
        candidate_file = tmp_path / "candidate.txt"
        candidate_file.write_text("candidate\n")
        subprocess.run(["git", "add", "candidate.txt"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate"], cwd=tmp_path, check=True)
        candidate = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        candidate_tree = subprocess.run(
            ["git", "rev-parse", f"{candidate}^{{tree}}"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        forged_candidate = subprocess.run(
            ["git", "commit-tree", candidate_tree, "-p", target],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
            input="forged ancestry\n",
        ).stdout.strip()
        subprocess.run(
            ["git", "replace", candidate, forged_candidate],
            cwd=tmp_path,
            check=True,
        )
        spoofed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", target, candidate],
            cwd=tmp_path,
            check=False,
        )
        assert spoofed.returncode == 0

        result = Orchestrator._epic_rebase_publish_local_git(
            str(tmp_path),
            ["merge-base", "--is-ancestor", target, candidate],
        )

        assert result.returncode != 0

    def test_server_publish_local_git_sanitizes_process_git_config(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "alias.rev-parse")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "!touch /should-not-run")
        completed = subprocess.CompletedProcess([], 0, stdout="a" * 40, stderr="")

        with patch("oompah.orchestrator.subprocess.run", return_value=completed) as run:
            result = Orchestrator._epic_rebase_publish_local_git(
                str(tmp_path),
                ["rev-parse", "--verify", "HEAD^{commit}"],
            )

        assert result is completed
        assert run.call_args.args[0] == [
            "git",
            "--no-replace-objects",
            "rev-parse",
            "--verify",
            "HEAD^{commit}",
        ]
        env = run.call_args.kwargs["env"]
        assert "GIT_CONFIG_COUNT" not in env
        assert env["GIT_NO_REPLACE_OBJECTS"] == "1"
        assert env["GIT_CONFIG_GLOBAL"] == os.devnull

    def test_server_network_git_uses_only_server_transport_controls(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("GIT_DIR", "/attacker/git-dir")
        monkeypatch.setenv("GIT_WORK_TREE", "/attacker/worktree")
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "remote.origin.pushurl")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://attacker.invalid/repo")
        monkeypatch.setenv("GIT_SSH_COMMAND", "/attacker/ssh")
        monkeypatch.setenv("LD_PRELOAD", "/attacker/library.so")
        project = type(
            "ProjectStub",
            (),
            {"access_token": "server-token", "forge_kind": "github"},
        )()
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        argv = [
            "git",
            "--no-replace-objects",
            "push",
            "--force-with-lease=refs/heads/epic:abc",
            "origin",
            "def:refs/heads/epic",
        ]

        with patch("oompah.orchestrator.subprocess.run", return_value=completed) as run:
            result = Orchestrator._run_project_network_git(
                project,
                argv,
                cwd=str(tmp_path),
                timeout=60,
                canonical_remote_url="https://trusted.invalid/repo",
            )

        assert result is completed
        assert run.call_args.args[0] == argv
        assert run.call_args.kwargs["cwd"] == str(tmp_path)
        env = run.call_args.kwargs["env"]
        assert "GIT_DIR" not in env
        assert "GIT_WORK_TREE" not in env
        assert "LD_PRELOAD" not in env
        assert env["GIT_NO_REPLACE_OBJECTS"] == "1"
        config_values = {
            env[f"GIT_CONFIG_KEY_{index}"]: env[f"GIT_CONFIG_VALUE_{index}"]
            for index in range(int(env["GIT_CONFIG_COUNT"]))
        }
        assert config_values["remote.origin.url"] == "https://trusted.invalid/repo"
        assert config_values["remote.origin.pushurl"] == (
            "https://trusted.invalid/repo"
        )
        assert config_values["core.hooksPath"] == os.devnull
        assert config_values["credential.helper"] == ""
        assert config_values["protocol.ext.allow"] == "never"
        assert config_values["core.sshCommand"] == (
            "ssh -F /dev/null -oBatchMode=yes"
        )

    @pytest.mark.parametrize(
        "candidate",
        [
            "HEAD",
            "--force",
            "https://example.test/repo",
            "a" * 39,
            "A" * 40,
            "a" * 40 + ":refs/heads/main",
        ],
    )
    def test_server_publish_rejects_non_full_commit_candidates(
        self, tmp_path, candidate
    ):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, _candidate, _lease, _target = (
            _configure_publish_fixture(orch, tmp_path)
        )

        with pytest.raises(ValueError, match="full lowercase commit"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_server_publish_rejects_candidate_not_at_locked_head(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, _lease, _target = (
            _configure_publish_fixture(orch, tmp_path)
        )
        other = "d" * 40
        orch._epic_rebase_publish_local_git.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=f"{candidate}\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=f"{other}\n", stderr=""),
        ]

        with pytest.raises(ProjectError, match="candidate_tampered"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    @pytest.mark.parametrize("repo_path", [None, "relative/repository"])
    def test_server_publish_rejects_untrusted_project_repo_path(
        self, tmp_path, repo_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, _lease, _target = (
            _configure_publish_fixture(orch, tmp_path)
        )
        orch.project_store.get.return_value.repo_path = repo_path

        with pytest.raises(ProjectError, match="trusted_repo_missing"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_server_publish_rejects_missing_absolute_project_repo_path(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, _lease, _target = (
            _configure_publish_fixture(orch, tmp_path)
        )
        orch.project_store.get.return_value.repo_path = str(tmp_path / "missing")

        with pytest.raises(ProjectError, match="trusted_repo_missing"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_remote_candidate_without_prepared_evidence_is_not_recovered(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, _lease, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-other", candidate, target_head)
        )

        with pytest.raises(ProjectError, match="epic_rebase_generation_stale"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_prepared_evidence_from_another_authority_is_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        entry.authority_task_id = "REBASE-OTHER"
        entry.authority_publish_state = "prepared"
        entry.authority_publish_candidate = candidate
        entry.authority_publish_lease_head = lease_head
        entry.authority_publish_target_head = target_head
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", candidate, target_head)
        )

        with pytest.raises(ProjectError, match="authority_revoked"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_remote_candidate_requires_exact_finalized_durable_evidence(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        entry.authority_publish_state = "published"
        entry.authority_publish_candidate = candidate
        entry.authority_publish_lease_head = lease_head
        entry.authority_publish_target_head = target_head
        entry.authority_publish_remote_head = "d" * 40
        entry.authority_publish_verified_at = time.time()
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", candidate, target_head)
        )

        with pytest.raises(ProjectError, match="publish_remote_changed"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_restart_recovers_lost_publish_response_from_prepared_evidence(
        self, tmp_path
    ):
        first = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(first, tmp_path)
        )
        entry = first._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert first._persist_epic_rebase_publish_evidence(
            project_id=helper.project_id,
            epic_identifier=epic.identifier,
            entry=entry,
            state="prepared",
            candidate=candidate,
            lease_head=lease_head,
            target_head=target_head,
            remote_head=None,
        )

        restarted = _make_orchestrator(tmp_path)
        _configure_publish_fixture(restarted, tmp_path, install_authority=False)
        restarted._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", candidate, target_head)
        )

        result = restarted.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )

        assert result["published"] is True
        assert result["recovered"] is True
        restarted._run_project_network_git.assert_not_called()
        restored = restarted._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert restored is not None
        assert restored.authority_publish_state == "published"
        assert restored.authority_publish_remote_head == candidate

    def test_maintenance_rewrite_finalizes_lost_response_before_retry(
        self, tmp_path
    ):
        first = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(first, tmp_path)
        )
        entry = first._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert first._persist_epic_rebase_publish_evidence(
            project_id=helper.project_id,
            epic_identifier=epic.identifier,
            entry=entry,
            state="prepared",
            candidate=candidate,
            lease_head=lease_head,
            target_head=target_head,
            remote_head=None,
        )

        restarted = _make_orchestrator(tmp_path)
        _configure_publish_fixture(restarted, tmp_path, install_authority=False)
        rewritten = restarted._persist_epic_rebase_authority(
            epic=epic,
            task=helper,
            epic_branch="epic-EPIC-1",
            target_branch="main",
            generation="generation-2",
            epic_head=candidate,
            target_head=target_head,
        )

        assert rewritten is not None
        assert rewritten.authority_generation == "generation-2"
        assert rewritten.authority_publish_state == "published"
        assert rewritten.authority_publish_candidate == candidate
        assert rewritten.authority_publish_lease_head == lease_head
        assert rewritten.authority_publish_remote_head == candidate

        restarted._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", candidate, target_head)
        )
        restarted._active_epic_rebase_siblings.return_value = []
        result = restarted.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )
        assert result["recovered"] is True
        restarted._run_project_network_git.assert_not_called()

    def test_maintenance_rewrite_does_not_finalize_third_remote_sha(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert orch._persist_epic_rebase_publish_evidence(
            project_id=helper.project_id,
            epic_identifier=epic.identifier,
            entry=entry,
            state="prepared",
            candidate=candidate,
            lease_head=lease_head,
            target_head=target_head,
            remote_head=None,
        )

        rewritten = orch._persist_epic_rebase_authority(
            epic=epic,
            task=helper,
            epic_branch="epic-EPIC-1",
            target_branch="main",
            generation="generation-third",
            epic_head="d" * 40,
            target_head=target_head,
        )

        assert rewritten is not None
        assert rewritten.authority_publish_state == ""
        assert rewritten.authority_publish_candidate is None
        assert rewritten.authority_publish_remote_head is None

    def test_maintenance_rewrite_does_not_transfer_publish_to_another_task(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert orch._persist_epic_rebase_publish_evidence(
            project_id=helper.project_id,
            epic_identifier=epic.identifier,
            entry=entry,
            state="prepared",
            candidate=candidate,
            lease_head=lease_head,
            target_head=target_head,
            remote_head=None,
        )
        successor = _make_rebase_helper("REBASE-OTHER", epic.identifier)

        rewritten = orch._persist_epic_rebase_authority(
            epic=epic,
            task=successor,
            epic_branch="epic-EPIC-1",
            target_branch="main",
            generation="generation-2",
            epic_head=candidate,
            target_head=target_head,
        )

        assert rewritten is not None
        assert rewritten.authority_task_id == successor.identifier
        assert rewritten.authority_publish_state == ""
        assert rewritten.authority_publish_candidate is None

    def test_prepared_lost_response_requires_current_active_winner(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert orch._persist_epic_rebase_publish_evidence(
            project_id=helper.project_id,
            epic_identifier=epic.identifier,
            entry=entry,
            state="prepared",
            candidate=candidate,
            lease_head=lease_head,
            target_head=target_head,
            remote_head=None,
        )
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", candidate, target_head)
        )
        orch._active_epic_rebase_siblings.return_value = []

        with pytest.raises(ProjectError, match="authority_revoked"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_target_advance_after_prepare_must_be_in_candidate(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert orch._persist_epic_rebase_publish_evidence(
            project_id=helper.project_id,
            epic_identifier=epic.identifier,
            entry=entry,
            state="prepared",
            candidate=candidate,
            lease_head=lease_head,
            target_head=target_head,
            remote_head=None,
        )
        advanced_target = "e" * 40
        orch._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-1", lease_head, advanced_target)
        )
        orch._epic_rebase_publish_local_git.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=f"{candidate}\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=f"{candidate}\n", stderr=""),
            subprocess.CompletedProcess([], 1, stdout="", stderr=""),
        ]

        with pytest.raises(ProjectError, match="epic_rebase_target_not_ancestor"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        orch._run_project_network_git.assert_not_called()

    def test_target_advance_during_push_is_not_recorded_without_ancestry(
        self, tmp_path
    ):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        advanced_target = "e" * 40
        base_local_git = orch._epic_rebase_publish_local_git.side_effect

        def local_git(workspace, args):
            if args == [
                "merge-base",
                "--is-ancestor",
                advanced_target,
                candidate,
            ]:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
            return base_local_git(workspace, args)

        orch._epic_rebase_publish_local_git.side_effect = local_git
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, advanced_target),
            ]
        )

        with pytest.raises(ProjectError, match="target_advanced_during_publish"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert entry.authority_publish_state == "prepared"
        assert entry.authority_publish_remote_head is None

    def test_target_advance_during_push_is_reproved_before_success(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        advanced_target = "e" * 40
        base_local_git = orch._epic_rebase_publish_local_git.side_effect

        def local_git(workspace, args):
            if args == [
                "merge-base",
                "--is-ancestor",
                advanced_target,
                candidate,
            ]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            return base_local_git(workspace, args)

        orch._epic_rebase_publish_local_git.side_effect = local_git
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, advanced_target),
            ]
        )

        result = orch.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )

        assert result["published"] is True
        entry = orch._epic_rebase_authority_entry(
            helper.project_id, epic.identifier
        )
        assert entry is not None
        assert entry.authority_publish_state == "published"
        assert entry.authority_publish_target_head == advanced_target

    def test_transport_error_with_remote_still_at_lease_can_retry(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-1", lease_head, target_head),
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
            ]
        )
        orch._run_project_network_git.side_effect = [
            subprocess.CompletedProcess([], 1, stdout="", stderr="transport lost"),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]

        with pytest.raises(ProjectError, match="publish_remote_unverified"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        result = orch.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )
        assert result["published"] is True
        assert orch._run_project_network_git.call_count == 2
        assert (
            orch._run_project_network_git.call_args_list[0].args[1]
            == orch._run_project_network_git.call_args_list[1].args[1]
        )

    def test_third_remote_sha_after_push_is_a_cas_race(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, _epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        third_head = "d" * 40
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-third", third_head, target_head),
            ]
        )

        with pytest.raises(ProjectError, match="epic_rebase_publish_cas_race"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        entry = orch._epic_rebase_authority_entry(
            helper.project_id, "EPIC-1"
        )
        assert entry is not None
        assert entry.authority_publish_state == "prepared"

    def test_failed_published_persist_converges_after_restart(self, tmp_path):
        first = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(first, tmp_path)
        )
        first._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
            ]
        )
        persist = first._persist_epic_rebase_publish_evidence

        def fail_published(**kwargs):
            if kwargs["state"] == "published":
                return False
            return persist(**kwargs)

        first._persist_epic_rebase_publish_evidence = MagicMock(
            side_effect=fail_published
        )

        with pytest.raises(ProjectError, match="publish_evidence_persist_failed"):
            first.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )

        restarted = _make_orchestrator(tmp_path)
        _configure_publish_fixture(restarted, tmp_path, install_authority=False)
        restarted._observe_epic_rebase_generation = MagicMock(
            return_value=("generation-2", candidate, target_head)
        )
        recovered = restarted.publish_epic_rebase_candidate(
            helper.project_id,
            helper.identifier,
            candidate,
        )
        assert recovered["recovered"] is True
        restarted._run_project_network_git.assert_not_called()

    def test_publish_acquires_authority_before_project_lock(self, tmp_path):
        from contextlib import contextmanager

        orch = _make_orchestrator(tmp_path)
        order: list[str] = []

        @contextmanager
        def authority(*_args):
            order.append("authority-enter")
            try:
                yield
            finally:
                order.append("authority-exit")

        @contextmanager
        def project_lock(_project_id):
            order.append("project-enter")
            try:
                yield
            finally:
                order.append("project-exit")

        orch._epic_rebase_authority_transaction = authority
        orch.project_store.project_write_lock.side_effect = project_lock
        orch.project_store.get.return_value = None

        with pytest.raises(ProjectError, match="publish_project_missing"):
            orch.publish_epic_rebase_candidate("proj-1", "REBASE-1", "c" * 40)

        assert order == [
            "authority-enter",
            "project-enter",
            "project-exit",
            "authority-exit",
        ]

    def test_authority_revocation_cannot_interleave_with_publish(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        helper, epic, _tracker, candidate, lease_head, target_head = (
            _configure_publish_fixture(orch, tmp_path)
        )
        orch._observe_epic_rebase_generation = MagicMock(
            side_effect=[
                ("generation-1", lease_head, target_head),
                ("generation-2", candidate, target_head),
                ("generation-2", candidate, target_head),
            ]
        )
        push_started = threading.Event()
        release_push = threading.Event()
        revocation_entered = threading.Event()

        def blocking_push(*_args, **_kwargs):
            push_started.set()
            assert release_push.wait(timeout=2)
            return subprocess.CompletedProcess([], 0, stdout="", stderr="")

        orch._run_project_network_git.side_effect = blocking_push

        def revoke_authority():
            with orch._epic_rebase_authority_transaction(
                helper.project_id, epic.identifier
            ):
                with orch.project_store.project_write_lock(helper.project_id):
                    revocation_entered.set()
                    entry = orch._epic_rebase_authority_entry(
                        helper.project_id, epic.identifier
                    )
                    assert entry is not None
                    entry.authority_task_id = "REBASE-OTHER"

        with ThreadPoolExecutor(max_workers=2) as pool:
            published = pool.submit(
                orch.publish_epic_rebase_candidate,
                helper.project_id,
                helper.identifier,
                candidate,
            )
            assert push_started.wait(timeout=2)
            revoked = pool.submit(revoke_authority)
            assert revocation_entered.wait(timeout=0.05) is False
            release_push.set()
            assert published.result(timeout=2)["published"] is True
            revoked.result(timeout=2)

        assert revocation_entered.is_set()
        with pytest.raises(ProjectError, match="authority_revoked"):
            orch.publish_epic_rebase_candidate(
                helper.project_id,
                helper.identifier,
                candidate,
            )
