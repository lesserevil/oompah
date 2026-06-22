# oompah 1.0 CLI and API Compatibility Surface

This document defines the stable surface that managed-project `AGENTS.md` files
and contributors may depend on for the 1.0 release.

Items listed here are considered stable: they will not change or be removed
without a deprecation cycle.

Items not listed here — such as internal flags or undocumented environment
variables — are implementation details and may change without notice.

## Server Locator

The oompah CLI connects to a running oompah server. The server location is
configured with a single environment variable:

```bash
export OOMPAH_SERVER_URL="http://127.0.0.1:<port>"
```

**`OOMPAH_SERVER_URL`** is the canonical, stable way to point the CLI at the
server. Set it once in the shell or in the task-runner invocation before
calling any `oompah task` command.

Default value when `OOMPAH_SERVER_URL` is unset: `http://127.0.0.1:8080`.

### Deprecated / not supported as client-side locators

- **`OOMPAH_SERVER_HOST`** — not supported. This variable does not exist.
- **`OOMPAH_SERVER_PORT`** (as a client variable) — not supported as a
  client-side server locator. `OOMPAH_SERVER_PORT` is a *service* configuration
  variable used by the oompah server process itself to choose which port to
  listen on. Setting it in a managed-project environment has no effect on where
  the `oompah task` CLI sends requests. Use `OOMPAH_SERVER_URL` instead.

## Stable CLI Commands

### Top-level entry point

```bash
oompah --help
```

### Task management — `oompah task`

All `oompah task` commands accept an optional `--project <project-id>` flag
to restrict the operation to a specific managed project.

| Command | Description |
|---------|-------------|
| `oompah task view <identifier>` | Show task details |
| `oompah task comment <identifier> --message "..."` | Add a comment to a task |
| `oompah task create --project <project-id> --title "..."` | Create a new task |
| `oompah task child-create <parent-id> --title "..."` | Create a child task under a parent |
| `oompah task set-status <identifier> <status>` | Update task status |
| `oompah task add-label <identifier> <label>` | Add a label to a task |
| `oompah task remove-label <identifier> <label>` | Remove a label from a task |
| `oompah task set-dependency <identifier> --depends-on <dep-id>` | Record a task dependency |

**Usage patterns expected in managed-project `AGENTS.md` files:**

```bash
oompah task view <task-id> --project <project-id>
oompah task comment <task-id> --message "Progress update" --author oompah
oompah task create --project <project-id> --title "Follow-up" --source <source-id>
oompah task child-create <parent-id> --title "Child task"
oompah task set-dependency <task-id> --depends-on <dep-id>
oompah task add-label <task-id> needs:frontend
oompah task set-status <task-id> Done --summary "Completed"
```

### Project bootstrap — `oompah project-bootstrap`

```bash
oompah project-bootstrap --help
```

The `oompah project-bootstrap` subcommand lets project owners inspect and apply
the baseline managed-project scaffolding (e.g. `AGENTS.md`, `docs/`, `plans/`,
Makefile, and git-hook templates). See
[`docs/project-bootstrap.md`](project-bootstrap.md) for details.

## What Managed-Project `AGENTS.md` Files May Depend On

A managed-project `AGENTS.md` (or equivalent agent instructions) may safely
reference:

- `OOMPAH_SERVER_URL` — to locate the oompah server.
- All `oompah task` subcommands listed in the table above.
- `oompah project-bootstrap --help` — to inspect the bootstrap templates.

Agent instructions should **not** reference:

- `OOMPAH_SERVER_HOST` — does not exist.
- `OOMPAH_SERVER_PORT` as a client variable — configures the server, not the client.
- `--port` or `--server` CLI flags — implementation-level shortcuts; use
  `OOMPAH_SERVER_URL` instead for environment-level configuration.

## Installation

Install the lightweight CLI from a release tag or `main`:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"
pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"
```

The default install includes only `oompah task` and `oompah project-bootstrap`.
It does not install the oompah service runtime. See
[`docs/cli-install.md`](cli-install.md) for full installation details.
