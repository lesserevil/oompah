---
id: OOMPAH-563
type: bug
status: Open
priority: 1
title: Make service-state persistence atomic and recover terminal-audit quarantine
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:36:54.712161Z'
updated_at: '2026-07-29T21:37:53.006245Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bdde81b07a41310991436e518c773d153354bfafae950790f7022c715f28a6f3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9e9faa16-2fc8-4f47-8cf8-00143fba229d
  claim_owner: c2c2ef6b-2a29-4c5e-a18b-825e02f11596
  claimed_at: '2026-07-29T21:37:47.657336+00:00'
  claim_expires_at: '2026-07-29T22:07:47.657336+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cfb10b58-eddd-4b60-8fc0-76274d98ace6
---
## Summary

Triggered by: OOMPAH-561

Live terminal-audit enforcement entered quarantine after .oompah/service_state.json was observed malformed twice during concurrent maintenance writes (Expecting ':' delimiter and Extra data). Scope: serialize orchestrator service-state read/modify/write operations with a process-local reentrant lock; write JSON through a same-directory temporary file and atomic replace; preserve and fail closed on an already-unreadable state document instead of overwriting it; keep terminal-audit callback merging compatible; add deterministic concurrent-writer and corrupt-state regression tests; document/verify recovery; and gracefully restart the live service after the tested fix is deployed so the current terminal-task baseline is rebuilt and the alert clears. Relevant files: oompah/orchestrator.py and focused service-state/terminal-audit tests. Acceptance criteria: concurrent paused/cursor/terminal-audit state updates produce one valid document containing every update; a corrupt document is not destroyed; terminal-audit baseline initializes without quarantine after restart; the dashboard alert disappears; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
