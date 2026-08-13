---
id: OOMPAH-1223
type: task
status: Backlog
priority: null
title: Block nested child dispatch until inferred parent hierarchy is dispatchable
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T07:08:25.770498Z'
updated_at: '2026-08-13T07:08:25.770498Z'
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
  creation_marker: 61f0d7b2-4ea4-49b9-b849-6b612fb4815b
  request_fingerprint: 9864e04fd65f31463c553e326207516f963ec46c2898d76407f6279da6ba9829
---
## Summary

Bug observed live on Trickle 2026-08-13. TRICKLE-138 and TRICKLE-139 are Open children of TRICKLE-130, an inferred rollup parent (issue_type feature) that is itself Backlog beneath top-level epic TRICKLE-127. evaluate_task reports both children dispatch.eligible and materializes implementation_start, but the authoritative implementation preflight resolves TRICKLE-130 as a nested epic and rejects every attempt with nested_lineage_unavailable because enforce-mode shared target facts for the Backlog parent are incomplete. These deterministic policy rejections consume all five substantive attempts, create retry.exhausted alerts, then get regenerated and repeat. Scope: make shared workflow decision facts and nested-dispatch admission use one hierarchy contract for inferred rollup parents; a child whose immediate/ancestor rollup is Backlog or otherwise lacks dispatchable target authority must be projected as a non-substantive blocked/waiting decision before implementation_start is materialized. If a topology read can transiently become unavailable after admission, return an administrative deferral rather than consuming implementation attempts. Preserve hard-start, exact topology generation, nested rebase repair, and fail-closed behavior for malformed/cyclic/cross-project hierarchies. Required tests: production-shaped feature->feature->task hierarchy with parent/root Backlog; Open child does not enqueue/claim implementation and has truthful non-action-required wait; promotion of required hierarchy resumes exactly once; transient topology unavailability preserves attempt budget; genuine provider/workspace failures still exhaust. Acceptance: live TRICKLE-138/139 no longer oscillate through nested_lineage_unavailable exhaustion and flow naturally once their parent hierarchy is promoted.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

