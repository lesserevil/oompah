---
id: OOMPAH-211
type: feature
status: In Progress
priority: 2
title: Deliver new task comments to running agents
parent: null
children: []
blocked_by: []
labels:
- needs:feature
assignee: null
created_at: '2026-07-15T20:52:07.206772Z'
updated_at: '2026-07-15T20:57:33.039245Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 90fef21e-063e-4cc0-b08f-7117ef6c4d3e
oompah.task_costs:
  total_input_tokens: 53
  total_output_tokens: 1863
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 53
      output_tokens: 1863
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 53
    output_tokens: 1863
    cost_usd: 0.0
    recorded_at: '2026-07-15T20:57:17.232280+00:00'
---
## Summary

Triggered by: OOMPAH-210

When a comment is added to a task with an active agent run, deliver it into that agent's live context rather than only exposing it on a future dispatch. Define ordering, idempotency, audit logging, retry behavior, and graceful fallback for providers that cannot accept mid-run messages. Add unit and integration tests proving a running agent receives a newly posted task comment exactly once.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 20:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-15 20:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 20:55
---
Understanding: OOMPAH-211 asks for delivering new task comments to running agents mid-run. Triggered by OOMPAH-210. My role is Duplicate Investigator — I will search for existing tasks covering the same ground before any implementation begins. Searching now for candidate duplicates.
---
author: oompah
created: 2026-07-15 20:56
---
Discovery: OOMPAH-211 is NOT a duplicate. Searched all task states (in-progress, done, archived, merged), plans/, docs/, README.md and WORKFLOW.md for tasks covering: deliver/inject task comments to running agents mid-run, live context injection, mid-flight messages, human-in-loop injection, idempotent comment delivery. No existing task or plan covers this scenario. OOMPAH-210 (the trigger) is about GitHub check-run 403 errors — a completely different topic. This feature request is genuinely new and requires backend feature implementation: comment-delivery pipeline to active agent runs, ordering/idempotency guarantees, audit logging, retry behavior, provider fallback, and unit/integration tests.
---
author: oompah
created: 2026-07-15 20:56
---
HANDOFF to feature agent: Duplicate investigation complete — this is a NEW feature, not a duplicate. No existing task covers delivering task comments to running agents mid-run. The implementation requires: (1) A mechanism to detect when a task has an active agent run, (2) A comment-delivery pipeline to inject new task comments into the live agent context, (3) Ordering and idempotency guarantees (exactly-once delivery), (4) Audit logging of delivery attempts, (5) Retry behavior on transient failures, (6) Graceful fallback for providers that cannot accept mid-run messages, (7) Unit and integration tests proving a running agent receives a newly posted task comment exactly once. Relevant codebase areas to explore: oompah/orchestrator.py (agent dispatch/run lifecycle), oompah/agents.py or similar (active run tracking), any ACP/SDK integration layers. Plans to read: plans/acp-agent.md, plans/acp-backends.md, plans/agent-watcher.md for context on agent run lifecycle.
---
author: oompah
created: 2026-07-15 20:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 39
- Tokens: 53 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 31s
- Log: OOMPAH-211__20260715T205451Z.jsonl
---
<!-- COMMENTS:END -->
