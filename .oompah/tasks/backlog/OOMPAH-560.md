---
id: OOMPAH-560
type: task
status: Backlog
priority: 0
title: Expose, document, and pilot parallel epic integration
parent: OOMPAH-555
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:29.405626Z'
updated_at: '2026-07-29T16:24:39.323994Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add integration queue and peer activity to state/task/activity APIs and the dashboard. Document configuration, submission, dependency semantics, recovery, rollback, and operator verification. Add OOMPAH_PARALLEL_EPIC_CHILDREN_ENABLED in .env/.env.example with a drain-first activation check. Build end-to-end tests for two parallel siblings, out-of-order dependent submission, overlap communication, ordered integration, terminal audit, and a single epic PR. Pilot on one owned epic before enabling globally.

Acceptance criteria: operators can see why every Ready task is waiting, rollout and rollback are documented and safe, the full end-to-end scenario passes, make test passes, and live production verification confirms parallel child agents without shared-worktree races.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:24
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
<!-- COMMENTS:END -->
