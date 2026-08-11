---
id: OOMPAH-1074
type: bug
status: In Progress
priority: 1
title: Retire delayed epic auto-close jobs when terminal validation takes ownership
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T08:29:52.903666Z'
updated_at: '2026-08-11T08:30:10.969310Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: oompah-940-delayed-auto-close-handoff-20260811
  request_fingerprint: 552ef6c524522e8d60300514186010a55f30d12a940d71c43b9c1fdad684f19f
---
## Summary

Triggered by: OOMPAH-940

Problem: Live OOMPAH-940 recovery on 2026-08-11 staged a valid Merged terminal audit and moved the epic to In Validation. A delayed same-lane epic_auto_close job then revalidated as current because EpicWorkflow AUTO_CLOSE currentness does not gate on lifecycle status, attempted another terminal transition from In Validation, and exhausted as policy with transition.terminal_rejected (coordinator: landed epic validation requires a current rollup state). The legitimate Done/Merged audit jobs remained active, but workflow_jobs.current_states.exhausted became 1 and aggregate health degraded. OOMPAH-931 only retires a distinct replacement in the same event lane; OOMPAH-961 terminal handoff retires workflow_managed rows only, so the delayed imperative row is not retired.

Implementation: make terminal-audit staging/lifecycle handoff atomically supersede or render stale every delayed epic_auto_close generation that no longer owns an eligible rollup state. Epic AUTO_CLOSE action-current validation must reject In Validation and other non-rollup source statuses before transition construction. Preserve exact landing/evidence fences, idempotent audit replay, valid In Progress/Done auto-close paths, append-only job history, and genuine current exhaustion visibility. Do not cancel the legitimate terminal audit or weaken terminal coordinator topology checks.

Relevant code: oompah/epic_workflow.py AUTO_CLOSE currentness; terminal transition/lifecycle handoff retirement; oompah/workflow_jobs.py event-lane replacement/current health; terminal coordinator and runtime integration.

Required tests and acceptance criteria: reproduce staged terminal audit -> task In Validation -> delayed epic_auto_close and prove the delayed job supersedes/stales without an effect or exhausted health; cover restart/replay and a race at transition staging; prove valid current In Progress/Done auto-close still runs; genuine terminal rejection without a newer handoff stays actionable; current exhausted becomes zero while the audit remains queued/running; the audit completes naturally and the next published reconcile remains healthy. Run focused epic/workflow jobs/terminal transition/runtime tests and make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

