---
id: OOMPAH-863
type: bug
status: Ready to Integrate
priority: 1
title: Clear stale standalone Ready capacity alerts after a concurrent slot winner
parent: OOMPAH-763
children: []
blocked_by:
- OOMPAH-845
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T17:58:24.963566Z'
updated_at: '2026-08-07T14:08:56.462926Z'
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
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-863
oompah.integration:
  version: 2
  state: ready
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-863
  base_branch: epic-OOMPAH-763
  base_sha: a70fe0bc9fe9d6259aa9ae12a6cede33d3626a3e
  head_sha: 3e5ddd154985dc916a725244ba7fadf60db807e1
  submitted_at: '2026-08-06T21:50:50.778719+00:00'
  updated_at: '2026-08-07T14:08:53.759383+00:00'
  last_error: 'Rebase onto the latest epic head conflicted: a5

    warning: skipped previously applied commit e20dd758d

    warning: skipped previously applied commit 1f8f25614

    warning: skipped previously applied commit 22252cc04

    warning: skipped previously applied commit e40319c09

    warning: skipped previously applied commit 83c7a3987

    warning: skipped previously applied commit ccd1bf455

    warning: skipped previously applied commit 5d7cdb766

    warning: skipped previously applied commit 930cd74b9

    warning: skipped previously applied commit 52cf744ab

    warning: skipped previously applied commit 34bf3aa8a

    warning: skipped previously applied commit b768ea15c

    warning: skipped previously applied commit 8953687bd

    warning: skipped previously applied commit 512ede780

    warning: skipped previously applied commit 48fdfec42

    warning: skipped previously applied commit fdc7f0b02

    warning: skipped previously applied commit c6494afe4

    warning: skipped previously applied commit 5703f6f72

    warning: skipped previously applied commit 54c8abf8f

    warning: skipped previously applied commit 3c70caced

    warning: skipped previously applied commit 9ae09fa46

    warning: skipped previously applied commit 03563661c

    warning: skipped previously applied commit 6b759e1ca

    warning: skipped previously applied commit 6552636e5

    warning: skipped previously applied commit 12b076629

    warning: skipped previously applied commit a5d1973d0

    hint: use --reapply-cherry-picks to include skipped commits

    hint: Disable this message with "git config set advice.skippedCherryPicks false"

    Rebasing (1/37)

    error: could not apply 40e46bf8e... Add workflow decision shadow diagnostics

    hint: Resolve all conflicts manually, mark them as resolved with

    hint: "git add/rm <conflicted_files>", then run "git rebase --continue".

    hint: You can instead skip this commit: run "git rebase --skip".

    hint: To abort and get back to the state before "git rebase", run "git rebase
    --abort".

    hint: Disable this message with "git config set advice.mergeConflict false"

    Could not apply 40e46bf8e... # Add workflow decision shadow diagnostics'
  backoff_until: '2026-08-07T14:13:53.759346+00:00'
  repair_failure_reason: auth_failed
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
author: oompah
created: 2026-08-06 21:42
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 21:42
---
Understanding: the race allows a sweep that lost the durable standalone delivery reservation to publish a capacity alert after another sweep has already created or adopted the same task review. I will trace the synchronized authority/reservation/review path, add a deterministic concurrent regression plus lifecycle/state projection coverage, bind alert publication to fresh canonical authority, then run focused tests and submit the exact pushed head.
---
author: oompah
created: 2026-08-06 21:42
---
Gate triage: exact OOMPAH-863 focused scope is green (70 serial + 70 parallel); the full gate reached 16,309 passes and failed only tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_calls_tick_for_queued_events, alongside LogFileWatcher.start unawaited-coroutine warnings. OOMPAH-845 independently reproduced and fixed that cross-test coroutine leak at 7bb2362fc and is Ready to Integrate. Do not alter OOMPAH-863 reservation logic for this unrelated failure. Reproduce the single event-loop node under saturation; preserve exact head 3e5ddd154 unless evidence shows an additional test-harness fix, and account for OOMPAH-845 rather than duplicating its patch.
---
author: oompah
created: 2026-08-06 21:43
---
Discovery: the accepted three-commit patch already implements the required exact-authority repair. Durable reservations persist normalized accepted head plus delivery generation; same-head contenders observe but cannot acquire the winning reservation; capacity-alert arm/clear and review creation/adoption are fenced by delivery authority; same-process sweeps coalesce while cross-process barrier tests preserve the real race. The rejected full gate failed only an unrelated event-loop assertion after leaked LogFileWatcher.start coroutine warnings; OOMPAH-845 commit 7bb2362fc fixes the leak solely in tests/test_error_watcher.py.
---
author: oompah
created: 2026-08-06 21:46
---
Implementation: retained the independently accepted OOMPAH-863 patch unchanged at 3e5ddd154. It adds schema-v2 durable authority_generation/head_sha fields with serialized migration, exact-reservation observation in both capacity decision paths, authority-fenced alert suppression, owned create/adopt clearing, and same-process sweep coalescing while preserving cross-process CAS coverage. I am intentionally not cherry-picking OOMPAH-845; it is now the recorded dependency for the unrelated leaked-coroutine gate failure.
---
author: oompah
created: 2026-08-06 21:50
---
Verification: exact pushed head remains 3e5ddd154 with no working-tree changes. Its focused suites previously passed 70/70 serial and 70/70 parallel, and check-secrets passed; the combined-tree gate then reached 16,309 passes with one unrelated event-loop failure caused by the leaked LogFileWatcher.start coroutine now fixed by dependency OOMPAH-845 at 7bb2362fc. Current git diff --check passes. A local re-run could not start because this session validation guard points its lease DB at a read-only operator checkout; no test assertion or secret scan failure was reported.
---
author: oompah
created: 2026-08-06 21:50
---
Completion: delivered the exact standalone Ready authority/reservation race repair at 3e5ddd154. Same-task concurrent and restarted losers cannot publish stale capacity waits after an exact reservation or adopted review exists; genuine other-task capacity waits, ordering, one-review fencing, create-failure diagnostics, close/release, exact-head handling, and restart recovery remain covered. Branch is clean, pushed, and tracking its task remote; submission is intentionally ordered behind OOMPAH-845 so the next combined gate includes the unrelated coroutine-leak fix.
---
author: oompah
created: 2026-08-06 21:51
---
Bound standalone capacity alerts to exact durable delivery authority and eliminated stale same-task waits across concurrent sweeps and restart recovery; focused race/lifecycle coverage passes, with combined gate ordered behind OOMPAH-845.
---
author: oompah
created: 2026-08-06 21:51
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 77
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 56s
- Log: OOMPAH-863__20260806T214222Z.jsonl
---
<!-- COMMENTS:END -->
