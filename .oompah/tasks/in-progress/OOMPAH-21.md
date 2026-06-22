---
id: OOMPAH-21
type: task
status: In Progress
priority: 2
title: Add the release/1.0 branch cut checklist
parent: OOMPAH-17
children: []
blocked_by:
- OOMPAH-19
labels: []
assignee: null
created_at: '2026-06-22T01:16:34.236540Z'
updated_at: '2026-06-22T02:20:28.706051Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f3777997-8db6-4158-a6d5-df5924b7e4db
oompah.task_costs:
  total_input_tokens: 1979968
  total_output_tokens: 16496
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1979968
      output_tokens: 16496
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 1979968
    output_tokens: 16496
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:20:06.216681+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#release-readiness-checklist

WHAT TO DO
Add a release/1.0 branch cut checklist that maintainers can follow before creating v1.0.0-draft.

THE CHECKLIST MUST COVER
- confirming main is clean
- cutting release/1.0
- setting package version to 1.0.0
- running quality gates
- creating or force-moving v1.0.0-draft
- verifying draft artifacts
- preserving immutable final tag semantics

HOW TO VERIFY
A maintainer can follow the checklist without needing hidden context from this task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:20
---
Agent completed successfully in 503s (1996464 tokens)
---
author: oompah
created: 2026-06-22 02:20
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 37
- Tokens: 2.0M in / 16.5K out [2.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 23s
- Log: OOMPAH-21__20260622T021151Z.jsonl
---
author: oompah
created: 2026-06-22 02:20
---
Agent completed without closing this issue (503s (1996464 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
