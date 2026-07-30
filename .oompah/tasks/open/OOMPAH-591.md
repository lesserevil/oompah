---
id: OOMPAH-591
type: task
status: Open
priority: 1
title: Reconcile the pending audit backlog and stale In Validation tasks
parent: OOMPAH-585
children: []
blocked_by:
- OOMPAH-589
- OOMPAH-590
start_blocked_by: &id001 []
labels: []
assignee: null
created_at: '2026-07-30T14:14:26.620047Z'
updated_at: '2026-07-30T14:31:40.870457Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-591
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ac6c3b35bd7c18002b6490060a3766a824a03ff5ecae340fb32b28cef4da9ad1
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d8bb9312-8bfe-432d-ad50-5b00c67635d9
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T14:31:27.603756+00:00'
  claim_expires_at: '2026-07-30T15:01:27.603756+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 45b70643-a132-48f7-90d7-948bd21bb528
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-591
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-591
  base_branch: epic-OOMPAH-585
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T14:31:38.603206+00:00'
---
## Summary

Implementation scope

After provider validation and retry behavior land, run an idempotent recovery over existing pending terminal-audit metadata. Requeue eligible requests, supersede only stale evidence revisions, and reconcile OOMPAH-580 and OOMPAH-582 plus every other stale In Validation task without direct task-file edits or unsafe terminal overrides. Add bounded batch/restart behavior if the existing reconciler cannot drain the backlog safely.

Tests

Use persisted metadata fixtures for multi-request tasks, stale fingerprints, already-completed audits, restart midway, and repeated recovery passes. Run focused recovery tests and make test.

Acceptance criteria

Pending audit count reaches zero or every remainder has a specific actionable terminal failure; OOMPAH-580 and OOMPAH-582 leave In Validation correctly; no successful audit is duplicated or overwritten.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:31
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
