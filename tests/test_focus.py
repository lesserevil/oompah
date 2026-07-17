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
    _compute_similarity_score,
    _extract_topic_prefix,
    _extract_work_keywords,
    _generate_focus_rules,
    _text_matches,
    _work_matches_focus,
    analyze_completed_issue,
    find_similar_issues,
    load_foci,
    save_foci,
    save_suggestion,
    score_focus,
    select_focus,
)
from oompah.models import Issue


def _make_issue(**kwargs):
    defaults = dict(id="1", identifier="tasks-001", title="Test issue", state="open")
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

    def test_ci_fix_focus_selected_by_label(self):
        """A task with label='ci-fix' should be matched to the ci_fix focus."""
        issue = _make_issue(title="Some failing tests", labels=["ci-fix"])
        focus = select_focus(issue)
        assert focus.name == "ci_fix"

    def test_ci_fix_focus_high_priority_beats_other_matches(self):
        """ci_fix focus should win over other matches via priority=100."""
        issue = _make_issue(
            title="Fix a bug in the login flow",
            labels=["ci-fix"],
            issue_type="bug",
        )
        focus = select_focus(issue)
        assert focus.name == "ci_fix"

    def test_ci_fix_focus_must_not_do_blocks_new_branch_and_pr(self):
        """The ci_fix focus's must_not_do prevents creating a new branch / PR.

        This is the exact constraint that the issue (oompah-zlz_2-0pr) was
        filed to encode: trickle-icl agent created a new branch and opened
        PR #32 instead of pushing to trickle-rl5.
        """
        ci_fix_focus = next(f for f in BUILTIN_FOCI if f.name == "ci_fix")
        rails = " ".join(ci_fix_focus.must_not_do).lower()
        assert "new branch" in rails, "ci_fix must forbid creating a new branch"
        assert "new pull request" in rails, "ci_fix must forbid opening a new PR"

    def test_ci_fix_focus_must_do_includes_checkout_existing_branch(self):
        """The ci_fix focus's must_do should direct the agent to identify
        and check out the existing branch from the task body — this is
        what makes 'branch trickle-rl5' in the task translate into the
        right git checkout call.
        """
        ci_fix_focus = next(f for f in BUILTIN_FOCI if f.name == "ci_fix")
        steps = " ".join(ci_fix_focus.must_do).lower()
        assert "existing branch" in steps
        assert "git checkout" in steps
        # Force-push guidance — ci_fix branches typically need --force-with-lease
        assert "--force-with-lease" in steps

    def test_ci_fix_focus_render_preserves_branch_instruction(self):
        """When rendered, the focus prompt should still tell the agent to
        check out the existing branch identified in the task body. The
        task body containing 'branch trickle-rl5' will be substituted into
        <branch> by the agent following the focus instructions.
        """
        ci_fix_focus = next(f for f in BUILTIN_FOCI if f.name == "ci_fix")
        rendered = ci_fix_focus.render()
        assert "<branch>" in rendered
        assert "git checkout" in rendered.lower()
        assert "do not create a new branch" in rendered.lower()

    def test_ci_fix_focus_priority_matches_merge_conflict(self):
        """Both safety-critical foci share priority=100 so neither wins
        a tie over the other on a task that somehow matches both — and
        both decisively beat keyword/label-only matches from other foci.
        """
        ci_fix_focus = next(f for f in BUILTIN_FOCI if f.name == "ci_fix")
        merge_conflict_focus = next(f for f in BUILTIN_FOCI if f.name == "merge_conflict")
        assert ci_fix_focus.priority == merge_conflict_focus.priority == 100


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

    def test_model_overrides_round_trip(self):
        original = Focus(
            name="docs", role="Tech Writer", description="docs",
            model_role="fast", model="gpt-4o-mini", provider_id="prov-xyz",
        )
        restored = Focus.from_dict(original.to_dict())
        assert restored.model_role == "fast"
        assert restored.model == "gpt-4o-mini"
        assert restored.provider_id == "prov-xyz"

    def test_model_overrides_default_to_none(self):
        f = Focus(name="x", role="X", description="x")
        assert f.model_role is None
        assert f.model is None
        assert f.provider_id is None
        d = f.to_dict()
        # Don't bloat foci.json with null fields when unset.
        assert "model_role" not in d
        assert "model" not in d
        assert "provider_id" not in d

    def test_allow_image_output_default_false(self):
        f = Focus(name="x", role="X", description="x")
        assert f.allow_image_output is False
        assert "allow_image_output" not in f.to_dict()

    def test_allow_image_output_round_trip(self):
        f = Focus(name="x", role="X", description="x", allow_image_output=True)
        d = f.to_dict()
        assert d["allow_image_output"] is True
        f2 = Focus.from_dict(d)
        assert f2.allow_image_output is True

    def test_model_overrides_blank_strings_normalize_to_none(self):
        restored = Focus.from_dict({
            "name": "x", "role": "X", "description": "x",
            "model_role": "  ", "model": "", "provider_id": None,
        })
        assert restored.model_role is None
        assert restored.model is None
        assert restored.provider_id is None


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
                id=str(i), identifier=f"tasks-{i:03d}",
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
            source_issues=["tasks-001"],
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

    def test_epic_planner_has_no_draft_label_filter(self):
        """epic_planner must NOT filter on 'draft' label after OOMPAH-171 removal."""
        focus = self._get_epic_planner()
        assert "draft" not in focus.labels

    def test_epic_planner_selected_for_plain_epic(self):
        """epic_planner should be selected for any epic (draft label no longer required)."""
        issue = _make_issue(title="New feature epic", issue_type="epic", labels=[])
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

    def test_epic_planner_must_do_includes_dependency_edit(self):
        """epic_planner must_do should instruct using task dependencies."""
        focus = self._get_epic_planner()
        dep_add_rule = any(
            "oompah task set-dependency" in rule and "--depends-on" in rule
            for rule in focus.must_do
        )
        assert dep_add_rule, "must_do should include a rule about task dependencies"

    def test_epic_planner_must_do_includes_parent_child_link(self):
        """epic_planner must_do should instruct linking children to parent epic."""
        focus = self._get_epic_planner()
        parent_child_rule = any("parent-child" in rule for rule in focus.must_do)
        assert parent_child_rule, "must_do should include a rule about parent-child linking"

    def test_epic_planner_must_do_does_not_mention_draft_label(self):
        """epic_planner must_do must NOT instruct removing a draft label (OOMPAH-171)."""
        focus = self._get_epic_planner()
        # Automatic draft lifecycle removed; no rule should mention draft labels
        draft_rules = [rule for rule in focus.must_do if "draft" in rule.lower()]
        assert not draft_rules, f"must_do must not mention draft label (OOMPAH-171), found: {draft_rules}"

    def test_epic_planner_must_do_includes_set_to_backlog(self):
        """epic_planner must_do should instruct setting the epic status to Backlog."""
        focus = self._get_epic_planner()
        backlog_rule = any("Backlog" in rule for rule in focus.must_do)
        assert backlog_rule, "must_do should include a rule about setting status to Backlog"

    def test_epic_planner_draft_label_does_not_affect_score(self):
        """draft label must NOT boost epic_planner score after OOMPAH-171 removal."""
        focus = self._get_epic_planner()
        issue_with_draft = _make_issue(title="New epic", issue_type="epic", labels=["draft"])
        issue_without_draft = _make_issue(title="New epic", issue_type="epic")
        score_with = score_focus(focus, issue_with_draft)
        score_without = score_focus(focus, issue_without_draft)
        # Draft label should not be in focus.labels, so scores should be equal
        assert score_with == score_without, (
            "draft label must not change epic_planner score (OOMPAH-171)"
        )


class TestFocusRenderWithProject:
    """Tests for Focus.render(project=) — per-project test_command injection."""

    def _merge_conflict_focus(self):
        for f in BUILTIN_FOCI:
            if f.name == "merge_conflict":
                return f
        raise AssertionError("merge_conflict focus not found")

    def _make_project(self, **kwargs):
        from oompah.models import Project
        defaults = dict(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        defaults.update(kwargs)
        return Project(**defaults)

    def test_render_without_project_unchanged(self):
        """Backwards-compat: no project -> behaves like the old render()."""
        focus = self._merge_conflict_focus()
        out_no_arg = focus.render()
        out_none = focus.render(None)
        assert out_no_arg == out_none
        # The original generic 'Run tests' line is still present.
        assert "Run tests after resolving all conflicts" in out_no_arg
        # And no Project Test Configuration block.
        assert "Project Test Configuration" not in out_no_arg

    def test_render_with_test_command_replaces_run_tests(self):
        focus = self._merge_conflict_focus()
        project = self._make_project(test_command="cargo test --workspace --lib")
        out = focus.render(project)
        # The generic line should be gone, replaced with the explicit one.
        assert "Run tests after resolving all conflicts" not in out
        assert "Run `cargo test --workspace --lib`" in out
        # The original tail (purpose) is preserved.
        assert "verify nothing is broken" in out

    def test_render_with_test_command_no_run_tests_bullet_appends_block(self):
        """Focus that doesn't have a 'Run tests' bullet still gets a hint block."""
        from oompah.focus import Focus
        focus = Focus(
            name="custom", role="Custom",
            description="Do a thing.",
            must_do=["Implement the thing"],
        )
        project = self._make_project(test_command="make test")
        out = focus.render(project)
        assert "Project Test Configuration" in out
        assert "make test" in out
        assert "configured test_command" in out

    def test_render_does_not_double_mention_test_command(self):
        """When a must_do bullet already names the command, no duplicate hint."""
        from oompah.focus import Focus
        focus = Focus(
            name="custom", role="Custom",
            description="Do a thing.",
            must_do=["Run tests to verify"],
        )
        project = self._make_project(test_command="make test")
        out = focus.render(project)
        # The must_do line is rewritten with the command.
        assert "Run `make test` to verify" in out
        # But the extras hint is suppressed since the command appears already.
        assert "configured test_command" not in out

    def test_render_with_test_command_full(self):
        focus = self._merge_conflict_focus()
        project = self._make_project(
            test_command="make test",
            test_command_full="make test-all",
        )
        out = focus.render(project)
        assert "make test-all" in out
        assert "broader pre-merge-queue coverage" in out

    def test_render_with_test_skip_paths(self):
        focus = self._merge_conflict_focus()
        project = self._make_project(
            test_command="make test",
            test_skip_paths=["tests/hw/*", "tests/integration/*"],
        )
        out = focus.render(project)
        assert "tests/hw/*" in out
        assert "tests/integration/*" in out
        assert "Skip" in out

    def test_render_no_test_command_no_changes(self):
        """Project without test_command behaves like project=None."""
        focus = self._merge_conflict_focus()
        project = self._make_project()
        # default test_command is None; no test_command_full or skip paths
        out = focus.render(project)
        assert "Run tests after resolving all conflicts" in out
        assert "Project Test Configuration" not in out


class TestExtractTopicPrefix:
    """Tests for _extract_topic_prefix() — topic prefix extraction."""

    def test_basic_prefix(self):
        assert _extract_topic_prefix("rogers-how to connect") == "rogers"
        assert _extract_topic_prefix("rogers-5hd setup") == "rogers"
        assert _extract_topic_prefix("database-migration-guide") == "database"

    def test_underscore_separator(self):
        # Splits on first underscore. "my_service_alive" splits to "my" / "service_alive";
        # prefix "my" is only 2 chars < MIN_PREFIX_LEN=3, so returns None.
        # "auth_oauth2_flow" splits to "auth" / "oauth2_flow"; prefix "auth" has
        # 4 chars >= 3, returns "auth".
        assert _extract_topic_prefix("my_service_alive") is None
        assert _extract_topic_prefix("auth_oauth2_flow") == "auth"

    def test_no_separator(self):
        # No hyphen or underscore: the whole title IS the prefix (provided
        # it meets minimum length and is word-like).
        assert _extract_topic_prefix("singleword") == "singleword"
        assert _extract_topic_prefix("anotherlongword") == "anotherlongword"

    def test_prefix_too_short(self):
        # 1-char prefix: too short → rejected
        assert _extract_topic_prefix("a-something") is None
        # 2-char prefix: rejected with MIN_PREFIX_LEN=3
        assert _extract_topic_prefix("ab-something") is None
        # 3-char prefix: accepted
        assert _extract_topic_prefix("abx-something") == "abx"

    def test_prefix_with_digit(self):
        # "v2-beta": prefix "v2" is 2 chars < MIN_PREFIX_LEN=3 → too short → None
        assert _extract_topic_prefix("v2-beta") is None
        # "api5-use-cases": prefix "api5" is 4 chars ≥ 3 → accepted
        assert _extract_topic_prefix("api5-use-cases") == "api5"

    def test_empty_title(self):
        assert _extract_topic_prefix("") is None
        assert _extract_topic_prefix(None) is None

    def test_prefix_with_non_alphanumeric(self):
        # Prefix with spaces or dots (no alphanumeric) should return None
        assert _extract_topic_prefix("foo bar-baz") is None
        assert _extract_topic_prefix("foo.bar-baz") is None

    def test_prefix_punctuation_after_prefix(self):
        # "foo.bar-baz" prefix is "foo.bar" (contains dot → invalid)
        assert _extract_topic_prefix("foo.bar-baz") is None
        # "foo-bar-baz" prefix is "foo" (valid)
        assert _extract_topic_prefix("foo-bar-baz") == "foo"
        assert _extract_topic_prefix("foo_bar_baz") == "foo"

    def test_only_numbers(self):
        # Numeric prefix: "123-something" → valid, returns "123"
        assert _extract_topic_prefix("123-something") == "123"

    def test_numeric_prefix(self):
        """Numeric prefixes like 'v2', '2fa': "2fa" (3 chars, MIN_PREFIX_LEN=3) is accepted."""
        assert _extract_topic_prefix("v2-deploy") is None  # "v2" is 2 chars < MIN_PREFIX_LEN=3
        assert _extract_topic_prefix("2fa-setup") == "2fa"


class TestComputeSimilarityScore:
    """Tests for _compute_similarity_score() — fuzzy similarity between two issues."""

    def test_same_title_exact(self):
        """Identical title + same project.type → max score."""
        a = _make_issue(identifier="a", title="rogers-how to reset", project_id="p", issue_type="bug", labels=["networking"])
        b = _make_issue(identifier="b", title="rogers-how to reset", project_id="p", issue_type="bug", labels=["networking"])
        score = _compute_similarity_score(a, b)
        assert score == 1.0

    def test_rogers_pattern_duplicates(self):
        """Issues with same 'rogers' prefix should score high even with different suffixes."""
        a = _make_issue(identifier="a", title="rogers-how to connect", project_id="p", issue_type="bug", labels=["networking"])
        b = _make_issue(identifier="b", title="rogers-5hd setup", project_id="p", issue_type="bug", labels=["networking"])
        # Both same project + same type + shared label → 0.5
        # Same prefix "rogers" → +0.25
        score = _compute_similarity_score(a, b)
        assert score >= 0.7, f"Expected high score for rogers-*/rogers-* pattern, got {score}"

    def test_rogers_different_suffix_different_labels(self):
        """Same topic prefix but no shared label — should still score on prefix alone."""
        a = _make_issue(identifier="a", title="rogers-zdn error", project_id="p", issue_type="bug", labels=["urgent"])
        b = _make_issue(identifier="b", title="rogers-5hd timeout", project_id="p", issue_type="bug", labels=["low-priority"])
        score = _compute_similarity_score(a, b)
        # Same project + same type (0.2) + same prefix "rogers" (0.25) + shared word (0 if none) = 0.45
        assert score >= 0.4, f"Expected at least 0.4 for same-prefix diff-labels, got {score}"

    def test_different_prefix_low_score(self):
        """Issues with different topic prefixes should score significantly lower than exact-match."""
        a = _make_issue(identifier="a", title="rogers-connect", project_id="p", issue_type="bug", labels=["networking"])
        b = _make_issue(identifier="b", title=" Completely-different-title", project_id="p", issue_type="bug", labels=["networking"])
        score = _compute_similarity_score(a, b)
        # Same project + same type + shared label = 0.5; NO word overlap in suffix = no extra
        assert score <= 0.5

    def test_different_project(self):
        """Different projects should score lower than same-project matches."""
        a = _make_issue(identifier="a", title=".database-migration", project_id="proj1", issue_type="bug", labels=["db"])
        b = _make_issue(identifier="b", title="database-cache-issue", project_id="proj2", issue_type="bug", labels=["db"])
        score = _compute_similarity_score(a, b)
        # Same type + shared label + SAME suffix words "database" (>= 3 chars, not stop word)
        # "database" (8 chars) is in the suffix words for both → overlap boosts to 0.25
        # + 0.5 for same type/labels = 0.75 if same project... but different project so capped at 0.5
        assert score <= 0.5, f"Expected ≤0.5 for different-project, got {score}"

    def test_no_shared_words_in_suffix(self):
        """Even with same signature, no shared words reduces score."""
        a = _make_issue(identifier="a", title="rogers-alpha", project_id="p", issue_type="bug", labels=[])
        b = _make_issue(identifier="b", title="rogers-beta", project_id="p", issue_type="bug", labels=[])
        score = _compute_similarity_score(a, b)
        # Same project/type (0.2) + same prefix (0.25) = 0.45
        assert score >= 0.4

    def test_max_score_capped_at_1(self):
        """Score must never exceed 1.0."""
        a = _make_issue(identifier="a", title="foo-bar-baz", project_id="p", issue_type="bug", labels=["a", "b", "c"])
        b = _make_issue(identifier="b", title="foo-bar-baz", project_id="p", issue_type="bug", labels=["a", "b", "c"])
        score = _compute_similarity_score(a, b)
        assert score <= 1.0

    def test_score_zero_for_completely_different_issues(self):
        """Completely unrelated issues should score near zero."""
        a = _make_issue(identifier="a", title="database-migration", project_id="p", issue_type="bug", labels=["db"])
        b = _make_issue(identifier="b", title="mouse-clicking-problem", project_id="q", issue_type="task", labels=["ui"])
        score = _compute_similarity_score(a, b)
        assert score < 0.2


class TestFindSimilarIssues:
    """Tests for find_similar_issues() — candidate scanning for duplicates."""

    def test_finds_high_score_matches(self):
        """Issues with 'rogers' prefix and same project should be found."""
        base = _make_issue(identifier="new-1", title="rogers-foo bar", project_id="p", issue_type="bug")
        candidates = [
            _make_issue(identifier="old-1", title="rogers-alpha", project_id="p", issue_type="bug"),
            _make_issue(identifier="old-2", title="rogers-beta fix", project_id="p", issue_type="bug"),
            _make_issue(identifier="old-3", title="unrelated-issue", project_id="p", issue_type="bug"),
        ]
        similar = find_similar_issues(base, candidates)
        identifiers = [s.identifier for s, _ in similar]
        assert "old-1" in identifiers
        assert "old-2" in identifiers
        assert "old-3" not in identifiers

    def test_ignores_self(self):
        """The candidate itself should never appear in results."""
        issue = _make_issue(identifier="self-1", title="foo-bar", project_id="p", issue_type="bug")
        candidates = [
            _make_issue(identifier="self-1", title="foo-bar", project_id="p", issue_type="bug"),
            _make_issue(identifier="other-1", title="foo-bar", project_id="p", issue_type="bug"),
        ]
        similar = find_similar_issues(issue, candidates)
        identifiers = [s.identifier for s, _ in similar]
        assert "self-1" not in identifiers
        assert "other-1" in identifiers

    def test_sorted_by_score(self):
        """Results should be descending by similarity score."""
        base = _make_issue(identifier="base", title="rogers-how", project_id="p", issue_type="bug", labels=["x"])
        candidates = [
            _make_issue(identifier="a", title="rogers-best-match", project_id="p", issue_type="bug", labels=["x", "y"]),
            _make_issue(identifier="b", title="rogers-worst-match", project_id="p", issue_type="bug"),
            _make_issue(identifier="c", title="rogers-medium-match", project_id="p", issue_type="bug"),
        ]
        similar = find_similar_issues(base, candidates)
        scores = [score for _, score in similar]
        assert scores == sorted(scores, reverse=True)

    def test_empty_candidates(self):
        """Empty candidate list should return empty results."""
        issue = _make_issue(identifier="x", title="foo-bar", project_id="p", issue_type="bug")
        assert find_similar_issues(issue, []) == []

    def test_min_score_threshold(self):
        """Issues below min_score should be excluded."""
        base = _make_issue(identifier="x", title="unique-title", project_id="p", issue_type="bug")
        candidates = [
            _make_issue(identifier="y", title="completely-different-title-here", project_id="p", issue_type="bug"),
        ]
        similar = find_similar_issues(base, candidates, min_score=0.8)
        assert len(similar) == 0

    def test_includes_closed_issues(self):
        """Closed candidate issues should be included in results."""
        base = _make_issue(identifier="x", title="rogers-connect", project_id="p", issue_type="bug")
        closed = _make_issue(identifier="closed-1", title="rogers-fix-already", project_id="p", issue_type="bug", state="closed")
        similar = find_similar_issues(base, [closed])
        assert len(similar) == 1
        assert similar[0][0].identifier == "closed-1"
        assert similar[0][1] >= 0.5


class TestDuplicateDetectorFocus:
    """Tests for the built-in duplicate_detector focus (oompah-zlz_2-x6w3)."""

    def _get_duplicate_detector(self):
        matches = [f for f in BUILTIN_FOCI if f.name == "duplicate_detector"]
        assert matches, "duplicate_detector focus not found in BUILTIN_FOCI"
        return matches[0]

    def test_exists_in_builtin_foci(self):
        names = [f.name for f in BUILTIN_FOCI]
        assert "duplicate_detector" in names

    def test_has_correct_role(self):
        focus = self._get_duplicate_detector()
        assert focus.role == "Duplicate Investigator"

    def test_has_must_do_rules(self):
        focus = self._get_duplicate_detector()
        assert len(focus.must_do) > 0

    def test_has_must_not_do_rules(self):
        focus = self._get_duplicate_detector()
        assert len(focus.must_not_do) > 0

    def test_must_do_includes_task_search(self):
        """must_do should mention searching for similar issues."""
        focus = self._get_duplicate_detector()
        text = " ".join(focus.must_do)
        assert ".oompah/tasks" in text and ("duplicate" in text.lower() or "similar" in text.lower())

    def test_must_do_includes_close_as_duplicate(self):
        """must_do should instruct closing confirmed duplicates."""
        focus = self._get_duplicate_detector()
        text = " ".join(focus.must_do)
        assert "oompah task set-status" in text.lower() and "archived" in text.lower()

    def test_must_not_do_prevents_implementing_before_confirming(self):
        """must_not_do should prevent implementing code before duplicate is confirmed."""
        focus = self._get_duplicate_detector()
        text = " ".join(focus.must_not_do).lower()
        assert "implement" in text or "code" in text or "branch" in text

    def test_must_not_do_blocks_new_branch_for_duplicates(self):
        """must_not_do should prevent creating new branches for confirmed duplicates."""
        focus = self._get_duplicate_detector()
        text = " ".join(focus.must_not_do).lower()
        assert "branch" in text or "pr" in text

    def test_priority_is_high(self):
        """duplicate_detector should have high priority to outrank other matches."""
        focus = self._get_duplicate_detector()
        assert focus.priority >= 15, "duplicate_detector priority should be high (>= 15)"

    def test_keywords_include_duplicate(self):
        focus = self._get_duplicate_detector()
        assert "duplicate" in focus.keywords

    def test_keywords_include_rogers_topic(self):
        """Keywords should include 'rogers' as an example of a topic prefix."""
        focus = self._get_duplicate_detector()
        assert "rogers" in focus.keywords

    def test_selected_for_duplicate_keyword(self):
        """An issue with 'duplicate' in title should strongly score duplicate_detector."""
        foci = [
            self._get_duplicate_detector(),
            Focus(name="feature", role="Feature", description="",
                  keywords=["implement", "add"], status="active"),
        ]
        issue = _make_issue(title="This looks like a duplicate of another issue", labels=[])
        focus = select_focus(issue, foci)
        assert focus.name == "duplicate_detector"

    def test_completed_focus_does_not_receive_the_same_focus_again(self):
        """A handoff lets the next run select a different applicable focus."""
        foci = [
            self._get_duplicate_detector(),
            Focus(name="chore", role="Maintenance", description="",
                  keywords=["update"], status="active"),
        ]
        issue = _make_issue(
            title="Update duplicate detection documentation",
            labels=["focus-complete:duplicate_detector"],
        )

        assert select_focus(issue, foci).name == "chore"

    def test_selected_for_rogers_prefix_issue(self):
        """An issue with a topic-prefix title should score duplicate_detector."""
        foci = [
            self._get_duplicate_detector(),
            Focus(name="bugfix", role="Bug Fixer", description="",
                  keywords=["bug", "crash"], status="active"),
        ]
        # "rogers-something" title with no other keyword matches
        issue = _make_issue(title="rogers-xyz issue: cannot authenticate", labels=[])
        focus = select_focus(issue, foci)
        # duplicate_detector has "rogers" keyword
        assert focus.name == "duplicate_detector"

    def test_render_contains_role(self):
        focus = self._get_duplicate_detector()
        rendered = focus.render()
        assert "Duplicate Investigator" in rendered

    def test_render_contains_must_do(self):
        focus = self._get_duplicate_detector()
        rendered = focus.render()
        assert "### You MUST:" in rendered

    def test_render_contains_must_not_do(self):
        focus = self._get_duplicate_detector()
        rendered = focus.render()
        assert "### You must NOT:" in rendered

    def test_render_requires_a_contextual_focus_handoff(self):
        rendered = self._get_duplicate_detector().render()
        assert "Focus handoff" in rendered
        assert "remaining work or risks" in rendered
        assert "Focus handoff: duplicate_detector" in rendered
        assert "focus-complete:duplicate_detector" in rendered

    def test_serialization_round_trip(self):
        focus = self._get_duplicate_detector()
        restored = Focus.from_dict(focus.to_dict())
        assert restored.name == focus.name
        assert restored.role == focus.role
        assert restored.priority == focus.priority
        assert restored.status == focus.status
        assert restored.must_do == focus.must_do
        assert restored.keywords == focus.keywords
