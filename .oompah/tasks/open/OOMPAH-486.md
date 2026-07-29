---
id: OOMPAH-486
type: feature
status: Open
priority: 1
title: Add terminal-audit metrics, maintenance health, and actionable alerts
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-483
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:25.195304Z'
updated_at: '2026-07-29T02:04:23.117508Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4e7f3870005234da335ab42730b57e4a6e6cd1432e2297b0d9226918d8bae59f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ecd00767-6d54-4f09-b519-5eb1d38621de
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:04:16.582239+00:00'
  claim_expires_at: '2026-07-29T02:34:16.582239+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f17c37b1-df78-4eb3-9af1-1ac083d11e9d
oompah.work_branch: epic-OOMPAH-460
---
## Summary

Implementation scope

Track counters/gauges for queued, running, passed, failed, retried, stale-discarded, overridden, grandfathered, and no-independent-candidate audits, plus oldest queue age and last successful audit time. Surface them in the existing snapshot/maintenance status shapes. Add dashboard alerts only when no independent candidate exists, an audit exceeds the configured attempt/age threshold, queue recovery fails, or persistence is corrupt. Deduplicate by project/task/audit and clear alerts on recovery. Normal queued/running/passed audits must not alert.

Tests

Use deterministic clocks to cover metric increments, restart restoration, per-project isolation, oldest age, alert threshold/dedup/clear, no-candidate instructions, corrupt persistence, and absence of normal-operation alerts. Run observability tests and make test.

Acceptance criteria

Operators can distinguish healthy validation throughput from an actionable audit stall without receiving routine operating-procedure noise.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
