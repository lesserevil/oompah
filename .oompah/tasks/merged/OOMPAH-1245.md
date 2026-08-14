---
id: OOMPAH-1245
type: task
status: Merged
priority: null
title: Let durable recovery supersede stale legacy completion fences
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:50:06.067428Z'
updated_at: '2026-08-14T07:44:46.863181Z'
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
  creation_marker: bb86dbc1-ab9d-4037-9411-584095a6a09e
  request_fingerprint: 1e18cd3b9004114671d1096d0b56bd194ec13a61fee1e22960cc1cb9455ab236
oompah.lifecycle_revision: 2
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-1180ab9ea845
    project_id: proj-14849f1b
    task_id: OOMPAH-1245
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 929ff8ffd468a5860a76840d4c888a90c7a64a04f4a94047e0de4ce25fc7d720
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #868 merged as 83196da17 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:44:38.110590+00:00'
    selected_ref: origin/main
    selected_sha: 948ef6f207eabe4c26910d8fc276d6d36b659e76
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1245
    target_state: Merged
    evidence_fingerprint: 929ff8ffd468a5860a76840d4c888a90c7a64a04f4a94047e0de4ce25fc7d720
    workflow_revision: null
    selected_ref: origin/main
    selected_sha: 948ef6f207eabe4c26910d8fc276d6d36b659e76
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-14T07:44:45.636955+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Scope: fix the split-brain admission path where durable workflow facts schedule implementation_recovery for an orphaned In Progress task, but Orchestrator._should_dispatch rejects the exact recovery because the task ID remains in the legacy in-memory state.completed set. Live reproduction: TRICKLE-141 produced a valid local rebase candidate but could not publish it; after its worker exited, canonical state remained In Progress with no owner, implementation_recovery jobs 16837/16838 exhausted and 16842 retried with reason completed. Make exact durable recovery atomically clear or bypass only a demonstrably stale completed fence after fresh tracker/ownership revalidation; preserve the fence for terminal state, accepted submission, active owner/agent, and ordinary duplicate dispatch. Relevant code: implementation_workflow_adapter._admit_dispatch, Orchestrator._should_dispatch, watchdog stale-completed cleanup, and workflow recovery tests. Add regression coverage reproducing In Progress + no live owner + state.completed, proving recovery admission proceeds, while completed work with authoritative handoff remains fenced. Acceptance: no repeated implementation_recovery rows fail solely with completed for an ownerless In Progress task; the task either resumes with a scoped worker or transitions through its authoritative completion path without operator database repair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 14:50
---
Live evidence: TRICKLE-141 is canonical In Progress with no running agent; work decision schedules implementation_recovery, while jobs 16837 and 16838 exhausted and 16842 retried because _should_dispatch returned completed. The previous worker left rebased candidate 26bfa49ab18e34ce6660fcf62ef910a37a79fcbd on local TRICKLE-130 after scoped publish capability was unavailable.
---
author: oompah
created: 2026-08-13 14:56
---
Implemented on PR #868: exact durable recovery may release only an ownerless In Progress legacy completion fence. Accepted submissions, live owners, terminal/provenance fences, and ordinary dispatch remain blocked. Regression set: 4 focused admission tests plus 173 adjacent workflow tests pass; terminal mutation and secret scans pass.
---
author: oompah
created: 2026-08-14 07:44
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #868 merged as 83196da17 and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
