---
id: OOMPAH-969
type: task
status: Open
priority: null
title: Preserve fast workflow admission under continuous ordinary events
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T19:25:38.748132Z'
updated_at: '2026-08-09T19:26:09.727565Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Regression of OOMPAH-959 observed live on 2026-08-09 while integrating OOMPAH-967. Durable workflow effect completion posts WORKFLOW_ADMISSION, but the dispatch loop allows a coalesced ordinary refresh/webhook event to subsume that admission wake into a full world reconciliation. With full ticks taking 178–188 seconds, all three shared workflow slots remained idle for roughly 165–201 seconds despite more than 76 due decision rows; OOMPAH-967 integration_attempt remained queued with attempts=0 for over 21 minutes. OOMPAH-955 reserved control-lane admission still worked, so this is specifically loss of fair/prompt shared admission continuation under continuous ordinary events.\n\nImplementation scope: preserve an independent bounded admission turn when completion requests WORKFLOW_ADMISSION even if ordinary events are already/coincidentally queued; keep event coalescing, single-owner orchestration, pause/quiesce semantics, control-slot reservation, and bounded scan behavior; do not create a busy loop or starve ordinary reconciliation. Relevant code: orchestrator dispatch/event coalescing around OOMPAH-959 and tests including test_ordinary_event_subsumes_coalesced_admission_wake.\n\nRequired tests: reproduce continuous ordinary events while shared jobs finish and prove due replacements are admitted promptly without waiting for the next full world scan; prove ordinary reconciliation still runs fairly; prove pause/quiesce prevents admission; preserve control-lane isolation and no-spin behavior. Acceptance: live-equivalent queued effects drain through prompt bounded continuations, shared slots do not remain idle behind a multi-minute full scan solely because an ordinary event subsumed admission, focused orchestrator/workflow tests pass, and protected CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 19:26
---
Accepted for direct-owner implementation. Live evidence confirms the shared admission continuation is starved by ordinary-event coalescing while the reserved control lane remains correct.
---
<!-- COMMENTS:END -->
