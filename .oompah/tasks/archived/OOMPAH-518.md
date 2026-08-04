---
id: OOMPAH-518
type: task
status: Archived
priority: null
title: Keep graceful restart cleanup on the owning event loop
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T17:06:49.891505Z'
updated_at: '2026-08-04T21:03:26.718549Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.work_branch: epic-OOMPAH-502
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-03b01d27c5bd: '2026-08-04T21:02:24.637331+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-518
    target_state: Archived
    evidence_fingerprint: faae74699a3dde07def4a824452d6fb5d2b2011d77a6ad90db4c04bc02d25107
    audit_ids:
    - audit-df90dfa0567d
    kind: result
    applied: true
    retired_at: '2026-08-04T21:02:24.637339+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-518
    audit_id: audit-df90dfa0567d
    attempt_id: attempt-03b01d27c5bd
    target_state: Archived
    evidence_fingerprint: faae74699a3dde07def4a824452d6fb5d2b2011d77a6ad90db4c04bc02d25107
    status: Archived
    audit_ids:
    - audit-df90dfa0567d
    applied: true
    created_at: '2026-08-04T21:02:24.637350+00:00'
    applied_at: '2026-08-04T21:02:33.898219+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-df90dfa0567d
    project_id: proj-14849f1b
    task_id: OOMPAH-518
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: faae74699a3dde07def4a824452d6fb5d2b2011d77a6ad90db4c04bc02d25107
    attempts:
    - version: 1
      attempt_id: attempt-03b01d27c5bd
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: faae74699a3dde07def4a824452d6fb5d2b2011d77a6ad90db4c04bc02d25107
      created_at: '2026-08-04T20:40:36.574070+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T20:40:36.574070+00:00'
      branch_key: epic-OOMPAH-502
      verdict: pass
      completed_at: '2026-08-04T21:02:24.637202+00:00'
      ended_at: '2026-08-04T21:02:24.637202+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:29:19.153104+00:00'
    updated_at: '2026-08-04T21:02:24.637202+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-03b01d27c5bd
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: faae74699a3dde07def4a824452d6fb5d2b2011d77a6ad90db4c04bc02d25107
    created_at: '2026-08-04T20:40:36.574070+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T20:40:36.574070+00:00'
    branch_key: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 60
  total_output_tokens: 2033
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 60
      output_tokens: 2033
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 60
    output_tokens: 2033
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:03:23.488406+00:00'
---
## Summary

Implementation scope: Fix the graceful restart shutdown path introduced under OOMPAH-507. A live auto-update on 2026-07-28 shut Uvicorn down, then Orchestrator.stop called _drain_background_work from the outer asyncio.run loop and raised RuntimeError because maintenance futures belonged to Uvicorn's closed loop. The service exited instead of reaching os.execv. Refactor shutdown so background tasks are drained or cancelled on their owning loop before it closes, or make stop safely handle already-closed foreign-loop tasks without awaiting them. Preserve agent drain semantics and ensure normal restart reaches exec even when maintenance work exists. Tests: add a regression reproducing tasks associated with a different or closed event loop, cover same-loop draining, and exercise server restart control flow through the existing Makefile and restart tests. Run focused restart and event-loop tests and the full branch gate. Acceptance criteria: no cross-loop Future exception; a normal auto-update or restart exits the server, completes cleanup, exec-restarts, and binds port 8090 with a new instance ID; active agents are still drained rather than killed; failures remain observable without preventing restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:06
---
Claimed for this session on epic-OOMPAH-502. Live reproduction is in oompah.log at 17:04:38 UTC: _drain_background_work raised 'Future attached to a different loop' after Uvicorn shutdown, preventing os.execv. I will keep this Backlog while implementing manually to avoid duplicate dispatch.
---
author: oompah
created: 2026-07-28 17:11
---
Implemented and pushed at eea181d3a. Scheduler run() now drains executor futures before its owning asyncio loop closes; shutdown defensively avoids attaching pending Futures from a closed foreign loop and still waits for executor completion. Verification: 96 focused restart/event-loop tests pass in 5.10s. Live test: forced one load restart from instance 63782c5b-ff9a-4c4a-a3fd-434d52aadcce, then make restart used request 29586011-550a-4df1-83d3-884bbad76752 and exec-restarted to instance 482ad174-b6c0-475a-851a-d2cf5e30365b on 0.0.0.0:8090 with no different-loop/Fatal error; auto concurrency remained enabled (effective 10).
---
author: oompah
created: 2026-07-28 17:12
---
Fixed cross-loop graceful restart cleanup; 96 focused tests and a live instance-changing drain restart pass.
---
author: oompah
created: 2026-07-28 18:01
---
Landed in merged epic PR #564 on main.
---
author: oompah
created: 2026-08-04 18:29
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 20:40
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 20:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 21:02
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- fix_commit: eea181d3a
- commit_stat: oompah/orchestrator.py +62 -3, tests/test_event_driven_loop.py +92 -0
- drain_function_location: oompah/orchestrator.py line 5912 _drain_background_work
- foreign_loop_guard_lines: 5933-5980 foreign_futures collection and closed-loop skip log
- regression_test_class: tests/test_event_driven_loop.py::TestDrainBackgroundWork
- regression_test_cases: test_awaits_pending_futures_on_current_loop; test_closed_foreign_loop_future_does_not_block_restart
- branch_gate_command: make test
- branch_gate_summary: 15386 passed, 7 skipped, 1 xfailed, 57 warnings in 514.60s
- landed_via: merged epic PR #564 on main (2026-07-28)
- previous_state: Merged
- days_since_merge: 7+
---
author: oompah
created: 2026-08-04 21:03
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 39
- Tokens: 60 in / 2.0K out [2.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 32s
- Log: OOMPAH-518__20260804T204112Z.jsonl
---
<!-- COMMENTS:END -->
