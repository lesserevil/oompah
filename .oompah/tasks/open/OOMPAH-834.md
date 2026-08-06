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
updated_at: '2026-08-06T09:17:53.069366Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Implement the production backend and event cutover for all nine ImplementationWorkflow actions: implementation_start, direct_owner_claim, duplicate_screening, focus_handoff, worker_exit, validation_submission, authority_revocation, implementation_retry, and implementation_recovery. Add a crash-safe exact disposition/effect-receipt ledger keyed by project, task, workflow generation, action, and immutable head/evidence; make inspect/apply/verify restart-idempotent and project-scoped. Route accepted API/ACP owner claims/releases, task handoffs/submissions, dispatch, worker exit, revocation, retry, duplicate screening, and startup recovery through schedule_event in enforce mode, disabling the corresponding legacy writer/timer/ownership path without calling whole-project sweeps from a task job. Relevant files: oompah/implementation_workflow.py, oompah/workflow_runtime.py or a new typed adapter module, oompah/orchestrator.py, oompah/server.py, workflow job/transition services. Required tests: native tracker plus temporary repo, exact multi-project routing, owner/submission races, child-exit crash after apply before verify, restart replay, stale generation fencing, retry timing, duplicate preflight, and enforce single-writer assertions. Acceptance: every implementation action has a real project-bound handler and production event source; durable job/receipt is the sole enforce-mode owner; no stale callback or legacy map can duplicate an effect.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

