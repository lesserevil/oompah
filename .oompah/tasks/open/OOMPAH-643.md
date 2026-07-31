---
id: OOMPAH-643
type: task
status: Open
priority: null
title: Reconcile stale terminal-audit enforcement records and live queue metrics
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:17:38.708513Z'
updated_at: '2026-07-31T06:18:18.125535Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9abbcf4dd79879d506fdc5f606cc6e4c8640347bccd38c7c18d8bad4639174ac
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 717c5e2e-0916-4ad5-8939-11708a4e79c5
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T06:18:11.143200+00:00'
  claim_expires_at: '2026-07-31T06:48:11.143200+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4c26d494-92b3-40d5-84b1-a992a04c101e
---
## Summary

Runtime recovery evidence on 2026-07-31 shows terminal_audit_health pending_count=0 and in_progress_count=0 while terminal_audit_enforcement still reports pending_audits=209, metrics queued=157, and an oldest queued OOMPAH-309 record that is not dispatchable. stale_discarded also rises on successive state reads/ticks (223 to 275) because TerminalAuditMetrics.sync_pending appears to rehydrate stale entries from TerminalAuditEnforcement.pending_audits after the runtime health scan discards them.

Implementation scope: make the enforcement persistence record, dispatchable audit set, health scan, and observability gauges converge after restart and terminal authority changes. Reconcile or remove pending entries whose task is no longer In Validation, whose audit/evidence revision is superseded, or whose transition was owner-overridden; ensure stale records are counted at most once and are not re-added on the next sync. The queued/running gauges and oldest queue identity must describe only genuinely dispatchable live audits, while lifetime queued_total and outcome counters remain monotonic. Relevant files: oompah/terminal_audit_enforcement.py, oompah/terminal_audit_observability.py, oompah/terminal_transition_coordinator.py, orchestrator startup/recovery synchronization, and their tests.

Required tests: persisted restart state containing mixed live and stale audits; terminal override and status/evidence revision changes; missing/archived task; multi-project isolation; repeated sync/tick idempotency; one legitimately queued audit remains visible and launchable. Acceptance: after recovery, enforcement pending count equals the live coordinator set, queued/running/oldest gauges are accurate, stale_discarded does not grow without a new stale event, terminal_audit_health agrees with observability, focused tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
