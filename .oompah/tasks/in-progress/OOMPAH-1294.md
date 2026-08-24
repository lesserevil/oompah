---
id: OOMPAH-1294
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=bea7300764c2440fb9a40ec351cdea22
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:53:32.349118Z'
updated_at: '2026-08-24T07:11:19.874480Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
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
  task_fingerprint: 8da589b7377691fa54cc1cf0043a75bfd11d6c3c1f875d4d82f0eb75bb8f5219
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T16:43:34.280498+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: All 28 similarity candidates reviewed are in terminal\
    \ states (Merged, Done, or Archived). The error `Pre-provider contributor evidence\
    \ exceeded its bounded task-authority deadline` does not match any active open\
    \ issue in the corpus. The closest semantic matches (OOMPAH-1000 through OOMPAH-1014)\
    \ address terminal-audit workflow and epic validation issues\u2014distinctly different\
    \ from a task-authority deadline timeout in the orchestrator. OOMPAH-1294 appears\
    \ to be a novel error condition requiring new investigation and handling.\n# Duplicate\
    \ Investigation: OOMPAH-1294\n\nI'm analyzing OOMPAH-1294 to determine if it's\
    \ a duplicate of an existing active issue.\n\n## Analysis\n\n**Current Task:**\n\
    - OOMPAH-1294: `[backend:orchestrator] Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline`\n- Status: Open\n- Error: Auto-filed by\
    \ error_watcher for timeout in backend:orchestrator (timeout_seconds=5.0)\n\n\
    **Reviewed Candidates from Corpus:**\n\nI examined all 28 similarity candidates\
    \ provided in the corpus:\n\n1. **OOMPAH-1000 through OOMPAH-1014** (Merged/Done)\
    \ - Address terminal audit identity, workflow admission, epic validation, and\
    \ related workflow orchestration issues. These are completed systemic fixes from\
    \ August 2026.\n\n2. **OOMPAH-1015** (Merged) - `terminal-audit enforcement: pre_recovery_finalization_metadata_malformed`\
    \ - Different error class (metadata malformation, not task-authority deadline)\n\
    \n3. **OOMPAH-1016 through OOMPAH-1026** (Archived) - All duplicates of OOMPAH-1015\
    \ from a startup flood\n\n4. **OOMPAH-1098** (Archived) - Checkpoint queue flush\
    \ failure (different component)\n\n5. **OOMPAH-1, OOMPAH-10** (Archived) - Unrelated\
    \ CI and tracker sync issues\n\n**Key Finding:** All similarity candidates are\
    \ in terminal states (Merged, Done, or Archived). Per the screening rules, completed\
    \ tasks are historical context, not active duplicate targets.\n\n**Distinguishing\
    \ Features of OOMPAH-1294:**\n- Error specifically about \"Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline\"\n- Occurs during backend:orchestrator\
    \ operation\n- 5-second timeout specification\n- References OOMPAH-1199 and a\
    \ specific run_id\n- Appears to be a resource contention or deadline enforcement\
    \ issue distinct from the terminal-audit workflow issues\n\nNo active (Open/In\
    \ Progress) task in the corpus describes this same error pattern.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: All 28 similarity candidates reviewed are in terminal"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: b9deb2f9-f167-4dde-82eb-d91065e2dcb9
oompah.work_contributors:
  runs:
  - run_id: fe5f6b853aae415f8d9d3aa99f42732d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
  - run_id: 64060c1e6b564da6b9142d8ea126df97--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
  - run_id: c1eb4993d55546538a167e9a78fc6ee7--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
  - run_id: e3c9193421f648b9aac0e09d0196fdc5--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1294
    source_sha: c7b3911883a90c1b5805204a430926eb1c6f53b8
    completed_at: '2026-08-21T16:43:34.289289+00:00'
  - run_id: 3d75bf5587304b7f81678b2cdf560bd3--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
  - run_id: 3927b361c9864204befa02c147be99a7--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1294
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1803
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1803
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1803
    cost_usd: 0.0
    recorded_at: '2026-08-21T16:43:34.277808+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=bea7300764c2440fb9a40ec351cdea22 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1199 identifier=OOMPAH-1199 run_id=bea7300764c2440fb9a40ec351cdea22 timeout_seconds=5.0

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
- fingerprint: a3186e498005a50d
- dedup_fingerprint: a3186e498005a50d

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-1294__20260821T032348Z.jsonl
---
author: oompah
created: 2026-08-21 07:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:32
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 24s
- Log: OOMPAH-1294__20260821T073206Z.jsonl
---
author: oompah
created: 2026-08-21 11:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:41
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:42
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 48s
- Log: OOMPAH-1294__20260821T114207Z.jsonl
---
author: oompah
created: 2026-08-21 11:42
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1294/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 16:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 16:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 16:43
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 1s
- Log: OOMPAH-1294__20260821T164238Z.jsonl
---
author: oompah
created: 2026-08-23 23:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 23:32
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 23:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 28s
- Log: OOMPAH-1294__20260823T233215Z.jsonl
---
author: oompah
created: 2026-08-24 07:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 07:03
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 07:11
---
Understanding: error_watcher is auto-filing a backend:orchestrator log condition for pre-provider contributor evidence timeouts. Plan: verify existing suppression/handling for pre_provider_retirement; if missing, adjust error_watcher or orchestrator so this bounded deadline paths do not reach error_watcher, and add/extend tests to prevent regression.
---
<!-- COMMENTS:END -->
