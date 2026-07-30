---
id: OOMPAH-601
type: bug
status: Open
priority: 1
title: Aggregate branch-ownership cleanup skips without warning floods
parent: OOMPAH-588
children: []
blocked_by:
- OOMPAH-600
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:00.331568Z'
updated_at: '2026-07-30T15:52:51.319249Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6d55bd19aff045e8d8aaf70e895e49bee62e7e4102e9a264dc04f07b2f713310
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c7b32848-de37-4399-a0ae-59299d927f15
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T15:52:50.620713+00:00'
  claim_expires_at: '2026-07-30T16:22:50.620713+00:00'
  retry_count: 0
  retry_after: null
---
## Summary

Implementation scope

Correct and consolidate aggressive cleanup handling for terminal child tasks that legitimately share an epic-owned branch. Resolve ownership through canonical task/epic aliases before deciding, preserve ambiguous/shared branches, and emit one structured summary per run with categorized counts instead of one warning per child every tick. Keep actionable corruption/unsafe-path cases as warnings or alerts. Measure and avoid the observed multi-second reconciliation slowdown. Relevant files include oompah/projects.py cleanup/ownership helpers, orchestrator maintenance status, and logs/state APIs.

Tests

Cover shared epic branches, task-style repair branches, aliases, missing project_id, cross-project same identifiers, dirty/unmerged branches, large batches, warning aggregation, and latency-safe bounded scans. Run focused cleanup tests and make test.

Acceptance criteria

Normal shared-branch ownership produces no warning flood, cleanup remains safe, categorized skip evidence is visible, and the maintenance tick stays within its configured healthy budget for representative inventory.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
<!-- COMMENTS:END -->
