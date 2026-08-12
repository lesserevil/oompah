---
id: OOMPAH-1129
type: bug
status: Open
priority: 2
title: Record authenticated actor provenance for orchestrator and project pause changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T22:38:43.861744Z'
updated_at: '2026-08-12T16:00:24.375067Z'
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
  creation_marker: incident-20260811-pause-resume-actor-provenance
  request_fingerprint: 738e1cd8e4736a45f2ce8c6021cab3e8725c1dbf66885804f3a29d6d88d46eed
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 38f2e84ceca6b8d3f7825bb1250208bfefece105adca8503cfd43d2e8034e669
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e718b671ba2fdbbb19a8d883f561b0c2db585edcec4c48236d50827de106b774:11842
  claim_owner: 02fd371b-4f1d-4e9b-a422-f3effd90464e
  claimed_at: '2026-08-12T16:00:22.482885+00:00'
  claim_expires_at: '2026-08-12T16:30:22.482885+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

During the Trickle migration incident the server recorded an explicit orchestrator resume request at 2026-08-11T20:51:57Z, but neither logs nor retained state identify the authenticated principal or request source. Operators cannot determine who or what changed scheduling safety state.

Implementation scope:
- Add structured audit records for orchestrator and per-project pause/resume operations in oompah/server.py and the relevant persisted-state layer.
- Derive actor identity from the authenticated server principal or scoped capability; do not trust a caller-supplied actor field.
- Record timestamp, scope, previous/new state, request/correlation ID, and safe source metadata without storing credentials.
- Expose recent provenance through an operator API/UI surface and structured logs suitable for incident diagnosis.

Required tests:
- Exercise authenticated global and project pause/resume endpoints and verify complete provenance.
- Verify spoofed actor input cannot override the authenticated identity.
- Verify credentials and tokens never appear in audit records or logs.
- Verify provenance survives restart according to the documented retention policy.

Acceptance criteria:
- Every scheduling safety-state change can be attributed to an authenticated principal and request.
- Operators can distinguish API, UI, startup, and internal/system transitions.
- Existing pause/resume authorization and behavior remain unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 01:38
---
Direct operator ownership is active on branch OOMPAH-1130. The workflow-authorized Open → In Progress transition is currently unavailable because OOMPAH-1130 prevents publication of the required generation; this comment and branch are the durable ownership handoff until that blocker is repaired.
---
<!-- COMMENTS:END -->
