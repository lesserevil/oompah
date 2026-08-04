---
id: OOMPAH-760
type: bug
status: Backlog
priority: 1
title: Persist completed focus before a task handoff reopens work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:25:45.766223Z'
updated_at: '2026-08-04T11:25:45.766223Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-757

Triggered by: OOMPAH-757

Live recurrence/incomplete case of OOMPAH-402 and OOMPAH-430 on revision 5368e236. OOMPAH-757 was first assigned to Technical Writer. The worker correctly posted a structured HANDOFF saying the work requires a backend Feature Developer and used the supported task-handoff path, which changed the tracker to Open. Reconciliation observed Open while the docs worker was still registered and terminated it before worker-result handling persisted focus-complete:docs. The task retained needs:feature but no durable completed-focus marker. After operator recovery from the separate retry self-abort tracked by OOMPAH-759, a fresh normal dispatch selected Technical Writer again at 11:24:42 UTC. Thus a valid handoff loops to the same inapplicable focus and can repeatedly consume agents without advancing implementation.

Implementation scope: make accepted task-handoff mutation, structured handoff comment, successor focus/request, completed-focus marker, tracker Open transition, running-worker retirement, retry cancellation, and dispatch wake one atomic/idempotent authority transition. Reconciliation and worker-exit handling must recognize an accepted handoff generation and must not terminate it as an unexpected state revert before completion metadata is durable. Focus selection must honor the exact completed focus and explicit requested/needs:* successor on fresh dispatch. Backfill bounded trusted Oompah-authored HANDOFF comments that predate the marker without trusting arbitrary human text; handle duplicate handoff, late worker exit, restart, and concurrent status refresh exactly once.

Relevant code: worker task-handoff API/CLI authentication path, _handoff_completed_focus, worker completion, reconcile no-longer-in-progress branch, focus-complete labels/metadata, retry scheduling, focus selection, and dispatch wake.

Required tests: exact OOMPAH-757 docs -> feature handoff where Open becomes visible before worker exit; reconcile during handoff; late/forced worker termination; retry and normal-dispatch paths; restart between comment/label/status writes; duplicate handoff; forged human HANDOFF comment rejection; already-completed focus; explicit needs:feature selection. Acceptance criteria: a valid focus handoff durably completes the old focus before the task is dispatchable, starts the requested applicable focus exactly once, never loops back to the old focus, and never leaves an orphaned In Progress claim; focused handoff/reconcile/focus-selection/retry/restart tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

