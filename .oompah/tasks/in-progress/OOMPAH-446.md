---
id: OOMPAH-446
type: task
status: In Progress
priority: null
title: Kill CLI agent process trees when worker cancellation times out
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-26T03:12:30.119065Z'
updated_at: '2026-07-26T03:12:45.967631Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 75f13b97-0f60-41db-9bb3-5be189508954
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
<!-- COMMENTS:END -->
