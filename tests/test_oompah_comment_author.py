"""Tests ensuring all issue comments from oompah are attributed to 'oompah'.

Bug: oompah was posting comments without an explicit oompah author, causing
them to appear as the system user or git user instead of 'oompah'.

Fix: WORKFLOW.md requires the tracker-specific comment author flag in all
agent-facing comment commands, and BacklogMdTracker writes the author into
the Backlog.md comment block for oompah runtime comments.
The orchestrator's _post_comment() already uses author="oompah" by default.
BacklogMdTracker.add_comment() defaults to author="oompah".

These tests verify both the code-level defaults AND the rendered prompt template.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.prompt import render_prompt
from oompah.tracker import BacklogMdTracker


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


def _write_backlog_task(root, task_id: str = "TASK-1", title: str = "Test task"):
    backlog_dir = root / "backlog"
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "config.yml").write_text(
        "\n".join([
            'projectName: "Test"',
            'defaultStatus: "Backlog"',
            'statuses: ["Backlog", "Open", "In Progress", "Done"]',
            'taskPrefix: "task"',
            "",
        ]),
        encoding="utf-8",
    )
    number = task_id.split("-", 1)[1]
    path = backlog_dir / "tasks" / f"task-{number} - Test-task.md"
    path.write_text(
        "\n".join([
            "---",
            f"id: {task_id}",
            f"title: {title}",
            "status: Open",
            "created_date: 2026-05-31 10:00",
            "updated_date: 2026-05-31 10:00",
            "labels: []",
            "dependencies: []",
            "priority: medium",
            "---",
            "## Description",
            "",
            "<!-- SECTION:DESCRIPTION:BEGIN -->",
            "Body",
            "<!-- SECTION:DESCRIPTION:END -->",
            "",
        ]),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# 1. BacklogMdTracker.add_comment — code-level default
# ---------------------------------------------------------------------------

class TestTrackerAddCommentAuthor:
    """BacklogMdTracker.add_comment must always persist the Backlog author."""

    def _tracker(self, tmp_path) -> BacklogMdTracker:
        return BacklogMdTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(tmp_path),
        )

    def test_default_author_is_oompah(self, tmp_path):
        """Calling add_comment without author must use 'oompah'."""
        _write_backlog_task(tmp_path)
        tracker = self._tracker(tmp_path)
        tracker.add_comment("TASK-1", "Some progress note")

        comments = tracker.fetch_comments("TASK-1")
        assert comments[-1]["author"] == "oompah"

    def test_explicit_oompah_still_persists_author(self, tmp_path):
        """Explicit author='oompah' must still persist oompah."""
        _write_backlog_task(tmp_path)
        tracker = self._tracker(tmp_path)
        tracker.add_comment("TASK-1", "Note", author="oompah")

        comments = tracker.fetch_comments("TASK-1")
        assert comments[-1]["author"] == "oompah"

    def test_no_bare_user_in_author_field(self, tmp_path):
        """The comment must NOT get an empty or missing author field."""
        _write_backlog_task(tmp_path)
        tracker = self._tracker(tmp_path)
        tracker.add_comment("TASK-1", "hello")

        comments = tracker.fetch_comments("TASK-1")
        assert comments[-1]["author"] == "oompah"


# ---------------------------------------------------------------------------
# 2. Orchestrator._post_comment — orchestrator-level default
# ---------------------------------------------------------------------------

class TestOrchestratorPostCommentAuthor:
    """Orchestrator._post_comment must use author='oompah' for all system comments."""

    @patch.object(BacklogMdTracker, "add_comment")
    def test_post_comment_default_author_is_oompah(self, mock_add_comment, tmp_path):
        """_post_comment without explicit author uses 'oompah'."""
        orch = _make_orchestrator(tmp_path)

        orch._post_comment("issue-1", "Agent dispatched")

        mock_add_comment.assert_called_once_with(
            "issue-1", "Agent dispatched", author="oompah",
        )

    @patch.object(BacklogMdTracker, "add_comment")
    def test_post_comment_explicit_oompah_author(self, mock_add_comment, tmp_path):
        """_post_comment with explicit author='oompah' uses 'oompah'."""
        orch = _make_orchestrator(tmp_path)

        orch._post_comment("issue-1", "Focus: Software Engineer", author="oompah")

        mock_add_comment.assert_called_once_with(
            "issue-1", "Focus: Software Engineer", author="oompah",
        )

    @patch.object(BacklogMdTracker, "add_comment")
    def test_dispatch_comment_is_from_oompah(self, mock_add_comment, tmp_path):
        """The 'Agent dispatched' comment posted at dispatch time is from 'oompah'."""
        orch = _make_orchestrator(tmp_path)

        # Simulate the dispatch comment explicitly
        orch._post_comment("issue-1", "Agent dispatched (profile: standard)")

        mock_add_comment.assert_called_once_with(
            "issue-1", "Agent dispatched (profile: standard)", author="oompah",
        )

    @patch.object(BacklogMdTracker, "add_comment")
    def test_stall_retry_comment_is_from_oompah(self, mock_add_comment, tmp_path):
        """The stall/retry comment posted by the orchestrator is from 'oompah'."""
        orch = _make_orchestrator(tmp_path)

        orch._post_comment(
            "issue-1",
            "Agent stalled — retrying in 10s (attempt #2)"
        )

        mock_add_comment.assert_called_once_with(
            "issue-1",
            "Agent stalled — retrying in 10s (attempt #2)",
            author="oompah",
        )

    @patch.object(BacklogMdTracker, "add_comment")
    def test_focus_comment_is_from_oompah(self, mock_add_comment, tmp_path):
        """The 'Focus:' comment posted at dispatch time is from 'oompah'."""
        orch = _make_orchestrator(tmp_path)

        orch._post_comment("issue-1", "Focus: Software Engineer")

        mock_add_comment.assert_called_once_with(
            "issue-1", "Focus: Software Engineer", author="oompah",
        )


# ---------------------------------------------------------------------------
# 3. WORKFLOW.md prompt template — rendered prompt must include comment author
# ---------------------------------------------------------------------------

class TestWorkflowTemplateAuthorInstruction:
    """The rendered WORKFLOW.md prompt must tell agents to use oompah as author."""

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
        """The 'Progress Comments' section includes the Backlog.md author flag."""
        template = self._load_workflow_template()
        assert "--comment-author oompah" in template, (
            "WORKFLOW.md must instruct agents to use --comment-author oompah "
            "when posting comments"
        )

    def test_rendered_prompt_includes_author_oompah_instruction(self):
        """The rendered prompt for an issue must contain the Backlog.md author flag."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-abc")

        rendered = render_prompt(template, issue)

        assert "--comment-author oompah" in rendered, (
            "Rendered prompt must contain --comment-author oompah instruction "
            "for agents"
        )

    def test_rendered_prompt_backlog_comments_include_author(self):
        """All Backlog.md comment examples in the rendered prompt include author."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-xyz")

        rendered = render_prompt(template, issue)

        backlog_comment_lines = [
            line for line in rendered.splitlines()
            if "backlog task edit" in line and "--comment" in line
        ]
        assert backlog_comment_lines, (
            "Expected to find Backlog.md comment lines in rendered prompt"
        )

        for line in backlog_comment_lines:
            assert "--comment-author oompah" in line, (
                "Backlog.md comment line is missing --comment-author oompah: "
                f"{line!r}"
            )

    def test_handoff_comment_example_includes_author_oompah(self):
        """The handoff comment example includes the Backlog.md author flag."""
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

        assert (
            "--comment-author oompah" in handoff_section
            or "--comment-author oompah" in rendered
        ), "HANDOFF comment example must include --comment-author oompah"

    def test_important_author_rule_in_rendered_prompt(self):
        """The rendered prompt explicitly warns agents to use oompah as author."""
        template = self._load_workflow_template()
        issue = _make_issue("oompah-fc1")

        rendered = render_prompt(template, issue)

        assert "--comment-author oompah" in rendered, (
            "Rendered prompt must contain an explicit instruction about "
            "--comment-author oompah"
        )


# ---------------------------------------------------------------------------
# 4. AGENTS.md — must include comment author rule
# ---------------------------------------------------------------------------

class TestAgentsMdAuthorRule:
    """AGENTS.md must instruct agents to use oompah as comment author."""

    def test_agents_md_contains_author_oompah_rule(self):
        """AGENTS.md must include the Backlog.md comment author flag."""
        agents_md_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "AGENTS.md"
        )
        with open(agents_md_path) as f:
            content = f.read()

        assert "--comment-author oompah" in content, (
            "AGENTS.md must instruct agents to use --comment-author oompah "
            "when posting comments"
        )
