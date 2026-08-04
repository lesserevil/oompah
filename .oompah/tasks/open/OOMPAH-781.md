---
id: OOMPAH-781
type: feature
status: Open
priority: 1
title: Cut terminal-audit lifecycle over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:58:59.010872Z'
updated_at: '2026-08-04T20:22:35.330000Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-781
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3e730440ffde04145aa9c18b89db7431eda9a2cd7a481c12d5b3ab63ea7ce0e7
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: aac864e3-c572-48a2-994d-c79c9ab49831
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T20:22:08.183805+00:00'
  claim_expires_at: '2026-08-04T20:52:08.183805+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 6479cc35-618b-4384-b2cd-6ee48a4db025
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-781
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-781
  base_branch: epic-OOMPAH-768
  base_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  updated_at: '2026-08-04T20:22:29.008927+00:00'
---
## Summary

Migrate audit request ownership, candidate selection, launch, rotation, finalization, result application, retries, exhaustion, and historical recovery into durable workflow jobs while retaining TerminalTransitionCoordinator safety. Model queued/running/finalizing/retry-wait/action-required explicitly; ensure normal candidate rotation/transport retry is informational; guarantee result finalization cannot be starved by comments/output; preserve independent-candidate policy and exact evidence. Required tests: no candidate, transport failure, dynamic policy denial, duplicate/revoked auditor, oversized output, restart at each stage, deleted branches, finalization starvation, and current audit enforcement suites. Acceptance: every In Validation task has a durable audit disposition and bounded recovery; no valid verdict is lost or indefinitely pending.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:22
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
