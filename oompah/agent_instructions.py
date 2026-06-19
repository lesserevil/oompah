"""Helpers for keeping managed-repo AGENTS.md task instructions current."""

from __future__ import annotations

import re
from pathlib import Path


GITHUB_ISSUES_AGENT_INSTRUCTIONS = """<!-- BEGIN OOMPAH GITHUB ISSUES INTEGRATION v:1 -->
## Issue Tracking with GitHub Issues

This project is managed by **oompah** using **GitHub Issues** as the
canonical task tracker. Do **not** create or edit Backlog.md task files, do
not use the `backlog` CLI for task tracking, and do not use `bd`, beads,
TodoWrite, markdown TODO lists, or another tracker for project work.

Prefer the `oompah task` CLI only when it is installed and configured for the
oompah server that manages this project. The CLI applies the correct GitHub
labels, status mapping, parent/child links, dependencies, and comments.

### Optional CLI Setup

The CLI is distributed from GitHub, not PyPI. Install it with `uv tool` or
`pipx` from a release tag or from `main`, then point it at the local oompah
server:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@<tag>"
pipx install "git+https://github.com/lesserevil/oompah@<tag>"
oompah task --help
OOMPAH_SERVER_URL=http://127.0.0.1:<port> oompah task view <owner/repo#number>
oompah task --server http://127.0.0.1:<port> view <owner/repo#number>
```

### CLI Quick Reference

Use these commands only after the CLI is installed and configured for the
correct server:

```bash
oompah task view <owner/repo#number>
oompah task comment <owner/repo#number> --message "Progress update" --author oompah
oompah task create --project <project-id> --title "Follow-up title" --description "Details" --source <owner/repo#number>
oompah task child-create <owner/repo#number> --title "Child task title" --description "Details"
oompah task set-dependency <owner/repo#number> --depends-on <owner/repo#other-number>
oompah task add-label <owner/repo#number> needs:frontend
oompah task set-status <owner/repo#number> Open
oompah task set-status <owner/repo#number> Done --summary "Completed"
```

### GitHub Fallback

If the CLI is unavailable, use GitHub directly while preserving the structured
metadata oompah needs:

- Create follow-up work as GitHub issues in the configured task hub repository
  and link back to the source issue.
- For epic children, use GitHub's structured sub-issue/parent relationship.
  If that is unavailable, apply the oompah-compatible `parent:<issue-number>`
  label to the child issue.
- For dependencies, use GitHub's structured dependency/blocking relationship.
  If that is unavailable, apply the oompah-compatible
  `depends-on:<issue-number>` label to the blocked issue.
- Body text such as `Parent: #123`, `Depends on #123`, or a task-list item is
  human context only. It is not sufficient for oompah rollups, dispatch, or
  dependency gates.

### Rules

- Always pass `--author oompah` when posting comments through the CLI. In the
  GitHub fallback path, make clear the update is from `oompah`.
- Use `oompah task create --project <project-id>` for follow-up work when the
  CLI is available; otherwise create the GitHub issue with the source link and
  structured metadata described above.
- Use `oompah task child-create <parent>` for epic children when the CLI is
  available; otherwise use GitHub sub-issues or the `parent:*` fallback label.
- Use `oompah task set-dependency` when the CLI is available; otherwise use
  GitHub dependencies or the `depends-on:*` fallback label.
- Do not edit `oompah:status:*`, `type:*`, `priority:*`, `parent:*`, or
  `depends-on:*` labels directly when the CLI or structured GitHub controls are
  available. Use `parent:*` and `depends-on:*` only as compatibility fallbacks.
- Epics use `type:epic`; their effective status is derived from child issue
  status by oompah.
- Existing `backlog/` files are legacy history. Do not add new files there for
  task tracking after GitHub Issues cutover.

## Session Completion

When ending a work session, complete all of these steps:

1. File follow-up issues for remaining work, using `oompah task create` when
   available or the GitHub fallback above.
2. Run the relevant quality gates for the code you changed.
3. Update the current issue status with `oompah task set-status` when
   available, or with the repository's GitHub issue status controls.
4. Push all committed work:
   ```bash
   git pull --rebase
   git push
   git status
   ```
5. Verify `git status` reports the branch is up to date with origin.

Work is not complete until the code is pushed and the GitHub issue is updated
through the CLI or GitHub fallback path. Never leave finished work only in a
local commit.

<!-- END OOMPAH GITHUB ISSUES INTEGRATION -->
"""

OOMPAH_TASK_AGENT_INSTRUCTIONS = """<!-- BEGIN OOMPAH TASK INTEGRATION v:1 -->
## Issue Tracking with Oompah Tasks

This project is managed by **oompah** using native Markdown task files as the
canonical task tracker. Oompah stores task files on the repository's default
branch under `.oompah/tasks/`; feature branches and agent worktrees must not
hand-edit those files. Do **not** create or edit Backlog.md task files, do not
use the `backlog` CLI for task tracking, do not use GitHub Issues as a task
replacement, and do not use `bd`, beads, TodoWrite, markdown TODO lists, or
another tracker for project work.

Use the `oompah task` CLI when it is installed and configured for the oompah
server that manages this project. The CLI applies the correct Markdown file
updates, status mapping, parent/child links, dependencies, and comments on the
default branch.

### Optional CLI Setup

The CLI is distributed from GitHub, not PyPI. Install it with `uv tool` or
`pipx` from a release tag or from `main`, then point it at the local oompah
server:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@<tag>"
pipx install "git+https://github.com/lesserevil/oompah@<tag>"
oompah task --help
OOMPAH_SERVER_URL=http://127.0.0.1:<port> oompah task view <task-id>
oompah task --server http://127.0.0.1:<port> view <task-id>
```

### CLI Quick Reference

Use these commands only after the CLI is installed and configured for the
correct server:

```bash
oompah task view <task-id>
oompah task comment <task-id> --message "Progress update" --author oompah
oompah task create --project <project-id> --title "Follow-up title" --description "Details" --source <task-id>
oompah task child-create <task-id> --title "Child task title" --description "Details"
oompah task set-dependency <task-id> --depends-on <other-task-id>
oompah task add-label <task-id> needs:frontend
oompah task set-status <task-id> Open
oompah task set-status <task-id> Done --summary "Completed"
```

### Rules

- Always pass `--author oompah` when posting comments through the CLI.
- Use `oompah task create --project <project-id>` for follow-up work.
- Use `oompah task child-create <parent>` for epic children.
- Use `oompah task set-dependency` for dependencies.
- Do not hand-edit `.oompah/tasks` from an agent worktree. Oompah updates the
  task store on the default branch so task state does not create feature branch
  merge conflicts.
- Epics use `type: epic`; their effective status is derived from child task
  status by oompah.
- Existing `backlog/` files are legacy history. Do not add new files there for
  task tracking.

## Session Completion

When ending a work session, complete all of these steps:

1. File follow-up tasks for remaining work using `oompah task create`.
2. Run the relevant quality gates for the code you changed.
3. Update the current task status with `oompah task set-status`.
4. Push all committed work:
   ```bash
   git pull --rebase
   git push
   git status
   ```
5. Verify `git status` reports the branch is up to date with origin.

Work is not complete until the code is pushed and the oompah task is updated.
Never leave finished work only in a local commit.

<!-- END OOMPAH TASK INTEGRATION -->
"""


_GITHUB_BLOCK_RE = re.compile(
    r"<!-- BEGIN OOMPAH GITHUB ISSUES INTEGRATION(?: [^>]*)? -->.*?"
    r"<!-- END OOMPAH GITHUB ISSUES INTEGRATION -->",
    re.DOTALL,
)
_OOMPAH_TASK_BLOCK_RE = re.compile(
    r"<!-- BEGIN OOMPAH TASK INTEGRATION(?: [^>]*)? -->.*?"
    r"<!-- END OOMPAH TASK INTEGRATION -->",
    re.DOTALL,
)
_BACKLOG_BLOCK_RE = re.compile(
    r"<!-- BEGIN BACKLOG INTEGRATION(?: [^>]*)? -->.*?"
    r"<!-- END BACKLOG INTEGRATION -->",
    re.DOTALL,
)
_TOP_BACKLOG_QUICK_REF_RE = re.compile(
    r"\n*This project uses \*\*Backlog\.md\*\* for issue tracking\..*?"
    r"## Quick Reference\s*\n\s*```bash\s*\n"
    r"backlog task list --plain.*?"
    r"backlog board --plain.*?"
    r"```\s*\n",
    re.DOTALL,
)


def render_github_issues_agent_instructions() -> str:
    """Return the canonical AGENTS.md GitHub Issues task-tracking block."""

    return GITHUB_ISSUES_AGENT_INSTRUCTIONS


def render_oompah_task_agent_instructions() -> str:
    """Return the canonical AGENTS.md native oompah task-tracking block."""

    return OOMPAH_TASK_AGENT_INSTRUCTIONS


def _replace_managed_task_block(text: str, replacement: str) -> str:
    """Replace any known oompah-managed task block with ``replacement``."""

    updated = text
    for regex in (_OOMPAH_TASK_BLOCK_RE, _GITHUB_BLOCK_RE, _BACKLOG_BLOCK_RE):
        if regex.search(updated):
            return regex.sub(replacement.strip(), updated, count=1)

    suffix = "" if updated.endswith("\n") else "\n"
    return updated + suffix + "\n" + replacement.strip() + "\n"


def update_agents_text_for_github_issues(text: str) -> tuple[str, bool]:
    """Return AGENTS.md text with oompah GitHub Issues instructions installed.

    The updater handles the two common managed-repo shapes:

    * a marker-delimited Backlog integration block generated by oompah;
    * the older top-of-file Backlog quick reference used by oompah itself.

    Unknown custom text is left in place and the canonical GitHub block is
    appended when no managed block exists.
    """

    original = text
    updated = text

    if _TOP_BACKLOG_QUICK_REF_RE.search(updated):
        has_managed_block = bool(
            _OOMPAH_TASK_BLOCK_RE.search(updated)
            or _GITHUB_BLOCK_RE.search(updated)
            or _BACKLOG_BLOCK_RE.search(updated)
        )
        replacement = "\n\n"
        if not has_managed_block:
            replacement = "\n\n" + GITHUB_ISSUES_AGENT_INSTRUCTIONS.strip() + "\n\n"
        updated = _TOP_BACKLOG_QUICK_REF_RE.sub(
            replacement,
            updated,
            count=1,
        )

    updated = _replace_managed_task_block(updated, GITHUB_ISSUES_AGENT_INSTRUCTIONS)

    # Keep a single trailing newline and avoid churn when no semantic change
    # was needed.
    updated = updated.rstrip() + "\n"
    return updated, updated != original


def update_agents_text_for_oompah_tasks(text: str) -> tuple[str, bool]:
    """Return AGENTS.md text with native oompah task instructions installed."""

    original = text
    updated = text

    if _TOP_BACKLOG_QUICK_REF_RE.search(updated):
        has_managed_block = bool(
            _OOMPAH_TASK_BLOCK_RE.search(updated)
            or _GITHUB_BLOCK_RE.search(updated)
            or _BACKLOG_BLOCK_RE.search(updated)
        )
        replacement = "\n\n"
        if not has_managed_block:
            replacement = "\n\n" + OOMPAH_TASK_AGENT_INSTRUCTIONS.strip() + "\n\n"
        updated = _TOP_BACKLOG_QUICK_REF_RE.sub(
            replacement,
            updated,
            count=1,
        )

    updated = _replace_managed_task_block(updated, OOMPAH_TASK_AGENT_INSTRUCTIONS)
    updated = updated.rstrip() + "\n"
    return updated, updated != original


def ensure_github_issues_agent_instructions(repo_path: str | Path) -> bool:
    """Install GitHub Issues task instructions into ``repo_path/AGENTS.md``.

    Returns ``True`` when the file changed, ``False`` when it already matched.
    Missing repositories or missing AGENTS.md files raise ``OSError`` so callers
    can decide whether to make cutover strict or best-effort.
    """

    agents_path = Path(repo_path) / "AGENTS.md"
    text = agents_path.read_text(encoding="utf-8")
    updated, changed = update_agents_text_for_github_issues(text)
    if changed:
        agents_path.write_text(updated, encoding="utf-8")
    return changed


def ensure_oompah_task_agent_instructions(repo_path: str | Path) -> bool:
    """Install native oompah task instructions into ``repo_path/AGENTS.md``."""

    agents_path = Path(repo_path) / "AGENTS.md"
    text = agents_path.read_text(encoding="utf-8")
    updated, changed = update_agents_text_for_oompah_tasks(text)
    if changed:
        agents_path.write_text(updated, encoding="utf-8")
    return changed
