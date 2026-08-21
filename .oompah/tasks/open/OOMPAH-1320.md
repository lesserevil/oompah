---
id: OOMPAH-1320
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:12:08.566823Z'
updated_at: '2026-08-21T05:06:59.094383Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-6721ed37af5c4e51ae3558e98f499304
  actor: shedwards
  committed_at: '2026-08-21T01:29:59.950511Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8f8a9e7ca03461ef8b7ad338935420f8209cba07dbf033be0e12f70f042ee33c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T05:06:49.401881+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The only closely related incident in the corpus is the\
    \ `backend:terminal_audit_enforcement` \u201Cpre_recovery_finalization_metadata_malformed:proj-14849f1b:*\u201D\
    \ flood, which was fixed/archived (canonical OOMPAH-1015) and is for a different\
    \ backend component/err string than this `backend:orchestrator` \u201CPre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200\
    \ \u2026\u201D error.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none  \nEvidence: The only closely related\
    \ incident in the corpus is the `backend:terminal_audit_enforcement` \u201Cpre_recovery_finalization_metadata_malformed:proj-14849f1b:*\u201D\
    \ flood, which was fixed/archived (canonical OOMPAH-1015) and is for a different\
    \ backend component/err string than this `backend:orchestrator` \u201CPre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200\
    \ \u2026\u201D error."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 97761749-5163-4ce5-ba3c-46dca3e36d45
oompah.work_contributors:
  runs:
  - run_id: 3d8c983349714087ae7bb78b3012cca6--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1320
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T05:06:49.408735+00:00'
oompah.task_costs:
  total_input_tokens: 32100
  total_output_tokens: 125
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 32100
      output_tokens: 125
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 32100
    output_tokens: 125
    cost_usd: 0.0
    recorded_at: '2026-08-21T05:06:49.400145+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1200 identifier=OOMPAH-1200 run_id=cdc92fe9ae4942f9aff1c4d8d5d14fe6 timeout_seconds=5.0

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
- fingerprint: d8afd06b57598237
- dedup_fingerprint: d8afd06b57598237

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:06
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 32.1K in / 125 out [40.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 43s
- Log: OOMPAH-1320__20260821T050629Z.jsonl
---
<!-- COMMENTS:END -->
