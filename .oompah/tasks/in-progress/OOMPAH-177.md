---
id: OOMPAH-177
type: task
status: In Progress
priority: 1
title: Add durable release-addendum queue claiming and recovery
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-173
labels: []
assignee: null
created_at: '2026-07-13T02:35:49.472960Z'
updated_at: '2026-07-13T04:17:30.078212Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5a5890be-20d0-4e61-bc2c-5b61d50a688a
---
## Summary

Read sections 4.2 and 8 of plans/release-branch-addendums.md. Implement ReleaseAddendumQueue alongside the orchestrator dispatch loop. It must scan durable open addendums, wake immediately on release_addendum_ready, claim one addendum atomically by setting in_progress plus claimed_by and lease_expires_at, and return expired leases to open. Queue keys are project ID, source identifier, and target branch; never construct an Issue or tracker child task. Tests: one claimant wins; events wake the queue; restart recovery discovers persisted open rows; expired lease recovery; blocked/merged/archived rows are not claimed; and repeated scans are idempotent. Acceptance: a persisted open addendum is independently dispatchable and recoverable without source-task status changes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

