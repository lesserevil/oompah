---
id: OOMPAH-983
type: task
status: Ready to Integrate
priority: null
title: Make reserved workflow control-capacity proof deterministic on Python 3.13
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T03:38:07.660153Z'
updated_at: '2026-08-10T03:59:09.850546Z'
work_branch: OOMPAH-983
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
  task_branch: OOMPAH-983
  head_sha: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
  submitted_at: '2026-08-10T03:47:07.254880+00:00'
  updated_at: '2026-08-10T03:47:07.254880+00:00'
oompah.work_branch: OOMPAH-983
---
## Summary

Triggered by OOMPAH-982 protected PR #790, GitHub Actions run 31352693288. Python 3.11 and 3.12 passed all 19,297 tests, while Python 3.13 timed out in tests/test_workflow_runtime.py::test_long_delivery_cannot_block_control_jobs_or_projection_generations waiting for validation_submission after the long standalone delivery and authority_revocation. This is an unrelated loaded-scheduler test race: the proof relies on real worker scheduling reaching an event inside a fixed timeout rather than a deterministic admission/completion barrier. Scope: make the regression deterministically synchronize exact shared-lane delivery, reserved control-slot authority_revocation, subsequent validation_submission admission, and projection-generation advancement; preserve production max_concurrent/control_reserved_slots behavior and do not merely widen sleeps/timeouts. Relevant files: tests/test_workflow_runtime.py and only narrow WorkflowRuntime/DurableWorkflowWorker seams if a reproducer proves production changes necessary. Required tests: reproduce under Python 3.13/two xdist workers or repeated focused load; the test fails if reserved control work cannot progress, proves delivery remains leased, both control effects finish in order, projections advance, and no effect duplicates; run the workflow-runtime suite and Ruff/diff checks. Acceptance: repeated focused runs are deterministic and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 03:39
---
Claimed directly from PR #790 run 31352693288. Python 3.11/3.12 and the exact local branch gate passed; Python 3.13 alone exposed a loaded-scheduler test race. The failed CI job is rerunning while deterministic event/state synchronization is implemented on branch OOMPAH-983.
---
author: oompah
created: 2026-08-10 03:47
---
Replaced the race-prone handler-apply wait with an exact post-retained-lane completion barrier keyed to the authority-revocation job. Production capacity behavior is unchanged and no timeout was widened. Validation: Python 3.13 focused 40/40, Python 3.12 focused 20/20, Python 3.13 workflow-runtime 118 passed; independent review approved.
---
author: oompah
created: 2026-08-10 03:59
---
Branch quality gate passed for `2a10a77a32b2b38e11b78b3137e13d289dc866d9` using `make test` in 169.5s. Review creation may proceed.
---
<!-- COMMENTS:END -->
