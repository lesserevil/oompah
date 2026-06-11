from __future__ import annotations

from oompah.agent_instructions import (
    ensure_github_issues_agent_instructions,
    update_agents_text_for_github_issues,
)


def test_update_replaces_backlog_integration_block():
    original = """# Project Rules

Keep docs in sync.

<!-- BEGIN BACKLOG INTEGRATION v:1 profile:minimal -->
## Backlog Task Tracker

Use Backlog.md for ALL task tracking.

```bash
backlog task create "Follow-up" --plain
```
<!-- END BACKLOG INTEGRATION -->
"""

    updated, changed = update_agents_text_for_github_issues(original)

    assert changed is True
    assert "BEGIN BACKLOG INTEGRATION" not in updated
    assert "Backlog Task Tracker" not in updated
    assert "backlog task create" not in updated
    assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" in updated
    assert "oompah task create --project <project-id>" in updated
    assert "oompah task set-status <owner/repo#number> Done" in updated
    assert "Work is not complete until the code is pushed" in updated


def test_update_replaces_top_level_backlog_quick_reference():
    original = """# Agent Instructions

This project uses **Backlog.md** for issue tracking. Do **not** use `bd`
(beads) as the task tracker for this project.

## Quick Reference

```bash
backlog task list --plain                     # Find available work
backlog task view TASK-123 --plain            # View task details
backlog task edit TASK-123 --status "In Progress" --plain
backlog task edit TASK-123 --status Done --plain
backlog board --plain                         # Show the task board
```

## Other Rules

Use Makefile targets.
"""

    updated, changed = update_agents_text_for_github_issues(original)

    assert changed is True
    assert "This project uses **Backlog.md**" not in updated
    assert "backlog task list --plain" not in updated
    assert "This project is managed by **oompah**" in updated
    assert "oompah task view <owner/repo#number>" in updated
    assert "## Other Rules" in updated
    assert updated.count("BEGIN OOMPAH GITHUB ISSUES INTEGRATION") == 1
    assert updated.count("This project is managed by **oompah**") == 1


def test_update_replaces_top_backlog_reference_without_duplicate_managed_block():
    original = """# Agent Instructions

This project uses **Backlog.md** for issue tracking. Do **not** use `bd`
(beads) as the task tracker for this project.

## Quick Reference

```bash
backlog task list --plain                     # Find available work
backlog task view TASK-123 --plain            # View task details
backlog task edit TASK-123 --status "In Progress" --plain
backlog task edit TASK-123 --status Done --plain
backlog board --plain                         # Show the task board
```

## Other Rules

Use Makefile targets.

<!-- BEGIN BACKLOG INTEGRATION -->
## Issue Tracking with Backlog.md

Use Backlog.md for ALL task tracking.
<!-- END BACKLOG INTEGRATION -->
"""

    updated, changed = update_agents_text_for_github_issues(original)

    assert changed is True
    assert "This project uses **Backlog.md**" not in updated
    assert "Use Backlog.md for ALL task tracking" not in updated
    assert "backlog task list --plain" not in updated
    assert "## Other Rules" in updated
    assert updated.count("BEGIN OOMPAH GITHUB ISSUES INTEGRATION") == 1
    assert updated.count("This project is managed by **oompah**") == 1


def test_update_existing_github_block_is_idempotent():
    original, changed = update_agents_text_for_github_issues("# Rules\n")
    assert changed is True

    updated, changed_again = update_agents_text_for_github_issues(original)

    assert changed_again is False
    assert updated.count("BEGIN OOMPAH GITHUB ISSUES INTEGRATION") == 1


def test_ensure_updates_agents_file(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """# Rules

<!-- BEGIN BACKLOG INTEGRATION -->
Use Backlog.md.
<!-- END BACKLOG INTEGRATION -->
""",
        encoding="utf-8",
    )

    changed = ensure_github_issues_agent_instructions(tmp_path)

    assert changed is True
    text = agents.read_text(encoding="utf-8")
    assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" in text
    assert "Use Backlog.md." not in text
