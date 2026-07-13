---
id: OOMPAH-184
type: task
status: In Progress
priority: 2
title: Document release-addendum workflow and operator migration
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-183
labels: []
assignee: null
created_at: '2026-07-13T02:37:55.470386Z'
updated_at: '2026-07-13T06:44:15.204410Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b94e027a-6c07-49b2-a2d6-182ac91fe8db
oompah.task_costs:
  total_input_tokens: 1605058
  total_output_tokens: 7166
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1605058
      output_tokens: 7166
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 1605058
    output_tokens: 7166
    cost_usd: 0.0
    recorded_at: '2026-07-13T06:44:10.173161+00:00'
---
## Summary

Read the full plans/release-branch-addendums.md. Update user-facing docs, operator/configuration documentation, project-definition help, API reference, and generated agent guidance to describe the main-first release-addendum workflow: supported release lines, selecting release targets, immediate queueing, per-branch lifecycle, task/epic snapshots, branch inspection, retries, and legacy migration. Remove active instructions that tell users to create or work child backport tasks; retain historical references only when clearly labelled. Use Mermaid for any diagrams. Update documentation tests or add targeted assertions for generated guidance. Acceptance: a junior operator can configure supported lines, approve a merged task for two branches, inspect outcomes, and understand migration without consulting source code.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 06:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 06:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 06:44
---
Agent completed successfully in 294s (1612224 tokens)
---
author: oompah
created: 2026-07-13 06:44
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 16
- Tokens: 1.6M in / 7.2K out [1.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 54s
- Log: OOMPAH-184__20260713T063920Z.jsonl
---
<!-- COMMENTS:END -->
