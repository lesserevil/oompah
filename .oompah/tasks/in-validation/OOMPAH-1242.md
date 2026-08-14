---
id: OOMPAH-1242
type: task
status: In Validation
priority: null
title: Retire nested topology repair when exact rebase helper owns the branch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:32:41.192085Z'
updated_at: '2026-08-14T07:41:19.871225Z'
work_branch: OOMPAH-1242
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 17b045c2-9045-4892-be53-3eac67d25256
  request_fingerprint: 4e8f025d5976a94cb2d61527c19326a04aac0e16daf6d281733a3e92c80ba605
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1242
  head_sha: f10263212cf4f759f81fd2fd034ce383956dfd8f
  submitted_at: '2026-08-13T14:44:09.735151+00:00'
  updated_at: '2026-08-13T14:44:09.735151+00:00'
oompah.work_branch: OOMPAH-1242
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-eea5cc7b7be5
    project_id: proj-14849f1b
    task_id: OOMPAH-1242
    digest: fc85e2fc2123055f28b8967c545a620c690793e6fd88b2612b8ecd86a4d7f07f
  - version: 1
    audit_id: audit-cd00c25c22be
    project_id: proj-14849f1b
    task_id: OOMPAH-1242
    digest: fc85e2fc2123055f28b8967c545a620c690793e6fd88b2612b8ecd86a4d7f07f
  oompah.terminal_override_records:
  - version: 1
    override_id: override-94a601de302f
    project_id: proj-14849f1b
    task_id: OOMPAH-1242
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc85e2fc2123055f28b8967c545a620c690793e6fd88b2612b8ecd86a4d7f07f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #868 merged as 83196da17 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:41:18.513705+00:00'
    selected_ref: f10263212cf4f759f81fd2fd034ce383956dfd8f
    selected_sha: f10263212cf4f759f81fd2fd034ce383956dfd8f
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-eea5cc7b7be5
    project_id: proj-14849f1b
    task_id: OOMPAH-1242
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc85e2fc2123055f28b8967c545a620c690793e6fd88b2612b8ecd86a4d7f07f
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T15:14:45.768219+00:00'
    eligible_at: '2026-08-13T15:14:45.768219+00:00'
    selected_ref: f10263212cf4f759f81fd2fd034ce383956dfd8f
    selected_sha: f10263212cf4f759f81fd2fd034ce383956dfd8f
  - version: 1
    audit_id: audit-cd00c25c22be
    project_id: proj-14849f1b
    task_id: OOMPAH-1242
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc85e2fc2123055f28b8967c545a620c690793e6fd88b2612b8ecd86a4d7f07f
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T15:14:45.768219+00:00'
    prerequisite_audit_id: audit-eea5cc7b7be5
    selected_ref: f10263212cf4f759f81fd2fd034ce383956dfd8f
    selected_sha: f10263212cf4f759f81fd2fd034ce383956dfd8f
  attempt_history: []
---
## Summary

Scope: fix restart recovery and durable nested-dispatch repair execution so an exact server-authorized epic-rebase helper never remains blocked by, or keeps retrying, an ordinary nested topology fast-forward repair for the branch it exclusively owns. Current live reproduction: TRICKLE-141 gained exact rebase authority for persisted source TRICKLE-130, but workflow job 16757 remained retry_wait because startup recovery calls raw topology collection and reports unique commits. Update the recovery/claim paths to revalidate exact helper publish authority and atomically cancel or supersede obsolete topology jobs before implementation admission. Relevant code: Orchestrator._recover_nested_dispatch_repairs_on_startup, _drive_nested_dispatch_repair, _preflight_nested_epic_dispatch, and durable workflow job wake/reconciliation. Tests must reproduce restart with an existing retry_wait topology row, prove exact-authority helpers retire it without attempting advance_nested_dispatch_topology, prove title-shaped helpers remain fenced, and prove implementation dispatch can then rearm. Acceptance: no retrying topology row remains for an exact helper, no direct SQLite/operator repair is needed, and the helper naturally returns to a runnable workflow decision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 14:40
---
Implemented exact-authority retirement in both startup recovery and the post-claim race boundary. An exact epic-rebase helper now cancels its obsolete nested topology repair before any fast-forward mutation; ordinary/title-shaped tasks remain fenced. Added restart and claim-race regressions. Focused suite: 103 passed; terminal mutation and secret scans passed.
---
author: oompah
created: 2026-08-13 14:44
---
Implemented exact-helper authority retirement for legacy nested-topology repair and shutdown-safe epic event routing. Regression coverage passes (103 focused tests); PR #868 is under hosted review.
---
author: oompah
created: 2026-08-13 15:14
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
