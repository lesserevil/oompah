---
id: OOMPAH-351
type: bug
status: Archived
priority: 1
title: Bound worker termination and service shutdown
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:37.758720Z'
updated_at: '2026-08-02T01:43:32.760017Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-1ad979eb0003: '2026-08-02T01:42:50.400595+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-351
    target_state: Archived
    evidence_fingerprint: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
    audit_ids:
    - audit-5a7928ab9055
    kind: result
    applied: true
    retired_at: '2026-08-02T01:42:50.400606+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-351
    audit_id: audit-5a7928ab9055
    attempt_id: attempt-1ad979eb0003
    target_state: Archived
    evidence_fingerprint: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
    status: Archived
    audit_ids:
    - audit-5a7928ab9055
    applied: true
    created_at: '2026-08-02T01:42:50.400622+00:00'
    applied_at: '2026-08-02T01:42:54.814772+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5a7928ab9055
    project_id: proj-14849f1b
    task_id: OOMPAH-351
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
    attempts:
    - version: 1
      attempt_id: attempt-1ad979eb0003
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
      created_at: '2026-08-02T01:29:20.955728+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:29:20.955728+00:00'
      branch_key: OOMPAH-351
      verdict: pass
      completed_at: '2026-08-02T01:42:50.400416+00:00'
      ended_at: '2026-08-02T01:42:50.400416+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:34.304931+00:00'
    updated_at: '2026-08-02T01:42:50.400416+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1ad979eb0003
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 58bfffb8386f4adc09607947a3781fc0fa488a01f0ab1869baeb8c31fe1450b0
    created_at: '2026-08-02T01:29:20.955728+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:29:20.955728+00:00'
    branch_key: OOMPAH-351
oompah.task_costs:
  total_input_tokens: 42
  total_output_tokens: 5859
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 42
      output_tokens: 5859
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 42
    output_tokens: 5859
    cost_usd: 0.0
    recorded_at: '2026-08-02T01:43:27.953044+00:00'
---
## Summary

Problem: orchestrator.stop cancels each worker and awaits it without a timeout. A cancellation-resistant ACP/CLI worker can make make stop and make restart hang indefinitely.

Implement: add configurable bounded termination phases: cancel worker, wait briefly, terminate managed subprocess/session, wait briefly, then record a forced-termination handoff and continue shutdown. Shutdown must continue across all workers even if one fails. Ensure checkpoint queues and webhook forwarders are stopped in a bounded manner.

Tests: fake worker that ignores cancellation; assert stop returns within configured bound, remaining workers are processed, and forced termination is logged/observable. Test normal graceful worker completion remains unchanged.

Acceptance: make restart cannot be held indefinitely by an agent worker; no orphaned managed subprocess remains after forced termination; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:07
---
Implemented bounded worker termination with OOMPAH_WORKER_TERMINATION_TIMEOUT_MS (default 10 seconds), documented in .env.example, plus regression coverage. Full suite is running.
---
author: oompah
created: 2026-07-22 01:16
---
Bounded cancelled-worker waits with a documented configurable timeout and regression test.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: bounded worker termination and shutdown is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
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
created: 2026-08-02 01:42
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 6dd2cdfcf
- config_env_var: OOMPAH_WORKER_TERMINATION_TIMEOUT_MS (default 10000ms) documented in .env.example:285 and oompah/config.py:658,1204
- orchestrator_bounded_paths: oompah/orchestrator.py:27715 (managed subprocess cleanup) and 30213-30284 (_terminate_agent bounded asyncio.wait with warning + forced cancel)
- regression_tests: tests/test_task_cost_telemetry.py: test_terminate_does_not_wait_forever_for_cancelled_worker, test_terminate_kills_cli_tree_when_worker_resists_cancel, test_session_shutdown_failure_is_observable_and_does_not_block_cleanup, test_shutdown_timeout_logs_warning_not_error
- focused_test_result: pytest -k 'terminate_does_not_wait_forever or terminate_kills_cli_tree or session_shutdown_failure or shutdown_timeout_logs_warning' => 4 passed
- neighbor_suite_result: pytest tests/test_orchestrator_handlers.py => 277 passed
- previous_state: Merged; auto-archive 7 days post-close per scheduler evidence
---
author: oompah
created: 2026-08-02 01:43
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 41, Tool calls: 36
- Tokens: 42 in / 5.9K out [5.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 55s
- Log: OOMPAH-351__20260802T012937Z.jsonl
---
<!-- COMMENTS:END -->
