---
id: OOMPAH-208
type: bug
status: In Progress
priority: 2
title: Exclude already-landed commits from release delivery targets
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T16:17:14.607504Z'
updated_at: '2026-07-15T16:17:27.711809Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d77f5560-51ad-440e-b590-8c7a741b31f1
---
## Summary

Triggered by: OOMPAH-199

Release Delivery must never queue a commit to a target release branch that already contains it. Filter target choices in the popup using each selected commit's inventory release_status, and enforce the same Git-ancestry check server-side immediately before ledger writes so stale or crafted requests cannot create duplicate deliveries. For mixed selections, queue only the undelivered commit-target pairs while reporting already-delivered pairs. Add UI and API regression tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

