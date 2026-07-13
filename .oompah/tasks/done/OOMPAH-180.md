---
id: OOMPAH-180
type: task
status: Done
priority: 2
title: Build task release-addendum selection and status UI
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-174
- OOMPAH-175
- OOMPAH-176
labels: []
assignee: null
created_at: '2026-07-13T02:36:12.732590Z'
updated_at: '2026-07-13T05:07:20.676760Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1280aa1f-79b3-47ac-bcd4-2a4f10bac8b0
---
## Summary

Read section 7 Task detail of plans/release-branch-addendums.md. Replace the task-detail Release Picks section and Add Release Picks dialog with Release addendums and an accessible Add release branches dialog. Show rows attached to the source task only: target branch, lifecycle/queue state, PR link, and blocked error; do not show child-task links. For a Merged task, fetch the release-branch catalog, render selectable available supported branches as a labelled checkbox group, precheck/disable active selections, and submit all new selections once to the approval API with an idempotency key. Add loading, stale, empty, error, focus, and Escape behavior. Tests: DOM/rendering and request-contract tests for all states, including no child-task link and refresh-to-open after success. Acceptance: selecting two branches queues two addendums with one user action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 04:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 04:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:43
---
Understanding: OOMPAH-180 is not a duplicate. Searched all tasks under OOMPAH-172 epic and the full task graph. OOMPAH-181 (epic UI) is the closest sibling but covers a different page/component. OOMPAH-180 uniquely covers the task-detail UI for release addendum selection and status display.

Scope: Replace the task-detail Release Picks section and Add Release Picks dialog in oompah/templates/dashboard.html with Release addendums and an accessible Add release branches dialog. Show rows (target branch, lifecycle/queue state, PR link, blocked error) from the source task's oompah.release_addendums metadata only — no child-task links. For Merged tasks, fetch the catalog API (OOMPAH-175, Done), render checkboxes, precheck/disable active selections, submit all new selections via the approval API (OOMPAH-176). Add all required UI states. Tests required for all rendering/request-contract scenarios.

OOMPAH-176 (approval API) is in-progress; will implement against its planned contract from plans/release-branch-addendums.md section 6 and any stub code already present.
---
author: oompah
created: 2026-07-13 04:51
---
Discovery: OOMPAH-180 is not a duplicate. Found all relevant code.

Key files:
- oompah/templates/dashboard.html: existing release-picks CSS (lines 768-850), renderReleasePicksSection() (lines 4033-4116), openAddReleasePicksModal() (lines 4107-4115), openDetailPanel fetches /release-picks (line 4255), old dialog HTML (lines 6141-6194)
- oompah/release_addendum_schema.py: AddendumRepository.read() returns list[ReleaseAddendum]; to_raw() includes target_branch, status, pr_url, error
- oompah/server.py: POST /api/v1/issues/{id}/release-addendums (line 3295, OOMPAH-176 done); GET /api/v1/projects/{id}/release-branches (OOMPAH-175); GET /api/v1/issues/{id}/release-picks (line 4731); NO GET /api/v1/issues/{id}/release-addendums yet
- tests/test_dashboard_release_picks_section.py: old tests, 5 test_openDetailPanel_* tests will need updating

Implementation plan:
1. Add GET /api/v1/issues/{identifier}/release-addendums to server.py (reads AddendumRepository)
2. Add release-addendum CSS classes to dashboard.html
3. Add renderReleaseAddendumsSection() JS function (no child-task link, shows blocked error)
4. Add openAddReleaseBranchesDialog() / closeAddReleaseBranchesDialog() / submitAddReleaseBranchesDialog() (fetches catalog, fieldset/legend/checkbox, idempotency key, Escape-to-close, focus trap)
5. Update openDetailPanel: add /release-addendums parallel fetch, replace renderReleasePicksSection call with renderReleaseAddendumsSection
6. Add new dialog HTML (add-release-branches-dialog)
7. Update 2 old tests in test_dashboard_release_picks_section.py (openDetailPanel integration)
8. Add tests/test_dashboard_release_addendums_ui.py with all new UI tests
9. Add tests/test_server_release_addendums_get.py for GET endpoint
---
author: oompah
created: 2026-07-13 05:06
---
Verification: make test — 7724 passed, 28 skipped, 12 warnings (0 failures). All new tests pass after rebase against origin/epic-OOMPAH-172.

New tests added:
- tests/test_dashboard_release_addendums_ui.py: 67 tests covering CSS classes, renderReleaseAddendumsSection (no child-task link, status/branch/PR/error, Merged-only button), openDetailPanel integration (parallel fetch, passes state), dialog HTML structure, all 3 JS functions, Escape-to-close, single-POST acceptance criterion, refresh-to-open-after-success
- tests/test_server_release_addendums_get.py: 15 tests covering GET endpoint contract, all statuses round-trip, 404, null stored value
- Updated 2 tests in test_dashboard_release_picks_section.py (openDetailPanel now checks renderReleaseAddendumsSection)

Old tests still passing: test_dashboard_release_picks_section.py (38), test_add_release_picks_modal.py, test_dashboard_release_pick_states.py
---
author: oompah
created: 2026-07-13 05:07
---
Completion: Delivered task release-addendum selection and status UI (OOMPAH-180).

Deliverables:
1. GET /api/v1/issues/{id}/release-addendums — reads AddendumRepository, returns {identifier, addendums}, 404/503 handling
2. CSS: .release-addendum-{list,entry,branch,status-*,pr-link,error,stale-badge} + .rab-{fieldset,legend,checkbox-row,stale-warning}
3. renderReleaseAddendumsSection(): target_branch, status badge (open/in_progress/in_review/blocked/merged/archived), PR link, blocked error; NO child-task link; 'Add release branches' button only for Merged tasks; empty-state
4. openAddReleaseBranchesDialog(): fetches /release-addendums (active targets), fetches /release-branches catalog (available=true only), fieldset+legend+checkbox group, prechecked+disabled for active entries, focus management, stale warning, empty/error states
5. closeAddReleaseBranchesDialog(): clears state
6. submitAddReleaseBranchesDialog(): validates ≥1 selection, idempotency_key=crypto.randomUUID(), POSTs ALL selected branches in ONE request (acceptance criterion satisfied), disables button during flight, closes+refreshes on success (refresh-to-open)
7. Escape-to-close keydown listener
8. add-release-branches-dialog HTML: role=dialog, aria-modal, aria-labelledby, fieldset+legend, Cancel/Queue-release-merges
9. openDetailPanel: parallel /release-addendums fetch, calls renderReleaseAddendumsSection(_raData, id, projectId, detail.state)
10. 82 new tests (67 UI + 15 server); 2 old tests updated; 7724 total pass

Acceptance: selecting two branches queues two addendums in one POST with one user action — verified in test_sends_all_branches_in_one_request (single 'await fetch(' in submit body).
---
author: oompah
created: 2026-07-13 05:07
---
Delivered task release-addendum selection and status UI. Added GET /api/v1/issues/{id}/release-addendums endpoint; replaced Release Picks section with Release addendums section (renderReleaseAddendumsSection, no child-task links, Merged-only button); added accessible Add release branches dialog (fieldset/legend/checkbox, catalog API, idempotency key, single POST for all selections, Escape-to-close, focus management, stale/empty/error states); 82 new tests, 7724 total pass.
---
author: oompah
created: 2026-07-13 05:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 119
- Tokens: 179 in / 5.4K out [5.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 30m 11s
- Log: OOMPAH-180__20260713T043716Z.jsonl
---
<!-- COMMENTS:END -->
