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
updated_at: '2026-07-28T21:52:31.737702Z'
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
author: oompah
created: 2026-07-28 21:52
---
Understanding: I will complete duplicate screening for the reserved read-only auditor focus by searching all task states, plans, docs, and history for an existing auditor-focus/prompt-contract/server-side capability implementation; I will read the closest candidates in full and then either archive this as a confirmed duplicate or hand off with evidence. I will not modify code in this duplicate-investigator phase.
---
author: oompah
created: 2026-07-28 21:52
---
Discovery: No duplicate confirmed. I searched .oompah/tasks across all states plus plans/, docs/, README.md, WORKFLOW.md, source/tests, and git history. Read the full records for OOMPAH-457, OOMPAH-461, OOMPAH-468, OOMPAH-470, OOMPAH-471, OOMPAH-474, OOMPAH-475, and the closest prior prompt-injection tasks OOMPAH-287, OOMPAH-290, and OOMPAH-291. OOMPAH-457 is the terminal-audit state/coordinator foundation and explicitly does not dispatch auditor agents; OOMPAH-461 adds In Validation and explicitly excludes the auditor scheduler; OOMPAH-468 identifies OOMPAH-469 as the separate auditor-focus contract; OOMPAH-470, OOMPAH-471, OOMPAH-474, and OOMPAH-475 are downstream candidate/evidence/result/dispatch work. OOMPAH-287/290/291 cover general provenance, authority boundaries, and prompt-injection regression, not this reserved focus and target-specific contract.
---
<!-- COMMENTS:END -->
