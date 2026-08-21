---
id: OOMPAH-1296
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1212 identifier=OOMPAH-1212 run_id=8b458485f69641f9932ad58ba9dbfc83
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:59:20.045563Z'
updated_at: '2026-08-21T07:48:39.285757Z'
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
  task_fingerprint: af53521ba791f2b25043debead4a2cd5c4b27571abc0642ba57889eee89b1111
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T03:27:11.520269+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The supplied corpus contains 29 peer tasks, all in terminal\
    \ states. None describe the specific \"Pre-provider contributor evidence exceeded\
    \ bounded task-authority deadline\" error with timeout_seconds=5.0 from backend:orchestrator.\
    \ The closest active-topic tasks (OOMPAH-1000\u20131014) address distinct orchestrator/workflow\
    \ problems unrelated to provider evidence timeout handling. No active duplicate\
    \ target was identified in the authoritative corpus.\nLooking at the supplied\
    \ project task corpus, I need to determine if OOMPAH-1296 is a duplicate of an\
    \ existing active issue.\n\n## Analysis\n\n**Current Issue OOMPAH-1296:**\n- Error:\
    \ \"Pre-provider contributor evidence exceeded its bounded task-authority deadline\"\
    \n- Source: `backend:orchestrator`\n- Timeout: 5.0 seconds\n- Related to issue_id=OOMPAH-1212\n\
    - Auto-filed by `error_watcher`\n\n**Task Corpus Review:**\n\nI've examined all\
    \ 29 similarity candidates provided in the corpus:\n\n- **OOMPAH-1000 through\
    \ OOMPAH-1014**: Merged/Done tasks addressing various orchestrator and workflow\
    \ issues (terminal audit binding, quality gates, workflow admission, epic validation,\
    \ etc.) \u2014 but these describe distinct problems with different error signatures\n\
    - **OOMPAH-1015 through OOMPAH-1027**: Archived/Merged tasks about \"terminal-audit\
    \ enforcement: pre_recovery_finalization_metadata_malformed\" \u2014 a different\
    \ class of errors\n- **OOMPAH-1**, **OOMPAH-10**, **OOMPAH-164**: Archived tasks\
    \ with unrelated topics\n\n**Key Finding:**\nAll peer tasks in the corpus are\
    \ in terminal states (Done, Merged, or Archived). None are currently active (Open,\
    \ In Progress, or Ready to Integrate). More importantly, none describe the specific\
    \ error about \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\" related to provider evidence collection and task-authority timeouts\
    \ in the orchestrator.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate\
    \ preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: The supplied corpus\
    \ contains 29 peer tasks, all in terminal states. None describe the specific \"\
    Pre-provider contributor evidence exceeded bounded task-authority deadline\" error\
    \ with timeout_seconds=5.0 from backend:orchestrator. The closest active-topic\
    \ tasks (OOMPAH-1000\u20131014) address distinct orchestrator/workflow problems\
    \ unrelated to provider evidence timeout handling. No active duplicate target\
    \ was identified in the authoritative corpus."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e195ff3f-302e-4b63-a4b4-0ea924545c86
oompah.work_contributors:
  runs:
  - run_id: 8edf3c0a7e444c399d8586acb6242cc1--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1296
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T03:27:11.542418+00:00'
  - run_id: b8f47d3d0cff4d40b9d1ca63c6180f20--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1296
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1922
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1922
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1922
    cost_usd: 0.0
    recorded_at: '2026-08-21T03:27:11.519580+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1212 identifier=OOMPAH-1212 run_id=8b458485f69641f9932ad58ba9dbfc83 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1212 identifier=OOMPAH-1212 run_id=8b458485f69641f9932ad58ba9dbfc83 timeout_seconds=5.0

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
- fingerprint: c8355b25379a4875
- dedup_fingerprint: c8355b25379a4875

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 37s
- Log: OOMPAH-1296__20260821T032537Z.jsonl
---
author: oompah
created: 2026-08-21 07:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:37
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 07:37
---
**Understanding & Plan:**

The error 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' occurs in backend:orchestrator during normal operation. The error is caught by error_watcher and auto-filed (not handled gracefully).

**Investigation Plan:**
1. Search for the error message in the codebase to find where it originates
2. Understand the deadline/timeout mechanism (5.0 sec timeout)
3. Identify if this is a genuine bug (too short timeout, incorrect implementation) or needs graceful handling
4. Implement fix or graceful error handling
5. Verify with tests that error_watcher is no longer triggered for this condition

Starting codebase exploration now.
---
author: oompah
created: 2026-08-21 07:48
---
**Root Cause Identified:**

Found the issue in `oompah/orchestrator.py` at line 57834-58090 in the `_stage_work_contributor_launch()` method.

The problem:
- The code attempts to persist contributor evidence (metadata write) with a bounded timeout
- When the persistence takes longer than `contributor_evidence_persist_timeout_seconds` (default 30s, but 5.0s in the error report), it times out
- This timeout is logged as `logger.error()` which triggers error_watcher to auto-file a task
- The error message: 'Pre-provider contributor evidence exceeded its bounded task-authority deadline'

The issue: This is NOT actually an error condition - it's a graceful degradation that retires the worker for retry (line 58084-58090). The timeout allows the system to stop waiting and continue, but it's being reported as an ERROR level log entry, which treats it as an unhandled error.

Next: Will fix by downgrading this to a WARNING level log, since this is expected behavior when persistence is slow (not a bug to report).
---
<!-- COMMENTS:END -->
