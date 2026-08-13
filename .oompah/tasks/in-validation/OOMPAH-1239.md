---
id: OOMPAH-1239
type: task
status: In Validation
priority: null
title: Bypass recursive topology preflight for authoritative epic-rebase helpers
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T13:08:46.480588Z'
updated_at: '2026-08-13T13:32:28.808935Z'
work_branch: OOMPAH-1239
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 1b3db1dd-b180-4102-a9bc-eb256db75f99
  request_fingerprint: 3ed5ff688af9b0650b3f1f817da53b242acba07da3d9ef6ebdfb6c4129606c78
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1239
  head_sha: f8d9349aee9aeb493a676bd56bdceca289d7aaa7
  submitted_at: '2026-08-13T13:12:58.318256+00:00'
  updated_at: '2026-08-13T13:12:58.318256+00:00'
oompah.work_branch: OOMPAH-1239
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-8c6b39a675b3
    project_id: proj-14849f1b
    task_id: OOMPAH-1239
    digest: 78fa9e5f8fc26fc487661c116d3f107f00eaaaf8cda79ac7c9f9703cfefa8351
  - version: 1
    audit_id: audit-867d863001bd
    project_id: proj-14849f1b
    task_id: OOMPAH-1239
    digest: 78fa9e5f8fc26fc487661c116d3f107f00eaaaf8cda79ac7c9f9703cfefa8351
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8c6b39a675b3
    project_id: proj-14849f1b
    task_id: OOMPAH-1239
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 78fa9e5f8fc26fc487661c116d3f107f00eaaaf8cda79ac7c9f9703cfefa8351
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T13:32:23.382593+00:00'
    eligible_at: '2026-08-13T13:32:23.382593+00:00'
    selected_ref: f8d9349aee9aeb493a676bd56bdceca289d7aaa7
    selected_sha: f8d9349aee9aeb493a676bd56bdceca289d7aaa7
  - version: 1
    audit_id: audit-867d863001bd
    project_id: proj-14849f1b
    task_id: OOMPAH-1239
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 78fa9e5f8fc26fc487661c116d3f107f00eaaaf8cda79ac7c9f9703cfefa8351
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T13:32:23.382593+00:00'
    prerequisite_audit_id: audit-8c6b39a675b3
    selected_ref: f8d9349aee9aeb493a676bd56bdceca289d7aaa7
    selected_sha: f8d9349aee9aeb493a676bd56bdceca289d7aaa7
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

Live scheduling bug observed after deploying OOMPAH-1237: exact-authority helper TRICKLE-141 now passes branch-pattern validation, but its implementation_start remains deferred while nested_dispatch_topology_repair reports that parent branch TRICKLE-130 has unique commits. This is a recursive deadlock: TRICKLE-141 exists specifically to rebase TRICKLE-130 onto authoritative parent epic-TRICKLE-127, so requiring that topology to already be repaired before dispatch prevents the repair. Implementation scope: in oompah/orchestrator.py, exempt only an exact server-authority-backed epic-rebase helper from ordinary nested-dispatch topology preflight while retaining authority, target, workspace, and publish validation; do not exempt ordinary nested children or forged/title-shaped tasks. Add focused regression tests in tests/test_release_pick_validation.py and/or nested-dispatch tests. Acceptance: TRICKLE-141 dispatches to the direct epic maintenance workspace; forged and ordinary nested tasks remain topology-fenced; existing topology and epic-rebase tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 13:09
---
Claimed directly from live TRICKLE-141 scheduling. Implementing the narrow exact-authority bypass now; only Trickle remains resumed.
---
author: oompah
created: 2026-08-13 13:12
---
Implemented exact publish-authority bypass for the recursive nested-topology preflight. Ordinary and title-shaped helpers remain fenced. 183 focused tests pass; terminal mutation and secret scans pass. Commit f8d9349ae pushed.
---
author: oompah
created: 2026-08-13 13:13
---
Exact-authority epic-rebase helpers no longer require their own completed rebase as a dispatch prerequisite; ordinary nested children remain topology-fenced. Tests/scans pass; f8d9349ae pushed.
---
author: oompah
created: 2026-08-13 13:32
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
