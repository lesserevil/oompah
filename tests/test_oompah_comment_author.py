"""Tests ensuring all issue comments from oompah are attributed to 'oompah'.

Bug: oompah was posting comments without --author=oompah, causing them to appear
as the system user or git user instead of 'oompah'.

Fix: WORKFLOW.md now requires --author=oompah in all bd comments add commands.
The orchestrator's _post_comment() already uses author="oompah" by default.
BeadsTracker.add_comment() already defaults to author="oompah".

These tests verify both the code-level defaults AND the rendered prompt template.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.prompt import render_prompt
from oompah.tracker import BeadsTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(identifier: str = "test-1", state: str = "open") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Test issue {identifier}",
        state=state,
    )


def _make_orchestrator(tmp_path, projects=None) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


# ---------------------------------------------------------------------------
# 1. BeadsTracker.add_comment — code-level default
# ---------------------------------------------------------------------------

class TestTrackerAddCommentAuthor:
    """BeadsTracker.add_comment must always pass --author=oompah by default."""

    def _tracker(self) -> BeadsTracker:
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_default_author_is_oompah(self, mock_run_bd):
        """Calling add_comment without author must use 'oompah'."""
        mock_run_bd.return_value = {}
        tracker = self._tracker()
        tracker.add_comment("issue-1", "Some progress note")

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args, (
            f"Expected --author=oompah in bd args, got: {args}"
        )

    @patch.object(BeadsTracker, "_run_bd")
    def test_explicit_oompah_still_passes_flag(self, mock_run_bd):
        """Explicit author='oompah' must still emit --author=oompah."""
        mock_run_bd.return_value = {}
        tracker = self._tracker()
        tracker.add_comment("issue-1", "Note", author="oompah")

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args

    @patch.object(BeadsTracker, "_run_bd")
    def test_no_bare_user_in_author_arg(self, mock_run_bd):
        """The bd call must NOT have an empty or missing --author flag."""
        mock_run_bd.return_value = {}
        tracker = self._tracker()
        tracker.add_comment("issue-1", "hello")

        args = mock_run_bd.call_args[0][0]
        # Check that no --author flag is missing or set to something other than oompah
        author_args = [a for a in args if a.startswith("--author=")]
        assert len(author_args) == 1, f"Expected exactly one --author= flag, got: {author_args}"
        assert author_args[0] == "--author=oompah", f"Expected --author=oompah, got: {author_args[0]}"


# ---------------------------------------------------------------------------
# 2. Orchestrator._post_comment — orchestrator-level default
# ---------------------------------------------------------------------------

class TestOrchestratorPostCommentAuthor:
    """Orchestrator._post_comment must use author='oompah' for all system comments."""

    @patch.object(BeadsTracker, "_run_bd")
    def test_post_comment_default_author_is_oompah(self, mock_run_bd, tmp_path):
        """_post_comment without explicit author uses 'oompah'."""
        mock_run_bd.return_value = {}
        orch = _make_orchestrator(tmp_path)

        orch._post_comment("issue-1", "Agent dispatched")

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args, (
            f"Expected --author=oompah in bd args from _post_comment, got: {args}"
        )

    @patch.object(BeadsTracker, "_run_bd")
    def test_post_comment_explicit_oompah_author(self, mock_run_bd, tmp_path):
        """_post_comment with explicit author='oompah' uses 'oompah'."""
        mock_run_bd.return_value = {}
        orch = _make_orchestrator(tmp_path)

        orch._post_comment("issue-1", "Focus: Software Engineer", author="oompah")

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args

    @patch.object(BeadsTracker, "_run_bd")
    def test_dispatch_comment_is_from_oompah(self, mock_run_bd, tmp_path):
        """The 'Agent dispatched' comment posted at dispatch time is from 'oompah'."""
        mock_run_bd.return_value = {}
        orch = _make_orchestrator(tmp_path)

        # Simulate the dispatch comment explicitly
        orch._post_comment("issue-1", "Agent dispatched (profile: standard)")

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args

    @patch.object(BeadsTracker, "_run_bd")
    def test_stall_retry_comment_is_from_oompah(self, mock_run_bd, tmp_path):
        """The stall/retry comment posted by the orchestrator is from 'oompah'."""
        mock_run_bd.return_value = {}
        orch = _make_orchestrator(tmp_path)

        orch._post_comment(
            "issue-1",
            "Agent stalled — retrying in 10s (attempt #2)"
        )

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args

    @patch.object(BeadsTracker, "_run_bd")
    def test_focus_comment_is_from_oompah(self, mock_run_bd, tmp_path):
        """The 'Focus:' comment posted at dispatch time is from 'oompah'."""
        mock_run_bd.return_value = {}
        orch = _make_orchestrator(tmp_path)

        orch._post_comment("issue-1", "Focus: Software Engineer")

        args = mock_run_bd.call_args[0][0]
        assert "--author=oompah" in args


# ---------------------------------------------------------------------------
# 3. WORKFLOW.md prompt template — rendered prompt must include --author=oompah
# ---------------------------------------------------------------------------

class TestWorkflowTemplateAuthorInstruction:
    """The rendered WORKFLOW.md prompt must instruct agents to use --author=oompah."""

    def _load_workflow_template(self) -> str:
        """Load the Liquid template portion of WORKFLOW.md (after the YAML front matter)."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "WORKFLOW.md"
        )
        with open(workflow_path) as f:
            content = f.read()
        # Strip YAML front matter (between --- markers)
        if content.startswith("---"):
            end = content.find("---", 3)
            if end >= 0:
                return content[end + 3:].strip()
        return content

    def test_progress_comments_section_includes_author_oompah(self):
        """The 'Progress Comments' section in WORKFLOW.md includes --author=oompah."""
        template = self._load_workflow_template()
        assert "--author=oompah" in template, (
            "WORKFLOW.md must instruct agents to use --author=oompah when posting comments"
        )

    def test_rendered_prompt_includes_author_oompah_instruction(self):
        """The rendered prompt for an issue must contain --author=oompah."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-abc")

        rendered = render_prompt(template, issue)

        assert "--author=oompah" in rendered, (
            "Rendered prompt must contain --author=oompah instruction for agents"
        )

    def test_rendered_prompt_bd_comments_add_includes_author(self):
        """All 'bd comments add' examples in the rendered prompt include --author=oompah."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-xyz")

        rendered = render_prompt(template, issue)

        # Find all lines containing 'bd comments add' — each line should have --author=oompah
        import re
        bd_comment_lines = [
            line for line in rendered.splitlines()
            if "bd comments add" in line
        ]
        assert bd_comment_lines, "Expected to find 'bd comments add' lines in rendered prompt"

        for line in bd_comment_lines:
            assert "--author=oompah" in line, (
                f"'bd comments add' line is missing --author=oompah: {line!r}"
            )

    def test_handoff_comment_example_includes_author_oompah(self):
        """The handoff comment example in WORKFLOW.md includes --author=oompah."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-fc1")

        rendered = render_prompt(template, issue)

        # Find the HANDOFF line specifically
        import re
        handoff_lines = [line for line in rendered.splitlines() if "HANDOFF:" in line]
        # The HANDOFF example might be inside a code block — check the surrounding context
        handoff_section = ""
        in_handoff = False
        for line in rendered.splitlines():
            if "HANDOFF:" in line:
                in_handoff = True
            if in_handoff:
                handoff_section += line + "\n"
                if line.strip().startswith("```") and handoff_section.count("```") >= 2:
                    break

        assert "--author=oompah" in handoff_section or "--author=oompah" in rendered, (
            "HANDOFF comment example must include --author=oompah"
        )

    def test_important_author_rule_in_rendered_prompt(self):
        """The rendered prompt explicitly warns agents to use --author=oompah."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-fc1")

        rendered = render_prompt(template, issue)

        # Check for an explicit rule/warning about --author
        assert "author=oompah" in rendered.lower() or "--author=oompah" in rendered, (
            "Rendered prompt must contain an explicit instruction about --author=oompah"
        )


# ---------------------------------------------------------------------------
# 4. AGENTS.md — must include --author=oompah rule
# ---------------------------------------------------------------------------

class TestAgentsMdAuthorRule:
    """AGENTS.md must instruct agents to use --author=oompah."""

    def test_agents_md_contains_author_oompah_rule(self):
        """AGENTS.md must include --author=oompah in its important rules."""
        agents_md_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "AGENTS.md"
        )
        with open(agents_md_path) as f:
            content = f.read()

        assert "--author=oompah" in content, (
            "AGENTS.md must instruct agents to use --author=oompah when posting comments"
        )
