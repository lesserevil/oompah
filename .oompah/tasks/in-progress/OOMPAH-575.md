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
updated_at: '2026-07-30T13:59:33.507507Z'
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
oompah.agent_run_id: c8332be3-4b98-43d0-af21-0b69eeff6438
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
author: oompah
created: 2026-07-30 13:52
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 13:52
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-30 13:59
---
Understanding: The issue is that Codex repair/development sessions need working scoped task-CLI auth. After code exploration, I found:

1. The CLI path (subscription billing) in codex.py DOES inject task_handoff_token into cli_env (lines 774-777). This part of the code looks correct.
2. The in-process SDK path (per_token billing) doesn't inject the token, but doesn't need it since oompah task commands are intercepted in-process via _exec_oompah_task_command_async.
3. The _issue_task_handoff_token in orchestrator.py correctly mints tokens with view/comment/submit/set-status/etc actions scoped to the exact project+task.

The missing pieces appear to be:
- Tests that prove a Codex CLI-session (subscription) agent can view, comment, and submit ONLY its assigned task via the CLI-provided env
- Tests that missing/expired tokens fail closed (return 401/403)
- Tests that unrelated tasks remain unauthorized
- Possibly a code gap: the in-process SDK path builds agent_env but never passes it anywhere useful

Security concerns: The code path looks correct but needs regression tests to prove the security boundary is enforced end-to-end.
---
<!-- COMMENTS:END -->
