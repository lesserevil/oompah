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
updated_at: '2026-07-13T06:07:56.142472Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 06:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 06:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 06:03
---
Understanding: OOMPAH-182 is NOT a duplicate. Searched all tasks under the OOMPAH-172 epic. OOMPAH-175 covers the release-branch catalog endpoint (GET /api/v1/projects/{id}/release-branches), OOMPAH-176 covers the approval POST endpoint, OOMPAH-180 covers the task-detail UI, OOMPAH-181 covers the epic-detail UI. OOMPAH-182 is uniquely scoped to: (1) GET /api/v1/projects/{project_id}/release-branches/{encoded_branch}/addendums — returns all source tasks/epics with addendums for a branch, grouped by status; (2) a Release branches dashboard view; (3) untracked_commits warning for direct target-branch commits. No other task covers this endpoint or view. Proceeding with implementation. Blocker OOMPAH-179 (PR reconciliation) is not yet done, but the branch inspection endpoint only reads from AddendumRepository (OOMPAH-173, Done) and the git log, which are already available.
---
author: oompah
created: 2026-07-13 06:07
---
Discovery: Found all relevant code. OOMPAH-182 is not a duplicate — this is the only task covering GET /api/v1/projects/{project_id}/release-branches/{encoded_branch}/addendums and the Release branches dashboard view.

Key findings:
1. AddendumRepository (oompah/release_addendum_schema.py) — reads oompah.release_addendums from any task metadata. Done (OOMPAH-173).
2. ReleaseBranchCatalog (oompah/release_branch_catalog.py) — lists configured release branches. Done (OOMPAH-175).
3. Approval API (POST .../release-addendums) — creates addendums. Done (OOMPAH-176).
4. GET .../release-addendums for per-task view — Done (OOMPAH-180).
5. Dashboard task-detail UI — Done (OOMPAH-180), CSS classes reusable.
6. Route pattern: {branch_name:path} works in FastAPI — verified locally; handles both release/1.0 and release%2F1.0.

Implementation plan:
- server.py: Add GET /api/v1/projects/{project_id}/release-branches/{branch_name:path}/addendums. Scans all project tasks via tracker.fetch_all_issues() + AddendumRepository.read(), filters to target branch, groups by status, computes untracked_commits from git log vs collected result_commits (best-effort, silent on failure).
- dashboard.html: Add 'Release branches' button in toolbar, a release-branch-inspector overlay panel with project-select, branch-select (from catalog API), grouped addendum rows linked to source tasks, untracked_commits warning, empty/loading/error states, Escape-to-close.
- tests/test_server_release_branch_inspection.py: route-safe branch names, grouping/order, unavailable historical branches, source deep links, warning behavior, 404/503 cases.
---
<!-- COMMENTS:END -->
