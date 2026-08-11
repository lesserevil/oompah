---
id: OOMPAH-1075
type: bug
status: In Progress
priority: 1
title: Keep branch quality gates off restart reconciliation control ticks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T09:03:11.276660Z'
updated_at: '2026-08-11T09:03:49.157859Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: restart-quality-gate-control-plane-hol-20260811
  request_fingerprint: 482c48aeb6292612f79b0753dd7f1ffca72997a6a0b26b9b9b97e64ee766532b
---
## Summary

Triggered by: OOMPAH-1071

Live reproduction on deployed main aafbdac663 at 2026-08-11 08:58 UTC: opening draft PR #810 for exact OOMPAH-1071 head baa287e4 caused the server to run the configured branch quality gate synchronously inside the first post-restart orchestrator tick. The gate passed in 167.8s, but the tick took 137656ms, workflow liveness crossed its 120s reconstruction deadline into restart_overdue, terminal-audit scan/dispatch remained pending, /api/v1/state stayed on the stale pre-restart generation, and the UI showed a running-gate alert plus degraded health. When the gate completed, tracker authority had changed and the expensive publication was superseded, requiring another full reconcile. This is a control-plane head-of-line blocking bug, not a gate failure.\n\nImplementation scope: move standalone branch quality-gate execution and result waiting out of the orchestrator control tick into durable/independently scheduled work, or otherwise ensure the tick never awaits the external full-suite process. Preserve immutable exact-head snapshots, exact owner/generation cancellation, at-most-one gate per task/head, restart recovery, review adoption, and fail-closed result fencing. Liveness reconstruction and terminal-audit health/dispatch must continue while a multi-minute gate runs; tracker changes during the gate must not invalidate an unrelated liveness publication. Relevant code: standalone review/gate reconciliation in oompah/orchestrator.py, oompah/quality_gate.py, durable workflow scheduling/continuations, liveness reconstruction, and alert/state projection.\n\nRequired tests: deterministic barrier holding a real/fake gate beyond the restart deadline while repeated control ticks publish a complete fresh liveness snapshot, clear reconstruction_pending before deadline, scan/dispatch terminal audits, and keep HTTP/WebSocket generations advancing; concurrent tracker mutation supersedes only gate result authority, not liveness publication; restart recovers one exact gate without duplication; cancellation and task/head replacement remain fenced; active gate alert is informational and clears on completion; no request/control lock is held across the gate. Acceptance: a 3+ minute branch gate cannot make health restart_overdue or stall state generations, current divergence/action-required/exhausted stay zero, the gate outcome remains exact and durable, focused concurrency/restart tests pass, terminal mutation scan passes, and the full Makefile gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

