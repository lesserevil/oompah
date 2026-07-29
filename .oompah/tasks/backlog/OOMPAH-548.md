---
id: OOMPAH-548
type: feature
status: Backlog
priority: 0
title: Add worker submission handoff and ordered terminal staging
parent: OOMPAH-545
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-547
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:10.331989Z'
updated_at: '2026-07-29T16:24:41.537893Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add oompah task submit <task-id> as the worker-scoped completion operation. Validate exact task ownership, clean worktree, pushed private branch, and current remote head; record integration metadata and transition to Ready to Integrate. When parallel epic mode is enabled, convert legacy direct Done requests from child workers into submission so no terminal path bypasses integration. After successful integration, route Done through the terminal-transition coordinator and independent audit against the integrated tree.

Tests must cover CLI and task-capability authorization, clean/pushed validation, idempotent resubmission, legacy Done conversion, stale head rejection, terminal audit staging, and clear failure comments.

Acceptance criteria: workers cannot mark unintegrated child code Done, successful submission is durable and idempotent, audit evidence references the integrated commit, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
<!-- COMMENTS:END -->
