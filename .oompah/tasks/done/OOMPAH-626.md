---
id: OOMPAH-626
type: bug
status: Done
priority: 1
title: Supersede in-flight terminal audits when evidence changes
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:02:35.998442Z'
updated_at: '2026-08-03T20:04:55.788216Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-626
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-626
  base_branch: epic-OOMPAH-585
  base_sha: 5c45358226b238c1c9c2bdeee8bf9c85489d6f19
  updated_at: '2026-07-30T22:11:44.007859+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-81d39d73e735: '2026-07-30T22:17:01.599562+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-333c2faea4fe
    project_id: proj-14849f1b
    task_id: OOMPAH-626
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 22bd0cf1b2145c87857e1fb9e20bc5a87268bf2002340c937f33efe33eb43a4b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:28:40.031817+00:00'
    applied: true
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
    reconciled_at: '2026-08-03T20:04:53.228433+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-626
    target_state: Merged
    evidence_fingerprint: 22bd0cf1b2145c87857e1fb9e20bc5a87268bf2002340c937f33efe33eb43a4b
    audit_ids:
    - audit-f30cc257120d
    kind: override
    applied: false
    retired_at: '2026-08-02T18:28:48.296763+00:00'
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
  oompah.terminal_audit_result_intents: []
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-626
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-626 to Merged: parent epic
      OOMPAH-585 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-f30cc257120d
    created_at: '2026-08-03T20:04:53.228433+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f30cc257120d
    project_id: proj-14849f1b
    task_id: OOMPAH-626
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bb45021285ea3083ae52600f71d87eeb03507a993e90fb38e27235ce2a4af9ee
    attempts:
    - version: 1
      attempt_id: attempt-81d39d73e735
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: bb45021285ea3083ae52600f71d87eeb03507a993e90fb38e27235ce2a4af9ee
      created_at: '2026-07-30T22:11:39.206396+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T22:11:39.206396+00:00'
      branch_key: OOMPAH-626
      verdict: pass
      completed_at: '2026-07-30T22:17:01.599429+00:00'
      ended_at: '2026-07-30T22:17:01.599429+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T22:11:25.573500+00:00'
    updated_at: '2026-07-30T22:17:01.599429+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-81d39d73e735
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bb45021285ea3083ae52600f71d87eeb03507a993e90fb38e27235ce2a4af9ee
    created_at: '2026-07-30T22:11:39.206396+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T22:11:39.206396+00:00'
    branch_key: OOMPAH-626
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-626
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 467
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 6
      output_tokens: 467
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 467
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:18:36.245171+00:00'
---
## Summary

Implementation scope: update TerminalTransitionCoordinator transition staging so a new request for the same target with a changed evidence fingerprint supersedes an existing in-progress audit record as well as pending and completed records. The old worker may finish, but its result must fail the existing audit-id/state/fingerprint CAS and must never apply a terminal state to stale evidence. Preserve coalescing for identical evidence and the ordered Done/Merged/Archived chain contract. Relevant context: OOMPAH-591 gained audit-0e821c979fd2 while audit-85eb5879d029 was still in progress; recovery later changed the old record back to pending, leaving two eligible Done audits with different fingerprints. Tests: reproduce staging changed evidence over an in-progress record, verify only the fresh record remains eligible, verify a late result for the superseded record is rejected, and run focused coordinator/dispatcher tests plus the Makefile gate. Acceptance criteria: one active audit per target/evidence revision; stale in-flight results cannot close the task; focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 22:03
---
Fixed the changed-evidence race: transition staging now supersedes matching in-progress records, leaving only the fresh revision eligible. The existing result CAS rejects a late verdict from the superseded worker. Verification: 144 focused transition/auditor/override tests passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 22:03
---
Supersede in-progress audits on changed evidence and reject stale late verdicts through the existing CAS.
---
author: oompah
created: 2026-07-30 22:06
---
Extended the fix to the exact persisted OOMPAH-591 shape: identical in-progress requests now coalesce instead of duplicating, and coalescing a fresh record repairs older active records with stale fingerprints by superseding them. Verification now covers 152 transition/dispatch/override/archive tests plus the terminal mutation scan.
---
author: oompah
created: 2026-07-30 22:06
---
Supersede changed in-flight evidence, coalesce identical in-progress requests, and self-heal stale duplicate revisions.
---
author: oompah
created: 2026-07-30 22:11
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 22:11
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 22:11
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 22:12
---
Auditor handoff: exact task head 7576453f passed the complete integration Makefile gate before absorption at epic head 5c4535822. Focused evidence is 152 passing transition/dispatch/override/archive tests plus a passing terminal mutation scan. Read-only command denials are expected; inspect the committed CAS regressions and submit the structured verdict without rerunning the complete suite.
---
author: oompah
created: 2026-07-30 22:17
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 5c45358226b238c1c9c2bdeee8bf9c85489d6f19
- focused_tests_passed: 492
- targeted_supersede_tests_passed: 5
- coordinator_tests_passed: 106
- changed_files: oompah/terminal_transition_coordinator.py, tests/test_terminal_transition_coordinator.py
- commits: 7420c1984 (supersede stale in-flight audits); 5c45358226 (coalesce active audit revisions safely)
---
author: oompah
created: 2026-07-30 22:18
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 105, Tool calls: 83
- Tokens: 6 in / 467 out [473 total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 56s
- Log: OOMPAH-626__20260730T221148Z.jsonl
---
author: oompah
created: 2026-08-02 18:28
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
author: oompah
created: 2026-08-03 20:04
---
Lifecycle reconciliation restored OOMPAH-626 to audited Done: Cannot transition shared-epic child OOMPAH-626 to Merged: parent epic OOMPAH-585 could not be verified. The parent review must land on its configured target branch first.
---
<!-- COMMENTS:END -->
