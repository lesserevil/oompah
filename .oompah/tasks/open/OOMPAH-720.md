---
id: OOMPAH-720
type: bug
status: Open
priority: 1
title: Keep owner-override fingerprints stable while audit attempts rotate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:07:40.475708Z'
updated_at: '2026-08-03T14:08:03.776440Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 19d92ef9754138f3ae89b8227dcae35ea9d72bcbc1f90b4350a126e5c6913929
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: dad6c1c4-f5fd-482f-9e9d-561fa9773b7b
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T14:07:53.208055+00:00'
  claim_expires_at: '2026-08-03T14:37:53.208055+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 89908f17-8bb3-4398-8d81-23b89256cfad
---
## Summary

Live reproduction on deployed main b97187ab after OOMPAH-604 and OOMPAH-663: EXOCOMP-171 is integrated at exact unchanged head e826d0d584294524cd0abd708456c457a50f11ed and its Done audit audit-bad47351b510 had two candidates terminate on the OOMPAH-719 tool-policy bug. An authenticated project owner then requested a Done audit override twice, refreshing task detail between attempts. Both requests returned HTTP 409: The task changed before the override was requested; refresh and retry. No task implementation, integrated SHA, branch, dependency, or acceptance evidence changed; only terminal-audit attempt/retry bookkeeping was advancing. The final candidate subsequently launched.

Implementation scope:
- Reproduce an owner override racing candidate completion/rotation for one active terminal request.
- Ensure canonical EvidenceFingerprint excludes audit-attempt lifecycle metadata, comments, retry counters, provider/model identity, and snapshot-refresh generation.
- Resolve the current active audit and current tracker issue under one ownership lock or re-fetch/recompute inside the lock so stale issue-snapshot timing cannot cause a false mismatch.
- Preserve a fail-closed 409 for genuine evidence changes such as a changed integrated SHA, task head, target, project, or acceptance-relevant task content.
- Make repeated identical authorized overrides idempotent across dispatch, candidate exit, and retry scheduling; they must either apply once or report already completed, never loop on refresh-and-retry.

Relevant code: server.py terminal override routing and _with_issue_ownership_lock; terminal_transition_coordinator.py active-record selection/fingerprint comparison; terminal_audit.py compute_issue_evidence_fingerprint; tracker snapshot/cache invalidation; audit candidate rotation.

Required tests:
- Stage an integrated Done audit, start candidate 1, terminate it, race candidate-2 rotation with an authenticated owner override, and prove the first valid override succeeds exactly once.
- Repeat with a stale board/detail snapshot while the tracker source generation advances only for audit metadata/comments.
- Verify genuine integrated-SHA/task-evidence changes still return 409.
- Verify all duplicate audit records are retired, running authority is revoked safely, terminal counters converge, and alerts clear.
- Run focused coordinator/API/race tests and the full Makefile gate.

Acceptance criteria:
- EXOCOMP-171-style owner recovery cannot be blocked by audit-attempt rotation when canonical task evidence is unchanged.
- No manual metadata edits or duplicate terminal restaging are required.
- Genuine stale-evidence overrides remain rejected.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 14:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 14:08
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
