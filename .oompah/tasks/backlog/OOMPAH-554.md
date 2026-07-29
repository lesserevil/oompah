---
id: OOMPAH-554
type: feature
status: Backlog
priority: 1
title: Automate coordination checkpoints, conflict warnings, and observability
parent: OOMPAH-550
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T16:23:19.226686Z'
updated_at: '2026-07-29T16:23:19.226686Z'
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

