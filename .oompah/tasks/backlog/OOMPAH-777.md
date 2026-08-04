---
id: OOMPAH-777
type: feature
status: Backlog
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
updated_at: '2026-08-04T14:05:39.638116Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Implement evaluate_task(task, facts) -> WorkDecision using the workflow contract. Return disposition, reason code, owner type, prerequisites, evidence revision, next reassessment, permitted actions, action_required, and severity. Centralize dependency satisfaction, queue eligibility, target/landing resolution, retry/exhaustion, audit/review/implementation ownership, and epic readiness without I/O. Required table/property tests across every status and error fact, cross-epic dependencies, mixed queue heads, nested epics, retries, authority changes, and terminal states. Acceptance: evaluator is deterministic and total; no nonterminal input returns unknown without an explicit bounded recovery decision; consumers need no independent lifecycle heuristics.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

