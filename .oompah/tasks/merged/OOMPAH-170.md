---
id: OOMPAH-170
type: task
status: Merged
priority: 2
title: Update epic workflow documentation for shared-only behavior
parent: OOMPAH-166
children: []
blocked_by:
- OOMPAH-168
labels: []
assignee: null
created_at: '2026-07-13T02:23:12.785814Z'
updated_at: '2026-07-13T19:35:54.672228Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3bf1e548-94d6-44d8-b842-17ff00138a35
oompah.task_costs:
  total_input_tokens: 42
  total_output_tokens: 693
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 42
      output_tokens: 693
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 42
    output_tokens: 693
    cost_usd: 0.0
    recorded_at: '2026-07-13T05:10:37.306111+00:00'
---
## Summary

Update user-facing docs, operator/configuration docs, generated project guidance, and relevant design plans so they describe only the shared epic workflow. Remove or clearly mark historical flat/stacked references where historical context is necessary. Update Mermaid diagrams to show the shared epic branch and landing flow. Update documentation tests or add coverage for generated guidance and remove stale strategy references from active documentation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 04:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 04:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:52
---
UNDERSTANDING: No duplicate found. OOMPAH-170 is a unique child of epic OOMPAH-166 covering the documentation layer. Siblings OOMPAH-167 (config), OOMPAH-168 (orchestration), OOMPAH-169 (UI) are all Done. Scope: update user-facing docs, operator docs, generated project guidance, design plans so they describe only shared epic workflow; remove/mark flat/stacked references; update Mermaid diagrams; add/update doc tests. Plan: (1) Find all docs with flat/stacked/strategy references, (2) Update them, (3) Find and update generated guidance templates, (4) Add doc coverage tests, (5) Run make test.
---
author: oompah
created: 2026-07-13 04:54
---
DISCOVERY: Found all locations needing updates. Primary target: docs/task-epic-workflow.md has stale flat/stacked references in: (1) Epic Planning section - 'stacked and shared projects'; (2) Epic Branch Strategies section - table with flat/stacked/shared rows; (3) Mermaid diagram with flat/stacked branches; (4) Review and Repair - 'stacked or shared epics'; (5) Closing and Rollup - 'stacked and shared epics' (2x). Secondary: tests/test_epic_strategy.py module docstring mentions 'stacked mode' and 'stacked + shared'. Also: plans/multi-branch-support.md line 123 references test_epic_strategy.py as 'Epic strategies' (minor stale context). The generated project guidance (oompah/agent_instructions.py OOMPAH_TASK_AGENT_INSTRUCTIONS) has no flat/stacked references - already clean. No new test file needed beyond updating the test docstring. No duplicate found - proceeding with implementation.
---
author: oompah
created: 2026-07-13 05:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 05:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 05:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 19
- Tokens: 42 in / 693 out [735 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 35s
- Log: OOMPAH-170__20260713T050713Z.jsonl
---
<!-- COMMENTS:END -->
