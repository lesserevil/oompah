---
id: OOMPAH-1077
type: task
status: Open
priority: null
title: Make workflow-worker heartbeat lease proof deterministic under loaded CI
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T09:45:59.661224Z'
updated_at: '2026-08-11T09:46:05.897231Z'
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
  creation_marker: ba8cb63b-b18c-47c9-a649-ff62bff38df3
  request_fingerprint: 8717186aaf2588a4b6febd726286b9fd9ad8279083d60b757222210d206c14a4
---
## Summary

Protected PR #812 Python 3.11 failed after 19,876 passing tests in tests/test_workflow_worker.py::test_heartbeat_renews_lease_during_long_effect: a real-clock 80ms lease plus 20ms heartbeat and a 150ms asyncio sleep returned LEASE_LOST under hosted load. OOMPAH-970 fixed the analogous detached WorkflowRuntime test but did not cover this lower-level worker test. A sleep-and-hope lease proof is a race-dependent test bug and cannot be handled by blind reruns. Implementation scope: replace the wall-clock timing gamble with deterministic synchronization or an injectable clock/renewal observation proving DurableWorkflowWorker renews the exact live lease while apply is blocked; preserve production lease-expiry semantics and do not merely widen delays. Relevant files: tests/test_workflow_worker.py and only the narrow oompah/workflow_worker.py seam if necessary. Required tests: repeated focused execution remains stable under scheduler delay; proof fails if renewal is absent; exact lease token, at least two renewals, single apply, and final completion remain asserted. Acceptance: focused repeated runs and the workflow-worker suite pass, the change is independently reviewed, and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

