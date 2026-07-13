---
id: OOMPAH-177
type: task
status: In Progress
priority: 1
title: Add durable release-addendum queue claiming and recovery
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-173
labels: []
assignee: null
created_at: '2026-07-13T02:35:49.472960Z'
updated_at: '2026-07-13T04:37:16.031595Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5a83e7a5-fea5-4a81-9324-4798b23ac658
oompah.task_costs:
  total_input_tokens: 2191277
  total_output_tokens: 13049
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2191277
      output_tokens: 13049
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 2191277
    output_tokens: 13049
    cost_usd: 0.0
    recorded_at: '2026-07-13T04:33:30.108447+00:00'
---
## Summary

Read sections 4.2 and 8 of plans/release-branch-addendums.md. Implement ReleaseAddendumQueue alongside the orchestrator dispatch loop. It must scan durable open addendums, wake immediately on release_addendum_ready, claim one addendum atomically by setting in_progress plus claimed_by and lease_expires_at, and return expired leases to open. Queue keys are project ID, source identifier, and target branch; never construct an Issue or tracker child task. Tests: one claimant wins; events wake the queue; restart recovery discovers persisted open rows; expired lease recovery; blocked/merged/archived rows are not claimed; and repeated scans are idempotent. Acceptance: a persisted open addendum is independently dispatchable and recoverable without source-task status changes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 04:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 04:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:33
---
Agent completed successfully in 958s (2204326 tokens)
---
author: oompah
created: 2026-07-13 04:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 27
- Tokens: 2.2M in / 13.0K out [2.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 58s
- Log: OOMPAH-177__20260713T041751Z.jsonl
---
author: oompah
created: 2026-07-13 04:33
---
Agent completed without closing this issue (958s (2204326 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-13 04:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-13 04:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
