---
tracker:
  kind: beads
  active_states:
    - open
    - in_progress
  terminal_states:
    - closed

polling:
  interval_ms: 30000

workspace:
  root: /tmp/umpah_workspaces

agent:
  max_concurrent_agents: 5
  max_turns: 10
  max_retry_backoff_ms: 300000

codex:
  command: "claude --dangerously-skip-permissions"
  turn_timeout_ms: 3600000
  stall_timeout_ms: 300000

server:
  port: 8080
---

You are an autonomous coding agent working on issue **{{ issue.identifier }}**.

## Issue Details

- **Title:** {{ issue.title }}
- **Description:** {{ issue.description }}
- **Priority:** {{ issue.priority }}
- **State:** {{ issue.state }}
- **Labels:** {{ issue.labels | join: ", " }}

{% if attempt %}
## Continuation Run

This is attempt #{{ attempt }}. Review your previous work and continue where you left off.
{% endif %}

## Instructions

1. Read the issue carefully and understand the requirements
2. Explore the codebase to understand the relevant context
3. Implement the changes needed to resolve the issue
4. Run any relevant tests to verify your changes
5. Update the issue status when complete using `bd close {{ issue.identifier }}`
