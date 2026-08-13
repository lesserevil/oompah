---
id: OOMPAH-1259
type: task
status: Backlog
priority: null
title: Rematerialize dead recurring scheduler generations during restart reconstruction
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T23:58:37.536440Z'
updated_at: '2026-08-13T23:58:37.536440Z'
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
---
## Summary

Bug: restart reconstruction can deadlock all workflow-worker admission when a recurring managed decision's only job becomes Superseded before its next reassessment deadline. activate_schedule sees the unchanged decision revision, retains the old job_generation, and reconcile_schedule replays the dead idempotency key instead of creating live authority. Liveness then reports required_recovery_count > materialized_recovery_count and indefinitely defers every worker, including unrelated valid work. Live reproduction: TRICKLE-134 child_landing_verification was superseded after evidence changed; the cursor remained materialized to that superseded generation while TRICKLE-141's valid direct_epic_maintenance_completion stayed queued behind the restart audit-priority boundary. Scope: update recurrence/materialization logic so an unchanged recurring decision immediately receives a new activation generation whenever its prior managed job is terminal without live authority (including Superseded), while preserving retry/exhaustion policy and preventing tight re-enqueue loops after successful completion. Add scheduler/store tests reproducing superseded same-revision restart recovery, proving the next scan materializes one live job and restart liveness converges; add regression coverage that completed recurring jobs wait until their deadline and exhausted jobs remain fenced. Acceptance: restart reconstruction reaches required=materialized, worker admission resumes, unrelated queued jobs execute, and focused workflow scheduler/runtime tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

