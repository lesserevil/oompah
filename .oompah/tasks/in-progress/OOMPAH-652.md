---
id: OOMPAH-652
type: bug
status: In Progress
priority: 1
title: Isolate the full Makefile test gate from a running Oompah service
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-31T08:57:15.160957Z'
updated_at: '2026-07-31T09:51:38.791792Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4e4f47b3a25b1f1379996386bbd81b33cb3d94161e692fcd6f77703b77da69c3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T09:04:05.312656+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Searched `.oompah/tasks`, `docs/`, and `plans/`.\
    \ Read active tasks OOMPAH-281 and OOMPAH-282; neither concerns test process isolation.\
    \ Closest historical task OOMPAH-172 addressed global in-process state pollution,\
    \ not lifecycle cleanup, and is Archived. OOMPAH-6\u2019s running-service reference\
    \ concerns authentication and is also Archived. No repository files or tracker\
    \ state were modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: e0aaf53e-d450-4020-ac99-3c392be123a8
oompah.task_costs:
  total_input_tokens: 20730993
  total_output_tokens: 60215
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 20730993
      output_tokens: 60215
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 393798
    output_tokens: 3390
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:04:05.309783+00:00'
  - profile: default
    model: haiku
    input_tokens: 20337195
    output_tokens: 56825
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:38:33.332830+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-652__20260731T090248Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-652
    source_sha: 8fd133e26aa2823ab68cde2a42b446933142b614
    completed_at: '2026-07-31T09:04:05.328759+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-652
  head_sha: 6ef786631ee8b52c1b3138596a3dbbe04349868a
  submitted_at: '2026-07-31T09:44:05.059912+00:00'
  updated_at: '2026-07-31T09:44:05.059912+00:00'
---
## Summary

Live reproduction on 2026-07-31: make test was run in a task worktree while the local service instance from the canonical checkout was healthy on port 8090. During the process-lifecycle portion of the suite, that unrelated service received shutdown and exited cleanly, leaving oompah not running. The gate itself later completed, so this was test cleanup escaping its ownership boundary. Implementation scope: identify the exact test/fixture/process-discovery path that can signal a sibling live service, constrain lifecycle cleanup to subprocess identities created by that test (PID plus start time/process group/session and exact temporary workspace), and add a gate-level guard so tests cannot read or act on the canonical service PID file, port, or process group. Do not mask the issue by merely restarting after tests. Relevant areas include tests marked oompah_process_global, tests/test_agent.py workspace capture, Granian/lifespan fixtures, Makefile lifecycle helpers, pytest worker isolation, and process cleanup utilities. Required regression: start a sentinel Oompah-like listener/service in a separate session with a PID/start-time identity, execute the complete process-global lifecycle test group or make test in a separate worktree, and prove the sentinel stays alive and its port remains bound; also prove each test-owned descendant is still cleaned up. Acceptance: repeated full gates cannot signal or stop a pre-existing service, all test-owned processes are reaped, focused lifecycle tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 09:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:03
---
Second deterministic live reproduction: OOMPAH-649 quality gate ran python -m pytest tests/ under /home/shedwards/.oompah/worktrees/oompah/OOMPAH-649 (run.d4XOQV) while canonical service PID 3243032 was healthy in its own setsid session. Gate reached completion at about 09:00:19; immediately afterward make status reported not running, PID 3243032 was gone, no graceful shutdown lines were written, and the server could not persist the green gate callback/PR. Direct PR #615 was required to break the pass->kill->lost-callback->rerun deadlock. This strongly indicates a hard signal/cleanup escape at full-suite teardown, not ordinary application shutdown.
---
author: oompah
created: 2026-07-31 09:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 13
- Tokens: 393.8K in / 3.4K out [397.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 19s
- Log: OOMPAH-652__20260731T090248Z.jsonl
---
author: oompah
created: 2026-07-31 09:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 09:04
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-31 09:12
---
In-progress operator review finding: the current Makefile stop/status predicates run process_identity.py capture ... > , overwriting the identity recorded at startup before deciding whether to signal. That does not protect against PID reuse; a reused PID with a matching cwd would be blessed as new ownership. Preserve the startup meta atomically, add a compare/validate command that checks live pid/start_time/process_group/session/cwd against that exact stored record, and never rewrite it during stop/status. Tests should mutate each stored field and simulate a reused PID/current identity mismatch, asserting no signal and safe stale-file handling.
---
author: oompah
created: 2026-07-31 09:13
---
Correction/clarification: the current Makefile stop/status predicates run process_identity.py capture and redirect into PID_META_FILE, overwriting the identity recorded at startup before deciding whether to signal. That does not protect against PID reuse; a reused PID with a matching cwd would be blessed as new ownership. Preserve the startup meta atomically, add a compare/validate command that checks live pid/start_time/process_group/session/cwd against that exact stored record, and never rewrite it during stop/status. Tests should mutate each stored field and simulate a reused PID/current identity mismatch, asserting no signal and safe stale-file handling.
---
author: oompah
created: 2026-07-31 09:23
---
Additional live process-ownership evidence during the drain: OOMPAH-651 worker exited and the task left running state, but its full make test process group 3603400 (leader sh -c make test, bash run-tests, pytest controller, four workers; exact cwd OOMPAH-651) remained alive as a child group of the service. Because that rejected branch lacked gate isolation, the operator terminated only PGID 3603400 before teardown could stop the service. Include the invariant that worker completion/termination reaps every captured test/tool process group, even when the provider returns before the command, while never touching sibling service/group identities.
---
author: oompah
created: 2026-07-31 09:30
---
Operator takeover: the full gate completed and the pre-existing service remained healthy, but the provider process then exited without committing, pushing, submitting, or releasing the In Progress lease. This leaves a dirty tested worktree and blocks the graceful restart. Per the direct-recovery fallback, I am reviewing and packaging this exact worktree; no changes will be integrated without source review and focused verification.
---
author: oompah
created: 2026-07-31 09:38
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 167
- Tokens: 20.3M in / 56.8K out [20.4M total]
- Cost: $0.0000
- Exit: terminated, Duration: 34m 1s
- Log: OOMPAH-652__20260731T090435Z.jsonl
---
author: oompah
created: 2026-07-31 09:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 09:40
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-31 09:41
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-652 (Isolate the full Makefile test gate from a running Oompah service), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-31 09:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 11
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 12s
- Log: OOMPAH-652__20260731T094029Z.jsonl
---
author: oompah
created: 2026-07-31 09:43
---
Operator recovery complete on pushed head 6ef786631. Live evidence: the original complete 14,257-test gate exited while pre-existing service PID 3339192 remained healthy. Review then added normal provider-exit reaping, atomic/fail-closed lifecycle identity handling, pre-identity restart migration, and exact PID/start-time/group/session/cwd mismatch tests. Final verification: 96 focused process/lifecycle/worker-exit tests pass; 3 live orphan/timing regressions pass; Granian and sentinel tests passed in the preceding focused run; terminal mutation scan passes; git diff --check is clean. Submit this exact pushed head to Oompah full integration gating.
---
author: oompah
created: 2026-07-31 09:44
---
Isolated full gates from operator service state and added exact-identity cleanup for every test/worker subprocess lifecycle.
---
author: oompah
created: 2026-07-31 09:50
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-652`
Target: `main`
Head: `6ef786631ee8b52c1b3138596a3dbbe04349868a`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
syncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_orchestrator_handlers.py::TestRunStep5cEpicMaintenance::test_tick_skips_new_epic_maintenance_when_previous_still_running
= 1 failed, 14265 passed, 7 skipped, 1 xfailed, 55 warnings in 380.62s (0:06:20) =
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-652'

Using CPython 3.12.12
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate
Resolved 53 packages in 34ms
   Building oompah @ file:///home/shedwards/.oompah/worktrees/oompah/OOMPAH-652
      Built oompah @ file:///home/shedwards/.oompah/worktrees/oompah/OOMPAH-652
Prepared 1 package in 264ms
Installed 53 packages in 79ms
 + annotated-doc==0.0.5
 + annotated-types==0.8.0
 + anyio==4.14.2
 + attrs==26.1.0
 + babel==2.18.0
 + bcrypt==4.3.0
 + certifi==2026.7.22
 + cffi==2.1.0
 + click==8.4.2
 + cryptography==49.0.0
 + fastapi==0.141.1
 + h11==0.16.0
 + httpcore==1.0.9
 + httptools==0.8.0
 + httpx==0.28.1
 + httpx-sse==0.4.3
 + idna==3.18
 + jinja2==3.1.6
 + jsonschema==4.26.0
 + jsonschema-specifications==2025.9.1
 + markupsafe==3.0.3
 + mcp==1.29.0
 + oompah==0.1.0 (from file:///home/shedwards/.oompah/worktrees/oompah/OOMPAH-652)
 + passlib==1.7.4
 + pycparser==3.0
 + pydantic==2.13.4
 + pydantic-core==2.46.4
 + pydantic-settings==2.14.2
 + pyjwt==2.13.0
 + python-dateutil==2.9.0.post0
 + python-dotenv==1.2.2
 + python-liquid==2.3.0
 + python-multipart==0.0.32
 + pytz==2026.3.post1
 + pyyaml==6.0.3
 + referencing==0.37.0
 + rpds-py==2026.6.3
 + six==1.17.0
 + sse-starlette==3.4.6
 + starlette==1.3.1
 + tree-sitter==0.26.0
 + tree-sitter-javascript==0.25.0
 + tree-sitter-markdown==0.5.1
 + tree-sitter-python==0.25.0
 + tree-sitter-rust==0.24.2
 + tree-sitter-typescript==0.23.2
 + tree-sitter-yaml==0.7.2
 + typing-extensions==4.16.0
 + typing-inspection==0.4.2
 + uvicorn==0.52.0
 + uvloop==0.22.1
 + watchfiles==1.2.0
 + websockets==17.0
Resolved 74 packages in 47ms
   Building oompah @ file:///home/shedwards/.oompah/worktrees/oompah/OOMPAH-652
      Built oompah @ file:///home/shedwards/.oompah/worktrees/oompah/OOMPAH-652
Prepared 1 package in 245ms
Uninstalled 2 packages in 2ms
Installed 23 packages in 38ms
 + charset-normalizer==3.4.9
 + claude-agent-sdk==0.2.128
 + distro==1.9.0
 + execnet==2.1.2
 + granian==2.7.9
 + griffelib==2.1.0
 + iniconfig==2.3.0
 + jiter==0.16.0
 ~ oompah==0.1.0 (from file:///home/shedwards/.oompah/worktrees/oompah/OOMPAH-652)
 + openai==2.51.0
 + openai-agents==0.17.8
 + packaging==26.2
 + pluggy==1.6.0
 + pygments==2.20.0
 + pytest==9.1.1
 + pytest-asyncio==1.4.0
 + pytest-timeout==2.4.0
 + pytest-xdist==3.8.0
 + requests==2.34.2
 + sniffio==1.3.1
 + tqdm==4.70.0
 + urllib3==2.7.0
 - websockets==17.0
 + websockets==16.1.1
make[1]: *** [Makefile:295: test] Error 1
```
---
author: oompah
created: 2026-07-31 09:51
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 09:51
---
Focus: CI Failure Fixer
---
<!-- COMMENTS:END -->
