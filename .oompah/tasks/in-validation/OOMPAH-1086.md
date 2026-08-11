---
id: OOMPAH-1086
type: task
status: In Validation
priority: null
title: Make transition-journal teardown deterministic after concurrent API use
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T12:54:01.877028Z'
updated_at: '2026-08-11T14:45:07.650111Z'
work_branch: OOMPAH-1086
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/823
review_number: '823'
review_head: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 7470f266-982d-42ab-830d-00e3b43b90d1
  request_fingerprint: 935f01c6fb5e78687100a3c8eefdc8a1b01e4dd8c5fd44805ff631612bc2b475
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1086
  head_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
  submitted_at: '2026-08-11T13:50:53.226522+00:00'
  updated_at: '2026-08-11T13:50:53.226522+00:00'
oompah.work_branch: OOMPAH-1086
oompah.review_url: https://github.com/lesserevil/oompah/pull/823
oompah.review_number: '823'
oompah.target_branch: main
oompah.review_head: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-38105e77a9ca
    project_id: proj-14849f1b
    task_id: OOMPAH-1086
    digest: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
  - version: 1
    audit_id: audit-90733bffbafa
    project_id: proj-14849f1b
    task_id: OOMPAH-1086
    digest: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1086","audit-38105e77a9ca","attempt-eccc2ca5124c"]': '2026-08-11T14:44:57.087523+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1086
    target_state: Done
    evidence_fingerprint: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
    workflow_revision: null
    selected_ref: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    selected_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    landing_revision: null
    audit_ids:
    - audit-38105e77a9ca
    kind: result
    applied: true
    retired_at: '2026-08-11T14:44:57.087539+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1086
    audit_id: audit-38105e77a9ca
    attempt_id: attempt-eccc2ca5124c
    target_state: Done
    evidence_fingerprint: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
    status: In Validation
    audit_ids:
    - audit-38105e77a9ca
    kind: result
    applied: true
    created_at: '2026-08-11T14:44:57.087549+00:00'
    applied_at: '2026-08-11T14:45:05.887690+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-38105e77a9ca
    project_id: proj-14849f1b
    task_id: OOMPAH-1086
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
    attempts:
    - version: 1
      attempt_id: attempt-eccc2ca5124c
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
      created_at: '2026-08-11T14:39:55.694358+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T14:39:55.694358+00:00'
      branch_key: OOMPAH-1086
      selected_ref: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
      selected_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
      verdict: pass
      completed_at: '2026-08-11T14:44:57.087336+00:00'
      ended_at: '2026-08-11T14:44:57.087336+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-11T14:38:26.100049+00:00'
    eligible_at: '2026-08-11T14:38:26.100049+00:00'
    selected_ref: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    selected_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    updated_at: '2026-08-11T14:44:57.087336+00:00'
  - version: 1
    audit_id: audit-90733bffbafa
    project_id: proj-14849f1b
    task_id: OOMPAH-1086
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-11T14:38:26.100049+00:00'
    prerequisite_audit_id: audit-38105e77a9ca
    selected_ref: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    selected_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    updated_at: '2026-08-11T14:44:57.087336+00:00'
    eligible_at: '2026-08-11T14:44:57.087336+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-eccc2ca5124c
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 588a16591a0399be10c987aa0f882b7068dba2fce6b8a5d7a87e034d93924fa8
    created_at: '2026-08-11T14:39:55.694358+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T14:39:55.694358+00:00'
    branch_key: OOMPAH-1086
    selected_ref: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
    selected_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
---
## Summary

Protected Python 3.12 CI for PR 820 / exact OOMPAH-1083 head be48003555fed724a752512d73fd70d5c72b2795 passed all 19,945 test bodies but failed in autouse teardown after 1,349 seconds. tests/conftest.py ResourceRegistry.close_all timed out at the global 5-second limit inside TransitionJournal.close -> sqlite3.Connection.close for the orchestrator created by tests/test_events.py::TestOrchestratorEventBus::test_notify_state_only_emits_state_updated; api, api-control, and api-task-create executor threads were still alive but idle. The exact Python 3.12 focused test then passed 10/10 in fresh xdist runs, proving a load/order-sensitive lifecycle race rather than a deterministic assertion failure. Investigate and repair the actual ownership boundary so all users of an orchestrator-owned TransitionJournal are quiesced before connection close and close cannot hang behind uncaptured API/default executors or an abandoned SQLite operation. Do not merely increase the global timeout, suppress teardown failure, or blindly retry CI. Add a deterministic barrier regression that holds the relevant concurrent journal/API lifecycle edge, initiates cleanup, and proves orderly bounded retirement/close without use-after-close, leaked threads, lost transition effects, or double close. Cover production graceful shutdown and the shared test resource registry if both use the defective boundary. Relevant files include oompah/task_transition_service.py, oompah/orchestrator.py, server API executor ownership, tests/conftest.py, and tests/test_events.py. Run focused transition/lifecycle/event tests under Python 3.12, repeated parallel cleanup stress, adjacent shutdown tests, terminal mutation scan, and the full gate. Acceptance: transition-journal close is deterministic under concurrent API load, teardown leaves no owning executor threads, and protected 3.11/3.12/3.13 CI passes at the exact review head.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 13:02
---
Deterministic reproduction confirmed a real ownership race independent of CI slowdown: TaskTransitionService.execute can durably begin, block on tracker I/O between journal calls, and concurrent TransitionJournal.close() closes the connection; when the admitted transition resumes its next append raises sqlite3.ProgrammingError ('Cannot operate on a closed database'). Fixing the journal/service admission boundary so close rejects new transition sagas and drains already-admitted sagas before SQLite close; regression will prove effect completion, durable final event, idempotent close, and rejection after retirement.
---
author: oompah
created: 2026-08-11 13:38
---
Diagnosis and scope update: the original PR 820 Python 3.12 teardown timeout cannot be causally attributed to a transition-journal ownership race. That run was uniformly slow (1349s vs ~435s baseline), timed out inside sqlite3.Connection.close after orchestrator pools were drained, and its exact failed job rerun passed; the journal RLock also prevents an in-flight SQLite call from executing concurrently inside close. Diagnosis did expose a separate deterministic lifecycle defect: closing while execute() was between its durable begin and outcome append (blocked in tracker I/O) made the later append fail with 'Cannot operate on a closed database.' Direct production readers also bypass TaskTransitionService. The narrow fix now gives each complete execute/recover saga one lifetime lease, gives every public journal reader/writer an operation lease, fences late callers once close starts, and drains already-admitted work before one idempotent close. No timeout was raised. Evidence on rebased fe06a0ff: new saga/direct-use/orchestrator-close regressions 10/10 fresh-process runs (30 executions); full transition-service file 112 passed; focused production direct-reader paths 5 passed; terminal mutation scan 21/21. Final complete gate is intentionally waiting for the sibling definitive gate to release host capacity.
---
author: oompah
created: 2026-08-11 13:50
---
Implementation pushed at exact head 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f. Final boundary covers complete ordinary/authorized transition sagas plus every direct public journal reader/writer; ContextVar leases propagate safely into asyncio.to_thread and are checked against live saga ownership so cancellation cannot revive a stale lease. Close is idempotent, fences late work, drains admitted work, and cannot split the durable saga. No global timeout changed. Green evidence: transition service 112 passed; shared registry/production drain/historical events 9 passed; exact production direct-reader tests 5 passed; three race regressions passed across 10 fresh processes (30 executions); adjacent transition/restart/event surface previously 264 passed after rebase; mutation scan 21/21; secret/commit hooks passed. Definitive local make test was operator-stopped at 22% to yield to the server's authoritative validation lease, after 4,505 passed and 0 failed. Original CI close timeout remains diagnosed as uniform 3.12 runner slowdown, not claimed as caused by the independently reproduced ownership defect.
---
author: oompah
created: 2026-08-11 13:51
---
Fenced transition-journal retirement across complete transition sagas and every public journal operation; added deterministic direct-use, saga-gap, and production graceful-drain regressions. Pushed exact head 6dedb86fa; focused/stress checks green, and local full gate yielded at 4,505 passed/0 failed to the server's authoritative validation lease.
---
author: oompah
created: 2026-08-11 13:57
---
Branch quality gate passed for `6dedb86fa1b6e4b310482bd5c5c1d2931c82981f` using `make test` in 186.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 14:01
---
Fresh independent exact-head review ACCEPTED 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f. Reviewer verified lifecycle fencing and active-use accounting, live saga lease propagation through asyncio.to_thread, stale ContextVar rejection, close fence/drain/idempotency without holding the SQLite lock, admission of every public reader/writer, complete ordinary and authorized saga coverage across tracker-I/O gaps, cancellation safety, production pool retirement, and the narrowed causal claim. Evidence: 185 focused/adjacent transition/restart/event tests, ad-hoc exact stale-context concurrent-close probe, terminal mutation scan 21/21, paranoid secret scan, clean exact pushed branch and canonical trailer. Protected CI on PR #823 remains the next boundary.
---
author: oompah
created: 2026-08-11 14:38
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 14:40
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 14:40
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 14:45
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- authoritative_gate: make test PASSED 186.32s
- commit_sha: 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f
- implementation_files[0]: oompah/task_transition_service.py (+180 lines lifecycle management)
- implementation_files[1]: tests/test_task_transition_service.py (+138 lines regression tests)
- implementation_files[2]: tests/test_restart_api.py (+97 lines production drain test)
- regression_tests[0]: test_journal_close_drains_admitted_transition_saga (line 135)
- regression_tests[1]: test_journal_close_drains_direct_use_and_fences_late_callers (line 214)
- regression_tests[2]: test_background_drain_waits_for_admitted_transition_saga (line 920)
- key_mechanisms[0]: _lifecycle_condition: Condition variable for synchronization
- key_mechanisms[1]: _active_uses: Counter tracking all active journal operations
- key_mechanisms[2]: _active_transition_leases: Set of saga lease objects
- key_mechanisms[3]: _closing: Flag fences new operations
- key_mechanisms[4]: _closed: Flag ensures idempotent close
- key_mechanisms[5]: ContextVar: Propagates lease to asyncio.to_thread contexts
- review_evidence: Fresh independent review ACCEPTED. Reviewer verified lifecycle fencing, active-use accounting, saga lease propagation, stale ContextVar rejection, close fence/drain/idempotency, comprehensive saga/direct-reader coverage, and cancellation safety.
- mutation_scan: 21/21 passed
---
<!-- COMMENTS:END -->
