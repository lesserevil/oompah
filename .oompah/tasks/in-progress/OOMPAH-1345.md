---
id: OOMPAH-1345
type: task
status: In Progress
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
updated_at: '2026-08-26T19:22:06.373003Z'
work_branch: OOMPAH-1345
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
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-1345
  base_branch: epic-OOMPAH-1342
  base_sha: d258fc16b1478ff902139c66cdb3e51fa96d209c
  head_sha: f13ca97b66bea10214dadec8464737557a4a04e8
  submitted_at: '2026-08-26T19:21:55.780979+00:00'
  updated_at: '2026-08-26T19:21:55.780979+00:00'
oompah.work_branch: OOMPAH-1345
---
## Summary

Implement workstream 3 of plans/service-throughput-recovery.md. Refactor GET /api/v1/reviews so a cache miss does not synchronously fetch all forge reviews. Maintain a bounded generation-aware snapshot using existing background/event-driven refresh paths; expose stale and per-project unavailable metadata while retaining successful sibling data. Add route, cache invalidation, webhook refresh, timeout, and partial-provider-failure tests in tests/. Acceptance: cold API requests perform no forge network calls and return promptly, while background refreshes advance exact project generations without stale resurrection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 18:56
---
Direct implementation ownership assigned to the current manual recovery session (owner claim: shedwards). The project is paused and the human-only fence is present; do not dispatch this task to an autonomous worker.
---
author: oompah
created: 2026-08-26 19:22
---
Changed reviews API to serve the scheduler review snapshot without synchronous forge fanout, with generation metadata and regression coverage. Focused API tests pass (58).
---
<!-- COMMENTS:END -->
