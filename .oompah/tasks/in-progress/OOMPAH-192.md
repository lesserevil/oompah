---
id: OOMPAH-192
type: epic
status: In Progress
priority: 1
title: Replace release-branch inspector with commit-centric release delivery
parent: null
children:
- OOMPAH-193
- OOMPAH-194
- OOMPAH-195
- OOMPAH-196
- OOMPAH-197
- OOMPAH-198
- OOMPAH-199
- OOMPAH-200
- OOMPAH-201
- OOMPAH-202
- OOMPAH-206
blocked_by: []
labels:
- epic:stale
- epic:rebasing
assignee: null
created_at: '2026-07-13T19:31:12.244396Z'
updated_at: '2026-07-13T23:32:15.314537Z'
work_branch: epic-OOMPAH-192
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/418
review_number: '418'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/418
oompah.review_number: '418'
oompah.work_branch: epic-OOMPAH-192
oompah.target_branch: main
---
## Summary

Implement the commit-centric release-delivery inventory defined in plans/release-delivery-commit-inventory.md. Replace the dashboard Release branches inspector with a project-scoped view of commits on the default branch and their delivery state on each configured release line. Operators must be able to queue selected source commits for selected release branches, including direct-to-main commits, without creating ordinary tracker tasks.

Scope
- Introduce a project-owned release-delivery ledger and migrate existing release addendums.
- Reuse the release queue/executor and protected-branch PR workflow.
- Deliver read inventory, queue write path, dashboard replacement, compatibility, docs, and tests.

Completion criteria
- Every child task below is Merged.
- The end-to-end acceptance criteria in plans/release-delivery-commit-inventory.md section 7 pass.
- Existing task/epic release history and release delivery remain intact through migration.

Plan
plans/release-delivery-commit-inventory.md

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

