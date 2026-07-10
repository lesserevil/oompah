---
id: OOMPAH-162
type: bug
status: Backlog
priority: 1
title: Tolerate stacked children merged to default branch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-10T16:20:40.351930Z'
updated_at: '2026-07-10T16:20:40.351930Z'
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

