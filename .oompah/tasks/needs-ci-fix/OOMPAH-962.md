---
id: OOMPAH-962
type: bug
status: Needs CI Fix
priority: 1
title: Recover quarantined control effects without task deadlock
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
- ci-fix
assignee: null
created_at: '2026-08-09T14:35:21.482578Z'
updated_at: '2026-08-09T15:53:50.777257Z'
work_branch: OOMPAH-962
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-962
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: d46e474e1a49a65b714c3304fc0fb6ccc35aea3d
  submitted_at: '2026-08-09T15:17:04.691942+00:00'
  updated_at: '2026-08-09T15:17:04.691942+00:00'
oompah.work_branch: OOMPAH-962
---
## Summary

Fix durable workflow recovery when a synchronous control-effect adapter exceeds its operation timeout and the invocation cannot be terminated. Live reproduction on OOMPAH-959: authority_revocation exceeded 60 seconds, WorkflowJobStore.quarantine_owned left the job running with phase=quarantined and lease_expires_at=NULL, and the per-task serialization predicate then blocked a newer direct_owner_claim indefinitely while the service process remained alive. Preserve the core safety invariant that a possibly running external mutation must never overlap a replacement. Add an observable bounded recovery path: detect when the detached call actually returns and safely finalize/recover its exact fenced job, or request/coalesce a graceful service recycle when it cannot be proven complete; surface operator health until recovery and do not require manual SQLite edits. Relevant code: workflow_worker quarantine/detached-call lifecycle, workflow job recovery and per-task serialization, orchestrator restart/health signaling. Tests: late successful and failed return, permanently blocked call, concurrent replacement, shutdown/restart, PID-generation fencing, no duplicate external mutation, no busy loop, and exact control/data lane behavior. Acceptance: a quarantined control effect either reaches a safe terminal/retry state after its call returns or triggers bounded safe recovery, subsequent same-task work flows automatically, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:42
---
Direct-owner implementation started in isolated worktree /home/shedwards/src/oompah-962 on branch OOMPAH-962. I am reproducing the authority_revocation timeout/quarantined NULL-lease deadlock and implementing fenced late-completion recovery while preserving never-overlap safety; no service mutation or deployment.
---
author: oompah
created: 2026-08-09 15:14
---
Implemented the quarantine settlement/recycle design on branch OOMPAH-962: exact late-result CAS settlement, durable bounded recycle marker, production mutation drain transfer, process/PID generation fencing, and no-overlap guards across control/data lanes and replacement paths. Focused config/job/worker/adapter/runtime suite is green (385 tests plus targeted replacement coverage). Rebasing onto current origin/main and performing final checks now.
---
author: oompah
created: 2026-08-09 15:17
---
Completed and pushed commit d46e474e1a49a65b714c3304fc0fb6ccc35aea3d on origin/OOMPAH-962, rebased on current origin/main. Verification: 386 focused tests passed across config, workflow ledger, worker, production implementation adapter, and runtime; terminal-audit scan passed; secret scan exited clean. The branch preserves quarantine until exact late settlement/process recovery, checkpoints late apply receipts without duplicate mutation, terminalizes late failures, requests one durable bounded graceful recycle for permanent blocks, and fences same-PID exec/PID reuse.
---
author: oompah
created: 2026-08-09 15:17
---
Implemented exact late quarantine settlement and bounded restart-safe recovery for timed-out workflow effects; pushed d46e474e1.
---
author: oompah
created: 2026-08-09 15:35
---
Independent-review corrections are complete and pushed at exact head 8bea28656286d06fd254e8d6a39592ade981939f. Marker/worker UUID mismatch no longer proves abandonment; only dead PID/start/process-generation or explicit operator authority recovers. Late settlement clears markers, stale markers are atomically replaced across lease ABA, failed settlement writes cross the bounded recycle path, and live quarantine count/age now degrade top-level health, emit an actionable alert, and fail the rollout canary. Verification: 468 affected tests passed, including the hosted workflow_scheduler health expectation; terminal-audit and secret scans passed.
---
author: oompah
created: 2026-08-09 15:53
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-962`
Target: `main`
Head: `d46e474e1a49a65b714c3304fc0fb6ccc35aea3d`
Command: `make test`
Result: `failed`
Process: exited with return code 2
Termination source: `process_exit`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
s 2 more items:
E         {'oldest_quarantined_age_seconds': None, 'quarantined': 0}
E         
E         Full diff:
E           {...
E         
E         ...Full output truncated (5 lines hidden), use '-vv' to show

tests/test_workflow_scheduler.py:761: AssertionError
=============================== warnings summary ===============================
tests/test_draft_epic_kanban.py::TestLabelAPIEndpoints::test_issues_api_returns_issue_type_field
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/unittest/mock.py:2217: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_http_auth.py::TestVerifyPassword::test_invalid_hash_format
tests/test_http_auth.py::TestVerifyPassword::test_valid_bcrypt_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_bcrypt_password
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r50h3ews/run/workspace/.venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

tests/test_http_auth.py: 21 warnings
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r50h3ews/run/workspace/tests/test_http_auth.py:37: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_apr1_password
tests/test_http_auth.py::TestLoadHtpasswdFile::test_valid_multiple_entries
tests/test_http_auth.py::TestVerifierCallable::test_multiple_users
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r50h3ews/run/workspace/tests/test_http_auth.py:49: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_mcp_gateway.py::test_mcp_client_can_initialize_list_allowed_tools_and_call_state
tests/test_mcp_gateway.py::test_authenticated_mcp_client_can_initialize_list_and_call_protected_api
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

tests/test_sdk_install_guards.py::TestClaudeSessionMcpServerGuard::test_no_tool_catalog_skips_mcp_server_path
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r50h3ews/run/workspace/oompah/acp_backends/claude.py:532: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for msg in client.receive_response():
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json
tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r50h3ews/run/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_workflow_scheduler.py::test_health_snapshot_exposes_queue_lease_retry_and_cursor_state
= 1 failed, 19025 passed, 22 skipped, 2 xfailed, 34 warnings in 150.79s (0:02:30) =

make: *** [Makefile:428: test] Error 1
```
---
<!-- COMMENTS:END -->
