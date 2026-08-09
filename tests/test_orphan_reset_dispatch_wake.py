"""Regression tests for waking dispatch after orphan resets."""

from unittest.mock import ANY, MagicMock, call, patch

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import DispatchEventType, Orchestrator
from oompah.statuses import DONE


def _make_orchestrator(tmp_path):
    project = MagicMock()
    project.id = "proj-1"
    project.repo_url = "https://github.com/org/repo"
    project.access_token = None

    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.return_value = project

    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    tracker = MagicMock()
    orchestrator._project_trackers[project.id] = tracker
    orchestrator._fetch_all_in_progress_issues = MagicMock(return_value=[])
    return orchestrator, tracker, project


def _make_issue(identifier: str, project_id: str) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue",
        state="In Progress",
        issue_type="task",
        project_id=project_id,
    )


def test_posts_one_refresh_requested_after_orphan_reset(tmp_path):
    orchestrator, tracker, project = _make_orchestrator(tmp_path)
    orphans = [
        _make_issue("feat-orphan-1", project.id),
        _make_issue("feat-orphan-2", project.id),
    ]

    with (
        patch.object(orchestrator, "_post_event") as post_event,
        patch.object(orchestrator, "_transition_issue_status") as transition,
    ):
        orchestrator._reset_orphaned_in_progress(orphans)

    assert transition.call_args_list == [
        call(
            orphans[0],
            "Open",
            project_id=project.id,
            tracker=tracker,
            authority=ANY,
            reason_code="watchdog.orphaned_owner_released",
        ),
        call(
            orphans[1],
            "Open",
            project_id=project.id,
            tracker=tracker,
            authority=ANY,
            reason_code="watchdog.orphaned_owner_released",
        ),
    ]
    post_event.assert_called_once()
    assert (
        post_event.call_args.args[0].event_type is DispatchEventType.REFRESH_REQUESTED
    )


def test_does_not_post_refresh_when_no_orphans_are_found(tmp_path):
    orchestrator, tracker, _project = _make_orchestrator(tmp_path)

    with patch.object(orchestrator, "_post_event") as post_event:
        orchestrator._reset_orphaned_in_progress([])

    tracker.update_issue.assert_not_called()
    post_event.assert_not_called()


def test_does_not_post_refresh_when_orphan_reset_fails(tmp_path):
    orchestrator, tracker, project = _make_orchestrator(tmp_path)
    orphan = _make_issue("feat-orphan", project.id)
    with (
        patch.object(orchestrator, "_post_event") as post_event,
        patch.object(
            orchestrator,
            "_transition_issue_status",
            side_effect=RuntimeError("tracker unavailable"),
        ) as transition,
    ):
        orchestrator._reset_orphaned_in_progress([orphan])

    transition.assert_called_once()
    post_event.assert_not_called()


def test_does_not_post_refresh_when_completed_orphan_is_preserved(tmp_path):
    orchestrator, tracker, project = _make_orchestrator(tmp_path)
    completed = _make_issue("feat-completed", project.id)
    orchestrator.state.completed.add(completed.id)

    outcome = MagicMock(applied_status="In Validation", observed_status="In Validation")
    with (
        patch.object(orchestrator, "_post_event") as post_event,
        patch.object(
            orchestrator,
            "_transition_issue_status",
            return_value=outcome,
        ) as transition,
    ):
        orchestrator._reset_orphaned_in_progress([completed])

    transition.assert_called_once_with(
        completed,
        DONE,
        project_id=project.id,
        tracker=tracker,
        authority=ANY,
        reason_code="watchdog.completed_orphan_reasserted",
    )
    post_event.assert_not_called()
