---
id: OOMPAH-1073
type: bug
status: Open
priority: 1
title: Make Backlog direct-owner claims lifecycle-atomic in enforce mode
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T08:21:18.898748Z'
updated_at: '2026-08-11T08:21:32.384293Z'
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
  creation_marker: direct-owner-backlog-illegal-edge-20260811
  request_fingerprint: aba69f23bc92b16499381e48a12f1fa34ba9d6019f4bdbacec64612ed885fb2a
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

