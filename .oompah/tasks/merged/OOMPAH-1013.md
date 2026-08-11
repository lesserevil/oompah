---
id: OOMPAH-1013
type: task
status: Merged
priority: null
title: Prevent cross-priority starvation in bounded terminal-audit health scans
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T03:11:11.351608Z'
updated_at: '2026-08-11T08:09:54.817182Z'
work_branch: OOMPAH-1013
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 1811b247-76cb-42e8-a581-6332fedb32d7
  request_fingerprint: a83e0074173ca57ca5cdc39b2a729c1c44644e24bed7a062c8e971c58bde77a3
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1013
  head_sha: fe63e237ffbc342ac6a147d1143477d49128df5f
  submitted_at: '2026-08-11T03:24:59.569845+00:00'
  updated_at: '2026-08-11T03:24:59.569845+00:00'
oompah.work_branch: OOMPAH-1013
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c4be13c271bc
    project_id: proj-14849f1b
    task_id: OOMPAH-1013
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 615350229177274e7f991b35e02543738bcd32329ebbceafabc9f98fc07de47b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #806 and hosted Python 3.11/3.12/3.13 gates are green; deployed
      build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 contains merge 62c3cda3ea602b614a3a3dfc92c66468b5c34a4b;
      independent audit verified that every exact reviewed branch change is patch-equivalent
      to or composition-equivalent with the protected merge and no unique branch changes
      remain.'
    created_at: '2026-08-11T08:09:34.809166+00:00'
    selected_ref: fe63e237ffbc342ac6a147d1143477d49128df5f
    selected_sha: fe63e237ffbc342ac6a147d1143477d49128df5f
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1013
    target_state: Merged
    evidence_fingerprint: 615350229177274e7f991b35e02543738bcd32329ebbceafabc9f98fc07de47b
    workflow_revision: null
    selected_ref: fe63e237ffbc342ac6a147d1143477d49128df5f
    selected_sha: fe63e237ffbc342ac6a147d1143477d49128df5f
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T08:09:44.727143+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: live OOMPAH-940 rollout diagnostics and the planned ~100-task dispatch load. Problem: Orchestrator._audit_candidate_window globally orders terminal-audit health candidates by priority, but cursor rotation is confined to the cursor priority group before the operation limit is applied. When higher-priority candidates fill the entire operation budget, lower-priority candidates can remain permanently outside every bounded slice, so candidate_scan_complete never becomes true and rollout health can remain degraded indefinitely despite continuation ticks. A read-only reproduction with eight priority-1 candidates, one priority-0 candidate, and operation limit 8 scanned HIGH-0..HIGH-7 for four consecutive cycles and never selected LOW-0. Scope: make bounded terminal-audit health traversal fair across priority groups while preserving priority ordering for actual auditor dispatch, deterministic cursor/restart behavior, candidate-key-set resets, continuation coalescing, and the operation/time budgets. Relevant code: Orchestrator._audit_candidate_window and bounded health scan accounting in oompah/orchestrator.py; observability regressions in tests/test_terminal_audit_observability.py. Required tests: mixed-priority corpus where the high-priority group fills the cap still selects every lower-priority candidate within a bounded number of slices; cursor persistence/restart continues rather than resets; candidate additions/removals reset safely; actual auditor dispatch priority is unchanged; no scan-error/action-required alert is emitted for ordinary continuation. Acceptance: a stable mixed-priority corpus completes a health cycle under an operation limit smaller than the high-priority group, with exact bounded work per slice and no lower-priority starvation; focused tests, the final combined Makefile gate, and live rollout canary pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 03:12
---
Implementation started on branch OOMPAH-1013. I will separate fair bounded health traversal from strict-priority auditor dispatch, add mixed-priority operation-cap/restart/corpus-reset/dispatch-order regressions, run focused checks plus the terminal mutation scan, then push the exact reviewed head.
---
author: oompah
created: 2026-08-11 03:24
---
Implemented the bounded-fair terminal-audit health traversal while preserving strict-priority launch order. Added regressions for mixed-priority operation caps, restart durability, candidate-corpus reset, and actual dispatch ordering. Focused observability suite: 78 passed. Terminal mutation scan: 21/21 allowlisted.
---
author: oompah
created: 2026-08-11 03:25
---
Implemented globally fair bounded terminal-audit health traversal while preserving strict-priority launch ordering. Added mixed-priority operation-cap, restart, corpus-reset, and actual dispatch-order regressions. Focused suite 78 passed; terminal mutation scan passed 21/21. Pushed fe63e237ffbc342ac6a147d1143477d49128df5f.
---
author: oompah
created: 2026-08-11 03:29
---
Independent review BLOCKED fe63e237f on a mixed-priority runtime-partial livelock: launch-priority reordering could repeatedly read HIGH-0 while the health cursor waited for an earlier LOW item, leaving seen_count stuck. Rework is directly owner-claimed in Needs CI Fix; an exact regression reproduces repeated runtime_limit ticks and the repair will keep health reads in fair traversal order while applying a separate launch-eligibility fence.
---
author: oompah
created: 2026-08-11 03:30
---
Addressed review BLOCK at follow-up head 2b2384f043a3ad6b6106019efab3875acae73b50. Runtime-partial health scans now process the durable traversal order and separately fence lower-priority launches until higher candidates have been considered. Exact regression proves the first partial tick advances LOW with no launch, then the next tick completes health and launches HIGH before LOW. Focused suite: 78 passed; terminal mutation scan: 21/21 allowlisted.
---
author: oompah
created: 2026-08-11 03:37
---
Addressed the second review BLOCK at 4e5621853df5e27b9b6cc54ef069de4c50922ad0. A fully observed slice now queues one cursor-rebased priority revisit when a lower pending audit was deferred only because in-slice higher candidates had not yet been examined and capacity remains. Higher candidates outside the slice do not create this continuation. Regression proves HIGH/no-record then LOW/pending launches LOW on the next continuation instead of idling. Focused suite: 79 passed; mutation scan: 21/21.
---
author: oompah
created: 2026-08-11 03:38
---
Independent re-review ACCEPTED exact head 4e5621853df5e27b9b6cc54ef069de4c50922ad0. The reviewer reproduced and cleared both adversarial cases: runtime-partial mixed-priority health now advances and completes; a pending lower-priority audit gets a one-shot cursor revisit and launches after higher-priority work proves non-launchable. Higher candidates outside the bounded slice do not trigger a revisit loop. Three exact adversarial tests and 79 focused observability tests pass. The complete repair series is composed at recovery head 80ad800a6, where all 1,712 changed-path tests pass.
---
author: oompah
created: 2026-08-11 08:09
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Protected PR #806 and hosted Python 3.11/3.12/3.13 gates are green; deployed build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 contains merge 62c3cda3ea602b614a3a3dfc92c66468b5c34a4b; independent audit verified that every exact reviewed branch change is patch-equivalent to or composition-equivalent with the protected merge and no unique branch changes remain.
---
author: oompah
created: 2026-08-11 08:09
---
Delivered through protected PR #806 and verified on healthy deployed build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17.
---
<!-- COMMENTS:END -->
