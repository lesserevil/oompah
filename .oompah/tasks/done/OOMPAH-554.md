---
id: OOMPAH-554
type: feature
status: Done
priority: 0
title: Automate coordination checkpoints, conflict warnings, and observability
parent: OOMPAH-550
children: []
blocked_by:
- OOMPAH-551
- OOMPAH-552
- OOMPAH-553
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:19.226686Z'
updated_at: '2026-07-29T18:28:17.648374Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Publish automatic peer-started, changed-path, conflict-risk, submitted-result, and dependency-integrated messages. Derive changed paths from the task branch/worktree at bounded checkpoints and require an implementation summary before submission. Add unread/conflict badges and a coordination timeline to task/activity APIs and the dashboard. Alert only on actionable store or delivery failures; prune terminal-epic history after the documented retention period.

Tests must cover path-overlap transitions, message storm prevention, self-message suppression, activity/websocket updates, dashboard escaping, retention cleanup, and no alerts for normal delivery/fallback.

Acceptance criteria: likely conflicts are surfaced to both agents promptly, normal coordination is quiet, history is visible and bounded, and focused tests plus make test pass.

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
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:28
---
Implemented in PR #579 and merged to main at 31f8938b8f669a316a830690aaedcc1e0d3834bf. Full GitHub CI passed on Python 3.11, 3.12, and 3.13; the deployed server exposes the new coordination and submission surfaces.
---
<!-- COMMENTS:END -->
