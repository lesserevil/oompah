---
id: OOMPAH-664
type: task
status: Backlog
priority: null
title: Make issue-list snapshots advance with canonical state-branch task changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T16:04:06.140108Z'
updated_at: '2026-07-31T18:12:53.439441Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction on 2026-07-31: the canonical native tracker contained OOMPAH-651 and OOMPAH-655 in Needs Human, and task detail plus task CLI reported those states, while GET /api/v1/issues?project_id=proj-14849f1b returned an empty Needs Human set. This caused an operator recovery pass to miss two authoritative tasks until the state-branch files were inspected directly. Prior OOMPAH-305/306 cache work did not prevent this recurrence. Implementation scope: bind every list/board snapshot to the exact project state-branch generation or commit, invalidate it synchronously after checkpoint and direct status mutations, and ensure list, detail, task CLI, websocket, and canonical Markdown agree. Never silently serve a stale empty lane as fresh; expose the existing stale indicator when a fresh authoritative read is unavailable. Relevant files include oompah/server.py issue snapshot/detail caches, state-branch checkpoint callbacks in oompah/oompah_md_tracker.py, websocket broadcasts, and state-cache regression tests. Required deterministic tests: barrier between a cached list read and Needs Human status moves from a separate tracker instance; checkpoint commit invalidation; two projects isolated; list/detail parity; restart; read failure preserves a stale-marked snapshot rather than claiming an empty current lane. Acceptance: an authoritative status move becomes visible in all read surfaces without TTL delay, OOMPAH-651/655-style tasks cannot disappear from lane queries, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

