---
id: OOMPAH-1225
type: bug
status: In Validation
priority: 1
title: Refresh GitLab review CI when MR list omits head_pipeline
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T08:09:49.181773Z'
updated_at: '2026-08-13T08:49:45.691085Z'
work_branch: OOMPAH-1225
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: gitlab-mr-list-missing-head-pipeline-ci-refresh
  request_fingerprint: 5b4e407fccdecbfa7bacb307fae8f5032d210c7257893900acc7ce2a0133e5c8
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1225
  head_sha: 69fb55edca7c6c2f5d04e2839266968c07bd5049
  submitted_at: '2026-08-13T08:49:19.100809+00:00'
  updated_at: '2026-08-13T08:49:19.100809+00:00'
oompah.work_branch: OOMPAH-1225
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-9fea7876e7fc
    project_id: proj-14849f1b
    task_id: OOMPAH-1225
    digest: eb1dc9a93689313bda2b33de034da6990901e41c94e2969e34b5ea2d42766f65
  - version: 1
    audit_id: audit-7f5b1674ec3e
    project_id: proj-14849f1b
    task_id: OOMPAH-1225
    digest: eb1dc9a93689313bda2b33de034da6990901e41c94e2969e34b5ea2d42766f65
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-9fea7876e7fc
    project_id: proj-14849f1b
    task_id: OOMPAH-1225
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eb1dc9a93689313bda2b33de034da6990901e41c94e2969e34b5ea2d42766f65
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T08:49:40.299244+00:00'
    eligible_at: '2026-08-13T08:49:40.299244+00:00'
    selected_ref: 69fb55edca7c6c2f5d04e2839266968c07bd5049
    selected_sha: 69fb55edca7c6c2f5d04e2839266968c07bd5049
  - version: 1
    audit_id: audit-7f5b1674ec3e
    project_id: proj-14849f1b
    task_id: OOMPAH-1225
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eb1dc9a93689313bda2b33de034da6990901e41c94e2969e34b5ea2d42766f65
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T08:49:40.299244+00:00'
    prerequisite_audit_id: audit-9fea7876e7fc
    selected_ref: 69fb55edca7c6c2f5d04e2839266968c07bd5049
    selected_sha: 69fb55edca7c6c2f5d04e2839266968c07bd5049
  attempt_history: []
---
## Summary

Triggered by: TRICKLE-118

Bug observed live on Trickle 2026-08-13. GitLab merge request !6 for TRICKLE-118 is open, mergeable, and its exact-head pipeline 62464633 succeeded, but GitLab's list merge requests response omitted head_pipeline. GitLabProvider.list_open_reviews therefore emitted an empty/unknown ci_status; the durable review workflow repeatedly projected review.ci_pending, kept TRICKLE-118 in In Review, occupied the configured 1/1 review capacity, and blocked seven standalone Ready tasks indefinitely. Scope: make the forge-neutral review observation resolve CI for the exact MR head when the list/detail payload lacks a conclusive head_pipeline verdict, using the existing get_ci_status_for_sha/pipeline API contract without confusing unavailable evidence with successful empty results. Preserve exact-head fencing, bounded provider calls, GitHub behavior, capability warnings, webhook/polling convergence, and fail-closed behavior for ambiguous or changing heads. Required tests: self-managed GitLab open MR list omits head_pipeline while exact-head pipeline is passed/failed/pending/unknown; only the matching immutable head controls review progression; transport/403/429/malformed responses stay retryable and do not falsely merge; a successful fallback releases review capacity and allows dependent Ready work to advance. Acceptance: live TRICKLE-118 no longer remains review.ci_pending after its successful exact-head pipeline, and no manual refresh or status edit is needed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 08:33
---
Implementation committed and pushed as 69fb55ed on PR #854. Local focused suites passed before rebase (121 GitLab/review tests; 331 broader SCM/review tests), post-rebase secret scan passed, and hosted Python 3.11/3.12/3.13 gates are running. Live source task TRICKLE-118 remains review.ci_pending until deployment.
---
author: oompah
created: 2026-08-13 08:49
---
Refresh GitLab review CI from the exact immutable MR head when list responses omit head_pipeline; preserve warnings and the embedded fast path. PR #854 passed hosted Python 3.11/3.12/3.13 gates.
---
author: oompah
created: 2026-08-13 08:49
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
