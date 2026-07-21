---
id: OOMPAH-336
type: bug
status: Open
priority: 1
title: Route release CI remediation to native project tasks
parent: null
children: []
blocked_by: []
labels:
- release-ci-failure
assignee: null
created_at: '2026-07-21T22:22:50.075291Z'
updated_at: '2026-07-21T22:30:25.132046Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 88284ac8-2787-49db-ba3a-5acbe2f13461
---
## Summary

Release-delivery CI failures must create actionable native tasks in the affected project, with CI-fix routing and explicit acceptance criteria. Existing remediation records that point to an unrelated external issue must be replaced by a project-local task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:26
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 22:26
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 22:27
---
Understanding: This task requires that release-delivery CI failures create actionable native tasks in the affected project (with ci-fix routing and acceptance criteria), and that stale remediation records pointing to unrelated external issues are replaced by project-local tasks. PR #485 'Route release CI remediation to project tasks' was just merged to main. I need to verify CI is green after the merge, and fix any failures if they exist.
---
<!-- COMMENTS:END -->
