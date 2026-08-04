---
id: OOMPAH-807
type: task
status: In Progress
priority: null
title: Allow revisionless audits for metadata-only Archived dispositions
parent: OOMPAH-763
children: []
blocked_by:
- OOMPAH-806
- OOMPAH-814
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T21:29:59.448729Z'
updated_at: '2026-08-04T23:56:24.286716Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-807
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5d8823017faedc20e0c4fc8b58a6f30dc19338faf49501d69680a12207539d23
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T21:39:15.100094+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-763 is a broad parent epic, while OOMPAH-806 concerns\
    \ integration-gate watchdog fencing. Neither addresses revisionless metadata-only\
    \ Archived audits; all other reviewed candidates are terminal and excluded.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: OOMPAH-763 is a broad parent epic, while OOMPAH-806\
    \ concerns integration-gate watchdog fencing. Neither addresses revisionless metadata-only\
    \ Archived audits; all other reviewed candidates are terminal and excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a4884efc-7acb-465b-9568-22430c7d1458
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-807
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-807
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  updated_at: '2026-08-04T23:53:47.422313+00:00'
oompah.task_costs:
  total_input_tokens: 46207
  total_output_tokens: 292
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46207
      output_tokens: 292
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46207
    output_tokens: 292
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:39:15.097392+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-807__20260804T213742Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-807
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-04T21:39:15.159731+00:00'
---
## Summary

Bug reproduction: OOMPAH-803 is a Backlog metadata duplicate of OOMPAH-775 with a structured replacement source and no implementation branch. Requesting Archived correctly enters In Validation, but every terminal-audit attempt fails before launch with 'terminal audit evidence has no safely resolvable revision' after trying origin/OOMPAH-803. Implementation scope: separate code-bearing completion audits from metadata-only Archived dispositions; for duplicate/obsolete retirement, validate structured reason, source/replacement reference, no active owner/worker/retry/review, no unresolved children/dependencies, and unchanged task requirements without requiring or inventing a code revision/worktree. Preserve fail-closed immutable-revision rules for Done/Merged and code-bearing Archived paths. Relevant code: oompah/orchestrator.py _create_workspace_for_auditor, ArchivedEvidenceCollector/terminal coordinator and enforcement, audit launch/recovery projections. Required tests: revisionless Backlog duplicate with valid replacement archives; missing replacement/reason fails actionable; active work/review blocks; code-bearing immutable SHA remains fail-closed; restart/retry does not loop transport/launch failures; OOMPAH-803 regression. Acceptance: metadata-only Archived audits launch/finalize without a fake branch, unsafe retirement remains blocked, and audit health does not report revision resolution as a transport failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 21:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.2K in / 292 out [46.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 12s
- Log: OOMPAH-807__20260804T213742Z.jsonl
---
author: oompah
created: 2026-08-04 21:51
---
Direct-owner claim: terminal-audit backlog consumed the server's available dispatch lane while this audit-lifecycle repair remained runnable. OOMPAH-809 tracks the systemic capacity-starvation cause. Work will continue in the existing clean task worktree; no fake revision branch will be added as a product workaround.
---
author: oompah
created: 2026-08-04 22:11
---
Landing-order dependency added on OOMPAH-806. Its complete clean pushed/submitted head is 8322a4d19. Rebase this task branch onto that exact head now, resolve only the localized legitimate overlap, run combined 806+807 focused verification, then commit/push/submit. The queue must integrate 806 first; this task may carry the exact prerequisite ancestry while waiting.
---
author: oompah
created: 2026-08-04 22:39
---
Implemented revisionless terminal auditing for provably metadata-only Archived dispositions, while preserving immutable revision enforcement for code-bearing terminal targets. Added OOMPAH-803 regression coverage, non-Git attempt workspaces, fail-closed evidence preflight, and auditor prompt/source evidence. Verification: terminal mutation scan passed; 612 combined focused tests passed.
---
author: oompah
created: 2026-08-04 23:50
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-807`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
rnings for more info.

tests/test_webhooks.py::TestForwarderProcessFullLifecycle::test_process_start_and_immediate_exit
  /home/shedwards/.oompah/tmp/oompah-quality-gate-d2cwc5aj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x730353b9b9c0>
  
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
FAILED tests/test_submit_queue_concurrency.py::TestShouldDispatchOpenReviewGate::test_cap3_two_open_dispatches
= 1 failed, 15709 passed, 8 skipped, 1 xfailed, 42 warnings in 802.43s (0:13:22) =

/home/shedwards/.oompah/tmp/oompah-quality-gate-d2cwc5aj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:33: RuntimeWarning: coroutine 'sleep' was never awaited
  gc.collect()
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
/home/shedwards/.oompah/tmp/oompah-quality-gate-d2cwc5aj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7396e26b39c0>

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
make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-04 23:53
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-04 23:53
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 23:54
---
Understanding: I will inspect the existing revisionless Archived-audit implementation and its prior gate failure, isolate the submit-queue concurrency regression or integration drift, add focused coverage if a change is needed, then run the relevant checks, commit, push, and resubmit the exact branch head.
---
author: oompah
created: 2026-08-04 23:55
---
Discovery: the reported submit-queue assertion is not reproducible on the exact branch head. It passes in isolation and the full 61-test submit-queue module passes under the same four-worker gate harness. The OOMPAH-806 internal-gate guard is not implicated because this fixture has no blocked integration record. I will now run the configured full gate on the clean submitted head.
---
<!-- COMMENTS:END -->
