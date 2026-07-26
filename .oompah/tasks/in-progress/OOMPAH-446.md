---
id: OOMPAH-446
type: task
status: In Progress
priority: null
title: Kill CLI agent process trees when worker cancellation times out
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-26T03:12:30.119065Z'
updated_at: '2026-07-26T03:22:53.377460Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2541193c-8043-4992-bf40-a2f8602f559c
oompah.task_costs:
  total_input_tokens: 40
  total_output_tokens: 7347
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 40
      output_tokens: 7347
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 40
    output_tokens: 7347
    cost_usd: 0.0
    recorded_at: '2026-07-26T03:15:46.441706+00:00'
---
## Summary

Problem
A live EXOCOMP-47 Codex process tree remained on the host for more than 90 minutes after oompah recorded the run as terminated and removed it from the running snapshot. The surviving `codex exec` process continued driving an arm64 VM while `make status` reported running=0. This regresses OOMPAH-351: `Orchestrator._terminate_running` pops the runtime entry after a bounded worker-task wait, but when the worker ignores cancellation it does not independently stop the session; `CLIAgent.stop` also terminates only the immediate subprocess and does not establish/kill a POSIX process group.

Implementation
Update `oompah/orchestrator.py` and `oompah/agent.py` so forced termination always invokes a bounded session/process shutdown even when the worker task resists cancellation. Launch CLI agents in their own POSIX session/process group and send SIGTERM then SIGKILL to the entire group, with a safe non-POSIX fallback. Do not remove the runtime entry or clean its worktree until the termination attempt has run. Preserve bounded service shutdown and telemetry behavior.

Tests
Add regression coverage in the agent/orchestrator test suites using a cancellation-resistant worker plus a subprocess that spawns a child. Assert `_terminate_running` returns within its configured bound, the immediate process and descendant are gone, the runtime entry/claim are cleared, normal graceful completion is unchanged, and failures are observable without crashing shutdown. Run `make test`.

Acceptance criteria
- A run recorded as terminated has no surviving managed CLI process or descendants.
- Cancellation-resistant workers cannot block service shutdown.
- `make status` cannot report running=0 while the corresponding managed agent process tree remains alive.
- Existing graceful termination and cost/telemetry tests continue to pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-26 03:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 03:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-26 03:12
---
Understanding (Duplicate Investigator): Investigating OOMPAH-446 which describes a bug where CLI agent process trees survive after oompah records the run as terminated. The issue references OOMPAH-351 as a regression and requests changes to orchestrator.py and agent.py for POSIX process group management. My task is to confirm whether this is a duplicate of any existing task before implementation work begins. Searching now for similar tasks.
---
author: oompah
created: 2026-07-26 03:15
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-446 is NOT a duplicate of any existing task.

**Evidence searched:**
- All .oompah/tasks/ states (archived, backlog, done, merged, open) — 280+ tasks scanned
- Patterns: process.group, SIGKILL, SIGTERM, CLIAgent, _terminate_running, process.tree, orphan, setsid, setpgrp, agent.stop, subprocess.kill, worker.cancel
- Reviewed OOMPAH-351 (Merged) in full — the task explicitly referenced in the description
- Reviewed tasks OOMPAH-350 (scheduler isolation), OOMPAH-352 (stall diagnostics), and tasks 440–445 which are all recent merged tasks in unrelated areas

**Closest related task — confirmed distinct:**
- **OOMPAH-351** (Merged): 'Bound worker termination and service shutdown'. This task added OOMPAH_WORKER_TERMINATION_TIMEOUT_MS, bounded worker-cancel waits, and a forced-termination path. However, the delivered implementation only bounds the WAIT time for worker cancellation; it does NOT: (1) create a POSIX process group/session for CLIAgent subprocesses, (2) send SIGTERM/SIGKILL to the entire process tree, or (3) ensure the subprocess and all its descendants die independently of the worker coroutine's response to cancellation. OOMPAH-446 is a regression fix that addresses the remaining gap.

**Root cause (confirmed from description):** `Orchestrator._terminate_running` pops the runtime entry after a bounded worker-task wait (OOMPAH-351's contribution), but when the worker ignores cancellation it does not independently stop the session. `CLIAgent.stop` terminates only the immediate subprocess and does not establish or kill a POSIX process group. A process tree rooted at a `codex exec` child can therefore outlive oompah's accounting of it by 90+ minutes.

**Relevant files for implementation:**
- `oompah/orchestrator.py`: `_terminate_running` method — needs to call CLIAgent.stop (with process group kill) even when worker task ignores cancellation
- `oompah/agent.py`: `CLIAgent.stop` / subprocess launch — needs `start_new_session=True` or `os.setsid()` + `os.killpg(SIGTERM)` + `os.killpg(SIGKILL)` with a safe non-POSIX fallback
- `tests/test_orchestrator_terminated.py` or equivalent — regression tests per description

**Remaining work:** Full implementation as described in the task:
1. Modify CLIAgent subprocess launch to use `start_new_session=True` (creates a new POSIX session/process group)
2. Modify CLIAgent.stop to send SIGTERM to entire process group, wait briefly, then SIGKILL entire group; safe non-POSIX fallback when os.killpg unavailable
3. Modify `Orchestrator._terminate_running` to invoke CLIAgent.stop independently after the worker-cancel timeout, BEFORE popping the runtime entry
4. Tests: cancellation-resistant worker + subprocess with a child; assert returns within bound, process and descendants gone, runtime entry cleared, normal graceful path unchanged
5. Run make test

**Recommended next focus:** feature (backend implementation in orchestrator.py and agent.py)
---
author: oompah
created: 2026-07-26 03:15
---
Agent completed successfully in 183s (7387 tokens)
---
author: oompah
created: 2026-07-26 03:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 61, Tool calls: 37
- Tokens: 40 in / 7.3K out [7.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 3s
- Log: OOMPAH-446__20260726T031246Z.jsonl
---
author: oompah
created: 2026-07-26 03:15
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-26 03:15
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-26 03:15
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-26 03:16
---
Understanding: I will make CLI subprocess shutdown process-tree aware by creating a dedicated POSIX session, terminating its process group with bounded SIGTERM/SIGKILL escalation and a safe fallback, then ensure orchestrator forced termination invokes session shutdown before clearing runtime state. I will add agent and orchestrator regression tests for descendants, cancellation-resistant workers, failure observability, and unchanged graceful completion; then run make test, commit, push, and close the task.
---
author: oompah
created: 2026-07-26 03:22
---
Discovery: AgentSession.start in oompah/agent.py launches bash without a dedicated session, and stop() terminates/kills only the direct asyncio subprocess. The CLI worker keeps the live AgentSession only in a local variable; RunningEntry stores dashboard metadata, so _terminate_running cannot stop the process independently. It also pops state.running before cancelling, letting a resistant worker outlive accounting. I will register active CLI sessions on the orchestrator, mark forced terminations to suppress the worker-exit race, run worker cancellation and session shutdown concurrently within OOMPAH_WORKER_TERMINATION_TIMEOUT_MS, and pop/clean only afterward.
---
<!-- COMMENTS:END -->
