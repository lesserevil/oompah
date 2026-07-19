---
id: OOMPAH-242
type: task
status: In Progress
priority: null
title: Require actionable descriptions for every auto-decomposed task
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-19T03:07:58.167396Z'
updated_at: '2026-07-19T03:10:25.820705Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0021db98-6bfc-4f37-89a3-2b8431725ee5
---
## Summary

Prevent auto-decomposition from creating title-only tasks that the dispatcher correctly refuses to run.

Scope:
- Validate every decomposition-planner child has a non-empty title and a substantive description before creating any child.
- Reject the entire decomposition plan if any child is invalid, leave the parent undecomposed, and retain the normal retry path.
- Add an explicit AGENTS.md rule requiring descriptions with scope, test requirements, and acceptance criteria for every task created by humans or agents.

Tests:
- Cover a valid plan, a blank description, whitespace-only description, and an invalid mixed plan; assert no child is created for invalid plans.

Acceptance criteria:
- Auto-decomposition never creates an Open task without a description.
- Project instructions clearly require actionable descriptions for all new tasks.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

