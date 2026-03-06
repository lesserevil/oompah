"""Tests for oompah.prompt."""

import pytest

from oompah.models import Issue
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt


def _make_issue(**kwargs):
    defaults = dict(id="1", identifier="beads-001", title="Fix the bug", state="open")
    defaults.update(kwargs)
    return Issue(**defaults)


class TestRenderPrompt:
    def test_basic_render(self):
        issue = _make_issue()
        template = "Working on {{ issue.identifier }}: {{ issue.title }}"
        result = render_prompt(template, issue)
        assert "beads-001" in result
        assert "Fix the bug" in result

    def test_empty_template_fallback(self):
        issue = _make_issue()
        result = render_prompt("  ", issue)
        assert "beads-001" in result
        assert "Fix the bug" in result

    def test_with_attempt(self):
        issue = _make_issue()
        template = "{% if attempt %}Attempt #{{ attempt }}{% endif %}"
        result = render_prompt(template, issue, attempt=3)
        assert "Attempt #3" in result

    def test_without_attempt(self):
        issue = _make_issue()
        template = "{% if attempt %}Attempt #{{ attempt }}{% else %}First run{% endif %}"
        result = render_prompt(template, issue, attempt=None)
        assert "First run" in result

    def test_with_comments(self):
        issue = _make_issue()
        template = "{% for c in comments %}- {{ c.author }}: {{ c.text }}\n{% endfor %}"
        comments = [
            {"author": "alice", "text": "found the bug", "created_at": "2025-01-01"},
        ]
        result = render_prompt(template, issue, comments=comments)
        assert "alice" in result
        assert "found the bug" in result

    def test_with_focus(self):
        issue = _make_issue()
        template = "{% if focus != blank %}{{ focus }}{% endif %}"
        result = render_prompt(template, issue, focus_text="## Your Role: Bug Fixer")
        assert "Bug Fixer" in result

    def test_issue_labels(self):
        issue = _make_issue(labels=["urgent", "backend"])
        template = "Labels: {{ issue.labels | join: ', ' }}"
        result = render_prompt(template, issue)
        assert "urgent" in result
        assert "backend" in result

    def test_invalid_template(self):
        issue = _make_issue()
        with pytest.raises(PromptError):
            render_prompt("{% invalid liquid %}", issue)


class TestBuildContinuationPrompt:
    def test_contains_info(self):
        issue = _make_issue()
        result = build_continuation_prompt(issue, 5, 20)
        assert "beads-001" in result
        assert "turn 5" in result
        assert "20" in result
        assert "open" in result
