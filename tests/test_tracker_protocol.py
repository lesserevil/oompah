"""Tests for the tracker protocol and adapter registry."""

from __future__ import annotations

from oompah.config import ServiceConfig, validate_dispatch_config
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.tracker import ADAPTER_REGISTRY, TrackerFactory, TrackerProtocol


class TestTrackerProtocolDefinition:
    def test_protocol_is_runtime_checkable(self):
        result = isinstance(object(), TrackerProtocol)
        assert isinstance(result, bool)

    def test_protocol_has_required_methods(self):
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
            assert hasattr(TrackerProtocol, method_name)

    def test_non_tracker_does_not_satisfy_protocol(self):
        assert not isinstance(object(), TrackerProtocol)


class TestAdapterRegistry:
    def test_registry_contains_only_supported_tracker_kinds(self):
        assert set(ADAPTER_REGISTRY) == {
            "github_issues",
            "github-issues",
            "gitlab_issues",
            "gitlab-issues",
            "oompah_md",
            "oompah.md",
            "oompah",
        }

    def test_all_values_are_callable(self):
        for kind, factory in ADAPTER_REGISTRY.items():
            assert callable(factory), f"Factory for {kind!r} is not callable"

    def test_oompah_md_factory_returns_native_tracker(self, tmp_path):
        factory = ADAPTER_REGISTRY["oompah_md"]
        tracker = factory(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(tmp_path),
        )
        assert isinstance(tracker, OompahMarkdownTracker)
        assert isinstance(tracker, TrackerProtocol)

    def test_factory_type_alias_is_exported(self):
        assert TrackerFactory is not None

    def test_registry_can_be_extended(self):
        original_keys = set(ADAPTER_REGISTRY.keys())
        ADAPTER_REGISTRY["_test_adapter"] = lambda **kw: None  # type: ignore[assignment]
        try:
            assert "_test_adapter" in ADAPTER_REGISTRY
            assert original_keys.issubset(ADAPTER_REGISTRY.keys())
        finally:
            ADAPTER_REGISTRY.pop("_test_adapter", None)


class TestValidateDispatchConfigUsesRegistry:
    def test_supported_kinds_are_valid(self):
        for kind in ("github_issues", "github-issues", "oompah_md", "oompah.md", "oompah"):
            cfg = ServiceConfig(tracker_kind=kind)
            assert validate_dispatch_config(cfg) == []

    def test_unknown_kind_is_rejected(self):
        cfg = ServiceConfig(tracker_kind="unknown_tracker")
        errors = validate_dispatch_config(cfg)
        assert errors
        assert "oompah_md" in errors[0]
        assert "github_issues" in errors[0]

    def test_newly_registered_kind_becomes_valid(self):
        ADAPTER_REGISTRY["_test_kind"] = lambda **kw: None  # type: ignore[assignment]
        try:
            cfg = ServiceConfig(tracker_kind="_test_kind")
            assert validate_dispatch_config(cfg) == []
        finally:
            ADAPTER_REGISTRY.pop("_test_kind", None)
