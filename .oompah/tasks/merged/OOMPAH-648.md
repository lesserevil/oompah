---
id: OOMPAH-648
type: task
status: Merged
priority: null
title: Keep live long-running tool calls from triggering agent stall termination
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:15:42.851609Z'
updated_at: '2026-07-31T18:18:08.214195Z'
work_branch: OOMPAH-648
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/614
review_number: '614'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a77d502a7a9d93979022d59c755b413ffda080824a6f76d3b30602f76263f18d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T07:17:57.313651+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I can now provide my duplicate\
    \ investigation verdict.\n\n## Investigation Summary\n\nI searched the entire\
    \ oompah task tracker for any existing tasks that might be duplicates of OOMPAH-648\
    \ (\"Keep live long-running tool calls from triggering agent stall termination\"\
    ):\n\n**Searches performed:**\n1. `.oompah/tasks/` across all states (open, backlog,\
    \ merged, archived) - 200+ tasks reviewed\n2. Pattern searches: `stall`, `timeout`,\
    \ `orchestrator`, `liveness`, `agent.*stall`, `long.*running`, `tool.*call`, `process.*tracking`,\
    \ `acp_tool_use`, `heartbeat`\n3. Project documentation: `docs/`, `plans/`, `README.md`,\
    \ `WORKFLOW.md`\n4. Source code: `oompah/` directory\n5. Referenced incident IDs\
    \ from the issue: OOMPAH-644, OOMPAH-645, OOMPAH-647\n\n**Relevant findings:**\n\
    - OOMPAH-171 (archived, status: Archived): About removing draft-epic lifecycle\
    \ \u2014 unrelated feature work, but notably this task itself *suffered* from\
    \ agent stall termination (\"Agent stalled 1 time(s) (3714s). Escalating from\
    \ 'default' to 'standard'\"), which is exactly the symptom OOMPAH-648 aims to\
    \ fix.\n- OOMPAH-281 (status: Open): Self-hosted GitHub Actions runner setup \u2014\
    \ unrelated to agent stall detection.\n- OOMPAH-282 (status: Backlog): Unicode\
    \ encoding error in state branch migration \u2014 unrelated to agent stall detection.\n\
    - No existing tasks found covering tool invocation tracking, command-specific\
    \ timeouts, process liveness detection, or distinguishing hung agents from live\
    \ tool calls.\n\n**Conclusion:** OOMPAH-648 is a fresh implementation task for\
    \ a previously unimplemented feature. No active duplicate exists.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: Exhaustively searched all .oompah/tasks directories\
    \ (200+ tasks), project docs, and source code for any existing tasks covering\
    \ agent stall supervision, tool invocation tracking, liveness heartbeats, process\
    \ supervision, or command-specific timeouts. Found none. OOM"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 308582af-d7cf-4a5c-a2ee-cddd09db635e
oompah.task_costs:
  total_input_tokens: 26033532
  total_output_tokens: 50485
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 26033499
      output_tokens: 45151
      cost_usd: 0.0
    unknown:
      input_tokens: 33
      output_tokens: 5334
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 4172
    cost_usd: 0.0
    recorded_at: '2026-07-31T07:17:57.310051+00:00'
  - profile: default
    model: haiku
    input_tokens: 26032987
    output_tokens: 40880
    cost_usd: 0.0
    recorded_at: '2026-07-31T07:43:25.379178+00:00'
  - profile: default
    model: haiku
    input_tokens: 366
    output_tokens: 99
    cost_usd: 0.0
    recorded_at: '2026-07-31T08:12:10.326412+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 5334
    cost_usd: 0.0
    recorded_at: '2026-07-31T08:38:11.031952+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-648__20260731T071619Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-648
    source_sha: 50625abed5be36e106dbd281871a2e464c671303
    completed_at: '2026-07-31T07:17:57.339371+00:00'
  - run_id: OOMPAH-648__20260731T071820Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: refactor
    source_branch: OOMPAH-648
    source_sha: ca51c22b90785daec5d4dd7f0e29dc22045957cc
    completed_at: '2026-07-31T07:43:25.383310+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-648
  head_sha: ca51c22b90785daec5d4dd7f0e29dc22045957cc
  submitted_at: '2026-07-31T08:11:51.578328+00:00'
  updated_at: '2026-07-31T08:11:51.578328+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/614
oompah.review_number: '614'
oompah.work_branch: OOMPAH-648
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-7d1427097e93: '2026-07-31T08:37:54.213561+00:00'
    no-auditor-audit-db48e6cb6d3e-2: '2026-07-31T09:01:23.248842+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-cb7445addbd3
    project_id: proj-14849f1b
    task_id: OOMPAH-648
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: 'PR #614 is merged at 8fd133e26; exact branch gate passed with 14,217
      tests; the first independent opus audit already recorded Audit PASS with safe
      merge/test evidence at 08:37. A duplicate audit was incorrectly dispatched after
      that pass and then exhausted candidates. Operator is applying the already-established
      successful verdict and clearing the duplicate-audit deadlock.'
    created_at: '2026-07-31T09:02:33.518649+00:00'
  - version: 1
    override_id: override-44e2b327e566
    project_id: proj-14849f1b
    task_id: OOMPAH-648
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bbbfa5c899c5ac3aaeb4f52b4bb73aa58cf5db653ad790a7f2f72c0cfaf5d8d6
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: PR 614 merged exact head ca51c22b90785daec5d4dd7f0e29dc22045957cc as 8fd133e26aa2823ab68cde2a42b446933142b614
      after a recorded passing terminal audit. This owner restage preserves the existing
      Merged lifecycle outcome while binding it to current evidence and retiring the
      obsolete pre-fix no-independent-candidate alert audit-db48e6cb6d3e.
    created_at: '2026-07-31T18:18:02.531977+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-648
    target_state: Merged
    evidence_fingerprint: bbbfa5c899c5ac3aaeb4f52b4bb73aa58cf5db653ad790a7f2f72c0cfaf5d8d6
    audit_ids:
    - audit-b23dd91dd27c
    - audit-db48e6cb6d3e
    - audit-e0a48441d5a8
    kind: override
    applied: true
    retired_at: '2026-07-31T18:18:07.434305+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b23dd91dd27c
    project_id: proj-14849f1b
    task_id: OOMPAH-648
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
    attempts:
    - version: 1
      attempt_id: attempt-7d1427097e93
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
      created_at: '2026-07-31T08:33:13.899055+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T08:33:13.899055+00:00'
      branch_key: OOMPAH-648
      verdict: pass
      completed_at: '2026-07-31T08:37:54.213364+00:00'
      ended_at: '2026-07-31T08:37:54.213364+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T08:24:09.754329+00:00'
    updated_at: '2026-07-31T08:37:54.213364+00:00'
  - version: 1
    audit_id: audit-db48e6cb6d3e
    project_id: proj-14849f1b
    task_id: OOMPAH-648
    target_state: Merged
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
    attempts:
    - version: 1
      attempt_id: attempt-7f82405190e5
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
      created_at: '2026-07-31T08:38:56.650288+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T08:38:56.650288+00:00'
      branch_key: OOMPAH-648
      ended_at: '2026-07-31T08:54:38.470566+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-6b1680cac785
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
      created_at: '2026-07-31T08:54:41.285755+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-07-31T08:54:41.285755+00:00'
      branch_key: OOMPAH-648
      candidate_rotation_count: 1
      ended_at: '2026-07-31T09:01:22.107199+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: no-auditor-audit-db48e6cb6d3e-2
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
      verdict: fail
      failure_classification: no_auditor
      created_at: '2026-07-31T09:01:23.248744+00:00'
      completed_at: '2026-07-31T09:01:23.248744+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T08:24:09.754329+00:00'
    updated_at: '2026-07-31T09:01:23.248744+00:00'
  - version: 1
    audit_id: audit-e0a48441d5a8
    project_id: proj-14849f1b
    task_id: OOMPAH-648
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bbbfa5c899c5ac3aaeb4f52b4bb73aa58cf5db653ad790a7f2f72c0cfaf5d8d6
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: api
    previous_state: In Validation
    created_at: '2026-07-31T18:17:59.081777+00:00'
    updated_at: '2026-07-31T18:18:07.434279+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7d1427097e93
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
    created_at: '2026-07-31T08:33:13.899055+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T08:33:13.899055+00:00'
    branch_key: OOMPAH-648
  - version: 1
    attempt_id: attempt-7f82405190e5
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
    created_at: '2026-07-31T08:38:56.650288+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T08:38:56.650288+00:00'
    branch_key: OOMPAH-648
    ended_at: '2026-07-31T08:54:38.470566+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-6b1680cac785
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94d808fab5ea8a54de74df6958de5dd299e0535df6df6303d3b4670f9700d25
    created_at: '2026-07-31T08:54:41.285755+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-07-31T08:54:41.285755+00:00'
    branch_key: OOMPAH-648
    candidate_rotation_count: 1
    ended_at: '2026-07-31T09:01:22.107199+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
---
## Summary

Live false-stall reproduction on 2026-07-31: OOMPAH-644 emitted acp_tool_use at 07:06:44 for 'python -m pytest -n 4 -q'; its pytest workers remained alive and consuming CPU, but no intermediate ACP event arrived, so the orchestrator logged Stall detected at 07:11:50 (elapsed 305331ms), failed to stop within 10s, terminated the worker, and retried it. OOMPAH-645 suffered the same sequence at 07:13:31 during its complete pytest run. Similar silent long commands contributed to auditor transport termination. Implementation scope: distinguish a hung agent from an active in-flight tool call/child process. Track tool invocation start/completion and liveness heartbeats from the ACP backend/process supervisor; while a bounded command is alive and showing process/IO/CPU liveness, use the configured command/agent deadline rather than the generic no-event stall threshold. If a tool truly exceeds its deadline, terminate it with a precise command-timeout diagnostic and preserve recoverable work. Never let an unbounded prompt/editor bypass the separate deadline protections in OOMPAH-647. Relevant files: orchestrator agent stall supervision, ACP event/session adapter, command process tracking, retry accounting, state/alerts, and tests. Required tests: deterministic silent command longer than five minutes remains active; live child process with no ACP events; exited/stuck child is still recovered; command-specific timeout; cancellation/restart; auditor and implementation isolation; no duplicate retry or worktree cleanup. Acceptance: full pytest/make gates can run longer than the generic event-stall threshold without killing a healthy worker, genuinely stuck commands still recover within configured bounds, focused agent-liveness tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 07:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 07:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 07:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 39, Tool calls: 17
- Tokens: 146 in / 4.2K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 49s
- Log: OOMPAH-648__20260731T071619Z.jsonl
---
author: oompah
created: 2026-07-31 07:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 07:18
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-31 07:43
---
Agent completed successfully in 1514s (26073867 tokens)
---
author: oompah
created: 2026-07-31 07:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 86
- Tokens: 26.0M in / 40.9K out [26.1M total]
- Cost: $0.0000
- Exit: normal, Duration: 25m 14s
- Log: OOMPAH-648__20260731T071820Z.jsonl
---
author: oompah
created: 2026-07-31 07:43
---
Agent completed without closing this issue (1514s (26073867 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-31 08:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:04
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-31 08:05
---
**Understanding & Previous Work Review**

A previous Refactoring Specialist agent completed significant implementation work (26M tokens). The changes implement tool liveness monitoring to distinguish live long-running tool calls from hung agents:

**Implementation Summary:**
- Created new `tool_liveness.py` module with `ToolLivenessMonitor` to track subprocess liveness per session
- Modified `orchestrator.py` to check tool liveness before triggering stall termination
- Updated `api_agent.py` to track and report subprocess progress
- Added comprehensive tests in `test_tool_liveness.py`

**Key Changes:**
- Tool invocations now register with start/deadline times
- Process liveness is tracked via subprocess.poll()
- Stall detection now defers for live bounded tools but still respects command-specific timeouts
- Generic stall threshold no longer kills healthy long-running commands

**Current Plan:**
1. Verify all tests pass
2. Check implementation meets acceptance criteria
3. Submit completed work

Starting verification now...
---
author: oompah
created: 2026-07-31 08:11
---
**Verification Complete**

Implementation successfully addresses all acceptance criteria:

✅ **Distinguished hung agent from active tool call:**
- ToolLivenessMonitor tracks subprocess.poll() for process liveness
- Dead child processes don't protect worker from recovery

✅ **Bounded command tracking:**
- _exec_run_command in api_agent.py registers invocations with timeout_s
- Process is attached immediately after subprocess.Popen()
- Graceful error handling ensures liveness never blocks command execution

✅ **Stall detection deferral:**
- Orchestrator._tool_stall_status() checks if a live bounded tool protects the session
- Generic stall threshold is bypassed while process.poll() returns None
- Tool deadline is honored independently

✅ **Timeout diagnostics:**
- Command-specific deadline produces precise 'command timed out after Xs' diagnostic
- Deadline-exceeded check prevents bypassing recovery

✅ **Test Coverage (11 tests):**
- Live silent commands protected past generic threshold ✓
- Exited child recovery with proper cleanup ✓
- Command-specific timeout enforcement ✓
- Process attachment and completion lifecycle ✓
- Concurrent command isolation ✓
- Executor timeout reporting ✓

✅ **All tests pass:**
- Full test suite: 14,217 passed, 7 skipped, 1 xfailed (no failures)
- Tool liveness tests: 11/11 passing
- Terminal mutation scan: passed
- No regressions detected

The implementation allows long-running commands (pytest, make gates) to complete without false stall termination while maintaining proper recovery for genuinely stuck processes.
---
author: oompah
created: 2026-07-31 08:11
---
Implemented tool liveness monitoring to prevent false stall termination of long-running tool calls. Added ToolLivenessMonitor to track subprocess liveness per session, modified orchestrator stall detection to defer for live bounded tools, and included 11 comprehensive tests covering silent commands, process tracking, timeouts, and recovery scenarios. All 14,217 tests pass with no regressions.
---
author: oompah
created: 2026-07-31 08:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 19
- Tokens: 366 in / 99 out [465 total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 58s
- Log: OOMPAH-648__20260731T080421Z.jsonl
---
author: oompah
created: 2026-07-31 08:16
---
Branch quality gate passed for `ca51c22b90785daec5d4dd7f0e29dc22045957cc` using `make test` in 264.5s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 08:24
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 08:24
---
YOLO: merged PR #614.
---
author: oompah
created: 2026-07-31 08:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 08:33
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 08:37
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merged_commit: ca51c22b9
- merge_commit: 8fd133e26
- pr: #614
- tool_liveness_tests: 11 passed in 1.47s
- focused_suites_passed: 430 tests (api_agent_budget/stall_to_dispatch_recovery/orchestrator_handlers/orchestrator_tick_telemetry)
- terminal_mutation_scanner: 15 passed
- branch_gate: make test passed in 264.5s per prior scheduler comment
- files_changed: oompah/tool_liveness.py (new, 165 lines), oompah/orchestrator.py (+136/-32 including _tool_stall_status), oompah/api_agent.py (+41), oompah/models.py (+3 LiveSession.tool_liveness), oompah/acp_agent.py (+5), oompah/acp_backends/base.py (+4), oompah/acp_backends/codex.py (+1), oompah/acp_backends/opencode.py (+1), oompah/acp_tools.py (+6), tests/test_tool_liveness.py (new, 231 lines)
---
author: oompah
created: 2026-07-31 08:38
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 34, Tool calls: 27
- Tokens: 33 in / 5.3K out [5.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 54s
- Log: OOMPAH-648__20260731T083320Z.jsonl
---
author: oompah
created: 2026-07-31 08:38
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 08:39
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 08:54
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-07-31 08:54
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 09:01
---
Needs Human — Merged audit requires operator input.

No independent auditor candidate is available for this audit (All eligible auditor candidates were already attempted for this audit.). Configure the `auditor` role with at least one healthy provider/model that is independent of the task contributors, then move the task back to Open to retry.
---
author: oompah
created: 2026-07-31 09:02
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: PR #614 is merged at 8fd133e26; exact branch gate passed with 14,217 tests; the first independent opus audit already recorded Audit PASS with safe merge/test evidence at 08:37. A duplicate audit was incorrectly dispatched after that pass and then exhausted candidates. Operator is applying the already-established successful verdict and clearing the duplicate-audit deadlock.
---
author: oompah
created: 2026-07-31 18:18
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: PR 614 merged exact head ca51c22b90785daec5d4dd7f0e29dc22045957cc as 8fd133e26aa2823ab68cde2a42b446933142b614 after a recorded passing terminal audit. This owner restage preserves the existing Merged lifecycle outcome while binding it to current evidence and retiring the obsolete pre-fix no-independent-candidate alert audit-db48e6cb6d3e.
---
<!-- COMMENTS:END -->
