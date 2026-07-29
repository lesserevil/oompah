---
id: OOMPAH-488
type: task
status: Open
priority: 1
title: Validate the complete task Done-Merged-Archived audit lifecycle
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-476
- OOMPAH-477
- OOMPAH-479
- OOMPAH-481
- OOMPAH-484
- OOMPAH-485
- OOMPAH-486
- OOMPAH-487
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:27.238658Z'
updated_at: '2026-07-29T02:09:47.678148Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3d3ae26df8c3bd62eb896f6ecfe8c0a0ea7b2cbe36c095fc3e808030a7029a2e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a1ab5d8b-6853-4b26-819e-fe95158ebadf
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:09:39.334206+00:00'
  claim_expires_at: '2026-07-29T02:39:39.334206+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: be6c7c61-0e0f-43d8-84fd-284d420fac05
oompah.work_branch: epic-OOMPAH-460
---
## Summary

Implementation scope

Create an end-to-end Git fixture and fake provider/SCM setup for one implementation task. Dispatch a worker with provider/model A, commit/push work, request Done, assert In Validation, dispatch provider/model B auditor, submit PASS, assert Done and review creation. Simulate correct review merge, assert a separate Merged audit with completion prerequisite, pass it, then age the task and pass a safe-retirement Archived audit. Assert durable comments/metadata, API summaries, metrics, state-branch commits, and restart recovery between at least two stages. Add failure variants for incomplete work, failed CI, wrong merge target, and unsafe archive.

Tests

This task is the test implementation. Keep fixtures deterministic and offline; do not call real providers or forges. Run the new test file repeatedly, relevant existing integration suites, and make test.

Acceptance criteria

The automated scenario proves three different auditors/contracts occur in order, the worker never self-certifies, each failure returns to the documented repair state, and state remains correct across restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 02:09
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
