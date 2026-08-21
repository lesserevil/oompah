---
id: OOMPAH-1269
type: task
status: Open
priority: null
title: publication_rollback storm livelocks trickle reconcile and starves dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-19T01:37:27.110739Z'
updated_at: '2026-08-21T02:22:21.249124Z'
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
  creation_marker: e4ad1915-a8f5-46d6-a481-5424475d7eb8
  request_fingerprint: 83c914bb2a5339cac782d8d64bf3a68d4cd2eba9819b71b16e9850d49ef9c949
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
  task_fingerprint: 5dc0783d247a95a6a1800a7a554d4fd4b26101485aa5a369f7f02477975a5be0
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 1da319a24e628f66f52b1a8ba85186317d7a26a644eea437b3c6bc3dc2243fb2:142898
  claim_owner: 884c7b0a-4fe0-4acd-9fe6-041416485094
  claimed_at: '2026-08-21T02:20:03.431274+00:00'
  claim_expires_at: '2026-08-21T02:50:03.431274+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 70afe474-4995-4349-a6b9-171524c9ec93
oompah.work_contributors:
  runs:
  - run_id: e9e763cf67dd4ac68c07510e10ceffe4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1269
    source_sha: null
    completed_at: ''
---
## Summary

Symptom: after restart, no tasks dispatch (running_count=0). Dispatch is deferred behind the post-restart audit-priority/liveness boundary, and the liveness scan never completes (status=action_required) because the trickle (proj-3e4e9214) reconcile integration phase takes ~19-35s and exceeds the ~120s restart budget.

Root cause: workflow_job_events has ~20.1M rows dominated by 'publication_rollback' events on live (non-Archived) trickle tasks: TRICKLE-117 alone has ~4.04M publication_rollback events (13,241 jobs), plus TRICKLE-127/128/129 in the millions. The event archival job (OOMPAH-1268) only relocates lifecycle-final:Archived task events, so it cannot reclaim these.

Mechanism: workflow_runtime publication compares the scan-time workflow_authority_revision against workflow_revision_source() at publish time (oompah/workflow_runtime.py ~4669-4687). For trickle it differs on nearly every pass, raising WorkflowPublicationSuperseded('workflow authority changed before publication') — logged 3,486 times. Each supersede calls rollback_authority -> WorkflowJobStore.restore_snapshot_authority (oompah/workflow_jobs.py ~2577-2640), which supersedes every managed job for the in-scope tasks and appends one publication_rollback event PER JOB (~13k for TRICKLE-117). 3,486 rollbacks x thousands of jobs = millions of events. The growing ledger slows the next scan, which makes the race worse: a self-reinforcing livelock.

Investigate:
1. Why trickle's workflow_authority_revision changes between capture and publish every pass (state-branch writes? the rollback itself bumping authority? epic/integration churn on TRICKLE-117/127/128/129?).
2. Whether restore_snapshot_authority should emit one aggregate rollback event instead of one-per-job, to bound ledger growth.
3. Whether repeated same-generation rollbacks should be idempotent/no-op when nothing actually changed.

Acceptance: trickle reconcile completes within the restart budget; publication_superseded rate for proj-3e4e9214 drops to near zero in steady state; workflow_job_events stops growing unboundedly; post-restart dispatch resumes (tasks reach In Progress). Add regression coverage for the supersede/rollback loop and for bounded event emission.

Evidence files: oompah/workflow_runtime.py (~4669-4687), oompah/workflow_controller.py (~1170-1339), oompah/workflow_jobs.py restore_snapshot_authority (~2512-2660). Log: 'Durable workflow publication superseded for proj-3e4e9214: workflow authority changed before publication' x3486.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-19 18:02
---
PR #885 bounds the damage: restore_snapshot_authority now emits ONE aggregate publication_rollback event per task+snapshot (job_count+job_ids) instead of one-per-job, so the ledger can't explode again (was ~4M events on TRICKLE-117). Root-cause churn (workflow_authority_revision advancing between capture and publish via owner-claim mutations) is currently quiescent (2 supersedes since restart, 0 owner claims) and remains open here for follow-up, along with reclaiming the ~20M historical rows. Auto-merge enabled.
---
author: oompah
created: 2026-08-21 02:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
