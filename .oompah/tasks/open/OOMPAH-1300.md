---
id: OOMPAH-1300
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:03:07.024179Z'
updated_at: '2026-08-21T16:13:36.916824Z'
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
  task_fingerprint: d702ad3ace7226f6c3c1d9f6420c4f03ec4041fab0bc8a96b2f727687ba8d936
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: bcb9f23d40d40f566183dc7e3d40328124cefd051e8f97681158ff46396dfed9:146657
  claim_owner: 8b3bb5f8-8d0e-4cf3-9d62-5bd5932d676d
  claimed_at: '2026-08-21T16:13:15.124155+00:00'
  claim_expires_at: '2026-08-21T16:43:15.124155+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5bf5cc6f-90bf-4076-9ed7-5e73564382f4
oompah.work_contributors:
  runs:
  - run_id: fa91c103003e48b6a65db7e3aba8d01e--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
  - run_id: e4cd30ea32894d8d8a161c29aa809d76--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1300
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1216 identifier=OOMPAH-1216 run_id=5063090547c34f1aa435b6e58794299f timeout_seconds=5.0

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
- fingerprint: 10a9dfa87ab29a16
- dedup_fingerprint: 10a9dfa87ab29a16

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 10s
- Log: OOMPAH-1300__20260821T033830Z.jsonl
---
author: oompah
created: 2026-08-21 07:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:44
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 59s
- Log: OOMPAH-1300__20260821T074325Z.jsonl
---
author: oompah
created: 2026-08-21 16:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
