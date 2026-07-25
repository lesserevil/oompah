---
id: OOMPAH-441
type: task
status: In Progress
priority: null
title: Resolve shared epic parent lookup for review gates
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-25T01:59:58.245991Z'
updated_at: '2026-07-25T02:00:12.950101Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the shared-epic review gate when a child task references a valid parent epic but the parent lookup fails, as seen with EXOCOMP-29 and PR #10. Resolve the parent from canonical tracker state where appropriate, preserve fail-closed behavior for genuinely unreachable parents, and add regression tests. Run the relevant Makefile test target and deploy the fix.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

