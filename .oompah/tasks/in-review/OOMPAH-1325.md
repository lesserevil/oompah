---
id: OOMPAH-1325
type: bug
status: In Review
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1307 identifier=OOMPAH-1307 run_id=cf289f342ff8435d925bd789c13b1e6d
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T08:06:24.549306Z'
updated_at: '2026-08-25T22:36:56.454173Z'
work_branch: OOMPAH-1325
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/911
review_number: '911'
review_head: fa6cffbc078a591a2df05fbf674ed34c0e7ad1e8
merged_at: null
oompah.lifecycle_revision: 4
oompah.last_batch:
  batch_id: batch-406b98cf5aef4911b932a9c5924b23e6
  actor: shedwards
  committed_at: '2026-08-24T02:44:47.015459Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7b6c82d765a10bddd8fcc4f872fec36ce04599ca941e22b853d2d19aeea3446e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-24T07:37:53.771409+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    # Duplicate Investigation: OOMPAH-1325\n\nI'll systematically review the task\
    \ corpus to determine whether OOMPAH-1325 is a duplicate of an existing task.\n\
    \n## Current Issue Summary\n\n**OOMPAH-1325** reports:\n- Error from `backend:orchestrator`:\
    \ \"Pre-provider contributor evidence exceeded its bounded task-authority deadline\"\
    \n- Specific context: issue_id=OOMPAH-1307, timeout_seconds=30.0\n- Auto-filed\
    \ by `error_watcher` on proj-14849f1b\n- Status: Open (active task)\n\n## Task\
    \ Corpus Review\n\n### Active Tasks (Non-Terminal Status)\nScanning for Open,\
    \ In Progress, or other non-terminal tasks:\n- **OOMPAH-1325** (current task,\
    \ status: Open) \u2014 no peers in Open status\n\n### Terminal Tasks Reviewed\
    \ (Excluded as Duplicate Targets)\nAll other tasks in the corpus are in terminal\
    \ states (Done, Merged, or Archived):\n- OOMPAH-1 through OOMPAH-10: Archived/Archived\n\
    - OOMPAH-1000 through OOMPAH-1027: Merged/Done/Archived\n- OOMPAH-164: Archived\n\
    \n### Candidate Analysis\n\n**OOMPAH-1015** (most similar in form):\n- Also auto-filed\
    \ by `error_watcher` on same project (proj-14849f1b)\n- Status: **Merged** (terminal\
    \ \u2014 excluded as duplicate target)\n- Error from `backend:terminal_audit_enforcement`\
    \ (not orchestrator)\n- Different error: \"pre_recovery_finalization_metadata_malformed:OOMPAH-415\"\
    \n- Different fingerprint: 5bb394d82599b866 vs 4f908520bbaded18\n- **Conclusion:**\
    \ Related by origin (error_watcher auto-file), but distinct backend component,\
    \ distinct error signature, and terminal state\n\n**OOMPAH-1016 through OOMPAH-1027**:\n\
    - All variants of the same OOMPAH-1015 malformed-ledger issue\n- Status: All Archived\
    \ or Merged (terminal)\n- Clearly part of a separate incident flood (per OOMPAH-1015\
    \ comments: \"2026-08-11 startup flood OOMPAH-1015..1070\")\n\n**Other tasks (OOMPAH-1000-1014):**\n\
    - Cover terminal-audit, workflow, quality-gate, epic, and landing issues\n- None\
    \ describe orchestrator task-authority deadlines\n- All terminal status\n\n###\
    \ Key Observations\n\n1. **No active task matches OOMPAH-1325's error signatu"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 400db96f3bfb4dadba0390b3e03cb268--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1325
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T07:37:53.786684+00:00'
  - run_id: 17183c47819c4f2daa09ac5a6a036e8d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1325
    source_sha: null
    completed_at: ''
  - run_id: 74bfbfdece114d7a94e5f1992ec6c830--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1325
    source_sha: null
    completed_at: ''
  - run_id: c67717145bef496c96faa2fd73b41b32--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1325
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2139
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2139
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2139
    cost_usd: 0.0
    recorded_at: '2026-08-24T07:37:53.770547+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1325
  base_branch: main
  base_sha: 1e08d58a3fcfd254a2bffedd2580d383f1b02193
  head_sha: fa6cffbc078a591a2df05fbf674ed34c0e7ad1e8
  submitted_at: '2026-08-24T12:16:39.014152+00:00'
  updated_at: '2026-08-25T22:36:54.783411+00:00'
  wait_reason: review_generation_requeue
  wait_generation: review:70ba7cdf87bcf9b83b2453cb4b2e57209647adc86504f01d1d56901f40a6ea6d
oompah.work_branch: OOMPAH-1325
oompah.review_url: https://github.com/lesserevil/oompah/pull/911
oompah.review_number: '911'
oompah.target_branch: main
oompah.review_head: fa6cffbc078a591a2df05fbf674ed34c0e7ad1e8
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1307 identifier=OOMPAH-1307 run_id=cf289f342ff8435d925bd789c13b1e6d timeout_seconds=30.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1307 identifier=OOMPAH-1307 run_id=cf289f342ff8435d925bd789c13b1e6d timeout_seconds=30.0

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
- fingerprint: 4f908520bbaded18
- dedup_fingerprint: 4f908520bbaded18

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 07:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 07:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 07:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 6s
- Log: OOMPAH-1325__20260824T073654Z.jsonl
---
author: oompah
created: 2026-08-24 11:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 11:09
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 11:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 29s
- Log: OOMPAH-1325__20260824T110934Z.jsonl
---
author: oompah
created: 2026-08-24 11:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 11:34
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 11:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 58s
- Log: OOMPAH-1325__20260824T113439Z.jsonl
---
author: oompah
created: 2026-08-24 12:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 12:04
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 12:05
---
Understanding: Issue OOMPAH-1325 reports a timeout error in backend:orchestrator where 'pre-provider contributor evidence exceeded its bounded task-authority deadline' with a 30-second timeout. This occurs when oompah operates on the provenanceguardedtracker project. The error is unhandled and auto-filed. Plan: (1) Locate the error message in code, (2) understand what operation times out, (3) identify root cause, (4) implement graceful handling or fix timeout issue, (5) verify no regression in error_watcher.
---
author: oompah
created: 2026-08-24 12:08
---
Discovery: Found the timeout handling in orchestrator.py:58070. The code logs a WARNING when 'Pre-provider contributor evidence' persistence task exceeds its timeout (default 30s or configured). The timeout is caught and handled gracefully - work is retired for retry. The warning is informational but being picked up by error_watcher and auto-filed. Root cause: This is a legitimate timeout scenario that's already handled correctly, but logged at WARNING level which may be too verbose for normal operation.
---
author: oompah
created: 2026-08-24 12:14
---
Implementation: Changed three logger.warning() calls in orchestrator.py:_stage_work_contributor_launch to logger.debug() for gracefully-handled timeout scenarios. Lines changed: 57957 (prior evidence pending), 58070 (evidence timeout), 58106 (cancelled evidence timeout). These are expected timeouts with automatic retry - logging at DEBUG avoids triggering error_watcher while still supporting diagnostics.
---
author: oompah
created: 2026-08-24 12:16
---
Verification: All tests pass. Ran test_provider_retirement.py (21 tests), test_error_watcher_orchestrator.py (13 tests), and orchestrator handler tests with 'contributor' filter (71 tests). Changes verified - three logger.warning calls converted to logger.debug for gracefully-handled timeout scenarios. This prevents error_watcher from auto-filing expected timeouts.
---
author: oompah
created: 2026-08-24 12:16
---
Fixed contributor evidence timeout auto-filing by changing logging level from WARNING to DEBUG for gracefully-handled timeout scenarios. Three logger.warning() calls in orchestrator.py:_stage_work_contributor_launch were changed to logger.debug(). This prevents error_watcher from auto-filing expected, handled timeouts while preserving diagnostics.
---
author: oompah
created: 2026-08-24 14:32
---
Branch quality gate passed for `fa6cffbc078a591a2df05fbf674ed34c0e7ad1e8` using `make test` in 185.1s. Review creation may proceed.
---
<!-- COMMENTS:END -->
