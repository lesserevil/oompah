---
id: OOMPAH-654
type: task
status: Open
priority: null
title: Keep service lifecycle identity metadata out of git worktree status
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T10:29:49.323393Z'
updated_at: '2026-07-31T10:31:16.510044Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8636c86f6d347afd10831ff399fc2b9d01193f270c6c2981b38987c794a9a5b9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4bb78865-92a3-408e-82b7-71458b85682c
  claim_owner: f6d86559-4e9d-42bf-ac66-416781dbb14f
  claimed_at: '2026-07-31T10:31:07.284463+00:00'
  claim_expires_at: '2026-07-31T11:01:07.284463+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: b5c9fce1-9a14-41d0-b3b8-32a3357f089e
---
## Summary

Regression found immediately after deploying OOMPAH-652 on merged main ec0ec7d89: normal make restart safely creates .oompah.pid.meta beside the ignored .oompah.pid, but .gitignore ignores only *.pid. Canonical main becomes dirty solely because the service is running. Implementation scope: add the exact lifecycle metadata and any atomic temporary variants created by Makefile identity capture to the appropriate gitignore rules without broadly ignoring unrelated metadata; audit Makefile cleanup/start/restart paths and documentation if necessary. Add a regression test that creates the configured PID_FILE/PID_META_FILE artifacts in a representative checkout and proves git status remains clean while unrelated *.meta files remain visible, and verify make restart/status lifecycle tests. Acceptance: a normal running service with .oompah.pid and .oompah.pid.meta (including transient .tmp.* files if observable) does not dirty a clean checkout; unrelated metadata is not hidden; focused tests and git diff --check pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 10:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 10:31
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
