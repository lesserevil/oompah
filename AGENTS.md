# Agent Instructions

<!-- BEGIN OOMPAH GITHUB ISSUES INTEGRATION v:1 -->
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
