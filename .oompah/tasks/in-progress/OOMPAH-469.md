---
id: OOMPAH-469
type: feature
status: In Progress
priority: 1
title: Add the reserved read-only auditor focus and prompt contract
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-461
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:09.346734Z'
updated_at: '2026-07-28T21:50:29.493083Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d222919a-5ab1-4c63-bab8-43657f6897be
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Add a built-in focus named auditor with role Completion Auditor, but exclude it from normal keyword/LLM focus triage. Its prompt must provide the requested target contract, trusted task metadata, delimited untrusted descriptions/comments, evidence summary, allowed read/test actions, and the auditor result tool schema. The focus must explicitly prohibit editing files, committing, pushing, merging, creating tasks, changing status, or fixing findings. Add a capability policy that exposes read-only repository/test operations plus the result tool and denies mutating task/Git actions server-side.

Tests

Verify auditor is never selected for ordinary work, renders all required instructions and untrusted boundaries, receives the target-specific contract, cannot call protected mutation tools, and can call the result tool. Add prompt-injection tests where task text asks the auditor to approve or modify code. Run focused tests and make test.

Acceptance criteria

Only the audit scheduler can select the focus; an auditor can inspect and report but cannot implement, merge, or change tracker state even when task content requests it.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:50
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
