---
id: OOMPAH-996
type: bug
status: Done
priority: 1
title: Do not return from AgentSession.stop before stderr transport retirement
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T12:43:02.225351Z'
updated_at: '2026-08-10T15:41:12.089332Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-93ede1e8847f
    project_id: proj-14849f1b
    task_id: OOMPAH-996
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c2d2af68429c921f643244189a70b961f59b093b1adf45771ab47402f94a4b6f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #798 merged as 2ab880be5 with exact OOMPAH-996 integration head bb8128258;
      parent OOMPAH-992 is authoritatively terminal and protected CI passed. Recording
      shared-child completion as Done because no separate parent review record exists.'
    created_at: '2026-08-10T15:41:05.516475+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-10 14:31
---
Residual stop-race repair is committed locally at exact integration head bb81282585fa91b1a88ae4409aaa58b99133482a. Root cause was an incomplete empty live-process snapshot being mistaken for proof of retirement, which skipped SIGKILL. The fix preserves snapshot completeness, escalates on uncertainty, partitions refresh/signal/observation deadlines, and adds deterministic incomplete-snapshot plus leak-safe fork coverage. Independent safety review approved. Focused evidence: Python 3.11 27 passed; Python 3.12 27 passed; original adversarial test 100/100 fresh-process runs; adjacent orchestrator 14 passed; process-global sentinel gate passed. Starting the exact full Makefile gate; head remains unpushed until it passes.
---
<!-- COMMENTS:END -->
