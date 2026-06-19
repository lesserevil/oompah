"""Tests for the TrackerProtocol and ADAPTER_REGISTRY.

Verifies that:
- TrackerProtocol is correctly defined as a runtime-checkable Protocol.
- BacklogMdTracker satisfies TrackerProtocol at runtime.
- ADAPTER_REGISTRY maps the expected kind strings to callables.
- The registry factory produces a BacklogMdTracker for the 'backlog_md' kind.
- validate_dispatch_config accepts known kinds and rejects unknown ones using
  the registry, not a hard-coded comparison.
"""

from __future__ import annotations

import pytest

from oompah.tracker import (
    ADAPTER_REGISTRY,
    BacklogMdTracker,
    TrackerFactory,
    TrackerProtocol,
)
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.config import ServiceConfig, validate_dispatch_config


class TestTrackerProtocolDefinition:
    """TrackerProtocol is a runtime-checkable Protocol."""

    def test_protocol_is_runtime_checkable(self):
        """isinstance() checks against TrackerProtocol must not raise TypeError."""
        # Any object should be testable (result doesn't matter here).
        result = isinstance(object(), TrackerProtocol)
        assert isinstance(result, bool)

    def test_backlog_md_tracker_satisfies_protocol(self):
        """BacklogMdTracker must satisfy TrackerProtocol at runtime."""
        tracker = BacklogMdTracker(
            active_states=["Open"],
            terminal_states=["Done"],
        )
        assert isinstance(tracker, TrackerProtocol)

    def test_protocol_has_required_methods(self):
        """All methods in the TrackerProtocol must be present."""
        required_methods = [
            "fetch_candidate_issues",
            "fetch_all_issues",
            "fetch_all_issues_enriched",
            "fetch_issue_detail",
            "fetch_children",
            "fetch_comments",
            "fetch_issues_by_states",
            "fetch_issues_by_labels",
            "fetch_issue_states_by_ids",
            "fetch_memories",
            "create_issue",
            "update_issue",
            "close_issue",
            "reopen_issue",
            "archive_issue",
            "mark_needs_human",
            "add_comment",
            "add_label",
            "remove_label",
            "add_parent_child",
            "add_dependency",
            "fetch_attachments",
            "set_attachments",
            "get_metadata",
            "set_metadata_field",
            "is_archived",
            "invalidate_read_cache",
        ]
        for method_name in required_methods:
            assert hasattr(TrackerProtocol, method_name), (
                f"TrackerProtocol is missing expected method: {method_name}"
            )

    def test_non_tracker_does_not_satisfy_protocol(self):
        """A plain object without tracker methods must not satisfy the protocol."""
        assert not isinstance(object(), TrackerProtocol)

    def test_minimal_conforming_object_satisfies_protocol(self):
        """An object that implements all protocol methods satisfies it at runtime.

        Because Protocol runtime checks only verify method *presence* (not
        signatures), implementing stubs for every declared method is sufficient.
        """
        class _FakeTracker:
            def fetch_candidate_issues(self): ...
            def fetch_all_issues(self): ...
            def fetch_all_issues_enriched(self): ...
            def fetch_issue_detail(self, identifier): ...
            def fetch_children(self, epic_id): ...
            def fetch_comments(self, identifier): ...
            def fetch_issues_by_states(self, state_names): ...
            def fetch_issues_by_labels(self, labels, *, states=None): ...
            def fetch_issue_states_by_ids(self, issue_ids): ...
            def fetch_memories(self): ...
            def create_issue(self, title, **kwargs): ...
            def update_issue(self, identifier, **fields): ...
            def close_issue(self, identifier, *, reason=None): ...
            def reopen_issue(self, identifier): ...
            def archive_issue(self, identifier): ...
            def mark_needs_human(self, identifier, comment, author="oompah"): ...
            def add_comment(self, identifier, text, author="oompah"): ...
            def add_label(self, identifier, label): ...
            def remove_label(self, identifier, label): ...
            def add_parent_child(self, child_id, parent_id): ...
            def add_dependency(self, blocked_id, blocker_id): ...
            def fetch_attachments(self, identifier): ...
            def set_attachments(self, identifier, attachments, *, project_root=None): ...
            def get_metadata(self, identifier): ...
            def set_metadata_field(self, identifier, key, value): ...
            def is_archived(self, issue): ...
            def invalidate_read_cache(self): ...

        assert isinstance(_FakeTracker(), TrackerProtocol)


class TestAdapterRegistry:
    """ADAPTER_REGISTRY maps kind strings to TrackerFactory callables."""

    def test_registry_is_dict(self):
        assert isinstance(ADAPTER_REGISTRY, dict)

    def test_backlog_md_is_registered(self):
        assert "backlog_md" in ADAPTER_REGISTRY

    def test_oompah_md_is_registered(self):
        assert "oompah_md" in ADAPTER_REGISTRY

    def test_all_values_are_callable(self):
        for kind, factory in ADAPTER_REGISTRY.items():
            assert callable(factory), f"Factory for {kind!r} is not callable"

    def test_backlog_md_factory_returns_backlog_tracker(self):
        """The backlog_md factory must return a BacklogMdTracker instance."""
        factory = ADAPTER_REGISTRY["backlog_md"]
        tracker = factory(
            active_states=["Open"],
            terminal_states=["Done"],
        )
        assert isinstance(tracker, BacklogMdTracker)

    def test_backlog_md_factory_returns_tracker_protocol(self):
        """The backlog_md factory must return a TrackerProtocol-conforming object."""
        factory = ADAPTER_REGISTRY["backlog_md"]
        tracker = factory(
            active_states=["Open"],
            terminal_states=["Done"],
        )
        assert isinstance(tracker, TrackerProtocol)

    def test_backlog_md_factory_accepts_cwd(self, tmp_path):
        """The backlog_md factory must honour the cwd keyword argument."""
        factory = ADAPTER_REGISTRY["backlog_md"]
        tracker = factory(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(tmp_path),
        )
        assert isinstance(tracker, BacklogMdTracker)
        # The tracker's root path must reflect the supplied cwd.
        assert tracker.root_path == tmp_path.resolve()

    def test_oompah_md_factory_returns_native_tracker(self, tmp_path):
        factory = ADAPTER_REGISTRY["oompah_md"]
        tracker = factory(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(tmp_path),
        )
        assert isinstance(tracker, OompahMarkdownTracker)
        assert isinstance(tracker, TrackerProtocol)

    def test_factory_type_alias_is_callable_type(self):
        """TrackerFactory is importable and is the Callable type alias."""
        # Just a sanity check that the name is exported correctly.
        assert TrackerFactory is not None

    def test_registry_can_be_extended(self):
        """Third-party code can register new adapters without breaking existing ones."""
        original_keys = set(ADAPTER_REGISTRY.keys())
        ADAPTER_REGISTRY["_test_adapter"] = lambda **kw: None  # type: ignore[assignment]
        try:
            assert "_test_adapter" in ADAPTER_REGISTRY
            # Existing keys must still be present.
            assert original_keys.issubset(ADAPTER_REGISTRY.keys())
        finally:
            ADAPTER_REGISTRY.pop("_test_adapter", None)


class TestValidateDispatchConfigUsesRegistry:
    """validate_dispatch_config delegates tracker-kind validation to the registry."""

    def test_backlog_md_is_valid(self):
        cfg = ServiceConfig(tracker_kind="backlog_md")
        assert validate_dispatch_config(cfg) == []

    def test_github_issues_is_valid(self):
        """'github_issues' must be accepted as a registered tracker kind."""
        cfg = ServiceConfig(tracker_kind="github_issues")
        assert validate_dispatch_config(cfg) == []

    def test_oompah_md_is_valid(self):
        """'oompah_md' must be accepted as a registered tracker kind."""
        cfg = ServiceConfig(tracker_kind="oompah_md")
        assert validate_dispatch_config(cfg) == []

    def test_oompah_md_aliases_are_valid(self):
        for alias in ("oompah", "oompah.md", "OOMPAH_MD"):
            cfg = ServiceConfig(tracker_kind=alias)
            errors = validate_dispatch_config(cfg)
            assert errors == [], f"Alias {alias!r} should be valid but got: {errors}"

    def test_backlog_alias_is_valid(self):
        """'backlog' and 'backlog.md' are normalised to 'backlog_md'."""
        for alias in ("backlog", "backlog.md", "Backlog", "BACKLOG_MD"):
            cfg = ServiceConfig(tracker_kind=alias)
            errors = validate_dispatch_config(cfg)
            assert errors == [], f"Alias {alias!r} should be valid but got: {errors}"

    def test_unknown_kind_is_rejected(self):
        """Unknown tracker.kind values must produce a descriptive error."""
        for unknown in ("jira", "beans", "beads", "bd", ""):
            cfg = ServiceConfig(tracker_kind=unknown or "   ")
            errors = validate_dispatch_config(cfg)
            assert errors, f"Kind {unknown!r} should be rejected but errors is empty"

    def test_error_message_mentions_registered_adapters(self):
        """The error for an unknown kind must name the registered adapters."""
        cfg = ServiceConfig(tracker_kind="unknown_tracker")
        errors = validate_dispatch_config(cfg)
        assert any("backlog_md" in e for e in errors), (
            f"Error should mention registered adapter 'backlog_md', got: {errors}"
        )

    def test_newly_registered_kind_becomes_valid(self):
        """Registering a new adapter makes its kind valid for dispatch."""
        ADAPTER_REGISTRY["_test_kind"] = lambda **kw: None  # type: ignore[assignment]
        try:
            cfg = ServiceConfig(tracker_kind="_test_kind")
            errors = validate_dispatch_config(cfg)
            assert errors == [], (
                f"Newly registered '_test_kind' should be valid but got: {errors}"
            )
        finally:
            ADAPTER_REGISTRY.pop("_test_kind", None)

    def test_removed_kind_becomes_invalid(self):
        """Removing an adapter from the registry makes its kind invalid."""
        saved = ADAPTER_REGISTRY.pop("backlog_md")
        try:
            cfg = ServiceConfig(tracker_kind="backlog_md")
            errors = validate_dispatch_config(cfg)
            assert errors, "After removing backlog_md from registry, it should be invalid"
        finally:
            ADAPTER_REGISTRY["backlog_md"] = saved
