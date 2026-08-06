---
id: OOMPAH-831
type: task
status: Needs CI Fix
priority: null
title: Make terminal-auditor search and safe inspection fallbacks match their advertised
  contract
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-05T15:44:15.632077Z'
updated_at: '2026-08-06T04:10:00.659178Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-831
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a081abf145f75b1cf5e229bc0b6d45d9cbd4c8147858bc305a945fc0c84af47a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate screening worker was terminated.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: '2026-08-05T18:57:18.936937+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-831
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-831
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  head_sha: 93b0295bcf533d129eb8568ede120e2ad3944066
  submitted_at: '2026-08-06T03:13:01.483750+00:00'
  updated_at: '2026-08-06T04:09:53.496195+00:00'
  last_error: "Combined-tree quality gate failed:  get traceback where the object\
    \ was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n\ntests/test_webhooks.py::TestWebhookForwarderHookCleanup::test_cleanup_transient_inspection_failure_does_not_block_launch\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-1bw1pckj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x785bada039c0>\n  \n  Traceback (most recent call last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
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
    \ short test summary info ============================\nFAILED tests/test_dispatch_lane_contract.py::TestDispatchLockExceptionSafety::test_second_dispatch_succeeds_after_first_raises\n\
    FAILED tests/test_epic_strategy.py::TestOpenEpicMainPrs::test_existing_pr_waits_for_changed_head_quality_gate\n\
    = 2 failed, 16085 passed, 8 skipped, 1 xfailed, 45 warnings in 1041.52s (0:17:21)\
    \ =\n\n/home/shedwards/.oompah/tmp/oompah-quality-gate-1bw1pckj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x7e00d0c039c0>\n\nTraceback (most recent call last):\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 126, in __del__\n    self.close()\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 104, in close\n    proto.pipe.close()\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 568, in close\n    self._close(None)\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 592, in _close\n    self._loop.call_soon(self._call_connection_lost, exc)\n\
    \  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n    self._check_closed()\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n    raise RuntimeError('Event loop is closed')\n\
    RuntimeError: Event loop is closed\n\nEnable tracemalloc to get traceback where\
    \ the object was allocated.\nSee https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n  warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    make: *** [Makefile:401: test] Error 1\n"
---
## Summary

Triggered by OOMPAH-542 Archived-audit attempts logged at 2026-08-05T15:25:51Z and 2026-08-05T15:29:47Z.

The terminal-auditor prompt directs candidates away from shell pipelines toward search_files and bounded read_file, but the exposed tool contract is internally inconsistent. search_files advertises Python regular expressions while executing GNU basic grep syntax, so alternation, \\s, and similar documented patterns silently return no matches. Search results identify line numbers while bounded reads require character offsets, leaving no reliable supported path from a match to surrounding source. When candidates fall back to safe repository inspection, unsupported git ls-tree is classified as fatal rather than an unexecuted recoverable read-only request. OOMPAH-542 consequently rotated two healthy candidates without producing a code verdict.

Implementation scope:
- Make search_files semantics match the advertised Python-regex contract across every ACP backend, or change the contract and implementation together to one precisely documented syntax.
- Preserve workspace containment, include filtering, bounded output, binary handling, invalid-pattern errors, and timeout/resource bounds.
- Provide a supported bounded continuation from a search match to surrounding source, such as context-bearing search results or line-addressable bounded reads.
- Classify demonstrably read-only git ls-tree inspection as allowed or recoverable without consuming the fatal denial budget. Validate flags, revision operands, --, and workspace-relative paths fail-closed.
- Keep arbitrary python -c, output redirection, credential access, path escape, process control, and state-changing git fatal.
- Keep policy incompatibility distinct from provider transport failure.

Required tests:
- Python-regex alternation and ^\\s{4}def patterns find expected source through all auditor tool catalogs.
- Invalid regex, include filtering, large output, binary files, and workspace escape remain bounded and safe.
- A returned match can be inspected with bounded context without shell commands.
- Replay the three OOMPAH-542 git ls-tree forms; none invokes the fatal-denial callback or rotates the candidate.
- Replay the supported search/read path through accepted submit_audit_result.
- Repeated arbitrary python -c, mutation, redirects, and state-changing git still consume the fatal budget and rotate safely.
- Recoverable inspection mismatches do not raise transport or policy-incompatibility health alerts.

Acceptance criteria:
- An OOMPAH-542-style auditor can locate and inspect _watchdog_stale_completed and submit a verdict with one healthy candidate using only advertised tools.
- Tool descriptions and execution semantics agree across supported backends.
- No write-capable or arbitrary-code command is newly admitted.
- Focused auditor, ACP-tool, provider-retirement, terminal-audit-health, and output-bounds suites plus the configured full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 15:50
---
Additional live evidence from OOMPAH-815 Done audit attempt attempt-6259cc99f102: read-only `git ls-remote origin <two branch names>` and local `git for-each-ref --format=... refs/remotes/origin/` each received the generic fatal policy denial and consumed two of three denial slots. The auditor recovered with `git branch -r` plus `git rev-parse`, so its audit remains live. Extend the safe/recoverable git inspection classification matrix beyond ls-tree to these forms where containment/network policy permits; unsupported read-only forms must return the stable recoverable marker rather than consume fatal mutation budget.
---
author: oompah
created: 2026-08-05 15:53
---
OOMPAH-815 attempt #1 was then terminated when safe `wc -l oompah/projects.py` became its third fatal denial, after `git ls-remote` and `git for-each-ref`; the intervening awk/sed mismatches were correctly recoverable. This confirms the bug is not one git subcommand: any demonstrably read-only inspection outside the allowlist needs either a supported catalog operation or the stable non-budget-consuming recoverable response. Preserve fatal handling for ambiguous/arbitrary execution.
---
author: oompah
created: 2026-08-05 18:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 18:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 41s
- Log: OOMPAH-831__20260805T183157Z.jsonl
---
author: oompah
created: 2026-08-05 18:57
---
Scheduler authority was revoked after verifying the worktree was clean: this duplicate-screening Codex provider bootstrap was queued as a heavyweight validation waiter due OOMPAH-841. The waiter is removed and no implementation was discarded. Resume normal dispatch only after standalone deployment OOMPAH-842 is live.
---
author: oompah
created: 2026-08-06 01:54
---
Direct-owner implementation is complete locally at exact restacked head 93b0295bcf533d129eb8568ede120e2ad3944066 on OOMPAH-840 parent 93cc4c856. Independent review caught and the follow-up commit fixed a fail-closed ordering bug: path-escape and credential-like operands are now checked before recoverable read-only recognition, with explicit ls-remote/for-each-ref regressions. The full focused auditor/ACP/provider/terminal-health matrix passes 435 tests; compileall, diff, and secret checks pass. Holding push/submission until the active OOMPAH-791 critical gate and OOMPAH-840 parent audit settle, so this work does not compete for the single full-gate lane.
---
author: oompah
created: 2026-08-06 03:13
---
Direct implementation complete at exact head 93b0295bcf533d129eb8568ede120e2ad3944066. The ordered commits are f3b8326ed (inspection/search contract) followed by 93b0295bc (security fence: credential/path escape denials remain fatal before recoverable git fallbacks). Verification: 435 focused auditor/ACP/authority/provider/terminal-audit/project-tool tests passed; py_compile, git diff --check, and make check-secrets passed. Independent re-review found no blockers. OOMPAH-843 must be replayed after this exact sequence rather than replacing these fences.
---
author: oompah
created: 2026-08-06 03:13
---
Align terminal-auditor search and safe inspection fallbacks with the advertised contract while preserving fatal credential/path escape fences; 435 focused tests and independent review pass at 93b0295bc.
---
author: oompah
created: 2026-08-06 03:39
---
Withdrawing the just-started exact gate before the scheduled graceful cutover's remaining drain budget expires. This is deployment coordination, not a code/test failure: exact head 93b0295bcf533d129eb8568ede120e2ad3944066 remains clean, pushed, focused-green, and independently accepted. Resubmit unchanged after the current-main restart is healthy.
---
author: oompah
created: 2026-08-06 03:43
---
Current-main restart is healthy at fe6257b and the deployment-coordination withdrawal is complete. Resubmitting the unchanged, clean, pushed exact head 93b0295bcf533d129eb8568ede120e2ad3944066 with its existing 435 focused-test and independent-review evidence.
---
author: oompah
created: 2026-08-06 03:43
---
Resubmit unchanged accepted auditor inspection/security head 93b0295bc after the scheduled cutover; 435 focused tests and independent review remain green.
---
author: oompah
created: 2026-08-06 04:10
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-831`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
 get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_webhooks.py::TestWebhookForwarderHookCleanup::test_cleanup_transient_inspection_failure_does_not_block_launch
  /home/shedwards/.oompah/tmp/oompah-quality-gate-1bw1pckj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x785bada039c0>
  
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
FAILED tests/test_dispatch_lane_contract.py::TestDispatchLockExceptionSafety::test_second_dispatch_succeeds_after_first_raises
FAILED tests/test_epic_strategy.py::TestOpenEpicMainPrs::test_existing_pr_waits_for_changed_head_quality_gate
= 2 failed, 16085 passed, 8 skipped, 1 xfailed, 45 warnings in 1041.52s (0:17:21) =

/home/shedwards/.oompah/tmp/oompah-quality-gate-1bw1pckj/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7e00d0c039c0>

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
<!-- COMMENTS:END -->
