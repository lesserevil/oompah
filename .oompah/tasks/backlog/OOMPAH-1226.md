---
id: OOMPAH-1226
type: task
status: Backlog
priority: null
title: Stop In Progress accepted submissions from hot-looping recovery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T08:33:09.430186Z'
updated_at: '2026-08-13T08:33:09.430186Z'
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
  creation_marker: 9cf0e19a-8481-49ec-8ea9-ad0dfcfdc0c0
  request_fingerprint: 3d4e88a5ed6b20d843f7d96cb3dfd9a8afaf2b998153647bda842ce1ff3d247d
---
## Summary

Bug observed live on resumed Trickle 2026-08-13. TRICKLE-140 is In Progress with accepted integration metadata for exact head 6d089ed6; that head is already contained in GitLab main and its source branch was normally deleted after MR !4 merged (follow-up MR !5 also merged). The CONFIG fact correctly reports accepted_submission_branch_unavailable and parks validation recovery, but _implementation_decision ignores accepted_submission_recovery_state for In Progress tasks and emits implementation.recovery_scheduled. OrchestratorImplementationEffects._admit_dispatch then immediately supersedes each job because the accepted submission outranks implementation. The runtime created at least 131 superseded implementation_recovery jobs in ~31 minutes. Scope: make In Progress accepted-submission authority preempt generic implementation recovery just as Open does; route exact/landed accepted work into the correct validation/landing lifecycle, park ambiguous/unavailable or advanced source evidence without a job, and never redispatch an implementer while accepted integration metadata is authoritative. Preserve exact-head/project/target fencing and normal recovery for genuinely interrupted work without accepted submission evidence. Required tests: In Progress accepted branch exact, merged+source-deleted/target-contains-head, branch unavailable without landing proof, branch advanced, and no accepted submission; repeated reconciliation creates no recovery-job churn; a proven landed submission naturally reaches its terminal lifecycle. Acceptance: live TRICKLE-140 stops producing implementation_recovery jobs, no new implementer is launched, its already-landed work proceeds to the appropriate terminal state, and durable job growth is bounded across repeated ticks and restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

