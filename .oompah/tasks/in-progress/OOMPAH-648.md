---
id: OOMPAH-648
type: task
status: In Progress
priority: null
title: Keep live long-running tool calls from triggering agent stall termination
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:15:42.851609Z'
updated_at: '2026-07-31T08:04:13.852931Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
  total_input_tokens: 26033133
  total_output_tokens: 45052
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 26033133
      output_tokens: 45052
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
<!-- COMMENTS:END -->
