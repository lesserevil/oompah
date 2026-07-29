---
id: OOMPAH-472
type: feature
status: Open
priority: 1
title: Collect target-landing evidence for Merged audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-471
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:12.977543Z'
updated_at: '2026-07-29T01:18:20.755580Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ee2de8e4b05f7994081f063147b5bd36b38754fc06a14d8f81fb617cb98259c8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 299590cc-931e-4e24-a9c9-e8d118cef15b
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:18:13.317646+00:00'
  claim_expires_at: '2026-07-29T01:48:13.317646+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 726c807d-9b72-4c86-a114-7268cabd19c2
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Build a read-only MergedEvidenceCollector. Require a current passed Done audit for the same completion fingerprint. Resolve the source branch/review, intended target branch, reviewed source SHA, merge commit/result, target HEAD, CI status, and commit/content containment. Detect wrong-target merges, open or closed-unmerged reviews, failed CI, stale branch tips, deleted branches with authoritative merged-review evidence, and unique commits stranded outside the target. For epic and nested-epic rollups, include child Done audit IDs and prove the complete branch chain landed on the configured target.

Tests

Use Git and fake SCM fixtures for correct landing, wrong target, open review, closed without merge, failed/pending CI, squash/rebase/merge commits, deleted branch, source advanced after review, stranded commits, shared epic, and nested epic target chains. Run focused tests and make test.

Acceptance criteria

A Merged audit can distinguish actual correct-target landing from tracker labels or stale review history alone and reports precise evidence for every failure mode.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:18
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 01:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
