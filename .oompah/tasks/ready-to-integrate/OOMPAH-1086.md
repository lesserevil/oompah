---
id: OOMPAH-1086
type: task
status: Ready to Integrate
priority: null
title: Make transition-journal teardown deterministic after concurrent API use
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T12:54:01.877028Z'
updated_at: '2026-08-11T13:57:13.564102Z'
work_branch: OOMPAH-1086
target_branch: null
review_url: null
review_number: null
review_head: null
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
<!-- COMMENTS:END -->
