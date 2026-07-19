# Agent Instructions

<!-- BEGIN OOMPAH TASK INTEGRATION v:2 -->
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
- Every new task or decomposition child must have an actionable description.
  Include the implementation scope, relevant files or context, required tests,
  and objective acceptance criteria. Never create a title-only task: Oompah
  will not dispatch it, and it blocks its parent epic or task rollup.
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

## Use Makefile Targets

**ALWAYS use Makefile targets** when one exists for the task you're performing. Before running a raw command, check if there's a `make` target that does the same thing. Makefile targets encode project-specific flags, sequences, and conventions that raw commands may miss.

```bash
# Examples:
make start            # NOT: uv run oompah
make restart          # NOT: killing and restarting manually
make graceful         # NOT: sending signals directly
make test             # NOT: pytest directly
```

If unsure whether a target exists, run `make help` or `grep` the Makefile.

## Configuration via .env

**ALL configuration options MUST go in the `.env` file**, not in WORKFLOW.md. WORKFLOW.md defines the workflow structure (tracker settings, agent profiles, prompt template) — all tunable values (concurrency limits, timeouts, thresholds, ports, budget) are set via `OOMPAH_*` environment variables in `.env`. See `.env.example` for the full reference.

## Documentation Rules

- When creating diagrams in documentation, **always use Mermaid** (```mermaid code blocks). Never use ASCII art diagrams.

### Documentation layout

Project docs are split across two top-level directories. Pick the right one when adding new docs.

- **`docs/`** — *user-facing documentation*. Setup guides, troubleshooting, operator how-tos, public API references. Anything someone reading the project to learn how to **use** it would want. Examples: `webhook-forwarding.md` (operator setup + verification).

- **`plans/`** — *design / implementation documentation*. Architecture notes, proposed-but-not-yet-shipped features, internal mechanism inventories, experimental design records. Anything someone reading the project to learn how it **works inside**, or how it **might work in the future**, would want. Examples: `acp-agent.md`, `agent-watcher.md`, `multimodal-attachments.md`, `polling-mechanisms.md`, `submit-queue.md`.

Quick test: if the doc tells the reader "what to do with oompah," it goes in `docs/`. If it tells them "what oompah does inside, or what it should do," it goes in `plans/`. When in doubt, lean toward `plans/` — user-facing docs are rare; design docs are common. (Recorded in oompah-zlz_2-wgr.)

## Test Coverage Required

**ALL code changes MUST be covered by tests.** Do not submit code without corresponding test coverage.

- New functions/methods require unit tests
- Bug fixes require a test that reproduces the bug
- Run `make test` before committing to verify tests pass
- Tests go in `tests/` following existing patterns (pytest, unittest.mock)

## Commit Attribution

All commits authored by an agent in this project MUST end with exactly this trailer block:

```
🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
```

Do NOT add `Co-Authored-By: Claude <noreply@anthropic.com>`, `Co-Authored-By: GPT-…`, or any other model/vendor attribution. The codebase author is oompah — the underlying model is an implementation detail. GitHub renders `Co-authored-by` as a profile link via the email address, and we want that link to resolve to the project's bot account (the `lesserevil` GitHub profile that owns `lesserevil@users.noreply.github.com`).

A `prepare-commit-msg` hook is installed into every agent worktree (see `oompah/git_hooks/prepare-commit-msg`, wired from `oompah/projects.py`). The hook is a safety net — it strips any model-attribution trailer it finds and stamps the canonical trailer — but the primary expectation is that you write commits with the correct trailer in the first place.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var
