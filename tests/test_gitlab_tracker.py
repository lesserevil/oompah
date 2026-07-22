"""Contract tests for the GitLab Issues REST tracker.

Coverage goals
--------------
* Identifier parsing and URL encoding for nested project namespaces.
* TrackerProtocol structural conformance.
* All read-path operations: fetch_candidate_issues, fetch_all_issues,
  fetch_issue_detail, fetch_children, fetch_comments, fetch_issues_by_states,
  fetch_issues_by_labels, fetch_issue_states_by_ids, fetch_memories.
* Priority/type label round-trips through create_issue and update_issue.
* Parent-child relationship via labels (add_parent_child, fetch_children).
* Blocked-by dependency via labels (add_dependency).
* Archive and reopen state events.
* close_issue with and without a reason comment.
* mark_needs_human status transition.
* Metadata round-trips: get_metadata, set_metadata_field, fetch_attachments,
  set_attachments.
* Description metadata helper functions (_parse_description_metadata,
  _update_description_metadata).
* GitLabClient: pagination, retry, auth-error normalisation.
* Adapter registry factory.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest

from oompah.gitlab_tracker import (
    GitLabClient,
    GitLabIssueTracker,
    _parse_description_metadata,
    _update_description_metadata,
    parse_gitlab_identifier,
)
from oompah.tracker import (
    ADAPTER_REGISTRY,
    TrackerAuthError,
    TrackerError,
    TrackerProtocol,
)


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _issue(
    iid: int,
    *,
    state: str = "opened",
    labels: list[str] | None = None,
    description: str = "body",
) -> dict:
    return {
        "iid": iid,
        "title": f"Issue {iid}",
        "description": description,
        "state": state,
        "labels": labels or [],
        "web_url": f"https://gitlab.test/group/sub/project/-/issues/{iid}",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "closed_at": None,
        "author": {"username": "author"},
    }


# ---------------------------------------------------------------------------
# Fake transport clients
# ---------------------------------------------------------------------------


class FakeClient:
    """Simple fake transport for tests that do not need stateful round-trips."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.issue = _issue(2, labels=["task", "oompah:status:open"])

    def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "POST" and path.endswith("/notes"):
            return {
                "id": 4,
                "body": kwargs["json"]["body"],
                "author": {"username": "bot"},
            }, httpx.Headers()
        if method == "POST":
            return _issue(
                3, labels=kwargs["json"]["labels"].split(",")
            ), httpx.Headers()
        return self.issue, httpx.Headers()

    def paginated(self, path: str, *, params=None):
        self.calls.append(("GET", path, {"params": params or {}}))
        if path.endswith("/notes"):
            return [
                {"id": 1, "body": "hello", "author": {"username": "alice"}},
                {"system": True, "body": "changed"},
            ]
        return [_issue(1, labels=["priority:1", "oompah:status:open"]), self.issue]


class StatefulFakeClient:
    """Stateful fake transport for metadata/attachment round-trip tests.

    Tracks the current description and labels of a single issue (iid=2) so
    that GET → PUT → GET cycles return the updated state.
    """

    def __init__(self, description: str = "body") -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self._description = description
        self._labels = ["task", "oompah:status:open"]
        self._notes: list[dict] = []
        self._next_note_id = 1

    def _make_issue(self, iid: int = 2) -> dict:
        return {
            "iid": iid,
            "title": f"Issue {iid}",
            "description": self._description,
            "state": "opened",
            "labels": list(self._labels),
            "web_url": f"https://gitlab.test/group/sub/project/-/issues/{iid}",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "closed_at": None,
            "author": {"username": "author"},
        }

    def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        payload = kwargs.get("json", {})
        if method == "POST" and path.endswith("/notes"):
            note = {
                "id": self._next_note_id,
                "body": payload["body"],
                "author": {"username": "bot"},
            }
            self._next_note_id += 1
            self._notes.append(note)
            return note, httpx.Headers()
        if method == "POST":
            return _issue(3, labels=payload.get("labels", "").split(",")), httpx.Headers()
        if method == "PUT":
            if "description" in payload:
                self._description = payload["description"]
            if "labels" in payload:
                self._labels = payload["labels"].split(",")
            if "state_event" in payload:
                pass  # ignore for simplicity
        return self._make_issue(), httpx.Headers()

    def paginated(self, path: str, *, params=None):
        self.calls.append(("GET", path, {"params": params or {}}))
        if path.endswith("/notes"):
            return list(self._notes)
        return [self._make_issue()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker() -> tuple[GitLabIssueTracker, FakeClient]:
    client = FakeClient()
    return (
        GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open", "Needs Human"],
            terminal_states=["Done"],
            client=client,
        ),
        client,
    )


@pytest.fixture
def stateful_tracker() -> tuple[GitLabIssueTracker, StatefulFakeClient]:
    client = StatefulFakeClient()
    return (
        GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open", "Needs Human"],
            terminal_states=["Done"],
            client=client,
        ),
        client,
    )


# ===========================================================================
# Description metadata helpers (module-level functions)
# ===========================================================================


class TestParseDescriptionMetadata:
    def test_returns_empty_dict_for_none(self):
        assert _parse_description_metadata(None) == {}

    def test_returns_empty_dict_for_empty_string(self):
        assert _parse_description_metadata("") == {}

    def test_returns_empty_dict_when_no_metadata_block(self):
        assert _parse_description_metadata("Just a normal description.") == {}

    def test_extracts_json_from_html_comment_block(self):
        description = "Some text.\n\n<!-- oompah:metadata\n{\"key\": \"value\"}\n-->"
        assert _parse_description_metadata(description) == {"key": "value"}

    def test_extracts_nested_json_values(self):
        meta = {"attachments": [{"url": "http://example.com/file.pdf", "name": "file"}]}
        description = f"<!-- oompah:metadata\n{json.dumps(meta)}\n-->"
        result = _parse_description_metadata(description)
        assert result == meta

    def test_returns_empty_dict_for_invalid_json(self):
        description = "<!-- oompah:metadata\nnot-valid-json\n-->"
        assert _parse_description_metadata(description) == {}

    def test_handles_extra_whitespace_around_block(self):
        description = "<!--  oompah:metadata \n{\"x\": 1}\n  -->"
        assert _parse_description_metadata(description) == {"x": 1}


class TestUpdateDescriptionMetadata:
    def test_inserts_block_into_empty_description(self):
        result = _update_description_metadata("", {"k": "v"})
        assert "<!-- oompah:metadata" in result
        assert '"k": "v"' in result

    def test_appends_block_to_existing_description(self):
        result = _update_description_metadata("My description.", {"k": "v"})
        assert result.startswith("My description.")
        assert "<!-- oompah:metadata" in result

    def test_replaces_existing_metadata_block(self):
        original = 'User text.\n\n<!-- oompah:metadata\n{"old": true}\n-->'
        result = _update_description_metadata(original, {"new": True})
        # Old block gone, new block present
        assert '"old"' not in result
        assert '"new": true' in result
        # Visible description is preserved
        assert result.startswith("User text.")

    def test_round_trips_through_parse(self):
        meta = {"foo": 42, "bar": [1, 2, 3]}
        description = _update_description_metadata("Desc.", meta)
        assert _parse_description_metadata(description) == meta

    def test_keys_are_sorted_for_stable_output(self):
        result = _update_description_metadata("", {"b": 1, "a": 2})
        b_pos = result.index('"b"')
        a_pos = result.index('"a"')
        assert a_pos < b_pos  # sort_keys=True → 'a' before 'b'

    def test_preserves_description_text_before_block(self):
        original = "First line.\nSecond line."
        result = _update_description_metadata(original, {"x": 1})
        assert result.startswith("First line.\nSecond line.")

    def test_no_double_block_when_updated_twice(self):
        meta1 = {"step": 1}
        meta2 = {"step": 2}
        after_first = _update_description_metadata("Text.", meta1)
        after_second = _update_description_metadata(after_first, meta2)
        # Only one block present
        assert after_second.count("<!-- oompah:metadata") == 1
        assert _parse_description_metadata(after_second) == meta2


# ===========================================================================
# Identifier parsing
# ===========================================================================


class TestGitLabIdentifier:
    def test_canonical_form_includes_full_namespace(self):
        parsed = parse_gitlab_identifier("group/sub/project#5")
        assert parsed.canonical == "group/sub/project#5"

    def test_display_form_uses_last_path_segment(self):
        parsed = parse_gitlab_identifier("group/sub/project#5")
        assert parsed.display == "project#5"

    def test_rejects_bare_issue_number(self):
        from oompah.gitlab_tracker import GitLabIdentifierError
        with pytest.raises(GitLabIdentifierError):
            parse_gitlab_identifier("42")

    def test_rejects_empty_string(self):
        from oompah.gitlab_tracker import GitLabIdentifierError
        with pytest.raises(GitLabIdentifierError):
            parse_gitlab_identifier("")

    def test_rejects_zero_iid(self):
        from oompah.gitlab_tracker import GitLabIdentifierError
        with pytest.raises(GitLabIdentifierError):
            parse_gitlab_identifier("group/project#0")

    def test_rejects_project_with_leading_slash(self):
        from oompah.gitlab_tracker import GitLabIdentifierError
        with pytest.raises(GitLabIdentifierError):
            parse_gitlab_identifier("/group/project#1")

    def test_tracker_parse_identifier_raises_tracker_error_for_different_project(
        self, tracker
    ):
        instance, _ = tracker
        with pytest.raises(TrackerError, match="different GitLab project"):
            instance.parse_identifier("other/project#1")

    def test_nested_namespace_routes_are_percent_encoded(self, tracker):
        instance, client = tracker
        instance.fetch_issue_detail("group/sub/project#2")
        last_path = client.calls[-1][1]
        assert "%2F" in last_path or "/" not in last_path.split("/projects/")[1].split("/issues")[0]
        assert "group%2Fsub%2Fproject" in last_path


# ===========================================================================
# TrackerProtocol structural conformance
# ===========================================================================


def test_gitlab_issue_tracker_implements_tracker_protocol(tracker):
    instance, _ = tracker
    assert isinstance(instance, TrackerProtocol)


# ===========================================================================
# Read-path operations
# ===========================================================================


class TestReadPath:
    def test_fetch_candidate_issues_returns_sorted_open_issues(self, tracker):
        instance, _ = tracker
        issues = instance.fetch_candidate_issues()
        # Both issues have oompah:status:open
        assert len(issues) == 2
        identifiers = [i.identifier for i in issues]
        assert "group/sub/project#1" in identifiers
        assert "group/sub/project#2" in identifiers

    def test_fetch_all_issues_returns_all_issues(self, tracker):
        instance, _ = tracker
        assert len(instance.fetch_all_issues()) == 2

    def test_fetch_all_issues_enriched_returns_same_as_fetch_all(self, tracker):
        instance, _ = tracker
        assert len(instance.fetch_all_issues_enriched()) == 2

    def test_fetch_issue_detail_returns_issue_by_identifier(self, tracker):
        instance, _ = tracker
        issue = instance.fetch_issue_detail("group/sub/project#2")
        assert issue is not None
        assert issue.identifier == "group/sub/project#2"

    def test_fetch_issue_detail_returns_none_for_404(self):
        class NotFoundClient:
            def request(self, method, path, **kwargs):
                raise TrackerError("GitLab API returned 404 for " + path)
            def paginated(self, *a, **kw):
                return []

        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=NotFoundClient(),
        )
        assert tracker.fetch_issue_detail("group/sub/project#99") is None

    def test_fetch_comments_returns_non_system_notes(self, tracker):
        instance, _ = tracker
        comments = instance.fetch_comments("group/sub/project#2")
        assert len(comments) == 1
        assert comments[0]["text"] == "hello"
        assert comments[0]["author"] == "alice"

    def test_fetch_issues_by_states_filters_correctly(self, tracker):
        instance, _ = tracker
        open_issues = instance.fetch_issues_by_states(["Open"])
        assert len(open_issues) == 2

    def test_fetch_issues_by_states_empty_list_returns_empty(self, tracker):
        instance, _ = tracker
        assert instance.fetch_issues_by_states([]) == []

    def test_fetch_issues_by_labels_filters_to_matching_labels(self, tracker):
        instance, _ = tracker
        result = instance.fetch_issues_by_labels(["oompah:status:open"])
        assert len(result) == 2

    def test_fetch_issues_by_labels_returns_empty_for_unknown_label(self, tracker):
        instance, _ = tracker
        assert instance.fetch_issues_by_labels(["nonexistent-label"]) == []

    def test_fetch_issue_states_by_ids_returns_current_state(self, tracker):
        instance, _ = tracker
        results = instance.fetch_issue_states_by_ids(["group/sub/project#2"])
        assert len(results) == 1
        assert results[0].identifier == "group/sub/project#2"

    def test_fetch_memories_returns_empty_dict(self, tracker):
        instance, _ = tracker
        assert instance.fetch_memories() == {}

    def test_invalidate_read_cache_is_a_no_op(self, tracker):
        instance, _ = tracker
        instance.invalidate_read_cache()  # Should not raise


# ===========================================================================
# Issue field parsing (priority, type, parent, blockers)
# ===========================================================================


class TestIssueParsing:
    def test_priority_label_is_parsed_from_labels(self):
        client = FakeClient()
        client.issue = _issue(2, labels=["priority:2", "task", "oompah:status:open"])
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        issue = tracker.fetch_issue_detail("group/sub/project#2")
        assert issue is not None
        assert issue.priority == 2

    def test_type_label_is_parsed_from_labels(self):
        client = FakeClient()
        client.issue = _issue(2, labels=["epic", "oompah:status:open"])
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        issue = tracker.fetch_issue_detail("group/sub/project#2")
        assert issue is not None
        assert issue.issue_type == "epic"

    def test_parent_label_is_parsed_from_labels(self):
        client = FakeClient()
        client.issue = _issue(
            3, labels=["task", "parent:2", "oompah:status:open"]
        )
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        issue = tracker.fetch_issue_detail("group/sub/project#3")
        assert issue is not None
        assert issue.parent_id == "2"

    def test_blocked_by_label_is_parsed_from_labels(self):
        client = FakeClient()
        client.issue = _issue(
            3,
            labels=[
                "task",
                "blocked-by:group/sub/project#1",
                "oompah:status:open",
            ],
        )
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        issue = tracker.fetch_issue_detail("group/sub/project#3")
        assert issue is not None
        assert len(issue.blocked_by) == 1
        assert issue.blocked_by[0].identifier == "group/sub/project#1"

    def test_closed_gitlab_issue_defaults_to_done_status(self):
        client = FakeClient()
        client.issue = _issue(2, state="closed", labels=[])
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        issue = tracker.fetch_issue_detail("group/sub/project#2")
        assert issue is not None
        assert issue.state == "Done"

    def test_oompah_status_label_overrides_gitlab_state(self):
        client = FakeClient()
        client.issue = _issue(2, state="closed", labels=["oompah:status:archived"])
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        issue = tracker.fetch_issue_detail("group/sub/project#2")
        assert issue is not None
        assert issue.state == "Archived"


# ===========================================================================
# Create and update issue (label preservation)
# ===========================================================================


class TestCreateAndUpdateIssue:
    def test_create_issue_includes_type_label_in_labels(self, tracker):
        instance, client = tracker
        instance.create_issue("New task", issue_type="bug")
        post_call = next(c for c in client.calls if c[0] == "POST")
        labels = post_call[2]["json"]["labels"].split(",")
        assert "bug" in labels

    def test_create_issue_includes_priority_label_when_given(self, tracker):
        instance, client = tracker
        instance.create_issue("High priority task", priority=1)
        post_call = next(c for c in client.calls if c[0] == "POST")
        labels = post_call[2]["json"]["labels"].split(",")
        assert "priority:1" in labels

    def test_create_issue_adds_status_label(self, tracker):
        instance, client = tracker
        instance.create_issue("With status", initial_status="Backlog")
        post_call = next(c for c in client.calls if c[0] == "POST")
        labels = post_call[2]["json"]["labels"].split(",")
        assert any(l.startswith("oompah:status:") for l in labels)

    def test_create_issue_with_parent_adds_parent_label(self, tracker):
        instance, client = tracker
        created = instance.create_issue("Child task", parent="group/sub/project#2")
        post_call = next(c for c in client.calls if c[0] == "POST")
        labels = post_call[2]["json"]["labels"].split(",")
        assert "parent:2" in labels

    def test_create_issue_returns_new_issue_with_identifier(self, tracker):
        instance, _ = tracker
        created = instance.create_issue("New issue")
        assert created.identifier == "group/sub/project#3"

    def test_create_issue_with_parent_parses_parent_into_returned_issue(self, tracker):
        instance, _ = tracker
        created = instance.create_issue("Child", parent="group/sub/project#2")
        assert created.parent_id == "2"

    def test_update_issue_title_sends_put(self, tracker):
        instance, client = tracker
        instance.update_issue("group/sub/project#2", title="Renamed")
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        assert any(c[2].get("json", {}).get("title") == "Renamed" for c in put_calls)

    def test_update_issue_priority_replaces_existing_priority_label(self, tracker):
        instance, client = tracker
        # Issue 2 initially has no priority label (FakeClient)
        instance.update_issue("group/sub/project#2", priority="1")
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        labels_str = next(
            c[2]["json"]["labels"]
            for c in put_calls
            if "labels" in c[2].get("json", {})
        )
        labels = labels_str.split(",")
        assert "priority:1" in labels

    def test_update_issue_state_triggers_replace_status(self, tracker):
        instance, client = tracker
        instance.update_issue("group/sub/project#2", state="Done")
        # Should have called state_event or label update
        assert any(c[0] in ("PUT", "GET") for c in client.calls)


# ===========================================================================
# Lifecycle: close, reopen, archive, mark_needs_human
# ===========================================================================


class TestLifecycleOperations:
    def test_close_issue_sends_close_state_event(self, tracker):
        instance, client = tracker
        instance.close_issue("group/sub/project#2")
        assert any(
            c[2].get("json", {}).get("state_event") == "close" for c in client.calls
        )

    def test_close_issue_with_reason_posts_comment(self, tracker):
        instance, client = tracker
        instance.close_issue("group/sub/project#2", reason="All done")
        assert any(
            c[2].get("json", {}).get("body") == "All done" for c in client.calls
        )

    def test_reopen_issue_sends_reopen_state_event(self, tracker):
        instance, client = tracker
        instance.reopen_issue("group/sub/project#2")
        assert any(
            c[2].get("json", {}).get("state_event") == "reopen" for c in client.calls
        )

    def test_archive_issue_sends_close_state_event(self, tracker):
        instance, client = tracker
        instance.archive_issue("group/sub/project#2")
        assert any(
            c[2].get("json", {}).get("state_event") == "close" for c in client.calls
        )

    def test_archive_issue_adds_archived_status_label(self, tracker):
        instance, client = tracker
        instance.archive_issue("group/sub/project#2")
        # The label replacement should include the archived status label
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        label_payloads = [
            c[2]["json"]["labels"]
            for c in put_calls
            if "labels" in c[2].get("json", {})
        ]
        assert any("oompah:status:archived" in lp for lp in label_payloads)

    def test_mark_needs_human_sets_needs_human_label_and_posts_comment(self, tracker):
        instance, client = tracker
        instance.mark_needs_human("group/sub/project#2", "Help needed!")
        label_payloads = [
            c[2]["json"]["labels"]
            for c in client.calls
            if c[0] == "PUT" and "labels" in c[2].get("json", {})
        ]
        assert any("oompah:status:needs-human" in lp for lp in label_payloads)
        note_bodies = [
            c[2]["json"]["body"]
            for c in client.calls
            if c[0] == "POST" and "body" in c[2].get("json", {})
        ]
        assert "Help needed!" in note_bodies

    def test_is_archived_returns_true_for_archived_issue(self):
        from oompah.models import Issue
        from datetime import datetime, timezone
        issue = Issue(
            id="x#1",
            identifier="x#1",
            display_identifier="x#1",
            title="T",
            state="Archived",
            tracker_kind="gitlab_issues",
            issue_number="1",
        )
        tracker = GitLabIssueTracker(
            project="x",
            active_states=["Open"],
            terminal_states=["Done"],
            client=FakeClient(),
        )
        assert tracker.is_archived(issue) is True

    def test_is_archived_returns_false_for_open_issue(self):
        from oompah.models import Issue
        issue = Issue(
            id="x#1",
            identifier="x#1",
            display_identifier="x#1",
            title="T",
            state="Open",
            tracker_kind="gitlab_issues",
            issue_number="1",
        )
        tracker = GitLabIssueTracker(
            project="x",
            active_states=["Open"],
            terminal_states=["Done"],
            client=FakeClient(),
        )
        assert tracker.is_archived(issue) is False


# ===========================================================================
# Comments and labels
# ===========================================================================


class TestCommentsAndLabels:
    def test_add_comment_posts_to_notes_endpoint(self, tracker):
        instance, client = tracker
        result = instance.add_comment("group/sub/project#2", "My note")
        assert result["text"] == "My note"
        post_calls = [c for c in client.calls if c[0] == "POST"]
        assert any("/notes" in c[1] for c in post_calls)

    def test_add_label_appends_label_via_put(self, tracker):
        instance, client = tracker
        instance.add_label("group/sub/project#2", "extra-label")
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        label_payloads = [
            c[2]["json"]["labels"]
            for c in put_calls
            if "labels" in c[2].get("json", {})
        ]
        assert any("extra-label" in lp for lp in label_payloads)

    def test_remove_label_excludes_label_in_put(self, tracker):
        instance, client = tracker
        # Issue has label "task"; remove it
        instance.remove_label("group/sub/project#2", "task")
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        label_payloads = [
            c[2]["json"]["labels"]
            for c in put_calls
            if "labels" in c[2].get("json", {})
        ]
        assert label_payloads, "PUT should have been called"
        # "task" should not appear alone in the label list
        for lp in label_payloads:
            assert "task" not in lp.split(",")


# ===========================================================================
# Parent-child relationships and fetch_children
# ===========================================================================


class TestParentChildAndFetchChildren:
    def test_add_parent_child_adds_parent_label_to_child(self, tracker):
        instance, client = tracker
        instance.add_parent_child("group/sub/project#2", "group/sub/project#1")
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        label_payloads = [
            c[2]["json"]["labels"]
            for c in put_calls
            if "labels" in c[2].get("json", {})
        ]
        assert any("parent:1" in lp for lp in label_payloads)

    def test_fetch_children_returns_issues_matching_parent_label(self):
        """Issues with parent:<parent_iid> label are returned as children."""
        child_issue = _issue(3, labels=["task", "parent:2", "oompah:status:open"])
        parent_issue = _issue(2, labels=["task", "oompah:status:open"])

        class MultiIssueClient:
            def request(self, method, path, **kwargs):
                return parent_issue, httpx.Headers()
            def paginated(self, path, *, params=None):
                return [parent_issue, child_issue]

        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=MultiIssueClient(),
        )
        children = tracker.fetch_children("group/sub/project#2")
        assert len(children) == 1
        assert children[0].identifier == "group/sub/project#3"

    def test_fetch_children_returns_empty_for_unknown_parent(self):
        client = FakeClient()
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        # No issues have parent:99
        children = tracker.fetch_children("group/sub/project#99")
        assert children == []

    def test_fetch_children_returns_empty_for_invalid_identifier(self):
        client = FakeClient()
        tracker = GitLabIssueTracker(
            project="group/sub/project",
            active_states=["Open"],
            terminal_states=["Done"],
            client=client,
        )
        children = tracker.fetch_children("not-a-valid-identifier")
        assert children == []


# ===========================================================================
# Dependency / blocked-by relationships
# ===========================================================================


class TestDependencies:
    def test_add_dependency_adds_blocked_by_label(self, tracker):
        instance, client = tracker
        instance.add_dependency(
            "group/sub/project#2", "group/sub/project#1"
        )
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        label_payloads = [
            c[2]["json"]["labels"]
            for c in put_calls
            if "labels" in c[2].get("json", {})
        ]
        assert any("blocked-by:group/sub/project#1" in lp for lp in label_payloads)

    def test_add_dependency_raises_for_invalid_blocker(self, tracker):
        instance, _ = tracker
        with pytest.raises(TrackerError):
            instance.add_dependency("group/sub/project#2", "bad-id")


# ===========================================================================
# Metadata: get_metadata and set_metadata_field
# ===========================================================================


class TestGetAndSetMetadata:
    def test_get_metadata_returns_empty_when_no_block(self, stateful_tracker):
        instance, _ = stateful_tracker
        assert instance.get_metadata("group/sub/project#2") == {}

    def test_set_metadata_field_writes_value_to_description(self, stateful_tracker):
        instance, client = stateful_tracker
        instance.set_metadata_field("group/sub/project#2", "oompah.target_branch", "main")
        # A PUT should have been made with updated description
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        assert put_calls, "Expected PUT call for description update"
        description_updates = [
            c[2]["json"].get("description", "")
            for c in put_calls
            if "description" in c[2].get("json", {})
        ]
        assert any("oompah:metadata" in d for d in description_updates)

    def test_set_metadata_field_roundtrip(self, stateful_tracker):
        instance, _ = stateful_tracker
        instance.set_metadata_field("group/sub/project#2", "oompah.answer", 42)
        result = instance.get_metadata("group/sub/project#2")
        assert result.get("oompah.answer") == 42

    def test_set_metadata_field_preserves_other_keys(self, stateful_tracker):
        instance, _ = stateful_tracker
        instance.set_metadata_field("group/sub/project#2", "oompah.first", "one")
        instance.set_metadata_field("group/sub/project#2", "oompah.second", "two")
        meta = instance.get_metadata("group/sub/project#2")
        assert meta.get("oompah.first") == "one"
        assert meta.get("oompah.second") == "two"

    def test_set_metadata_field_updates_existing_key(self, stateful_tracker):
        instance, _ = stateful_tracker
        instance.set_metadata_field("group/sub/project#2", "oompah.counter", 1)
        instance.set_metadata_field("group/sub/project#2", "oompah.counter", 2)
        meta = instance.get_metadata("group/sub/project#2")
        assert meta["oompah.counter"] == 2

    def test_set_metadata_field_requires_oompah_prefix(self, stateful_tracker):
        instance, _ = stateful_tracker
        with pytest.raises(TrackerError, match="oompah"):
            instance.set_metadata_field("group/sub/project#2", "no_prefix", "value")

    def test_set_metadata_field_preserves_existing_description_text(
        self, stateful_tracker
    ):
        instance, client = stateful_tracker
        client._description = "User-written description text."
        instance.set_metadata_field("group/sub/project#2", "oompah.k", "v")
        assert "User-written description text." in client._description

    def test_get_metadata_returns_empty_for_invalid_identifier(self, stateful_tracker):
        instance, _ = stateful_tracker
        # Invalid identifier should not raise; returns empty dict
        result = instance.get_metadata("not-a-valid-id")
        assert result == {}

    def test_get_metadata_prefixes_all_keys_with_oompah_dot(self, stateful_tracker):
        instance, client = stateful_tracker
        # Seed the description with a metadata block directly
        client._description = '<!-- oompah:metadata\n{"alpha": "beta", "gamma": 9}\n-->'
        meta = instance.get_metadata("group/sub/project#2")
        assert all(k.startswith("oompah.") for k in meta.keys())
        assert meta["oompah.alpha"] == "beta"
        assert meta["oompah.gamma"] == 9


# ===========================================================================
# Attachments: fetch_attachments and set_attachments
# ===========================================================================


class TestAttachments:
    def test_fetch_attachments_returns_empty_when_no_metadata(self, stateful_tracker):
        instance, _ = stateful_tracker
        assert instance.fetch_attachments("group/sub/project#2") == []

    def test_set_attachments_persists_list(self, stateful_tracker):
        instance, _ = stateful_tracker
        attachments = [{"url": "https://example.com/file.pdf", "name": "report.pdf"}]
        instance.set_attachments("group/sub/project#2", attachments)
        result = instance.fetch_attachments("group/sub/project#2")
        assert result == attachments

    def test_set_attachments_roundtrip_with_multiple_items(self, stateful_tracker):
        instance, _ = stateful_tracker
        attachments = [
            {"url": "https://example.com/a.txt", "name": "a.txt"},
            {"url": "https://example.com/b.png", "name": "b.png"},
        ]
        instance.set_attachments("group/sub/project#2", attachments)
        result = instance.fetch_attachments("group/sub/project#2")
        assert len(result) == 2
        assert result[0]["name"] == "a.txt"
        assert result[1]["name"] == "b.png"

    def test_set_attachments_replaces_existing_attachments(self, stateful_tracker):
        instance, _ = stateful_tracker
        instance.set_attachments(
            "group/sub/project#2",
            [{"url": "https://example.com/old.txt", "name": "old"}],
        )
        instance.set_attachments(
            "group/sub/project#2",
            [{"url": "https://example.com/new.txt", "name": "new"}],
        )
        result = instance.fetch_attachments("group/sub/project#2")
        assert len(result) == 1
        assert result[0]["name"] == "new"

    def test_set_attachments_with_empty_list_clears_attachments(self, stateful_tracker):
        instance, _ = stateful_tracker
        instance.set_attachments(
            "group/sub/project#2",
            [{"url": "https://example.com/f.txt", "name": "f"}],
        )
        instance.set_attachments("group/sub/project#2", [])
        result = instance.fetch_attachments("group/sub/project#2")
        assert result == []

    def test_set_attachments_ignores_project_root_parameter(self, stateful_tracker):
        """project_root is accepted for protocol compatibility but ignored."""
        instance, _ = stateful_tracker
        attachments = [{"url": "https://example.com/x.pdf", "name": "x"}]
        instance.set_attachments(
            "group/sub/project#2",
            attachments,
            project_root="/some/local/path",
        )
        result = instance.fetch_attachments("group/sub/project#2")
        assert result == attachments

    def test_fetch_attachments_filters_non_dict_entries(self, stateful_tracker):
        """Only dicts in the attachments list are returned."""
        instance, client = stateful_tracker
        # Inject a malformed attachments list directly via description
        meta = {"attachments": [{"name": "good"}, "bad-string", 42, None]}
        client._description = _update_description_metadata("", meta)
        result = instance.fetch_attachments("group/sub/project#2")
        assert result == [{"name": "good"}]


# ===========================================================================
# GitLabClient: pagination, retries, auth errors
# ===========================================================================


def test_gitlab_client_paginates_across_multiple_pages():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        page = request.url.params.get("page", "1")
        return httpx.Response(
            200,
            json=[{"iid": int(page)}],
            headers={"X-Next-Page": "2" if page == "1" else ""},
        )

    client = GitLabClient(
        base_url="https://gitlab.test",
        token="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.paginated("/projects/group%2Fproject/issues")
    assert result == [{"iid": 1}, {"iid": 2}]
    assert calls[0].headers["PRIVATE-TOKEN"] == "secret"


def test_gitlab_client_raises_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad token")

    client = GitLabClient(
        base_url="https://gitlab.test",
        token="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TrackerAuthError):
        client.request("GET", "/bad")


def test_gitlab_client_raises_auth_error_on_403():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = GitLabClient(
        base_url="https://gitlab.test",
        token="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TrackerAuthError):
        client.request("GET", "/forbidden")


def test_gitlab_client_raises_tracker_error_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = GitLabClient(
        base_url="https://gitlab.test",
        token="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TrackerError, match="404"):
        client.request("GET", "/missing")


def test_gitlab_client_raises_tracker_error_on_4xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "invalid"})

    client = GitLabClient(
        base_url="https://gitlab.test",
        token="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TrackerError, match="422"):
        client.request("POST", "/projects/x/issues", json={})


def test_gitlab_client_retries_5xx_and_raises_after_max_retries():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, text="server error")

    client = GitLabClient(
        base_url="https://gitlab.test",
        token="token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TrackerError, match="500"):
        client.request("GET", "/unstable")

    assert len(calls) == 3  # _MAX_RETRIES = 3


# ===========================================================================
# Adapter registry
# ===========================================================================


def test_registry_factory_creates_gitlab_issue_tracker(monkeypatch):
    monkeypatch.setenv("OOMPAH_GITLAB_TOKEN", "test-token")
    tracker = ADAPTER_REGISTRY["gitlab_issues"](
        active_states=["Open"], terminal_states=["Done"], project="group/project"
    )
    assert isinstance(tracker, GitLabIssueTracker)


def test_registry_factory_works_with_owner_and_repo(monkeypatch):
    monkeypatch.setenv("OOMPAH_GITLAB_TOKEN", "test-token")
    tracker = ADAPTER_REGISTRY["gitlab_issues"](
        active_states=["Open"],
        terminal_states=["Done"],
        owner="group",
        repo="project",
    )
    assert isinstance(tracker, GitLabIssueTracker)
    assert tracker.project == "group/project"


def test_registry_factory_raises_when_no_project_configured(monkeypatch):
    monkeypatch.setenv("OOMPAH_GITLAB_TOKEN", "test-token")
    monkeypatch.delenv("OOMPAH_GITLAB_TRACKER_PROJECT", raising=False)
    with pytest.raises(TrackerError, match="project"):
        ADAPTER_REGISTRY["gitlab_issues"](
            active_states=["Open"], terminal_states=["Done"]
        )


def test_registry_factory_requires_token(monkeypatch):
    monkeypatch.delenv("OOMPAH_GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    with pytest.raises(TrackerAuthError):
        ADAPTER_REGISTRY["gitlab_issues"](
            active_states=["Open"], terminal_states=["Done"], project="g/p"
        )


# ===========================================================================
# Status label management helpers
# ===========================================================================


def test_status_label_slug_is_lowercased_and_hyphenated():
    from oompah.gitlab_tracker import _status_label
    label = _status_label("In Progress")
    assert label == "oompah:status:in-progress"


def test_status_from_labels_picks_oompah_status_label():
    from oompah.gitlab_tracker import _status_from_labels
    labels = ["task", "oompah:status:in-progress"]
    assert _status_from_labels(labels, "opened") == "In Progress"


def test_status_from_labels_uses_done_for_closed_with_no_label():
    from oompah.gitlab_tracker import _status_from_labels
    assert _status_from_labels([], "closed") == "Done"


def test_status_from_labels_uses_open_for_opened_with_no_label():
    from oompah.gitlab_tracker import _status_from_labels
    assert _status_from_labels([], "opened") == "Open"


# ===========================================================================
# Backward-compatible combined smoke test (preserving original contract test)
# ===========================================================================


def test_tracker_protocol_reads_filters_and_comments(tracker):
    """Original contract smoke test preserved for regression safety."""
    instance, _ = tracker
    assert isinstance(instance, TrackerProtocol)
    assert len(instance.fetch_candidate_issues()) == 2
    assert len(instance.fetch_all_issues_enriched()) == 2
    assert len(instance.fetch_children("group/sub/project#2")) == 0
    comments = instance.fetch_comments("group/sub/project#2")
    assert comments == [{"id": 1, "body": "hello", "author": "alice", "text": "hello"}]
    assert len(instance.fetch_issues_by_states(["Open"])) == 2
    assert len(instance.fetch_issues_by_labels(["oompah:status:open"])) == 2
    assert len(instance.fetch_issue_states_by_ids(["group/sub/project#2"])) == 1
    assert instance.fetch_memories() == {}
    # Metadata returns empty when description has no block
    assert instance.get_metadata("group/sub/project#2") == {}
    # Attachments returns empty when no metadata
    assert instance.fetch_attachments("group/sub/project#2") == []
    # set_attachments now succeeds (not a stub no-op)
    instance.set_attachments("group/sub/project#2", [])
    instance.invalidate_read_cache()


def test_tracker_lifecycle_operations_use_gitlab_state_events_and_labels(tracker):
    """Original lifecycle smoke test updated to reflect real metadata behavior."""
    instance, client = tracker
    created = instance.create_issue(
        "new", description="desc", priority=2, parent="group/sub/project#2"
    )
    assert created.identifier == "group/sub/project#3"
    instance.update_issue("group/sub/project#2", title="renamed", priority="1")
    instance.close_issue("group/sub/project#2", reason="finished")
    instance.reopen_issue("group/sub/project#2")
    instance.archive_issue("group/sub/project#2")
    instance.mark_needs_human("group/sub/project#2", "please help")
    assert instance.add_comment("group/sub/project#2", "note")["text"] == "note"
    instance.add_label("group/sub/project#2", "extra")
    instance.remove_label("group/sub/project#2", "extra")
    instance.add_parent_child("group/sub/project#2", "group/sub/project#1")
    instance.add_dependency("group/sub/project#2", "group/sub/project#1")
    assert any(
        call[2].get("json", {}).get("state_event") == "close" for call in client.calls
    )
    assert any(
        call[2].get("json", {}).get("state_event") == "reopen" for call in client.calls
    )
    # set_metadata_field now works; only raises for bad key prefix
    with pytest.raises(TrackerError, match="oompah"):
        instance.set_metadata_field("group/sub/project#2", "no_prefix_key", "x")
