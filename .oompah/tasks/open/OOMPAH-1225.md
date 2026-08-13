---
id: OOMPAH-1225
type: bug
status: Open
priority: 1
title: Refresh GitLab review CI when MR list omits head_pipeline
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T08:09:49.181773Z'
updated_at: '2026-08-13T08:10:10.524755Z'
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
  creation_marker: gitlab-mr-list-missing-head-pipeline-ci-refresh
  request_fingerprint: 5b4e407fccdecbfa7bacb307fae8f5032d210c7257893900acc7ce2a0133e5c8
oompah.lifecycle_revision: 1
---
## Summary

Triggered by: TRICKLE-118

Bug observed live on Trickle 2026-08-13. GitLab merge request !6 for TRICKLE-118 is open, mergeable, and its exact-head pipeline 62464633 succeeded, but GitLab's list merge requests response omitted head_pipeline. GitLabProvider.list_open_reviews therefore emitted an empty/unknown ci_status; the durable review workflow repeatedly projected review.ci_pending, kept TRICKLE-118 in In Review, occupied the configured 1/1 review capacity, and blocked seven standalone Ready tasks indefinitely. Scope: make the forge-neutral review observation resolve CI for the exact MR head when the list/detail payload lacks a conclusive head_pipeline verdict, using the existing get_ci_status_for_sha/pipeline API contract without confusing unavailable evidence with successful empty results. Preserve exact-head fencing, bounded provider calls, GitHub behavior, capability warnings, webhook/polling convergence, and fail-closed behavior for ambiguous or changing heads. Required tests: self-managed GitLab open MR list omits head_pipeline while exact-head pipeline is passed/failed/pending/unknown; only the matching immutable head controls review progression; transport/403/429/malformed responses stay retryable and do not falsely merge; a successful fallback releases review capacity and allows dependent Ready work to advance. Acceptance: live TRICKLE-118 no longer remains review.ci_pending after its successful exact-head pipeline, and no manual refresh or status edit is needed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

