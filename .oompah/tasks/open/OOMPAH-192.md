---
id: OOMPAH-192
type: epic
status: Open
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
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:31:12.244396Z'
updated_at: '2026-07-13T20:36:43.623430Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

