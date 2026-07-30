---
id: OOMPAH-577
type: task
status: In Review
priority: null
title: Allow a changed integrated head to retry a failed completed terminal audit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:07:59.102017Z'
updated_at: '2026-07-30T03:14:11.990824Z'
work_branch: OOMPAH-577
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/588
review_number: '588'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/588
oompah.review_number: '588'
oompah.work_branch: OOMPAH-577
oompah.target_branch: main
---
## Summary

Triggered by: OOMPAH-483\n\nImplementation scope: update TerminalTransitionCoordinator request handling so a completed audit record only rejects an identical stale request. When the same target is requested with a different evidence fingerprint after a failed audit and new pushed/integrated work, preserve the old record as Superseded and enqueue a fresh Pending record. Do not allow duplicate same-fingerprint requests and do not weaken successful terminal-state idempotency. Ensure the integration completion sweep can move a Ready-to-Integrate task back to In Validation after its earlier audit failed and the integrated SHA changed. Relevant files: oompah/terminal_transition_coordinator.py, tests/test_terminal_transition_coordinator.py, and integration transition tests in tests/test_orchestrator_handlers.py. Tests: same-fingerprint completed rejection, changed-fingerprint completed supersession, preserved history/audit IDs, fresh pending record, and repeated sweep coalescing. Acceptance criteria: OOMPAH-483 at integrated SHA 11ea824f7 can enter a new independent Done audit instead of logging 'already completed'; identical completed evidence stays idempotently rejected; focused and full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

