---
id: OOMPAH-425
type: feature
status: Archived
priority: 1
title: Auto-scale agent concurrency when configured as zero
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:45:34.887827Z'
updated_at: '2026-08-02T01:48:00.834247Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f903ac64a8a8: '2026-08-02T01:47:35.028483+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-425
    target_state: Archived
    evidence_fingerprint: bc78b0c30049e7a69db5da871fa1a272fa36cf432110ad8d3a046859c7babf46
    audit_ids:
    - audit-a916a08af396
    kind: result
    applied: true
    retired_at: '2026-08-02T01:47:35.028493+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-425
    audit_id: audit-a916a08af396
    attempt_id: attempt-f903ac64a8a8
    target_state: Archived
    evidence_fingerprint: bc78b0c30049e7a69db5da871fa1a272fa36cf432110ad8d3a046859c7babf46
    status: Archived
    audit_ids:
    - audit-a916a08af396
    applied: true
    created_at: '2026-08-02T01:47:35.028510+00:00'
    applied_at: '2026-08-02T01:47:39.536311+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a916a08af396
    project_id: proj-14849f1b
    task_id: OOMPAH-425
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bc78b0c30049e7a69db5da871fa1a272fa36cf432110ad8d3a046859c7babf46
    attempts:
    - version: 1
      attempt_id: attempt-f903ac64a8a8
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: bc78b0c30049e7a69db5da871fa1a272fa36cf432110ad8d3a046859c7babf46
      created_at: '2026-08-02T01:38:59.839326+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:38:59.839326+00:00'
      branch_key: OOMPAH-425
      verdict: pass
      completed_at: '2026-08-02T01:47:35.028309+00:00'
      ended_at: '2026-08-02T01:47:35.028309+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:50.532180+00:00'
    updated_at: '2026-08-02T01:47:35.028309+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-f903ac64a8a8
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bc78b0c30049e7a69db5da871fa1a272fa36cf432110ad8d3a046859c7babf46
    created_at: '2026-08-02T01:38:59.839326+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:38:59.839326+00:00'
    branch_key: OOMPAH-425
---
## Summary

Support OOMPAH_MAX_CONCURRENT_AGENTS=0 as automatic capacity mode. Recalculate the effective concurrency cap on every scheduler tick using live CPU and available-memory capacity, while never terminating already-running agents if the calculated cap falls below the current running count. Preserve positive values as fixed caps, expose the effective cap in the runtime snapshot, document the environment setting, and add deterministic regression tests for scaling, tick reevaluation, and no-kill behavior. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:48
---
Implemented auto concurrency mode: configuration value 0 recalculates a conservative CPU/memory-based effective cap at every scheduler tick, never terminates agents when capacity drops, and exposes configured/effective limits in the runtime snapshot. Added regression coverage and ran make test successfully. Host .env has been set to 0 and will be applied on restart.
---
author: oompah
created: 2026-07-23 20:49
---
Added auto concurrency mode and enabled it locally with max concurrency set to 0.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: per-tick automatic concurrency scaling is present on origin/main in commit ad8db8419. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in ad8db8419 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:39
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:39
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:47
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: ad8db8419 Auto-scale agent concurrency (2026-07-23)
- merged_via: epic-OOMPAH-418 merge 10fac3f6e; reachable from HEAD 6252b5434
- code_symbols_at_head: _available_memory_bytes @ orchestrator.py:310; _auto_concurrency_limit @ 9421; _refresh_effective_concurrency @ 9434; tick call @ 5041; snapshot concurrency block @ 30655-30658
- env_documentation: .env.example line 92-93 documents zero-value auto mode
- tests_added: tests/test_auto_concurrency.py — 4 deterministic tests
- focused_test_run: python -m pytest tests/test_auto_concurrency.py -q => 4 passed in 2.69s
- config_change: oompah/config.py: comment on ServiceConfig.max_concurrent_agents documents auto sizing at zero
---
author: oompah
created: 2026-08-02 01:48
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 54, Tool calls: 40
- Tokens: 46 in / 7.2K out [7.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 53s
- Log: OOMPAH-425__20260802T013913Z.jsonl
---
<!-- COMMENTS:END -->
