---
id: OOMPAH-616
type: bug
status: Backlog
priority: 1
title: Integrate terminal-audit retry ownership fencing
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:47:41.612111Z'
updated_at: '2026-07-30T20:47:41.612111Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: land the already implemented and fully tested OOMPAH-615 fix onto the OOMPAH-585 epic branch. Reuse commit ce8a124fc from origin/OOMPAH-615; resolve only genuine conflicts with the current epic head. The change must serialize terminal-audit staging against implementation In Progress writes, fence in-flight retry dispatch before worker creation, suppress normal-exit retries after an In Validation handoff, wake the audit lane after cleanup, and release the fence when an incomplete audit returns work to Open. Relevant files: oompah/orchestrator.py, oompah/server.py, tests/test_dispatch_close_race.py, tests/test_orchestrator_handlers.py, and tests/test_terminal_status_interfaces.py. Tests: run the focused scheduler/server/audit race suites on the combined epic tree; preserve the recorded full-gate evidence from ce8a124fc (terminal mutation scan passed; 13,736 passed, 7 skipped) and allow Oompah's exact combined-tree gate to run at integration. Acceptance criteria: the commit is pushed on the child's expected epic task branch, integration cannot regress In Validation to In Progress, no stale implementation worker can start after terminal ownership, and the child is submitted through the normal epic integration queue.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

