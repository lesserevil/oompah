---
id: OOMPAH-156
type: bug
status: In Progress
priority: null
title: Deduplicate auto-filed internal error tasks before creating new tasks
parent: null
children: []
blocked_by: []
labels:
- needs:backend
assignee: null
created_at: '2026-06-24T16:39:49.133027Z'
updated_at: '2026-06-24T16:40:34.366172Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5255238f-1b23-42f2-8532-9897c923e182
---
## Summary

Internal backend errors from error_watcher should only create one task per stable fingerprint while an existing non-terminal task already tracks the problem. If the same internal bug repeats, oompah should attach a comment to the existing task when possible instead of creating another task. This must survive process restarts and GitHub intake resyncs, not only the current in-memory dedup window.\n\nAcceptance criteria:\n- Before auto-filing an internal error task, error_watcher searches existing tasks for the same dedup fingerprint.\n- If a non-terminal matching task exists, no new task is created.\n- Repeated occurrences add a concise comment to the existing task when supported.\n- Different fingerprints still create separate tasks.\n- Tests cover duplicate suppression across a fresh ErrorWatcher instance.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

