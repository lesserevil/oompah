---
id: OOMPAH-996
type: bug
status: In Progress
priority: 1
title: Do not return from AgentSession.stop before stderr transport retirement
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T12:43:02.225351Z'
updated_at: '2026-08-10T13:47:12.542519Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-652

PR #798 Python 3.11 CI intermittently reproduced a lifecycle race in tests/test_agent.py::test_stop_kills_spawned_descendant: AgentSession.stop() killed the owned POSIX process group and returned while session._stderr_task was still pending. This regresses OOMPAH-652's intended atomic process/pipe retirement. Diagnose and fix oompah/agent.py::_join_process_transport so every normally retired owned process tree joins or boundedly cancels and awaits its stderr task and consumes its exception before returning, while preserving PID/start-time/session/process-group/workspace identity refusal and bounded shutdown. Cover concrete and alternate asyncio subprocess handle behavior, returncode callback timing, descendant-held EOF, SIGTERM, SIGKILL escalation, cancellation, stderr reader errors, and reused identity refusal. Tests must deterministically reproduce the early-return race and ensure no owned stderr task, pipe transport, process, or descendant survives stop. Run focused tests/test_agent.py, adjacent lifecycle suites, Python 3.11 verification, and the full Makefile gate. Acceptance: normal owned-tree retirement leaves _stderr_task done with its exception consumed, the exact process transport reaped, no pending-task/unraisable warning, bounded shutdown, and unchanged identity-safe refusal.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 12:43
---
Claimed directly for the active OOMPAH-989 integration branch after exact Python 3.11 CI reproduction in PR #798. Implementing and validating the lifecycle regression before rerunning CI.
---
author: oompah
created: 2026-08-10 13:47
---
Implementation and two independent adversarial reviews are complete on the shared OOMPAH-989 integration branch at exact local head 88bff3ad5a6d96b454a584a8a9078544f72c8e4e. Python 3.11/3.12 lifecycle and adjacent orchestrator termination suites pass; the replacement remains unpushed pending the exact full Makefile gate.
---
<!-- COMMENTS:END -->
