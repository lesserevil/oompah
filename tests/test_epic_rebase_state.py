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
import time
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.epic_staleness import StalenessResult
from oompah.models import EpicRebaseState, EpicRebaseStateEntry, Issue
from oompah.orchestrator import Orchestrator
from oompah.statuses import DONE, IN_REVIEW, NEEDS_REBASE


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


# ---------------------------------------------------------------------------
# _set_epic_rebase_state
# ---------------------------------------------------------------------------


class TestSetEpicRebaseState:
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

        candidates = [
            _make_issue("epic-open", state="open"),
            _make_issue("epic-closed", state="closed"),
        ]
        orch._prune_stale_epic_rebase_states(candidates)

        assert "epic-open" in orch._epic_rebase_states
        assert "epic-closed" not in orch._epic_rebase_states

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

        orch._set_epic_rebase_state("epic-1", EpicRebaseState.STALE)
        orch._clear_epic_rebase_state("epic-1")

        disk = json.loads((tmp_path / "state.json").read_text())
        assert "epic-1" not in disk.get("epic_rebase_states", {})


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_includes_epic_rebase_states(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing", updated_at=1234.0, project_id="proj-1"
        )
        snapshot = orch.get_snapshot()
        assert "epic_rebase_states" in snapshot
        assert snapshot["epic_rebase_states"]["epic-1"]["state"] == "rebasing"
        assert snapshot["epic_rebase_states"]["epic-1"]["updated_at"] == 1234.0


# ---------------------------------------------------------------------------
# Epic stale alert explanation
# ---------------------------------------------------------------------------


class TestEpicStaleAlert:
    def test_includes_detail_action_and_message(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("TASK-465")
        result = StalenessResult(
            stale=True,
            commits_behind=6,
            shared_files=("oompah/orchestrator.py",),
            threshold=5,
        )

        orch._arm_epic_stale_alert(issue, _make_project(), result)

        alerts = [
            a for a in orch._alerts
            if a.get("source") == "epic_stale:TASK-465"
        ]
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["title"] == "Epic TASK-465 on oompah is 6 commits behind main"
        assert "threshold: 5" in alert["detail"]
        assert "Overlapping files: oompah/orchestrator.py" in alert["detail"]
        assert "Oompah will file a high-priority rebase task" in alert["action"]
        assert alert["message"] == f"{alert['title']}. {alert['action']}"
        assert alert["epic_identifier"] == "TASK-465"
        assert alert["project_id"] == "proj-1"
        assert alert["project_name"] == "oompah"
        assert alert["target_branch"] == "main"
        assert alert["commits_behind"] == 6

    def test_uses_resolved_target_branch(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("TASK-465")
        result = StalenessResult(
            stale=True,
            commits_behind=6,
            shared_files=(),
            threshold=5,
        )

        orch._arm_epic_stale_alert(
            issue,
            _make_project(),
            result,
            target_branch="epic-TASK-4",
        )

        alert = next(
            a for a in orch._alerts
            if a.get("source") == "epic_stale:TASK-465"
        )
        assert (
            alert["title"]
            == "Epic TASK-465 on oompah is 6 commits behind epic-TASK-4"
        )
        assert alert["target_branch"] == "epic-TASK-4"

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
            if a.get("source") == "epic_stale:TASK-465"
        )
        assert "last rebase run failed" in alert["action"]
        assert "finish or retry the rebase" in alert["action"]
        assert alert["message"] == f"{alert['title']}. {alert['action']}"

# ---------------------------------------------------------------------------
# Proactive rebase dispatch
# ---------------------------------------------------------------------------


class TestDispatchProactiveRebaseAgents:
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

        issue = _make_issue("TASK-18", state="open", project_id="proj-1")
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
        tracker.update_issue.assert_any_call(
            "TASK-18",
            status=NEEDS_REBASE,
            priority="0",
            **{"add-label": "merge-conflict"},
        )

    def test_shared_nested_epic_helper_targets_parent_epic_branch(
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

        assert filed == 1
        tracker.create_issue.assert_called_once()
        assert tracker.create_issue.call_args.kwargs["title"] == (
            "Rebase epic-TASK-18 onto epic-TASK-4"
        )


# ---------------------------------------------------------------------------
# Epic staleness target resolution
# ---------------------------------------------------------------------------


class TestCheckEpicStaleness:
    def test_shared_nested_epic_checks_parent_epic_branch(self, tmp_path):
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
        check.assert_called_once_with(
            "/tmp/repo",
            "epic-TASK-18",
            "epic-TASK-4",
            threshold_commits=5,
        )
