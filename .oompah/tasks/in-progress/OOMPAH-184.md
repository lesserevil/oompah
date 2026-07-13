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
updated_at: '2026-07-13T06:49:29.467377Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 18d960f9-4a72-4cdc-b281-fbc4516e1e2e
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
author: oompah
created: 2026-07-13 06:44
---
Agent completed without closing this issue (294s (1612224 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-13 06:45
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-13 06:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 06:49
---
Understanding: This is NOT a duplicate. OOMPAH-185 was previously archived as the duplicate of this task. Confirmed no other duplicate exists.

Scope assessment:
- docs/release-addendums.md: COMPLETE - comprehensive operator guide covering all workflow aspects
- docs/task-epic-workflow.md: COMPLETE - has Release Delivery section
- docs/operator-runbook.md: COMPLETE - has Supported Release Lines paragraph in §1.3
- oompah/agent_instructions.py OOMPAH_TASK block: COMPLETE - has Release Addendums section
- oompah/agent_instructions.py GITHUB_ISSUES block: MISSING - needs Release Addendums section
- docs/managed-project-onboarding.md: MISSING - no release lines step in the checklist
- tests/test_agent_instructions.py: PARTIAL - has test for oompah_task instructions but MISSING test for github_issues instructions describing release addendums
- docs/README.md: COMPLETE - indexes release-addendums.md

Plan: (1) Add Release Addendums section to GITHUB_ISSUES_AGENT_INSTRUCTIONS; (2) Add step to managed-project-onboarding.md; (3) Add test for github_issues instructions; (4) Add assertions for release-addendums.md doc coverage.
---
<!-- COMMENTS:END -->
