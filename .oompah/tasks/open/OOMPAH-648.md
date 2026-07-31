---
id: OOMPAH-648
type: task
status: Open
priority: null
title: Keep live long-running tool calls from triggering agent stall termination
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:15:42.851609Z'
updated_at: '2026-07-31T07:16:13.924115Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a77d502a7a9d93979022d59c755b413ffda080824a6f76d3b30602f76263f18d
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e29821fc-d336-4975-bc4d-3cfea1353ae9
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T07:16:05.812176+00:00'
  claim_expires_at: '2026-07-31T07:46:05.812176+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: da5fd97a-6389-4596-b2eb-77876beb36f7
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
<!-- COMMENTS:END -->
