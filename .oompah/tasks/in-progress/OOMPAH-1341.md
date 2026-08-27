---
id: OOMPAH-1341
type: bug
status: In Progress
priority: null
title: Run stalled-task watchdog in durable mode and reclaim obsolete review capacity
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T16:14:26.107948Z'
updated_at: '2026-08-27T23:48:46.364137Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 53c97af1-a34d-48a0-bba1-6f39470e2c09
  request_fingerprint: 7c75150ecd7ebbe7b82e77a19511afdc4a2f600598f07a13249a897ff135bd5c
oompah.lifecycle_revision: 2
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ef7b1fa56bec0f89af30e31d094f81565c59eb1844a6b48c19bf7b102854f65
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-27T23:37:03.328664+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1341 proposes a specific, unaddressed feature:\
    \ scheduling stalled-task watchdog from durable workflow tick and adding stale-review\
    \ cleanup maintenance. The 25 similarity candidates in the corpus\u2014while addressing\
    \ related workflow, terminal-audit, and lifecycle concerns\u2014all occupy terminal\
    \ states (Merged, Done, Archived) and describe distinct problems (epic auto-close,\
    \ restart liveness, terminal validation, audit churn). No active task duplicates\
    \ this exact scope. The closest historical predecessors are OOMPAH-1000\u2013\
    1012 (terminal audit infrastructure, now Merged), but they do not include watchdog\
    \ scheduling or review-capacity reclamation.\n# Duplicate Investigation Analysis\n\
    \nI am investigating whether OOMPAH-1341 is a duplicate of an existing active\
    \ task. Let me analyze the supplied project corpus systematically.\n\n## Methodology\n\
    \nI've reviewed all 25 similarity candidates in the provided corpus against the\
    \ current task OOMPAH-1341. The corpus is authoritative and self-sufficient per\
    \ the instructions.\n\n## Key Findings\n\n**OOMPAH-1341** describes:\n- Schedule\
    \ stalled-task watchdog from durable workflow tick through serialized maintenance\
    \ lane\n- Add stale-review cleanup job at same configurable interval  \n- Preserve\
    \ single-writer lifecycle contract\n- Expose results in public maintenance snapshot\n\
    \n**All peer tasks in corpus** (OOMPAH-1 through OOMPAH-1080, plus OOMPAH-1349):\n\
    - **Status distribution**: 1 Duplicate Candidate (1349), 1 Archived (1081), 19\
    \ Merged, 3 Done, rest Archived\n- **All 25 similarity candidates are in terminal\
    \ states** (Done, Merged, or Archived)\n- **Related but distinct scopes**:\n \
    \ - OOMPAH-1000 through OOMPAH-1012: Terminal audit, epic workflow, and restart\
    \ liveness fixes (all Merged/Done)\n  - OOMPAH-1072-1080: Error aggregation, owner\
    \ claims, audit churn (all Merged)\n  - None address stalled-task watchdog scheduling\
    \ or stale-review cleanup specifically\n\n## Exclusion of Terminal Tasks\n\nPer\
    \ instructions: \"Exclude every candidate in a terminal state (Done, Merged, or\
    \ Archived). A completed task is historical context, not an active duplicate target.\"\
    \n\n**All 25 candidates are terminal.** No active peer tasks remain to evaluate.\n\
    \n## Context\n\nTask comments indicate:\n- Direct owner was implementing this\
    \ feature as of 2026-08-26\n- Previous duplicate screening attempts occurred with\
    \ mixed results\n- The feature is a specific new addition (watchdog in durable\
    \ mode + stale-review cleanup), not a replication of existing work\n\n---\n\n\
    Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-1341 proposes a specific, unaddressed feature:\
    \ scheduling st"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a091d614-66dd-4745-9451-1179ad81f4c7
oompah.work_contributors:
  runs:
  - run_id: 03df9146d6884129819da23661f8aa41--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1341
    source_sha: null
    completed_at: ''
  - run_id: cd06a57ac06746bd8e83342cd593f10e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1341
    source_sha: 621a590246c3ea705814a2012daf55ff378db2a7
    completed_at: '2026-08-27T23:37:03.335509+00:00'
  - run_id: 77ad734515df480baeef1832500783c1--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: refactor
    source_branch: OOMPAH-1341
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1932
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1932
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1932
    cost_usd: 0.0
    recorded_at: '2026-08-27T23:37:03.326850+00:00'
---
## Summary

### Problem
The configured stalled-task watchdog never runs in production when WorkflowRuntime is installed: `_tick()` returns through `_run_durable_workflow_tick`, whose `_run_non_lifecycle_housekeeping` intentionally omits `_maybe_run_stalled_task_watchdog`. Therefore the 10-minute setting is inert and no `stalled_task_watchdog` maintenance result/log exists. Separately, stale conflicting open reviews remain on the forge and consume all review capacity (8/8), even when their patch is already represented on main or the owning task/review generation is obsolete.

### Scope
1. Schedule the existing stalled-task watchdog from the durable workflow tick through a serialized maintenance lane that retains TaskTransitionService authority and does not race workflow publication. Preserve the single-writer lifecycle contract; do not silently reintroduce legacy lifecycle sweeps.
2. Add a separate non-task-lifecycle stale-review cleanup maintenance job at the same configurable interval. It must use a fresh authoritative open-review listing and exact review detail/head/target facts. Close a review only when safely proven obsolete: exact reviewed head already contained in target; or all review commits are patch-equivalent to target (`git cherry` has no `+` commits); or exact task/review generation is superseded by a newer current review. Never close on title similarity, branch advancement alone, provider errors, missing head/target, cross-repository source, active durable review work, or stranded unique commits.
3. After successful close, release only the exact review-capacity reservation and reconcile capacity from a fresh successful listing. Close failure must preserve capacity.
4. Expose watchdog and stale-review-cleanup run state/results in the public maintenance snapshot and log unexpected maintenance-future failures promptly.

### Tests
- Durable runtime tick schedules watchdog remediation at configured interval and records public maintenance telemetry.
- Watchdog remains coalesced/interval-gated and uses authoritative transition service.
- Fresh provider listing failure closes nothing.
- Exact target-contained and patch-equivalent conflicted reviews close and release exact capacity.
- Unique commits, wrong target, missing head, ambiguous task mapping, active review work, and close failure fail closed.
- Public maintenance snapshot exposes both jobs/results.

### Acceptance Criteria
- Production server records a completed stalled_task_watchdog run every configured 600 seconds.
- Stalled tasks with decisive machine evidence are repaired automatically.
- Obsolete open reviews no longer leak review capacity; live unique reviews remain untouched.
- Dashboard review capacity reflects forge truth after cleanup.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 16:16
---
Direct owner: I am implementing this watchdog/review-capacity fix now and will carry it through tests, PR merge, deployment, and live verification. No separate agent dispatch is required.
---
author: oompah
created: 2026-08-27 16:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-27 16:09
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14s
---
author: oompah
created: 2026-08-27 16:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-27 16:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-27 16:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 15s
- Log: OOMPAH-1341__20260827T162632Z.jsonl
---
author: oompah
created: 2026-08-27 23:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-27 23:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-27 23:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 13s
- Log: OOMPAH-1341__20260827T233622Z.jsonl
---
author: oompah
created: 2026-08-27 23:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-27 23:48
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-27 23:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: OOMPAH-1341__20260827T234806Z.jsonl
---
<!-- COMMENTS:END -->
