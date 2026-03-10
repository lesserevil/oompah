"""Tests for oompah.focus."""

import json
import os

import pytest

from oompah.focus import (
    BUILTIN_FOCI,
    DEFAULT_FOCUS,
    MIN_DOMAIN_KEYWORDS,
    MIN_ISSUES_FOR_PROPOSAL,
    Focus,
    FocusSuggestion,
    _extract_work_keywords,
    _generate_focus_rules,
    _text_matches,
    _work_matches_focus,
    analyze_completed_issue,
    load_foci,
    save_foci,
    save_suggestion,
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

    def test_merge_in_title_does_not_trigger_conflict_focus(self):
        """Issue with 'merge' in title but no conflict context should not get merge_conflict focus."""
        issue = _make_issue(
            title="Merge Executor (In-Order)",
            description="Merge via GitLab API with safety. Failures: conflict->failed.",
            issue_type="task",
        )
        focus = select_focus(issue)
        assert focus.name != "merge_conflict"


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
        issue = _make_issue(title="Add a new feature to support user profiles", issue_type="feature")
        comments = [{"text": "Implemented the new feature for user profile creation"}]
        result = analyze_completed_issue(issue, comments, foci=BUILTIN_FOCI, threshold=0.1)
        assert result is None  # feature focus should match

    def test_returns_none_when_too_few_domain_keywords(self):
        """Generic work without domain keywords should not trigger a suggestion."""
        narrow_foci = [
            Focus(name="narrow", role="", description="",
                  keywords=["quantum", "photon"], status="active"),
        ]
        issue = _make_issue(title="Rename some variables", description="Cleanup")
        comments = [{"text": "Renamed foo to bar"}]
        result = analyze_completed_issue(issue, comments, foci=narrow_foci)
        assert result is None

    def test_returns_suggestion_when_no_match(self, tmp_path, monkeypatch):
        # Use tmp paths to avoid writing to real files
        foci_path = str(tmp_path / "foci.json")
        suggestions_path = str(tmp_path / "suggestions.json")
        monkeypatch.setattr("oompah.focus.DEFAULT_FOCI_PATH", foci_path)
        monkeypatch.setattr("oompah.focus.DEFAULT_SUGGESTIONS_PATH", suggestions_path)

        # Foci that won't match the work
        narrow_foci = [
            Focus(name="narrow", role="", description="",
                  keywords=["quantum", "photon"], status="active"),
        ]
        # Use text with enough domain keywords (cache, database, api, config)
        issue = _make_issue(
            title="Add API cache layer with database config",
            description="Build a cache in front of the database API with config-driven TTL",
        )
        comments = [{"text": "Added cache invalidation via webhook callback on config change"}]
        result = analyze_completed_issue(issue, comments, foci=narrow_foci)
        assert result is not None
        assert isinstance(result, FocusSuggestion)
        assert len(result.sample_keywords) > 0

        # A single issue should NOT create a proposed focus yet
        saved = load_foci(foci_path)
        proposed = [f for f in saved if f.status == "proposed"]
        assert len(proposed) == 0, "One issue should not be enough to propose a focus"

    def test_proposed_focus_after_enough_issues(self, tmp_path, monkeypatch):
        """A proposed focus should only be saved after MIN_ISSUES_FOR_PROPOSAL issues."""
        foci_path = str(tmp_path / "foci.json")
        suggestions_path = str(tmp_path / "suggestions.json")
        monkeypatch.setattr("oompah.focus.DEFAULT_FOCI_PATH", foci_path)
        monkeypatch.setattr("oompah.focus.DEFAULT_SUGGESTIONS_PATH", suggestions_path)

        narrow_foci = [
            Focus(name="narrow", role="", description="",
                  keywords=["quantum", "photon"], status="active"),
        ]

        # Submit suggestions from multiple distinct issues, all in the same domain
        for i in range(MIN_ISSUES_FOR_PROPOSAL):
            issue = _make_issue(
                id=str(i), identifier=f"beads-{i:03d}",
                title="Add API cache layer with database config",
                description="Build a cache in front of the database API with config-driven TTL",
            )
            comments = [{"text": "Added cache invalidation via webhook callback on config change"}]
            result = analyze_completed_issue(issue, comments, foci=narrow_foci)
            assert result is not None
            save_suggestion(result, suggestions_path)

        # Now enough issues have accumulated — a proposed focus should exist
        saved = load_foci(foci_path)
        proposed = [f for f in saved if f.status == "proposed"]
        assert len(proposed) >= 1, f"Expected proposed focus after {MIN_ISSUES_FOR_PROPOSAL} issues"
        p = proposed[0]
        assert len(p.must_do) > 0
        assert len(p.must_not_do) > 0


class TestHandoffLabelScoring:
    def test_needs_label_routes_to_correct_focus(self):
        """A needs:frontend label should strongly prefer the frontend focus."""
        foci = [
            Focus(name="bugfix", role="Bug Fixer", description="", keywords=["bug", "crash"], status="active"),
            Focus(name="frontend", role="Frontend Dev", description="", keywords=["ui", "css"], status="active"),
        ]
        # Issue title suggests bugfix, but label says needs:frontend
        issue = _make_issue(title="Fix a crash in the parser", labels=["needs:frontend"])
        focus = select_focus(issue, foci)
        assert focus.name == "frontend"

    def test_needs_label_overrides_type_match(self):
        """needs: label should win over issue_type matching."""
        foci = [
            Focus(name="bugfix", role="Bug Fixer", description="", keywords=["bug"], issue_types=["bug"], priority=10, status="active"),
            Focus(name="security", role="Security Auditor", description="", keywords=["xss"], priority=15, status="active"),
        ]
        issue = _make_issue(title="Fix a bug", issue_type="bug", labels=["needs:security"])
        focus = select_focus(issue, foci)
        assert focus.name == "security"

    def test_needs_label_score_value(self):
        """Direct test that needs: label adds 200 to score."""
        focus = Focus(name="frontend", role="", description="", keywords=["ui"])
        issue = _make_issue(title="unrelated title", labels=["needs:frontend"])
        score = score_focus(focus, issue)
        assert score >= 200

    def test_needs_label_no_match(self):
        """needs: label for a different focus should not boost score."""
        focus = Focus(name="bugfix", role="", description="", keywords=["bug"])
        issue = _make_issue(title="some issue", labels=["needs:frontend"])
        score = score_focus(focus, issue)
        assert score == 0

    def test_needs_label_case_insensitive(self):
        focus = Focus(name="Frontend", role="", description="", keywords=["ui"])
        issue = _make_issue(title="x", labels=["needs:frontend"])
        score = score_focus(focus, issue)
        assert score >= 200


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


class TestEpicPlannerFocus:
    """Tests for the built-in epic_planner focus."""

    def _get_epic_planner(self):
        """Retrieve the epic_planner focus from BUILTIN_FOCI."""
        matches = [f for f in BUILTIN_FOCI if f.name == "epic_planner"]
        assert matches, "epic_planner focus not found in BUILTIN_FOCI"
        return matches[0]

    def test_epic_planner_exists_in_builtin_foci(self):
        names = [f.name for f in BUILTIN_FOCI]
        assert "epic_planner" in names

    def test_epic_planner_has_correct_role(self):
        focus = self._get_epic_planner()
        assert focus.role == "Epic Planner"

    def test_epic_planner_has_must_do_rules(self):
        focus = self._get_epic_planner()
        assert len(focus.must_do) > 0

    def test_epic_planner_has_must_not_do_rules(self):
        focus = self._get_epic_planner()
        assert len(focus.must_not_do) > 0

    def test_epic_planner_issue_type_is_epic(self):
        focus = self._get_epic_planner()
        assert "epic" in focus.issue_types

    def test_epic_planner_keywords_include_epic(self):
        focus = self._get_epic_planner()
        assert "epic" in focus.keywords

    def test_epic_planner_selected_for_epic_issue_type(self):
        """epic_planner should be selected when issue_type is 'epic'."""
        issue = _make_issue(title="Build new payment system", issue_type="epic")
        focus = select_focus(issue)
        assert focus.name == "epic_planner"

    def test_epic_planner_selected_by_keyword_epic(self):
        """epic_planner should score for issues with 'epic' in the title."""
        foci = [
            Focus(name="epic_planner", role="Epic Planner", description="",
                  keywords=["epic", "plan", "breakdown"], issue_types=["epic"],
                  priority=8, status="active"),
            Focus(name="feature", role="Feature Dev", description="",
                  keywords=["feature", "add"], status="active"),
        ]
        issue = _make_issue(title="Epic: redesign user onboarding")
        focus = select_focus(issue, foci)
        assert focus.name == "epic_planner"

    def test_epic_planner_selected_for_planning_keywords(self):
        """epic_planner should score for issues that mention planning/breakdown."""
        foci = [
            Focus(name="epic_planner", role="Epic Planner", description="",
                  keywords=["epic", "plan", "planning", "breakdown", "decompose"],
                  issue_types=["epic"], priority=8, status="active"),
        ]
        issue = _make_issue(title="Plan and breakdown authentication tasks", issue_type="epic")
        focus = select_focus(issue, foci)
        assert focus.name == "epic_planner"

    def test_epic_planner_render_contains_role(self):
        focus = self._get_epic_planner()
        rendered = focus.render()
        assert "Epic Planner" in rendered

    def test_epic_planner_render_contains_must_do(self):
        focus = self._get_epic_planner()
        rendered = focus.render()
        assert "### You MUST:" in rendered

    def test_epic_planner_render_contains_must_not_do(self):
        focus = self._get_epic_planner()
        rendered = focus.render()
        assert "### You must NOT:" in rendered

    def test_epic_planner_serialization_round_trip(self):
        focus = self._get_epic_planner()
        restored = Focus.from_dict(focus.to_dict())
        assert restored.name == focus.name
        assert restored.role == focus.role
        assert restored.issue_types == focus.issue_types
        assert restored.keywords == focus.keywords
        assert restored.must_do == focus.must_do
        assert restored.must_not_do == focus.must_not_do
        assert restored.priority == focus.priority
        assert restored.status == focus.status

    def test_epic_planner_not_selected_when_inactive(self):
        """Inactive epic_planner should not be selected."""
        foci = [
            Focus(name="epic_planner", role="Epic Planner", description="",
                  keywords=["epic"], issue_types=["epic"], status="inactive"),
        ]
        issue = _make_issue(title="Plan new epic", issue_type="epic")
        focus = select_focus(issue, foci)
        assert focus.name == DEFAULT_FOCUS.name

    def test_epic_planner_score_from_issue_type(self):
        """Issue type 'epic' should add significant score for epic_planner."""
        focus = self._get_epic_planner()
        issue = _make_issue(title="Some work", issue_type="epic")
        score = score_focus(focus, issue)
        assert score >= 50  # at minimum the issue_type contribution

    def test_epic_planner_description_mentions_decomposing(self):
        focus = self._get_epic_planner()
        assert "decomposing" in focus.description.lower() or "decompose" in focus.description.lower()

    def test_epic_planner_has_draft_label(self):
        """epic_planner should match on epics with the 'draft' label."""
        focus = self._get_epic_planner()
        assert "draft" in focus.labels

    def test_epic_planner_selected_for_draft_epic(self):
        """epic_planner should be selected for an epic with the 'draft' label."""
        issue = _make_issue(title="New feature epic", issue_type="epic", labels=["draft"])
        focus = select_focus(issue)
        assert focus.name == "epic_planner"

    def test_epic_planner_keywords_include_children(self):
        """epic_planner keywords should include 'children'."""
        focus = self._get_epic_planner()
        assert "children" in focus.keywords

    def test_epic_planner_keywords_include_subtask(self):
        """epic_planner keywords should include 'subtask'."""
        focus = self._get_epic_planner()
        assert "subtask" in focus.keywords

    def test_epic_planner_must_do_includes_dep_add(self):
        """epic_planner must_do should instruct use of bd dep add for dependencies."""
        focus = self._get_epic_planner()
        dep_add_rule = any("bd dep add" in rule for rule in focus.must_do)
        assert dep_add_rule, "must_do should include a rule about bd dep add"

    def test_epic_planner_must_do_includes_parent_child_link(self):
        """epic_planner must_do should instruct linking children to parent epic."""
        focus = self._get_epic_planner()
        parent_child_rule = any("parent-child" in rule for rule in focus.must_do)
        assert parent_child_rule, "must_do should include a rule about parent-child linking"

    def test_epic_planner_must_do_includes_remove_draft_label(self):
        """epic_planner must_do should instruct removing the draft label when done."""
        focus = self._get_epic_planner()
        remove_draft_rule = any("draft" in rule and ("remove" in rule or "label" in rule) for rule in focus.must_do)
        assert remove_draft_rule, "must_do should include a rule about removing the draft label"

    def test_epic_planner_must_do_includes_set_deferred(self):
        """epic_planner must_do should instruct setting the epic status to 'deferred'."""
        focus = self._get_epic_planner()
        deferred_rule = any("deferred" in rule for rule in focus.must_do)
        assert deferred_rule, "must_do should include a rule about setting status to deferred"

    def test_epic_planner_draft_label_boosts_score(self):
        """draft label on an epic should boost the epic_planner score."""
        focus = self._get_epic_planner()
        issue_with_draft = _make_issue(title="New epic", issue_type="epic", labels=["draft"])
        issue_without_draft = _make_issue(title="New epic", issue_type="epic")
        score_with = score_focus(focus, issue_with_draft)
        score_without = score_focus(focus, issue_without_draft)
        assert score_with > score_without, "draft label should increase the epic_planner score"
