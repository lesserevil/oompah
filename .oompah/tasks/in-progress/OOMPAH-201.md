---
id: OOMPAH-201
type: task
status: In Progress
priority: 2
title: Document and deprecate the old release-branch inspector
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-196
- OOMPAH-200
labels: []
assignee: null
created_at: '2026-07-13T19:32:59.843679Z'
updated_at: '2026-07-13T22:56:44.435108Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: eca5f4cb-68fd-495f-9400-5624c927a6bb
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 4.2, 8, and 9.

Update operator-facing documentation for the Release delivery commit inventory: configuration, how to select commits/branches, status evidence, cherry-pick SHA behavior, direct-to-main commits, protected-branch PR behavior, and stale/force-push remediation. Document task/epic detail as a shortcut. Deprecate the old branch-inspection endpoint and UI terminology according to the compatibility plan.

Acceptance criteria
- docs/release-addendums.md, docs/managed-project-onboarding.md, docs/operator-runbook.md, and docs/task-epic-workflow.md accurately describe the new screen and workflows.
- Documentation explicitly states that arbitrary release-branch commits are not treated as proof of delivery without ledger or ancestry evidence.
- The legacy branch-inspection endpoint returns a documented compatibility/deprecation response, then 410 at the specified removal point.
- No stale user-facing references remain to the removed Release branches page.

Tests
- Add endpoint tests for the compatibility response and 410 behavior.
- Run git diff --check and the relevant documentation/link checks available in the repository.

Dependencies
- OOMPAH-196 and OOMPAH-200.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 22:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 22:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 22:54
---
Understanding: OOMPAH-201 is NOT a duplicate. Searched all related tasks (OOMPAH-182 added the old branch-inspection API that this task will deprecate; OOMPAH-184 documented the old addendum workflow; OOMPAH-185 archived as duplicate of OOMPAH-184; OOMPAH-200 replaces the UI overlay). No other task covers: (1) documenting the new Release delivery commit inventory workflow in the four target doc files, or (2) making GET /release-branches/{branch}/addendums return a deprecation/410 response. Dependencies OOMPAH-196 (task/epic compat) and OOMPAH-200 (UI overlay replacement) are Done and In-Progress respectively. Proceeding with implementation of: docs updates (docs/release-addendums.md, managed-project-onboarding.md, operator-runbook.md, task-epic-workflow.md), legacy endpoint deprecation (initially compatibility response, then 410), and endpoint tests.
---
author: oompah
created: 2026-07-13 22:56
---
Discovery: Found all relevant code and docs. Key findings:\n1. dashboard.html already updated by OOMPAH-200 — 'Release delivery' button replaces old 'Release branches' button. No stale UI references remain in the template.\n2. docs/release-addendums.md: 'Inspect a release line' section still refers to old 'Release branches' view and GET /release-branches/{branch}/addendums.\n3. docs/task-epic-workflow.md L53: still says 'branch inspection' — needs update.\n4. docs/operator-runbook.md L83: says 'inspection' referring to old endpoint — needs update.\n5. docs/managed-project-onboarding.md: cross-ref to release-addendums.md is fine but the linked section needs updating.\n6. oompah/server.py L4554: GET /api/v1/projects/{project_id}/release-branches/{branch}/addendums returns full addendums — needs to return deprecation/compatibility response now, 410 at removal.\n7. No GET /release-delivery/branches/{branch} endpoint exists yet (plan says 'optional drill-down'). \nPlan: (a) Rewrite docs/release-addendums.md to document the new Release delivery commit inventory screen and deprecate old endpoint. (b) Update 3 other docs. (c) Make old endpoint return deprecation response with replacement path + add _LEGACY_BRANCH_INSPECTION_REMOVED flag for 410. (d) Add tests.
---
<!-- COMMENTS:END -->
