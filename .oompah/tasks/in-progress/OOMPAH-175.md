---
id: OOMPAH-175
type: task
status: In Progress
priority: 1
title: Implement current supported-release branch catalog API
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-174
labels: []
assignee: null
created_at: '2026-07-13T02:35:44.755827Z'
updated_at: '2026-07-13T03:26:09.182970Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5ee32921-5459-4d93-bcaa-f1db6be88c76
---
## Summary

Read section 5 of plans/release-branch-addendums.md. Implement ReleaseBranchCatalog and GET /api/v1/projects/{project_id}/release-branches. Discover remote heads with git ls-remote --heads origin, use local origin refs only as a stale fallback, and return only remotely available branches listed in supported_release_branches. Preserve configured ordering. Include formerly selected but deleted branches as unavailable history when requested by addendum readers. Cache successful discovery for 60 seconds and add invalidation hooks for tracked-branch pushes and successful addendum merges. Tests: filtering, configured order, stale fallback, first-load failure 503, cache expiry/invalidation, and deleted historic branch behavior. Acceptance: clients receive no free-form or glob-derived target candidates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 03:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 03:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:23
---
Understanding: OOMPAH-175 is not a duplicate — no other task covers the ReleaseBranchCatalog or GET /api/v1/projects/{project_id}/release-branches. OOMPAH-173 (schema, Done) and OOMPAH-174 (project config, In Progress) are distinct siblings under the same epic.

Plan:
1. Implement ReleaseBranchCatalog (oompah/release_branch_catalog.py) with list_candidates(project) using git ls-remote --heads origin, 60s cache, stale fallback via local refs/remotes/origin/*, deleted-branch history from addendums, and cache invalidation interface.
2. Add GET /api/v1/projects/{project_id}/release-branches endpoint in server.py returning {project_id, source_branch, branches: [{name, available, stale}], refreshed_at} with 503 on first-load failure.
3. Wire invalidation to tracked-branch push webhooks and successful addendum merges.
4. Tests: filtering, configured order, stale fallback, first-load 503, cache expiry/invalidation, deleted-branch history.
---
author: oompah
created: 2026-07-13 03:26
---
Discovery: Found all relevant code.

Key files:
- oompah/release_addendum_schema.py: Existing addendum schema (OOMPAH-173, Done)
- oompah/models.py:388 — supported_release_branches field (OOMPAH-174)
- oompah/cache.py — TTLCache with get/set/invalidate/invalidate_prefix
- oompah/server.py:797 — _api_cache = TTLCache(); cache key convention is 'noun:project_id'
- oompah/server.py:8001 — _handle_webhook_event; push event path is at 8100
- oompah/server.py:8880 — _webhook_advanced_tracked_branch (push to tracked branch)
- oompah/oompah_md_tracker.py:957 — _git() pattern (subprocess.run with cwd)

Plan:
1. Create oompah/release_branch_catalog.py with ReleaseBranchCatalog class: git ls-remote --heads origin, 60s TTLCache, stale fallback via refs/remotes/origin/*, historic-branch inclusion from addendum metadata.
2. Add GET /api/v1/projects/{project_id}/release-branches endpoint in server.py (returns 503 on first-load failure, 404 for unknown project).
3. Add cache invalidation in _handle_webhook_event for push events (on tracked-branch push), and expose invalidation function for addendum-merge hook.
4. Tests: filtering, configured order, stale fallback, first-load 503, cache expiry/invalidation, deleted-branch history.
---
<!-- COMMENTS:END -->
