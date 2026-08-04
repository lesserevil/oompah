---
id: OOMPAH-782
type: feature
status: Backlog
priority: 1
title: Cut review and CI reconciliation over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:00.734500Z'
updated_at: '2026-08-04T14:06:20.999849Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Migrate In Review and repair progression to unified review/CI/Git facts and durable observation/action jobs. Normalize open, draft, merged, closed-unmerged, missing PR, deleted source, changed head, capacity, CI pending/failing/passing, conflicts, and merge target. Use LandingFact for completion and TaskTransitionService for repair/terminal transitions. Required tests: provider timeout versus empty result, branch deletion after merge, head changes after recorded merge, capacity release/restart, CI registration delay, conflict repair, GitLab/GitHub parity, and UI reason parity. Acceptance: every In Review task has one durable owner/reassessment and naturally reaches merged, repair, retry, or actionable escalation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

