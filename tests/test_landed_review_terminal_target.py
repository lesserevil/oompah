"""Topology target selection for landed protected reviews."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from oompah.models import Issue
from oompah.orchestrator import EpicTargetResolutionError, Orchestrator
from oompah.terminal_audit import TargetState


def issue(**overrides) -> Issue:
    values = {
        "id": "TASK-1",
        "identifier": "TASK-1",
        "title": "Landed review",
        "state": "In Review",
        "project_id": "project-1",
    }
    values.update(overrides)
    return Issue(**values)


def orchestrator() -> Orchestrator:
    """Build only the method surface exercised by this pure resolver."""

    return object.__new__(Orchestrator)


def test_standalone_task_targets_merged():
    assert (
        orchestrator().resolve_landed_review_terminal_target(issue(), "project-1")
        is TargetState.MERGED
    )


def test_ordinary_shared_child_targets_done():
    orch = orchestrator()
    child = issue(parent_id="EPIC-1")
    parent = issue(
        id="EPIC-1",
        identifier="EPIC-1",
        issue_type="epic",
    )
    orch._resolve_parent_epic = MagicMock(return_value=parent)

    target = orch.resolve_landed_review_terminal_target(child, "project-1")

    assert target is TargetState.DONE
    orch._resolve_parent_epic.assert_called_once_with(child, fail_closed=True)


def test_nested_epic_targets_merged_after_parent_resolution():
    orch = orchestrator()
    nested = issue(
        identifier="EPIC-2",
        id="EPIC-2",
        issue_type="epic",
        parent_id="EPIC-1",
    )
    parent = issue(
        id="EPIC-1",
        identifier="EPIC-1",
        issue_type="epic",
    )
    orch._resolve_parent_epic = MagicMock(return_value=parent)

    target = orch.resolve_landed_review_terminal_target(nested, "project-1")

    assert target is TargetState.MERGED
    orch._resolve_parent_epic.assert_called_once_with(nested, fail_closed=True)


def test_named_but_unreadable_parent_fails_closed():
    orch = orchestrator()
    child = issue(parent_id="EPIC-1")
    orch._resolve_parent_epic = MagicMock(
        side_effect=EpicTargetResolutionError(
            child.identifier,
            child.parent_id,
            "is absent from the canonical project snapshot",
        )
    )

    with pytest.raises(EpicTargetResolutionError):
        orch.resolve_landed_review_terminal_target(child, "project-1")


def test_non_rollup_parent_fails_closed():
    orch = orchestrator()
    child = issue(parent_id="TASK-PARENT")
    orch._resolve_parent_epic = MagicMock(return_value=None)

    with pytest.raises(
        EpicTargetResolutionError,
        match="does not resolve to an epic rollup",
    ):
        orch.resolve_landed_review_terminal_target(child, "project-1")
