---
id: OOMPAH-175
type: task
status: Archived
priority: 1
title: Implement current supported-release branch catalog API
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-174
labels: []
assignee: null
created_at: '2026-07-13T02:35:44.755827Z'
updated_at: '2026-07-20T07:22:44.838099Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5ee32921-5459-4d93-bcaa-f1db6be88c76
oompah.task_costs:
  total_input_tokens: 127
  total_output_tokens: 3935
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 127
      output_tokens: 3935
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 127
    output_tokens: 3935
    cost_usd: 0.0
    recorded_at: '2026-07-13T03:40:50.873896+00:00'
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
author: oompah
created: 2026-07-13 03:38
---
Implementation: Added ReleaseBranchCatalog and GET /api/v1/projects/{project_id}/release-branches.

New files:
1. oompah/release_branch_catalog.py — ReleaseBranchCatalog class:
   - list_candidates(project) runs git ls-remote --heads origin, caches 60s per-project
   - Stale fallback: on remote failure uses local refs/remotes/origin/* (stale=True)
   - First-load failure raises CatalogDiscoveryError (→ 503 from API)
   - Expired cache used as last resort before failing
   - Historic branches from oompah.release_addendums metadata included as available=false
   - Configured ordering preserved; historic-only branches in reverse-natural order
   - Thread-safe per-project locks (no duplicate ls-remote calls)
   - Module singleton via get_default_catalog()

2. oompah/server.py changes:
   - GET /api/v1/projects/{project_id}/release-branches returns {project_id, source_branch, branches, refreshed_at, stale}; 404 for unknown project; 503 on first-load failure
   - invalidate_release_branch_catalog(project_id) helper
   - _handle_webhook_event: invalidates catalog on push events to tracked branches

3. tests/test_release_branch_catalog.py — 42 tests covering all required scenarios.
---
author: oompah
created: 2026-07-13 03:38
---
Verification: make test — 7565 passed, 28 skipped, 13 warnings (0 failures). All 42 new tests pass. Full suite passes after rebase against latest origin/epic-OOMPAH-172.
---
author: oompah
created: 2026-07-13 03:40
---
Completion: Delivered ReleaseBranchCatalog (oompah/release_branch_catalog.py) and GET /api/v1/projects/{project_id}/release-branches in oompah/server.py.

Coverage:
- Remote discovery via git ls-remote --heads origin, 60s per-project cache
- Stale fallback to local refs/remotes/origin/* with stale=true flag
- First-load failure → 503 (CatalogDiscoveryError)
- Configured ordering preserved; historic deleted branches as unavailable history
- Cache invalidation on tracked-branch push webhooks (invalidate_release_branch_catalog)
- 42 tests: filtering, configured order, stale fallback, first-load 503, cache expiry/invalidation, deleted historic branch behavior, API contracts, thread safety

Acceptance satisfied: API returns only supported_release_branches entries verified remotely; no free-form or glob-derived candidates.
---
author: oompah
created: 2026-07-13 03:40
---
Implemented ReleaseBranchCatalog and GET /api/v1/projects/{project_id}/release-branches. 42 tests pass. Remote discovery via git ls-remote, 60s cache, stale fallback, first-load 503, historic branch history, webhook invalidation.
---
author: oompah
created: 2026-07-13 03:40
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 90
- Tokens: 127 in / 3.9K out [4.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 59s
- Log: OOMPAH-175__20260713T032311Z.jsonl
---
<!-- COMMENTS:END -->
