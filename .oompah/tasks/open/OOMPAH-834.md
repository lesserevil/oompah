---
id: OOMPAH-834
type: task
status: Open
priority: 1
title: Bind implementation lifecycle events to durable task-scoped handlers
parent: OOMPAH-804
children: []
blocked_by:
- OOMPAH-781
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:27.595461Z'
updated_at: '2026-08-06T09:18:28.959618Z'
work_branch: epic-OOMPAH-804--task-OOMPAH-834
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a6f9dee590a1fc5a8c40f1239ab3ebaa8e29734260cd74804b838af5ad054eda
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 805fb74a-ff12-42f6-88ce-121b9d6e57e5
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T09:18:06.713927+00:00'
  claim_expires_at: '2026-08-06T09:48:06.713927+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: abc145f8-7fde-474a-98e5-cf6898011ce6
oompah.work_branch: epic-OOMPAH-804--task-OOMPAH-834
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-804--task-OOMPAH-834
  base_branch: epic-OOMPAH-768--task-OOMPAH-804
  base_sha: b98ebb40d269ebeb7a134dc43add36bf782d9402
  updated_at: '2026-08-06T09:18:22.794194+00:00'
---
## Summary

Implement the production backend and event cutover for all nine ImplementationWorkflow actions: implementation_start, direct_owner_claim, duplicate_screening, focus_handoff, worker_exit, validation_submission, authority_revocation, implementation_retry, and implementation_recovery. Add a crash-safe exact disposition/effect-receipt ledger keyed by project, task, workflow generation, action, and immutable head/evidence; make inspect/apply/verify restart-idempotent and project-scoped. Route accepted API/ACP owner claims/releases, task handoffs/submissions, dispatch, worker exit, revocation, retry, duplicate screening, and startup recovery through schedule_event in enforce mode, disabling the corresponding legacy writer/timer/ownership path without calling whole-project sweeps from a task job. Relevant files: oompah/implementation_workflow.py, oompah/workflow_runtime.py or a new typed adapter module, oompah/orchestrator.py, oompah/server.py, workflow job/transition services. Required tests: native tracker plus temporary repo, exact multi-project routing, owner/submission races, child-exit crash after apply before verify, restart replay, stale generation fencing, retry timing, duplicate preflight, and enforce single-writer assertions. Acceptance: every implementation action has a real project-bound handler and production event source; durable job/receipt is the sole enforce-mode owner; no stale callback or legacy map can duplicate an effect.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 09:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 09:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
