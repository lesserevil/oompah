---
id: OOMPAH-942
type: bug
status: Done
priority: 1
title: Backfill trusted terminal-parent heads for pruned epic targets
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:26.152660Z'
updated_at: '2026-08-10T01:13:11.447130Z'
work_branch: OOMPAH-942
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-942
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: dcda220c225eef11f4704f61cade067d609e2da9
  submitted_at: '2026-08-09T10:04:18.080825+00:00'
  updated_at: '2026-08-09T10:04:18.080825+00:00'
oompah.work_branch: OOMPAH-942
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-b8deaf092ff9
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
  - version: 1
    audit_id: audit-16b8d9c8019f
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-942","audit-b8deaf092ff9","attempt-e3e223790931"]': '2026-08-09T14:25:16.041446+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-942
    target_state: Done
    evidence_fingerprint: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    audit_ids:
    - audit-b8deaf092ff9
    kind: override
    applied: true
    retired_at: '2026-08-09T14:25:16.041466+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-942
    audit_id: audit-b8deaf092ff9
    attempt_id: attempt-e3e223790931
    target_state: Done
    evidence_fingerprint: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    status: Needs CI Fix
    audit_ids:
    - audit-b8deaf092ff9
    kind: result
    applied: true
    created_at: '2026-08-09T14:25:16.041480+00:00'
    applied_at: '2026-08-09T14:25:22.904093+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-86de5b476c6d
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Exact task head dcda220c225eef11f4704f61cade067d609e2da9 was independently
      reviewed, merged in PR #754 as 90452d6647d132a069dd5bdac4ac8077233aa52e, and
      authoritatively contained in the OOMPAH-940 combined tree that passed hosted
      Python 3.11/3.12/3.13. The failed historical audit recorded 18,892 passing tests
      and only the known nested quality-gate Python-path infrastructure failures already
      covered by OOMPAH-831/OOMPAH-862; no task-code failure.'
    created_at: '2026-08-09T14:42:20.145908+00:00'
    selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
    selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
    applied: true
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done work is complete, but current parent-landing evidence
      cannot be reconstructed safely enough to promote it to Merged; retain immutable
      terminal provenance and retire reassessment.
    marked_at: '2026-08-10T01:13:09.857002+00:00'
    updated_at: '2026-08-10T01:13:09.857002+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done work is complete, but current parent-landing
        evidence cannot be reconstructed safely enough to promote it to Merged; retain
        immutable terminal provenance and retire reassessment.
      recorded_at: '2026-08-10T01:13:09.857002+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b8deaf092ff9
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    attempts:
    - version: 1
      attempt_id: attempt-e3e223790931
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
      created_at: '2026-08-09T14:02:05.192902+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:02:05.192902+00:00'
      branch_key: OOMPAH-942
      selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
      selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
      verdict: fail
      failure_classification: ci_failure
      completed_at: '2026-08-09T14:25:16.041318+00:00'
      ended_at: '2026-08-09T14:25:16.041318+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:52:43.120907+00:00'
    selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
    selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
    updated_at: '2026-08-09T14:25:16.041318+00:00'
  - version: 1
    audit_id: audit-16b8d9c8019f
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: oompah-workflow-rollup
      source: integrator
    previous_state: Done
    created_at: '2026-08-10T00:11:08.807589+00:00'
    selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
    selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
  attempt_history:
  - version: 1
    attempt_id: attempt-e3e223790931
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    created_at: '2026-08-09T14:02:05.192902+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:02:05.192902+00:00'
    branch_key: OOMPAH-942
    selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
    selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 328
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 328
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 328
    cost_usd: 0.0
    recorded_at: '2026-08-09T14:26:26.586001+00:00'
---
## Summary

Fourteen resolver-shaped legacy child rows have exact source authority but target pruned epic refs; terminal parents such as OOMPAH-460/585/586/587/588/619 have no accepted exact head, so exact landing evidence remains unavailable. Scope: define and persist a one-time/restart-safe backfill from authoritative parent integration receipts, accepted terminal audit provenance, or exact forge landing evidence; never infer from branch names or current main. Feed the resulting immutable accepted parent head into IntegrationLandingRequestResolver/GitLandingCollector. Tests: each authoritative source, missing/ambiguous/conflicting evidence, pruned branch, restart idempotence, and no mutation of historical jobs. Acceptance: qualifying children prove ancestry/complete patch equivalence against the accepted parent head; unknown parents remain actionable and fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:32
---
Implemented/pushed 1b50116ce. Terminal-parent exact heads now backfill from existing immutable landing facts, integrated queue receipts, exact completed audit bindings, or route-matching merged-review heads; the selected proof is persisted before child use and ambiguity, wrong targets, malformed authority, or persistence failure remain fail-closed. Focused integration/runtime result: 153 passed; targeted undefined-name lint passed.
---
author: oompah
created: 2026-08-09 09:32
---
Backfilled and persisted exact terminal-parent heads with fail-closed legacy authority selection; 153 focused tests pass.
---
author: oompah
created: 2026-08-09 09:54
---
Independent review found and fixed a source-authority gap before integration: exact terminal-audit parent backfill now requires the persisted audit binding to match the parent source branch (or an equal immutable revision), and malformed or wrong-ref authority blocks lower-priority fallback. Added a wrong-source fail-closed regression. Verification: 154 integration/runtime tests passed; mutation and secret scans passed.
---
author: oompah
created: 2026-08-09 09:54
---
Backfilled trusted terminal-parent heads only from exact route-bound authority; independent review fix binds terminal-audit proof to the parent source branch. 154 focused tests pass.
---
author: oompah
created: 2026-08-09 09:55
---
Backfilled trusted terminal-parent heads only from exact route-bound authority; independent review fix binds terminal-audit proof to the parent source branch. Exact head 53799805c; 154 focused tests pass.
---
author: oompah
created: 2026-08-09 10:04
---
Second independent review completed before integration. Fixed two additional authority gaps: terminal-audit parent receipts must match the current canonical issue evidence fingerprint, and simultaneous queue/audit/forge exact receipts must agree on one revision before any backfill is persisted. Added stale pre-edit audit and cross-authority conflict regressions. Verification: 156 integration/runtime tests passed; mutation/secret scans and targeted Ruff passed. Exact head dcda220c2.
---
author: oompah
created: 2026-08-09 10:04
---
Persist only one exact route-bound terminal-parent head after current-fingerprint and cross-authority agreement. Exact head dcda220c2; 156 focused tests pass.
---
author: oompah
created: 2026-08-09 12:52
---
Reconciled the in-flight integration deadlock: the accepted task commits are authoritatively contained in origin/epic-OOMPAH-940, so the exhausted administrative integration job is obsolete. Advancing to terminal validation while OOMPAH-958 fixes the systemic lease contract.
---
author: oompah
created: 2026-08-09 12:52
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:02
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:02
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 14:25
---
Audit FAIL — ci failure. Routing task to Needs CI Fix.

[REDACTED]
---
author: oompah
created: 2026-08-09 14:26
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 28, Tool calls: 7
- Tokens: 10 in / 328 out [338 total]
- Cost: $0.0000
- Exit: normal, Duration: 24m 17s
- Log: OOMPAH-942__20260809T140224Z.jsonl
---
author: oompah
created: 2026-08-09 14:42
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Exact task head dcda220c225eef11f4704f61cade067d609e2da9 was independently reviewed, merged in PR #754 as 90452d6647d132a069dd5bdac4ac8077233aa52e, and authoritatively contained in the OOMPAH-940 combined tree that passed hosted Python 3.11/3.12/3.13. The failed historical audit recorded 18,892 passing tests and only the known nested quality-gate Python-path infrastructure failures already covered by OOMPAH-831/OOMPAH-862; no task-code failure.
---
<!-- COMMENTS:END -->
