---
id: OOMPAH-351
type: bug
status: In Validation
priority: 1
title: Bound worker termination and service shutdown
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:37.758720Z'
updated_at: '2026-08-02T01:29:36.418343Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5a7928ab9055
    project_id: proj-14849f1b
    task_id: OOMPAH-351
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
    attempts:
    - version: 1
      attempt_id: attempt-1ad979eb0003
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
      created_at: '2026-08-02T01:29:20.955728+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:29:20.955728+00:00'
      branch_key: OOMPAH-351
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:34.304931+00:00'
    updated_at: '2026-08-02T01:29:20.955728+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1ad979eb0003
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
    created_at: '2026-08-02T01:29:20.955728+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:29:20.955728+00:00'
    branch_key: OOMPAH-351
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
author: oompah
created: 2026-07-22 01:16
---
Bounded cancelled-worker waits with a documented configurable timeout and regression test.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: bounded worker termination and shutdown is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 6dd2cdfcf and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:29
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
