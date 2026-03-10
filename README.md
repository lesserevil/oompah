# oompah

An automation service that orchestrates coding agents to execute project work sourced from issue trackers.

Oompah polls for open issues, matches each to a specialized agent focus, spins up isolated git worktrees, and runs AI coding agents to resolve the work — committing, pushing, and creating pull requests autonomously.

## Features

- **Issue-driven orchestration** — polls [beads](https://github.com/lesserevil/beads) for open issues, dispatches agents by priority, and tracks progress through comments
- **Agent focus system** — matches issues to specialized roles (Bug Investigator, Feature Developer, Security Auditor, etc.) using keyword scoring, issue types, and labels
- **Git worktrees** — each agent works in an isolated worktree on a named branch, preventing interference between concurrent agents
- **Multi-project support** — manage multiple git repos, each with their own issue tracker and SCM provider
- **SCM integration** — list open PRs/MRs across GitHub and GitLab, detect rebase needs, trigger server-side rebases, and auto-notify agents about merge conflicts
- **Provider flexibility** — connect to any OpenAI-compatible API for model inference, with per-profile model roles and cost tracking
- **Budget controls** — set spending limits, track costs by agent profile, and pause dispatch when budgets are exceeded
- **Live dashboard** — real-time web UI with kanban board, agent activity, cost tracking, reviews page, and focus management
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

## Configuration

Oompah is configured through a single `WORKFLOW.md` file that combines YAML front matter (service configuration) with a Liquid template (agent prompt).

```markdown
---
tracker:
  kind: beads
  active_states: [open, in_progress]
  terminal_states: [closed]

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
| `tracker` | `kind` | Issue tracker type | `beads` |
| `tracker` | `active_states` | States that trigger agent dispatch | `[open, in_progress]` |
| `tracker` | `terminal_states` | States that mean "done" | `[closed]` |
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
- **`/projects-manage`** — Project CRUD (git repos with beads tracking)
- **`/providers`** — Model provider configuration

## Project setup

Each project needs:

1. A git repository with [beads](https://github.com/lesserevil/beads) initialized (`bd init`)
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
