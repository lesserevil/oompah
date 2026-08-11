---
id: OOMPAH-1086
type: task
status: Backlog
priority: null
title: Make transition-journal teardown deterministic after concurrent API use
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T12:54:01.877028Z'
updated_at: '2026-08-11T12:54:01.877028Z'
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
  creation_marker: 7470f266-982d-42ab-830d-00e3b43b90d1
  request_fingerprint: 935f01c6fb5e78687100a3c8eefdc8a1b01e4dd8c5fd44805ff631612bc2b475
---
## Summary

Protected Python 3.12 CI for PR 820 / exact OOMPAH-1083 head be48003555fed724a752512d73fd70d5c72b2795 passed all 19,945 test bodies but failed in autouse teardown after 1,349 seconds. tests/conftest.py ResourceRegistry.close_all timed out at the global 5-second limit inside TransitionJournal.close -> sqlite3.Connection.close for the orchestrator created by tests/test_events.py::TestOrchestratorEventBus::test_notify_state_only_emits_state_updated; api, api-control, and api-task-create executor threads were still alive but idle. The exact Python 3.12 focused test then passed 10/10 in fresh xdist runs, proving a load/order-sensitive lifecycle race rather than a deterministic assertion failure. Investigate and repair the actual ownership boundary so all users of an orchestrator-owned TransitionJournal are quiesced before connection close and close cannot hang behind uncaptured API/default executors or an abandoned SQLite operation. Do not merely increase the global timeout, suppress teardown failure, or blindly retry CI. Add a deterministic barrier regression that holds the relevant concurrent journal/API lifecycle edge, initiates cleanup, and proves orderly bounded retirement/close without use-after-close, leaked threads, lost transition effects, or double close. Cover production graceful shutdown and the shared test resource registry if both use the defective boundary. Relevant files include oompah/task_transition_service.py, oompah/orchestrator.py, server API executor ownership, tests/conftest.py, and tests/test_events.py. Run focused transition/lifecycle/event tests under Python 3.12, repeated parallel cleanup stress, adjacent shutdown tests, terminal mutation scan, and the full gate. Acceptance: transition-journal close is deterministic under concurrent API load, teardown leaves no owning executor threads, and protected 3.11/3.12/3.13 CI passes at the exact review head.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

