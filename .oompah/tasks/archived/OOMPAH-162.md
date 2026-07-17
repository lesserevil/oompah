---
id: OOMPAH-162
type: bug
status: Archived
priority: 1
title: Tolerate stacked children merged to default branch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-10T16:20:40.351930Z'
updated_at: '2026-07-17T17:06:14.346921Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Repair the orchestrator handling for stacked epic children whose pull request was merged directly to the project default branch instead of the expected epic branch. This caused the dashboard to warn that COROOT-8 had COROOT-30 closed with an unmerged branch even though PR #3 was already merged to main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-10 16:20
---
Fixed stacked epic child landing checks so a child branch already merged to the project default branch is treated as landed instead of stuck against the expected epic branch. Added regressions for merged-label and deferred-Done paths. Verification: make test passed with 7461 passed, 5 skipped. Pushed commits 74d1e9e8, 6ad81fe4, and b3999ce9 to main; restarted the server and confirmed dashboard alerts are empty.
---
<!-- COMMENTS:END -->
