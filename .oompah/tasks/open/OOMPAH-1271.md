---
id: OOMPAH-1271
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1195 identifier=OOMPAH-1195 run_id=ced25410896e41afb3bf7d9c9eb3e65d
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T22:36:38.933130Z'
updated_at: '2026-08-21T11:03:44.763559Z'
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
  task_fingerprint: 58ae2dc87b2cdfa4b94a3b503316333242995391986014e324bd3f9ff9d8b4ca
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 125a8aa99cb1e2861ec01f527ce9ec888c31dcbc9486b0fbfcb6659a0183b27b:146121
  claim_owner: 94774825-4468-4d75-bdb4-5977b2bd9951
  claimed_at: '2026-08-21T11:01:51.639538+00:00'
  claim_expires_at: '2026-08-21T11:31:51.639538+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7042da94-3aab-46bf-b1b7-c54c5c570f92
oompah.work_contributors:
  runs:
  - run_id: bbf5ebcd1b17461ca4aa72862204a3f4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1271
    source_sha: null
    completed_at: ''
  - run_id: dae8bb925bfa4f4c8ad67eb14b574512--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1271
    source_sha: null
    completed_at: ''
  - run_id: 8250bef9e2cc462a8adaee79529fa165--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1271
    source_sha: null
    completed_at: ''
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1195 identifier=OOMPAH-1195 run_id=ced25410896e41afb3bf7d9c9eb3e65d timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1195 identifier=OOMPAH-1195 run_id=ced25410896e41afb3bf7d9c9eb3e65d timeout_seconds=5.0

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
- fingerprint: 3cebd005e58f58c1
- dedup_fingerprint: 3cebd005e58f58c1

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 02:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 48s
- Log: OOMPAH-1271__20260821T022358Z.jsonl
---
author: oompah
created: 2026-08-21 05:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 47s
- Log: OOMPAH-1271__20260821T055237Z.jsonl
---
author: oompah
created: 2026-08-21 11:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:03
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
