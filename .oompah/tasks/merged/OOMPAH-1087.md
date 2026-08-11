---
id: OOMPAH-1087
type: task
status: Merged
priority: null
title: Prevent redundant WebSocket keepalive races during dashboard reconnects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T13:38:34.915522Z'
updated_at: '2026-08-11T15:15:46.128309Z'
work_branch: OOMPAH-1087
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/822
review_number: '822'
review_head: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 26ecd924-6fee-4fc9-9b64-dcf37334f4d8
  request_fingerprint: a4c85ef17eaf3089604c59256d01d1ebab7be8ce232c89a37ae0046f73c9a3c1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1087
  base_branch: main
  base_sha: fe9599111d478b8221a2949c878fecb61d558760
  head_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
  submitted_at: '2026-08-11T14:43:59.726348+00:00'
  updated_at: '2026-08-11T14:43:59.726348+00:00'
oompah.work_branch: OOMPAH-1087
oompah.review_url: https://github.com/lesserevil/oompah/pull/822
oompah.review_number: '822'
oompah.target_branch: main
oompah.review_head: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-a15f97a02624
    project_id: proj-14849f1b
    task_id: OOMPAH-1087
    digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
  - version: 1
    audit_id: audit-08766b832596
    project_id: proj-14849f1b
    task_id: OOMPAH-1087
    digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1087","audit-a15f97a02624","attempt-94a80f55ed5d"]': '2026-08-11T15:07:59.999370+00:00'
    '["proj-14849f1b","OOMPAH-1087","audit-08766b832596","attempt-cf685fd726e1"]': '2026-08-11T15:15:34.602069+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1087
    target_state: Done
    evidence_fingerprint: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    workflow_revision: null
    selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    landing_revision: null
    audit_ids:
    - audit-a15f97a02624
    kind: result
    applied: true
    retired_at: '2026-08-11T15:07:59.999386+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1087
    target_state: Merged
    evidence_fingerprint: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    workflow_revision: null
    selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    landing_revision: null
    audit_ids:
    - audit-08766b832596
    kind: result
    applied: true
    retired_at: '2026-08-11T15:15:34.602088+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1087
    audit_id: audit-a15f97a02624
    attempt_id: attempt-94a80f55ed5d
    target_state: Done
    evidence_fingerprint: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    status: In Validation
    audit_ids:
    - audit-a15f97a02624
    kind: result
    applied: true
    created_at: '2026-08-11T15:07:59.999397+00:00'
    applied_at: '2026-08-11T15:08:08.436395+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1087
    audit_id: audit-08766b832596
    attempt_id: attempt-cf685fd726e1
    target_state: Merged
    evidence_fingerprint: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    status: Merged
    audit_ids:
    - audit-08766b832596
    kind: result
    applied: true
    created_at: '2026-08-11T15:15:34.602100+00:00'
    applied_at: '2026-08-11T15:15:44.524460+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a15f97a02624
    project_id: proj-14849f1b
    task_id: OOMPAH-1087
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    attempts:
    - version: 1
      attempt_id: attempt-94a80f55ed5d
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
      created_at: '2026-08-11T15:03:46.787924+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T15:03:46.787924+00:00'
      branch_key: OOMPAH-1087
      selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
      selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
      verdict: pass
      completed_at: '2026-08-11T15:07:59.999188+00:00'
      ended_at: '2026-08-11T15:07:59.999188+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T15:02:58.783392+00:00'
    eligible_at: '2026-08-11T15:02:58.783392+00:00'
    selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    updated_at: '2026-08-11T15:07:59.999188+00:00'
  - version: 1
    audit_id: audit-08766b832596
    project_id: proj-14849f1b
    task_id: OOMPAH-1087
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    attempts:
    - version: 1
      attempt_id: attempt-cf685fd726e1
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
      created_at: '2026-08-11T15:12:19.616835+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T15:12:19.616835+00:00'
      branch_key: OOMPAH-1087
      selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
      selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
      verdict: pass
      completed_at: '2026-08-11T15:15:34.601890+00:00'
      ended_at: '2026-08-11T15:15:34.601890+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T15:02:58.783392+00:00'
    prerequisite_audit_id: audit-a15f97a02624
    selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    updated_at: '2026-08-11T15:15:34.601890+00:00'
    eligible_at: '2026-08-11T15:07:59.999188+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-94a80f55ed5d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    created_at: '2026-08-11T15:03:46.787924+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T15:03:46.787924+00:00'
    branch_key: OOMPAH-1087
    selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
  - version: 1
    attempt_id: attempt-cf685fd726e1
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 65d3490e8857ef5aee77ccd04ee5c566d4c2ad143af3efedc0517229668b8801
    created_at: '2026-08-11T15:12:19.616835+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T15:12:19.616835+00:00'
    branch_key: OOMPAH-1087
    selected_ref: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
    selected_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
oompah.task_costs:
  total_input_tokens: 266
  total_output_tokens: 10415
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 266
      output_tokens: 10415
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 266
    output_tokens: 10415
    cost_usd: 0.0
    recorded_at: '2026-08-11T15:08:15.551969+00:00'
---
## Summary

Live deployed main fe06a0ff logged an uncaught websockets legacy protocol ERROR at 2026-08-11 13:35:40 UTC: keepalive_ping failed in ping -> write_frame -> drain with AssertionError waiter is None or waiter.cancelled. The dashboard had disconnected/reconnected immediately beforehand while large state refreshes were under load. OOMPAH-690 already implements application-level browser ping/pong, stale-socket closure, reconnect, and backfill, so Uvicorn/websockets protocol keepalive may be redundant and racing connection close/backpressure. Reproduce the server lifecycle with concurrent/buffered sends plus client disconnect/reconnect at the protocol keepalive boundary; determine whether to disable Uvicorn protocol pings when the application heartbeat owns liveness or repair close/send serialization. Do not merely suppress ERROR logs. Preserve proxy liveness detection, browser application pong/freshness, sequence/full-sync recovery, client isolation, and graceful shutdown. Apply the fix consistently to both Uvicorn construction paths in oompah/__main__.py and any Granian fallback semantics. Add tests asserting the configured keepalive ownership, reconnect under blocked send/close emits no protocol assertion, application heartbeat still detects stale sockets and backfills, and no duplicate reconnect/send owner. Run focused WebSocket lifecycle/liveness/fault-injection tests and the canonical exact branch gate. Acceptance: the live disconnect/reconnect shape cannot emit a keepalive assertion or leave a stale UI connection, and dashboard recovery remains automatic.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 13:45
---
Reproduced the ownership conflict from the live 13:35:40 UTC keepalive_ping assertion: Uvicorn defaulted to a second protocol ping owner even though OOMPAH-690 dashboard application ping/pong already owns freshness, reconnect, and full-state backfill. Exact head 4d8c7b9a9 disables Uvicorn protocol pings through one shared config helper used by both default and Granian-fallback startup paths; transport WebSockets remain enabled. Focused dashboard liveness/WebSocket lifecycle/fault-injection/bootstrap coverage passed 99/99, Ruff (excluding one pre-existing unrelated F401), py_compile, diff check, commit hooks, and paranoid secret scan are green.
---
author: oompah
created: 2026-08-11 13:45
---
Made the dashboard application heartbeat the sole WebSocket liveness owner in both embedded Uvicorn paths, eliminating redundant protocol keepalive close/backpressure assertions while preserving reconnect and full-sync recovery.
---
author: oompah
created: 2026-08-11 13:51
---
Branch quality gate passed for `4d8c7b9a9fdda0e0119fe6ebbe6a0951c0631f71` using `make test` in 176.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 13:55
---
Fresh independent exact-head review ACCEPTED 4d8c7b9a9fdda0e0119fe6ebbe6a0951c0631f71. Reviewer verified both embedded Uvicorn construction paths use the shared configuration, Uvicorn 0.41 accepts ws_ping_interval=None and disables only protocol keepalive, while application ping/pong, 30-second stale closure, bounded reconnect, sequence/full-refresh backfill, and client cleanup remain intact. Evidence: 99/99 focused WebSocket/dashboard/bootstrap tests plus 7/7 direct causal/recovery assertions; exact clean pushed branch, canonical trailer, diff and secret scans green. Protected CI on PR #822 remains the next boundary.
---
author: oompah
created: 2026-08-11 14:41
---
Direct-owner refresh: PR 822 was green at 4d8c7b9 but its computed merge still targeted stale main fe06a0ff. With OOMPAH-1086 now merged to main fe959911, moving this task back to In Progress, rebasing its clean exact fix onto latest main, and requiring a fresh exact gate/review before merge.
---
author: oompah
created: 2026-08-11 14:43
---
Rebased cleanly onto latest main fe9599111 after OOMPAH-1086 landed. Replacement exact head is 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061, pushed with an exact force-with-lease against prior 4d8c7b9. Post-rebase focused WebSocket/dashboard lifecycle suite: 124 passed; terminal mutation scan 21/21; diff check clean. This replacement head requires fresh exact review and canonical branch gate before merge.
---
author: oompah
created: 2026-08-11 14:44
---
Rebased the WebSocket keepalive ownership fix onto latest main fe959911; exact head 0cf8f158 with 124 focused lifecycle tests green.
---
author: oompah
created: 2026-08-11 14:58
---
Branch quality gate passed for `0cf8f1586ddf6b48bd2315dd0b53234e36fdc061` using `make test` in 185.8s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 15:03
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 15:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 15:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 15:08
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- changes: oompah/__main__.py (30+/8-) + tests/test_uvicorn_websocket_keepalive.py (36+ new)
- shared_config_function: _uvicorn_config_kwargs(port) sets ws_ping_interval=None
- startup_paths[0]: Granian fallback: line ~588 uses **_uvicorn_config_kwargs(port)
- startup_paths[1]: Default Uvicorn: line ~597 uses **_uvicorn_config_kwargs(port)
- test_coverage[0]: test_uvicorn_protocol_keepalive_is_disabled_for_application_heartbeat: ws_ping_interval=None verified
- test_coverage[1]: test_both_embedded_uvicorn_paths_share_one_keepalive_configuration: exactly 2 calls, no hardcoded alternatives
- test_coverage[2]: test_dashboard_websocket_liveness.py: 16 tests for heartbeat/reconnect/backfill
- test_coverage[3]: test_ws_fault_injection.py: test_disconnect_reconnect_recovery validates reconnect
- preserved[0]: Application ping/pong heartbeat
- preserved[1]: Stale socket closure (30s timeout)
- preserved[2]: Reconnect with bounded backoff
- preserved[3]: Full-sync backfill on epoch/sequence changes
- preserved[4]: Client isolation and graceful shutdown
- quality_gate: make test PASSED (185.8s) for exact head 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
---
author: oompah
created: 2026-08-11 15:08
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 74, Tool calls: 32
- Tokens: 266 in / 10.4K out [10.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 26s
- Log: OOMPAH-1087__20260811T150404Z.jsonl
---
author: oompah
created: 2026-08-11 15:12
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 15:12
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 15:15
---
Audit PASS — Merged

Completion audit PASS for OOMPAH-1087: WebSocket keepalive ownership fix verified. Uvicorn protocol pings disabled via shared _uvicorn_config_kwargs(ws_ping_interval=None) in both Granian and default startup paths. Application-level heartbeat, reconnect recovery, and backfill preserved. Test coverage confirms configuration consistency and fault injection validates disconnect/reconnect. Quality gate (make test, 185.8s) passed for exact head 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061.

Safe evidence:
- fix_location: oompah/__main__.py - _uvicorn_config_kwargs(port) function
- key_change: ws_ping_interval=None in uvicorn Config
- startup_paths[0]: Granian fallback path: _uvicorn.Config(app, **_uvicorn_config_kwargs(port))
- startup_paths[1]: Default Uvicorn path: uvicorn.Config(app, **_uvicorn_config_kwargs(port))
- test_coverage[0]: test_uvicorn_protocol_keepalive_is_disabled_for_application_heartbeat
- test_coverage[1]: test_both_embedded_uvicorn_paths_share_one_keepalive_configuration
- test_coverage[2]: test_dashboard_websocket_liveness (16+ tests for heartbeat/reconnect/backfill)
- test_coverage[3]: test_disconnect_reconnect_recovery (fault injection)
- preserved_features[0]: Application ping/pong heartbeat
- preserved_features[1]: Stale socket closure (30s timeout)
- preserved_features[2]: Reconnect with bounded backoff
- preserved_features[3]: Full-sync backfill on epoch/sequence changes
- preserved_features[4]: Client isolation and graceful shutdown
- quality_gate: make test PASSED in 185.8s for 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
---
<!-- COMMENTS:END -->
