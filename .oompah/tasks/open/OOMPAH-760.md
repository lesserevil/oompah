---
id: OOMPAH-760
type: bug
status: Open
priority: 1
title: Persist completed focus before a task handoff reopens work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:25:45.766223Z'
updated_at: '2026-08-04T11:28:29.282250Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b618e2de7a17cf673ff221e1bd18c0cdbaea44a2ebb4ac1e0e1125298329f0e8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4ba3d544-0f93-4829-b912-daa23e1c03a5
  claim_owner: bb82706b-fb95-42cd-a68d-43d670f815c6
  claimed_at: '2026-08-04T11:28:14.040416+00:00'
  claim_expires_at: '2026-08-04T11:58:14.040416+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d917a910-5de3-4bec-adf1-0b59914e90e6
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:28
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
