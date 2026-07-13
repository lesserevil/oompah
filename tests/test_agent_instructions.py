from __future__ import annotations

from pathlib import Path

from oompah.agent_instructions import (
    ensure_github_issues_agent_instructions,
    ensure_oompah_task_agent_instructions,
    render_github_issues_agent_instructions,
    render_oompah_task_agent_instructions,
    update_agents_text_for_github_issues,
    update_agents_text_for_oompah_tasks,
)

_DOCS_DIR = Path(__file__).parent.parent / "docs"


def test_update_appends_github_block_to_custom_rules():
    original = """# Project Rules

Keep docs in sync.
"""

    updated, changed = update_agents_text_for_github_issues(original)

    assert changed is True
    assert updated.startswith(original)
    assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" in updated
    assert "oompah task create --project <project-id>" in updated
    assert "oompah task set-status <owner/repo#number> Done" in updated
    assert "Use these commands only after the CLI is installed" in updated
    assert "GitHub Fallback" in updated
    assert "Work is not complete until the code is pushed" in updated


def test_update_replaces_existing_github_block_without_duplicates():
    original, first_changed = update_agents_text_for_github_issues("# Agent Instructions\n")
    assert first_changed is True
    original += "\n## Other Rules\n\nUse Makefile targets.\n"

    updated, changed = update_agents_text_for_github_issues(original)

    assert changed is False
    assert "This project is managed by **oompah**" in updated
    assert "oompah task view <owner/repo#number>" in updated
    assert "uv tool install" in updated
    assert "OOMPAH_SERVER_URL=http://127.0.0.1:<port>" in updated
    assert "## Other Rules" in updated
    assert updated.count("BEGIN OOMPAH GITHUB ISSUES INTEGRATION") == 1
    assert updated.count("This project is managed by **oompah**") == 1


def test_update_replaces_oompah_task_block_with_github_block():
    original, task_changed = update_agents_text_for_oompah_tasks("# Agent Instructions\n")
    assert task_changed is True
    original += "\n## Other Rules\n\nUse Makefile targets.\n"

    updated, changed = update_agents_text_for_github_issues(original)

    assert changed is True
    assert "## Other Rules" in updated
    assert "BEGIN OOMPAH TASK INTEGRATION" not in updated
    assert updated.count("BEGIN OOMPAH GITHUB ISSUES INTEGRATION") == 1
    assert updated.count("This project is managed by **oompah**") == 1


def test_rendered_github_instructions_make_cli_optional_with_fallbacks():
    rendered = render_github_issues_agent_instructions()

    assert "Prefer the `oompah task` CLI only when it is installed" in rendered
    assert "oompah server that manages this project" in rendered
    assert "uv tool install" in rendered
    assert "pipx install" in rendered
    assert "OOMPAH_SERVER_URL=http://127.0.0.1:<port>" in rendered
    assert "oompah task --server http://127.0.0.1:<port>" in rendered
    assert "GitHub Fallback" in rendered
    assert "GitHub's structured sub-issue/parent relationship" in rendered
    assert "`parent:<issue-number>`" in rendered
    assert "GitHub's structured dependency/blocking relationship" in rendered
    assert "`depends-on:<issue-number>`" in rendered
    assert "`Parent: #123`" in rendered
    assert "human context only" in rendered
    assert "not sufficient for oompah rollups" in rendered


def test_rendered_oompah_task_instructions_use_native_markdown_store():
    rendered = render_oompah_task_agent_instructions()

    assert "BEGIN OOMPAH TASK INTEGRATION" in rendered
    assert "native Markdown task manager" in rendered
    assert "under\n`.oompah/tasks`" in rendered
    assert "standalone task CLI only" in rendered
    assert "does not install the oompah service runtime" in rendered
    assert "uv tool install" in rendered
    assert "uv pip install -e '.[server]'" in rendered
    assert "GitHub Issues are customer-facing intake" in rendered
    assert "Do not decompose work in GitHub" in rendered
    assert "OOMPAH_SERVER_URL=\"${OOMPAH_SERVER_URL:-http://127.0.0.1:<port>}\"" in rendered
    assert "oompah task view <task-id> --project <project-id>" in rendered
    assert "oompah task set-status <task-id> Done --project <project-id>" in rendered
    assert "Work is not complete until the code is pushed" in rendered
    assert "GitHub Fallback" not in rendered


def test_rendered_oompah_task_instructions_allow_untracked_design_plans():
    rendered = render_oompah_task_agent_instructions()

    assert "Planning Does Not Require a Task" in rendered
    assert "captured in `plans/` without creating a corresponding" in rendered
    assert "they are not task trackers" in rendered
    assert "when implementation work is accepted" in rendered
    assert "does not prohibit design documents in `plans/`" in rendered


def test_rendered_oompah_task_instructions_describe_release_addendums():
    rendered = render_oompah_task_agent_instructions()

    assert "### Release Addendums" in rendered
    assert "default branch first" in rendered
    assert "Do not create, assign, or work\na child backport task" in rendered
    assert "docs/release-addendums.md" in rendered


def test_update_oompah_task_replaces_github_block():
    original, changed = update_agents_text_for_github_issues("# Rules\n")
    assert changed is True

    updated, native_changed = update_agents_text_for_oompah_tasks(original)

    assert native_changed is True
    assert "BEGIN OOMPAH TASK INTEGRATION" in updated
    assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" not in updated
    assert "GitHub Fallback" not in updated
    assert "`.oompah/tasks`" in updated


def test_update_oompah_task_appends_to_custom_rules():
    original = """# Agent Instructions

## Other Rules

Use Makefile targets.
"""

    updated, changed = update_agents_text_for_oompah_tasks(original)

    assert changed is True
    assert updated.startswith(original)
    assert "BEGIN OOMPAH TASK INTEGRATION" in updated
    assert "oompah task view <task-id> --project <project-id>" in updated
    assert "## Other Rules" in updated
    assert updated.count("BEGIN OOMPAH TASK INTEGRATION") == 1


def test_update_oompah_task_replaces_legacy_bootstrap_github_section():
    original = """# Agent Instructions

## Issue Tracking with GitHub Issues

This project uses **GitHub Issues** for ALL task tracking.

Do not use Backlog.md, the `backlog` CLI, `bd`, beads, TodoWrite,
TaskCreate, standalone markdown TODO lists, or another tracker for
project work.

## Documentation must match code

Docs are part of the contract.
"""

    updated, changed = update_agents_text_for_oompah_tasks(original)

    assert changed is True
    assert "BEGIN OOMPAH TASK INTEGRATION" in updated
    assert "This project uses **GitHub Issues** for ALL task tracking" not in updated
    assert "Do not use Backlog.md" not in updated
    assert "## Documentation must match code" in updated
    assert "Docs are part of the contract." in updated


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

Use oompah-managed tasks.
""",
        encoding="utf-8",
    )

    changed = ensure_github_issues_agent_instructions(tmp_path)

    assert changed is True
    text = agents.read_text(encoding="utf-8")
    assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" in text
    assert "Use oompah-managed tasks." in text


def test_ensure_updates_agents_file_for_oompah_tasks(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """# Rules

<!-- BEGIN OOMPAH GITHUB ISSUES INTEGRATION -->
Use GitHub Issues.
<!-- END OOMPAH GITHUB ISSUES INTEGRATION -->
""",
        encoding="utf-8",
    )

    changed = ensure_oompah_task_agent_instructions(tmp_path)

    assert changed is True
    text = agents.read_text(encoding="utf-8")
    assert "BEGIN OOMPAH TASK INTEGRATION" in text
    assert "Use GitHub Issues." not in text


# ---------------------------------------------------------------------------
# Shared-only epic workflow: generated guidance contains no stale references
# ---------------------------------------------------------------------------


def test_oompah_task_instructions_no_flat_or_stacked_strategy():
    """Generated oompah task AGENTS.md block must not reference the
    removed flat or stacked epic strategies."""
    rendered = render_oompah_task_agent_instructions()

    assert "flat" not in rendered.lower().replace("platform", "").replace("scaffold", ""), (
        "Generated oompah task instructions must not mention the removed 'flat' epic strategy."
    )
    assert "stacked" not in rendered.lower(), (
        "Generated oompah task instructions must not mention the removed 'stacked' epic strategy."
    )
    assert "epic_strategy" not in rendered, (
        "Generated oompah task instructions must not expose the internal epic_strategy field."
    )


def test_github_issues_instructions_no_flat_or_stacked_strategy():
    """Generated GitHub Issues AGENTS.md block must not reference the
    removed flat or stacked epic strategies."""
    rendered = render_github_issues_agent_instructions()

    assert "stacked" not in rendered.lower(), (
        "Generated GitHub Issues instructions must not mention the removed 'stacked' epic strategy."
    )
    assert "epic_strategy" not in rendered, (
        "Generated GitHub Issues instructions must not expose the internal epic_strategy field."
    )


def test_task_epic_workflow_doc_describes_shared_only_behavior():
    """docs/task-epic-workflow.md must describe the shared epic workflow
    and must not present flat or stacked as current strategies."""
    doc = (_DOCS_DIR / "task-epic-workflow.md").read_text(encoding="utf-8")

    # Shared workflow must be described
    assert "shared" in doc.lower(), (
        "task-epic-workflow.md must describe the shared epic branch workflow."
    )
    assert "epic branch" in doc.lower(), (
        "task-epic-workflow.md must reference the epic branch."
    )

    # Flat and stacked must not appear as current strategies
    # (they may appear only in historical/migration prose if ever needed,
    #  but the active section must not present them as valid choices)
    lines_with_flat = [
        line for line in doc.splitlines()
        if "| `flat`" in line or "Strategy -- flat" in line or "-- flat -->" in line
    ]
    assert not lines_with_flat, (
        f"task-epic-workflow.md must not have active 'flat' strategy rows: {lines_with_flat}"
    )

    lines_with_stacked = [
        line for line in doc.splitlines()
        if "| `stacked`" in line or "Strategy -- stacked" in line or "-- stacked -->" in line
    ]
    assert not lines_with_stacked, (
        f"task-epic-workflow.md must not have active 'stacked' strategy rows: {lines_with_stacked}"
    )


# ---------------------------------------------------------------------------
# Release addendum: generated guidance in both AGENTS.md variants
# ---------------------------------------------------------------------------


def test_rendered_github_issues_instructions_describe_release_addendums():
    """GitHub Issues variant of AGENTS.md must also describe the
    release-addendum workflow and must not tell agents to create child
    backport tasks."""
    rendered = render_github_issues_agent_instructions()

    assert "### Release Addendums" in rendered, (
        "GitHub Issues AGENTS.md block must include a '### Release Addendums' section."
    )
    assert "default branch first" in rendered, (
        "GitHub Issues AGENTS.md block must state that work lands on the default branch first."
    )
    assert "child backport task" in rendered, (
        "GitHub Issues AGENTS.md block must explicitly prohibit child backport tasks."
    )
    assert "docs/release-addendums.md" in rendered, (
        "GitHub Issues AGENTS.md block must reference docs/release-addendums.md."
    )


# ---------------------------------------------------------------------------
# Release addendum: docs/release-addendums.md content coverage
# ---------------------------------------------------------------------------


def test_release_addendums_doc_covers_operator_workflow():
    """docs/release-addendums.md must cover the full junior-operator
    workflow: configuring lines, queuing, lifecycle, retries, inspection,
    epic snapshots, and migration."""
    doc = (_DOCS_DIR / "release-addendums.md").read_text(encoding="utf-8")

    # Configuring supported release lines
    assert "supported_release_branches" in doc or "Supported Release" in doc, (
        "release-addendums.md must document how to configure supported release lines."
    )

    # Queuing a task for two branches
    assert "target_branches" in doc or "Queue" in doc, (
        "release-addendums.md must explain how to queue a merged task for release branches."
    )

    # Per-branch lifecycle table
    for status in ("open", "in_progress", "in_review", "blocked", "merged", "archived"):
        assert status in doc, (
            f"release-addendums.md must document the '{status}' addendum status."
        )

    # Retries
    assert "retry" in doc.lower(), (
        "release-addendums.md must document how to retry a blocked addendum."
    )

    # Branch inspection
    assert "inspect" in doc.lower() or "Release branches" in doc, (
        "release-addendums.md must document branch inspection."
    )

    # Epic snapshots
    assert "epic" in doc.lower() and "snapshot" in doc.lower(), (
        "release-addendums.md must describe epic addendum snapshots."
    )

    # Migration section
    assert "Migration" in doc or "migration" in doc, (
        "release-addendums.md must include a migration section."
    )

    # Mermaid diagram present
    assert "```mermaid" in doc, (
        "release-addendums.md must include at least one Mermaid diagram."
    )

    # No active instructions to create child backport tasks
    # (historical references are allowed in migration section)
    migration_start = doc.lower().find("migration")
    pre_migration = doc[:migration_start] if migration_start != -1 else doc
    assert "create" not in pre_migration.lower() or "child backport" not in pre_migration.lower(), (
        "release-addendums.md must not instruct users to create child backport tasks "
        "outside the historical migration section."
    )
