---
id: OOMPAH-789
type: task
status: In Progress
priority: 1
title: Add restart and external-failure injection at every workflow boundary
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-790
- OOMPAH-783
labels:
- human-only
assignee: null
created_at: '2026-08-04T13:59:14.267846Z'
updated_at: '2026-08-04T18:00:37.379273Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Create controllable fault hooks/test adapters for process death or exception before/after job enqueue, lease, revalidation, Git/forge effect, tracker mutation, verification, transition journaling, and completion. Inject stale/missing tracker snapshots, duplicate/dropped events, fetch failure, deleted branches, target/head changes, expired leases, auth/policy changes, transport failures, and concurrent API/scheduler intents. Use real temporary SQLite, native Markdown trackers, and Git repositories. Acceptance: each boundary has a deterministic restart test; recoverable faults converge after restart; unrecoverable faults become bounded action_required without unsafe mutation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

