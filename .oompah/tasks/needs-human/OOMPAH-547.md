---
id: OOMPAH-547
type: feature
status: Needs Human
priority: 0
title: Split finish-order dependencies from hard-start dependencies
parent: OOMPAH-545
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:09.212852Z'
updated_at: '2026-07-29T18:15:43.782428Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Reinterpret Issue.blocked_by and existing dependency APIs as finish-order constraints. Add start_blocked_by metadata plus supported CLI/API add/remove operations for hard-start dependencies. Normal finish dependencies must not reject implementation dispatch; hard-start edges must reject until satisfied. Inherit both relationship types from parent epics at the appropriate dispatch or integration boundary. Validate new edges against cycles across the combined graph and return an actionable edge path.

Tests must cover ordinary dispatch, inherited epic edges, P0 behavior, duplicate preflight, cycle creation/rejection, exact idempotent removal, native/GitHub/GitLab persistence, and API/CLI errors.

Acceptance criteria: finish edges allow early work, hard-start edges preserve true prerequisites, cycles cannot be introduced, existing dependency data remains readable, and focused tests plus make test pass.

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
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:15
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Backlog with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
<!-- COMMENTS:END -->
