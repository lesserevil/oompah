---
id: OOMPAH-182
type: task
status: Done
priority: 2
title: Add release-branch addendum inspection API and dashboard view
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-179
labels: []
assignee: null
created_at: '2026-07-13T02:36:18.950799Z'
updated_at: '2026-07-13T06:19:04.549820Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 25c964ea-7c37-4bd9-be0c-7f446fd80870
oompah.task_costs:
  total_input_tokens: 192
  total_output_tokens: 5991
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 192
      output_tokens: 5991
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 192
    output_tokens: 5991
    cost_usd: 0.0
    recorded_at: '2026-07-13T06:19:01.639582+00:00'
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
author: oompah
created: 2026-07-13 06:17
---
Implementation: Added release-branch addendum inspection API and dashboard view.

Changes:
1. oompah/server.py: Added _compute_untracked_commits() helper and GET /api/v1/projects/{project_id}/release-branches/{branch_name:path}/addendums endpoint. The endpoint scans all project tasks via tracker.fetch_all_issues() + AddendumRepository.read(), groups addendums by status (open/in_progress/in_review/blocked/merged/archived), returns full to_raw() addendum dicts with identifier/title/type source links, and computes an informational untracked_commits warning via git log (best-effort, silent on failure, never claims raw commits are features).

2. oompah/templates/dashboard.html:
   - Added CSS for .release-branch-inspector-overlay and all .rbi-* classes (after epic addendum CSS)
   - Added 'Release branches' button to the toolbar (between Reviews and Console)
   - Added openReleaseBranchInspector()/closeReleaseBranchInspector()/_rbiKeyHandler()/_rbiPopulateProjectSelect()/_rbiOnProjectChange()/_rbiLoadBranchList()/_rbiOnBranchChange()/_rbiLoadBranchAddendums()/_rbiRenderInspectorBody()/_rbiShowNoProjectMessage() JS functions
   - Added the release-branch-inspector-overlay panel HTML (project select, branch select, body with live region)

3. tests/test_server_release_branch_inspection.py: 39 new tests covering all required scenarios (route safety, grouping, historical branches, source deep links, warning behavior, empty/error states, _compute_untracked_commits unit tests).
---
author: oompah
created: 2026-07-13 06:18
---
Verification: make test — 7925 passed, 28 skipped, 0 failures. All 39 new tests pass.

Coverage confirmed:
- TestRouteSafety (4): branch/1.0 as path, branch%2F1.0 encoded, dots, deep nesting
- TestGroupingAndOrdering (9): all 6 status groups, cross-branch exclusion, multi-task
- TestSourceDeepLinks (6): identifier, title, type task/epic, full addendum dict, included_child_ids
- TestHistoricalBranches (2): historical branches return 200, nonexistent branch returns empty groups
- TestUntrackedCommitsWarning (6): no repo_path, git failure, all tracked, untracked present, not-a-feature, cap at 50
- TestErrorCases (5): 404, tracker 503, fetch 503, malformed metadata graceful, response keys
- TestComputeUntrackedCommits (7): no repo, OSError, nonzero rc, all tracked, untracked, cap 50, correct git command
---
author: oompah
created: 2026-07-13 06:18
---
Completion: Delivered GET /api/v1/projects/{project_id}/release-branches/{branch_name:path}/addendums and a Release branches dashboard view.

Deliverables:
1. server.py: _compute_untracked_commits() + GET .../release-branches/{branch}/addendums — groups all source tasks/epics by addendum status, returns full to_raw() evidence, computes untracked_commits warning via git log (informational, never claims raw commits are features), 404/503 error contracts, graceful degradation throughout.

2. dashboard.html: Release branches inspector overlay panel — toolbar button, project/branch selects, Escape-to-close, aria-modal, aria-live region, loading/empty/error states, grouped entries with identifier deep links (openDetailPanel), PR links, untracked_commits warning section, reuses existing release-addendum-status CSS classes.

3. tests/test_server_release_branch_inspection.py: 39 tests covering route safety, grouping/order, unavailable historical branches, source deep links, warning behavior, empty/error UI states, and _compute_untracked_commits unit coverage.

Full suite: 7925 passed, 0 failures. Branch pushed to origin/epic-OOMPAH-172. A maintainer can now select any configured release line in the dashboard and see its queued and delivered work without reading raw task metadata.
---
author: oompah
created: 2026-07-13 06:18
---
Implemented GET /api/v1/projects/{project_id}/release-branches/{branch}/addendums (section 7 Branch inspection) with grouping by status, source deep links, execution evidence, and informational untracked_commits warning. Added Release branches dashboard inspector overlay with project/branch selects, loading/error/empty states, grouped addendum rows linking back to source tasks, PR links, Escape-to-close, aria-modal accessibility. 39 new tests cover route safety, grouping, historical branches, source links, warning behavior, and error cases. Full suite 7925 passed.
---
author: oompah
created: 2026-07-13 06:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 128
- Tokens: 192 in / 6.0K out [6.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 18s
- Log: OOMPAH-182__20260713T060148Z.jsonl
---
<!-- COMMENTS:END -->
