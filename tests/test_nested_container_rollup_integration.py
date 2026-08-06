"""Tests for nested container rollup edge filtering in integration dependencies."""

from oompah.dependency_graph import integration_dependencies, issue_index
from oompah.integration_queue import IntegrationQueueItem
from oompah.models import BlockerRef, Issue
from oompah.orchestrator import Orchestrator
from oompah.server import _integration_queue_summary


def make_issue(identifier, parent_id=None, blocked_by=None):
    """Helper to create an Issue for testing."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Task {identifier}",
        parent_id=parent_id,
        blocked_by=[
            BlockerRef(id=dep, identifier=dep)
            for dep in (blocked_by or [])
        ],
    )


def test_child_excludes_implicit_parent_rollup_edge():
    """Child task should not depend on parent when parent has rollup on child."""
    parent = make_issue("PARENT-804", blocked_by=["CHILD-834", "CHILD-835"])
    child1 = make_issue("CHILD-834", parent_id="PARENT-804")
    child2 = make_issue("CHILD-835", parent_id="PARENT-804")
    external = make_issue("EXTERNAL-500")

    index = issue_index([parent, child1, child2, external])

    # Child1 should not include parent in integration dependencies
    # even though parent has finish dependencies on it (for rollup)
    deps = integration_dependencies(child1, index)
    assert "PARENT-804" not in deps, f"Child should not depend on parent, got: {deps}"
    assert "CHILD-835" not in deps, f"Child should not depend on implicit sibling, got: {deps}"


def test_child_preserves_explicit_external_dependencies():
    """Child should preserve external finish dependencies."""
    parent = make_issue("PARENT-804", blocked_by=["CHILD-834"])
    child = make_issue("CHILD-834", parent_id="PARENT-804", blocked_by=["EXTERNAL-500"])
    external = make_issue("EXTERNAL-500")

    index = issue_index([parent, child, external])

    deps = integration_dependencies(child, index)
    assert "EXTERNAL-500" in deps, f"Child should keep explicit external dependency, got: {deps}"
    assert "PARENT-804" not in deps, f"Child should not depend on parent, got: {deps}"


def test_child_preserves_explicit_sibling_dependencies():
    """Child should preserve explicitly declared sibling dependencies."""
    parent = make_issue("PARENT-804", blocked_by=["CHILD-834", "CHILD-835"])
    # CHILD-834 explicitly depends on CHILD-835
    child1 = make_issue("CHILD-834", parent_id="PARENT-804", blocked_by=["CHILD-835"])
    child2 = make_issue("CHILD-835", parent_id="PARENT-804")

    index = issue_index([parent, child1, child2])

    deps = integration_dependencies(child1, index)
    assert "CHILD-835" in deps, f"Child should preserve explicit sibling dependency, got: {deps}"
    assert "PARENT-804" not in deps, f"Child should not depend on parent, got: {deps}"


def test_child_preserves_ancestor_external_dependencies():
    """Child should preserve inherited external dependencies from ancestors."""
    grandparent = make_issue("GRAND-800", blocked_by=["EXTERNAL-500"])
    parent = make_issue("PARENT-804", parent_id="GRAND-800", blocked_by=["CHILD-834"])
    child = make_issue("CHILD-834", parent_id="PARENT-804")
    external = make_issue("EXTERNAL-500")

    index = issue_index([grandparent, parent, child, external])

    deps = integration_dependencies(child, index)
    # Child should inherit external dependency from grandparent through parent
    assert "EXTERNAL-500" in deps, f"Child should preserve ancestor external dependency, got: {deps}"
    # But not depend on immediate parent
    assert "PARENT-804" not in deps, f"Child should not depend on parent, got: {deps}"


def test_standalone_child_without_parent():
    """Standalone child (no parent) should work normally."""
    child = make_issue("TASK-500", blocked_by=["TASK-400"])
    dependency = make_issue("TASK-400")

    index = issue_index([child, dependency])

    deps = integration_dependencies(child, index)
    assert "TASK-400" in deps, f"Standalone task should keep its dependencies, got: {deps}"


def test_multiple_siblings_complex_scenario():
    """Complex scenario with multiple siblings and dependencies."""
    parent = make_issue("PARENT-804", blocked_by=["CHILD-834", "CHILD-835", "CHILD-836"])
    # CHILD-834 -> CHILD-835 (explicit)
    # CHILD-835 -> CHILD-836 (explicit)
    # CHILD-836 -> EXTERNAL-500 (explicit)
    child1 = make_issue("CHILD-834", parent_id="PARENT-804", blocked_by=["CHILD-835"])
    child2 = make_issue("CHILD-835", parent_id="PARENT-804", blocked_by=["CHILD-836"])
    child3 = make_issue("CHILD-836", parent_id="PARENT-804", blocked_by=["EXTERNAL-500"])
    external = make_issue("EXTERNAL-500")

    index = issue_index([parent, child1, child2, child3, external])

    deps1 = integration_dependencies(child1, index)
    # CHILD-834 depends on CHILD-835 explicitly
    assert "CHILD-835" in deps1
    # But not on parent or other siblings without explicit dependency
    assert "PARENT-804" not in deps1
    assert "CHILD-836" not in deps1

    deps2 = integration_dependencies(child2, index)
    # CHILD-835 depends on CHILD-836 explicitly
    assert "CHILD-836" in deps2
    # But not on parent
    assert "PARENT-804" not in deps2

    deps3 = integration_dependencies(child3, index)
    # CHILD-836 depends on external
    assert "EXTERNAL-500" in deps3
    # But not on parent
    assert "PARENT-804" not in deps3


def test_integration_dependencies_empty_for_no_deps():
    """Task with no dependencies should return empty tuple."""
    task = make_issue("TASK-100")
    index = issue_index([task])

    deps = integration_dependencies(task, index)
    assert deps == (), f"Task with no dependencies should return empty tuple, got: {deps}"


def test_integration_dependencies_handles_missing_issue():
    """References to missing issues should be handled gracefully."""
    task = make_issue("TASK-100", blocked_by=["MISSING-999"])
    index = issue_index([task])

    # Should not crash, even though MISSING-999 is not in the index
    deps = integration_dependencies(task, index)
    # The missing dependency will be included since it's explicit
    assert "MISSING-999" in deps


def test_nested_three_levels_deep():
    """Test filtering works for deeply nested hierarchies."""
    # GRAND-800 (blocked by PARENT-804)
    # PARENT-804 (blocked by CHILD-834, parent=GRAND-800)
    # CHILD-834 (parent=PARENT-804)
    grandparent = make_issue("GRAND-800", blocked_by=["PARENT-804"])
    parent = make_issue("PARENT-804", parent_id="GRAND-800", blocked_by=["CHILD-834"])
    child = make_issue("CHILD-834", parent_id="PARENT-804")

    index = issue_index([grandparent, parent, child])

    # CHILD-834 should not depend on PARENT-804
    deps = integration_dependencies(child, index)
    assert "PARENT-804" not in deps, f"Child should not depend on parent, got: {deps}"


def test_all_ancestor_rollups_are_removed_but_external_order_is_retained():
    root = make_issue(
        "ROOT",
        blocked_by=["PARENT-A", "PARENT-B", "EXTERNAL"],
    )
    parent_a = make_issue(
        "PARENT-A",
        parent_id="ROOT",
        blocked_by=["LEAF", "PEER"],
    )
    parent_b = make_issue("PARENT-B", parent_id="ROOT")
    leaf = make_issue("LEAF", parent_id="PARENT-A")
    peer = make_issue("PEER", parent_id="PARENT-A")
    external = make_issue("EXTERNAL")

    dependencies = integration_dependencies(
        leaf,
        issue_index([root, parent_a, parent_b, leaf, peer, external]),
    )

    assert dependencies == ("EXTERNAL",)


def test_ids_and_identifiers_are_one_canonical_dependency_namespace():
    parent = Issue(
        id="native-parent",
        identifier="PARENT",
        title="Parent",
        blocked_by=[
            BlockerRef(id="native-child"),
            BlockerRef(id="native-sibling"),
        ],
    )
    child = Issue(
        id="native-child",
        identifier="CHILD",
        title="Child",
        parent_id="native-parent",
        blocked_by=[
            BlockerRef(id="native-sibling"),
            BlockerRef(id="native-external"),
        ],
    )
    sibling = Issue(
        id="native-sibling",
        identifier="SIBLING",
        title="Sibling",
        parent_id="PARENT",
    )
    external = Issue(
        id="native-external",
        identifier="EXTERNAL",
        title="External",
    )

    assert integration_dependencies(
        child,
        issue_index([parent, child, sibling, external]),
    ) == ("SIBLING", "EXTERNAL")


def test_dashboard_waiting_on_matches_executor_projection():
    parent = make_issue(
        "OOMPAH-804",
        blocked_by=["OOMPAH-834", "EXTERNAL"],
    )
    child = make_issue("OOMPAH-834", parent_id="OOMPAH-804")
    child.state = "Ready to Integrate"
    external = make_issue("EXTERNAL")
    external.state = "Open"
    item = IntegrationQueueItem(
        project_id="oompah",
        epic_id="OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch="epic-OOMPAH-804--task-OOMPAH-834",
        head_sha="a" * 40,
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-08-06T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-08-06T00:00:00+00:00",
    )
    issues = [parent, child, external]

    dependency_map = Orchestrator.__new__(Orchestrator)._integration_dependency_map(
        issues,
        [item],
    )
    summary = _integration_queue_summary(item, child, issues)

    assert dependency_map[item.task_id] == ("EXTERNAL",)
    assert summary["waiting_on"] == list(dependency_map[item.task_id])
