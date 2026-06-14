"""Tests verifying the GitHub issue intake workflow documentation.

Covers:
- docs/github-issue-intake.md exists and contains the required guidance sections
- AGENTS.md uses GitHub Issues as the canonical tracker (not Backlog.md)
- The Proposed → Backlog → Open intake flow is documented
"""

from __future__ import annotations

import os
import re

import pytest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_doc(relpath: str) -> str:
    """Read a repo-relative file and return its text content."""
    return open(os.path.join(REPO_ROOT, relpath), encoding="utf-8").read()


# ===========================================================================
# docs/github-issue-intake.md — existence and content checks
# ===========================================================================


class TestGitHubIssueIntakeDoc:
    """docs/github-issue-intake.md must exist and cover the intake flow."""

    @pytest.fixture(autouse=True)
    def doc(self):
        path = os.path.join(REPO_ROOT, "docs", "github-issue-intake.md")
        if not os.path.isfile(path):
            pytest.fail(
                "docs/github-issue-intake.md is missing — "
                "the GitHub issue intake workflow is not documented"
            )
        self._content = open(path, encoding="utf-8").read()

    def test_covers_proposed_status(self):
        """Must document the Proposed intake status."""
        assert "Proposed" in self._content, (
            "docs/github-issue-intake.md must mention the Proposed status"
        )

    def test_covers_backlog_status(self):
        """Must document the Backlog status as part of the intake flow."""
        assert "Backlog" in self._content, (
            "docs/github-issue-intake.md must mention the Backlog status"
        )

    def test_covers_open_status(self):
        """Must document the Open (dispatchable) status."""
        assert "Open" in self._content, (
            "docs/github-issue-intake.md must mention the Open status"
        )

    def test_documents_authorization_model(self):
        """Must explain who can advance an issue through the intake flow."""
        assert any(
            kw in self._content
            for kw in ("authorized", "Authorized", "authorization", "Authorization")
        ), (
            "docs/github-issue-intake.md must document who is authorized to "
            "advance issues through intake"
        )

    def test_documents_status_label_prefix(self):
        """Must reference oompah:status:* labels so readers know how status is encoded."""
        assert "oompah:status:" in self._content, (
            "docs/github-issue-intake.md must reference oompah:status:* labels"
        )

    def test_documents_proposed_to_open_flow(self):
        """Must describe the progression from Proposed through to Open."""
        content = self._content
        # All three status names must appear and Proposed must precede Open.
        proposed_pos = content.find("Proposed")
        open_pos = content.find("Open")
        assert proposed_pos != -1 and open_pos != -1, (
            "Both 'Proposed' and 'Open' must appear in the intake doc"
        )
        assert proposed_pos < open_pos, (
            "'Proposed' must appear before 'Open' in the intake doc to reflect "
            "the intake progression"
        )

    def test_documents_validation_before_backlog(self):
        """Must make validation the gate before Backlog."""
        content = self._content.lower()
        validation_pos = content.find("intake validation")
        backlog_pos = content.find("oompah:status:backlog", validation_pos)
        assert validation_pos != -1, (
            "docs/github-issue-intake.md must document intake validation"
        )
        assert backlog_pos != -1, (
            "docs/github-issue-intake.md must document Backlog promotion"
        )
        assert validation_pos < backlog_pos, (
            "validation must be described before Backlog promotion"
        )

    def test_documents_owner_open_transition(self):
        """Must state that a project owner moves Backlog work to Open."""
        content = self._content.lower()
        assert "owner" in content and "open" in content, (
            "docs/github-issue-intake.md must document owner advancement to Open"
        )

    def test_no_ascii_art_diagrams(self):
        """Diagrams must use Mermaid, not ASCII art."""
        ascii_art_indicators = [
            "+--",
            "--|",
            "-->",
            "==>",
            "| (",
            "+-+",
        ]
        # Mermaid blocks are allowed; ASCII art outside code blocks is not.
        # Heuristic: look for ASCII art patterns outside of mermaid/code fences.
        lines = self._content.splitlines()
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
            if not in_code_block:
                # None of these ASCII art ladder patterns should appear outside a block
                for pattern in ["+--+", "| --- |"]:
                    assert pattern not in line, (
                        f"Possible ASCII art diagram in docs/github-issue-intake.md "
                        f"(use Mermaid instead): {line!r}"
                    )

    def test_uses_mermaid_for_diagrams(self):
        """The intake flow diagram must use a Mermaid code block."""
        assert "```mermaid" in self._content, (
            "docs/github-issue-intake.md must use a Mermaid diagram (```mermaid) "
            "for the intake workflow illustration"
        )

    def test_documents_filing_requirements(self):
        """Must describe what information is required when filing an issue."""
        content = self._content.lower()
        assert any(
            kw in content
            for kw in ("required", "description", "title", "issue type", "information")
        ), (
            "docs/github-issue-intake.md must describe what information is "
            "required when filing a GitHub issue"
        )


# ===========================================================================
# AGENTS.md — must use GitHub Issues, not Backlog.md as primary tracker
# ===========================================================================


class TestAgentsMdGitHubIssuesGuidance:
    """AGENTS.md must instruct agents to use GitHub Issues, not Backlog.md."""

    @pytest.fixture(autouse=True)
    def content(self):
        agents_path = os.path.join(REPO_ROOT, "AGENTS.md")
        if not os.path.isfile(agents_path):
            pytest.fail("AGENTS.md is missing from the repository root")
        self._content = open(agents_path, encoding="utf-8").read()

    def test_has_github_issues_integration_block(self):
        """AGENTS.md must contain the OOMPAH GITHUB ISSUES INTEGRATION block."""
        assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" in self._content, (
            "AGENTS.md must contain the GitHub Issues integration block "
            "(BEGIN OOMPAH GITHUB ISSUES INTEGRATION). "
            "Run ensure_github_issues_agent_instructions() to install it."
        )

    def test_instructs_use_oompah_task_cli(self):
        """AGENTS.md must instruct agents to use the oompah task CLI."""
        assert "oompah task" in self._content, (
            "AGENTS.md must tell agents to use the oompah task CLI for "
            "GitHub-backed work"
        )

    def test_does_not_use_backlog_md_as_primary_tracker(self):
        """AGENTS.md must not tell agents that Backlog.md is the active tracker."""
        # These phrases indicate that Backlog.md is the primary tracker.
        forbidden_phrases = [
            "This project uses **Backlog.md** for issue tracking",
            "Use Backlog.md for ALL task tracking",
            "backlog task list --plain",
            "backlog board --plain",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in self._content, (
                f"AGENTS.md must not contain the legacy Backlog.md instruction: "
                f"{phrase!r}"
            )

    def test_explicitly_forbids_backlog_cli_for_new_work(self):
        """AGENTS.md must explicitly tell agents NOT to use the backlog CLI."""
        # Matches with or without markdown bold emphasis (**not**)
        assert "backlog` CLI for task tracking" in self._content or \
               "create or edit Backlog.md task files" in self._content, (
            "AGENTS.md must explicitly tell agents not to use the backlog CLI "
            "or create Backlog.md task files"
        )

    def test_includes_oompah_task_set_status_done(self):
        """AGENTS.md must show agents how to close a task via oompah task set-status."""
        assert "oompah task set-status" in self._content, (
            "AGENTS.md must include oompah task set-status for closing tasks"
        )


# ===========================================================================
# Cutover and README guidance — must point operators at GitHub issue intake
# ===========================================================================


class TestCutoverWorkflowGuidance:
    """Cutover docs must explain what happens to new GitHub issues."""

    @pytest.fixture(autouse=True)
    def content(self):
        self._content = _read_doc("docs/cutover-workflow.md")

    def test_links_to_intake_workflow(self):
        """The cutover workflow must link to the GitHub issue intake doc."""
        assert "docs/github-issue-intake.md" in self._content, (
            "docs/cutover-workflow.md must link to docs/github-issue-intake.md"
        )

    def test_documents_post_cutover_proposed_flow(self):
        """Post-cutover user-filed issues must start at Proposed."""
        content = self._content
        assert "Proposed" in content and "intake validation" in content, (
            "docs/cutover-workflow.md must mention Proposed intake and "
            "intake validation after GitHub Issues cutover"
        )
        assert "Backlog" in content and "Open" in content, (
            "docs/cutover-workflow.md must mention Backlog and owner Open "
            "promotion after intake"
        )


class TestReadmeTrackerGuidance:
    """README tracker guidance must not present Backlog.md as the only path."""

    @pytest.fixture(autouse=True)
    def content(self):
        self._content = _read_doc("README.md")

    def test_lists_github_issues_as_supported_tracker(self):
        """README must name GitHub Issues in the tracker overview."""
        assert "GitHub Issues" in self._content, (
            "README.md must list GitHub Issues as a supported tracker"
        )

    def test_tracker_kind_reference_includes_github_issues(self):
        """README config reference must include tracker.kind=github_issues."""
        assert "github_issues" in self._content, (
            "README.md must document tracker.kind=github_issues"
        )

    def test_project_setup_marks_backlog_as_legacy(self):
        """README project setup must mark Backlog.md as legacy, not primary."""
        content = self._content.lower()
        assert "legacy backlog" in content, (
            "README.md must mark Backlog.md project setup as legacy"
        )
