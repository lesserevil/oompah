---
id: OOMPAH-674
type: bug
status: Open
priority: 1
title: Include authenticated state in dashboard WebSocket bootstrap
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:42:35.189136Z'
updated_at: '2026-08-01T04:43:36.144150Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8ea86dc11708d3327cad1b4170a7bc0479709b0d035394c916c46d95e64eb484
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e50d0c8b-4d7d-4d75-ab36-ff7459606d07
  claim_owner: 1e454a96-d2b2-4725-b6ab-c6f7bfb0ceb8
  claimed_at: '2026-08-01T04:43:31.388040+00:00'
  claim_expires_at: '2026-08-01T05:13:31.388040+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 5637749b-8211-4add-b265-8d4beb69d435
---
## Summary

Bug follow-up to OOMPAH-670. The dashboard normally initializes from /ws, but websocket_endpoint sends _cached_state_snapshot_or_unavailable() directly while /api/v1/state augments the snapshot with http_auth. Therefore a fresh authenticated dashboard keeps httpAuthEnabled=false and status mutations include actor_login, which the authenticated server correctly rejects as actor_mismatch. Implementation scope: centralize and enrich public state snapshots so REST and every WebSocket state message include the same redacted build, service, and auth metadata; ensure no credentials or secret material can enter the payload. Add regression tests that exercise initial WebSocket state and refresh state under HTTP Basic auth and prove the dashboard status mutation omits client-supplied actor identity. Acceptance criteria: authenticated drag/drop and status changes succeed without actor_mismatch; REST and WebSocket expose consistent redacted http_auth.enabled; unauthenticated deployments preserve compatibility; focused tests and the configured Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 04:43
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 04:43
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
