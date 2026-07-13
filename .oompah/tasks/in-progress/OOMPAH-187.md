---
id: OOMPAH-187
type: task
status: In Progress
priority: 2
title: Keep Needs Human tasks visible in the in-flight dashboard filter
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T14:08:30.012087Z'
updated_at: '2026-07-13T14:08:53.847557Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The dashboard In-flight only toggle currently treats Open, In Progress, Needs CI Fix, Needs Rebase, In Review, and open-review work as in flight, but hides Needs Human tasks. Update the canonical client-side in-flight predicate (including parent/ancestor visibility calculation and toggle tooltip/copy) so Needs Human is considered in flight and remains visible when the filter is enabled. Preserve existing terminal-task hiding behavior. Tests: extend tests/test_dashboard_hide_merged.py with a direct Needs Human case, an epic/parent visibility case, and a counter/hidden-state assertion; update the dashboard tooltip test to name Needs Human. Acceptance: with In-flight only enabled, OOMPAH-44/46/48-style Needs Human cards remain visible and their parent context remains visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

