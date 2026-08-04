---
id: OOMPAH-507
type: bug
status: In Validation
priority: 1
title: Drain active agents before deployment restarts
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:07.476394Z'
updated_at: '2026-08-04T21:49:10.133329Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 043c813c-e0d1-459f-af02-6e7a329ab491
oompah.work_branch: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 146
  total_output_tokens: 6664
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 146
      output_tokens: 6664
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 6664
    cost_usd: 0.0
    recorded_at: '2026-07-28T17:48:45.090926+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f827c1e91924
    project_id: proj-14849f1b
    task_id: OOMPAH-507
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 859963d73184aecd00c8c97de76214d2bb41d3ed640dc354a768d7229c5ed4a8
    attempts:
    - version: 1
      attempt_id: attempt-c00c7d4c9d53
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 859963d73184aecd00c8c97de76214d2bb41d3ed640dc354a768d7229c5ed4a8
      created_at: '2026-08-04T21:41:36.344427+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:41:36.344427+00:00'
      branch_key: epic-OOMPAH-502
      ended_at: '2026-08-04T21:49:07.000107+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:28:34.036972+00:00'
    updated_at: '2026-08-04T21:41:36.344427+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-c00c7d4c9d53
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 859963d73184aecd00c8c97de76214d2bb41d3ed640dc354a768d7229c5ed4a8
    created_at: '2026-08-04T21:41:36.344427+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:41:36.344427+00:00'
    branch_key: epic-OOMPAH-502
    ended_at: '2026-08-04T21:49:07.000107+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
---
## Summary

Problem: make restart performs an immediate stop/start and terminates active agents. The recent deployment interrupted OOMPAH-456, orphaned its running entry, and forced a fresh agent to reread and recover work.

Implementation: make the normal Makefile restart path request the existing process-level graceful restart, pause dispatch, wait for active agents to finish, exec the updated process, and verify service health before returning. Add an environment-only configurable drain timeout with a safe long default. If the deadline expires, persist undrained task identities exactly once and re-dispatch them after restart as today. Provide an explicitly named emergency force-restart target for operators; do not silently fall back to killing agents when the healthy API is reachable. Preserve user pause state, PID/port handling, auto-update restarts, and Granian/Uvicorn behavior.

Tests: graceful-restart unit/integration tests for zero, one, and multiple running agents; completion during drain; timeout recovery deduplication; repeated restart requests; user-paused state; process exec/health wait; Makefile contract tests proving normal restart drains and force-restart is explicit. Update operator docs and AGENTS guidance.

Acceptance criteria: normal deployments do not terminate active agents; dispatch remains paused during drain; code changes are loaded after exec; timeout recovery is lossless and observable; emergency force restart remains available.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:34
---
Implemented and pushed in commit 8e9455a92. make restart now calls the drain API, waits up to the env-configured deadline, and verifies a new service_instance_id before success; make graceful aliases it, while make force-restart is the explicit interrupting path. Restart requests are atomically coalesced and expose drain state; existing timeout recovery and pause preservation remain intact. Focused API/orchestrator/Make/config tests: 180 passed.
---
author: oompah
created: 2026-07-28 15:34
---
Routine restarts drain active agents and health-check the re-exec; only force-restart interrupts work.
---
author: oompah
created: 2026-07-28 17:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 17:48
---
Duplicate Investigator: No duplicate found.

Investigation scope: Searched .oompah/tasks (open/archived/merged/backlog), docs/, plans/, and git log for tasks with keywords: graceful, drain, restart, agent-restart, active-agent, service, orchestrator, deployment.

Findings:
- OOMPAH-507 is a discrete child task under epic OOMPAH-502 (Reduce agent wall-clock latency without weakening delivery gates)
- Sequential sibling tasks verified (OOMPAH-506, OOMPAH-508, OOMPAH-517, OOMPAH-518) — all are follow-ups or prerequisites, not duplicates
- OOMPAH-518 explicitly references OOMPAH-507 as the source implementation it depends on (Fix the graceful restart shutdown path introduced under OOMPAH-507)
- No other tasks in the tracker cover 'graceful deployment restart with agent drain' functionality
- Implementation already completed in commit 7bce3acbd (feat: make normal restarts drain agents) per previous session

Conclusion: OOMPAH-507 is a unique, non-duplicate task with distinct scope within OOMPAH-502 epic. The implementation is complete and merged. Ready for next focus phase.
---
author: oompah
created: 2026-07-28 17:48
---
Agent completed successfully in 105s (6810 tokens)
---
author: oompah
created: 2026-07-28 17:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 58, Tool calls: 26
- Tokens: 146 in / 6.7K out [6.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 45s
- Log: OOMPAH-507__20260728T174706Z.jsonl
---
author: oompah
created: 2026-07-28 17:48
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 17:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 17:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 3
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 38s
- Log: OOMPAH-507__20260728T175310Z.jsonl
---
author: oompah
created: 2026-07-28 17:54
---
Restored after patch-equivalent commit 8e9455a92 was verified on the rebased epic branch; graceful draining restart remains fully implemented and live-validated.
---
author: oompah
created: 2026-08-04 18:28
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
