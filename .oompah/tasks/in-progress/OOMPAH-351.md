---
id: OOMPAH-351
type: bug
status: In Progress
priority: 1
title: Bound worker termination and service shutdown
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:37.758720Z'
updated_at: '2026-07-22T01:12:50.097556Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: orchestrator.stop cancels each worker and awaits it without a timeout. A cancellation-resistant ACP/CLI worker can make make stop and make restart hang indefinitely.

Implement: add configurable bounded termination phases: cancel worker, wait briefly, terminate managed subprocess/session, wait briefly, then record a forced-termination handoff and continue shutdown. Shutdown must continue across all workers even if one fails. Ensure checkpoint queues and webhook forwarders are stopped in a bounded manner.

Tests: fake worker that ignores cancellation; assert stop returns within configured bound, remaining workers are processed, and forced termination is logged/observable. Test normal graceful worker completion remains unchanged.

Acceptance: make restart cannot be held indefinitely by an agent worker; no orphaned managed subprocess remains after forced termination; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:07
---
Implemented bounded worker termination with OOMPAH_WORKER_TERMINATION_TIMEOUT_MS (default 10 seconds), documented in .env.example, plus regression coverage. Full suite is running.
---
<!-- COMMENTS:END -->
