---
id: OOMPAH-1223
type: task
status: Merged
priority: null
title: Block nested child dispatch until inferred parent hierarchy is dispatchable
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T07:08:25.770498Z'
updated_at: '2026-08-14T07:36:02.854053Z'
work_branch: OOMPAH-1223
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 61f0d7b2-4ea4-49b9-b849-6b612fb4815b
  request_fingerprint: 9864e04fd65f31463c553e326207516f963ec46c2898d76407f6279da6ba9829
oompah.lifecycle_revision: 3
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1223
  head_sha: 9110278408b23f4ad74e33aa8367a4f12ce24045
  submitted_at: '2026-08-13T08:13:08.164084+00:00'
  updated_at: '2026-08-13T08:13:08.164084+00:00'
oompah.work_branch: OOMPAH-1223
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-7e7229dc7054
    project_id: proj-14849f1b
    task_id: OOMPAH-1223
    digest: 32c98be40957bc3783a01f698dcdf40f370d8d7e7ac5f2c27965d4323fdc8392
  - version: 1
    audit_id: audit-85843b9892dd
    project_id: proj-14849f1b
    task_id: OOMPAH-1223
    digest: 32c98be40957bc3783a01f698dcdf40f370d8d7e7ac5f2c27965d4323fdc8392
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8396f8c8c370
    project_id: proj-14849f1b
    task_id: OOMPAH-1223
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 32c98be40957bc3783a01f698dcdf40f370d8d7e7ac5f2c27965d4323fdc8392
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #853 merged as cb84fab5b and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:35:48.304903+00:00'
    selected_ref: 9110278408b23f4ad74e33aa8367a4f12ce24045
    selected_sha: 9110278408b23f4ad74e33aa8367a4f12ce24045
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1223
    target_state: Merged
    evidence_fingerprint: 32c98be40957bc3783a01f698dcdf40f370d8d7e7ac5f2c27965d4323fdc8392
    workflow_revision: null
    selected_ref: 9110278408b23f4ad74e33aa8367a4f12ce24045
    selected_sha: 9110278408b23f4ad74e33aa8367a4f12ce24045
    landing_revision: null
    audit_ids:
    - audit-7e7229dc7054
    - audit-85843b9892dd
    kind: override
    applied: true
    retired_at: '2026-08-14T07:36:01.108976+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-7e7229dc7054
    project_id: proj-14849f1b
    task_id: OOMPAH-1223
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 32c98be40957bc3783a01f698dcdf40f370d8d7e7ac5f2c27965d4323fdc8392
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T08:13:32.299869+00:00'
    eligible_at: '2026-08-13T08:13:32.299869+00:00'
    selected_ref: 9110278408b23f4ad74e33aa8367a4f12ce24045
    selected_sha: 9110278408b23f4ad74e33aa8367a4f12ce24045
    updated_at: '2026-08-14T07:36:01.108927+00:00'
  - version: 1
    audit_id: audit-85843b9892dd
    project_id: proj-14849f1b
    task_id: OOMPAH-1223
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 32c98be40957bc3783a01f698dcdf40f370d8d7e7ac5f2c27965d4323fdc8392
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T08:13:32.299869+00:00'
    prerequisite_audit_id: audit-7e7229dc7054
    selected_ref: 9110278408b23f4ad74e33aa8367a4f12ce24045
    selected_sha: 9110278408b23f4ad74e33aa8367a4f12ce24045
    updated_at: '2026-08-14T07:36:01.108956+00:00'
  attempt_history: []
---
## Summary

Bug observed live on Trickle 2026-08-13. TRICKLE-138 and TRICKLE-139 are Open children of TRICKLE-130, an inferred rollup parent (issue_type feature) that is itself Backlog beneath top-level epic TRICKLE-127. evaluate_task reports both children dispatch.eligible and materializes implementation_start, but the authoritative implementation preflight resolves TRICKLE-130 as a nested epic and rejects every attempt with nested_lineage_unavailable because enforce-mode shared target facts for the Backlog parent are incomplete. These deterministic policy rejections consume all five substantive attempts, create retry.exhausted alerts, then get regenerated and repeat. Scope: make shared workflow decision facts and nested-dispatch admission use one hierarchy contract for inferred rollup parents; a child whose immediate/ancestor rollup is Backlog or otherwise lacks dispatchable target authority must be projected as a non-substantive blocked/waiting decision before implementation_start is materialized. If a topology read can transiently become unavailable after admission, return an administrative deferral rather than consuming implementation attempts. Preserve hard-start, exact topology generation, nested rebase repair, and fail-closed behavior for malformed/cyclic/cross-project hierarchies. Required tests: production-shaped feature->feature->task hierarchy with parent/root Backlog; Open child does not enqueue/claim implementation and has truthful non-action-required wait; promotion of required hierarchy resumes exactly once; transient topology unavailability preserves attempt budget; genuine provider/workspace failures still exhaust. Acceptance: live TRICKLE-138/139 no longer oscillate through nested_lineage_unavailable exhaustion and flow naturally once their parent hierarchy is promoted.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 07:08
---
Claiming directly from the live Trickle incident. Workaround for in-flight tasks: keep their Open state and stop treating regenerated exhaustion as human action; after OOMPAH-1222 deployment I will implement the unified hierarchy admission fix, deploy it, and verify TRICKLE-138/139 resume only when the parent hierarchy has valid dispatch authority.
---
author: oompah
created: 2026-08-13 07:45
---
Implementation complete. Unified declared and inferred rollup classification across runtime partitioning, target facts, production handler revalidation, event routing, and restart seeding. Open leaves now project a jobless informational hierarchy wait until every ancestor has active authority; Backlog rollups advance through durable system-owned transitions; late topology races use a pre-effect administrative deferral without consuming attempts. Expanded focused suite: 526 passed; additional production-shaped hierarchy tests cover feature -> feature -> task, ancestor promotion, exactly-once leaf release, and free late-topology waits.
---
author: oompah
created: 2026-08-13 08:02
---
Hosted gate compatibility follow-up complete: fixed loose tracker doubles being misclassified as inferred rollups and preserved specific Open-rollup landing work ahead of aggregate status reconciliation while keeping Backlog hierarchy activation authoritative. All eight hosted failures now pass locally; expanded focused coverage is 893 passed. Corrected head 911027840 is pushed and full Python 3.11/3.12/3.13 gates are running.
---
author: oompah
created: 2026-08-13 08:13
---
Unified inferred and declared rollup authority across runtime partitioning, target facts, event routing, hierarchy admission, and restart recovery. Backlog ancestors now activate durably before descendants dispatch; late topology races defer without consuming retry attempts. Focused hierarchy/review compatibility coverage: 893 passed. Hosted full gates passed on Python 3.11, 3.12, and 3.13.
---
author: oompah
created: 2026-08-13 08:13
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:35
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #853 merged as cb84fab5b and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
