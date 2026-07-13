---
id: OOMPAH-175
type: task
status: Open
priority: 1
title: Implement current supported-release branch catalog API
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-174
labels: []
assignee: null
created_at: '2026-07-13T02:35:44.755827Z'
updated_at: '2026-07-13T02:54:18.052421Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Read section 5 of plans/release-branch-addendums.md. Implement ReleaseBranchCatalog and GET /api/v1/projects/{project_id}/release-branches. Discover remote heads with git ls-remote --heads origin, use local origin refs only as a stale fallback, and return only remotely available branches listed in supported_release_branches. Preserve configured ordering. Include formerly selected but deleted branches as unavailable history when requested by addendum readers. Cache successful discovery for 60 seconds and add invalidation hooks for tracked-branch pushes and successful addendum merges. Tests: filtering, configured order, stale fallback, first-load failure 503, cache expiry/invalidation, and deleted historic branch behavior. Acceptance: clients receive no free-form or glob-derived target candidates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

