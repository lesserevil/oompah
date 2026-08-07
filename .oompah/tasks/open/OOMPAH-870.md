---
id: OOMPAH-870
type: bug
status: Open
priority: 1
title: Land already-contained Ready heads without requiring a zero-diff forge review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:24:09.733359Z'
updated_at: '2026-08-07T07:13:01.759897Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b4c55ab50f13d1fbeeb1bf36f04eba9e9b39b2039e5f815d1f54b3740bb679c6
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: f48a9d8b-59b3-4b72-8dba-afd4c95b05cc
  claim_owner: 1f41f145-fc51-4991-b60c-19864fd45ab6
  claimed_at: '2026-08-07T07:13:00.129652+00:00'
  claim_expires_at: '2026-08-07T07:43:00.129652+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Triggered by: OOMPAH-612

Reproduce OOMPAH-612 after its exact accepted-head gate passes when the accepted branch head is already an ancestor of the target branch. The Ready integration path currently asks the forge for a replacement review even though the accepted head has zero target diff, receives no review, emits a persistent warning, and cannot reach a terminal state. Implement a durable Ready fast-path that revalidates exact accepted-head containment and terminal authority, records canonical no-op landing evidence, and advances through terminal audit/landing without creating or reusing an invalid review. Preserve OOMPAH-819 stale-review generation fences and OOMPAH-698 legacy In Review reconciliation semantics. Relevant code: integration/review staging, accepted-head containment checks, terminal transition coordinator, alert publication. Required tests: exact gate plus already-contained head terminates; stale or mismatched accepted heads remain rejected; restart/replay is idempotent; no forge warning is emitted for a valid zero-diff landing. Acceptance: an exact-gated Ready task whose accepted head is contained in target cannot deadlock waiting for an impossible forge review.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

