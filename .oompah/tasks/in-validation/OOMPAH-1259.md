---
id: OOMPAH-1259
type: task
status: In Validation
priority: null
title: Rematerialize dead recurring scheduler generations during restart reconstruction
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T23:58:37.536440Z'
updated_at: '2026-08-14T00:38:06.887027Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: a062e5de-23f3-4832-8907-b6f8cc04d962
  request_fingerprint: 675f80aa4382d987678bd7cec461f49413f18d11b31fe5e248de18c893d0f066
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-2d740494729a
    project_id: proj-14849f1b
    task_id: OOMPAH-1259
    digest: 97cbe51f2cc16cdac084c2b5d8fff6f1183294f28d813cad98cf8117f9e60766
  - version: 1
    audit_id: audit-d715f4745539
    project_id: proj-14849f1b
    task_id: OOMPAH-1259
    digest: 97cbe51f2cc16cdac084c2b5d8fff6f1183294f28d813cad98cf8117f9e60766
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2d740494729a
    project_id: proj-14849f1b
    task_id: OOMPAH-1259
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 97cbe51f2cc16cdac084c2b5d8fff6f1183294f28d813cad98cf8117f9e60766
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-14T00:29:44.030455+00:00'
    eligible_at: '2026-08-14T00:29:44.030455+00:00'
    selected_ref: origin/OOMPAH-1259
    selected_sha: fb8a2ba298f396ef36a06430faaae6344142e7cb
  - version: 1
    audit_id: audit-d715f4745539
    project_id: proj-14849f1b
    task_id: OOMPAH-1259
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 97cbe51f2cc16cdac084c2b5d8fff6f1183294f28d813cad98cf8117f9e60766
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-14T00:29:44.030455+00:00'
    prerequisite_audit_id: audit-2d740494729a
    selected_ref: origin/OOMPAH-1259
    selected_sha: fb8a2ba298f396ef36a06430faaae6344142e7cb
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

Bug: restart reconstruction can deadlock all workflow-worker admission when a recurring managed decision's only job becomes Superseded before its next reassessment deadline. activate_schedule sees the unchanged decision revision, retains the old job_generation, and reconcile_schedule replays the dead idempotency key instead of creating live authority. Liveness then reports required_recovery_count > materialized_recovery_count and indefinitely defers every worker, including unrelated valid work. Live reproduction: TRICKLE-134 child_landing_verification was superseded after evidence changed; the cursor remained materialized to that superseded generation while TRICKLE-141's valid direct_epic_maintenance_completion stayed queued behind the restart audit-priority boundary. Scope: update recurrence/materialization logic so an unchanged recurring decision immediately receives a new activation generation whenever its prior managed job is terminal without live authority (including Superseded), while preserving retry/exhaustion policy and preventing tight re-enqueue loops after successful completion. Add scheduler/store tests reproducing superseded same-revision restart recovery, proving the next scan materializes one live job and restart liveness converges; add regression coverage that completed recurring jobs wait until their deadline and exhausted jobs remain fenced. Acceptance: restart reconstruction reaches required=materialized, worker admission resumes, unrelated queued jobs execute, and focused workflow scheduler/runtime tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 00:15
---
Implementation checkpoint: reproduced the live restart deadlock as an unchanged recurring managed decision whose only current job was Superseded before its reassessment deadline. The scheduler now rotates that dead generation immediately only when no exact live replacement owns execution; protected event replacements and quarantined calls remain exclusive, completed jobs retain deadline semantics, and Cancelled/Exhausted rows remain fenced. Verification so far: 148 scheduler/store tests passed; 418 combined job-store/scheduler/runtime/epic tests passed; terminal mutation scan 21/21 passed; secret scan passed. Awaiting independent exact-diff review before commit.
---
author: oompah
created: 2026-08-14 00:29
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 00:38
---
Completed and live-verified. PR #876 merged to main at eb61ed2adae7447952c31b30198849642f7a7ba6 after all Python 3.11/3.12/3.13 CI gates passed. The managed service auto-restarted on that exact revision with only Trickle resumed. Restart reconstruction converged (required=materialized, initially 11/11 and currently 10/10; pending=false), and TRICKLE-134's superseded recurring child_landing_verification generation was immediately rematerialized and executed on successive current generations. Focused scheduler suite: 41 passed; combined scheduler/store/runtime/epic suite: 419 passed; terminal mutation scan: 21/21. Branch/worktree were pushed, merged, and pruned.
---
<!-- COMMENTS:END -->
