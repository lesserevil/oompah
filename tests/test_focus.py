"""Tests for oompah.focus."""

import json
import os

import pytest

from oompah.focus import (
    BUILTIN_FOCI,
    DEFAULT_FOCUS,
    Focus,
    FocusSuggestion,
    _extract_work_keywords,
    _generate_focus_rules,
    _text_matches,
    _work_matches_focus,
    analyze_completed_issue,
    load_foci,
    save_foci,
    score_focus,
    select_focus,
)
from oompah.models import Issue


def _make_issue(**kwargs):
    defaults = dict(id="1", identifier="beads-001", title="Test issue", state="open")
    defaults.update(kwargs)
    return Issue(**defaults)


class TestTextMatches:
    def test_basic_match(self):
        assert _text_matches("fix the bug", ["bug"]) == 1

    def test_multiple_matches(self):
        assert _text_matches("fix the bug and the error", ["bug", "error"]) == 2

    def test_no_match(self):
        assert _text_matches("hello world", ["bug"]) == 0

    def test_case_insensitive(self):
        assert _text_matches("Fix the BUG", ["bug"]) == 1

    def test_word_boundary(self):
        # "form" should NOT match "performance"
        assert _text_matches("improve performance", ["form"]) == 0

    def test_word_boundary_exact(self):
        assert _text_matches("fill out the form", ["form"]) == 1

    def test_empty_text(self):
        assert _text_matches("", ["bug"]) == 0

    def test_empty_keywords(self):
        assert _text_matches("some text", []) == 0


class TestScoreFocus:
    def test_keyword_match(self):
        focus = Focus(name="bugfix", role="", description="", keywords=["bug", "crash"])
        issue = _make_issue(title="Fix a crash in the parser")
        score = score_focus(focus, issue)
        assert score > 0

    def test_issue_type_match(self):
        focus = Focus(name="bugfix", role="", description="", issue_types=["bug"])
        issue = _make_issue(issue_type="bug")
        score = score_focus(focus, issue)
        assert score >= 50

    def test_label_match(self):
        focus = Focus(name="frontend", role="", description="", labels=["ui"])
        issue = _make_issue(labels=["ui", "urgent"])
        score = score_focus(focus, issue)
        assert score >= 30

    def test_no_match_returns_zero(self):
        focus = Focus(name="security", role="", description="", keywords=["xss", "injection"])
        issue = _make_issue(title="Add unit tests for the math module")
        score = score_focus(focus, issue)
        assert score == 0

    def test_priority_only_added_when_score_positive(self):
        focus = Focus(name="sec", role="", description="", keywords=["unique_keyword_xyz"], priority=15)
        issue = _make_issue(title="unrelated work")
        score = score_focus(focus, issue)
        assert score == 0  # priority should NOT be added when no matches


class TestSelectFocus:
    def test_selects_best_match(self):
        foci = [
            Focus(name="bugfix", role="Bug Fixer", description="", keywords=["bug", "crash"], status="active"),
            Focus(name="feature", role="Feature Dev", description="", keywords=["feature", "add"], status="active"),
        ]
        issue = _make_issue(title="Fix a crash in the login flow")
        focus = select_focus(issue, foci)
        assert focus.name == "bugfix"

    def test_returns_default_when_no_match(self):
        foci = [
            Focus(name="bugfix", role="", description="", keywords=["crash"], status="active"),
        ]
        issue = _make_issue(title="Update the README")
        focus = select_focus(issue, foci)
        assert focus.name == DEFAULT_FOCUS.name

    def test_ignores_inactive_foci(self):
        foci = [
            Focus(name="bugfix", role="", description="", keywords=["bug"], status="inactive"),
        ]
        issue = _make_issue(title="Fix a bug")
        focus = select_focus(issue, foci)
        assert focus.name == DEFAULT_FOCUS.name

    def test_ignores_proposed_foci(self):
        foci = [
            Focus(name="bugfix", role="", description="", keywords=["bug"], status="proposed"),
        ]
        issue = _make_issue(title="Fix a bug")
        focus = select_focus(issue, foci)
        assert focus.name == DEFAULT_FOCUS.name

    def test_merge_conflict_focus_selected_by_label(self):
        issue = _make_issue(title="Some feature work", labels=["merge-conflict"])
        focus = select_focus(issue)
        assert focus.name == "merge_conflict"

    def test_merge_conflict_focus_high_priority(self):
        """Merge conflict focus should win over other matches."""
        issue = _make_issue(
            title="Fix a bug in the login flow",
            labels=["merge-conflict"],
            issue_type="bug",
        )
        focus = select_focus(issue)
        assert focus.name == "merge_conflict"


class TestFocusRender:
    def test_render_contains_role(self):
        focus = Focus(
            name="bugfix", role="Bug Investigator",
            description="Find and fix bugs.",
            must_do=["Reproduce the bug"],
            must_not_do=["Refactor unrelated code"],
        )
        text = focus.render()
        assert "Bug Investigator" in text
        assert "Find and fix bugs." in text
        assert "Reproduce the bug" in text
        assert "Refactor unrelated code" in text
        assert "### You MUST:" in text
        assert "### You must NOT:" in text


class TestFocusSerialization:
    def test_round_trip(self):
        original = Focus(
            name="test", role="Tester", description="Write tests",
            must_do=["Cover edge cases"], must_not_do=["Skip tests"],
            keywords=["test", "spec"], issue_types=["task"],
            labels=["testing"], priority=5, status="active",
        )
        restored = Focus.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.role == original.role
        assert restored.keywords == original.keywords
        assert restored.status == original.status
        assert restored.priority == original.priority


class TestLoadSaveFoci:
    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "foci.json")
        foci = [
            Focus(name="custom", role="Custom", description="Custom focus",
                  keywords=["custom"], status="active"),
        ]
        save_foci(foci, path)
        loaded = load_foci(path)
        custom = [f for f in loaded if f.name == "custom"]
        assert len(custom) == 1
        assert custom[0].role == "Custom"

    def test_user_foci_override_builtins(self, tmp_path):
        path = str(tmp_path / "foci.json")
        # Override the "bugfix" builtin
        custom_bugfix = Focus(
            name="bugfix", role="Custom Bug Fixer", description="My custom bugfix",
            keywords=["bug"], status="active",
        )
        save_foci([custom_bugfix], path)
        loaded = load_foci(path)
        bugfix = [f for f in loaded if f.name == "bugfix"]
        assert len(bugfix) == 1
        assert bugfix[0].role == "Custom Bug Fixer"

    def test_load_nonexistent_returns_builtins(self):
        loaded = load_foci("/nonexistent/foci.json")
        assert len(loaded) == len(BUILTIN_FOCI)


class TestExtractWorkKeywords:
    def test_extracts_from_title_and_comments(self):
        keywords = _extract_work_keywords(
            "Fix database migration",
            "The migration script fails on PostgreSQL",
            [{"text": "Found the issue in the migration runner"}],
        )
        assert "migration" in keywords
        assert "database" in keywords

    def test_skips_system_comments(self):
        keywords = _extract_work_keywords(
            "Test issue",
            None,
            [
                {"text": "Agent dispatched with profile quick"},
                {"text": "Focus: bugfix"},
                {"text": "The actual work comment about caching"},
            ],
        )
        # System comments should be skipped
        assert "dispatched" not in keywords

    def test_stops_words_excluded(self):
        keywords = _extract_work_keywords("the quick brown fox", None, [])
        assert "the" not in keywords


class TestWorkMatchesFocus:
    def test_good_match(self):
        focus = Focus(name="test", role="", description="", keywords=["bug", "crash", "error"])
        score = _work_matches_focus(focus, ["bug", "crash", "other"])
        assert score > 0.5

    def test_no_match(self):
        focus = Focus(name="test", role="", description="", keywords=["deploy", "docker"])
        score = _work_matches_focus(focus, ["database", "migration"])
        assert score == 0.0


class TestGenerateFocusRules:
    def test_domain_match_produces_rules(self):
        issue = _make_issue(title="Add caching layer", issue_type="task")
        desc, must_do, must_not_do = _generate_focus_rules(
            ["cache", "redis", "ttl"], ["cache", "redis", "ttl", "invalidation"], issue,
        )
        assert "caching" in desc.lower() or "cache" in desc.lower()
        assert len(must_do) > len(["base1", "base2", "base3"])  # more than baseline
        assert len(must_not_do) > len(["base1", "base2"])
        assert any("invalidation" in r.lower() or "cache" in r.lower() for r in must_do)

    def test_database_domain(self):
        issue = _make_issue(title="Fix migration", issue_type="bug")
        desc, must_do, must_not_do = _generate_focus_rules(
            ["database", "migration"], ["database", "migration", "schema"], issue,
        )
        assert "database" in desc.lower()
        assert any("migration" in r.lower() for r in must_do)

    def test_no_domain_match_uses_issue_type(self):
        issue = _make_issue(title="Weird thing", issue_type="bug")
        desc, must_do, must_not_do = _generate_focus_rules(
            ["xylophone", "platypus"], ["xylophone", "platypus"], issue,
        )
        assert "specialist" in desc.lower()
        # Bug-specific rules should be added
        assert any("reproduce" in r.lower() for r in must_do)

    def test_multiple_domains_combined(self):
        issue = _make_issue(title="API with caching", issue_type="feature")
        desc, must_do, must_not_do = _generate_focus_rules(
            ["api", "cache", "endpoint"],
            ["api", "cache", "endpoint", "http", "redis", "ttl"],
            issue,
        )
        # Should have rules from both API and cache domains
        assert any("api" in r.lower() or "input" in r.lower() for r in must_do)
        assert any("cache" in r.lower() or "invalidation" in r.lower() for r in must_do)

    def test_always_has_baseline_rules(self):
        issue = _make_issue(title="Anything", issue_type="task")
        desc, must_do, must_not_do = _generate_focus_rules(
            ["something"], ["something"], issue,
        )
        assert len(must_do) >= 3  # baseline rules
        assert len(must_not_do) >= 2
        assert any("understand" in r.lower() or "read" in r.lower() for r in must_do)


class TestAnalyzeCompletedIssue:
    def test_returns_none_when_focus_matches(self):
        issue = _make_issue(title="Fix a crash in the parser", issue_type="bug")
        comments = [{"text": "Found the bug in the error handler"}]
        result = analyze_completed_issue(issue, comments, foci=BUILTIN_FOCI, threshold=0.1)
        assert result is None  # bugfix focus should match

    def test_returns_suggestion_when_no_match(self, tmp_path, monkeypatch):
        # Use tmp paths to avoid writing to real files
        foci_path = str(tmp_path / "foci.json")
        monkeypatch.setattr("oompah.focus.DEFAULT_FOCI_PATH", foci_path)

        # Foci that won't match the work
        narrow_foci = [
            Focus(name="narrow", role="", description="",
                  keywords=["quantum", "photon"], status="active"),
        ]
        issue = _make_issue(
            title="Implement caching layer for database queries",
            description="Add Redis caching to reduce database load",
        )
        comments = [{"text": "Implemented cache invalidation with TTL strategy"}]
        result = analyze_completed_issue(issue, comments, foci=narrow_foci)
        assert result is not None
        assert isinstance(result, FocusSuggestion)
        assert len(result.sample_keywords) > 0

        # Verify the proposed focus saved to disk has rules
        saved = load_foci(foci_path)
        proposed = [f for f in saved if f.status == "proposed"]
        assert len(proposed) >= 1
        p = proposed[0]
        assert len(p.must_do) > 0, "Proposed focus should have must_do rules"
        assert len(p.must_not_do) > 0, "Proposed focus should have must_not_do rules"
        assert "review and edit" not in p.description.lower(), "Description should be meaningful, not boilerplate"


class TestFocusSuggestionSerialization:
    def test_round_trip(self):
        original = FocusSuggestion(
            suggested_name="cache_specialist",
            suggested_role="Cache Specialist",
            reason="No match",
            source_issues=["beads-001"],
            sample_keywords=["cache", "redis"],
            created_at="2025-01-01T00:00:00",
            status="pending",
        )
        restored = FocusSuggestion.from_dict(original.to_dict())
        assert restored.suggested_name == original.suggested_name
        assert restored.source_issues == original.source_issues
        assert restored.status == original.status
