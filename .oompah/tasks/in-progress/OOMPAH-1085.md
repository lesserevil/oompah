---
id: OOMPAH-1085
type: task
status: In Progress
priority: null
title: Dispatch exact terminal-audit successors through a dedicated bounded continuation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-11T12:49:48.293345Z'
updated_at: '2026-08-11T15:23:21.897174Z'
work_branch: OOMPAH-1085
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 878c6a42-3053-4e28-9139-8645e8b04dc0
  request_fingerprint: 8824c8446f415f1a94222b85e22a48381259f92dbe2560f42f2a306bb103013a
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1085
  head_sha: 7bd90702b13bfa876f49e5b4e5e27483997945b6
  submitted_at: '2026-08-11T13:35:21.687037+00:00'
  updated_at: '2026-08-11T13:35:21.687037+00:00'
oompah.work_branch: OOMPAH-1085
oompah.agent_run_id: 8edf6d56-a309-470c-aea6-203826fef15a
oompah.work_contributors:
  runs:
  - run_id: 677e8b1ddbc445509377e5599ada2af7--contributor-57ff1a86c984
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: ci_fix
    source_branch: OOMPAH-1085
    source_sha: null
    completed_at: ''
---
## Summary

Live OOMPAH-1082 acceptance failed on 2026-08-11: the Merged terminal-audit successor became durably eligible at 12:37:31.504 UTC and the Done workflow job completed at 12:37:40.499, but the successor was not claimed until 12:39:36.908 (116.409 seconds after completion). The current wake bridge stores the exact hint and posts generic REFRESH_REQUESTED, which is serialized behind a long full-world scheduler tick; _refresh_requested has no effective consumer. Implement a dedicated, coalesced, single-flight terminal-audit continuation lane that can run the audit phase independently of an in-flight full reconciliation. Preserve exact prerequisite and workflow-job CAS authority, same-branch fencing, pause/capacity/fairness behavior, restart durability, and no-concurrent-sibling guarantees. Re-arm the lane when a worker retires or capacity is released and eligible exact wakes remain, and on unpause/restart. Add observability for eligible, wake registered, lane scheduled/started/deferred, claim/dispatch, and latency. Tests must barrier-block a production durable reconciliation after its audit phase, complete Done PASS, retire the current worker/branch fence, and prove the exact Merged successor is claimed before the full reconciliation is released; also cover a wake arriving while the lane is active with one-owner/one-recheck handoff, capacity held until worker exit, coalesced multiple wakes, pause/unpause, restart, stale hint retirement, no duplicate launch, and deferred/failure paths. Run focused and adjacent terminal-audit/orchestrator tests plus the project gate. Acceptance: successor dispatch latency is bounded by the dedicated continuation and does not depend on completion of an unrelated full-world tick.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 13:09
---
Implemented the dedicated single-flight terminal-audit continuation lane on branch OOMPAH-1085. Exact wakes now bypass serialized full-world reconciliation, share one audit scan lock with ordinary ticks, retain pause/restart authority, and re-arm on WORKER_EXIT capacity release. Added blocked-durable-reconcile, active-wake coalescing, capacity handoff, pause/unpause, restart reconstruction, stale-hint, one-owner, failure-observability, and latency coverage. Focused terminal-audit suites pass (141); broader adjacent audit/event/quiesce suites pass (708 and 238); terminal mutation scan passes 21/21. The full project gate is running. After it completes I will compose current origin/main (OOMPAH-1083), rerun combined focused checks and the final gate, then push and submit.
---
author: oompah
created: 2026-08-11 13:18
---
Additional production evidence on the pre-fix path: the OOMPAH-1083 Done audit PASS was accepted at 13:12:30 UTC, its worker/worktree and branch fence retired by 13:12:42, but the exact Merged successor did not begin dispatch until 13:13:43. The roughly 61-second post-retirement gap confirms the remaining delay was the generic full-tick wake path, not provider capacity or same-branch authority.
---
author: oompah
created: 2026-08-11 13:35
---
Review-ready head 7bd90702b13bfa876f49e5b4e5e27483997945b6 is pushed on OOMPAH-1085, based exactly on origin/main fe06a0ff1. Post-rebase verification: 238 focused orchestrator/audit/event/pause tests passed; 1,102 adjacent terminal-audit/quiesce/quality-gate/server tests passed; focused terminal suite 141 passed; terminal mutation scan 21/21; paranoid secret scan passed. A duplicate manual full gate was stopped at 9,467 passed, 7 skipped, 2 xfailed, zero failures so the server can own the single canonical exact-head branch gate. Production acceptance context includes both the 116.409-second OOMPAH-1082 delay and the later roughly 61-second OOMPAH-1083 post-retirement delay on the pre-fix generic path.
---
author: oompah
created: 2026-08-11 13:35
---
Implemented and pushed a dedicated coalesced single-flight terminal-audit continuation lane at 7bd90702b. Exact successor wakes now bypass unrelated full-world reconciliation while preserving shared audit ownership, workflow CAS authority, branch/capacity/pause/restart fences, and emitting claim/dispatch latency telemetry. Added production blocked-reconcile and race/lifecycle regression coverage; focused and adjacent verification is green. Ready for the server-owned exact-head branch gate and independent terminal audits.
---
author: oompah
created: 2026-08-11 13:41
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-1085`
Target: `main`
Head: `7bd90702b13bfa876f49e5b4e5e27483997945b6`
Command: `make test`
Result: `failed`
Process: exited with return code 2
Termination source: `process_exit`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
ion_delegates_are_thin(
        method: object, max_lines: int
    ) -> None:
        lines, branches = _method_metrics(method)
    
>       assert lines <= max_lines
E       assert 11 <= 8

tests/test_workflow_module_boundaries.py:177: AssertionError
=============================== warnings summary ===============================
tests/test_auditor_quiesce_fence.py::test_worker_task_creation_cancelled_error_rolls_back_before_reraising
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/unittest/mock.py:2217: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_http_auth.py::TestVerifyPassword::test_invalid_hash_format
tests/test_http_auth.py::TestVerifyPassword::test_valid_bcrypt_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_bcrypt_password
  /home/shedwards/.oompah/tmp/oompah-quality-gate-rns9hxyc/run/workspace/.venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

tests/test_http_auth.py: 21 warnings
  /home/shedwards/.oompah/tmp/oompah-quality-gate-rns9hxyc/run/workspace/tests/test_http_auth.py:37: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_apr1_password
tests/test_http_auth.py::TestLoadHtpasswdFile::test_valid_multiple_entries
tests/test_http_auth.py::TestVerifierCallable::test_multiple_users
  /home/shedwards/.oompah/tmp/oompah-quality-gate-rns9hxyc/run/workspace/tests/test_http_auth.py:49: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_mcp_gateway.py::test_mcp_client_can_initialize_list_allowed_tools_and_call_state
tests/test_mcp_gateway.py::test_authenticated_mcp_client_can_initialize_list_and_call_protected_api
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

tests/test_sdk_install_guards.py::TestClaudeSessionMcpServerGuard::test_no_tool_catalog_skips_mcp_server_path
  /home/shedwards/.oompah/tmp/oompah-quality-gate-rns9hxyc/run/workspace/oompah/acp_backends/claude.py:532: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for msg in client.receive_response():
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json
tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-rns9hxyc/run/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_workflow_module_boundaries.py::test_orchestrator_composition_delegates_are_thin[_post_event-8]
= 1 failed, 19962 passed, 22 skipped, 2 xfailed, 34 warnings in 161.59s (0:02:41) =

make: *** [Makefile:458: test] Error 1
```
---
author: oompah
created: 2026-08-11 13:42
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-11 13:42
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-11 13:42
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 40s
- Log: OOMPAH-1085__20260811T134228Z.jsonl
---
author: oompah
created: 2026-08-11 13:45
---
Independent review blocked the submitted head before its canonical gate: an exact successor wake can survive an authoritative complete scan when the task disappeared from the candidate corpus, causing every later WORKER_EXIT to re-arm the lane, and older scans can compare a stale hint then delete a newer audit ID. Reopening for authoritative absent-task reconciliation, scheduler-loop-owned wake mutation, value-CAS removal, and repeated-exit/no-spin regressions.
---
author: oompah
created: 2026-08-11 13:45
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 34s
- Log: OOMPAH-1085__20260811T134228Z.jsonl
---
author: oompah
created: 2026-08-11 14:57
---
Rebased the repaired dedicated audit-successor implementation onto current origin/main fe9599111d478b8221a2949c878fecb61d558760 and pushed replacement exact head 7ca1e67353d25254370466b870728463dbf6f681. The repair atomically retires completed/absent exact running entries while retaining incomplete or contradictory evidence, marshals provider-thread callbacks onto the scheduler loop, snapshots shared maps safely, makes repeated worker-exit events idempotent, and keeps the event-post helper thin. Post-rebase verification: 178 focused event-loop/terminal-audit observability tests passed; terminal mutation scan 21/21; git diff check clean. Earlier pre-rebase adjacent evidence was 1,140 tests plus 261 focused and an independent repair review ACCEPT. Awaiting a fresh independent exact-head review before submission.
---
author: oompah
created: 2026-08-11 15:23
---
Fresh fairness repair is pushed at exact head dcb52a5110f91cab5b6b732f5378ba13fb6a4d27, rebased on origin/main 6449341d762d9c7645271b8479dfa406e648be54. The dedicated terminal-audit owner now recomputes non-audit capacity reservation only after acquiring the shared audit lane lock, so runnable implementation proof published while the continuation waits cannot be missed. It preserves both the ordinary dispatcher's exact ready hint and runtime-published WorkDecision provider readiness, while excluding non-provider implementation control jobs. Deterministic races prove max_agents=1 keeps the implementation turn and max_agents=4 with a configured two-slot reserve launches only into the two unreserved slots. Verification: 246 focused audit/event/architecture tests passed; 912 adjacent terminal coordinator/enforcement/workflow/runtime/decision tests passed; terminal mutation scan 21/21; compileall and git diff checks clean. Branch is pushed and clean; awaiting fresh independent exact-head review. Do not submit or merge yet.
---
<!-- COMMENTS:END -->
