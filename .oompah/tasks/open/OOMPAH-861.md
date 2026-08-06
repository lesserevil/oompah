---
id: OOMPAH-861
type: task
status: Open
priority: null
title: Keep accepted branch identity immutable after owner-submit gate failure
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T13:27:20.466495Z'
updated_at: '2026-08-06T13:28:39.459835Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-861
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 210ae92181a8873ff8114a0ada021b62c6bd7c15043520e8a66fa5a16d3b94e9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 8d5d8230-a290-48c2-ad10-3a693a12c285
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T13:28:22.447086+00:00'
  claim_expires_at: '2026-08-06T13:58:22.447086+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a33a7b59-e651-4680-887e-dc51f00db7d7
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-861
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-861
  base_branch: epic-OOMPAH-763
  base_sha: 52cf744ab676b50bdb999e9b0feb39bc092418c1
  updated_at: '2026-08-06T13:28:34.258730+00:00'
---
## Summary

Live OOMPAH-860 regression on 2026-08-06 after OOMPAH-815 reached Done. OOMPAH-860 is a child of OOMPAH-763 with null work_branch. Direct-owner work was prepared on epic-OOMPAH-763--task-OOMPAH-860, but the authenticated submit validator rejected it and required plain OOMPAH-860. The exact same validated head was then pushed/submitted from OOMPAH-860; integration authority recorded task_branch=OOMPAH-860 and the exact full gate ran that branch. When the gate failed, CI repair dispatch recomputed epic-OOMPAH-763--task-OOMPAH-860, found the registered worktree still correctly checked out on the accepted OOMPAH-860 branch, and refused to reset it. This recreates the precise split identity that OOMPAH-815 promised to eliminate. Implementation scope: trace owner-claim submit validation, accepted IntegrationRecord persistence/projection, transition to Needs CI Fix/In Progress, and repair workspace creation; once a branch+head is accepted, persist and reuse that immutable branch for every repair/retry/audit path, including null/stale work_branch and parent status changes. Eliminate any post-accept fallback that recomputes hierarchy; make submit validation and repair resolution use the same canonical resolver/generation. Preserve exact remote-head/ancestry proof, dirty-worktree no-reset safety, concurrent resubmit fencing, and hierarchical branches before acceptance. Required tests: exact OOMPAH-860 sequence (hierarchical submit rejected, plain submit accepted, gate failure, repair reuses plain worktree); restart between acceptance/failure/repair; null and stale work_branch; parent/child status changes after acceptance; concurrent same-head submit; invalid remote/head/ancestry fails before mutation; canonical hierarchical control; no repeated zero-turn dispatch loop. Acceptance: every accepted submission can be repaired on the exact persisted branch without manual checkout/metadata edits, and submit validation can never require a branch that the subsequent repair dispatcher rejects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 13:28
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-06 13:28
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
