---
id: OOMPAH-1227
type: task
status: Open
priority: null
title: Hydrate immutable GitLab MR identity before review merge
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:16:04.050669Z'
updated_at: '2026-08-13T09:16:23.219875Z'
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
  creation_marker: 7ebb5290-c5a2-488e-9586-76491c07d68c
  request_fingerprint: 344cc165d4c7e22ad84d51c59e84eaa4c68fa512d3bfc1da15c5cc44f2e06548
oompah.lifecycle_revision: 1
---
## Summary

Bug: GitLab merge-request list responses can omit diff_refs/base_sha (as observed live on TRICKLE-118 MR !6) even when the MR detail endpoint contains an exact immutable base SHA. GitLabProvider.list_open_reviews then publishes base_sha='', while the accepted IntegrationRecord has a valid base SHA. ProductionReviewWorkflowBackend._exact_identity correctly rejects the merge, but the resulting non-retryable stale_evidence exhaustion strands a successful, mergeable review and consumes review capacity. Implementation scope: update oompah/scm.py GitLab review collection to hydrate missing immutable MR detail fields from GET /projects/:id/merge_requests/:iid without weakening repository/source/head/base identity checks; preserve list fast paths and explicit unavailable semantics. Add regression tests in tests/test_scm.py and/or tests/test_gitlab_review_flows.py proving a list item missing diff_refs/base_sha is enriched from detail, exact head/base/repository identity reaches merge admission, and detail failure remains fail-closed rather than inventing identity. Acceptance: TRICKLE-118's exact successful MR can proceed without operator identity override, existing embedded-field paths avoid unnecessary calls, focused SCM/review tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 09:16
---
Claimed directly for live scheduling recovery. Reproduced on TRICKLE-118: GitLab MR list evidence reported exact head and successful CI but blank base_sha; MR detail reports base_sha 983b2f1f…. The review_merge job exhausted stale_evidence and left the project review slot blocked. Implementing fail-closed detail hydration now.
---
<!-- COMMENTS:END -->
