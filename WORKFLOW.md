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
  root: /tmp/oompah_workspaces

agent:
  max_concurrent_agents: 5
  max_turns: 10
  max_retry_backoff_ms: 300000
  budget_limit: 50.00
  profiles:
    - name: quick
      provider_id: prov-efa393f7
      model_role: fast
      max_turns: 5
      issue_types: [chore]
      keywords: [typo, rename, cleanup, lint, format]
      max_priority: 4
    - name: standard
      provider_id: prov-efa393f7
      model_role: standard
      max_turns: 10
      issue_types: [task, feature]
    - name: deep
      provider_id: prov-efa393f7
      model_role: deep
      max_turns: 20
      issue_types: [bug, epic]
      keywords: [security, architecture, refactor, critical]
      min_priority: 0
      max_priority: 1
    - name: default
      provider_id: prov-efa393f7
      model_role: fast

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
