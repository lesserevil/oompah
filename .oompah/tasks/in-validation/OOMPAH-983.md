---
id: OOMPAH-983
type: task
status: In Validation
priority: null
title: Make reserved workflow control-capacity proof deterministic on Python 3.13
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T03:38:07.660153Z'
updated_at: '2026-08-10T04:18:14.699581Z'
work_branch: OOMPAH-983
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/791
review_number: '791'
review_head: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
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
oompah.review_url: https://github.com/lesserevil/oompah/pull/791
oompah.review_number: '791'
oompah.target_branch: main
oompah.review_head: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-5d61600eb469
    project_id: proj-14849f1b
    task_id: OOMPAH-983
    digest: 4d63c3ce2dbe33ac32df122b78d36b7bf1b705d2274474c1fe6da59f293b2aaa
  - version: 1
    audit_id: audit-6462080061c4
    project_id: proj-14849f1b
    task_id: OOMPAH-983
    digest: 4d63c3ce2dbe33ac32df122b78d36b7bf1b705d2274474c1fe6da59f293b2aaa
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5d61600eb469
    project_id: proj-14849f1b
    task_id: OOMPAH-983
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4d63c3ce2dbe33ac32df122b78d36b7bf1b705d2274474c1fe6da59f293b2aaa
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-10T04:18:07.261452+00:00'
    selected_ref: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
    selected_sha: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
  - version: 1
    audit_id: audit-6462080061c4
    project_id: proj-14849f1b
    task_id: OOMPAH-983
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4d63c3ce2dbe33ac32df122b78d36b7bf1b705d2274474c1fe6da59f293b2aaa
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-10T04:18:07.261452+00:00'
    selected_ref: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
    selected_sha: 2a10a77a32b2b38e11b78b3137e13d289dc866d9
  attempt_history: []
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
author: oompah
created: 2026-08-10 04:18
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
