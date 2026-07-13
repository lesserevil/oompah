---
id: OOMPAH-182
type: task
status: In Progress
priority: 2
title: Add release-branch addendum inspection API and dashboard view
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-179
labels: []
assignee: null
created_at: '2026-07-13T02:36:18.950799Z'
updated_at: '2026-07-13T06:01:41.613594Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 25c964ea-7c37-4bd9-be0c-7f446fd80870
---
## Summary

Read section 7 Branch inspection of plans/release-branch-addendums.md. Implement GET /api/v1/projects/{project_id}/release-branches/{encoded_branch}/addendums and a Release branches dashboard view. Return all source tasks/epics with addendums for that branch, grouped by open, in_progress, in_review, blocked, merged, and archived, with source links and execution evidence. Include an informational untracked_commits warning for direct target-branch changes that cannot be mapped to addendums; do not represent raw commits as features. Tests: route-safe branch names, grouping/order, unavailable historical branches, source deep links, warning behavior, and empty/error UI states. Acceptance: a maintainer can inspect one release line and see its queued and delivered work without reading raw task metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

