---
id: OOMPAH-1078
type: task
status: Open
priority: null
title: Prevent manual In Validation transitions from stranding terminal audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T10:13:51.547647Z'
updated_at: '2026-08-11T10:13:55.014538Z'
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
  creation_marker: fb2a09ae-ea46-4667-bd75-8a9f367c2db3
  request_fingerprint: d17b7df2e7e113a319d6343a89d928aaeb0be8479b7cfddbb5a52132b5d87d97
---
## Summary

Live regression observed 2026-08-11 on merged build 4be80277a: an authenticated direct owner ran 'oompah task set-status OOMPAH-1077 In Validation' after its shared implementation had merged. The API accepted the nonterminal status and retired the owner claim, but did not atomically stage terminal-audit metadata or a durable terminal_audit job. Subsequent complete workflow publications reported reason_code=evidence.terminal_audit_missing, required_recovery_count=6/materialized_recovery_count=5, no active_job_id for OOMPAH-1077, restart reconstruction remained incomplete, and otherwise valid auditors could not dispatch. Implementation scope: make direct API/CLI/dashboard In Validation transitions impossible to strand. Either reject In Validation as a coordinator-owned status unless an exact audit request/delivery evidence is atomically staged, or route the request through the canonical terminal-audit coordinator transaction. Preserve idempotency, project-owner authentication, exact branch/head/provenance requirements, existing submit and terminal override flows, and rollback on staging failure. Relevant code: API task status route, TaskTransitionService/terminal audit staging, CLI set-status behavior, workflow runtime materialization. Required tests: direct In Progress->In Validation without audit evidence cannot commit a naked status; an authorized canonical staging path writes status plus audit metadata/job atomically; injected job-store/tracker failures leave the original status/claim recoverable; retries are idempotent; dashboard/CLI error is actionable; restart liveness never observes In Validation with missing audit materialization solely from this route. Acceptance: the reproduced OOMPAH-1077 sequence is rejected or atomically produces a pending audit, required/materialized recovery counts remain equal, focused API/transition/audit/runtime tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

