# Agent Instructions

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

<!-- BEGIN BACKLOG INTEGRATION -->
## Issue Tracking with Backlog.md

**IMPORTANT**: This project uses **Backlog.md** for ALL issue tracking. Do
NOT use `bd`, beads, markdown TODOs, task lists, or other tracking methods.

### Why Backlog.md?

- Markdown-native: tasks live in `backlog/tasks` and `backlog/completed`
- Git-friendly: task state is versioned as normal project files
- Dependency-aware: parent tasks and blockers are stored in task frontmatter
- Agent-friendly: `--plain` output avoids interactive UI where supported
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
backlog task list --status "To Do" --plain
backlog task list --status "In Progress" --plain
```

**Create new issues:**

```bash
backlog task create "Issue title" --description "Detailed context" --priority medium --plain
backlog task create "Child task" --description "Details" --parent TASK-123 --plain
backlog task create "Blocked task" --description "Details" --depends-on TASK-123 --plain
```

**Claim and update:**

```bash
backlog task edit TASK-123 --status "In Progress" --assignee oompah --plain
backlog task edit TASK-123 --priority high --plain
backlog task edit TASK-123 --comment "Progress update" --comment-author oompah --plain
```

**Complete work:**

```bash
backlog task edit TASK-123 --status Done --final-summary "Completed" --plain
```

### Issue Types

Backlog.md tasks use labels for issue type:

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

Add or remove labels with:

```bash
backlog task edit TASK-123 --add-label bug --plain
backlog task edit TASK-123 --remove-label bug --plain
```

### Priorities

- `high` - Critical or important work
- `medium` - Default priority
- `low` - Polish, optimization, or future ideas

### Workflow for AI Agents

1. **Check ready work**: `backlog task list --status "To Do" --plain`
   shows available tasks
2. **Claim your task**: set status to `In Progress` and assign it to `oompah`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create a linked task:
   - Use `--parent TASK-123` for child work
   - Use `--depends-on TASK-123` for blocked work
5. **Complete**: set status to `Done` and add a final summary

### Storage

Backlog.md stores tasks as markdown files:

- Active tasks: `backlog/tasks/*.md`
- Completed tasks: `backlog/completed/*.md`
- Project config: `backlog/config.yml`

Prefer the `backlog` CLI for task changes. Direct file edits are acceptable
only when the CLI cannot represent the needed metadata change.

The project was migrated from beads. Original bead IDs are preserved in task
frontmatter under `beads.id`; they are historical references only and do not
make `bd` the active tracker.

### Important Rules

- Use Backlog.md for ALL task tracking
- Use `--plain` when running Backlog.md commands from automation
- Always set comment author to `oompah` when posting comments:
  `backlog task edit TASK-123 --comment "message" --comment-author oompah --plain`
- Link discovered work with `--parent` or `--depends-on`
- Check `backlog task list --status "To Do" --plain` before asking
  "what should I work on?"
- Do NOT create markdown TODO lists
- Do NOT use `bd` or beads for new task tracking
- Do NOT use external issue trackers
- Do NOT duplicate tracking systems
- Do NOT post comments without `--comment-author oompah`

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BACKLOG INTEGRATION -->
