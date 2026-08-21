---
id: OOMPAH-1304
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224 run_id=c8470fa192aa4f5787330252c657bf61
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:16:50.124021Z'
updated_at: '2026-08-21T08:01:05.611405Z'
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
  task_fingerprint: 2327af567ea1d6b993917c810da24035cc05c1ba197b91883a30ce4513646c96
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 85e439290a0c2a2663e902b2f4596803de79b9ee39c22b0d6a82bd0de9050d2b:144700
  claim_owner: 94774825-4468-4d75-bdb4-5977b2bd9951
  claimed_at: '2026-08-21T08:00:32.583180+00:00'
  claim_expires_at: '2026-08-21T08:30:32.583180+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c11d4419-178a-43c4-b34d-a912c58f8368
oompah.work_contributors:
  runs:
  - run_id: 916c28a615764a8a919566a0994848ef--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1304
    source_sha: null
    completed_at: ''
  - run_id: 54d1bb48503844e789ba9d1145e55338--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1304
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224 run_id=c8470fa192aa4f5787330252c657bf61 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1224 identifier=OOMPAH-1224 run_id=c8470fa192aa4f5787330252c657bf61 timeout_seconds=5.0

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
- fingerprint: 6c336909c7943257
- dedup_fingerprint: 6c336909c7943257

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 10s
- Log: OOMPAH-1304__20260821T034400Z.jsonl
---
author: oompah
created: 2026-08-21 08:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 08:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
