---
id: OOMPAH-684
type: task
status: Open
priority: null
title: Prevent stale retry dispatch after operator task resubmission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:44:29.390457Z'
updated_at: '2026-08-01T21:47:36.950811Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 57d3415e0f3269957b9627d45a447cc345e9142b40cdb196449e066c34db7fe9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 666b274d-d98e-4f70-856d-ca2c83dbd6cc
  claim_owner: 9c8dda42-c87b-429a-bdb1-42da8ebebe7e
  claimed_at: '2026-08-01T21:47:26.691226+00:00'
  claim_expires_at: '2026-08-01T22:17:26.691226+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f2ea5450-ecd6-4b8b-924e-2599880ff3a1
---
## Summary

Regression of merged OOMPAH-661 observed on NODEVIRT-7 on 2026-08-01. An operator recovered the preserved worktree, committed validated head bb916af, pushed the assigned branch, and successfully submitted it through the operator-authenticated task CLI. The task entered Ready to Integrate. Roughly three minutes later, stale retry/assignment authority launched implementation run e84dc6296e524e23ac0255bfb692c480 and rewrote the canonical task to In Progress with integration state working, despite the accepted head already being pushed and queued. The redundant worker initially performed only read-only inspection; an operator live handoff told it not to mutate the accepted branch.

This is a direct recurrence of the generation-authority invariant from OOMPAH-661 and must be fixed at the race boundary rather than special-cased.

Implementation scope:
- Trace operator CLI submit through api_submit_issue, native Markdown tracker persistence, retry cancellation, refresh/event coalescing, claimed/running state, and due retry dispatch to identify how stale authority survived.
- Make accepted submission and retry/claim cancellation one atomic authority transition for the exact task generation. A due callback or candidate selected before submission must re-read and reject Ready to Integrate, matching integration metadata/head, replacement assignment, or changed tracker updated_at before it writes In Progress or launches a worker.
- Fence already-starting dispatch setup so a submit that wins before provider launch cancels setup and removes the running/claimed row without tracker rollback.
- If a worker process crosses the boundary, terminate or quarantine it before repository mutation and preserve the accepted Ready to Integrate generation.
- Ensure same-head operator resubmission from Needs Human exercises identical cancellation semantics to a first worker submission.
- Add observability identifying which authority generation lost the race without exposing tokens.

Relevant code: retry authority generation and persisted retries, normal dispatch claim/setup, worker assignment metadata, api_submit_issue/task CLI submission reconciliation, native tracker cache/update ordering, running state, and event-driven refresh.

Required deterministic tests:
- Failed/Needs Human native task is operator-resubmitted at a pushed head while a due retry callback is selected; only Ready to Integrate survives and no worker launches.
- Submit wins during dispatch setup before provider launch; setup aborts without writing In Progress.
- Provider launch crossing the boundary cannot mutate the worktree and accepted head/status are restored automatically.
- Same-head resubmission clears retrying, claimed, running placeholder, integration working metadata, and stale assignment atomically.
- Restart/event coalescing cannot rehydrate the withdrawn retry.
- Unrelated tasks and legitimate post-rejection retries remain unaffected.

Acceptance criteria:
- The exact NODEVIRT-7 sequence cannot redispatch after successful resubmission.
- Ready to Integrate head/status/integration metadata remain authoritative through all tested interleavings.
- Focused retry/submission/dispatch race tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 21:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
