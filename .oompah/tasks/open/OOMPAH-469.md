---
id: OOMPAH-469
type: feature
status: Open
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
updated_at: '2026-07-28T22:14:37.837002Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 25f8d5f5-b51d-483a-b115-ffd9d2c534e2
oompah.work_branch: epic-OOMPAH-458
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fc95dc43786acea1fa29f7e6b793dad2c457cbea2c2d863770d6dbc5a33d2d33
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 1b2f43f9-07b8-4f72-a957-931c4870a359
  claim_owner: f5cb4973-0a40-4473-8af0-31431f690e1c
  claimed_at: '2026-07-28T22:14:32.988036+00:00'
  claim_expires_at: '2026-07-28T22:44:32.988036+00:00'
  retry_count: 0
  retry_after: null
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
author: oompah
created: 2026-07-28 21:52
---
Focus handoff: duplicate_detector — Outcome: no duplicate confirmed; OOMPAH-469 is a distinct implementation task. Evidence/decisions: searched with rg across .oompah/tasks, plans, docs, README.md, and WORKFLOW.md, plus git log/history; reviewed the full task records and comments for OOMPAH-457/461/468/470/471/474/475 and prior prompt-injection tasks OOMPAH-287/290/291. The terminal-audit foundation (OOMPAH-457) and In Validation status (OOMPAH-461) are prerequisites and explicitly leave auditor dispatch/focus work out of scope. OOMPAH-468 calls this task the separate auditor-focus contract; downstream tasks consume it. No code or tests were changed, so no focused test run is applicable in this phase. Remaining work/risks: implement the reserved auditor focus/prompt renderer and server-side read-only capability policy, preserve untrusted delimiters and target-specific contracts, exclude it from ordinary triage, and add prompt-injection/tool-authorization tests. Recommended next focus: feature.
---
author: oompah
created: 2026-07-28 21:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 38
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 35s
- Log: OOMPAH-469__20260728T215031Z.jsonl
---
author: oompah
created: 2026-07-28 22:14
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-28 22:14
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
