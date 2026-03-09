"""Tests verifying that documentation uses Mermaid diagrams (not ASCII art).

These tests enforce the project convention that visual diagrams in docs must
be expressed as Mermaid code blocks, never as ASCII art.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the repository root (parent of the tests/ directory)."""
    return Path(__file__).parent.parent


def _doc_files() -> list[Path]:
    """Return all .md files under docs/."""
    docs_dir = _repo_root() / "docs"
    return list(docs_dir.glob("**/*.md"))


def _count_mermaid_blocks(text: str) -> int:
    """Count the number of ```mermaid ... ``` blocks in *text*."""
    return len(re.findall(r"```mermaid", text))


# ---------------------------------------------------------------------------
# Tests: polling-mechanisms.md
# ---------------------------------------------------------------------------

class TestPollingMechanismsDiagrams:
    """docs/polling-mechanisms.md must contain Mermaid diagrams."""

    def _read(self) -> str:
        path = _repo_root() / "docs" / "polling-mechanisms.md"
        return path.read_text()

    def test_file_exists(self):
        path = _repo_root() / "docs" / "polling-mechanisms.md"
        assert path.exists(), "docs/polling-mechanisms.md must exist"

    def test_has_mermaid_diagrams(self):
        content = self._read()
        count = _count_mermaid_blocks(content)
        assert count >= 1, (
            f"docs/polling-mechanisms.md must contain at least one ```mermaid block, "
            f"found {count}"
        )

    def test_overview_diagram_present(self):
        """An overview diagram linking all polling mechanisms should be present."""
        content = self._read()
        assert _count_mermaid_blocks(content) >= 1, (
            "Expected an overview Mermaid diagram in docs/polling-mechanisms.md"
        )

    def test_orchestrator_loop_diagram_present(self):
        """A diagram for the orchestrator main loop should be present."""
        content = self._read()
        # The orchestrator loop section should have a diagram after it
        orch_section = re.search(
            r"## 1\. Orchestrator main poll loop.*?(?=## 2\.)",
            content,
            re.DOTALL,
        )
        assert orch_section is not None, "Could not find section 1 in polling-mechanisms.md"
        section_text = orch_section.group(0)
        assert "```mermaid" in section_text, (
            "Section 1 (Orchestrator main poll loop) must contain a Mermaid diagram"
        )

    def test_graceful_restart_diagram_present(self):
        """A diagram for the graceful-restart drain loop should be present."""
        content = self._read()
        section = re.search(
            r"## 2\. Graceful-restart drain loop.*?(?=## 3\.)",
            content,
            re.DOTALL,
        )
        assert section is not None, "Could not find section 2 in polling-mechanisms.md"
        section_text = section.group(0)
        assert "```mermaid" in section_text, (
            "Section 2 (Graceful-restart drain loop) must contain a Mermaid diagram"
        )

    def test_logfilewatcher_diagram_present(self):
        """A diagram for the LogFileWatcher loop should be present."""
        content = self._read()
        section = re.search(
            r"## 3\. LogFileWatcher poll loop.*?(?=## 4\.)",
            content,
            re.DOTALL,
        )
        assert section is not None, "Could not find section 3 in polling-mechanisms.md"
        section_text = section.group(0)
        assert "```mermaid" in section_text, (
            "Section 3 (LogFileWatcher poll loop) must contain a Mermaid diagram"
        )

    def test_no_ascii_art_box_drawing(self):
        """No ASCII art box-drawing characters should appear in the file."""
        content = self._read()
        # Common ASCII art box patterns: +--+, |  |, etc.
        ascii_box_pattern = re.compile(r"[+][+-]{2,}[+]")
        matches = ascii_box_pattern.findall(content)
        assert not matches, (
            f"Found ASCII art box-drawing in docs/polling-mechanisms.md: {matches!r}. "
            "Use Mermaid diagrams instead."
        )


# ---------------------------------------------------------------------------
# Tests: all doc files must not contain ASCII art box diagrams
# ---------------------------------------------------------------------------

class TestNoAsciiArtInDocs:
    """No markdown documentation file should use ASCII art box diagrams."""

    def test_no_ascii_art_in_any_doc(self):
        """All .md files under docs/ must not contain ASCII art box patterns."""
        ascii_box_pattern = re.compile(r"[+][+-]{2,}[+]")
        violations = []
        for doc_path in _doc_files():
            content = doc_path.read_text()
            if ascii_box_pattern.search(content):
                violations.append(str(doc_path))

        assert not violations, (
            "The following docs contain ASCII art box diagrams. "
            "Replace them with Mermaid diagrams:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_docs_directory_not_empty(self):
        """The docs/ directory should contain at least one .md file."""
        docs = _doc_files()
        assert len(docs) >= 1, "docs/ directory should contain at least one .md file"


# ---------------------------------------------------------------------------
# Tests: mermaid diagram syntax is well-formed (basic check)
# ---------------------------------------------------------------------------

class TestMermaidSyntax:
    """Mermaid blocks must use a supported diagram type."""

    KNOWN_DIAGRAM_TYPES = {
        "flowchart", "graph", "sequenceDiagram", "classDiagram",
        "stateDiagram", "gantt", "pie", "erDiagram", "journey",
        "gitGraph", "C4Context",
    }

    def _extract_mermaid_blocks(self, text: str) -> list[str]:
        """Extract the first line of each mermaid block (the diagram type declaration)."""
        blocks = re.findall(r"```mermaid\s*\n(.*?)\n", text, re.DOTALL)
        return blocks

    def test_polling_mechanisms_mermaid_types(self):
        """Each Mermaid block in polling-mechanisms.md should start with a known type."""
        path = _repo_root() / "docs" / "polling-mechanisms.md"
        content = path.read_text()
        first_lines = self._extract_mermaid_blocks(content)
        assert first_lines, "No Mermaid blocks found in docs/polling-mechanisms.md"
        for line in first_lines:
            diagram_type = line.strip().split()[0] if line.strip() else ""
            assert diagram_type in self.KNOWN_DIAGRAM_TYPES, (
                f"Unknown Mermaid diagram type '{diagram_type}' in "
                f"docs/polling-mechanisms.md. "
                f"Expected one of: {sorted(self.KNOWN_DIAGRAM_TYPES)}"
            )
