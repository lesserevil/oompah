---
id: OOMPAH-575
type: task
status: In Progress
priority: null
title: Propagate scoped task CLI auth to Codex agent sessions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:15:25.255613Z'
updated_at: '2026-07-30T13:51:40.090890Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 161ed12e153fe52f6201c32494aa9699b3e730445a34d9fc929cf8f3982e45d4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T13:34:22.411780+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Reviewed active OOMPAH-281 and OOMPAH-282 plus\
    \ closest terminal tasks OOMPAH-186, OOMPAH-211, OOMPAH-217, and OOMPAH-6; none\
    \ cover scoped task-CLI authentication propagation to Codex sessions."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 9d2c2b07-5576-45a7-b607-6f6fee3ca27a
oompah.task_costs:
  total_input_tokens: 642758
  total_output_tokens: 3111
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 642758
      output_tokens: 3111
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 642758
    output_tokens: 3111
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:34:22.410428+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-575__20260730T133259Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-575
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T13:34:22.420413+00:00'
---
## Summary

Implementation scope

Ensure service-launched Codex repair/development sessions receive working scoped task-CLI authentication for their assigned project/task. A repair session for OOMPAH-479 could use its repository tools but plain `oompah task view` returned HTTP 401, while the operator shell and MCP-backed session were authenticated. Trace task-handoff credential creation and environment propagation through the Codex ACP launch path; preserve least-privilege assignment scoping and avoid exposing server-wide credentials. Relevant files include oompah/task_handoff.py, oompah/acp_backends/codex.py, oompah/acp_session.py, and server/orchestrator launch wiring.

Tests

Add a Codex-session regression proving an assigned agent can view, comment on, and submit only its assigned task using the CLI-provided environment; assert missing/expired tokens fail closed and unrelated tasks remain unauthorized. Run focused task-handoff/ACP tests and the configured full Makefile gate.

Acceptance criteria

A service-launched Codex agent can execute the documented `oompah task` workflow for its own assigned task without operator credentials, receives no broader tracker authority, and no 401 occurs in the normal launch path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:32
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:32
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 13:34
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 12
- Tokens: 642.8K in / 3.1K out [645.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 27s
- Log: OOMPAH-575__20260730T133259Z.jsonl
---
author: oompah
created: 2026-07-30 13:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 13:34
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-30 13:51
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 68
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 59s
- Log: OOMPAH-575__20260730T133445Z.jsonl
---
<!-- COMMENTS:END -->
