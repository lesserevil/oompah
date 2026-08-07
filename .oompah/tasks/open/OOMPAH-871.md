---
id: OOMPAH-871
type: bug
status: Open
priority: 1
title: Prevent provenance-only terminal tasks from watchdog reopen and redispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:24:14.554398Z'
updated_at: '2026-08-07T07:14:47.889391Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d5315e2b5150ac71c464336b3c712f7ea42c50006472f8171c1b4fe8b0d3179d
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4a38bc71-843b-41f8-8505-d73ab154df8b
  claim_owner: 1f41f145-fc51-4991-b60c-19864fd45ab6
  claimed_at: '2026-08-07T07:14:18.401638+00:00'
  claim_expires_at: '2026-08-07T07:44:18.401638+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a6c9d7ea-cecb-4fe8-9a73-92709eb330ab
---
## Summary

Triggered by: OOMPAH-576

Reproduce OOMPAH-576 after its original implementation merged and an operator explicitly retained the record only as terminal provenance. A watchdog later reopened and redispatched the task, causing a new documentation-only accepted head and another full validation/review cycle. Define and persist an authoritative provenance-only or terminal-suppression state that every watchdog, reconciliation path, dependency rollup, and restart recovery honors. Relevant code: watchdog task reconciliation, terminal-state evidence, archived/provenance metadata, dispatch eligibility, restart recovery. Required tests: terminal provenance records remain non-dispatchable across repeated watchdog ticks and service restart; legitimate owner-requested revision creates a new authority generation and can dispatch; stale branch or historical review observations cannot reopen the record; alerts explain malformed provenance metadata without mutating status. Acceptance: a task retained solely as merged/archived provenance cannot re-enter a dispatchable or validation state unless a project owner explicitly starts a new revision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

