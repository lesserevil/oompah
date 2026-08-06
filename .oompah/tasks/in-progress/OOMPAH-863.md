---
id: OOMPAH-863
type: bug
status: In Progress
priority: 1
title: Clear stale standalone Ready capacity alerts after a concurrent slot winner
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T17:58:24.963566Z'
updated_at: '2026-08-06T21:42:10.598572Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-863
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7752a9d697051b42829f41131d2549044bd68bcdf9b08358058a2e1bdc27616b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T18:06:59.995365+00:00'
  matched_identifiers: []
  evidence: Project-owner review of the active task corpus found no equivalent task.
    OOMPAH-863 specifically fixes stale same-task standalone capacity alerts after
    a concurrent delivery sweep has already won the durable review slot. OOMPAH-752
    covers FIFO selection, OOMPAH-735 alert actionability, and historical capacity
    tasks cover reservation, but none bind alert publication to the exact concurrent
    winner generation. The inconclusive result is the deployed pre-OOMPAH-853 corpus
    budget bug.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T18:06:59.995365+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Project-owner review of the active task corpus found no
    equivalent task. OOMPAH-863 specifically fixes stale same-task standalone capacity
    alerts after a concurrent delivery sweep has already won the durable review slot.
    OOMPAH-752 covers FIFO selection, OOMPAH-735 alert actionability, and historical
    capacity tasks cover reservation, but none bind alert publication to the exact
    concurrent winner generation. The inconclusive result is the deployed pre-OOMPAH-853
    corpus budget bug.
oompah.agent_run_id: f40d6223-4bf0-4302-9be4-44e43b8e42e7
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-863
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-863
  base_branch: epic-OOMPAH-763
  base_sha: a5d1973d043ff2375d56d89d0ea8bd5326e24f63
  head_sha: 3e5ddd154985dc916a725244ba7fadf60db807e1
  submitted_at: '2026-08-06T21:21:07.909745+00:00'
  updated_at: '2026-08-06T21:40:41.633140+00:00'
  last_error: "Combined-tree quality gate failed: ning: coroutine 'LogFileWatcher.start'\
    \ was never awaited\n    def __init__(self, name, parent):\n  Enable tracemalloc\
    \ to get traceback where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n\ntests/test_event_driven_loop.py::TestFullSyncIntervalConfig::test_default_is_300000\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/.venv/lib/python3.12/site-packages/_pytest/fixtures.py:1132:\
    \ RuntimeWarning: coroutine 'LogFileWatcher.start' was never awaited\n    def\
    \ __init__(self, request: FixtureRequest) -> None:\n  Enable tracemalloc to get\
    \ traceback where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n\ntests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password\n\
    tests/test_http_auth.py::TestVerifyPassword::test_wrong_bcrypt_password\ntests/test_http_auth.py::TestVerifyPassword::test_valid_bcrypt_password\n\
    tests/test_http_auth.py::TestCredentialReload::test_atomic_rotation_adds_and_removes_users\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/.venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854:\
    \ DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13\n\
    \    from crypt import crypt as _crypt\n\ntests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password\n\
    tests/test_http_auth.py::TestVerifyPassword::test_wrong_apr1_password\ntests/test_http_auth.py::TestLoadHtpasswdFile::test_valid_multiple_entries\n\
    tests/test_http_auth.py::TestVerifierCallable::test_multiple_users\n  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/tests/test_http_auth.py:49:\
    \ DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated\
    \ as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash()\
    \ instead.\n    return ctx.encrypt(\"password\")\n\ntests/test_http_auth.py: 21\
    \ warnings\n  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/tests/test_http_auth.py:37:\
    \ DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated\
    \ as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash()\
    \ instead.\n    return ctx.encrypt(\"password\")\n\ntests/test_mcp_gateway.py::test_mcp_client_can_initialize_list_allowed_tools_and_call_state\n\
    tests/test_mcp_gateway.py::test_authenticated_mcp_client_can_initialize_list_and_call_protected_api\n\
    \  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/contextlib.py:105:\
    \ DeprecationWarning: Use `streamable_http_client` instead.\n    self.gen = func(*args,\
    \ **kwds)\n\ntests/test_sdk_install_guards.py::TestClaudeSessionMcpServerGuard::test_no_tool_catalog_skips_mcp_server_path\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/oompah/acp_backends/claude.py:508:\
    \ RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited\n\
    \    async for msg in client.receive_response():\n  Enable tracemalloc to get\
    \ traceback where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n\ntests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json\n\
    tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408:\
    \ DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.\n\
    \    headers, stream = encode_request(\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n\
    =========================== short test summary info ============================\n\
    FAILED tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_calls_tick_for_queued_events\n\
    = 1 failed, 16309 passed, 8 skipped, 1 xfailed, 40 warnings in 1046.82s (0:17:26)\
    \ =\n\nmake: *** [Makefile:401: test] Error 1\n"
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2914
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2914
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2914
    cost_usd: 0.0
    recorded_at: '2026-08-06T18:01:08.530869+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-863__20260806T180027Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-863
    source_sha: 0e0056375918977c9b0b2d59524ce8ae68ceee40
    completed_at: '2026-08-06T18:01:08.552372+00:00'
---
## Summary

Live deterministic reproduction while validating OOMPAH-851: two concurrent _reconcile_standalone_ready_to_integrate_tasks sweeps run with max_in_flight_prs=1. Durable reservation correctly permits only one review, but the losing sweep can arm standalone_ready_delivery for the same task after the winner creates or adopts its review. The dashboard then reports that the already-delivering task is waiting for capacity until a later sweep clears the row. This is a truthful-state/authority race, not normal capacity backpressure. Implementation scope: bind capacity-alert arm and clear to the exact standalone delivery authority, durable reservation, review identity, accepted head, and generation under the existing project/task synchronization or an equivalent CAS. A losing or stale sweep must refresh canonical review/reservation state immediately before publishing a wait alert; a winner must clear the same-task alert atomically with review creation/adoption. Preserve real capacity alerts for other waiting tasks, FIFO/priority ordering, one-review capacity, exact-head fencing, restart recovery, webhook lag handling, and failed-review-create diagnostics. Relevant code: Orchestrator._reconcile_standalone_ready_to_integrate_tasks, standalone delivery authority/reservation helpers, review creation/adoption, alert projection, and tests/test_standalone_ready_to_integrate.py. Required tests: deterministic barrier reproduction of two sweeps for the same task, repeated under load; two-task contention where the genuine loser remains informational; existing-review adoption; review-create failure; review close/release; restart between reservation and alert publication; and websocket/state snapshots. Acceptance criteria: once a concurrent winner creates or adopts the task review, the same response generation and every later snapshot contain no capacity-wait alert for that task; genuine waiting tasks remain truthful; exactly one review is created; stale callbacks cannot re-arm the alert; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 18:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 18:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 18:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.9K out [2.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-863__20260806T180027Z.jsonl
---
author: oompah
created: 2026-08-06 18:01
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-06 18:20
---
Direct-owner implementation claimed after the deployed scheduler completed multiple ticks with ten available agent slots but normal_dispatch=0. Filed OOMPAH-864 for the distinct owner-resolution rearm deadlock. OOMPAH-863 repair now persists accepted head and delivery generation on durable review reservations, makes concurrent/restarted same-head sweeps observe (not acquire) the winning reservation, and suppresses stale capacity alerts in both the pre-gate capacity and post-gate CAS paths. Deterministic same-process and restart regressions plus schema-v1 migration coverage are added. Static parsing and diff check pass; independent review and leased tests remain before commit/submission.
---
author: oompah
created: 2026-08-06 18:39
---
Concurrent same-head reservation and stale-alert repair is committed/rebased and independently accepted, including cross-process schema migration serialization and spawn-concurrent regression cleanup. make check-secrets and static checks pass. Focused serial/xdist verification will run after the currently queued OOMPAH-846 bundle.
---
author: oompah
created: 2026-08-06 21:21
---
Made standalone review-capacity reservations exact and restart-durable, serialized schema migration across processes, coalesced overlapping same-process Ready reconciliation without weakening terminal authority fencing, and removed false capacity-wait alerts for exact owned reservations. Independent review accepted the final repair; all 70 focused tests passed serial and parallel; check-secrets passed at exact pushed head 3e5ddd154985dc916a725244ba7fadf60db807e1.
---
author: oompah
created: 2026-08-06 21:40
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-863`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
ning: coroutine 'LogFileWatcher.start' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_event_driven_loop.py::TestFullSyncIntervalConfig::test_default_is_300000
  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/.venv/lib/python3.12/site-packages/_pytest/fixtures.py:1132: RuntimeWarning: coroutine 'LogFileWatcher.start' was never awaited
    def __init__(self, request: FixtureRequest) -> None:
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_bcrypt_password
tests/test_http_auth.py::TestVerifyPassword::test_valid_bcrypt_password
tests/test_http_auth.py::TestCredentialReload::test_atomic_rotation_adds_and_removes_users
  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/.venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

tests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_apr1_password
tests/test_http_auth.py::TestLoadHtpasswdFile::test_valid_multiple_entries
tests/test_http_auth.py::TestVerifierCallable::test_multiple_users
  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/tests/test_http_auth.py:49: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_http_auth.py: 21 warnings
  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/tests/test_http_auth.py:37: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_mcp_gateway.py::test_mcp_client_can_initialize_list_allowed_tools_and_call_state
tests/test_mcp_gateway.py::test_authenticated_mcp_client_can_initialize_list_and_call_protected_api
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

tests/test_sdk_install_guards.py::TestClaudeSessionMcpServerGuard::test_no_tool_catalog_skips_mcp_server_path
  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/oompah/acp_backends/claude.py:508: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for msg in client.receive_response():
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json
tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-5eff804h/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_calls_tick_for_queued_events
= 1 failed, 16309 passed, 8 skipped, 1 xfailed, 40 warnings in 1046.82s (0:17:26) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-06 21:42
---
Agent dispatched (profile: deep)
---
<!-- COMMENTS:END -->
