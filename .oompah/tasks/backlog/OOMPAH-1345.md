---
id: OOMPAH-1345
type: task
status: Backlog
priority: 1
title: Serve reviews API from a bounded generation-aware snapshot
parent: OOMPAH-1342
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-26T18:43:16.245447Z'
updated_at: '2026-08-26T18:46:18.330652Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-reviews-api
  request_fingerprint: 5a3db0f23c9f70bbbab1f418eae47d0ecb3157c46df451e04969ebec76c5df55
---
## Summary

Implement workstream 3 of plans/service-throughput-recovery.md. Refactor GET /api/v1/reviews so a cache miss does not synchronously fetch all forge reviews. Maintain a bounded generation-aware snapshot using existing background/event-driven refresh paths; expose stale and per-project unavailable metadata while retaining successful sibling data. Add route, cache invalidation, webhook refresh, timeout, and partial-provider-failure tests in tests/. Acceptance: cold API requests perform no forge network calls and return promptly, while background refreshes advance exact project generations without stale resurrection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

