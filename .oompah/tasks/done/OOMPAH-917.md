---
id: OOMPAH-917
type: bug
status: Done
priority: 1
title: Make native validation lease teardown assertion race-free
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T15:12:45.375040Z'
updated_at: '2026-08-08T16:27:21.444254Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d2d4f0e2d610
    project_id: proj-14849f1b
    task_id: OOMPAH-917
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9538697418e8e379ad0686b0af6dc291f24d0cc878ee8beca11b9821a06aed13
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:27:17.505579+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

The exact systemic full gate intermittently fails tests/test_native_validation_guard.py::test_native_post_attach_cancellation_exits_without_self_stopping because the shim receives the expected cancellation result before the broker finally block releases its durable ValidationResourceLease handle. Update the regression test to wait with the existing bounded _wait_until helper for owner_count to reach zero, preserving the product contract that cleanup completes promptly without requiring impossible synchronous ordering. Run the focused serial Makefile gate and the exact full make test gate. Acceptance: the test fails if cleanup never completes, passes regardless of the valid callback/finally scheduling order, and the exact full gate is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 15:14
---
Direct owner implementation is complete on the systemic composition head: the regression now uses the existing bounded wait helper for asynchronous lease release. Focused serial reproduction passes. This task remains Backlog/unclaimed only because the currently deployed expired-transition recovery bug blocks promotion; it will be promoted and direct-claimed immediately after the repaired head is deployed.
---
<!-- COMMENTS:END -->
