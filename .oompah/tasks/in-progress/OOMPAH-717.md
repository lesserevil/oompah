---
id: OOMPAH-717
type: task
status: In Progress
priority: null
title: Prevent generated hook collisions from hot-looping and starving epic integration
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-03T13:00:53.157839Z'
updated_at: '2026-08-03T13:38:43.707771Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d8ace93bf4e88a08c6506eeec48f53bb3de7feb3979aff430a84719b449ac79f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T13:01:42.096610+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** The task corpus contains no active task addressing\
    \ integration executor hot-looping, generated hook collisions, or queue starvation\
    \ issues. The closest completed tasks (OOMPAH-162, OOMPAH-163) address orthogonal\
    \ epic workflow problems. OOMPAH-717 is a distinct, previously untracked issue\
    \ specific to the integration queue and executor error handling.\nLooking at the\
    \ task corpus, I need to determine if OOMPAH-717 is a duplicate of any existing\
    \ active task.\n\n**Analysis:**\n\nOOMPAH-717 addresses a specific, compound problem:\n\
    1. Generated Oompah helpers (like `.oompah-no-hooks/prepare-commit-msg`) causing\
    \ untracked-file collisions during epic integration\n2. Error reporting masking\
    \ (successful checkout stderr hiding actual merge failures)\n3. Unbounded hot-looping\
    \ in the integration executor without backoff or attempt limits\n4. Starvation\
    \ of independent queue groups when one row repeatedly fails\n\nLet me examine\
    \ the task corpus for overlapping issues:\n\n**Reviewed Active/Terminal Tasks:**\n\
    - **OOMPAH-162** (Archived): Handles stacked epic children merged to default branch\u2014\
    orthogonal issue\n- **OOMPAH-163** (Archived): Validates epic target branches\
    \ through dispatch\u2014different validator problem\n- **OOMPAH-164-175** (All\
    \ Archived): Cover epic workflow standardization, release branches, documentation\u2014\
    not integration executor or queue health\n- **OOMPAH-10** (Archived): Native tracker\
    \ sync failures\u2014different component (markdown tracker, not integration)\n\
    - **OOMPAH-156-161** (All Archived): Error handling, task deduplication, API issues\u2014\
    not integration executor collision/retry logic\n\n**Conclusion:**\n\nNo active\
    \ (non-terminal) task covers the specific problem of:\n- Generated hook collisions\
    \ in shared epic worktrees causing executor failures\n- Error masking in integration\
    \ executor\n- Bounded retry/backoff for poisoned queue rows\n- Head-of-line protection\
    \ and queue health diagnostics\n\nAll related tasks are in terminal states (Archived/Merged).\
    \ OOMPAH-717 describes a genuinely new issue with no prior active task.\n\n---\n\
    \nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\n**Evidence:** The task corpus contains no active task addressing\
    \ integration executor hot-looping, generated hook collisions, or queue starvation\
    \ issues. The closest completed tasks (OOMPAH-162, OOMPAH-163) address orthogonal\
    \ epic"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 21384bd4-bc80-462b-b669-8252a3e55b73
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1538
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1538
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1538
    cost_usd: 0.0
    recorded_at: '2026-08-03T13:01:42.095113+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-717__20260803T130115Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-717
    source_sha: b97187abdd50d76deda75be427f26049fd396cb6
    completed_at: '2026-08-03T13:01:42.112362+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-717
  head_sha: 76526b08a14ad5a43ed137c2bc844594e3a1f733
  submitted_at: '2026-08-03T13:29:54.561971+00:00'
  updated_at: '2026-08-03T13:29:54.561971+00:00'
---
## Summary

Live reproduction: NODEVIRT-8 remained Ready to Integrate for more than 3,400 automatic attempts. Its task head tracks .oompah-no-hooks/prepare-commit-msg while the shared epic worktree contains the same Oompah-generated helper as an untracked file. The executor fast-forward therefore fails because the untracked helper would be overwritten. Error selection reports the successful checkout stderr (Already on epic-NODEVIRT-2) instead of the failing merge stderr, classifies the result as an epic-head race, and retries immediately without backoff or an attempt bound. Dependent Ready rows remain at attempts=0.

Implementation scope:
- Treat every Oompah-generated worktree helper path as non-deliverable at submission and integration boundaries, including legacy task heads that already track a helper. Reject with an actionable repair status or sanitize through an explicit safe repair path before mutating the shared epic branch.
- In the integration executor, report stderr from the command that actually failed; successful checkout output must never mask reset or merge failures.
- Distinguish genuine remote epic-head compare-and-swap races from deterministic local preparation/merge failures. Do not classify untracked-file collisions as immediately retryable epic-head races.
- Add bounded retry/backoff and head-of-line protection so one repeatedly failing row cannot hot-loop thousands of times or prevent independent eligible queue groups from progressing.
- Surface an alert/health diagnostic for excessive Ready attempts with the exact task, failing step, real error, next retry, and repair action.

Relevant code: oompah/integration_executor.py, oompah/integration_queue.py, oompah/orchestrator.py integration routing and queue health, ProjectStore generated-helper handling, and dashboard integration diagnostics.

Required tests:
- Reproduce a shared epic worktree with an untracked .oompah-no-hooks/prepare-commit-msg and a submitted task head that tracks that path; prove the real collision is reported and no immediate retry loop occurs.
- Prove successful checkout stderr cannot mask a failing reset or merge.
- Prove a genuine epic compare-and-swap race remains retryable.
- Prove a poisoned row is bounded/backed off and another independent eligible epic/project row advances.
- Prove clean task heads still integrate normally and generated helpers never enter delivered trees.

Acceptance criteria:
- The NODEVIRT-8 reproduction cannot exceed the configured retry budget or monopolize integration processing.
- Operators see the real untracked-file collision and a safe repair path.
- Independent Ready work proceeds while the failed row waits.
- Focused integration executor/queue/orchestrator/ProjectStore tests and make test pass.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 13:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 13:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 13:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 32s
- Log: OOMPAH-717__20260803T130115Z.jsonl
---
author: oompah
created: 2026-08-03 13:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 13:01
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 13:02
---
Understanding: the failure combines generated-helper paths entering submitted heads, masked subprocess errors, incorrect race classification, and an unbounded queue retry loop. I’ll trace ProjectStore, integration executor/queue, orchestrator health routing, and dashboard diagnostics; implement safe rejection/repair signaling, accurate errors, bounded backoff with fair scheduling, then add focused regression tests.
---
author: oompah
created: 2026-08-03 13:03
---
Discovery: ProjectStore installs .oompah-no-hooks/prepare-commit-msg in each worktree and the executor filters that path from dirty checks. A submitted commit can therefore track the helper unnoticed; the executor later resets/merges into an epic worktree containing the same untracked helper. The checkout/reset/merge failure path currently chooses checkout stderr first and returns epic_head_race for every failure. I’m tracing submission validation and queue routing before patching.
---
author: oompah
created: 2026-08-03 13:28
---
Implementation: added generated-helper detection at submission and integration boundaries, including legacy tracked helper paths; fixed executor failure-step/stderr reporting; separated deterministic checkout/reset/merge failures from retryable epic CAS races; added durable bounded exponential backoff with due-time queue claims and fair independent-row progress; added retry diagnostics and dashboard visibility with repair guidance. Added focused regression coverage across executor, queue, orchestrator, ProjectStore, submission, and dashboard paths.
---
author: oompah
created: 2026-08-03 13:29
---
Verification: focused executor/queue/orchestrator/ProjectStore/submission/dashboard suites passed, and the repository parallel gate completed with 15,097 passed, 7 skipped, 1 xfailed, and 45 warnings.  passed. The Makefile wrapper could not create its uv transient scope because the environment returned a DBus kernel-thread error; the same configured test runner completed successfully directly.
---
author: oompah
created: 2026-08-03 13:29
---
Completion: commit 76526b08a14ad5a43ed137c2bc844594e3a1f733 is pushed on origin/OOMPAH-717. Generated helpers are rejected with a safe git-rm repair path, integration failures retain the real failing stderr, CAS retries are bounded/backed off and fair, and diagnostics are visible in queue health/dashboard output. Focused suites and the 15,097-test parallel gate passed; branch is clean and up to date.
---
author: oompah
created: 2026-08-03 13:30
---
Bound generated-helper integration failures with safe rejection, accurate error diagnostics, durable capped backoff, and fair queue progress; added regression coverage and dashboard health details.
---
author: oompah
created: 2026-08-03 13:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 135
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 28m 13s
- Log: OOMPAH-717__20260803T130159Z.jsonl
---
author: oompah
created: 2026-08-03 13:37
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-717`
Target: `main`
Head: `76526b08a14ad5a43ed137c2bc844594e3a1f733`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
en::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-ldcgxt9z/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

tests/test_webhooks.py::TestCheckGhWebhookAvailable::test_gh_not_on_path_returns_false
  /home/shedwards/.oompah/tmp/oompah-quality-gate-ldcgxt9z/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x77cf4ae0b9c0>
  
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
FAILED tests/test_makefile_restart_wait.py::TestMakefileStructure::test_process_global_gate_keeps_preexisting_sentinel_alive@oompah_process_global
= 1 failed, 15095 passed, 8 skipped, 1 xfailed, 43 warnings in 418.81s (0:06:58) =

/home/shedwards/.oompah/tmp/oompah-quality-gate-ldcgxt9z/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x77cf4ae0b9c0>

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
created: 2026-08-03 13:38
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 13:38
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-03 13:38
---
Understanding: I am handling the post-gate CI failure on the existing OOMPAH-717 branch. I will retrieve the failing GitHub Actions output, reproduce the targeted Makefile structure test locally, apply the minimal stability fix with regression coverage, then commit, push, and resubmit.
---
<!-- COMMENTS:END -->
