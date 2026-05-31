# oompah

An automation service that orchestrates coding agents to execute project work sourced from issue trackers.

Oompah polls for open issues, matches each to a specialized agent focus, spins up isolated git worktrees, and runs AI coding agents to resolve the work — committing, pushing, and creating pull requests autonomously.

## Features

- **Issue-driven orchestration** — polls supported task trackers such as Backlog.md and [beads](https://github.com/lesserevil/beads), dispatches agents by priority, and tracks progress through comments
- **Agent focus system** — matches issues to specialized roles (Bug Investigator, Feature Developer, Security Auditor, etc.) using keyword scoring, issue types, and labels
- **Git worktrees** — each agent works in an isolated worktree on a named branch, preventing interference between concurrent agents
- **Multi-project support** — manage multiple git repos, each with their own issue tracker and SCM provider
- **SCM integration** — list open PRs/MRs across GitHub and GitLab, detect rebase needs, trigger server-side rebases, and auto-notify agents about merge conflicts
- **Provider flexibility** — connect to any OpenAI-compatible API for model inference, with per-profile model roles and cost tracking
- **Budget controls** — set spending limits, track costs by agent profile, and pause dispatch when budgets are exceeded
- **Live dashboard** — real-time web UI with kanban board, agent activity, cost tracking, reviews page, and focus management
- **Per-project ACP console** — interactive chat panel in the dashboard for each project, backed by the same Claude / Codex (openai-agents) ACP backends the workers use. Transcripts persist on disk; the operator can switch backends mid-conversation and the prior context carries over via per-backend translators. See `plans/console.md` § "Backend switching" for the full design.
- **Multimodal attachments** — drop images, audio, or PDFs onto an issue; agents with image-capable models receive them inline. With `allow_image_output` foci, agents can attach generated images back to the issue. Stored in the project repo via git LFS. See `plans/multimodal-attachments.md`.
- **Forge webhook forwarding** — listens for PR/push events via `gh webhook forward` so reactions are near-realtime instead of waiting for the periodic full-sync. Requires the `cli/gh-webhook` extension; install with `make install-gh-extensions`. See `docs/webhook-forwarding.md`.
- **Hot reload** — edit `WORKFLOW.md` and the service picks up changes without restart

## Quick start

```bash
# Clone and install
git clone https://github.com/lesserevil/oompah.git
cd oompah
uv venv
uv pip install -e .

# Configure WORKFLOW.md (see below), then run
oompah
```

> [uv](https://docs.astral.sh/uv/) is the recommended way to manage virtual environments and dependencies. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## Backends

Oompah supports two ACP (Agent Control Protocol) backends for running AI coding agents. The base install is lightweight — backend SDKs are optional extras you install only for the backends you use.

### Install matrix

| Backend | Dispatch mode | What drives the agent | Install command |
|---|---|---|---|
| `claude` | ACP (subscription) | Claude Agent SDK → `claude` CLI | `uv pip install 'oompah[claude]'` |
| `codex` | ACP (per-token or subscription) | OpenAI Agents SDK → `codex` CLI | `uv pip install 'oompah[codex]'` |
| *(none)* | API | Direct HTTP to any OpenAI-compatible API | `uv pip install oompah` (base install) |

### Installing backend extras

```bash
# Claude backend only (recommended default — bills against Pro/Max subscription)
uv pip install -e '.[claude]'

# Codex backend only
uv pip install -e '.[codex]'

# Both backends
uv pip install -e '.[all]'

# Development dependencies only (no ACP backend)
uv pip install -e '.[dev]'
```

**Why are SDKs optional?** The Claude Agent SDK and OpenAI Agents SDK are large dependencies that operators running in pure API mode (or using only one backend) should not have to install. The base `oompah` package ships with no ACP backend SDK; each backend's SDK is gated behind a lazy import that surfaces a clear install hint when the SDK is missing. See `plans/acp-agent.md` for the architectural rationale.

## Configuration

Oompah is configured through a single `WORKFLOW.md` file that combines YAML front matter (service configuration) with a Liquid template (agent prompt).

```markdown
---
tracker:
  kind: backlog
  active_states: ["To Do", "In Progress"]
  terminal_states: [Done]

polling:
  interval_ms: 30000

workspace:
  root: /tmp/oompah_workspaces

agent:
  max_concurrent_agents: 5
  stall_turns: 5
  budget_limit: 50.00
  profiles:
    - name: quick
      model_role: fast
      issue_types: [chore]
      keywords: [typo, rename, cleanup]
    - name: standard
      model_role: standard
      issue_types: [task, feature]
    - name: deep
      model_role: deep
      issue_types: [bug, epic]

server:
  port: 8080
---

You are an autonomous coding agent working on issue **{{ issue.identifier }}**.

## Issue Details

- **Title:** {{ issue.title }}
- **Description:** {{ issue.description }}

## Instructions

1. Read the issue carefully
2. Explore the codebase
3. Implement the changes
4. Run tests
5. Commit, push, and create a PR
```

### Configuration reference

| Section | Key | Description | Default |
|---|---|---|---|
| `tracker` | `kind` | Issue tracker type (`backlog`, `backlog_md`, or `beads`) | `beads` |
| `tracker` | `active_states` | States that trigger agent dispatch | `[open, in_progress]` for beads, `["To Do", "In Progress"]` for Backlog.md |
| `tracker` | `terminal_states` | States that mean "done" | `[closed]` for beads, `[Done]` for Backlog.md |
| `polling` | `interval_ms` | Poll interval in milliseconds | `30000` |
| `workspace` | `root` | Directory for agent workspaces | `/tmp/oompah_workspaces` |
| `agent` | `max_concurrent_agents` | Max parallel agents | `10` |
| `agent` | `stall_turns` | Turns without progress before retry | `5` |
| `agent` | `budget_limit` | Max spend in dollars (0 = unlimited) | `0` |
| `agent` | `profiles` | List of agent tier definitions | `[]` |
| `server` | `port` | Dashboard HTTP port | none (no server) |

### Agent profiles

Each profile defines a tier of agent with its own model and matching rules:

```yaml
- name: quick           # Profile name
  model_role: fast      # Model role (mapped in provider config)
  issue_types: [chore]  # Match issues of these types
  keywords: [typo]      # Match issues containing these words
  min_priority: 0       # Only match priorities >= this
  max_priority: 4       # Only match priorities <= this
  provider_id: prov-xxx # Optional — overrides default provider
```

Providers are configured at runtime via the dashboard (`/providers`) and stored in `.oompah/providers.json`. When only one provider exists, all profiles use it automatically. Use `provider_id` only to pin a profile to a specific provider in multi-provider setups.

## Focus system

Foci are specialized agent roles that tailor the prompt to the type of work. Oompah includes 8 built-in foci:

| Focus | Role | Matches |
|---|---|---|
| `feature` | Feature Developer | new features, implementations |
| `refactor` | Refactoring Specialist | cleanup, restructuring |
| `frontend` | Frontend Developer | UI, CSS, components |
| `docs` | Technical Writer | documentation, READMEs |
| `test` | Test Engineer | tests, coverage |
| `security` | Security Auditor | vulnerabilities, auth |
| `devops` | DevOps Engineer | CI/CD, deployment |
| `chore` | Maintenance Engineer | typos, version bumps |

When no focus matches, a general-purpose Software Engineer focus is used.

### Per-focus model overrides

Each focus may optionally pin the model and/or provider used when that focus
runs, regardless of which agent profile won profile matching. All three
fields are optional — when unset, the agent profile picks the model as
before.

```json
{
  "name": "docs",
  "role": "Technical Writer",
  "model_role": "fast",
  "model": null,
  "provider_id": null
}
```

Resolution priority: `focus.model` > `focus.model_role` > `profile.model` >
`profile.model_role` > provider default. A focus pointing at a missing
provider or undefined `model_role` falls back to the profile-level choice
(with a warning) rather than failing dispatch. Edit these fields on the
`/foci` dashboard or directly in `.oompah/foci.json`. See
`plans/per-focus-models.md` for the full design.

### Focus lifecycle

- **Active** — available for agent dispatch
- **Inactive** — disabled, not used for new agents
- **Proposed** — auto-generated from completed work analysis, must be reviewed before activation

After every closed issue, oompah analyzes the work done and suggests new foci when existing ones don't cover the domain. Proposed foci include auto-generated must-do and must-not-do rules based on the detected work domain.

Manage foci at `http://localhost:8080/foci`.

## Web dashboard

Start the dashboard by setting `server.port` in `WORKFLOW.md`:

- **`/`** — Kanban board with drag-and-drop, agent status, cost tracking
- **`/reviews`** — Open PRs/MRs across all projects with rebase controls
- **`/foci`** — Focus library management with inline editing
- **`/projects-manage`** — Project CRUD (git repos with tracker-backed tasks)
- **`/providers`** — Model provider configuration

### Cross-agent continuity (console)

The dashboard's per-project Console panel runs against the same ACP
backends the worker dispatch path uses (Claude SDK, Codex via
openai-agents). Operators can flip backends mid-conversation via the
`backend:` dropdown in the console header — the on-disk JSONL
transcript is the canonical state, and a per-backend translator
rebuilds the SDK-native history on the next turn. The Claude
translator emits Anthropic Messages API shape; the Codex translator
emits the openai-agents `Runner.run_streamed(input=…)` input-item
list. Tool calls and their results survive the round-trip across
backends, with `_tool_use_id` ↔ `call_id` preserved. See
`plans/console.md` § "Backend switching" for the design.

## Project setup

Each project needs:

1. A git repository with a supported task tracker initialized, such as Backlog.md (`backlog init`) or legacy beads (`bd init`)
2. A `WORKFLOW.md` in the oompah working directory
3. At least one model provider configured

Register projects through the dashboard or API:

```bash
curl -X POST http://localhost:8080/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"repo_url": "https://github.com/org/repo.git", "name": "my-project"}'
```

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest -v

# Run a single test module
pytest tests/test_focus.py -v
```

## License

[MIT](LICENSE)
