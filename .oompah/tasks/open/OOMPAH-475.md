---
id: OOMPAH-475
type: feature
status: Open
priority: 1
title: Dispatch, retry, and recover independent auditor agents
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-465
- OOMPAH-466
- OOMPAH-468
- OOMPAH-469
- OOMPAH-470
- OOMPAH-471
- OOMPAH-472
- OOMPAH-473
- OOMPAH-474
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:15.927352Z'
updated_at: '2026-07-29T01:25:07.904259Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0f24e8e01a09c697f39206579599cd6c6686fb4e0022d352835b5a8cfcc1eaef
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 66a68ef5-8a42-4788-b406-5ad8aaab6b4d
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:24:57.693498+00:00'
  claim_expires_at: '2026-07-29T01:54:57.693498+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c84f562e-a966-429d-911a-79a008c82eab
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Add a priority audit lane that reads persisted In Validation requests, gathers target-specific evidence, selects an independent candidate, claims the task/epic branch, and starts the reserved auditor focus. Auditors consume the normal global concurrency limit and serialize with implementation workers on the same task or epic branch. Persist running attempt identity before launch. On transient provider/tool failure, rotate candidates with normal backoff up to OOMPAH_AUDIT_MAX_ATTEMPTS. Rehydrate pending/running attempts on restart, detect abandoned auditor sessions, and retry idempotently. If every independent candidate is exhausted, submit the no-independent-auditor failure so the coordinator moves to Needs Human with configuration instructions.

Tests

Cover priority versus ordinary Open work, concurrency limit, one-agent-per-epic serialization, successful result, candidate rotation, rate limit, timeout, crash, restart, abandoned claim, changed fingerprint during run, stale result, max attempts, no candidates, and actionable final comment. Run focused scheduler tests and make test.

Acceptance criteria

Every eligible persisted audit is eventually dispatched once, retried safely, or moved to actionable Needs Human; auditor work never races a branch writer or exceeds configured global concurrency.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:25
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
