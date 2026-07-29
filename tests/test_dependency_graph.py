from oompah.dependency_graph import (
    dependency_cycle_for_new_edge,
    effective_dependencies,
    issue_index,
)
from oompah.models import BlockerRef, Issue


def _issue(identifier: str, **kwargs) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        state="Open",
        **kwargs,
    )


def test_cycle_detection_spans_finish_and_hard_start_edges():
    first = _issue(
        "A",
        blocked_by=[BlockerRef(id="B", identifier="B")],
    )
    second = _issue(
        "B",
        start_blocked_by=[BlockerRef(id="C", identifier="C")],
    )
    third = _issue("C")
    assert dependency_cycle_for_new_edge([first, second, third], "C", "A") == (
        "C",
        "A",
        "B",
        "C",
    )


def test_cycle_detection_reports_self_edge():
    assert dependency_cycle_for_new_edge([_issue("A")], "A", "A") == (
        "A",
        "A",
    )


def test_effective_dependencies_inherit_nested_epic_edges():
    root = _issue(
        "E-ROOT",
        blocked_by=[BlockerRef(id="UPSTREAM", identifier="UPSTREAM")],
    )
    child_epic = _issue(
        "E-CHILD",
        parent_id="E-ROOT",
        start_blocked_by=[BlockerRef(id="BOOT", identifier="BOOT")],
    )
    task = _issue(
        "T-1",
        parent_id="E-CHILD",
        blocked_by=[BlockerRef(id="LOCAL", identifier="LOCAL")],
    )
    index = issue_index([root, child_epic, task])
    assert effective_dependencies(task, index) == ("LOCAL", "UPSTREAM")
    assert effective_dependencies(task, index, hard_start=True) == ("BOOT",)
