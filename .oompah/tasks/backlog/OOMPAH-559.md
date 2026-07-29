---
id: OOMPAH-559
type: feature
status: Backlog
priority: 0
title: Recover integration failures and clean private workspaces safely
parent: OOMPAH-555
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:27.458733Z'
updated_at: '2026-07-29T16:24:33.819710Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Route rebase conflicts to Needs Rebase and combined-tree failures to Needs CI Fix with actionable task comments and the correct private branch. Re-dispatch repair agents with dependency and coordination context. Recover integrating tasks after service restart, invalidate stale integration evidence when upstream code changes, clean private worktrees after integration, and delete remote task branches only after epic landing. Extend stale cleanup without touching active or recoverable work.

Tests must cover each recovery state, exact final human instructions when escalation is unavoidable, watchdog interaction, stale evidence, branch cleanup timing, active-work protection, and interrupted service restarts.

Acceptance criteria: failures never lose commits or silently stall, repair work resumes on the correct branch, storage is reclaimed safely, and focused tests plus make test pass.

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
