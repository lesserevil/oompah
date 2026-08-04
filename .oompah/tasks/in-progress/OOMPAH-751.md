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
updated_at: '2026-08-04T01:52:15.592162Z'
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
oompah.agent_run_id: e2a3a69e-0639-424c-ada4-fba6ddda3e4e
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2110
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2110
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2110
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:49:57.184350+00:00'
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
<!-- COMMENTS:END -->
