---
id: OOMPAH-350
type: bug
status: Archived
priority: 1
title: Isolate scheduler execution from the HTTP event loop
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:36.177730Z'
updated_at: '2026-08-02T01:37:11.845652Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-81e561cb4018: '2026-08-02T01:36:31.729819+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-350
    target_state: Archived
    evidence_fingerprint: 85ce2f6490b759c4d8346e4bef979e5e9912f363c5a714afe62efe816470cac7
    audit_ids:
    - audit-0c9f590431cd
    kind: result
    applied: true
    retired_at: '2026-08-02T01:36:31.729831+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-350
    audit_id: audit-0c9f590431cd
    attempt_id: attempt-81e561cb4018
    target_state: Archived
    evidence_fingerprint: 85ce2f6490b759c4d8346e4bef979e5e9912f363c5a714afe62efe816470cac7
    status: Archived
    audit_ids:
    - audit-0c9f590431cd
    applied: true
    created_at: '2026-08-02T01:36:31.729848+00:00'
    applied_at: '2026-08-02T01:36:36.317660+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0c9f590431cd
    project_id: proj-14849f1b
    task_id: OOMPAH-350
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 85ce2f6490b759c4d8346e4bef979e5e9912f363c5a714afe62efe816470cac7
    attempts:
    - version: 1
      attempt_id: attempt-81e561cb4018
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 85ce2f6490b759c4d8346e4bef979e5e9912f363c5a714afe62efe816470cac7
      created_at: '2026-08-02T01:29:16.549416+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:29:16.549416+00:00'
      branch_key: OOMPAH-350
      verdict: pass
      completed_at: '2026-08-02T01:36:31.729632+00:00'
      ended_at: '2026-08-02T01:36:31.729632+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:29.163087+00:00'
    updated_at: '2026-08-02T01:36:31.729632+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-81e561cb4018
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 85ce2f6490b759c4d8346e4bef979e5e9912f363c5a714afe62efe816470cac7
    created_at: '2026-08-02T01:29:16.549416+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:29:16.549416+00:00'
    branch_key: OOMPAH-350
oompah.task_costs:
  total_input_tokens: 39
  total_output_tokens: 1149
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 39
      output_tokens: 1149
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 39
    output_tokens: 1149
    cost_usd: 0.0
    recorded_at: '2026-08-02T01:37:09.881587+00:00'
---
## Summary

Problem: the default Uvicorn startup path schedules orchestrator.run and server.serve on one asyncio event loop. Any remaining synchronous scheduler or lifecycle path can stop all HTTP responses even though the port remains open.

Implement: make the default server path run the orchestrator on a dedicated thread/event loop, matching the isolation model used by the Granian lifespan. Keep one authoritative orchestrator instance, thread-safe refresh/event delivery, cached state broadcasts, webhook forwarding, workflow reload, graceful restart, and existing single-process semantics.

Tests: integration test blocks a scheduler operation and proves GET /api/v1/state remains responsive; test refresh requests cross the thread boundary; test startup/shutdown wiring does not duplicate the orchestrator.

Acceptance: a blocked scheduler tick cannot prevent state and health API responses; Uvicorn remains the supported default; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:07
---
Implemented default-Uvicorn scheduler isolation: the orchestrator now owns a dedicated event-loop thread, while HTTP/WebSockets and stale-loop supervision remain responsive on the ASGI loop. Full suite is running.
---
author: oompah
created: 2026-07-22 01:15
---
Moved the default scheduler onto a dedicated thread and retained HTTP-loop supervision.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: scheduler event-loop isolation is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 6dd2cdfcf and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:29
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:36
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 6dd2cdfcf889304fa4b84fad63fe4634bd69f6b7
- delivery_commit_subject: Harden scheduler against blocking tracker work
- delivery_commit_date: 2026-07-22 01:15:33 +0000
- delivery_on_main: true
- days_since_merge: 11
- auto_archive_threshold_days: 7
- orchestrator_thread_marker: oompah/__main__.py:485 _run_orchestrator_thread; server.py:410 mirrors for Granian
- stop_threadsafe_marker: oompah/orchestrator.py:4765 stop_threadsafe; called from __main__.py:563 and server.py:429
- tests_added_in_delivery: tests/test_dispatch_loop_heartbeat.py; tests/test_orchestrator_handlers.py; tests/test_task_cost_telemetry.py
- previous_state: Merged
- requested_target: Archived
---
author: oompah
created: 2026-08-02 01:37
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 23
- Tokens: 39 in / 1.1K out [1.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 51s
- Log: OOMPAH-350__20260802T012927Z.jsonl
---
<!-- COMMENTS:END -->
