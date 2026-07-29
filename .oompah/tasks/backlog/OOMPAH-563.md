---
id: OOMPAH-563
type: bug
status: Backlog
priority: 1
title: Make service-state persistence atomic and recover terminal-audit quarantine
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:36:54.712161Z'
updated_at: '2026-07-29T21:36:54.712161Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-561

Live terminal-audit enforcement entered quarantine after .oompah/service_state.json was observed malformed twice during concurrent maintenance writes (Expecting ':' delimiter and Extra data). Scope: serialize orchestrator service-state read/modify/write operations with a process-local reentrant lock; write JSON through a same-directory temporary file and atomic replace; preserve and fail closed on an already-unreadable state document instead of overwriting it; keep terminal-audit callback merging compatible; add deterministic concurrent-writer and corrupt-state regression tests; document/verify recovery; and gracefully restart the live service after the tested fix is deployed so the current terminal-task baseline is rebuilt and the alert clears. Relevant files: oompah/orchestrator.py and focused service-state/terminal-audit tests. Acceptance criteria: concurrent paused/cursor/terminal-audit state updates produce one valid document containing every update; a corrupt document is not destroyed; terminal-audit baseline initializes without quarantine after restart; the dashboard alert disappears; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

