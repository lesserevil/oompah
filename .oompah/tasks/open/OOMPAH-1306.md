---
id: OOMPAH-1306
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1229 identifier=OOMPAH-1229 run_id=71d95951ec3d4994b2e05c931ec66ae6
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:17:21.518869Z'
updated_at: '2026-08-24T05:40:53.410372Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: af7608d604e6db1436c517a80f7a20bde57796c9a6cec3e26535b4cc411515e8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-23T22:59:54.185998+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The supplied corpus contains 28 similarity candidates\
    \ across 729 total indexed tasks. No active (non-terminal) task describes \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\" or addresses\
    \ orchestrator-level task-authority timeout enforcement. The three previous inconclusive\
    \ screenings suggest this is a distinct, previously unresolved issue. OOMPAH-1306\
    \ should proceed to active investigation as a new bug.\nI'll analyze OOMPAH-1306\
    \ against the supplied project task corpus to determine if it's a duplicate of\
    \ an existing issue.\n\n## Analysis\n\n**OOMPAH-1306 Details:**\n- Error: \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\"\n- Backend\
    \ component: `backend:orchestrator`\n- Related identifiers: issue_id=OOMPAH-1229,\
    \ timeout_seconds=5.0\n- Fingerprint: 7c3579b54223f860\n- Status: Open\n- Type:\
    \ Bug\n\n**Corpus Review:**\n\nI've examined all 28 similar candidate tasks provided.\
    \ The corpus includes:\n- **Terminal/completed tasks** (excluded per instructions):\
    \ OOMPAH-1, OOMPAH-10, OOMPAH-1000\u20131027 (all Merged or Archived)\n- **Active\
    \ tasks**: Only OOMPAH-1306 itself is Open\n\nThe completed tasks (OOMPAH-1000\u2013\
    1014) address systemic issues with:\n- Terminal audit validation and quality gates\n\
    - Epic workflow automation\n- Dependency resolution\n- Workflow admission and\
    \ publication\n- Terminal-audit metadata handling\n\n**None of these tasks describe\
    \ the specific error**: \"Pre-provider contributor evidence exceeded its bounded\
    \ task-authority deadline\" in the orchestrator backend.\n\nThe error pattern\
    \ in OOMPAH-1306 is distinct:\n- It's about provider contributor evidence timing\
    \ out against a 5-second deadline\n- It occurs in `backend:orchestrator` (not\
    \ `terminal_audit_enforcement` or other components)\n- The error references a\
    \ specific task authority boundary violation\n\nNo active non-terminal task in\
    \ the provided corpus matches this error signature or root cause.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: The supplied corpus contains 28 similarity candidates\
    \ across 729 total indexed tasks. No active (non-terminal) task describes \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\" or addresses\
    \ orchestrator-level task-authority timeout enforcement. The three previous inconclusive\
    \ screenings suggest this is a distinct, previously unresolved issue. OOMPAH-1306\
    \ should proceed to active"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: af026049-c45e-47ed-871b-45ca94efff2c
oompah.work_contributors:
  runs:
  - run_id: bb966e100ff34518893789fa8005a920--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1306
    source_sha: null
    completed_at: ''
  - run_id: 6dedddfb8d594677a3d919718aaf6349--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1306
    source_sha: null
    completed_at: ''
  - run_id: d6063f8cbc634f17b4bc6fa985bef0aa--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1306
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-23T22:59:54.238816+00:00'
  - run_id: 30d235b666564e639a6caeb36924e7c7--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1306
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1918
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1918
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1918
    cost_usd: 0.0
    recorded_at: '2026-08-23T22:59:54.185144+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1229 identifier=OOMPAH-1229 run_id=71d95951ec3d4994b2e05c931ec66ae6 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1229 identifier=OOMPAH-1229 run_id=71d95951ec3d4994b2e05c931ec66ae6 timeout_seconds=5.0

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 7c3579b54223f860
- dedup_fingerprint: 7c3579b54223f860

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:44
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 57s
- Log: OOMPAH-1306__20260821T034505Z.jsonl
---
author: oompah
created: 2026-08-21 08:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 08:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 08:06
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 32s
- Log: OOMPAH-1306__20260821T080638Z.jsonl
---
author: oompah
created: 2026-08-21 12:06
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 12:07
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 42s
---
author: oompah
created: 2026-08-21 12:07
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1306/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-23 22:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 22:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 22:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-1306__20260823T225850Z.jsonl
---
author: oompah
created: 2026-08-24 05:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 05:40
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
