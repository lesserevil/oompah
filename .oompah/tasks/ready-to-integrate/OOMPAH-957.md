---
id: OOMPAH-957
type: bug
status: Ready to Integrate
priority: 1
title: Stabilize concurrent validation and review-capacity CI regressions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T12:10:50.093058Z'
updated_at: '2026-08-09T12:47:32.374754Z'
work_branch: OOMPAH-957
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-957
  head_sha: 7d0807c2005cf299bc2a90a97909600d65171573
  submitted_at: '2026-08-09T12:14:54.798015+00:00'
  updated_at: '2026-08-09T12:14:54.798015+00:00'
oompah.work_branch: OOMPAH-957
---
## Summary

Triggered by: OOMPAH-947

Hosted CI run 31312000132 for OOMPAH-947 failed only Python 3.11 in two concurrency regressions while 3.12/3.13 passed. Evidence: tests/test_review_capacity.py::test_schema_one_concurrent_process_initialization_is_serialized calls Barrier.wait(timeout=15) but the suite default pytest timeout is 5 seconds, so it times out before its stated rendezvous bound under loaded hosted runners. tests/test_native_validation_guard.py::test_parallel_native_command_boundaries_are_consumed_independently uses two concurrent guarded Bash subprocesses but caps the first communicate at 5 seconds; on the loaded full suite that cap expired without an assertion failure. Scope: make both tests deterministically compatible with the suite timeout policy, retaining a bounded failure mode and preserving the real invariants: two spawned schema migrators contend and complete with schema v2, and two distinct light command groups both yield independently consumable boundaries. Do not weaken production review-capacity migration or native guard security. Relevant files: tests/test_review_capacity.py, tests/test_native_validation_guard.py, and only production code if a deterministic reproducer proves a behavior defect. Required tests: focused repeat runs plus the hosted Python 3.11/3.12/3.13 suite; demonstrate failure remains bounded and genuine migration/boundary regressions still fail. Acceptance: a normal loaded hosted runner no longer flakes from incompatible five-second nested timeouts, while real deadlock/missing-boundary defects remain detected.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 12:14
---
Investigated CI run 31312000132: the Python 3.11 schema failure was the suite's 5-second default interrupting a test whose intentional Barrier rendezvous allows 15 seconds; the remaining native failure was the test's independent hard-coded 5-second subprocess cap. Implemented test-stability repair at 7d0807c2005cf299bc2a90a97909600d65171573: explicit 30-second test budget for the schema race and a shared 12-second bounded deadline for both concurrent guarded processes. Focused pair passed; 12 repeat runs passed; ruff and diff checks clean. No production behavior or server restart.
---
author: oompah
created: 2026-08-09 12:15
---
Pushed 7d0807c2005cf299bc2a90a97909600d65171573; focused concurrency tests and repeated runs pass.
---
author: oompah
created: 2026-08-09 12:47
---
Diagnosed the full-gate failure in test_cancelled_aged_waiter_does_not_transfer_protection as a real-clock fixture race, not a production lease-selection defect: the prior 10ms aging band lets an ordinary >210ms host scheduling delay legitimately make the nominally fresh worker starvation-protected. Reproduced that policy outcome deterministically. Updated the test at pushed head 1159766a5e93291320f6d4b91df85a1c102dd48c to use a 1s aging band, age the cancelled waiter beyond the exact 21s protection boundary, and explicitly model 250ms of replacement-worker latency below its first boost. Verification: focused aging/cancellation corpus 4 passed; 20 repeated exact-test runs passed; both original OOMPAH-957 concurrency regressions passed; secret scan and diff check passed. No production code changed and no full gate was started.
---
<!-- COMMENTS:END -->
