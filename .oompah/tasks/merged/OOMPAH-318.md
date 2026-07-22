---
id: OOMPAH-318
type: epic
status: Merged
priority: 1
title: Add full GitLab forge parity for managed projects
parent: null
children:
- OOMPAH-319
- OOMPAH-320
- OOMPAH-321
- OOMPAH-322
- OOMPAH-323
- OOMPAH-324
- OOMPAH-325
- OOMPAH-326
- OOMPAH-327
- OOMPAH-328
- OOMPAH-329
- OOMPAH-353
- OOMPAH-405
blocked_by: []
labels:
- needs:backend
- needs:frontend
- needs:docs
- epic:rebasing
assignee: null
created_at: '2026-07-21T20:33:00.759935Z'
updated_at: '2026-07-22T21:27:57.472889Z'
work_branch: epic-OOMPAH-318
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/533
review_number: '533'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/533
oompah.review_number: '533'
oompah.work_branch: epic-OOMPAH-318
oompah.target_branch: main
---
## Summary

Implement the decision-complete design in plans/gitlab-forge-parity.md.

Goal: GitLab.com and GitLab 17.0+ self-managed projects have parity with GitHub for project setup, GitLab Issues and native intake, Merge Requests, pipelines, webhook-driven updates with polling fallback, release delivery, YOLO, UI/API/ACP tools, bootstrap, documentation, and tests. GitLab Issue Boards and merge trains are explicitly out of scope.

Execution rules:
- Complete children in dependency order.
- Each child must include regression tests and run make test before review.
- Preserve GitHub project behavior and persisted configuration compatibility.
- Use plans/gitlab-forge-parity.md as the authoritative design document.

Done when all child acceptance criteria are met and the cross-forge end-to-end suite passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 08:19
---
YOLO: merged PR #533.
---
<!-- COMMENTS:END -->
