"""Tests for nested container rollup edge filtering in integration dependencies."""

from oompah.dependency_graph import integration_dependencies, issue_index
from oompah.models import BlockerRef, Issue


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
    # Child doesn't have grandparent in effective_dependencies at all
    # because they're linked through parent, not direct ancestor of child


if __name__ == "__main__":
    # Run tests manually for verification
    test_child_excludes_implicit_parent_rollup_edge()
    test_child_preserves_explicit_external_dependencies()
    test_child_preserves_explicit_sibling_dependencies()
    test_child_preserves_ancestor_external_dependencies()
    test_standalone_child_without_parent()
    test_multiple_siblings_complex_scenario()
    test_integration_dependencies_empty_for_no_deps()
    test_integration_dependencies_handles_missing_issue()
    test_nested_three_levels_deep()
    print("All tests passed!")
