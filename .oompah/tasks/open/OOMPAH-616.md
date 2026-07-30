---
id: OOMPAH-616
type: bug
status: Open
priority: 1
title: Integrate terminal-audit retry ownership fencing
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:47:41.612111Z'
updated_at: '2026-07-30T20:48:34.012147Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-616
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 54f20cacdfc4e9acc07a8fbb560a8db4079825625f6ad4d699372e0d32e4497c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c4c196f0-002b-4ee3-a8c5-da9fb6bcdd3e
  claim_owner: c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b
  claimed_at: '2026-07-30T20:48:20.610665+00:00'
  claim_expires_at: '2026-07-30T21:18:20.610665+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 666032db-c114-4d08-9f56-ece5bc8e02e0
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-616
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-616
  base_branch: epic-OOMPAH-585
  base_sha: 64b9b00c55f34d164d4eca2dd6071887ea5b5bb3
  updated_at: '2026-07-30T20:48:31.160016+00:00'
---
## Summary

Implementation scope: land the already implemented and fully tested OOMPAH-615 fix onto the OOMPAH-585 epic branch. Reuse commit ce8a124fc from origin/OOMPAH-615; resolve only genuine conflicts with the current epic head. The change must serialize terminal-audit staging against implementation In Progress writes, fence in-flight retry dispatch before worker creation, suppress normal-exit retries after an In Validation handoff, wake the audit lane after cleanup, and release the fence when an incomplete audit returns work to Open. Relevant files: oompah/orchestrator.py, oompah/server.py, tests/test_dispatch_close_race.py, tests/test_orchestrator_handlers.py, and tests/test_terminal_status_interfaces.py. Tests: run the focused scheduler/server/audit race suites on the combined epic tree; preserve the recorded full-gate evidence from ce8a124fc (terminal mutation scan passed; 13,736 passed, 7 skipped) and allow Oompah's exact combined-tree gate to run at integration. Acceptance criteria: the commit is pushed on the child's expected epic task branch, integration cannot regress In Validation to In Progress, no stale implementation worker can start after terminal ownership, and the child is submitted through the normal epic integration queue.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 20:47
---
Claimed directly by the operator Codex session to transplant the already-tested OOMPAH-615 commit onto the valid OOMPAH-585 epic branch; do not dispatch a second implementation agent.
---
author: oompah
created: 2026-07-30 20:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 20:48
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
