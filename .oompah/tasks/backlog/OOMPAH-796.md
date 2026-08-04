---
id: OOMPAH-796
type: feature
status: Backlog
priority: 1
title: Implement the universal totality and liveness controller
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:26.773150Z'
updated_at: '2026-08-04T21:22:59.048730Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Build a controller that evaluates every nonterminal WorkDecision on relevant events and bounded full-sync. Enforce exactly one disposition: runnable, durably owned, named-prerequisite blocked, retry-scheduled, or action_required. Detect missing/conflicting/expired/impossible ownership, overdue reassessment, exhausted recovery, and graph impossibility. Enqueue reason-coded recovery jobs instead of writing status; deduplicate/escalate only when automatic recovery is unavailable. Required tests: totality across statuses, duplicate owners, missing queue/audit/review job, expired lease, stale facts, retry due/exhausted, dependency cycles, restart convergence, and idempotent remediation. Acceptance: no unknown nonterminal disposition survives one full-sync interval and every synthetic stall recovers or escalates with concrete evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Hard-start prerequisite OOMPAH-785 is Done. Promoting the universal totality/liveness controller for server dispatch as the first OOMPAH-770 implementation wave.
---
<!-- COMMENTS:END -->
