---
id: OOMPAH-603
type: feature
status: Open
priority: 2
title: Define and enforce repository hygiene health thresholds
parent: OOMPAH-588
children: []
blocked_by:
- OOMPAH-600
- OOMPAH-601
- OOMPAH-602
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:03.538398Z'
updated_at: '2026-07-30T16:04:48.114248Z'
work_branch: epic-OOMPAH-588--task-OOMPAH-603
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 011f90700a51d70bffc65436c95b7ee557a31fc8aef83e8b4a190a4052525e42
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 661d86ba-56f8-4c9b-b380-2a29ba17f468
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T16:04:38.819299+00:00'
  claim_expires_at: '2026-07-30T16:34:38.819299+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 2f2fbd3c-e73d-483d-8a4f-08e8e21d769a
oompah.work_branch: epic-OOMPAH-588--task-OOMPAH-603
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-588--task-OOMPAH-603
  base_branch: epic-OOMPAH-588
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T16:04:45.759569+00:00'
---
## Summary

Implementation scope

Turn cleanup inventory into actionable health rather than raw counts. Report registered worktrees and local/remote branches by active, dirty, unmerged, terminal-protected, shared-owner, and safely-prunable categories; define configurable age/count thresholds in .env/.env.example; alert only on overdue safely-prunable artifacts or cleanup errors. Provide an operator verification path in docs/. Relevant files include maintenance status/state APIs, cleanup scheduler, dashboard/operator docs, and configuration.

Tests

Cover healthy protected inventory, overdue safe artifacts, dirty/unmerged preservation, threshold configuration, cleanup success/alert clear, restart persistence, and dashboard/API rendering. Run focused health/UI tests and make test.

Acceptance criteria

Operators can distinguish necessary retained work from hygiene debt, green status is based on zero overdue safe artifacts/errors rather than an unrealistic zero-branch count, and alerts clear after safe cleanup.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 16:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 16:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
