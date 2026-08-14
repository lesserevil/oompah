---
id: OOMPAH-1227
type: task
status: Merged
priority: null
title: Hydrate immutable GitLab MR identity before review merge
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:16:04.050669Z'
updated_at: '2026-08-14T07:29:33.726703Z'
work_branch: OOMPAH-1227
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
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1227
  head_sha: 7887a5d9eb293c686e649dc70e275042a69ee70f
  submitted_at: '2026-08-13T09:47:21.308990+00:00'
  updated_at: '2026-08-13T09:47:21.308990+00:00'
oompah.work_branch: OOMPAH-1227
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-dcd196f20717
    project_id: proj-14849f1b
    task_id: OOMPAH-1227
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 66af1616c951ff2737e29c959515faf06dbb08e50130bd6ab80d3092b50cc336
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #856 merged as 04f76e840 with all hosted checks
      passing, and the landed tree is contained by origin/main; this stale Open projection
      requires no further implementation.'
    created_at: '2026-08-14T07:29:27.171052+00:00'
    selected_ref: 7887a5d9eb293c686e649dc70e275042a69ee70f
    selected_sha: 7887a5d9eb293c686e649dc70e275042a69ee70f
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-13 09:23
---
Implementation pushed and opened as PR #856. GitLab list responses missing immutable head/base evidence are hydrated through the exact MR detail endpoint; malformed/unavailable detail remains an unavailable observation. Focused GitLab SCM and review suites: 120 passed, 2 skipped. Hosted gates are running.
---
author: oompah
created: 2026-08-13 09:47
---
Hydrate incomplete GitLab merge-request identity from the exact detail endpoint and fail closed when immutable head/base identity remains unavailable. Focused provider tests and hosted CI on Python 3.11, 3.12, and 3.13 pass.
---
<!-- COMMENTS:END -->
