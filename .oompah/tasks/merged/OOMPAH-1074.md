---
id: OOMPAH-1074
type: bug
status: Merged
priority: 1
title: Retire delayed epic auto-close jobs when terminal validation takes ownership
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T08:29:52.903666Z'
updated_at: '2026-08-11T10:41:07.121504Z'
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
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-5a49b825d935
    project_id: proj-14849f1b
    task_id: OOMPAH-1074
    digest: 30fe51448e83f6292669a2f9af4aab5521615db0e68c3d8bb933f5297c03daf8
  - version: 1
    audit_id: audit-e86ab0f4bbb6
    project_id: proj-14849f1b
    task_id: OOMPAH-1074
    digest: 30fe51448e83f6292669a2f9af4aab5521615db0e68c3d8bb933f5297c03daf8
  oompah.terminal_override_records:
  - version: 1
    override_id: override-135eed155632
    project_id: proj-14849f1b
    task_id: OOMPAH-1074
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30fe51448e83f6292669a2f9af4aab5521615db0e68c3d8bb933f5297c03daf8
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner completion using exact protected delivery evidence. Final
      head 52e50a is contained in protected PR #811 merge e53434b41; Python 3.11/3.12/3.13
      checks passed; independent exact-head review accepted the delayed epic-auto-close
      retirement fix and 582 focused tests passed. No additional terminal full-suite
      rerun is needed.'
    created_at: '2026-08-11T10:40:54.586470+00:00'
    selected_ref: origin/OOMPAH-1074
    selected_sha: 52e50a446eaef3abe4f2b9dc2ff732f98d9ad6a0
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1074
    target_state: Merged
    evidence_fingerprint: 30fe51448e83f6292669a2f9af4aab5521615db0e68c3d8bb933f5297c03daf8
    workflow_revision: null
    selected_ref: origin/OOMPAH-1074
    selected_sha: 52e50a446eaef3abe4f2b9dc2ff732f98d9ad6a0
    landing_revision: null
    audit_ids:
    - audit-5a49b825d935
    - audit-e86ab0f4bbb6
    kind: override
    applied: true
    retired_at: '2026-08-11T10:41:05.407767+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5a49b825d935
    project_id: proj-14849f1b
    task_id: OOMPAH-1074
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30fe51448e83f6292669a2f9af4aab5521615db0e68c3d8bb933f5297c03daf8
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T09:22:48.969987+00:00'
    selected_ref: origin/OOMPAH-1074
    selected_sha: 52e50a446eaef3abe4f2b9dc2ff732f98d9ad6a0
    updated_at: '2026-08-11T10:41:05.407717+00:00'
  - version: 1
    audit_id: audit-e86ab0f4bbb6
    project_id: proj-14849f1b
    task_id: OOMPAH-1074
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 30fe51448e83f6292669a2f9af4aab5521615db0e68c3d8bb933f5297c03daf8
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T09:22:48.969987+00:00'
    selected_ref: origin/OOMPAH-1074
    selected_sha: 52e50a446eaef3abe4f2b9dc2ff732f98d9ad6a0
    updated_at: '2026-08-11T10:41:05.407749+00:00'
  attempt_history: []
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 09:22
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 10:41
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner completion using exact protected delivery evidence. Final head 52e50a is contained in protected PR #811 merge e53434b41; Python 3.11/3.12/3.13 checks passed; independent exact-head review accepted the delayed epic-auto-close retirement fix and 582 focused tests passed. No additional terminal full-suite rerun is needed.
---
<!-- COMMENTS:END -->
