---
id: OOMPAH-950
type: bug
status: Ready to Integrate
priority: 1
title: Retire direct-owner claim after durable validation submission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:26:10.227707Z'
updated_at: '2026-08-09T12:07:41.944830Z'
work_branch: OOMPAH-950
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-950
  head_sha: fe66b5cfcdb4e0f448dec17f271fe2edebe04f33
  submitted_at: '2026-08-09T11:16:49.854299+00:00'
  updated_at: '2026-08-09T11:16:49.854299+00:00'
oompah.work_branch: OOMPAH-950
---
## Summary

Triggered by: OOMPAH-947

Live reproducer: OOMPAH-947 was directly claimed by oompah-cli, submitted at exact pushed head 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5, and its durable validation_submission job completed the In Progress to Ready to Integrate transition. The old owner claim 6b1f041eebb442f0b1248c1c51b96662 remained active with retirement_pending=false, so workflow facts continued reporting implementation.active/direct_owner and standalone review/integration did not start. OOMPAH-804 records an earlier manual release after the same Ready-transition race. Root cause: ProductionImplementationWorkflowBackend applies the transition through TaskTransitionService without the orchestrator post-commit owner-retirement hook; validation-submission effects do not schedule exact-claim revocation; _reconcile_inactive_owner_claims intentionally skips a non-pending claim in Ready to Integrate.\n\nImplementation scope: make successful durable validation submission atomically hand off authority from the exact captured direct-owner claim to Ready-to-Integrate workflow ownership. Capture/fence the claim generation in the submission job, persist retirement intent before or together with the committed status transition, and schedule idempotent AUTHORITY_REVOCATION after commit. Preserve crash recovery, ABA replacement safety, exact head/evidence fencing, ordinary scheduler-worker submissions, failed/stale submissions, standalone and epic-child modes, and the rule that a failed status transition must not revoke continuing owner authority. Ensure state/WebSocket projections refresh after revocation and reconciliation repairs the post-commit/pre-revocation crash boundary without waiting for lease expiry. Relevant files: oompah/server.py _accept_worker_submission, oompah/implementation_workflow_adapter.py validation submission/backend transition, oompah/orchestrator.py owner-claim retirement/reconciliation, workflow job/transition hooks, and tests/test_owner_claim.py plus durable workflow adapter/runtime tests.\n\nRequired tests: production-shaped direct-owner claim plus accepted exact-head submit transitions to Ready and retires only that claim; crash/restart after status commit but before revocation enqueue converges; ABA replacement survives stale revocation; stale/head-mismatched or failed submissions retain the active claim; ordinary worker submission remains unchanged; standalone Ready work becomes review/integration eligible; epic child queues once; state facts no longer report implementation.active after handoff.\n\nAcceptance: accepted direct-owner submissions never require manual DELETE, Ready tasks are not stranded behind their former owner lease, claim retirement is durable/idempotent/exact-generation fenced across restart and races, no valid owner is prematurely revoked, focused owner/workflow/integration tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 11:16
---
Implemented durable exact direct-owner claim retirement after accepted validation submission. Serialized owner mutations with submission capture; checkpointed and replayed immutable transition intent across post-commit crashes; added idempotent state publication on revocation recovery; made reconciliation ABA-safe and commit-order safe. Independent re-review: no blockers. Validation: 530 focused tests passed; terminal mutation scan, secret scan, compile, and diff checks passed. Pushed fe66b5cfcdb4e0f448dec17f271fe2edebe04f33.
---
author: oompah
created: 2026-08-09 11:17
---
Retire the exact direct-owner claim after accepted validation submission with serialized authority capture, durable crash-safe transition intent replay, idempotent revocation publication, and ABA-safe reconciliation. 530 focused tests and independent no-blocker review passed.
---
author: oompah
created: 2026-08-09 11:22
---
Re-armed exact-head submission after restart reconciliation superseded the first validation event with an idempotent direct-owner-claim event. Reviewed head remains fe66b5cfcdb4e0f448dec17f271fe2edebe04f33; 530 focused tests pass.
---
author: oompah
created: 2026-08-09 12:07
---
Branch quality gate passed for `fe66b5cfcdb4e0f448dec17f271fe2edebe04f33` using `make test` in 161.1s. Review creation may proceed.
---
<!-- COMMENTS:END -->
