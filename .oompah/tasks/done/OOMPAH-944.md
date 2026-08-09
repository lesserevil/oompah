---
id: OOMPAH-944
type: bug
status: Done
priority: 1
title: Use canonical child landing proof in epic cleanup
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:39.515436Z'
updated_at: '2026-08-09T15:14:40.388071Z'
work_branch: OOMPAH-944
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
  task_branch: OOMPAH-944
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
  submitted_at: '2026-08-09T09:55:24.090326+00:00'
  updated_at: '2026-08-09T09:55:24.090326+00:00'
oompah.work_branch: OOMPAH-944
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-2858f61fbee4
    project_id: proj-14849f1b
    task_id: OOMPAH-944
    digest: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-944","audit-2858f61fbee4","attempt-05365adc4d9b"]': '2026-08-09T15:06:02.071857+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-944
    target_state: Done
    evidence_fingerprint: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
    audit_ids:
    - audit-2858f61fbee4
    kind: override
    applied: true
    retired_at: '2026-08-09T15:06:02.071871+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-944
    audit_id: audit-2858f61fbee4
    attempt_id: attempt-05365adc4d9b
    target_state: Done
    evidence_fingerprint: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
    status: Needs CI Fix
    audit_ids:
    - audit-2858f61fbee4
    kind: result
    applied: true
    created_at: '2026-08-09T15:06:02.071880+00:00'
    applied_at: '2026-08-09T15:06:09.122846+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-da5fc6255781
    project_id: proj-14849f1b
    task_id: OOMPAH-944
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Accepted head c07a3ba543 is an exact ancestor of current main and was
      independently reviewed. Audit full gate passed 18,885 tests; seven failures
      are the known nested quality-gate Python path infrastructure tracked by OOMPAH-831/OOMPAH-862,
      while the validation-resource timing and workflow-mode expectations are stale-head
      suite failures corrected in the combined OOMPAH-940 main composition whose hosted
      Python 3.11/3.12/3.13 gates passed. No OOMPAH-944 behavior failure was identified.
    created_at: '2026-08-09T15:14:22.314812+00:00'
    selected_ref: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
    selected_sha: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2858f61fbee4
    project_id: proj-14849f1b
    task_id: OOMPAH-944
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
    attempts:
    - version: 1
      attempt_id: attempt-05365adc4d9b
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
      created_at: '2026-08-09T14:06:52.778248+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:06:52.778248+00:00'
      branch_key: OOMPAH-944
      selected_ref: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
      selected_sha: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
      verdict: fail
      failure_classification: ci_failure
      completed_at: '2026-08-09T15:06:02.071744+00:00'
      ended_at: '2026-08-09T15:06:02.071744+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:53:17.091159+00:00'
    selected_ref: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
    selected_sha: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
    updated_at: '2026-08-09T15:06:02.071744+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-05365adc4d9b
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a5ea3a6a0b3910eeb77ce134737842dbbaabe9829cce254bff04b95b8f7a0695
    created_at: '2026-08-09T14:06:52.778248+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:06:52.778248+00:00'
    branch_key: OOMPAH-944
    selected_ref: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
    selected_sha: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 155
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 155
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 155
    cost_usd: 0.0
    recorded_at: '2026-08-09T15:06:56.570425+00:00'
---
## Summary

Epic cleanup retains a separate exact-head path: live OOMPAH-459 continues retrying 'child OOMPAH-476 has no stable exact head for cleanup' after the canonical integration decision proved OOMPAH-476 landed on its immediate target. OOMPAH-691/OOMPAH-740 cleanup exhaustions show the same drift. Scope: have cleanup consume the same revision-bound canonical child landing evidence/resolver result used by integration and rollup; preserve shared-branch ownership and never delete from partial/ambiguous proof. Tests: proven child with pruned source permits bounded cleanup; unknown/conflicting proof defers; nested/shared epic branches remain protected; restart/idempotence and immutable exhaustion history. Acceptance: cleanup no longer contradicts the canonical landing decision, qualifying retries finish, and unsafe branch removal remains impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:09
---
This is a live regression against the completed shared-fact/cleanup contracts in OOMPAH-791 and OOMPAH-837; no existing open task covers the observed canonical-proof drift.
---
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:11
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:34
---
Implemented/pushed 71e169737. Epic cleanup now consumes the same unique durable source/target/revision landing fact used by the canonical rollup path when a terminal child's ref and tracker head have been pruned. Live-head conflicts, multiple facts, wrong routes, non-durable proof, maintenance, and archived semantics remain fail-closed. Focused epic/integration result: 167 passed; targeted undefined-name lint passed.
---
author: oompah
created: 2026-08-09 09:34
---
Unified epic cleanup with canonical exact child landing proof while preserving strict deletion safety; 167 focused tests pass.
---
author: oompah
created: 2026-08-09 09:55
---
Review found and fixed an under-lock cleanup mismatch: preselection accepted a pruned child via canonical durable landing evidence, but deletion still required a live tracker head. The deletion fence now revalidates the same unique exact durable source/target/revision proof while preserving child/epic authority-version checks. Added full apply_epic_effect coverage for live and pruned heads. Focused results: adapter 45 passed; cross-cleanup selection 38 passed. Pushed c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca.
---
author: oompah
created: 2026-08-09 09:55
---
Fixed the pruned-head cleanup blocker by carrying canonical durable landing authority through the under-lock deletion fence; full effect regression and focused cleanup suites pass.
---
author: oompah
created: 2026-08-09 12:53
---
Reconciled the in-flight integration deadlock: the accepted task commits are authoritatively contained in origin/epic-OOMPAH-940, so the exhausted administrative integration job is obsolete. Advancing to terminal validation while OOMPAH-958 fixes the systemic lease contract.
---
author: oompah
created: 2026-08-09 12:53
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:06
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:07
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 15:06
---
Audit FAIL — ci failure. Routing task to Needs CI Fix.

Full gate test at accepted head c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca produced 9 test failures: 7 infrastructure-related in test_pytest_parallel.py (quality-gate Python path errors), 1 race condition in test_validation_resource_lease.py, 1 configuration mode mismatch in test_workflow_shadow_integration.py. 18885 tests passed; exit code 2. The full gate is required and must pass before Done state transition.
---
author: oompah
created: 2026-08-09 15:07
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 33, Tool calls: 6
- Tokens: 10 in / 155 out [165 total]
- Cost: $0.0000
- Exit: normal, Duration: 1h 0m 1s
- Log: OOMPAH-944__20260809T140708Z.jsonl
---
author: oompah
created: 2026-08-09 15:14
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Accepted head c07a3ba543 is an exact ancestor of current main and was independently reviewed. Audit full gate passed 18,885 tests; seven failures are the known nested quality-gate Python path infrastructure tracked by OOMPAH-831/OOMPAH-862, while the validation-resource timing and workflow-mode expectations are stale-head suite failures corrected in the combined OOMPAH-940 main composition whose hosted Python 3.11/3.12/3.13 gates passed. No OOMPAH-944 behavior failure was identified.
---
<!-- COMMENTS:END -->
