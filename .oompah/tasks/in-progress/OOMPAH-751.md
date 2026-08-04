---
id: OOMPAH-751
type: bug
status: In Progress
priority: 1
title: Do not poison task completion when advisory peer authorization changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T01:46:13.265163Z'
updated_at: '2026-08-04T02:05:50.222616Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2f733d40f8ef116556b2dfd652bf5659d4526315156e002142c846059300d610
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T01:49:57.194431+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-751 addresses a race condition in advisory peer\
    \ authorization during coordination message send that poisons task completion\
    \ by triggering HTTP 500 and handoff failure reconciliation. Searched all 34 included\
    \ corpus candidates: all are Archived (terminal state, excluded per instructions)\
    \ and cover unrelated domains (git sync, UI, release delivery, epic workflow,\
    \ GitHub API access, agent workflow). No active task duplicates OOMPAH-751's specific\
    \ scope: preventing HTTP 500 and completion poisoning when recipients transition\
    \ out of suggested-peer authorization mid-send. Referenced OOMPAH-689 (expected\
    \ peer denials) and OOMPAH-746 (trigger incident) do not appear in corpus to verify\
    \ status.\nI'm performing duplicate investigation for OOMPAH-751. Let me analyze\
    \ the task corpus carefully.\n\n**OOMPAH-751 Summary:**\nThis task addresses a\
    \ race condition where advisory peer authorization changes between peer discovery\
    \ and coordination message send. When OOMPAH-746 tried to send a coordination\
    \ message to OOMPAH-734, the recipient was no longer in the suggested-peer set.\
    \ The system raised PermissionError \u2192 HTTP 500, recorded a handoff failure,\
    \ and incorrectly moved the completed task to Needs Human. The issue requires\
    \ distinguishing between expected peer denials (OOMPAH-689 scope) and race-closed\
    \ coordination policy results.\n\n**Corpus Analysis:**\n\nReviewing all 34 included\
    \ similarity candidates:\n- **OOMPAH-10, 189, 190, 191, 204**: Native tracker\
    \ git sync errors (different issue domain)\n- **OOMPAH-157, 187, 209, 211**: Dashboard\
    \ UI and task comment delivery (unrelated)\n- **OOMPAH-158, 161, 165, 166, 168**:\
    \ Task tracking and epic workflow (unrelated)\n- **OOMPAH-175, 177, 178, 183,\
    \ 195, 201, 214, 215, 216**: Release delivery and branch management (unrelated)\n\
    - **OOMPAH-188, 210**: GitHub API permission errors (different surface, not about\
    \ peer authorization race)\n- **OOMPAH-203**: Auto-update service restart behavior\
    \ (unrelated)\n- **OOMPAH-207**: PR merge conflict (unrelated)\n- **OOMPAH-212**:\
    \ Duplicate task record deduplication (unrelated)\n- **OOMPAH-217, 218**: Agent\
    \ workflow and safety limits (unrelated)\n- **OOMPAH-1, 2, 100**: CI failures\
    \ or stale issues (unrelated)\n\n**Critical finding:** All 34 candidates are in\
    \ **Archived** status (terminal state). Per the instructions, completed tasks\
    \ are historical context, not active duplicate targets. No active peer-authorization-race\
    \ or coordination-send-failure task exists in the corpus besides OOMPAH-751 itself.\n\
    \nThe task references OOMPAH-689 as covering a related but distinct scenario (expected\
    \ read-only peer denials), and OOMPAH-746 as the trigger incident, but neither\
    \ appears in the corpus to evaluate.\n\n---\n\nFocus"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 658ae263-6b0a-4069-a73f-383da6f8b353
oompah.task_costs:
  total_input_tokens: 2536248
  total_output_tokens: 12916
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2536248
      output_tokens: 12916
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2110
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:49:57.184350+00:00'
  - profile: default
    model: haiku
    input_tokens: 2536238
    output_tokens: 10806
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:57:37.174297+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-751__20260804T014835Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-751
    source_sha: c54a60a63a1742fa0dfa4ad2a68f46cc61d87fdf
    completed_at: '2026-08-04T01:49:57.203109+00:00'
  - run_id: OOMPAH-751__20260804T015230Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-751
    source_sha: b3e9fc225f169222978c366fffae5d86a6314c58
    completed_at: '2026-08-04T01:57:37.215525+00:00'
---
## Summary

Triggered by: OOMPAH-746

Live reproduction: OOMPAH-746 completed and pushed repair head 3ed0f959, then sent an advisory coordination message to OOMPAH-734. Between peer discovery and send, the dynamic suggested-peer set no longer authorized that recipient. Orchestrator.coordination_send raised PermissionError, but the task-handoff endpoint converted it to HTTP 500, recorded an actionable handoff failure, and worker-exit reconciliation moved OOMPAH-746 to Needs Human before its own successful work could be submitted. OOMPAH-689 covers expected read-only peer denials, not this coordination-send race. Implementation scope: treat a recipient that is no longer suggested as an expected fail-closed coordination policy result rather than an assigned-task handoff or authentication failure; return a structured non-500 response; preserve the worker capability for its own comment and submit operations; and ensure optional coordination cannot poison successful completion. Either authorize against a stable peer grant or make send-time revalidation explicitly race-safe and idempotent. Preserve strict denial and non-disclosure for arbitrary recipients, cross-project sends, wrong or expired tokens, and mutations outside the granted task. Relevant code: task-handoff coordination-send handling in oompah/server.py, Orchestrator.coordination_send and peer derivation, task_handoff failure recording, worker-exit reconciliation, and auth-health classification. Required tests: peer suggested then removed before send; recipient transitions from running to Ready or In Review; durable fallback to a non-running still-authorized peer; arbitrary recipient; cross-project recipient; expired token; advisory send failure followed by successful own-task submit; restart and idempotency. Acceptance criteria: the race cannot return a generic 500, degrade worker auth health, prevent own-task submission, or move completed work to Needs Human; unauthorized disclosure and mutation remain impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 01:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 01:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 01:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 31s
- Log: OOMPAH-751__20260804T014835Z.jsonl
---
author: oompah
created: 2026-08-04 01:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 01:52
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-04 01:57
---
Agent completed successfully in 331s (2547044 tokens)
---
author: oompah
created: 2026-08-04 01:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 21
- Tokens: 2.5M in / 10.8K out [2.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 31s
- Log: OOMPAH-751__20260804T015230Z.jsonl
---
author: oompah
created: 2026-08-04 01:57
---
Agent completed without closing this issue (331s (2547044 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-08-04 01:58
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 01:58
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-04 01:59
---
Understanding: This docs focus will validate the existing OOMPAH-751 design note against the coordination-send endpoint and authorization code, keep the documentation concise and implementation-facing, then record a docs handoff because the required server behavior and regression tests must be completed by a code specialist.
---
author: oompah
created: 2026-08-04 02:00
---
Discovery:  re-derives suggested peers before  and raises  when the recipient is absent.  currently lets that reach its generic exception handler, which records an actionable handoff failure and returns HTTP 500. Peer derivation excludes only terminal states;  and  remain eligible when the graph/path relationship still authorizes them, and a non-running authorized recipient should use durable fallback.
---
author: oompah
created: 2026-08-04 02:01
---
Discovery correction: Orchestrator.coordination_send re-derives suggested peers before CoordinationStore.append and raises PermissionError when the recipient is absent. api_task_handoff currently lets that reach its generic exception handler, which records an actionable handoff failure and returns HTTP 500. Peer derivation excludes only terminal states; Ready to Integrate and In Review remain eligible when the graph/path relationship still authorizes them, and a non-running authorized recipient should use durable fallback.
---
author: oompah
created: 2026-08-04 02:02
---
Implementation (docs focus): Updated docs/scoped-task-cli-authentication.md and plans/advisory-coordination-send-races.md to define recipient-policy denials as structured, non-disclosing, non-actionable results; clarify authorization-before-storage and idempotency; and distinguish terminal peers from Ready to Integrate or In Review peers that remain eligible for durable fallback. Also documented that uncheckpointed live changed-path evidence may disappear when a worker exits.
---
author: oompah
created: 2026-08-04 02:03
---
Verification (docs focus): Focused coordination and task-handoff suites passed: 83 tests in tests/test_coordination.py, tests/test_server_coordination.py, and tests/test_task_handoff.py. git diff --check also passed. The first uv invocation was blocked before test collection by its systemd transient-scope launcher; rerunning with the available Python test runtime completed successfully.
---
author: oompah
created: 2026-08-04 02:05
---
Completion (docs focus): Delivered and pushed commit ef5f04049, completing the advisory coordination race contract and clarifying non-terminal durable fallback, terminal peer exclusion, non-disclosing policy denial, and authorization/idempotency ordering. The branch is clean and up to date with origin.
---
author: oompah
created: 2026-08-04 02:05
---
Focus handoff: docs

Outcome: Documentation contract is complete and pushed at ef5f04049 (building on b3e9fc225).

Evidence and decisions: Updated docs/scoped-task-cli-authentication.md and plans/advisory-coordination-send-races.md. Focused tests passed, 83 total across tests/test_coordination.py, tests/test_server_coordination.py, and tests/test_task_handoff.py; git diff --check and make check-secrets passed. Recipient-policy denials must be structured, non-disclosing, non-500, and non-actionable. Ready to Integrate and In Review remain non-terminal and use durable fallback while a graph or durable checkpoint still qualifies the peer; terminal peers are denied. Authorization precedes storage, so denied sends create no row and authorized idempotent retries return the original.

Remaining work and risks: Implement the server-side PermissionError handling before the generic task-handoff failure path; preserve token capability for own comment and submit; prevent auth-health and worker-exit poisoning; add the full lifecycle, arbitrary/cross-project, expired-token, completion, restart, and idempotency regression matrix. Security boundaries and non-disclosure require careful review.

Recommended next focus: security, covering the server/auth implementation and regression tests.
---
<!-- COMMENTS:END -->
