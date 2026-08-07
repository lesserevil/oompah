---
id: OOMPAH-899
type: task
status: Open
priority: null
title: Make lifecycle startup timeout safe for late listeners
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T17:37:48.469758Z'
updated_at: '2026-08-07T17:47:18.747584Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b664e59942164efb5f18ae48ee800b4e9385baee1e8ec13416a73f3e3e760745
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c3476554-2335-4932-b42d-86e2579d1c5b
  claim_owner: 49784b9a-a068-4eb9-b3ab-0679503393f6
  claimed_at: '2026-08-07T17:47:14.721310+00:00'
  claim_expires_at: '2026-08-07T18:17:14.721310+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Live deployment bug: Makefile start hard-codes a 10-second listener deadline. On a slow but otherwise successful server startup, the lifecycle command exits as failed and deletes the PID and metadata artifacts while its verified owned process continues running and later binds the configured port. A later invocation cannot reliably distinguish or safely manage that late listener.

Implementation scope:
- Replace the hard-coded listener deadline with a documented OOMPAH_* configuration in .env/.env.example, using a safe positive bounded range and preserving current behavior as the default.
- Make start timeout handling identity-safe: do not delete or lose verified owned PID/metadata evidence merely because the listener deadline elapsed. Retain it or quarantine it with an explicit recoverable lifecycle state and operator guidance.
- Re-check the exact owned process identity after a timeout and distinguish a genuine startup failure from a late successful listener. A late listener must remain discoverable by make status/start/stop and must not be treated as an unknown orphan.
- Preserve fail-closed behavior for PID reuse, mismatched metadata, unverified processes, and a port occupied by a foreign process; never signal an unverified process.
- Keep restart/graceful lifecycle semantics and private test/gate isolation intact.

Relevant areas: Makefile lifecycle targets, lifecycle PID/meta helpers and status logic, .env.example, and lifecycle integration tests.

Required tests:
- Slow startup that exceeds the configured wait but later listens: lifecycle identity is retained or quarantined truthfully, later status identifies it, and a subsequent lifecycle operation manages only that exact process.
- Late-listener race after timeout: no deleted-identity orphan or duplicate server can bind the port.
- Genuine no-listener timeout, foreign-port occupant, PID reuse, and metadata mismatch remain fail-closed with no unsafe signal.
- Configured deadline bounds/default validation and make start behavior are covered.
- Existing slow-start, late-listener, PID/meta, status, stop/restart/graceful, and no-orphan focused suites pass.

Acceptance criteria:
- Startup wait duration is configurable only through bounded OOMPAH_* .env configuration; no hard-coded 10-second lifecycle deadline remains.
- A verified process that listens after the wait deadline is never silently orphaned or stripped of lifecycle identity.
- Lifecycle status and follow-up operations distinguish late success, confirmed startup failure, and unverified identity with actionable evidence.
- No code path deletes PID/meta evidence before the owned process is proven stopped or has been durably quarantined, and focused lifecycle tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

