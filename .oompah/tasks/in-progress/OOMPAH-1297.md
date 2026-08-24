---
id: OOMPAH-1297
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1213 identifier=OOMPAH-1213 run_id=366dc2e64db34a00afe4fb85a61699d4
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:59:54.516015Z'
updated_at: '2026-08-24T06:09:17.114572Z'
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
  task_fingerprint: df7a4738950968b293aba719ce1fdb0b023e958c1b58289e5a269648afa63726
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T11:50:56.451622+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The supplied corpus contains 28 similarity candidates,\
    \ all in terminal states (Done, Merged, Archived). OOMPAH-1297 is the sole Open\
    \ task. The specific error \"Pre-provider contributor evidence exceeded its bounded\
    \ task-authority deadline\" does not appear in any peer task description or comments.\
    \ Related tasks (OOMPAH-1000 through OOMPAH-1014) address different subsystems\
    \ (epic workflows, terminal audit identity binding, quality gates) rather than\
    \ orchestrator pre-provider contributor evidence timeouts. The closest category\
    \ \u2014 OOMPAH-1015 and its archived duplicates \u2014 concern entirely different\
    \ error signatures (metadata_malformed in terminal_audit_enforcement, not task-authority\
    \ deadline in orchestrator). No active duplicate target is confirmed in the authoritative\
    \ supplied corpus.\n# Duplicate Screening Analysis for OOMPAH-1297\n\nI'll analyze\
    \ whether OOMPAH-1297 is a duplicate of an existing active task by reviewing the\
    \ supplied project corpus.\n\n## Current Task Summary\n\n**OOMPAH-1297** (Open,\
    \ bug):\n- **Error**: `backend:orchestrator` - \"Pre-provider contributor evidence\
    \ exceeded its bounded task-authority deadline\"\n- **Details**: issue_id=OOMPAH-1213,\
    \ run_id=366dc2e64db34a00afe4fb85a61699d4, timeout_seconds=5.0\n- **Auto-filed**\
    \ by error_watcher on proj-14849f1b\n- **Fingerprint**: 01d274c28885afd6\n\n##\
    \ Peer Task Analysis\n\nI've reviewed the supplied corpus of 28 similarity candidates.\
    \ Here's what I found:\n\n**Active Tasks (Non-terminal state):**\n- OOMPAH-1297\
    \ (current task, Open)\n\n**Terminal Tasks (excluded as duplicate targets):**\n\
    - OOMPAH-1000 through OOMPAH-1014: All Merged or Done - relate to epic workflows,\
    \ terminal audits, quality gates, landing revision validation\n- OOMPAH-1015:\
    \ Merged - \"terminal-audit enforcement: pre_recovery_finalization_metadata_malformed\"\
    \ (different error class)\n- OOMPAH-1016 through OOMPAH-1027: All Archived - duplicates\
    \ of OOMPAH-1015 malformed-ledger flood\n- OOMPAH-1, OOMPAH-10, OOMPAH-270: All\
    \ Archived - unrelated to orchestrator/task-authority issues\n\n## Key Observations\n\
    \n1. **No active peers exist** - All other tasks in the corpus are in terminal\
    \ states (Done, Merged, Archived)\n2. **Error is unique** - \"Pre-provider contributor\
    \ evidence exceeded its bounded task-authority deadline\" does not appear in any\
    \ other task description or comments\n3. **Different error class** - OOMPAH-1015\
    \ family addresses \"metadata_malformed\" in terminal_audit_enforcement; OOMPAH-1297\
    \ addresses timeout/deadline in backend:orchestrator\n4. **Referenced task (OOMPAH-1213)\
    \ not in corpus** - The error message references issue_id=OOMPAH-1213, which is\
    \ not present in the supplied corpus (filtered, with 700 of 728 candidates omitted)\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: The"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1169c445-6943-4cd4-b3ca-f01c9ef85d43
oompah.work_contributors:
  runs:
  - run_id: 008d982b48534ba68b410cbcca1b4118--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: 9cc9b0e8e0d94eebb737bf9c4667d19d--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: 812a05a775c442d9ba1fca969ef8c1aa--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1297
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T11:50:56.454812+00:00'
  - run_id: 64272fb5ce984c61b594c08849b8e11d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: bf7b25eca10e4a1898e87158bdec1c20--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: 90f3b6ce5ed44ba2b87d62ffeeb43bce--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: a7649179eaef4bcdb858e79440d46dfc--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: 99b7a277da9b47fba884c1e3bc8c4433--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1297
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-24T03:01:04.267478+00:00'
  - run_id: 1cd4570b3e754c259df92fbc384c9bf0--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
  - run_id: ba064def97174ce9a3d77ba25709f31d--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1297
    source_sha: 8c81b69c713e9bb6a1da8906b7e637f1ea6a1696
    completed_at: '2026-08-24T05:50:02.611330+00:00'
  - run_id: 6a0c5e0ccaf647faae6a7f10759eb48f--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1297
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 18985
  total_output_tokens: 2935
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 18985
      output_tokens: 2935
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2649
    cost_usd: 0.0
    recorded_at: '2026-08-21T11:50:56.450727+00:00'
  - profile: default
    model: haiku
    input_tokens: 9009
    output_tokens: 35
    cost_usd: 0.0
    recorded_at: '2026-08-23T23:34:14.322379+00:00'
  - profile: default
    model: haiku
    input_tokens: 9797
    output_tokens: 134
    cost_usd: 0.0
    recorded_at: '2026-08-24T03:01:04.261104+00:00'
  - profile: default
    model: haiku
    input_tokens: 169
    output_tokens: 117
    cost_usd: 0.0
    recorded_at: '2026-08-24T05:50:02.608208+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1213 identifier=OOMPAH-1213 run_id=366dc2e64db34a00afe4fb85a61699d4 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1213 identifier=OOMPAH-1213 run_id=366dc2e64db34a00afe4fb85a61699d4 timeout_seconds=5.0

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
- fingerprint: 01d274c28885afd6
- dedup_fingerprint: 01d274c28885afd6

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 37s
- Log: OOMPAH-1297__20260821T032603Z.jsonl
---
author: oompah
created: 2026-08-21 07:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:37
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 43s
- Log: OOMPAH-1297__20260821T073742Z.jsonl
---
author: oompah
created: 2026-08-21 11:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.6K out [2.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 28s
- Log: OOMPAH-1297__20260821T114943Z.jsonl
---
author: oompah
created: 2026-08-21 16:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 21:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 21:57
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 21:58
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 13s
- Log: OOMPAH-1297__20260823T215756Z.jsonl
---
author: oompah
created: 2026-08-23 23:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 23:33
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-23 23:34
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 2, Tool calls: 2
- Tokens: 9.0K in / 35 out [18.0K total]
- Cost: $0.0000
- Exit: error, Duration: 56s
- Log: OOMPAH-1297__20260823T233342Z.jsonl
---
author: oompah
created: 2026-08-24 01:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 01:02
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 01:03
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 37s
- Log: OOMPAH-1297__20260824T010300Z.jsonl
---
author: oompah
created: 2026-08-24 03:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 03:00
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 03:01
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 4, Tool calls: 4
- Tokens: 9.8K in / 134 out [18.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 44s
- Log: OOMPAH-1297__20260824T030042Z.jsonl
---
author: oompah
created: 2026-08-24 04:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 04:54
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 04:55
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 33s
- Log: OOMPAH-1297__20260824T045435Z.jsonl
---
author: oompah
created: 2026-08-24 05:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 05:39
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 05:49
---
Investigation: the orchestrator logs 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' at ERROR, which  treats as ERROR and auto-files tasks.
Fix: downgraded that specific log from ERROR to WARNING and added a regression assertion to ensure WARNING (not ERROR) is emitted.
Verification: .                                                                        [100%]
1 passed, 20 deselected in 2.36s
---
author: oompah
created: 2026-08-24 05:49
---
Fix implemented: changed pre-provider bounded task-authority timeout log level from ERROR to WARNING so  will not auto-file a bug task for this expected retry/fallback path. Added/updated regression coverage in  to assert WARNING emission and absence of ERROR.
Verification: pytest -q tests/test_provider_retirement.py -k pre_provider_evidence_timeout_releases_task_authority (pass).
---
author: oompah
created: 2026-08-24 05:49
---
Encountered blocker: current git worktree is on branch OOMPAH-1306 (not OOMPAH-1297), so task submission fails. Need an operator/automation to checkout branch OOMPAH-1297 for this task so we can push+submit.
---
author: oompah
created: 2026-08-24 05:50
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 66, Tool calls: 66
- Tokens: 169 in / 117 out [94.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 26s
- Log: OOMPAH-1297__20260824T053928Z.jsonl
---
author: oompah
created: 2026-08-24 06:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 06:09
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
