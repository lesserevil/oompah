"""Helpers for keeping managed-repo AGENTS.md task instructions current."""

from __future__ import annotations

import re
from pathlib import Path


GITHUB_ISSUES_AGENT_INSTRUCTIONS = """<!-- BEGIN OOMPAH GITHUB ISSUES INTEGRATION v:1 -->
## Issue Tracking with GitHub Issues

This project is managed by **oompah** using **GitHub Issues** as the
canonical task tracker. Do not use TodoWrite, standalone markdown TODO lists,
or another tracker for project work.

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

### Release Addendums

Ordinary work lands on the project's default branch first. When a merged task
or epic must also be delivered to a supported release line, an operator queues
a release addendum on that original source item. Do not create, assign, or work
a child backport task for new release delivery: addendums retain their own
per-branch lifecycle and remain attached to the merged source task or epic.
See `docs/release-addendums.md` for the operator workflow.

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

OOMPAH_TASK_AGENT_INSTRUCTIONS = """<!-- BEGIN OOMPAH TASK INTEGRATION v:2 -->
## Issue Tracking with oompah

This project is managed by **oompah**. The canonical task tracker is oompah's
native Markdown task manager, stored by oompah on the default branch under
`.oompah/tasks`. Do not use TodoWrite, standalone markdown TODO lists, or
direct GitHub issue edits for internal task tracking.

Use the `oompah task` CLI against the running oompah server. The CLI/API keeps
task status, parent/child relationships, dependencies, comments, and
git-backed `.oompah/tasks` files consistent. Humans and agents may inspect
`.oompah/tasks`, but oompah should be the only writer.

### Planning Does Not Require a Task

Design work may be captured in `plans/` without creating a corresponding
oompah task. Plans describe possible approaches, architecture, or future work;
they are not task trackers and do not imply that the work has been accepted or
scheduled.

Create an oompah task when implementation work is accepted or needs status,
ownership, dependencies, or orchestration. A task may link to a plan instead of
copying the plan into task metadata. Checklists in a plan are specification or
acceptance-criteria aids, not task status. The prohibition on standalone
Markdown TODO lists does not prohibit design documents in `plans/`.

### Release Addendums

Ordinary work lands on the project's default branch first. When a merged task
or epic must also be delivered to a supported release line, an operator queues
a release addendum on that original source item. Do not create, assign, or work
a child backport task for new release delivery: addendums retain their own
per-branch lifecycle and remain attached to the merged source task or epic.
See `docs/release-addendums.md` for the operator workflow.

### Install the Task CLI

The CLI is distributed from GitHub, not PyPI. The default GitHub install is the
standalone task CLI only; it does not install the oompah service runtime, create
service configuration, or start a local service.

Prefer a release tag when one is available:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@<tag>"
pipx install "git+https://github.com/lesserevil/oompah@<tag>"
```

For unreleased development versions, install from `main`:

```bash
uv tool install "git+https://github.com/lesserevil/oompah"
pipx install "git+https://github.com/lesserevil/oompah"
```

Service operators install the server runtime separately from a cloned oompah
repo with `uv pip install -e '.[server]'` or `make setup`; managed-project
contributors should not need that.

### Server Setup

Point the CLI at the oompah service that manages this project:

```bash
export OOMPAH_SERVER_URL="${OOMPAH_SERVER_URL:-http://127.0.0.1:<port>}"
oompah task --help
oompah task view <task-id>
```

### CLI Quick Reference

```bash
oompah task view <task-id> --project <project-id>
oompah task comment <task-id> --project <project-id> --message "Progress update" --author oompah
oompah task create --project <project-id> --title "Follow-up title" --description "Details"
oompah task child-create <task-id> --project <project-id> --title "Child task title" --description "Details"
oompah task set-dependency <task-id> --project <project-id> --depends-on <other-task-id>
oompah task add-label <task-id> needs:frontend --project <project-id>
oompah task set-status <task-id> Open --project <project-id>
oompah task set-status <task-id> Done --project <project-id> --summary "Completed"
```

### GitHub Issue Intake

GitHub Issues are customer-facing intake, not the internal task graph.

- A customer may open or comment on a GitHub issue.
- Oompah validates the GitHub issue in GitHub and asks for missing information
  there.
- Do not decompose work in GitHub. Do not create GitHub sub-issues for oompah
  decomposition.
- Once intake is sound, oompah creates an internal native Markdown task in
  `Proposed` with metadata referencing the external GitHub issue.
- If the work is too large, oompah decomposes the internal task. The imported
  task becomes the internal epic and child tasks are created under
  `.oompah/tasks`.
- Oompah works and tracks the internal task or epic. On state changes, oompah
  comments on the originating GitHub issue.
- Oompah closes the originating GitHub issue when the internal task reaches
  `Merged` or `Archived`.

GitHub comments are copied into the internal task. Comments made by oompah on
GitHub are not copied back into the internal task, and comments made on
internal tasks are not copied to GitHub except for oompah's status-change
comments.

### Rules

- Search existing oompah tasks before creating follow-up work.
- File follow-up work with `oompah task create --project <project-id>`, not
  GitHub Issues.
- Create decomposition children with `oompah task child-create`; do not
  hand-write parent metadata.
- Record blockers with `oompah task set-dependency`; do not hand-write
  dependency metadata.
- Always pass `--author oompah` when posting progress comments through the CLI.
- Do not edit `.oompah/tasks` files directly unless you are repairing a tracker
  bug and have checked with the project owner.
- Do not edit GitHub `oompah:*`, `type:*`, `priority:*`, `parent:*`, or
  `depends-on:*` labels directly.
## Session Completion

When ending a work session, complete all of these steps:

1. File follow-up tasks with `oompah task create` for remaining work.
2. Run the relevant quality gates for the code you changed.
3. Update the current oompah task status or leave a clear handoff comment.
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
_LEGACY_BOOTSTRAP_GITHUB_SECTION_RE = re.compile(
    r"## Issue Tracking with GitHub Issues\n.*?"
    r"(?=\n## (?:Documentation must match code|Use Makefile Targets|Test Coverage Required|Session Completion)|\Z)",
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
    for regex in (_OOMPAH_TASK_BLOCK_RE, _GITHUB_BLOCK_RE):
        if regex.search(updated):
            return regex.sub(replacement.strip(), updated, count=1)

    if _LEGACY_BOOTSTRAP_GITHUB_SECTION_RE.search(updated):
        return _LEGACY_BOOTSTRAP_GITHUB_SECTION_RE.sub(
            replacement.strip() + "\n",
            updated,
            count=1,
        )

    suffix = "" if updated.endswith("\n") else "\n"
    return updated + suffix + "\n" + replacement.strip() + "\n"


def update_agents_text_for_github_issues(text: str) -> tuple[str, bool]:
    """Return AGENTS.md text with oompah GitHub Issues instructions installed.

    Unknown custom text is left in place and the canonical GitHub block is
    appended when no managed block exists.
    """

    original = text
    updated = _replace_managed_task_block(text, GITHUB_ISSUES_AGENT_INSTRUCTIONS)

    # Keep a single trailing newline and avoid churn when no semantic change
    # was needed.
    updated = updated.rstrip() + "\n"
    return updated, updated != original


def update_agents_text_for_oompah_tasks(text: str) -> tuple[str, bool]:
    """Return AGENTS.md text with native oompah task instructions installed."""

    original = text
    updated = _replace_managed_task_block(text, OOMPAH_TASK_AGENT_INSTRUCTIONS)
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
