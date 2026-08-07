---
id: OOMPAH-874
type: task
status: Open
priority: null
title: Classify cancelled exact gates as retryable scheduling, not CI failure
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T07:23:57.611687Z'
updated_at: '2026-08-07T07:30:47.830719Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e71daca7a4708b1529a58c4ff0ff21b218377c8a94a6cb3d4fa44dea29af6719
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: aca87dec-1fb7-4208-83f7-b792ace8e98d
  claim_owner: 1f41f145-fc51-4991-b60c-19864fd45ab6
  claimed_at: '2026-08-07T07:30:39.049878+00:00'
  claim_expires_at: '2026-08-07T08:00:39.049878+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9b98672f-7c97-4e15-952d-2f07bee4c517
---
## Summary

Live regression on OOMPAH-869 on 2026-08-07: the operator deliberately cancelled exact gate generation 8c6215cf after 57 seconds because it raced ahead of a critical-path gate. The cancellation was explicitly recorded as scheduling preemption, not a product-test failure. After resume, Oompah nevertheless kept the ci-fix label/state and dispatched a CI Failure Fixer, which began searching an unchanged, already-focused validated branch for nonexistent code defects. A direct owner takeover was also briefly raced by the scheduled retry before succeeding on a second attempt.\n\nImplementation scope:\n- Give exact-gate cancellation/authority withdrawal a durable outcome distinct from test failure.\n- Return the accepted exact head to a retryable Ready/integration state without adding ci-fix, emitting a branch-quality-failed warning, or dispatching a CI Failure Fixer.\n- Preserve real nonzero make-test failures as Needs CI Fix with the current diagnostics.\n- Ensure restart/resume reconciliation preserves the cancellation classification and queues the same immutable accepted head exactly once.\n- Fence retry scheduling so an authorized direct-owner takeover cannot race a newly scheduled CI-fixer retry after the takeover fence is persisted.\n- Keep operator-visible provenance describing who cancelled the generation and why.\n\nRelevant code: oompah/quality_gate.py cancellation/finalization paths, integration queue reconciliation in oompah/orchestrator.py, CI-fix dispatch classification, validation_resource_lease cancellation records, owner-claim takeover fencing in oompah/server.py, and dashboard alert projection.\n\nRequired tests:\n- Operator-cancel a running exact gate: task remains retryable at the identical accepted head, no ci-fix label/warning/agent is created, and the next gate may run normally.\n- Restart/resume after cancellation preserves one retryable queue entry and never converts it to test failure.\n- A genuine make-test nonzero result still dispatches CI-fix with its output tail.\n- Race a scheduled retry with an owner claim: the persisted human-only/takeover fence wins atomically and no new scheduler authority is installed.\n- Cover event/API projections so the UI distinguishes cancelled/retryable from failed/actionable.\n\nAcceptance criteria:\n- Replaying the OOMPAH-869 sequence cannot launch implementation work for a cancelled gate.\n- Exact head 519ec2e49 can be re-gated without a code-changing CI-fix cycle.\n- Owner takeover succeeds in one bounded request despite a concurrent retry candidate.\n- Focused quality-gate/integration/owner-claim tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

