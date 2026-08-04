---
id: OOMPAH-777
type: feature
status: In Progress
priority: 1
title: Implement the pure total WorkDecision evaluator
parent: OOMPAH-765
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-786
labels: []
assignee: null
created_at: '2026-08-04T13:58:52.177276Z'
updated_at: '2026-08-04T15:27:58.844032Z'
work_branch: epic-OOMPAH-765--task-OOMPAH-777
target_branch: epic-OOMPAH-765
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-765
oompah.work_branch: epic-OOMPAH-765--task-OOMPAH-777
---
## Summary

Implement evaluate_task(task, facts) -> WorkDecision using the workflow contract. Return disposition, reason code, owner type, prerequisites, evidence revision, next reassessment, permitted actions, action_required, and severity. Centralize dependency satisfaction, queue eligibility, target/landing resolution, retry/exhaustion, audit/review/implementation ownership, and epic readiness without I/O. Required table/property tests across every status and error fact, cross-epic dependencies, mixed queue heads, nested epics, retries, authority changes, and terminal states. Acceptance: evaluator is deterministic and total; no nonterminal input returns unknown without an explicit bounded recovery decision; consumers need no independent lifecycle heuristics.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 15:27
---
Implemented the pure, deterministic WorkDecision evaluator with stable reason codes, owner/disposition/action output, dependency semantics, lease/retry recovery, audit/integration/rollup/landing decisions, and structural alert-severity invariants. Added 40 focused tests plus incident-contract coverage. Verification: 195 focused/adjacent tests passed; ruff check and format-check passed; make terminal-audit-scan passed; staged secret scan and git diff --check passed.
---
<!-- COMMENTS:END -->
