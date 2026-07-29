---
id: OOMPAH-570
type: bug
status: Backlog
priority: 1
title: Recover interrupted integration leases and explicit blocked-head retries
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:53:31.874608Z'
updated_at: '2026-07-29T23:53:31.874608Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-562

Implementation scope: make durable epic-child integration recover promptly after a service exec/restart interrupts an in-flight quality gate, and make an explicit task submission able to retry a blocked queue row even when task_branch and head_sha are unchanged. Preserve idempotency for periodic Ready-to-Integrate synchronization and for ready/integrating/integrated rows so no automatic retry loop or duplicate integration is introduced. Add an explicit retry flag or equivalent boundary between the submit API path and background queue synchronization. On orchestrator startup, safely identify/requeue abandoned integrating leases; ensure any active branch-quality-gate process group is terminated during shutdown before leases become reclaimable. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py, oompah/quality_gate.py, server submission wiring, and their tests. Tests: reproduce (1) blocked identical explicit resubmit versus background sync, (2) restart with a durable integrating row and rebased private head, (3) shutdown process-tree cleanup, and (4) no duplicate claims/integration. Acceptance criteria: an operator never waits for the hour-long lease after a normal restart, a same-head explicit resubmit clears a blocked row without branch-name workarounds, background sync remains idempotent, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

