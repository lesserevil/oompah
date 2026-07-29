---
id: OOMPAH-474
type: feature
status: Open
priority: 1
title: Add the auditor-only structured result submission API and tool
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-466
- OOMPAH-469
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:14.992374Z'
updated_at: '2026-07-29T01:23:40.709806Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4cddd67c9f2bb5ce97c8ca4fd0e6672095b56fbaa867049566aadf017869676e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 055b299d-0232-4fad-9bce-0cd45b8b78a0
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:23:33.656797+00:00'
  claim_expires_at: '2026-07-29T01:53:33.656797+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 290691d7-1175-437f-9e95-ce12491f8102
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Add an internal result endpoint/tool keyed by audit ID and task/project identity. Accept only PASS, FAIL, or NEEDS_HUMAN plus the defined failure enum, concise summary, bounded structured evidence references, and optional questions/instructions. Authenticate the call as the running auditor session, verify that session owns the audit, validate payload size and enums, reject credentials/unsafe fields, and pass the typed result to the coordinator. The tool must not accept an arbitrary status. Make repeated identical submissions idempotent and conflicting submissions reject.

Tests

Cover owner session, wrong session/task/project, expired/stale audit, malformed enum, oversized output, attempted status injection, secret-like fields, duplicate/conflicting submissions, and coordinator failure. Run API/tool tests and make test.

Acceptance criteria

An auditor can submit exactly one safe structured verdict for its assigned audit; it cannot mutate state directly or affect another audit.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:23
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
