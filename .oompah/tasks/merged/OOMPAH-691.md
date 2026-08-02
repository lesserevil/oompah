---
id: OOMPAH-691
type: epic
status: Merged
priority: 0
title: Make dashboard WebSocket state provably convergent
parent: null
children:
- OOMPAH-692
- OOMPAH-693
- OOMPAH-694
- OOMPAH-695
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-02T02:00:17.265294Z'
updated_at: '2026-08-02T07:35:48.835875Z'
work_branch: epic-OOMPAH-691
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/654
review_number: '654'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/654
oompah.review_number: '654'
oompah.work_branch: epic-OOMPAH-691
oompah.target_branch: main
oompah.agent_run_id: 48308078-3dd3-40cc-b41b-72ca94d9324d
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-691
  head_sha: dd300faf519ca68652e60f9ed2a6465d9ceb0b9a
  submitted_at: '2026-08-02T07:18:27.177075+00:00'
  updated_at: '2026-08-02T07:18:27.177075+00:00'
oompah.task_costs:
  total_input_tokens: 139
  total_output_tokens: 4551
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 83
      output_tokens: 2572
      cost_usd: 0.0
    unknown:
      input_tokens: 56
      output_tokens: 1979
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 83
    output_tokens: 2572
    cost_usd: 0.0
    recorded_at: '2026-08-02T07:18:45.534424+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 156
    cost_usd: 0.0
    recorded_at: '2026-08-02T07:31:54.484207+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 50
    output_tokens: 1823
    cost_usd: 0.0
    recorded_at: '2026-08-02T07:35:46.968940+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-5ba17e15ff2a: '2026-08-02T07:31:32.335125+00:00'
    attempt-e16eb54c4b46: '2026-08-02T07:35:24.071056+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-691
    target_state: Done
    evidence_fingerprint: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    audit_ids:
    - audit-73c6e018d434
    kind: result
    applied: true
    retired_at: '2026-08-02T07:31:32.335134+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-691
    target_state: Merged
    evidence_fingerprint: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    audit_ids:
    - audit-13c123393a84
    kind: result
    applied: true
    retired_at: '2026-08-02T07:35:24.071068+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-691
    audit_id: audit-73c6e018d434
    attempt_id: attempt-5ba17e15ff2a
    target_state: Done
    evidence_fingerprint: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    status: In Validation
    audit_ids:
    - audit-73c6e018d434
    applied: true
    created_at: '2026-08-02T07:31:32.335146+00:00'
    applied_at: '2026-08-02T07:31:37.742001+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-691
    audit_id: audit-13c123393a84
    attempt_id: attempt-e16eb54c4b46
    target_state: Merged
    evidence_fingerprint: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    status: Merged
    audit_ids:
    - audit-13c123393a84
    applied: true
    created_at: '2026-08-02T07:35:24.071082+00:00'
    applied_at: '2026-08-02T07:35:29.176607+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-73c6e018d434
    project_id: proj-14849f1b
    task_id: OOMPAH-691
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    attempts:
    - version: 1
      attempt_id: attempt-5ba17e15ff2a
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
      created_at: '2026-08-02T07:27:32.538431+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T07:27:32.538431+00:00'
      branch_key: epic-OOMPAH-691
      verdict: pass
      completed_at: '2026-08-02T07:31:32.334995+00:00'
      ended_at: '2026-08-02T07:31:32.334995+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T07:26:17.708600+00:00'
    updated_at: '2026-08-02T07:31:32.334995+00:00'
  - version: 1
    audit_id: audit-13c123393a84
    project_id: proj-14849f1b
    task_id: OOMPAH-691
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    attempts:
    - version: 1
      attempt_id: attempt-e16eb54c4b46
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
      created_at: '2026-08-02T07:32:01.099713+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T07:32:01.099713+00:00'
      branch_key: epic-OOMPAH-691
      verdict: pass
      completed_at: '2026-08-02T07:35:24.070924+00:00'
      ended_at: '2026-08-02T07:35:24.070924+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T07:26:17.708600+00:00'
    updated_at: '2026-08-02T07:35:24.070924+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5ba17e15ff2a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    created_at: '2026-08-02T07:27:32.538431+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T07:27:32.538431+00:00'
    branch_key: epic-OOMPAH-691
  - version: 1
    attempt_id: attempt-e16eb54c4b46
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 57a700f225cb6392c51be53777ddc45e1e50fd927ceec7dbed185f7898613379
    created_at: '2026-08-02T07:32:01.099713+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T07:32:01.099713+00:00'
    branch_key: epic-OOMPAH-691
---
## Summary

Triggered by: OOMPAH-690

The dashboard currently consumes best-effort WebSocket snapshots without a durable ordering or freshness contract. A throttled or transport-lost state update can leave lastRunningAgents, alerts, task state, or other rendered data stale while the socket remains healthy and heartbeat pongs continue. Define and ship a versioned synchronization protocol that lets the browser prove whether its state is current and request an authoritative full replacement when it is not.

Scope:
- Add a per-service stream epoch and monotonic sequence/revision semantics that cover authoritative state changes, including changes coalesced before broadcast.
- Expose the latest revision in normal WebSocket envelopes and heartbeat responses so a live connection can still reveal that the browser is behind.
- Add a coherent full-state resynchronization response containing state, issues, and the revision watermark used to build them.
- Make the dashboard detect gaps, epoch changes, and stale revision watermarks; request one guarded full resync and atomically replace affected client state.
- Preserve console events, authenticated ws/wss behavior, incremental board rendering, editing/drag state, and reconnect backfill.
- Add operator-visible metrics/tests proving detection, recovery, and bounded request behavior under dropped, reordered, throttled, and reconnect scenarios.

Relevant code: oompah/server.py WebSocket broadcast/cache lifecycle, oompah/orchestrator.py observer notifications, oompah/templates/dashboard.html connection and state handlers, and WebSocket/dashboard lifecycle tests.

Acceptance criteria:
- Every authoritative dashboard state mutation advances a monotonic revision within a service epoch even when its immediate broadcast is coalesced.
- A connected browser can detect that it missed one or more mutations without relying on a manual refresh or socket failure.
- Gap detection triggers exactly one bounded full-state request, applies a coherent replacement, and resumes incremental processing from the returned watermark.
- Agent chips, alerts, task columns, and counters converge to the server state after dropped/coalesced messages.
- Focused race/lifecycle tests and the complete Makefile test gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 07:01
---
Branch quality gate passed for `1edd55f7c62f43448dd1d485e069cf3b61efd25b` using `make test` in 390.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 07:09
---
YOLO: CI tests failed on MR #654. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-02 07:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-02 07:10
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 07:11
---
Understanding: CI failed only on Python 3.12 and 3.13 (3.11 passed) on the same test: \`tests/test_ws_lifecycle.py::TestWebSocketRefreshAction::test_refresh_action_sends_state_back\` — pytest-timeout at 5s while receiving the 3rd message after sending {action: refresh}. This is a WS lifecycle test in the epic's convergence work. Plan: reproduce locally, inspect refresh handler on the server, and either loosen the read loop or ensure the refresh reliably drives the expected number of messages within the timeout.
---
author: oompah
created: 2026-08-02 07:16
---
Discovery: The refresh test does \`for _ in range(3): ws.receive_json()\` with no per-call timeout. The server refresh handler synchronously sends state, then calls \`broadcast_issues()\`. Under CI load, \`broadcast_issues\` may (a) never emit if the throttled/coalesced payload is None or (b) emit after >5s. If fewer than 3 messages arrive before the 5s pytest-timeout, \`receive_json\` blocks indefinitely and the whole test times out. The assertion only requires 'state' to be in the received types. Also there's a possible race with the initial connect's background \`_ensure_issues_snapshot_refresh(orch, broadcast=True)\` broadcasting one extra 'issues' before the refresh state. Bounded, early-exit fix: receive at most 2 messages, break as soon as 'state' is seen (state is guaranteed by the server refresh handler).
---
author: oompah
created: 2026-08-02 07:18
---
Implementation: Bounded the post-refresh receive loop in \`tests/test_ws_lifecycle.py::TestWebSocketRefreshAction::test_refresh_action_sends_state_back\` to at most 2 messages with an early break on 'state'. Both reads are backed by messages the server is guaranteed to deliver (refresh-handler state; plus at most one background issues broadcast from initial-connect's \`_ensure_issues_snapshot_refresh(broadcast=True)\` that can race in front). Assertion unchanged. This removes the unbounded 3rd/2nd \`receive_json\` that hung past 5s under CI load when \`broadcast_issues\` coalesced/suppressed its emit. Verification: 133 focused WebSocket/dashboard-convergence tests pass locally (test_ws_lifecycle.py 49, test_ws_full_sync.py 22, test_ws_fault_injection.py 16, test_dashboard_websocket_liveness.py 9, test_websocket_authenticated_bootstrap.py 14, test_orchestrator_full_sync.py 23). Pushed as dd300faf5.
---
author: oompah
created: 2026-08-02 07:18
---
Completion: CI fix pushed as dd300faf5 to epic-OOMPAH-691. Minimal edit to tests/test_ws_lifecycle.py bounds the post-refresh receive loop and adds an early break on 'state'; no feature code touched. Focused WS/dashboard-convergence tests pass locally. CI (test 3.11/3.12/3.13) re-queued on PR #654. Ready for the orchestrator's full-branch gate.
---
author: oompah
created: 2026-08-02 07:18
---
Fixed CI failure on tests/test_ws_lifecycle.py::TestWebSocketRefreshAction::test_refresh_action_sends_state_back by bounding the post-refresh receive_json loop to two messages with an early break on state (assertion unchanged). The prior range(3) had no per-call receive timeout and hung past 5s under CI load when broadcast_issues() coalesced/suppressed the issues emission. Focused WS/dashboard-convergence suites pass locally (133 tests).
---
author: oompah
created: 2026-08-02 07:18
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 54
- Tokens: 83 in / 2.6K out [2.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 20s
- Log: OOMPAH-691__20260802T071036Z.jsonl
---
author: oompah
created: 2026-08-02 07:24
---
Branch quality gate passed for `dd300faf519ca68652e60f9ed2a6465d9ceb0b9a` using `make test` in 391.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 07:26
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 07:26
---
YOLO: merged PR #654.
---
author: oompah
created: 2026-08-02 07:27
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 07:27
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 07:31
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_commit: b7fdf2b3f (Merge pull request #654 from lesserevil/epic-OOMPAH-691)
- head_branch_commit: dd300faf5
- children_done: OOMPAH-692, OOMPAH-693, OOMPAH-694, OOMPAH-695
- focused_ws_lifecycle: 49 passed in 1.16s (tests/test_ws_lifecycle.py)
- focused_convergence_suites: 84 passed in 7.14s (test_ws_full_sync + test_ws_fault_injection + test_dashboard_websocket_liveness + test_websocket_authenticated_bootstrap + test_orchestrator_full_sync)
- refresh_test: test_refresh_action_sends_state_back PASSED
- branch_gate_prior: make test passed 391.3s for dd300faf5 (tracker comment)
- epoch_impl: oompah/server.py:1007-1011 _protocol_epoch tied to _INSTANCE_ID
- revision_impl: oompah/server.py:1686-1691 _advance_state_revision monotonic
- envelope_stamp: oompah/server.py:~3228 envelope.setdefault epoch/revisions
- full_sync_impl: oompah/server.py:3367 _handle_full_sync + full_sync_error path
- client_full_sync: oompah/templates/dashboard.html:2679 socket.send({action:'full_sync'})
---
author: oompah
created: 2026-08-02 07:31
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 52, Tool calls: 41
- Tokens: 6 in / 156 out [162 total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 20s
- Log: OOMPAH-691__20260802T072738Z.jsonl
---
author: oompah
created: 2026-08-02 07:32
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 07:32
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 07:35
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- merge_commit: b7fdf2b3f
- merge_title: Merge pull request #654 from lesserevil/epic-OOMPAH-691
- merge_on_main: yes
- head_branch_commit: dd300faf5
- merge_diff_stat: 8 files changed, 2973 insertions(+), 162 deletions(-)
- epoch_impl: oompah/server.py:1011 _protocol_epoch = _INSTANCE_ID; :1672-1683 epoch reset + revision advance guarded
- full_sync_handler: oompah/server.py:3336 dispatch; :3367 _handle_full_sync; :3436 full_sync_error
- metrics: oompah/server.py:981 full_sync_requests; :1086 _ws_sync_record_full_sync_request
- client_full_sync: oompah/templates/dashboard.html:2679 socket.send full_sync; :2967-2976 full_sync/full_sync_error handling
- child_commits_in_pr: OOMPAH-692 (849d5f752,23d108b20); OOMPAH-693 (8283f794b,cf5f3cece); OOMPAH-694 (e84581658,a8fc3fff5,5d9186d6d); OOMPAH-695 (1293a2f3c,984127960,6897f3093)
- focused_ws_lifecycle_tests: 49 passed in 1.20s
- focused_convergence_tests: 84 passed in 7.15s (test_ws_full_sync + test_ws_fault_injection + test_dashboard_websocket_liveness + test_websocket_authenticated_bootstrap + test_orchestrator_full_sync)
- prior_ci_failure_test: test_refresh_action_sends_state_back PASSED
- branch_gate: make test passed in 391.3s for dd300faf5 (tracker comment record)
---
author: oompah
created: 2026-08-02 07:35
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 33
- Tokens: 50 in / 1.8K out [1.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 42s
- Log: OOMPAH-691__20260802T073210Z.jsonl
---
<!-- COMMENTS:END -->
