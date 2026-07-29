---
id: OOMPAH-555
type: epic
status: Backlog
priority: 0
title: Execute epic children in parallel with ordered integration
parent: null
children:
- OOMPAH-556
- OOMPAH-557
- OOMPAH-558
- OOMPAH-559
- OOMPAH-560
blocked_by:
- OOMPAH-545
- OOMPAH-550
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:20.776850Z'
updated_at: '2026-07-29T16:24:55.207552Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Remove the one-agent-per-epic bottleneck by giving each child an isolated task branch and integrating completed work into the epic branch in dependency order.

Implementation scope

Allocate private child worktrees and branches, add a durable per-epic integration queue and lease, select submissions topologically, rebase onto the latest epic head, run the configured project quality gate, fast-forward with compare-and-swap protection, and stage terminal audit. Handle same-epic and cross-epic dependencies, conflicts, CI failures, crashes, cleanup, rollout, and a safe feature flag. Preserve the invariant that no PR/MR is created until the entire epic is ready.

Acceptance criteria

Multiple epic children run concurrently without sharing a filesystem, dependent tasks may code early but finish in order on a combined tested tree, failures recover without losing commits, one final epic PR is created only after all children finish, and focused tests plus make test and a live pilot pass.

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
