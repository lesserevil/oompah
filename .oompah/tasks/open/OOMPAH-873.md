---
id: OOMPAH-873
type: bug
status: Open
priority: 1
title: Make issue-list and full-sync snapshots match fresh state-branch detail reads
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:50:20.335247Z'
updated_at: '2026-08-07T05:50:26.221461Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-768

Live regression after OOMPAH-664 and OOMPAH-691 through OOMPAH-695: the canonical state-branch file for OOMPAH-768 is .oompah/tasks/in-progress/OOMPAH-768.md with status In Progress and updated_at 2026-08-07T04:20:57Z, and GET issue detail returns In Progress with tracker_state_fresh=true, but repeated GET /api/v1/issues full snapshots publish tracker_state/state Done and place the task in the Done column. Because the authoritative full-sync payload is itself stale, WebSocket gap detection cannot converge the UI. Reproduce and repair the native tracker fetch_all_issues/snapshot cache/source-generation path so list serialization and detail reads share one exact state-branch authority generation. Relevant code: native Markdown tracker read/cache invalidation and atomic status-file moves, server _ensure_issues_snapshot_refresh/_fetch_and_serialize_issues/source generation checks, full-sync response construction. Required tests: status-file move or lifecycle write followed by fresh detail and forced issue snapshot yields identical state; paused projects still refresh API-mutated tracker state; snapshot generation never advances while serving an older task object; concurrent move/read is atomic; WebSocket full sync contains the same state as detail. Acceptance: every full issue snapshot and full-sync response for a reported source revision exactly matches direct detail reads from that revision, so sequence recovery cannot install stale task columns.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

