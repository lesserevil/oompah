---
id: OOMPAH-782
type: feature
status: Open
priority: 1
title: Cut review and CI reconciliation over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:00.734500Z'
updated_at: '2026-08-04T20:22:23.526782Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4d7be90effcf4eb44b89bc2e71d5b6a5bed23ea571f0690ffd8d2643f8526655
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9cfd4251-3c94-4af4-9e0c-55e933540ea3
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T20:22:21.953242+00:00'
  claim_expires_at: '2026-08-04T20:52:21.953242+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Migrate In Review and repair progression to unified review/CI/Git facts and durable observation/action jobs. Normalize open, draft, merged, closed-unmerged, missing PR, deleted source, changed head, capacity, CI pending/failing/passing, conflicts, and merge target. Use LandingFact for completion and TaskTransitionService for repair/terminal transitions. Required tests: provider timeout versus empty result, branch deletion after merge, head changes after recorded merge, capacity release/restart, CI registration delay, conflict repair, GitLab/GitHub parity, and UI reason parity. Acceptance: every In Review task has one durable owner/reassessment and naturally reaches merged, repair, retry, or actionable escalation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

