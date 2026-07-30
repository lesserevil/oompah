---
id: OOMPAH-593
type: task
status: Backlog
priority: 1
title: Integrate and live-verify scoped Codex task CLI authentication
parent: OOMPAH-586
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:54.281403Z'
updated_at: '2026-07-30T14:17:28.285381Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-575

Implementation scope

Use the existing OOMPAH-575 branch rather than reimplementing it. Get its focused handoff-auth regression through the normal delivery path, deploy it, then run a live least-privilege probe from a service-launched Codex task: view, comment, coordinate if allowed, and submit its assigned task; verify an unrelated task and expired/missing capability fail closed. Record only safe evidence. If the live path still returns 401, fix the actual launch/environment propagation gap with tests before resubmission.

Tests

Retain OOMPAH-575 focused suites, add any live-path reproducer required, and run make test for the final head.

Acceptance criteria

OOMPAH-575 reaches Merged; a newly launched Codex worker completes the documented task CLI workflow with no operator credentials and no broader task authority.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes
