---
id: OOMPAH-968
type: bug
status: Done
priority: 1
title: Fence absent-to-retained provenance changes during workflow publication
parent: OOMPAH-940
children: []
blocked_by:
- OOMPAH-967
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T18:30:50.075307Z'
updated_at: '2026-08-09T19:52:53.298158Z'
work_branch: OOMPAH-968
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
  task_branch: OOMPAH-968
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
  submitted_at: '2026-08-09T19:25:00.003039+00:00'
  updated_at: '2026-08-09T19:25:00.003039+00:00'
oompah.work_branch: OOMPAH-968
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-283cac3bcd42
    project_id: proj-14849f1b
    task_id: OOMPAH-968
    digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
  - version: 1
    audit_id: audit-7c38826b083b
    project_id: proj-14849f1b
    task_id: OOMPAH-968
    digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d83112702b86
    project_id: proj-14849f1b
    task_id: OOMPAH-968
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-09T19:52:30.878415+00:00'
    selected_ref: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    selected_sha: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-968
    target_state: Done
    evidence_fingerprint: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
    audit_ids:
    - audit-283cac3bcd42
    - audit-7c38826b083b
    kind: override
    applied: true
    retired_at: '2026-08-09T19:52:43.358947+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-283cac3bcd42
    project_id: proj-14849f1b
    task_id: OOMPAH-968
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
    attempts:
    - version: 1
      attempt_id: attempt-1965bac73fae
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
      created_at: '2026-08-09T19:45:50.621302+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T19:45:50.621302+00:00'
      branch_key: OOMPAH-968
      selected_ref: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
      selected_sha: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T19:45:36.044266+00:00'
    selected_ref: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    selected_sha: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    updated_at: '2026-08-09T19:52:43.358905+00:00'
  - version: 1
    audit_id: audit-7c38826b083b
    project_id: proj-14849f1b
    task_id: OOMPAH-968
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T19:45:36.044266+00:00'
    selected_ref: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    selected_sha: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    updated_at: '2026-08-09T19:52:43.358932+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1965bac73fae
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39b867a8aede1bf98c7147263bcf00a2ae04dad470d1486db452a3caf4c13a5
    created_at: '2026-08-09T19:45:50.621302+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T19:45:50.621302+00:00'
    branch_key: OOMPAH-968
    selected_ref: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
    selected_sha: 6f3ee4170c16cbe273dca74e9512321b6c0cabfd
oompah.task_costs:
  total_input_tokens: 96
  total_output_tokens: 11
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 96
      output_tokens: 11
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 96
    output_tokens: 11
    cost_usd: 0.0
    recorded_at: '2026-08-09T19:52:46.529019+00:00'
---
## Summary

A workflow snapshot collected while a task has no terminal-provenance marker currently does not request the terminal-audit snapshot proof, so an authenticated owner can add a retained marker after collection but before publication and the stale delivery decision may still publish. Scope: make marker absence part of the exact terminal-provenance authority observed and revalidated for terminal Done-task publication, without turning ordinary absent metadata into an operator warning or changing healthy delivery behavior. Preserve the project write lock and workflow job-store publication fence; supersede and roll back any snapshot when provenance changes absent→retained before publication. Relevant code: oompah/orchestrator.py terminal-audit fact source, oompah/work_decision.py if representation changes, oompah/workflow_runtime.py proof selection/publication, and focused tests. Required regression: collect a normal Done-task landing-refresh decision with no marker, add an owner-retained marker immediately before publication, prove publication_authority_changed, no stale delivery authority is published, and no current job is incorrectly retired; retry must observe retained provenance and publish the zero-job terminal decision. Acceptance: absent, retained, and new-revision marker states are all exact publication authority; no malformed payload bypass exists; focused workflow/provenance tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 18:53
---
Implementation is pushed at 92ebd94c2 on OOMPAH-968, based on final OOMPAH-967 head 5adb50e55. Markerless Done tasks now project stable explicit absence authority; healthy absence preserves the normal landing decision, invalid/ambiguous absence fails closed, and the existing locked in-transaction proof detects absent-to-retained mutation. The production regression proves first publication supersedes and rolls back without retiring the exhausted row, then the retained retry publishes zero-job authority and retires it. Verification: 547 focused tests pass; critical Ruff/diff checks pass; three independent reviews are running.
---
author: oompah
created: 2026-08-09 19:03
---
Corrective exact head 514bc9e30 is pushed. A later audit-envelope read failure now preserves scoped malformed zero-job authority; impossible present/non-retained generation-zero markers fail closed in persistence and decision layers; and the runtime matrix proves clean absence publication, clean stale effect supersession/nonclaimability, retained retry, exhausted-row rollback/retirement, retained-to-revision supersession, and unchanged generation-1 publication. Verification: 553 focused tests pass; two independent final reviews report no blockers (189 selected tests plus acceptance review); critical Ruff/diff checks pass.
---
author: oompah
created: 2026-08-09 19:03
---
Exact head 514bc9e30 fences absent-to-retained provenance publication races, fails closed on audit-read and generation-zero edge cases, and proves clean/stale/exhausted convergence. 553 focused tests and two independent reviews are green.
---
author: oompah
created: 2026-08-09 19:06
---
Prior submission is superseded by pushed corrective head 285fc11fe. The supported absent-to-authorize-new-revision path now records the revising owner, reason, and timestamps on its generation-one marker, so the writer, adapter, decision, and publication proof agree. Added direct persistence, production adapter, and truly absent-to-authorize runtime coverage. Verification: 555 focused tests pass; critical Ruff/diff checks pass. Final independent re-reviews are in progress; do not integrate 514bc9e30.
---
author: oompah
created: 2026-08-09 19:09
---
Final exact head 277a99a1c is pushed. Revision and retention timestamps are now distinct: absent-to-authorize records owner/reason/updated_at with generation 1 and leaves marked_at empty until the first actual retain; retained facts still require a real mark timestamp. Verification: 557 focused tests pass; two independent final reviews report no blockers (one reran 193 relevant tests); critical Ruff/diff checks pass. This supersedes every prior submitted head and is the integration candidate.
---
author: oompah
created: 2026-08-09 19:09
---
Final exact head 277a99a1c closes absent-to-retained and absent-to-revision publication races with consistent owner/generation/timestamp authority. 557 focused tests and two independent final reviews are green.
---
author: oompah
created: 2026-08-09 19:25
---
Rebased the independently reviewed provenance-publication fence onto merged OOMPAH-967 without tree changes. Exact head 6f3ee4170c16cbe273dca74e9512321b6c0cabfd; 557 focused tests and three independent reviews are green.
---
author: oompah
created: 2026-08-09 19:25
---
Post-dependency integration head 6f3ee4170 is pushed on merged main c28022a79. The full tree is byte-identical to independently reviewed head 277a99a1c; only the four commit IDs changed during clean rebase. This is the new exact integration candidate.
---
author: oompah
created: 2026-08-09 19:36
---
Protected CI: Python 3.11 and 3.13 passed. Python 3.12 had one unrelated timing failure after 19,176 passes: detached effect heartbeat lease expiry was ~63 ms beyond the test assertion window. Rerunning the failed job and checking existing tracker coverage for the lease-heartbeat race; exact code head remains 6f3ee4170.
---
author: oompah
created: 2026-08-09 19:45
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 19:45
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 19:45
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 19:52
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: [REDACTED]
---
author: oompah
created: 2026-08-09 19:52
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 5
- Tokens: 96 in / 11 out [107 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 53s
- Log: OOMPAH-968__20260809T194603Z.jsonl
---
author: oompah
created: 2026-08-09 19:52
---
Absent-to-retained provenance publication fencing is integrated on main via PR #776; the exact protected matrix, focused tests, and independent reviews passed. Detached-auditor harness repair is tracked separately in OOMPAH-971.
---
<!-- COMMENTS:END -->
