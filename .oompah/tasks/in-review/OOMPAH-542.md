---
id: OOMPAH-542
type: bug
status: In Review
priority: 1
title: Wake dispatch when watchdog clears stale completion suppression
parent: null
children: []
blocked_by: []
labels:
- human-only
- needs:backend
- needs:test
assignee: null
created_at: '2026-07-29T14:22:15.797334Z'
updated_at: '2026-07-29T14:31:41.288282Z'
work_branch: OOMPAH-542
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/576
review_number: '576'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/576
oompah.review_number: '576'
oompah.work_branch: OOMPAH-542
oompah.target_branch: main
---
## Summary

Triggered by: OOMPAH-470

Production regression on 2026-07-29: OOMPAH-470 completed without closing 21 times and was placed in OrchestratorState.completed/Needs Human. The 15-minute stalled-task watchdog safely reopened it at 14:10, but the internal 5-minute watchdog did not clear the stale completed suppression until 14:19. _watchdog_stale_completed then removed the ID without requesting a refresh, so the dispatch phase had already rejected every candidate and all 9 slots stayed idle until an operator called project resume at 14:20. This regresses the intent of merged OOMPAH-429.\n\nImplementation scope:\n- When _watchdog_stale_completed removes one or more active tracker issues from state.completed, immediately request a follow-up dispatch refresh after the current maintenance/tick phase.\n- Ensure the wake is coalesced/event-driven and does not recursively dispatch inside the watchdog or create a busy loop.\n- Review the stalled-task-watchdog reopen path and, when it runs inside the orchestrator, clear matching in-memory completion/reopen suppression immediately where safe so recovery does not require a second watchdog interval.\n- Preserve terminal task suppression and all dependency/one-agent-per-epic behavior.\n\nTests:\n- Active candidate in state.completed is cleared and emits exactly one refresh request.\n- Multiple stale entries coalesce to one wake; no stale entries emit none.\n- A terminal candidate remains completed and emits no wake.\n- A watchdog-reopened task is selectable on the next dispatch pass rather than waiting five minutes.\n- Run focused watchdog/event-loop tests and make test.\n\nAcceptance criteria:\nA safe watchdog reopen makes the task dispatchable immediately; clearing stale completion state always schedules prompt dispatch; no polling interval or manual resume is required; terminal issues remain suppressed; and production resumes OOMPAH-470 automatically after equivalent recovery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 14:22
---
Claimed by the current interactive session for immediate implementation and production verification. The human-only label prevents duplicate scheduler dispatch.
---
author: oompah
created: 2026-07-29 14:31
---
Implemented and committed as 05380e6fe. Verified watchdog reopens now clear completed/claimed/retry-budget suppression only after tracker state confirms Open, then emit one coalescible dispatch refresh for the entire batch. The internal scheduler watchdog likewise wakes dispatch once after clearing one or more stale completed entries. Full quality gate: make test — 13,116 passed, 7 skipped.
---
<!-- COMMENTS:END -->
