---
id: OOMPAH-1261
type: task
status: Backlog
priority: null
title: Recover Ready-to-Integrate work when the remote review head advances past the
  accepted submission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T01:17:47.268102Z'
updated_at: '2026-08-14T01:17:47.268102Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 5cf07b32-4562-410f-b82c-de37c40187c0
  request_fingerprint: 1a91df46d5640339a0e28cc8b1c15a2ac70f7a10c937d3194305fd4c9011d4a0
---
## Summary

Bug reproduced by TRICKLE-136: the accepted integration submission records head 835ae436 while the remote task branch and open MR !19 point at fea95f19. standalone_delivery keeps evaluating the stale accepted head, exhausts 5/5 attempts, and cannot naturally return the task to a truthful resubmission flow. Scope: in the Ready to Integrate / standalone delivery path, compare the accepted integration head with the authoritative current remote task-branch and review head; when they differ, durably retire the stale delivery generation without consuming retry budget, expose a precise resubmission-required disposition for the newer head, and converge after an exact-head resubmission. Preserve fail-closed behavior for ambiguous/missing remote identity and do not silently adopt unsubmitted code. Relevant areas include standalone delivery, integration fact collection, submitted-head authority, recovery projections, and restart reconstruction. Add regressions for remote branch/MR head advance after accepted submission, unchanged exact head, missing/ambiguous remote identity, concurrent resubmission race, retry-budget preservation, and restart recovery. Acceptance: TRICKLE-136 can be worked around by exact-head resubmission and then flows naturally; future drift does not exhaust standalone delivery against a known-stale head; diagnostics name accepted and observed heads; focused/full CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

