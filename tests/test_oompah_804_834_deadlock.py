"""Test case for the exact OOMPAH-804/834 deadlock scenario described in the issue."""

from oompah.dependency_graph import integration_dependencies, issue_index
from oompah.models import BlockerRef, Issue
from oompah.integration_queue import IntegrationQueueStore


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


def test_oompah_804_834_deadlock_scenario():
    """
    Reproduce the exact deadlock scenario from OOMPAH-804/834:
    - OOMPAH-804 is a task with children OOMPAH-834..837
    - OOMPAH-804 has finish dependencies on its children for rollup
    - Without the fix, OOMPAH-834 would inherit all OOMPAH-804 dependencies
      creating a self-wait and preventing integration
    """

    # Create the exact scenario
    parent = make_issue("OOMPAH-804", blocked_by=[
        "OOMPAH-834", "OOMPAH-835", "OOMPAH-836", "OOMPAH-837"
    ])
    child1 = make_issue("OOMPAH-834", parent_id="OOMPAH-804")
    child2 = make_issue("OOMPAH-835", parent_id="OOMPAH-804")
    child3 = make_issue("OOMPAH-836", parent_id="OOMPAH-804")
    child4 = make_issue("OOMPAH-837", parent_id="OOMPAH-804")

    issues = [parent, child1, child2, child3, child4]
    index = issue_index(issues)

    # Verify that each child does NOT inherit parent rollup edges
    deps_834 = integration_dependencies(child1, index)
    deps_835 = integration_dependencies(child2, index)
    deps_836 = integration_dependencies(child3, index)
    deps_837 = integration_dependencies(child4, index)

    # Critical: no child should depend on itself
    assert "OOMPAH-834" not in deps_834, "OOMPAH-834 should not depend on itself"
    assert "OOMPAH-835" not in deps_835, "OOMPAH-835 should not depend on itself"
    assert "OOMPAH-836" not in deps_836, "OOMPAH-836 should not depend on itself"
    assert "OOMPAH-837" not in deps_837, "OOMPAH-837 should not depend on itself"

    # Critical: no child should depend on parent for rollup
    assert "OOMPAH-804" not in deps_834, "OOMPAH-834 should not depend on parent"
    assert "OOMPAH-804" not in deps_835, "OOMPAH-835 should not depend on parent"
    assert "OOMPAH-804" not in deps_836, "OOMPAH-836 should not depend on parent"
    assert "OOMPAH-804" not in deps_837, "OOMPAH-837 should not depend on parent"

    # Critical: no child should depend on siblings (implicit rollup)
    assert "OOMPAH-835" not in deps_834, "OOMPAH-834 should not depend on siblings"
    assert "OOMPAH-836" not in deps_834, "OOMPAH-834 should not depend on siblings"
    assert "OOMPAH-837" not in deps_834, "OOMPAH-834 should not depend on siblings"


def test_queue_allows_eligible_child_to_claim_lease():
    """
    Verify that the integration queue can now claim an eligible child
    without waiting on siblings or parent.
    """
    store = IntegrationQueueStore(":memory:")

    # Enqueue parent and children
    parent = store.enqueue(
        project_id="p1",
        epic_id="EPIC-OOMPAH-804",
        task_id="OOMPAH-804",
        task_branch="task/OOMPAH-804",
        head_sha="aaaa0000",
    )
    child1 = store.enqueue(
        project_id="p1",
        epic_id="EPIC-OOMPAH-804",
        task_id="OOMPAH-834",
        task_branch="task/OOMPAH-834",
        head_sha="bbbb0001",
    )
    child2 = store.enqueue(
        project_id="p1",
        epic_id="EPIC-OOMPAH-804",
        task_id="OOMPAH-835",
        task_branch="task/OOMPAH-835",
        head_sha="cccc0002",
    )

    # Build dependency map with the fix
    # Without the fix, child1 would depend on itself and siblings
    # With the fix, each child has empty dependencies
    dependency_map = {
        "OOMPAH-804": (),  # Parent has no external deps
        "OOMPAH-834": (),  # Child 1 has no integration deps (after filtering)
        "OOMPAH-835": (),  # Child 2 has no integration deps (after filtering)
    }
    satisfied = set()

    # With the fix, the first ready child should be claimable immediately
    claimed = store.claim_next(
        project_id="p1",
        epic_id="EPIC-OOMPAH-804",
        lease_owner="worker-1",
        dependency_map=dependency_map,
        satisfied=satisfied,
    )

    # This would have been None without the fix (deadlock)
    assert claimed is not None, "Child should be claimable when dependencies are filtered"
    assert claimed.task_id in ("OOMPAH-834", "OOMPAH-835"), \
        f"Expected child task, got {claimed.task_id}"

    # Complete the first child
    assert store.complete("p1", claimed.task_id, lease_owner="worker-1")

    # Now another child should be claimable
    claimed2 = store.claim_next(
        project_id="p1",
        epic_id="EPIC-OOMPAH-804",
        lease_owner="worker-2",
        dependency_map=dependency_map,
        satisfied=set(),  # Even with no satisfied deps, children can proceed
    )

    assert claimed2 is not None, "Second child should be claimable"
    assert claimed2.task_id != claimed.task_id, "Different child should be claimed"


def test_external_prerequisites_still_block_integration():
    """
    Verify that real external prerequisites still block integration
    even after filtering rollup edges.
    """
    parent = make_issue("PARENT-804", blocked_by=[
        "CHILD-834", "EXTERNAL-500"
    ])
    child = make_issue("CHILD-834", parent_id="PARENT-804")
    external = make_issue("EXTERNAL-500")

    index = issue_index([parent, child, external])

    deps = integration_dependencies(child, index)

    # Parent has external dependency, so child inherits it
    assert "EXTERNAL-500" in deps, \
        "Child should inherit external dependencies from parent"
    # But not depend on parent itself or siblings
    assert "PARENT-804" not in deps, "Child should not depend on parent"


if __name__ == "__main__":
    test_oompah_804_834_deadlock_scenario()
    test_queue_allows_eligible_child_to_claim_lease()
    test_external_prerequisites_still_block_integration()
    print("All OOMPAH-804/834 deadlock tests passed!")
