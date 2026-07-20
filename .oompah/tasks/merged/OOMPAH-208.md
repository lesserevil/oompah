---
id: OOMPAH-208
type: bug
status: Merged
priority: 2
title: Exclude already-landed commits from release delivery targets
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T16:17:14.607504Z'
updated_at: '2026-07-15T16:19:24.308912Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d77f5560-51ad-440e-b590-8c7a741b31f1
oompah.task_costs:
  total_input_tokens: 32
  total_output_tokens: 720
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 32
      output_tokens: 720
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 32
    output_tokens: 720
    cost_usd: 0.0
    recorded_at: '2026-07-15T16:18:54.783501+00:00'
---
## Summary

Triggered by: OOMPAH-199

Release Delivery must never queue a commit to a target release branch that already contains it. Filter target choices in the popup using each selected commit's inventory release_status, and enforce the same Git-ancestry check server-side immediately before ledger writes so stale or crafted requests cannot create duplicate deliveries. For mixed selections, queue only the undelivered commit-target pairs while reporting already-delivered pairs. Add UI and API regression tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 16:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-15 16:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 16:17
---
Understanding: OOMPAH-208 asks to prevent duplicate commit deliveries to release branches. It was triggered by OOMPAH-199. As Duplicate Investigator, my first step is to read OOMPAH-199 and search for any other related tasks covering the same ground before deciding whether to implement or archive this as a duplicate.
---
author: oompah
created: 2026-07-15 16:18
---
Implemented in e5fd7fcb: the popup disables a target when all selected commits are already delivered there, and the queue API removes Git-ancestry-proven commit-target pairs before writing delivery bundles. Added UI and API regression tests; make test passed.
---
author: oompah
created: 2026-07-15 16:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 20
- Tokens: 32 in / 720 out [752 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 25s
- Log: OOMPAH-208__20260715T161734Z.jsonl
---
<!-- COMMENTS:END -->
