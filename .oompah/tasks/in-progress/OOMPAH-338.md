---
id: OOMPAH-338
type: task
status: In Progress
priority: null
title: Add GitLab tracker lifecycle relationships and metadata persistence
parent: OOMPAH-323
children: []
blocked_by:
- OOMPAH-337
labels: []
assignee: null
created_at: '2026-07-21T23:24:39.407769Z'
updated_at: '2026-07-22T02:43:38.294703Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d7756050-9b62-4ec0-ac33-59d2f775481a
oompah.task_costs:
  total_input_tokens: 204633
  total_output_tokens: 1587
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 204633
      output_tokens: 1587
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 204633
    output_tokens: 1587
    cost_usd: 0.0
    recorded_at: '2026-07-22T02:43:35.365817+00:00'
---
## Summary

Extend GitLabIssueTracker on top of the core adapter to preserve Oompah task/epic semantics: priority/type labels, parent-child and blocked-by dependency issue links, fetch_children, attachments metadata round trips, generic metadata fields, and enriched issue detail. Define and test the GitLab link direction/type mapping so parent and dependency retrieval remains correct across globally unambiguous nested-namespace identifiers. Add mocked API tests for link creation/listing, comments and attachment/metadata round trips, label preservation, and archive/reopen behavior. Keep native external intake out of scope. Acceptance: all non-governance relationship and metadata TrackerProtocol operations have GitLab implementations and tested round-trip behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 02:42
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 02:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 02:43
---
Agent completed successfully in 49s (206220 tokens)
---
author: oompah
created: 2026-07-22 02:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 204.6K in / 1.6K out [206.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-338__20260722T024251Z.jsonl
---
author: oompah
created: 2026-07-22 02:43
---
Agent completed without closing this issue (49s (206220 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
