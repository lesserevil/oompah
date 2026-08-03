from __future__ import annotations

from oompah.container_dependency_graph import (
    build_container_dependency_graph,
    container_dependency_cycle_for_new_edge,
    find_container_dependency_cycles,
)
from oompah.integration import IntegrationRecord
from oompah.models import BlockerRef, Issue


def _issue(
    identifier: str,
    *,
    state: str = "In Progress",
    issue_type: str = "task",
    parent_id: str | None = None,
    blocked_by: list[str] | None = None,
    integrated_sha: str | None = None,
) -> Issue:
    issue = Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        blocked_by=[BlockerRef(identifier=value) for value in blocked_by or []],
        project_id="project-1",
    )
    if integrated_sha:
        issue.integration = IntegrationRecord(
            state="integrated",
            integrated_sha=integrated_sha,
        )
    return issue


def test_exocomp_shape_detects_container_cycle_and_exact_sha():
    epic_a = _issue("EXOCOMP-129", issue_type="epic")
    epic_b = _issue("EXOCOMP-134", issue_type="epic")
    task_141 = _issue(
        "EXOCOMP-141",
        state="Done",
        parent_id=epic_a.identifier,
        integrated_sha="1" * 40,
    )
    task_171 = _issue(
        "EXOCOMP-171",
        parent_id=epic_b.identifier,
        blocked_by=[task_141.identifier],
    )
    task_142 = _issue(
        "EXOCOMP-142",
        state="Ready to Integrate",
        parent_id=epic_a.identifier,
        blocked_by=[task_171.identifier],
    )
    issues = [epic_a, epic_b, task_141, task_171, task_142]

    assert build_container_dependency_graph(issues) == {
        "EXOCOMP-129": ("EXOCOMP-134",),
        "EXOCOMP-134": ("EXOCOMP-129",),
    }
    cycles = find_container_dependency_cycles(
        issues,
        ready_task_ids=[task_142.identifier],
    )

    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle.path == ("EXOCOMP-129", "EXOCOMP-134", "EXOCOMP-129")
    assert cycle.affected_ready_tasks == ("EXOCOMP-142",)
    assert cycle.prerequisite_shas == (("EXOCOMP-141", "1" * 40),)
    assert cycle.selected_repair == "needs_human_authorized_delivery_order"
    assert cycle.to_dict()["repair_plan"] == {
        "kind": "needs_authorized_delivery_order",
        "authoritative_container": None,
        "prerequisite_shas": {"EXOCOMP-141": "1" * 40},
        "dependent_containers": ["EXOCOMP-129", "EXOCOMP-134"],
        "policy": "parent_only",
    }


def test_longer_multi_epic_cycle_is_reported_as_one_deterministic_component():
    epics = [_issue(f"E-{letter}", issue_type="epic") for letter in "ABC"]
    done_a = _issue("DONE-A", state="Done", parent_id="E-A")
    done_b = _issue("DONE-B", state="Done", parent_id="E-B")
    done_c = _issue("DONE-C", state="Done", parent_id="E-C")
    task_a = _issue("TASK-A", parent_id="E-A", blocked_by=["TASK-B"])
    task_b = _issue("TASK-B", parent_id="E-B", blocked_by=["DONE-C"])
    task_c = _issue("TASK-C", parent_id="E-C", blocked_by=["DONE-A"])
    issues = [*epics, done_a, done_b, done_c, task_a, task_b, task_c]

    cycles = find_container_dependency_cycles(issues)

    assert [cycle.path for cycle in cycles] == [
        ("E-A", "E-B", "E-C", "E-A"),
    ]


def test_landed_parent_breaks_cross_epic_container_edge():
    landed = _issue("E-LANDED", issue_type="epic", state="Merged")
    consumer = _issue("E-CONSUMER", issue_type="epic")
    prerequisite = _issue(
        "TASK-LANDED",
        state="Done",
        parent_id=landed.identifier,
        integrated_sha="2" * 40,
    )
    dependent = _issue(
        "TASK-CONSUMER",
        parent_id=consumer.identifier,
        blocked_by=[prerequisite.identifier],
    )

    assert find_container_dependency_cycles(
        [landed, consumer, prerequisite, dependent]
    ) == ()


def test_new_dependency_is_rejected_when_it_closes_container_cycle():
    epic_a = _issue("E-A", issue_type="epic")
    epic_b = _issue("E-B", issue_type="epic")
    confined = _issue("DONE-A", state="Done", parent_id="E-A")
    existing = _issue(
        "TASK-B",
        parent_id="E-B",
        blocked_by=[confined.identifier],
    )
    proposed = _issue("TASK-A", parent_id="E-A")

    cycle = container_dependency_cycle_for_new_edge(
        [epic_a, epic_b, confined, existing, proposed],
        proposed.identifier,
        existing.identifier,
    )

    assert cycle is not None
    assert cycle.path == ("E-A", "E-B", "E-A")
