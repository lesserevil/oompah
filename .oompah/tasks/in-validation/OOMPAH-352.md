---
id: OOMPAH-352
type: task
status: In Validation
priority: 2
title: Add stall diagnostics and wedge recovery telemetry
parent: OOMPAH-348
children: []
blocked_by:
- OOMPAH-349
- OOMPAH-350
- OOMPAH-351
labels: []
assignee: null
created_at: '2026-07-22T00:56:40.490026Z'
updated_at: '2026-08-02T01:23:54.783827Z'
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
    audit_id: audit-2cb86c46bcdd
    project_id: proj-14849f1b
    task_id: OOMPAH-352
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 23c0de360f05807fc40ed3e25c3c2f76395ee4f97d6ca0047f87f5fc67e9339a
    attempts:
    - version: 1
      attempt_id: attempt-2aa8a1ee9440
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 23c0de360f05807fc40ed3e25c3c2f76395ee4f97d6ca0047f87f5fc67e9339a
      created_at: '2026-08-02T01:23:47.956854+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:23:47.956854+00:00'
      branch_key: OOMPAH-352
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:39.526691+00:00'
    updated_at: '2026-08-02T01:23:47.956854+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-2aa8a1ee9440
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 23c0de360f05807fc40ed3e25c3c2f76395ee4f97d6ca0047f87f5fc67e9339a
    created_at: '2026-08-02T01:23:47.956854+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:23:47.956854+00:00'
    branch_key: OOMPAH-352
---
## Summary

Implement operator-visible diagnostics for scheduler and HTTP stalls. Capture tick phase, active operation, executor queue depth, and Python thread stacks when a tick exceeds a configurable threshold. Expose recent stall events in GET /api/v1/state and write a bounded diagnostic artifact under ~/.oompah. Avoid secrets and prompt contents.

Tests: trigger a controlled slow operation; assert one bounded diagnostic artifact and sanitized state telemetry are produced, repeated alerts are rate-limited, and normal ticks do not emit artifacts.

Acceptance: an operator can identify the blocking phase and thread stack from the running service after a stall; diagnostics do not themselves block the API; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:07
---
Implemented first-occurrence stale-loop diagnostics: an independently running supervisor captures all thread stacks when the dispatch loop first becomes stale. Regression coverage added; full suite is running.
---
author: oompah
created: 2026-07-22 01:16
---
Added first-stall all-thread diagnostics and regression coverage.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: stall diagnostics and recovery telemetry is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
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
created: 2026-08-02 01:23
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
<!-- COMMENTS:END -->
