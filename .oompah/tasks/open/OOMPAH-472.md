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
updated_at: '2026-07-28T18:09:18.747422Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

