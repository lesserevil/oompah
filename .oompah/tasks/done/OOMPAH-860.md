---
id: OOMPAH-860
type: task
status: Done
priority: null
title: Eliminate leaked coroutine and webhook subprocess state from exact gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-06T12:00:52.058327Z'
updated_at: '2026-08-06T14:58:20.085361Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-860
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-860
  base_branch: epic-OOMPAH-763
  base_sha: 52cf744ab676b50bdb999e9b0feb39bc092418c1
  head_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
  integrated_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
  submitted_at: '2026-08-06T13:37:28.746669+00:00'
  updated_at: '2026-08-06T14:09:56.308858+00:00'
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-860
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a59de283ba3fce1ef00a700d3279358371450c7869f1fc4dae4177bb4da8171f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: 'Required structural peers could not fit the bounded duplicate corpus.
    Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851,
    OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-861.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 3
  retry_after: '2026-08-06T13:28:38.317196+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.task_costs:
  total_input_tokens: 48811
  total_output_tokens: 466
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 48811
      output_tokens: 466
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 48811
    output_tokens: 466
    cost_usd: 0.0
    recorded_at: '2026-08-06T13:28:38.315039+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-860__20260806T132816Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-860
    source_sha: 34bf3aa8a471ef7fdc11d500423f3d06d06ca782
    completed_at: '2026-08-06T13:28:38.345766+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-4b4ed3a105c9: '2026-08-06T14:58:06.404486+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-860
    target_state: Done
    evidence_fingerprint: 04ac076dd4796fbe2edc9aa1bda946bf2b2de4446450fd2460daefcf26dcd542
    audit_ids:
    - audit-0503df39d875
    kind: result
    applied: true
    retired_at: '2026-08-06T14:58:06.404497+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-860
    audit_id: audit-0503df39d875
    attempt_id: attempt-4b4ed3a105c9
    target_state: Done
    evidence_fingerprint: 04ac076dd4796fbe2edc9aa1bda946bf2b2de4446450fd2460daefcf26dcd542
    status: Done
    audit_ids:
    - audit-0503df39d875
    applied: true
    created_at: '2026-08-06T14:58:06.404514+00:00'
    applied_at: '2026-08-06T14:58:17.268682+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0503df39d875
    project_id: proj-14849f1b
    task_id: OOMPAH-860
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 04ac076dd4796fbe2edc9aa1bda946bf2b2de4446450fd2460daefcf26dcd542
    attempts:
    - version: 1
      attempt_id: attempt-4b4ed3a105c9
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 04ac076dd4796fbe2edc9aa1bda946bf2b2de4446450fd2460daefcf26dcd542
      created_at: '2026-08-06T14:10:24.565431+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T14:10:24.565431+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-860
      verdict: pass
      completed_at: '2026-08-06T14:58:06.404250+00:00'
      ended_at: '2026-08-06T14:58:06.404250+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-06T14:09:58.930515+00:00'
    updated_at: '2026-08-06T14:58:06.404250+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4b4ed3a105c9
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 04ac076dd4796fbe2edc9aa1bda946bf2b2de4446450fd2460daefcf26dcd542
    created_at: '2026-08-06T14:10:24.565431+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T14:10:24.565431+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-860
---
## Summary

Live regression at canonical OOMPAH-837 head c31b8d32a on 2026-08-06: the combined-tree gate reached 16,631 passing tests, then failed an innocent synchronous epic-rebase test when garbage collection surfaced PytestUnraisableExceptionWarning from an asyncio BaseSubprocessTransport after its event loop closed, plus 'coroutine sleep was never awaited' and unittest.mock _terminate lookup context. Root-cause inspection found two allocator leaks: tests/test_submission_fencing.py creates six raw asyncio.sleep(0) coroutine objects in worker_task fields that the tested paths never await or close; tests/test_webhooks.py::test_launch_skips_missing_gh calls real WebhookForwarder._launch with extension availability unresolved, so when gh exists it spawns a real subprocess/stderr task and returns without terminating it. Xdist/GC later attributes the warnings to unrelated tests. Implementation scope: replace unused raw coroutines with a non-awaitable sentinel/None or explicitly owned tasks with deterministic cancellation+await; make the missing-gh test mock create_subprocess_exec to raise FileNotFoundError and assert no tracked process/task; audit adjacent fixtures for identical ownership mistakes without broad production changes. Required tests: focused submission_fencing + webhooks + epic_rebase_state with RuntimeWarning and PytestUnraisableExceptionWarning promoted to errors; repeat under -n 4/loadgroup or loadscope; complete exact make test at the repaired shared head. Acceptance: no real gh process launches in the missing-extension test, no unawaited sleep coroutine remains, focused tests leave no subprocess/task/transport residue, and the exact shared gate passes without unraisable warnings.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 12:22
---
Focused warning-as-error validation found and repaired one adjacent environment-dependent real spawn: test_exponential_backoff_capped_at_60s exercised real _launch after a crash. It now mocks _launch while preserving/asserting the actual restart delay/attempt path. On OOMPAH-837 head ef2120815, the affected submission-fencing, webhook, and epic-rebase suites passed 265 serial and 265 xdist tests with RuntimeWarning and PytestUnraisableExceptionWarning promoted to errors; independent static review accepted. The same test-only commit is cherry-picked cleanly onto task branch epic-OOMPAH-763--task-OOMPAH-860 at 34bf3aa8; branch-specific focused validation is intentionally waiting until the active OOMPAH-837 exact gate and audit release the serialized lane.
---
author: oompah
created: 2026-08-06 12:44
---
Dedicated task branch epic-OOMPAH-763--task-OOMPAH-860 is clean and pushed at exact head 34bf3aa8a. This patch already passed 265 serial + 265 xdist warning-as-error tests in the shared OOMPAH-837 composition and that exact full gate has now passed. Branch-specific focused validation is deliberately queued behind the active independent OOMPAH-837 terminal audit; no submission until that exact-branch evidence completes.
---
author: oompah
created: 2026-08-06 12:57
---
Branch-specific validation completed at pushed head 34bf3aa8a after OOMPAH-837 released the serialized lane: 256 serial and 256 xdist/loadscope tests passed with RuntimeWarning and PytestUnraisableExceptionWarning promoted to errors. make check-secrets and git diff --check passed; worktree is clean and exactly up to date with origin. Holding submission only long enough for the newly queued OOMPAH-804 parent terminal audit to take priority.
---
author: oompah
created: 2026-08-06 13:15
---
Closed exact-gate test resource leaks on dedicated pushed head 34bf3aa8a: no raw sleep coroutines, no real webhook gh spawn in missing-extension or backoff tests. Branch-specific warning-as-error validation passed 256 serial and 256 xdist/loadscope tests; check-secrets and diff check passed.
---
author: oompah
created: 2026-08-06 13:24
---
The combined-tree quality gate failed on `OOMPAH-860`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
runtestloop(session=session)
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/pluggy/_hooks.py", line 512, in __call__
INTERNALERROR>     return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
INTERNALERROR>            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/pluggy/_manager.py", line 120, in _hookexec
INTERNALERROR>     return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
INTERNALERROR>            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/pluggy/_callers.py", line 167, in _multicall
INTERNALERROR>     raise exception
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/pluggy/_callers.py", line 139, in _multicall
INTERNALERROR>     teardown.throw(exception)
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/_pytest/logging.py", line 801, in pytest_runtestloop
INTERNALERROR>     return (yield)  # Run all the tests.
INTERNALERROR>             ^^^^^
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/pluggy/_callers.py", line 139, in _multicall
INTERNALERROR>     teardown.throw(exception)
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/_pytest/terminal.py", line 707, in pytest_runtestloop
INTERNALERROR>     result = yield
INTERNALERROR>              ^^^^^
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/pluggy/_callers.py", line 121, in _multicall
INTERNALERROR>     res = hook_impl.function(*args)
INTERNALERROR>           ^^^^^^^^^^^^^^^^^^^^^^^^^
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/xdist/dsession.py", line 138, in pytest_runtestloop
INTERNALERROR>     self.loop_once()
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/xdist/dsession.py", line 163, in loop_once
INTERNALERROR>     call(**kwargs)
INTERNALERROR>   File "/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/xdist/dsession.py", line 217, in worker_workerfinished
INTERNALERROR>     assert not crashitem, (crashitem, node)
INTERNALERROR> AssertionError: ('tests/test_orchestrator_handlers.py::TestRunStep5cEpicMaintenance::test_tick_skips_new_epic_maintenance_when_previous_still_running', <WorkerController gw1>)
INTERNALERROR> assert not 'tests/test_orchestrator_handlers.py::TestRunStep5cEpicMaintenance::test_tick_skips_new_epic_maintenance_when_previous_still_running'

===== 7520 passed, 7 skipped, 1 xfailed, 42 warnings in 511.83s (0:08:31) ======

/home/shedwards/.oompah/tmp/oompah-quality-gate-un518ycf/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function WeakKeyDictionary.__init__.<locals>.remove at 0x76ef073fa520>

Traceback (most recent call last):
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/weakref.py", line 369, in remove
    def remove(k, selfref=ref(self)):
    
KeyboardInterrupt

Enable tracemalloc to get traceback where the object was allocated.
See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))
make: *** [Makefile:401: test] Error 3

```
---
author: oompah
created: 2026-08-06 13:26
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 13:26
---
Agent failed: Task worktree /home/shedwards/.oompah/worktrees/oompah/OOMPAH-860 is on OOMPAH-860, not expected branch epic-OOMPAH-763--task-OOMPAH-860; refusing to reset it. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-06 13:26
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
---
author: oompah
created: 2026-08-06 13:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 13:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 13:27
---
Gate result is an xdist worker-process disappearance after 7,520 passing tests, not a failed assertion in the O860 patch; no kernel OOM/kill/segfault evidence was logged. Repair dispatch then reproduced OOMPAH-815 branch-identity split: submit had required/accepted OOMPAH-860, but repair recomputed epic-OOMPAH-763--task-OOMPAH-860. Filed OOMPAH-861 for the regression. In-flight workaround: clean worktree switched to the hierarchical branch at the identical accepted head 34bf3aa8 so the scheduled repair agent can start without reset or code loss.
---
author: oompah
created: 2026-08-06 13:28
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 48.8K in / 466 out [49.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 0s
- Log: OOMPAH-860__20260806T132816Z.jsonl
---
author: oompah
created: 2026-08-06 13:29
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-861. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-06 13:37
---
Resubmitting exact hierarchical head d5edb84f1 after the full gate lost xdist worker gw1 in a known loaded-tick fixture. Composed the already-audited OOMPAH-791 stabilization patch exactly: contract-faithful dispatch timing mapping and release-recovery isolation for the crash item, plus its paired free-tier snapshot isolation. Verification: 53 serial + 53 xdist tests passed with warning errors; the exact crash node passed 20/20 separate four-worker xdist runs; original O860 256 serial + 256 xdist warning-as-error suite remains green; check-secrets/diff clean; independent exact-head review ACCEPT.
---
author: oompah
created: 2026-08-06 14:10
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 14:10
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 14:10
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 14:58
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- worktree_head_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
- origin_OOMPAH-860_head_sha: 34bf3aa8a471ef7fdc11d500423f3d06d06ca782
- origin_hierarchical_head_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
- primary_commit_subject: OOMPAH-860: close leaked exact-gate test resources
- primary_commit_stat: tests/test_submission_fencing.py +6/-6, tests/test_webhooks.py +17/-5
- stabilization_commit_subject: Stabilize loaded orchestration gate tests
- worker_task_none_locations: tests/test_submission_fencing.py:120,246,330,390,560,622,666 (7/7 replaced)
- asyncio_sleep_0_leaks_remaining: none in tests/
- test_launch_skips_missing_gh_mocks: patch(oompah.webhooks.asyncio.create_subprocess_exec, AsyncMock, side_effect=FileNotFoundError) + asserts process=None, stderr_task=None, disabled=True
- test_exponential_backoff_mocks_launch: patch.object(fwd, '_launch', AsyncMock) + asyncio.sleep mock, verifies launch.assert_awaited_once_with(fp)
- make_test_serial_result: 16081 passed, 7 skipped, 1 xfailed, 42 warnings in 2282.33s exit_code=0
- [REDACTED-credential-key]: clean exit_code=0
- git_diff_check_result: clean exit_code=0
- worktree_git_status: clean, up to date with origin (detached HEAD at hierarchical branch head)
---
<!-- COMMENTS:END -->
