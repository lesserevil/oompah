---
id: OOMPAH-598
type: bug
status: Open
priority: 1
title: Detect and deliver standalone Ready to Integrate tasks without PRs
parent: OOMPAH-587
children: []
blocked_by:
- OOMPAH-593
start_blocked_by: &id001 []
labels: []
assignee: null
created_at: '2026-07-30T14:15:29.695490Z'
updated_at: '2026-07-30T15:36:48.145186Z'
work_branch: epic-OOMPAH-587--task-OOMPAH-598
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 804c0cd117349b00c1fad257b2fb304f290d07ececee26378ec020331156ebe8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 194f76ae-1442-46f5-b89f-0edde3c4fda9
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T15:36:36.835940+00:00'
  claim_expires_at: '2026-07-30T16:06:36.835940+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cc18d70f-5a11-48b4-9d0d-575d62d9af28
oompah.work_branch: epic-OOMPAH-587--task-OOMPAH-598
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-587--task-OOMPAH-598
  base_branch: epic-OOMPAH-587
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:36:44.968589+00:00'
---
## Summary

Implementation scope

Add reconciliation for standalone tasks whose tracker state is Ready to Integrate and whose branch is pushed, but which have neither an active integration execution nor an open PR. Select the configured delivery mechanism deterministically, enqueue/open it idempotently, and alert on genuinely undeliverable rows. Recover the current OOMPAH-574, OOMPAH-575, OOMPAH-576, and OOMPAH-581 rows. Do not create duplicate PRs or bypass the configured full gate. Relevant areas include landing reconciliation, integration queue, review creation, webhook state, and release-delivery status.

Tests

Cover pushed standalone branch, missing branch, existing open/closed PR, existing queue row, duplicate ticks, restart, gate failure/retry, and successful merge/audit. Run focused tests and make test.

Acceptance criteria

A pushed standalone Ready task cannot remain invisible with no PR/queue activity beyond the reconciliation interval; all four current rows obtain a valid delivery path or explicit actionable failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:17
---
Coordination: OOMPAH-593 exclusively owns delivery/live verification of OOMPAH-575. After OOMPAH-593 completes, this task owns stranded-ready reconciliation and delivery for OOMPAH-574, OOMPAH-576, and OOMPAH-581 plus the generic watchdog fix; do not duplicate OOMPAH-575 work.
---
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:36
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
