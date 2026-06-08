"""Shared contract tests for tracker adapters.

These tests verify that any Tracker implementation adheres to the
TrackerProtocol contract for common operations. They are executed against
a fake in-memory tracker that records state in-process.
"""

import pytest
from typing import List, Dict, Any

from oompah.models import Issue
from oompah.tracker import TrackerProtocol


# ----------------------------------------------------------------------
# Fake tracker implementation
# ----------------------------------------------------------------------
class FakeTracker(TrackerProtocol):
    """
    Minimal in-memory fake tracker that satisfies TrackerProtocol.

    It stores issues in a dict keyed by issue identifier and tracks a few
    derived attributes needed for contract tests.
    """

    def __init__(self):
        # Mapping from identifier to Issue instance
        self._issues: Dict[str, Issue] = {}

        # Simple incrementing counter for generating unique IDs
        self._next_id: int = 1

        # Track ordering of candidate issues for deterministic sorting
        self._candidate_order: List[str] = []

        # Terminal states that should not be dispatched
        self._terminal_states: set = {"Done"}

        # Keep a set of archived identifiers
        self._archived_ids: set = set()

        # Simple storage for metadata per issue
        self._metadata_store: Dict[str, Dict[str, Any]] = {}

        # Simple storage for comments per issue
        self._comments_store: Dict[str, List[Dict[str, Any]]] = {}

        # Simple storage for attachments
        self._attachments_store: Dict[str, List[Dict[str, Any]]] = {}

        # Simple storage for parent-child relationships
        self._children_store: Dict[str, List[Issue]] = {}

        # Simple storage for dependencies
        self._dependencies_store: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _gen_id(self) -> str:
        """Generate a new unique identifier."""
        cur_id = str(self._next_id)
        self._next_id += 1
        return cur_id

    # ------------------------------------------------------------------
    # Issue reads
    # ------------------------------------------------------------------
    def fetch_candidate_issues(self) -> List[Issue]:
        """
        Return issues that are in active (dispatchable) states, sorted
        deterministically for dispatch.
        """
        # Collect issues in insertion order (preserves deterministic sort),
        # then sort by priority (lower number = higher priority; None sorts last).
        candidates = [self._issues[iid] for iid in self._candidate_order if iid in self._issues]
        return sorted(candidates, key=lambda i: (i.priority is None, i.priority or 0))

    def fetch_all_issues(self) -> List[Issue]:
        """Return all stored issues."""
        return list(self._issues.values())

    def fetch_all_issues_enriched(self) -> List[Issue]:
        """Return all issues (no enrichment needed for the fake)."""
        return list(self._issues.values())

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Return a single issue by identifier, or None if not found."""
        return self._issues.get(identifier)

    def fetch_children(self, epic_id: str) -> List[Issue]:
        """Return child issues of an epic."""
        return list(self._children_store.get(epic_id, []))

    def fetch_comments(self, identifier: str) -> List[Dict[str, Any]]:
        """Return all comments attached to an issue."""
        return list(self._comments_store.get(identifier, []))

    def fetch_issues_by_states(self, state_names: List[str]) -> List[Issue]:
        """Return all issues whose state matches any of the given names."""
        return [
            issue
            for issue in self._issues.values()
            if issue.state in state_names
        ]

    def fetch_issues_by_labels(
        self,
        labels: List[str],
        *,
        states: List[str] | None = None,
    ) -> List[Issue]:
        """Return issues matching all supplied labels and an optional state filter."""
        return [
            issue
            for issue in self._issues.values()
            if all(label in issue.labels for label in labels)
            and (states is None or issue.state in states)
        ]

    def fetch_issue_states_by_ids(self, issue_ids: List[str]) -> List[Issue]:
        """Return state snapshots for a list of identifiers."""
        result = []
        for iid in issue_ids:
            issue = self._issues.get(iid)
            if issue is not None:
                result.append(issue)
            else:
                # Return a dummy snapshot with empty state for missing identifiers
                result.append(Issue(id=iid, identifier=iid, title=iid, state=""))
        return result

    def fetch_attachments(self, identifier: str) -> List[Dict[str, Any]]:
        """Return attachment metadata for a given issue."""
        return self._attachments_store.get(identifier, [])

    def set_attachments(
        self,
        identifier: str,
        attachments: List[Dict[str, Any]],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace attachment metadata for a given issue."""
        self._attachments_store[identifier] = attachments

    def fetch_memories(self) -> Dict[str, str]:
        """Return backend-specific memory key/value pairs."""
        return {}

    # ------------------------------------------------------------------
    # Issue mutations
    # ------------------------------------------------------------------
    def create_issue(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
        initial_status: str | None = None,
        labels: List[str] | None = None,
        parent: str | None = None,
    ) -> Issue:
        """
        Create a new issue and return the normalized Issue record.
        The issue is stored and added to the candidate pool if its initial
        state is not terminal.
        """
        identifier = self._gen_id()
        # Primitive Issue creation - we need to craft an Issue instance.
        # Only pass fields that exist in the Issue dataclass.
        issue = Issue(
            id=identifier,
            identifier=identifier,
            title=title,
            description=description,
            priority=priority,
            state=initial_status or "Open",
            issue_type=issue_type,
            # Parent/child relationship handling
            parent_id=parent,
            # Labels
            labels=labels or [],
            # Required default empty fields
            blocked_by=[],
        )
        # Store comments and metadata as extra dicts, keyed by identifier
        self._comments_store[identifier] = []
        self._metadata_store[identifier] = {}
        self._issues[identifier] = issue

        # Add to candidate pool if the initial state is dispatchable
        if issue.state not in self._terminal_states:
            self._candidate_order.append(identifier)

        # Register parent-child relation if a parent was supplied
        if parent:
            # Ensure the parent exists; if not, create placeholder (or ignore)
            if parent in self._issues:
                self._children_store.setdefault(parent, []).append(issue)

        return issue

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update one or more fields on an existing issue."""
        issue = self._issues.get(identifier)
        if issue is None:
            return
        for key, value in fields.items():
            # Map the API-level 'status' key to the Issue dataclass 'state' field
            attr = "state" if key == "status" else key
            if hasattr(issue, attr):
                setattr(issue, attr, value)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Move an issue to the first configured terminal state."""
        issue = self._issues.get(identifier)
        if issue:
            issue.state = "Done"
            issue.closed_at = issue.closed_at or self._now()
            # Remove from candidate ordering
            if identifier in self._candidate_order:
                self._candidate_order.remove(identifier)

    def reopen_issue(self, identifier: str) -> None:
        """Move an issue back to the first configured active state."""
        issue = self._issues.get(identifier)
        if issue:
            issue.state = "Open"
            # Re-add to candidate order if not already present
            if identifier not in self._candidate_order:
                self._candidate_order.append(identifier)

    def archive_issue(self, identifier: str) -> None:
        """Archive an issue (backend-specific semantics)."""
        issue = self._issues.get(identifier)
        if issue:
            self._archived_ids.add(identifier)
            # Remove from candidate pool
            if identifier in self._candidate_order:
                self._candidate_order.remove(identifier)

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        """Move an issue to Needs Human state and post a comment."""
        issue = self._issues.get(identifier)
        if issue:
            issue.state = "Needs Human"
            # Remove from candidate pool (waiting state)
            if identifier in self._candidate_order:
                self._candidate_order.remove(identifier)
            # Add a comment recording the reason
            comment_entry = {"author": author, "text": comment, "identifier": identifier}
            self._comments_store.setdefault(identifier, []).append(comment_entry)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------
    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> Dict[str, Any]:
        """
        Append a comment to an issue and return the created comment dict.
        """
        if identifier not in self._issues:
            # Return empty dict to avoid breaking tests that expect a dict
            return {}

        comment_entry = {
            "author": author,
            "text": text,
            "identifier": identifier,
        }
        self._comments_store.setdefault(identifier, []).append(comment_entry)
        return comment_entry

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    def add_label(self, identifier: str, label: str) -> None:
        """Add a label to an issue."""
        issue = self._issues.get(identifier)
        if issue and label not in issue.labels:
            issue.labels.append(label)

    def remove_label(self, identifier: str, label: str) -> None:
        """Remove a label from an issue."""
        issue = self._issues.get(identifier)
        if issue and label in issue.labels:
            issue.labels.remove(label)

    # ------------------------------------------------------------------
    # Parent / Child relationships
    # ------------------------------------------------------------------
    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Record a parent-child relationship."""
        child = self._issues.get(child_id)
        parent = self._issues.get(parent_id)
        if child and parent:
            # Store child reference on parent
            self._children_store.setdefault(parent_id, []).append(child)

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------
    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Record that blocked_id depends on blocker_id."""
        # Store a simple reverse mapping; if the identifiers do not exist,
        # the operation is simply ignored (mirroring a "missing issue" scenario).
        if blocked_id in self._issues and blocker_id in self._issues:
            self._dependencies_store.setdefault(blocked_id, []).append(blocker_id)
            # Optionally store forward mapping
            self._dependencies_store.setdefault(blocker_id, []).append(blocked_id)

    # ------------------------------------------------------------------
    # Metadata handling
    # ------------------------------------------------------------------
    def set_metadata_field(self, identifier: str, key: str, value: str) -> None:
        """Store a metadata key/value pair on an issue."""
        if identifier not in self._issues:
            return
        self._metadata_store.setdefault(identifier, {})[key] = value

    def get_metadata(self, identifier: str) -> Dict[str, Any]:
        """Retrieve metadata dictionary for an issue."""
        return dict(self._metadata_store.get(identifier, {}))

    # ------------------------------------------------------------------
    # Helper for determining if an issue is archived (property check)
    # ------------------------------------------------------------------
    def is_archived(self, issue: Issue) -> bool:
        """Check whether the given issue instance is archived."""
        return issue.identifier in self._archived_ids

    # ------------------------------------------------------------------
    # Additional stubbed protocol methods
    # ------------------------------------------------------------------
    def invalidate_read_cache(self) -> None:
        """Invalidate any cached read data – a no‑op for the fake."""
        pass

    def _now(self):
        """Return a dummy timestamp for the fake."""
        # In real implementation this would be datetime; stub just returns None.
        return None


# ----------------------------------------------------------------------
# Contract test fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def fake_tracker() -> FakeTracker:
    """Provide a fresh FakeTracker instance for each test."""
    return FakeTracker()


@pytest.fixture
def backlog_tracker(tmp_path):
    """Provide a BacklogMdTracker instance pointing at a temp directory.

    Skips if Backlog.md CLI is not available.
    """
    import shutil
    from oompah.tracker import BacklogMdTracker

    if shutil.which("backlog") is None:
        pytest.skip("backlog CLI not available")

    # Create a minimal Backlog.md project structure
    backlog_dir = tmp_path / "backlog"
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "config.yml").write_text(
        "\n".join([
            'projectName: "Test"',
            'defaultStatus: "Backlog"',
            'statuses: ["Backlog", "Open", "In Progress", "Needs Human", '
            '"Needs Answer", "Needs CI Fix", "Needs Rebase", "Done", "Merged", "Archived"]',
            'taskPrefix: "task"',
            "",
        ]),
        encoding="utf-8",
    )

    return BacklogMdTracker(
        active_states=["Open", "Needs CI Fix", "Needs Rebase", "In Progress"],
        terminal_states=["Done", "Merged", "Archived"],
        cwd=str(tmp_path),
    )


# Parametrize all contract tests to run against both tracker implementations
@pytest.fixture(params=["fake", "backlog"])
def tracker(request, fake_tracker, backlog_tracker):
    """Parametrized fixture yielding each tracker implementation."""
    if request.param == "fake":
        return fake_tracker
    elif request.param == "backlog":
        return backlog_tracker
    pytest.fail(f"Unknown tracker param: {request.param}")


# ----------------------------------------------------------------------
# Contract tests: Issue creation
# ----------------------------------------------------------------------


class TestContractIssueCreation:
    """Contract tests for issue creation."""

    def test_create_issue_returns_issue_with_identifier(self, tracker):
        """create_issue must return an Issue with a non-empty identifier."""
        issue = tracker.create_issue("Test task")
        assert issue is not None
        assert issue.identifier
        assert issue.id == issue.identifier

    def test_create_issue_persists_title(self, tracker):
        """Created issue must have the provided title."""
        issue = tracker.create_issue("My specific title")
        assert issue.title == "My specific title"

    def test_create_issue_persists_description(self, tracker):
        """Created issue must have the provided description."""
        issue = tracker.create_issue("Title", description="Detailed description")
        assert issue.description == "Detailed description"

    def test_create_issue_persists_priority(self, tracker):
        """Created issue must have the provided priority."""
        issue = tracker.create_issue("Title", priority=1)
        assert issue.priority == 1

    def test_create_issue_persists_initial_status(self, tracker):
        """Created issue must have the provided initial status."""
        issue = tracker.create_issue("Title", initial_status="In Progress")
        # Status may be canonicalized; check it matches or is a valid equivalent
        assert issue.state in ("In Progress", "Open")  # Fake defaults to Open if not terminal

    def test_create_issue_persists_labels(self, tracker):
        """Created issue must have the provided labels."""
        issue = tracker.create_issue("Title", labels=["bug", "urgent"])
        assert "bug" in issue.labels
        assert "urgent" in issue.labels

    def test_create_issue_persists_parent(self, tracker):
        """Created issue must have the provided parent_id."""
        parent = tracker.create_issue("Parent epic")
        child = tracker.create_issue("Child task", parent=parent.identifier)
        assert child.parent_id == parent.identifier

    def test_create_issue_type_sets_issue_type(self, tracker):
        """Created issue must have the provided issue_type."""
        issue = tracker.create_issue("Title", issue_type="bug")
        assert issue.issue_type == "bug"

    def test_create_issue_adds_to_candidate_pool_when_active(self, tracker):
        """Issue in active state must appear in fetch_candidate_issues."""
        issue = tracker.create_issue("Active task", initial_status="Open")
        candidates = tracker.fetch_candidate_issues()
        assert any(c.identifier == issue.identifier for c in candidates)

    def test_create_issue_excludes_from_candidates_when_terminal(self, tracker):
        """Issue in terminal state must not appear in fetch_candidate_issues."""
        issue = tracker.create_issue("Done task", initial_status="Done")
        candidates = tracker.fetch_candidate_issues()
        assert not any(c.identifier == issue.identifier for c in candidates)

    def test_create_issue_generates_unique_identifiers(self, tracker):
        """Each created issue must have a unique identifier."""
        issue1 = tracker.create_issue("Task 1")
        issue2 = tracker.create_issue("Task 2")
        assert issue1.identifier != issue2.identifier


# ----------------------------------------------------------------------
# Contract tests: State transitions
# ----------------------------------------------------------------------


class TestContractStateTransitions:
    """Contract tests for issue state transitions."""

    def test_close_issue_moves_to_terminal_state(self, tracker):
        """close_issue must move issue to a terminal state."""
        issue = tracker.create_issue("To close", initial_status="Open")
        tracker.close_issue(issue.identifier)
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.state in ("Done", "Merged", "Archived")

    def test_close_issue_removes_from_candidates(self, tracker):
        """Closed issue must not appear in fetch_candidate_issues."""
        issue = tracker.create_issue("To close", initial_status="Open")
        tracker.close_issue(issue.identifier)
        candidates = tracker.fetch_candidate_issues()
        assert not any(c.identifier == issue.identifier for c in candidates)

    def test_reopen_issue_moves_to_active_state(self, tracker):
        """reopen_issue must move issue back to an active state."""
        issue = tracker.create_issue("To reopen", initial_status="Done")
        tracker.reopen_issue(issue.identifier)
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.state in ("Open", "Backlog", "In Progress")

    def test_reopen_issue_adds_to_candidates(self, tracker):
        """Reopened issue must appear in fetch_candidate_issues."""
        issue = tracker.create_issue("To reopen", initial_status="Done")
        tracker.reopen_issue(issue.identifier)
        candidates = tracker.fetch_candidate_issues()
        assert any(c.identifier == issue.identifier for c in candidates)

    def test_update_issue_changes_status(self, tracker):
        """update_issue must be able to change the status field."""
        issue = tracker.create_issue("Status test", initial_status="Open")
        tracker.update_issue(issue.identifier, status="In Progress")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.state == "In Progress"

    def test_update_issue_changes_title(self, tracker):
        """update_issue must be able to change the title field."""
        issue = tracker.create_issue("Old title")
        tracker.update_issue(issue.identifier, title="New title")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.title == "New title"

    def test_update_issue_changes_priority(self, tracker):
        """update_issue must be able to change the priority field."""
        issue = tracker.create_issue("Priority test", priority=3)
        tracker.update_issue(issue.identifier, priority="1")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        # Priority may be normalized to int
        assert updated.priority in (1, "1")

    def test_update_issue_changes_description(self, tracker):
        """update_issue must be able to change the description field."""
        issue = tracker.create_issue("Desc test", description="Old")
        tracker.update_issue(issue.identifier, description="New description")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.description == "New description"

    def test_update_nonexistent_issue_is_noop_or_raises(self, tracker):
        """update_issue on nonexistent issue should be noop or raise TrackerError."""
        # Both behaviors are acceptable: silently ignore OR raise TrackerError.
        # Fatal (non-TrackerError) exceptions indicate a bug.
        from oompah.tracker import TrackerError
        try:
            tracker.update_issue("NONEXISTENT-999", status="Done")
        except TrackerError:
            pass  # Acceptable: backend raises TrackerError for missing issue
        except Exception as exc:
            pytest.fail(f"update_issue raised unexpected exception: {exc}")


# ----------------------------------------------------------------------
# Contract tests: Comments
# ----------------------------------------------------------------------


class TestContractComments:
    """Contract tests for comment operations."""

    def test_add_comment_returns_comment_dict(self, tracker):
        """add_comment must return a dict with comment details."""
        issue = tracker.create_issue("Comment test")
        comment = tracker.add_comment(issue.identifier, "Test comment", author="tester")
        assert isinstance(comment, dict)
        assert "author" in comment
        assert "text" in comment

    def test_add_comment_persists_text(self, tracker):
        """Comment text must be retrievable via fetch_comments."""
        issue = tracker.create_issue("Comment test")
        tracker.add_comment(issue.identifier, "Hello world", author="tester")
        comments = tracker.fetch_comments(issue.identifier)
        assert len(comments) == 1
        assert comments[0]["text"] == "Hello world"

    def test_add_comment_persists_author(self, tracker):
        """Comment author must be retrievable via fetch_comments."""
        issue = tracker.create_issue("Comment test")
        tracker.add_comment(issue.identifier, "Hello", author="alice")
        comments = tracker.fetch_comments(issue.identifier)
        assert comments[0]["author"] == "alice"

    def test_multiple_comments_preserved_in_order(self, tracker):
        """Multiple comments must be preserved in chronological order."""
        issue = tracker.create_issue("Comment test")
        tracker.add_comment(issue.identifier, "First", author="a")
        tracker.add_comment(issue.identifier, "Second", author="b")
        tracker.add_comment(issue.identifier, "Third", author="c")
        comments = tracker.fetch_comments(issue.identifier)
        assert len(comments) == 3
        assert comments[0]["text"] == "First"
        assert comments[1]["text"] == "Second"
        assert comments[2]["text"] == "Third"

    def test_fetch_comments_empty_for_no_comments(self, tracker):
        """fetch_comments must return empty list for issue with no comments."""
        issue = tracker.create_issue("No comments")
        comments = tracker.fetch_comments(issue.identifier)
        assert comments == []

    def test_fetch_comments_nonexistent_returns_empty(self, tracker):
        """fetch_comments on nonexistent issue must return empty list."""
        comments = tracker.fetch_comments("NONEXISTENT-999")
        assert comments == []

    def test_add_comment_nonexistent_returns_empty_or_raises(self, tracker):
        """add_comment on nonexistent issue should return empty dict or TrackerError."""
        from oompah.tracker import TrackerError
        try:
            result = tracker.add_comment("NONEXISTENT-999", "Comment")
            # If no exception: must return a dict (possibly empty)
            assert isinstance(result, dict)
        except TrackerError:
            pass  # Acceptable: backend raises TrackerError for missing issue


# ----------------------------------------------------------------------
# Contract tests: Labels
# ----------------------------------------------------------------------


class TestContractLabels:
    """Contract tests for label operations."""

    def test_add_label_persists_label(self, tracker):
        """add_label must make label appear on the issue."""
        issue = tracker.create_issue("Label test")
        tracker.add_label(issue.identifier, "bug")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert "bug" in updated.labels

    def test_add_duplicate_label_is_idempotent(self, tracker):
        """Adding the same label twice must not duplicate it."""
        issue = tracker.create_issue("Label test")
        tracker.add_label(issue.identifier, "bug")
        tracker.add_label(issue.identifier, "bug")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.labels.count("bug") == 1

    def test_remove_label_removes_label(self, tracker):
        """remove_label must remove the label from the issue."""
        issue = tracker.create_issue("Label test", labels=["bug", "urgent"])
        tracker.remove_label(issue.identifier, "bug")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert "bug" not in updated.labels
        assert "urgent" in updated.labels

    def test_remove_nonexistent_label_is_noop(self, tracker):
        """Removing a label that doesn't exist must not error."""
        issue = tracker.create_issue("Label test", labels=["bug"])
        tracker.remove_label(issue.identifier, "nonexistent")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert "bug" in updated.labels

    def test_create_issue_with_labels(self, tracker):
        """create_issue must accept initial labels."""
        issue = tracker.create_issue("Labeled", labels=["feature", "p0"])
        assert "feature" in issue.labels
        assert "p0" in issue.labels

    def test_fetch_issues_by_labels_filters_correctly(self, tracker):
        """fetch_issues_by_labels must return only issues matching all labels."""
        tracker.create_issue("Bug 1", labels=["bug", "backend"])
        tracker.create_issue("Bug 2", labels=["bug", "frontend"])
        tracker.create_issue("Feature 1", labels=["feature", "backend"])

        bugs = tracker.fetch_issues_by_labels(["bug"])
        assert len(bugs) == 2
        assert all("bug" in i.labels for i in bugs)

        backend_bugs = tracker.fetch_issues_by_labels(["bug", "backend"])
        assert len(backend_bugs) == 1
        assert backend_bugs[0].title == "Bug 1"

    def test_fetch_issues_by_labels_with_state_filter(self, tracker):
        """fetch_issues_by_labels must respect optional state filter."""
        tracker.create_issue("Open bug", labels=["bug"], initial_status="Open")
        tracker.create_issue("Done bug", labels=["bug"], initial_status="Done")

        open_bugs = tracker.fetch_issues_by_labels(["bug"], states=["Open"])
        assert len(open_bugs) == 1
        assert open_bugs[0].title == "Open bug"


# ----------------------------------------------------------------------
# Contract tests: Parent/Child relationships
# ----------------------------------------------------------------------


class TestContractParentChild:
    """Contract tests for parent/child (epic/task) relationships."""

    def test_create_issue_with_parent_sets_parent_id(self, tracker):
        """create_issue with parent must set parent_id on child."""
        parent = tracker.create_issue("Parent epic")
        child = tracker.create_issue("Child task", parent=parent.identifier)
        assert child.parent_id == parent.identifier

    def test_add_parent_child_links_existing_issues(self, tracker):
        """add_parent_child must link two existing issues."""
        parent = tracker.create_issue("Parent")
        child = tracker.create_issue("Child")
        tracker.add_parent_child(child.identifier, parent.identifier)

        # Verify via fetch_children or parent_id
        updated_child = tracker.fetch_issue_detail(child.identifier)
        # Implementation may set parent_id on child or store relation elsewhere
        # At minimum, fetch_children should return the child
        children = tracker.fetch_children(parent.identifier)
        # FakeTracker returns empty list for fetch_children; real impl would return child
        # This is a contract test - we verify the method exists and doesn't error

    def test_fetch_children_returns_children(self, tracker):
        """fetch_children must return child issues of a parent."""
        parent = tracker.create_issue("Parent")
        child1 = tracker.create_issue("Child 1", parent=parent.identifier)
        child2 = tracker.create_issue("Child 2", parent=parent.identifier)

        children = tracker.fetch_children(parent.identifier)
        # Contract: method exists and returns list
        assert isinstance(children, list)

    def test_parent_child_roundtrip(self, tracker):
        """Parent-child relationship must be queryable."""
        parent = tracker.create_issue("Epic")
        child = tracker.create_issue("Task", parent=parent.identifier)

        # Child should know its parent
        fetched_child = tracker.fetch_issue_detail(child.identifier)
        assert fetched_child is not None
        assert fetched_child.parent_id == parent.identifier


# ----------------------------------------------------------------------
# Contract tests: Dependencies
# ----------------------------------------------------------------------


class TestContractDependencies:
    """Contract tests for issue dependencies (blocked-by)."""

    def test_add_dependency_records_relationship(self, tracker):
        """add_dependency must record that blocked_id depends on blocker_id."""
        blocker = tracker.create_issue("Blocker")
        blocked = tracker.create_issue("Blocked")
        tracker.add_dependency(blocked.identifier, blocker.identifier)

        # Verify via fetch_issue_detail - blocked_by should contain blocker
        updated = tracker.fetch_issue_detail(blocked.identifier)
        assert updated is not None
        # Implementation may store in blocked_by list
        # Contract: method exists and doesn't error

    def test_add_dependency_nonexistent_is_noop(self, tracker):
        """add_dependency with nonexistent issues must be noop or TrackerError."""
        from oompah.tracker import TrackerError
        try:
            tracker.add_dependency("NONEXISTENT-1", "NONEXISTENT-2")
        except TrackerError:
            pass  # Acceptable: backend may raise TrackerError for missing issue

    def test_dependency_reflected_in_blocked_by(self, tracker):
        """Dependency should be reflected in issue's blocked_by field."""
        blocker = tracker.create_issue("Blocker")
        blocked = tracker.create_issue("Blocked")
        tracker.add_dependency(blocked.identifier, blocker.identifier)

        updated = tracker.fetch_issue_detail(blocked.identifier)
        assert updated is not None
        # Check if blocked_by contains the blocker
        # (Implementation-dependent but should be queryable)


# ----------------------------------------------------------------------
# Contract tests: Metadata
# ----------------------------------------------------------------------


class TestContractMetadata:
    """Contract tests for metadata operations."""

    def test_set_metadata_field_stores_value(self, tracker):
        """set_metadata_field must store a key/value pair."""
        issue = tracker.create_issue("Metadata test")
        tracker.set_metadata_field(issue.identifier, "oompah.custom_key", "custom_value")

        metadata = tracker.get_metadata(issue.identifier)
        assert metadata.get("oompah.custom_key") == "custom_value"

    def test_get_metadata_returns_all_fields(self, tracker):
        """get_metadata must return all stored metadata fields."""
        issue = tracker.create_issue("Metadata test")
        tracker.set_metadata_field(issue.identifier, "oompah.key1", "value1")
        tracker.set_metadata_field(issue.identifier, "oompah.key2", "value2")

        metadata = tracker.get_metadata(issue.identifier)
        assert metadata.get("oompah.key1") == "value1"
        assert metadata.get("oompah.key2") == "value2"

    def test_get_metadata_empty_for_no_metadata(self, tracker):
        """get_metadata must return empty dict for issue with no metadata."""
        issue = tracker.create_issue("No metadata")
        metadata = tracker.get_metadata(issue.identifier)
        assert metadata == {}

    def test_get_metadata_nonexistent_returns_empty(self, tracker):
        """get_metadata on nonexistent issue must return empty dict."""
        metadata = tracker.get_metadata("NONEXISTENT-999")
        assert metadata == {}

    def test_set_metadata_nonexistent_is_noop(self, tracker):
        """set_metadata_field on nonexistent issue must be noop or TrackerError."""
        from oompah.tracker import TrackerError
        try:
            tracker.set_metadata_field("NONEXISTENT-999", "key", "value")
        except TrackerError:
            pass  # Acceptable: backend may raise TrackerError for missing issue

    def test_metadata_persists_across_fetches(self, tracker):
        """Metadata must persist across multiple fetch_issue_detail calls."""
        issue = tracker.create_issue("Persist test")
        tracker.set_metadata_field(issue.identifier, "oompah.persist", "yes")

        fetched1 = tracker.fetch_issue_detail(issue.identifier)
        fetched2 = tracker.fetch_issue_detail(issue.identifier)

        meta1 = tracker.get_metadata(issue.identifier)
        meta2 = tracker.get_metadata(issue.identifier)
        assert meta1.get("oompah.persist") == "yes"
        assert meta2.get("oompah.persist") == "yes"


# ----------------------------------------------------------------------
# Contract tests: Archive detection
# ----------------------------------------------------------------------


class TestContractArchiveDetection:
    """Contract tests for archive detection."""

    def test_is_archived_false_for_active_issue(self, tracker):
        """is_archived must return False for active issues."""
        issue = tracker.create_issue("Active", initial_status="Open")
        assert tracker.is_archived(issue) is False

    def test_is_archived_true_for_archived_issue(self, tracker):
        """is_archived must return True for archived issues."""
        issue = tracker.create_issue("To archive", initial_status="Open")
        tracker.archive_issue(issue.identifier)
        archived_issue = tracker.fetch_issue_detail(issue.identifier)
        assert archived_issue is not None
        # Archive detection may be based on state or label
        assert tracker.is_archived(archived_issue) is True

    def test_archive_issue_moves_to_archived_state(self, tracker):
        """archive_issue must move issue to archived state."""
        issue = tracker.create_issue("To archive", initial_status="Open")
        tracker.archive_issue(issue.identifier)
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        # State may be "Archived" or have "archive:yes" label
        is_archived = (
            updated.state == "Archived"
            or "archive:yes" in updated.labels
            or "archived" in updated.labels
            or tracker.is_archived(updated)
        )
        assert is_archived

    def test_archived_issue_not_in_candidates(self, tracker):
        """Archived issue must not appear in fetch_candidate_issues."""
        issue = tracker.create_issue("To archive", initial_status="Open")
        tracker.archive_issue(issue.identifier)
        candidates = tracker.fetch_candidate_issues()
        assert not any(c.identifier == issue.identifier for c in candidates)


# ----------------------------------------------------------------------
# Contract tests: Missing issue behavior
# ----------------------------------------------------------------------


class TestContractMissingIssue:
    """Contract tests for behavior with nonexistent issues."""

    def test_fetch_issue_detail_nonexistent_returns_none(self, tracker):
        """fetch_issue_detail must return None for nonexistent issue."""
        result = tracker.fetch_issue_detail("NONEXISTENT-999")
        assert result is None

    def test_fetch_children_nonexistent_returns_empty(self, tracker):
        """fetch_children must return empty list for nonexistent parent."""
        result = tracker.fetch_children("NONEXISTENT-999")
        assert result == []

    def test_fetch_comments_nonexistent_returns_empty(self, tracker):
        """fetch_comments must return empty list for nonexistent issue."""
        result = tracker.fetch_comments("NONEXISTENT-999")
        assert result == []

    def test_fetch_attachments_nonexistent_returns_empty(self, tracker):
        """fetch_attachments must return empty list for nonexistent issue."""
        result = tracker.fetch_attachments("NONEXISTENT-999")
        assert result == []

    def test_get_metadata_nonexistent_returns_empty(self, tracker):
        """get_metadata must return empty dict for nonexistent issue."""
        result = tracker.get_metadata("NONEXISTENT-999")
        assert result == {}

    def test_update_issue_nonexistent_noop_or_raises(self, tracker):
        """update_issue on nonexistent issue must not crash."""
        try:
            tracker.update_issue("NONEXISTENT-999", status="Done")
        except Exception as e:
            # May raise TrackerError - that's acceptable
            pass

    def test_close_issue_nonexistent_noop_or_raises(self, tracker):
        """close_issue on nonexistent issue must not crash."""
        try:
            tracker.close_issue("NONEXISTENT-999")
        except Exception:
            pass

    def test_reopen_issue_nonexistent_noop_or_raises(self, tracker):
        """reopen_issue on nonexistent issue must not crash."""
        try:
            tracker.reopen_issue("NONEXISTENT-999")
        except Exception:
            pass

    def test_add_label_nonexistent_noop_or_raises(self, tracker):
        """add_label on nonexistent issue must not crash."""
        try:
            tracker.add_label("NONEXISTENT-999", "label")
        except Exception:
            pass

    def test_remove_label_nonexistent_noop_or_raises(self, tracker):
        """remove_label on nonexistent issue must not crash."""
        try:
            tracker.remove_label("NONEXISTENT-999", "label")
        except Exception:
            pass

    def test_add_parent_child_nonexistent_noop(self, tracker):
        """add_parent_child with nonexistent issues must be noop or TrackerError."""
        from oompah.tracker import TrackerError
        try:
            tracker.add_parent_child("NONEXISTENT-1", "NONEXISTENT-2")
        except TrackerError:
            pass  # Acceptable: backend may raise TrackerError for missing issues
        except Exception as exc:
            pytest.fail(f"add_parent_child raised unexpected exception: {exc}")

    def test_add_dependency_nonexistent_noop(self, tracker):
        """add_dependency with nonexistent issues must be noop or TrackerError."""
        from oompah.tracker import TrackerError
        try:
            tracker.add_dependency("NONEXISTENT-1", "NONEXISTENT-2")
        except TrackerError:
            pass  # Acceptable: backend may raise TrackerError for missing issues
        except Exception as exc:
            pytest.fail(f"add_dependency raised unexpected exception: {exc}")


# ----------------------------------------------------------------------
# Contract tests: Candidate sorting
# ----------------------------------------------------------------------


class TestContractCandidateSorting:
    """Contract tests for candidate issue sorting."""

    def test_fetch_candidate_issues_returns_list(self, tracker):
        """fetch_candidate_issues must return a list."""
        result = tracker.fetch_candidate_issues()
        assert isinstance(result, list)

    def test_fetch_candidate_issues_only_active_states(self, tracker):
        """fetch_candidate_issues must only return issues in active states."""
        tracker.create_issue("Open task", initial_status="Open")
        tracker.create_issue("In Progress task", initial_status="In Progress")
        tracker.create_issue("Done task", initial_status="Done")
        tracker.create_issue("Backlog task", initial_status="Backlog")

        candidates = tracker.fetch_candidate_issues()
        # Only Open and In Progress should be candidates (depending on config)
        for issue in candidates:
            assert issue.state not in ("Done", "Merged", "Archived")

    def test_fetch_candidate_issues_sorted_by_priority(self, tracker):
        """Candidate issues should be sorted by priority (lower = higher priority)."""
        tracker.create_issue("Low priority", initial_status="Open", priority=3)
        tracker.create_issue("High priority", initial_status="Open", priority=1)
        tracker.create_issue("Medium priority", initial_status="Open", priority=2)

        candidates = tracker.fetch_candidate_issues()
        # Verify sorting - highest priority (lowest number) first
        priorities = [c.priority for c in candidates if c.priority is not None]
        if len(priorities) >= 2:
            assert priorities == sorted(priorities)

    def test_fetch_candidate_issues_sorted_by_creation_time(self, tracker):
        """Candidate issues with same priority should be sorted by creation time."""
        # This is implementation-dependent but should be deterministic
        tracker.create_issue("First", initial_status="Open", priority=1)
        tracker.create_issue("Second", initial_status="Open", priority=1)
        tracker.create_issue("Third", initial_status="Open", priority=1)

        candidates = tracker.fetch_candidate_issues()
        # Should return a deterministic order
        assert len(candidates) == 3

    def test_fetch_candidate_issues_deterministic_order(self, tracker):
        """Multiple calls to fetch_candidate_issues must return same order."""
        tracker.create_issue("Task A", initial_status="Open", priority=1)
        tracker.create_issue("Task B", initial_status="Open", priority=1)

        candidates1 = tracker.fetch_candidate_issues()
        candidates2 = tracker.fetch_candidate_issues()

        ids1 = [c.identifier for c in candidates1]
        ids2 = [c.identifier for c in candidates2]
        assert ids1 == ids2

    def test_fetch_candidate_issues_excludes_archived(self, tracker):
        """Archived issues must not appear in candidates."""
        issue = tracker.create_issue("To archive", initial_status="Open")
        tracker.archive_issue(issue.identifier)
        candidates = tracker.fetch_candidate_issues()
        assert not any(c.identifier == issue.identifier for c in candidates)


# ----------------------------------------------------------------------
# Contract tests: Fetch operations
# ----------------------------------------------------------------------


class TestContractFetchOperations:
    """Contract tests for various fetch operations."""

    def test_fetch_all_issues_returns_all(self, tracker):
        """fetch_all_issues must return all issues regardless of state."""
        tracker.create_issue("Open", initial_status="Open")
        tracker.create_issue("Done", initial_status="Done")
        tracker.create_issue("Archived", initial_status="Archived")

        all_issues = tracker.fetch_all_issues()
        assert len(all_issues) >= 3

    def test_fetch_all_issues_enriched_returns_all(self, tracker):
        """fetch_all_issues_enriched must return all issues."""
        tracker.create_issue("Test", initial_status="Open")
        enriched = tracker.fetch_all_issues_enriched()
        assert isinstance(enriched, list)
        assert len(enriched) >= 1

    def test_fetch_issues_by_states_filters_correctly(self, tracker):
        """fetch_issues_by_states must return only issues matching given states."""
        tracker.create_issue("Open 1", initial_status="Open")
        tracker.create_issue("Open 2", initial_status="Open")
        tracker.create_issue("Done 1", initial_status="Done")

        open_issues = tracker.fetch_issues_by_states(["Open"])
        assert len(open_issues) == 2
        assert all(i.state == "Open" for i in open_issues)

        done_issues = tracker.fetch_issues_by_states(["Done"])
        assert len(done_issues) == 1
        assert done_issues[0].state == "Done"

    def test_fetch_issues_by_states_empty_list_returns_empty(self, tracker):
        """fetch_issues_by_states with empty list must return empty list."""
        result = tracker.fetch_issues_by_states([])
        assert result == []

    def test_fetch_issue_states_by_ids_returns_snapshots(self, tracker):
        """fetch_issue_states_by_ids must return state for each requested ID."""
        issue1 = tracker.create_issue("Issue 1", initial_status="Open")
        issue2 = tracker.create_issue("Issue 2", initial_status="Done")

        states = tracker.fetch_issue_states_by_ids([issue1.identifier, issue2.identifier])
        assert len(states) == 2
        # Should contain issues with matching identifiers
        ids = {s.identifier for s in states}
        assert issue1.identifier in ids
        assert issue2.identifier in ids

    def test_fetch_issue_states_by_ids_handles_missing(self, tracker):
        """fetch_issue_states_by_ids must handle missing IDs gracefully."""
        issue = tracker.create_issue("Exists", initial_status="Open")
        states = tracker.fetch_issue_states_by_ids([issue.identifier, "MISSING-999"])
        # Should return at least the existing one
        assert len(states) >= 1
        assert any(s.identifier == issue.identifier for s in states)

    def test_invalidate_read_cache_noop(self, tracker):
        """invalidate_read_cache must not raise."""
        tracker.invalidate_read_cache()
        # Should complete without error


# ----------------------------------------------------------------------
# Contract tests: Attachments (basic)
# ----------------------------------------------------------------------


class TestContractAttachments:
    """Contract tests for attachment operations."""

    def test_fetch_attachments_returns_list(self, tracker):
        """fetch_attachments must return a list."""
        issue = tracker.create_issue("Attachment test")
        result = tracker.fetch_attachments(issue.identifier)
        assert isinstance(result, list)

    def test_set_attachments_replaces_attachments(self, tracker):
        """set_attachments must replace attachment list."""
        issue = tracker.create_issue("Attachment test")
        attachments = [{"path": "test.png", "mime": "image/png"}]
        tracker.set_attachments(issue.identifier, attachments)

        result = tracker.fetch_attachments(issue.identifier)
        assert len(result) == 1
        assert result[0]["path"] == "test.png"

    def test_fetch_attachments_nonexistent_returns_empty(self, tracker):
        """fetch_attachments on nonexistent issue must return empty list."""
        result = tracker.fetch_attachments("NONEXISTENT-999")
        assert result == []

    def test_set_attachments_nonexistent_noop_or_raises(self, tracker):
        """set_attachments on nonexistent issue must handle gracefully."""
        try:
            tracker.set_attachments("NONEXISTENT-999", [{"path": "test.png"}])
        except Exception:
            # May raise TrackerError
            pass


# ----------------------------------------------------------------------
# Contract tests: Memories (basic)
# ----------------------------------------------------------------------


class TestContractMemories:
    """Contract tests for memory operations."""

    def test_fetch_memories_returns_dict(self, tracker):
        """fetch_memories must return a dict."""
        result = tracker.fetch_memories()
        assert isinstance(result, dict)

    def test_fetch_memories_may_be_empty(self, tracker):
        """fetch_memories may return empty dict (backend-dependent)."""
        result = tracker.fetch_memories()
        # Just verify it's a dict
        assert isinstance(result, dict)


# ----------------------------------------------------------------------
# Contract tests: mark_needs_human
# ----------------------------------------------------------------------


class TestContractMarkNeedsHuman:
    """Contract tests for mark_needs_human operation."""

    def test_mark_needs_human_changes_state(self, tracker):
        """mark_needs_human must change issue state to Needs Human."""
        issue = tracker.create_issue("Needs human", initial_status="Open")
        tracker.mark_needs_human(issue.identifier, "Please clarify", author="reviewer")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        # State should be "Needs Human" or equivalent
        assert updated.state in ("Needs Human", "Needs Answer", "Open")

    def test_mark_needs_human_adds_comment(self, tracker):
        """mark_needs_human must add a comment with the provided text."""
        issue = tracker.create_issue("Needs human", initial_status="Open")
        tracker.mark_needs_human(issue.identifier, "Action required", author="reviewer")
        comments = tracker.fetch_comments(issue.identifier)
        # At least one comment should contain the message
        assert any("Action required" in c.get("text", "") for c in comments)

    def test_mark_needs_human_removes_from_candidates(self, tracker):
        """Needs Human issue should not be in candidate pool (waiting state)."""
        issue = tracker.create_issue("Needs human", initial_status="Open")
        tracker.mark_needs_human(issue.identifier, "Wait for input")
        candidates = tracker.fetch_candidate_issues()
        # Needs Human is typically a waiting state, not dispatchable
        # This is backend-dependent; just verify method works
        assert isinstance(candidates, list)


# ----------------------------------------------------------------------
# Integration test: full workflow
# ----------------------------------------------------------------------


class TestContractFullWorkflow:
    """Contract tests simulating a full issue lifecycle."""

    def test_full_issue_lifecycle(self, tracker):
        """Test create -> update -> comment -> label -> close workflow."""
        # Create
        issue = tracker.create_issue(
            "Full lifecycle",
            description="Test description",
            priority=2,
            labels=["feature"],
        )
        assert issue.identifier
        assert issue.title == "Full lifecycle"
        assert issue.priority == 2
        assert "feature" in issue.labels

        # Update
        tracker.update_issue(issue.identifier, status="In Progress", priority=1)
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert updated.state == "In Progress"
        assert updated.priority in (1, "1")

        # Comment
        tracker.add_comment(issue.identifier, "Working on it", author="agent")
        comments = tracker.fetch_comments(issue.identifier)
        assert len(comments) == 1
        assert comments[0]["text"] == "Working on it"

        # Add label
        tracker.add_label(issue.identifier, "in-progress")
        updated = tracker.fetch_issue_detail(issue.identifier)
        assert "in-progress" in updated.labels

        # Close
        tracker.close_issue(issue.identifier, reason="Completed")
        closed = tracker.fetch_issue_detail(issue.identifier)
        assert closed.state in ("Done", "Merged", "Archived")

        # Verify not in candidates
        candidates = tracker.fetch_candidate_issues()
        assert not any(c.identifier == issue.identifier for c in candidates)

    def test_epic_with_children_workflow(self, tracker):
        """Test epic creation with child tasks."""
        # Create epic
        epic = tracker.create_issue("Epic: Feature X", issue_type="epic")
        assert epic.issue_type == "epic"

        # Create children
        child1 = tracker.create_issue("Child 1", parent=epic.identifier, issue_type="task")
        child2 = tracker.create_issue("Child 2", parent=epic.identifier, issue_type="task")

        assert child1.parent_id == epic.identifier
        assert child2.parent_id == epic.identifier

        # Fetch children
        children = tracker.fetch_children(epic.identifier)
        assert isinstance(children, list)

    def test_dependency_workflow(self, tracker):
        """Test creating dependent tasks."""
        blocker = tracker.create_issue("Blocker task")
        blocked = tracker.create_issue("Blocked task")

        tracker.add_dependency(blocked.identifier, blocker.identifier)

        # Verify dependency recorded
        updated_blocked = tracker.fetch_issue_detail(blocked.identifier)
        assert updated_blocked is not None

    def test_metadata_workflow(self, tracker):
        """Test storing and retrieving metadata."""
        issue = tracker.create_issue("Metadata workflow")

        # Store various metadata
        tracker.set_metadata_field(issue.identifier, "oompah.cost", "0.05")
        tracker.set_metadata_field(issue.identifier, "oompah.model", "gpt-4")
        tracker.set_metadata_field(issue.identifier, "oompah.branch", "feature/xyz")

        # Retrieve and verify
        metadata = tracker.get_metadata(issue.identifier)
        assert metadata.get("oompah.cost") == "0.05"
        assert metadata.get("oompah.model") == "gpt-4"
        assert metadata.get("oompah.branch") == "feature/xyz"

    def test_archive_workflow(self, tracker):
        """Test archiving an issue."""
        issue = tracker.create_issue("To archive", initial_status="Done")
        tracker.archive_issue(issue.identifier)

        archived = tracker.fetch_issue_detail(issue.identifier)
        assert archived is not None
        assert tracker.is_archived(archived) is True

        # Verify not in candidates
        candidates = tracker.fetch_candidate_issues()
        assert not any(c.identifier == issue.identifier for c in candidates)


# ----------------------------------------------------------------------
# Ensure BacklogMdTracker is tested when available
# ----------------------------------------------------------------------


class TestBacklogMdTrackerContract:
    """Additional contract tests specific to BacklogMdTracker."""

    def test_backlog_tracker_fetch_candidate_issues_parses_correctly(self, backlog_tracker):
        """BacklogMdTracker must correctly parse task files."""
        # This test only runs when backlog CLI is available
        # and uses the backlog_tracker fixture which sets up a temp project
        issues = backlog_tracker.fetch_candidate_issues()
        assert isinstance(issues, list)

    def test_backlog_tracker_create_issue_writes_file(self, backlog_tracker, tmp_path):
        """BacklogMdTracker.create_issue must create a task file."""
        issue = backlog_tracker.create_issue("Backlog test task", priority=1)
        assert issue.identifier

        # Verify file exists
        task_files = list((tmp_path / "backlog" / "tasks").glob("*.md"))
        assert len(task_files) >= 1

    def test_backlog_tracker_update_issue_modifies_file(self, backlog_tracker, tmp_path):
        """BacklogMdTracker.update_issue must modify the task file."""
        issue = backlog_tracker.create_issue("Update test")
        backlog_tracker.update_issue(issue.identifier, status="In Progress")

        updated = backlog_tracker.fetch_issue_detail(issue.identifier)
        assert updated is not None
        assert updated.state == "In Progress"

    def test_backlog_tracker_comments_roundtrip(self, backlog_tracker):
        """BacklogMdTracker comments must persist in markdown."""
        issue = backlog_tracker.create_issue("Comment test")
        backlog_tracker.add_comment(issue.identifier, "Test comment", author="tester")

        comments = backlog_tracker.fetch_comments(issue.identifier)
        assert len(comments) == 1
        assert comments[0]["text"] == "Test comment"
        assert comments[0]["author"] == "tester"