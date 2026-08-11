---
id: OOMPAH-1073
type: bug
status: Merged
priority: 1
title: Make Backlog direct-owner claims lifecycle-atomic in enforce mode
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T08:21:18.898748Z'
updated_at: '2026-08-11T10:40:46.934567Z'
work_branch: OOMPAH-1073
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/813
review_number: '813'
review_head: 1732c3e65a53ffaac96c5670e02f1ec075004382
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: direct-owner-backlog-illegal-edge-20260811
  request_fingerprint: aba69f23bc92b16499381e48a12f1fa34ba9d6019f4bdbacec64612ed885fb2a
oompah.review_url: https://github.com/lesserevil/oompah/pull/813
oompah.review_number: '813'
oompah.work_branch: OOMPAH-1073
oompah.target_branch: main
oompah.review_head: 1732c3e65a53ffaac96c5670e02f1ec075004382
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-0aafbaf7b460
    project_id: proj-14849f1b
    task_id: OOMPAH-1073
    digest: d9e2c176899a3d4da242ae064ceaa6f886c7a067e8e5afe7c7a5b58a4b2e8858
  - version: 1
    audit_id: audit-c4ca32be87a5
    project_id: proj-14849f1b
    task_id: OOMPAH-1073
    digest: d9e2c176899a3d4da242ae064ceaa6f886c7a067e8e5afe7c7a5b58a4b2e8858
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f3f53be92bc9
    project_id: proj-14849f1b
    task_id: OOMPAH-1073
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d9e2c176899a3d4da242ae064ceaa6f886c7a067e8e5afe7c7a5b58a4b2e8858
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner completion using exact protected delivery evidence. Final
      head 8b699dbc73bb10aaf0cf45bff2d81b2d58e0a197 is contained in protected PR #813
      merge 8496297f9; Python 3.11/3.12/3.13 checks passed; independent exact-head
      review accepted both retirement-pending and task-missing compensation fixes;
      1,004 surrounding and 285 focused tests plus terminal scan passed. The recorded
      local gate covered earlier head 1732c3e65, so a new terminal full-suite rerun
      would be redundant.'
    created_at: '2026-08-11T10:40:33.990993+00:00'
    selected_ref: origin/OOMPAH-1073
    selected_sha: 8b699dbc73bb10aaf0cf45bff2d81b2d58e0a197
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1073
    target_state: Merged
    evidence_fingerprint: d9e2c176899a3d4da242ae064ceaa6f886c7a067e8e5afe7c7a5b58a4b2e8858
    workflow_revision: null
    selected_ref: origin/OOMPAH-1073
    selected_sha: 8b699dbc73bb10aaf0cf45bff2d81b2d58e0a197
    landing_revision: null
    audit_ids:
    - audit-0aafbaf7b460
    - audit-c4ca32be87a5
    kind: override
    applied: true
    retired_at: '2026-08-11T10:40:45.318160+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0aafbaf7b460
    project_id: proj-14849f1b
    task_id: OOMPAH-1073
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d9e2c176899a3d4da242ae064ceaa6f886c7a067e8e5afe7c7a5b58a4b2e8858
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T09:49:33.834197+00:00'
    selected_ref: origin/OOMPAH-1073
    selected_sha: 8b699dbc73bb10aaf0cf45bff2d81b2d58e0a197
    updated_at: '2026-08-11T10:40:45.318115+00:00'
  - version: 1
    audit_id: audit-c4ca32be87a5
    project_id: proj-14849f1b
    task_id: OOMPAH-1073
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d9e2c176899a3d4da242ae064ceaa6f886c7a067e8e5afe7c7a5b58a4b2e8858
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T09:49:33.834197+00:00'
    selected_ref: origin/OOMPAH-1073
    selected_sha: 8b699dbc73bb10aaf0cf45bff2d81b2d58e0a197
    updated_at: '2026-08-11T10:40:45.318144+00:00'
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-1071

Problem: POST /api/v1/projects/{project_id}/tasks/{identifier}/owner-claim accepts every nonterminal state, including Backlog. In enforce mode it durably persists the direct-owner claim effect, then ProductionImplementationWorkflowBackend.build_transition emits a Backlog -> In Progress TransitionIntent with actor oompah and TransitionAuthority.ORCHESTRATOR. The transition gate rejects transition.illegal_edge, so the workflow job exhausts as policy after its owner-claim side effect has committed. Live reproduction on 2026-08-11 exhausted jobs 4641/4642 for OOMPAH-1071/1072 while leaving each task Backlog with an active owner claim; current exhausted-job health became nonzero.

Implementation: preserve the authenticated project-owner authority and owner identity through the imperative DIRECT_OWNER_CLAIM payload and durable transition, or perform an explicitly authorized Backlog -> Open promotion before the ordinary Open -> In Progress claim transition. The chosen design must remain restart-safe and idempotent, never grant promotion to non-owners, never leave a claim active when its required lifecycle transition fails permanently, and preserve current fencing of scheduler/validation ownership. Do not weaken the global transition matrix for ordinary orchestrator/worker transitions.

Relevant code: api_grant_owner_claim in oompah/server.py; ProductionImplementationWorkflowBackend.build_transition and direct-owner effects in oompah/implementation_workflow_adapter.py; transition authority/gates; durable workflow failure compensation.

Required tests and acceptance criteria: reproduce an owner-authenticated Backlog claim in enforce mode and prove the task reaches In Progress with an active matching claim and the job completes; a non-owner cannot promote; Open claims remain unchanged; terminal and In Validation claims remain rejected; a transition race or permanent rejection leaves no orphan active claim; crash/restart after the claim effect converges idempotently; no current exhausted workflow job or action-required alert remains. Run focused owner-claim/implementation workflow/runtime/transition tests and make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 09:33
---
Branch quality gate passed for `1732c3e65a53ffaac96c5670e02f1ec075004382` using `make test` in 169.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 09:49
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 10:40
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner completion using exact protected delivery evidence. Final head 8b699dbc73bb10aaf0cf45bff2d81b2d58e0a197 is contained in protected PR #813 merge 8496297f9; Python 3.11/3.12/3.13 checks passed; independent exact-head review accepted both retirement-pending and task-missing compensation fixes; 1,004 surrounding and 285 focused tests plus terminal scan passed. The recorded local gate covered earlier head 1732c3e65, so a new terminal full-suite rerun would be redundant.
---
<!-- COMMENTS:END -->
