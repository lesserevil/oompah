---
id: OOMPAH-570
type: bug
status: Open
priority: 1
title: Recover interrupted integration leases and explicit blocked-head retries
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:53:31.874608Z'
updated_at: '2026-07-29T23:53:53.624372Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 70211f087949bc92d36b39a24ee18fe20444239fd436a12269a096e08f38a265
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 036e621e-1ce7-4d02-a09b-db482cbe58b2
  claim_owner: 7e0ec335-e793-4bc9-8be7-8876913419b0
  claimed_at: '2026-07-29T23:53:49.910005+00:00'
  claim_expires_at: '2026-07-30T00:23:49.910005+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c5e8cfe2-bd7d-48c1-8c97-1cd456726881
---
## Summary

Triggered by: OOMPAH-562

Implementation scope: make durable epic-child integration recover promptly after a service exec/restart interrupts an in-flight quality gate, and make an explicit task submission able to retry a blocked queue row even when task_branch and head_sha are unchanged. Preserve idempotency for periodic Ready-to-Integrate synchronization and for ready/integrating/integrated rows so no automatic retry loop or duplicate integration is introduced. Add an explicit retry flag or equivalent boundary between the submit API path and background queue synchronization. On orchestrator startup, safely identify/requeue abandoned integrating leases; ensure any active branch-quality-gate process group is terminated during shutdown before leases become reclaimable. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py, oompah/quality_gate.py, server submission wiring, and their tests. Tests: reproduce (1) blocked identical explicit resubmit versus background sync, (2) restart with a durable integrating row and rebased private head, (3) shutdown process-tree cleanup, and (4) no duplicate claims/integration. Acceptance criteria: an operator never waits for the hour-long lease after a normal restart, a same-head explicit resubmit clears a blocked row without branch-name workarounds, background sync remains idempotent, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:53
---
Accepted for implementation after live queue recovery exposed the restart-lease and same-head retry gaps.
---
author: oompah
created: 2026-07-29 23:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 23:53
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
