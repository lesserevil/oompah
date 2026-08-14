---
id: OOMPAH-1226
type: task
status: Merged
priority: null
title: Stop In Progress accepted submissions from hot-looping recovery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T08:33:09.430186Z'
updated_at: '2026-08-14T07:45:51.040537Z'
work_branch: OOMPAH-1226
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
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-ed8ecbdcf92a
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    digest: ca35590c581c1ec5c1f62b2038f9d6b57a9dcf6d03784e6fd79f94bd1304d8ce
  - version: 1
    audit_id: audit-4df7ea746e7c
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    digest: ca35590c581c1ec5c1f62b2038f9d6b57a9dcf6d03784e6fd79f94bd1304d8ce
  - version: 1
    audit_id: audit-b873f4978c4a
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    digest: 714965cb4f076f05c98db9b51485fec89ddfcdecc75db4a98d467b500ba6e7e3
  - version: 1
    audit_id: audit-dbee3bc2aa0d
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    digest: 714965cb4f076f05c98db9b51485fec89ddfcdecc75db4a98d467b500ba6e7e3
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7db28c54ca53
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 714965cb4f076f05c98db9b51485fec89ddfcdecc75db4a98d467b500ba6e7e3
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #855 merged as ff129764b and that landed tree is
      contained by origin/main; the fresh terminal request supersedes the stale audit
      fingerprint.'
    created_at: '2026-08-14T07:45:47.103756+00:00'
    selected_ref: e63e61f8a4145de79582937e263f6b4dff7d5e5a
    selected_sha: e63e61f8a4145de79582937e263f6b4dff7d5e5a
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-ed8ecbdcf92a
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ca35590c581c1ec5c1f62b2038f9d6b57a9dcf6d03784e6fd79f94bd1304d8ce
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T09:23:44.314092+00:00'
    eligible_at: '2026-08-13T09:23:44.314092+00:00'
    selected_ref: origin/OOMPAH-1226
    selected_sha: e63e61f8a4145de79582937e263f6b4dff7d5e5a
  - version: 1
    audit_id: audit-4df7ea746e7c
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    target_state: Merged
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ca35590c581c1ec5c1f62b2038f9d6b57a9dcf6d03784e6fd79f94bd1304d8ce
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T09:23:44.314092+00:00'
    prerequisite_audit_id: audit-ed8ecbdcf92a
    selected_ref: origin/OOMPAH-1226
    selected_sha: e63e61f8a4145de79582937e263f6b4dff7d5e5a
  - version: 1
    audit_id: audit-b873f4978c4a
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 714965cb4f076f05c98db9b51485fec89ddfcdecc75db4a98d467b500ba6e7e3
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Validation
    created_at: '2026-08-14T07:45:38.106603+00:00'
    eligible_at: '2026-08-14T07:45:38.106603+00:00'
    selected_ref: e63e61f8a4145de79582937e263f6b4dff7d5e5a
    selected_sha: e63e61f8a4145de79582937e263f6b4dff7d5e5a
  - version: 1
    audit_id: audit-dbee3bc2aa0d
    project_id: proj-14849f1b
    task_id: OOMPAH-1226
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 714965cb4f076f05c98db9b51485fec89ddfcdecc75db4a98d467b500ba6e7e3
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Validation
    created_at: '2026-08-14T07:45:38.106603+00:00'
    prerequisite_audit_id: audit-b873f4978c4a
    selected_ref: e63e61f8a4145de79582937e263f6b4dff7d5e5a
    selected_sha: e63e61f8a4145de79582937e263f6b4dff7d5e5a
  attempt_history: []
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1226
  head_sha: e63e61f8a4145de79582937e263f6b4dff7d5e5a
  submitted_at: '2026-08-13T09:25:26.525989+00:00'
  updated_at: '2026-08-13T09:25:26.525989+00:00'
oompah.work_branch: OOMPAH-1226
---
## Summary

Bug observed live on resumed Trickle 2026-08-13. TRICKLE-140 is In Progress with accepted integration metadata for exact head 6d089ed6; that head is already contained in GitLab main and its source branch was normally deleted after MR !4 merged (follow-up MR !5 also merged). The CONFIG fact correctly reports accepted_submission_branch_unavailable and parks validation recovery, but _implementation_decision ignores accepted_submission_recovery_state for In Progress tasks and emits implementation.recovery_scheduled. OrchestratorImplementationEffects._admit_dispatch then immediately supersedes each job because the accepted submission outranks implementation. The runtime created at least 131 superseded implementation_recovery jobs in ~31 minutes. Scope: make In Progress accepted-submission authority preempt generic implementation recovery just as Open does; route exact/landed accepted work into the correct validation/landing lifecycle, park ambiguous/unavailable or advanced source evidence without a job, and never redispatch an implementer while accepted integration metadata is authoritative. Preserve exact-head/project/target fencing and normal recovery for genuinely interrupted work without accepted submission evidence. Required tests: In Progress accepted branch exact, merged+source-deleted/target-contains-head, branch unavailable without landing proof, branch advanced, and no accepted submission; repeated reconciliation creates no recovery-job churn; a proven landed submission naturally reaches its terminal lifecycle. Acceptance: live TRICKLE-140 stops producing implementation_recovery jobs, no new implementer is launched, its already-landed work proceeds to the appropriate terminal state, and durable job growth is bounded across repeated ticks and restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 08:33
---
Live workaround audit: TRICKLE-140 exact accepted head 6d089ed6 is already in GitLab main, but the source ref is deleted after merge. Leaving status untouched until a fenced lifecycle operation can consume this proof; direct status editing would hide the scheduler defect. The service continues to hot-loop superseded recovery jobs, so code repair is required.
---
author: oompah
created: 2026-08-13 09:23
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-13 09:25
---
Implemented exact target-containment proof for accepted submissions whose source branch was deleted, routed landed submissions into validation, and parked ambiguous accepted authority ahead of generic implementation recovery. Added regression coverage for landed, unavailable, advanced, and repeated-reconciliation cases. PR #855 exact head e63e61f8 passed hosted gates on Python 3.11, 3.12, and 3.13 and merged as ff129764.
---
author: oompah
created: 2026-08-14 07:45
---
PR #855 merged as ff129764b; the landed tree is contained by origin/main and no implementation remains.
---
<!-- COMMENTS:END -->
