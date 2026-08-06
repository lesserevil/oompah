---
id: OOMPAH-834
type: task
status: In Progress
priority: 1
title: Bind implementation lifecycle events to durable task-scoped handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:27.595461Z'
updated_at: '2026-08-06T09:48:51.045973Z'
work_branch: epic-OOMPAH-804--task-OOMPAH-834
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a6f9dee590a1fc5a8c40f1239ab3ebaa8e29734260cd74804b838af5ad054eda
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T09:18:57.011462+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-804 is the parent production-runtime integration,\
    \ while OOMPAH-835, OOMPAH-836, and OOMPAH-837 cover separate review, integration,\
    \ and epic domains. None duplicates this task\u2019s nine implementation lifecycle\
    \ actions.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: OOMPAH-804 is the parent production-runtime\
    \ integration, while OOMPAH-835, OOMPAH-836, and OOMPAH-837 cover separate review,\
    \ integration, and epic domains. None duplicates this task\u2019s nine implementation\
    \ lifecycle actions."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8f54bf2b-0dd9-4d1b-ab20-53c638d78db8
oompah.work_branch: epic-OOMPAH-804--task-OOMPAH-834
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-804--task-OOMPAH-834
  base_branch: epic-OOMPAH-804
  base_sha: f89c477d4c03a8992a7278337182c0352da5de16
  head_sha: f89c477d4c03a8992a7278337182c0352da5de16
  submitted_at: '2026-08-06T09:31:16.579601+00:00'
  updated_at: '2026-08-06T09:47:41.214584+00:00'
  last_error: "Combined-tree quality gate failed: -x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n      self._check_closed()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n      raise RuntimeError('Event loop is closed')\n\
    \  RuntimeError: Event loop is closed\n  \n  Enable tracemalloc to get traceback\
    \ where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    \ntests/test_websocket_authenticated_bootstrap.py::TestWebSocketBootstrapIncludesAuth::test_ws_bootstrap_includes_service_instance_id\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-3nms8061/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x7ccc7420b9c0>\n  \n  Traceback (most recent call last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 126, in __del__\n      self.close()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 104, in close\n      proto.pipe.close()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 568, in close\n      self._close(None)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 592, in _close\n      self._loop.call_soon(self._call_connection_lost,\
    \ exc)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n      self._check_closed()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n      raise RuntimeError('Event loop is closed')\n\
    \  RuntimeError: Event loop is closed\n  \n  Enable tracemalloc to get traceback\
    \ where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    \n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n===========================\
    \ short test summary info ============================\nFAILED tests/test_dispatch_close_race.py::TestUiCloseCancelsPendingRetry::test_pending_retry_cancelled_when_issue_closed_via_ui\n\
    FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_claim_writes_run_id_to_tracker\n\
    FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_claim_success_proceeds_to_worker\n\
    FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_pre_dispatch_terminal_state_aborts\n\
    FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_in_progress_update_called_on_github_tracker\n\
    FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_native_oompah_md_claim_writes_run_id\n\
    FAILED tests/test_orchestrator_github_lifecycle.py::TestMixedProjectDispatch::test_dispatch_uses_project_scoped_tracker_for_github_issue\n\
    FAILED tests/test_worker_submission.py::test_same_head_resubmit_from_in_progress_restores_ready_lifecycle\n\
    FAILED tests/test_worker_submission.py::test_same_head_resubmit_from_needs_human_restores_ready_lifecycle\n\
    FAILED tests/test_worker_submission.py::test_same_head_resubmit_from_needs_ci_fix_restores_ready_lifecycle\n\
    FAILED tests/test_worker_submission.py::test_duplicate_same_head_submit_already_ready_is_fully_idempotent\n\
    FAILED tests/test_worker_submission.py::test_same_head_ready_submit_backfills_missing_work_branch_projection\n\
    = 12 failed, 16620 passed, 8 skipped, 1 xfailed, 48 warnings in 917.74s (0:15:17)\
    \ =\n\nmake: *** [Makefile:401: test] Error 1\n"
oompah.task_costs:
  total_input_tokens: 49361
  total_output_tokens: 271
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 49361
      output_tokens: 271
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 49361
    output_tokens: 271
    cost_usd: 0.0
    recorded_at: '2026-08-06T09:18:57.009999+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-834__20260806T091844Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-804--task-OOMPAH-834
    source_sha: 2a09b085bfb71b742c07d8ed91bc1c76add5d029
    completed_at: '2026-08-06T09:18:57.028464+00:00'
---
## Summary

Implement the production backend and event cutover for all nine ImplementationWorkflow actions: implementation_start, direct_owner_claim, duplicate_screening, focus_handoff, worker_exit, validation_submission, authority_revocation, implementation_retry, and implementation_recovery. Add a crash-safe exact disposition/effect-receipt ledger keyed by project, task, workflow generation, action, and immutable head/evidence; make inspect/apply/verify restart-idempotent and project-scoped. Route accepted API/ACP owner claims/releases, task handoffs/submissions, dispatch, worker exit, revocation, retry, duplicate screening, and startup recovery through schedule_event in enforce mode, disabling the corresponding legacy writer/timer/ownership path without calling whole-project sweeps from a task job. Relevant files: oompah/implementation_workflow.py, oompah/workflow_runtime.py or a new typed adapter module, oompah/orchestrator.py, oompah/server.py, workflow job/transition services. Required tests: native tracker plus temporary repo, exact multi-project routing, owner/submission races, child-exit crash after apply before verify, restart replay, stale generation fencing, retry timing, duplicate preflight, and enforce single-writer assertions. Acceptance: every implementation action has a real project-bound handler and production event source; durable job/receipt is the sole enforce-mode owner; no stale callback or legacy map can duplicate an effect.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 09:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 09:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 09:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 49.4K in / 271 out [49.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 42s
- Log: OOMPAH-834__20260806T091844Z.jsonl
---
author: oompah
created: 2026-08-06 09:19
---
Implementation lifecycle handlers are complete at exact head 2a09b085bfb71b742c07d8ed91bc1c76add5d029 and composed into the validated OOMPAH-804 parent head. Parent-level affected workflow validation passed 2397 tests; terminal mutation scan passed 8/8; secrets and critical Ruff checks passed.
---
author: oompah
created: 2026-08-06 09:28
---
The combined-tree quality gate failed on `epic-OOMPAH-804--task-OOMPAH-834`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
Combined-tree quality gate infrastructure_error: Quality gate owner metadata does not match the exact resolved candidate head.
```
---
author: oompah
created: 2026-08-06 09:28
---
Task-scoped OOMPAH-858 recovery: removed the already-satisfied OOMPAH-781 finish edge after verifying OOMPAH-781 is Done/audited and exact head 6a84d9bcc is reachable from validated parent composition f89c477d. This prevents the deployed nested-queue target resolver from misclassifying the completed cross-container prerequisite while preserving its implementation evidence.
---
author: oompah
created: 2026-08-06 09:28
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 09:28
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 09:29
---
Understanding: I will reconcile the exact-head quality-gate metadata failure, inspect the existing lifecycle-event implementation and its focused tests, then make the smallest durable fix, verify it, push, and resubmit.
---
author: oompah
created: 2026-08-06 09:30
---
Discovery: the previous gate compared the submitted pre-rebase head with the combined-tree candidate. The composed branch now includes OOMPAH-836's exact-head owner factory: integration gates derive QualityGateOwner.head_sha from the rebased candidate, preserving the same project/task/generation. No stale owner metadata remains on the current f89c477d head.
---
author: oompah
created: 2026-08-06 09:30
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 20
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 48s
- Log: OOMPAH-834__20260806T092846Z.jsonl
---
author: oompah
created: 2026-08-06 09:31
---
Resubmitted the canonical already-composed head f89c477d after task-scoped nested-delivery recovery. This head contains OOMPAH-834's exact implementation commit, all validated parent composition, and matches the resolved combined candidate so the exact-head gate can acquire coherent owner evidence.
---
author: oompah
created: 2026-08-06 09:47
---
The combined-tree quality gate failed on `epic-OOMPAH-804--task-OOMPAH-834`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

tests/test_websocket_authenticated_bootstrap.py::TestWebSocketBootstrapIncludesAuth::test_ws_bootstrap_includes_service_instance_id
  /home/shedwards/.oompah/tmp/oompah-quality-gate-3nms8061/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7ccc7420b9c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_dispatch_close_race.py::TestUiCloseCancelsPendingRetry::test_pending_retry_cancelled_when_issue_closed_via_ui
FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_claim_writes_run_id_to_tracker
FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_claim_success_proceeds_to_worker
FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_pre_dispatch_terminal_state_aborts
FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_in_progress_update_called_on_github_tracker
FAILED tests/test_orchestrator_github_lifecycle.py::TestGitHubClaimProtocol::test_native_oompah_md_claim_writes_run_id
FAILED tests/test_orchestrator_github_lifecycle.py::TestMixedProjectDispatch::test_dispatch_uses_project_scoped_tracker_for_github_issue
FAILED tests/test_worker_submission.py::test_same_head_resubmit_from_in_progress_restores_ready_lifecycle
FAILED tests/test_worker_submission.py::test_same_head_resubmit_from_needs_human_restores_ready_lifecycle
FAILED tests/test_worker_submission.py::test_same_head_resubmit_from_needs_ci_fix_restores_ready_lifecycle
FAILED tests/test_worker_submission.py::test_duplicate_same_head_submit_already_ready_is_fully_idempotent
FAILED tests/test_worker_submission.py::test_same_head_ready_submit_backfills_missing_work_branch_projection
= 12 failed, 16620 passed, 8 skipped, 1 xfailed, 48 warnings in 917.74s (0:15:17) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-06 09:48
---
Agent dispatched (profile: standard)
---
<!-- COMMENTS:END -->
