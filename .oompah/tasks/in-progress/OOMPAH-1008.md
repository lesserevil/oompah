---
id: OOMPAH-1008
type: bug
status: In Progress
priority: 2
title: Make late-effect quarantine deterministic under full-suite load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T01:18:23.370723Z'
updated_at: '2026-08-11T03:05:30.450400Z'
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
  creation_marker: o1007-full-gate-late-success-timeout-flake
  request_fingerprint: fa98def25d0cdaefcd8d17bafe1f395bfcba2ca5b37b3c365b29d4affc199d53
---
## Summary

Triggered by: OOMPAH-1007

The OOMPAH-1007 full make test gate on 2026-08-11 produced 19,729 passes and one load-sensitive failure in tests/test_workflow_worker.py::test_late_success_checkpoints_receipt_without_duplicate_apply. With operation_timeout_seconds=0.01, the effect timed out as intended but the subsequent quarantine authority operation also observed TimeoutError, so DurableWorkflowWorker returned LEASE_LOST instead of ACTION_REQUIRED. The exact test then passed 20/20 in isolated repetitions, indicating scheduler/load coupling rather than an OOMPAH-1007 functional regression. Scope: inspect oompah/workflow_worker.py late-effect timeout/quarantine sequencing and the WorkflowJobStore quarantine boundary; give quarantine persistence its own deterministic bounded deadline or otherwise separate effect-timeout exhaustion from internal quarantine bookkeeping without weakening lease fencing. Add a reproducer that deterministically delays the relevant authority operation (not a sleep-only probabilistic test), prove the late external receipt still checkpoints without duplicate apply, and prove a true lease loss remains LEASE_LOST. Run focused workflow-worker/job tests and make test. Acceptance: the test has no dependence on a 10ms wall-clock scheduling window under parallel full-suite load, while late effects remain fenced and restart safe.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 02:20
---
Claimed for direct-owner implementation in the current systemic workflow recovery program. The repair will isolate quarantine bookkeeping from the effect timeout without weakening lease fencing, add deterministic regression coverage, pass focused and complete gates, and use protected delivery.
---
author: oompah
created: 2026-08-11 02:29
---
Implementation is committed and pushed at exact head 2401de12283a0810f5c27bacdb65b1666deea859. Quarantine persistence now has an independent environment-configured bounded deadline instead of inheriting a short adapter operation timeout; deterministic barrier coverage holds the store operation beyond the original 10ms budget while proving exact receipt checkpointing and no duplicate apply, and a separate regression preserves true lease-loss classification. Focused suites passed 213/213 serial and 213/213 xdist; the late-effect regression passed 20/20 repetitions; mutation scan 21/21, secret hooks, compile, and diff checks are green. Independent exact-head review is pending before protected integration.
---
author: oompah
created: 2026-08-11 03:05
---
Independent review accepted the implementation. The review follow-up is committed and pushed at exact head 6590e3558; configuration and worker construction now reject NaN and positive/negative infinity so no non-finite persistence deadline can bypass the bounded quarantine contract. Focused config/worker validation passed 218 tests, and the combined four-fix branch passed 827 changed-path tests.
---
<!-- COMMENTS:END -->
