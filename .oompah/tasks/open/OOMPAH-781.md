---
id: OOMPAH-781
type: feature
status: Open
priority: 1
title: Cut terminal-audit lifecycle over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:58:59.010872Z'
updated_at: '2026-08-04T20:20:49.325977Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Migrate audit request ownership, candidate selection, launch, rotation, finalization, result application, retries, exhaustion, and historical recovery into durable workflow jobs while retaining TerminalTransitionCoordinator safety. Model queued/running/finalizing/retry-wait/action-required explicitly; ensure normal candidate rotation/transport retry is informational; guarantee result finalization cannot be starved by comments/output; preserve independent-candidate policy and exact evidence. Required tests: no candidate, transport failure, dynamic policy denial, duplicate/revoked auditor, oversized output, restart at each stage, deleted branches, finalization starvation, and current audit enforcement suites. Acceptance: every In Validation task has a durable audit disposition and bounded recovery; no valid verdict is lost or indefinitely pending.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

