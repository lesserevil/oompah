---
id: OOMPAH-172
type: epic
status: In Review
priority: 1
title: Implement queued release-branch addendums
parent: null
children:
- OOMPAH-173
- OOMPAH-174
- OOMPAH-175
- OOMPAH-176
- OOMPAH-177
- OOMPAH-178
- OOMPAH-179
- OOMPAH-180
- OOMPAH-181
- OOMPAH-182
- OOMPAH-183
- OOMPAH-184
- OOMPAH-185
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:35:12.892610Z'
updated_at: '2026-07-13T06:55:58.315437Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement plans/release-branch-addendums.md. Replace new release-pick child tasks with durable, queueable release addendums attached to the original merged task or epic. Supported release lines are configured per project; approval of any task or epic merged to main immediately queues one addendum per selected supported release branch. Preserve an auditable task/branch view, migrate existing release-pick records safely, and retire the old child-backport workflow.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:38
---
Filed implementation children OOMPAH-173 through OOMPAH-184 from plans/release-branch-addendums.md, with scoped tests and acceptance criteria. OOMPAH-185 was immediately archived as a duplicate of OOMPAH-184.
---
<!-- COMMENTS:END -->
