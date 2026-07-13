---
id: OOMPAH-201
type: task
status: Backlog
priority: 2
title: Document and deprecate the old release-branch inspector
parent: OOMPAH-192
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:32:59.843679Z'
updated_at: '2026-07-13T19:32:59.843679Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

