---
id: OOMPAH-429
type: bug
status: Done
priority: 1
title: Clear scheduler completion state when an operator reopens a task
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T22:24:40.832138Z'
updated_at: '2026-07-23T22:27:58.230133Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

When a task moved to Needs Human/Done is manually or watchdog reopened to an active status, remove its identifier from the orchestrator in-memory completed set immediately. EXOCOMP-55 reproduced the bug: it was returned to Open with a valid feature handoff but remained rejected as completed until the periodic watchdog sweep. Update the issue-status API transition path, preserve terminal-state behavior, add regression coverage for reopening a completed task, and verify the reopened task can dispatch on the next scheduler pass. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 22:26
---
Implemented and verified the immediate-reopen fix: reopening a dispatchable task now clears the scheduler's stale completed/claimed entries, so it can be selected on the next tick rather than waiting for the watchdog. Full test suite passed; committing and deploying next.
---
author: oompah
created: 2026-07-23 22:27
---
Fixed and deployed in 3e921ab76. Reopening a dispatchable task now removes stale scheduler completed/claimed entries immediately; full test suite passed. Verified EXOCOMP-55 was requeued and is now In Progress.
---
<!-- COMMENTS:END -->
