---
id: OOMPAH-905
type: task
status: Done
priority: null
title: Age validation-resource waiters so strict priority cannot starve focused repair
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T19:44:43.282351Z'
updated_at: '2026-08-09T20:15:28.142450Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-66f34ffeabb6
    project_id: proj-14849f1b
    task_id: OOMPAH-905
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4e9c5f58a462d61d16cb5c4c5d150862318d2617768ac2f3be954ca311c40fc5
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner reconciliation for OOMPAH-905: its accepted implementation
      is patch-contained in published epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
      Independent composition review completed, affected tests passed 392/392, and
      the exact full make test passed 17,860 with zero failures.'
    created_at: '2026-08-08T03:58:00.441671+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-905
    target_state: Done
    evidence_fingerprint: 4e9c5f58a462d61d16cb5c4c5d150862318d2617768ac2f3be954ca311c40fc5
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T03:58:11.397686+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-905 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:15:26.385629+00:00'
    updated_at: '2026-08-09T20:15:26.385629+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-905 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:15:26.385629+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live direct-work reproduction on 2026-08-07 after OOMPAH-816/852 deployment: OOMPAH-859's canonical worker validation waiter remained queued for more than 19 minutes while exact-gate and auditor arrivals repeatedly overtook it; its 1800-second acquire timeout can expire even though the capacity-1 lane is making progress. OOMPAH-784/O795 worker waits show the same class. This violates OOMPAH-816's fairness/no-starvation acceptance and can deadlock focused repair behind a continuous stream of later high-priority work. Implementation scope: add bounded aging/fairness to ValidationResourceLease durable waiter selection while retaining exact-gate urgency and single-slot safety; guarantee a live low-priority waiter receives service within a documented bound under continuous higher-priority arrivals; preserve FIFO within effective priority, restart/PID pruning, cancellation, owner fencing, and truthful wait telemetry. Relevant files: oompah/validation_resource_lease.py, validation-resource projections/health, and tests for multiprocess ordering. Required tests: deterministic continuous exact/auditor arrivals cannot starve an older worker; urgent exact work still overtakes a fresh worker; aging persists across restart; cancelled/dead waiters do not inherit priority; capacity never exceeds one; existing O859/O784 ordering reproduction. Acceptance: no valid waiter reaches acquire timeout solely because later higher-priority work continues to arrive, and normal wait observability remains informational/self-clearing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 19:57
---
Direct implementation complete at 21633ebade7e9069d7a793029bab5a388ec658c1 (published as epic-OOMPAH-763--task-OOMPAH-905). After 21 default 30-second aging intervals, a live waiter enters durable FIFO starvation protection; later exact/auditor arrivals can no longer overtake it, while fresh exact work retains urgency before the bound. Telemetry exposes effective priority/protection/remaining time. Deterministic multiprocess, restart, cancellation, dead-requester, urgency, and capacity coverage passes: 498 tests. Included in the combined systemic epic validation batch; not separately submitted.
---
author: oompah
created: 2026-08-08 03:58
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner reconciliation for OOMPAH-905: its accepted implementation is patch-contained in published epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268. Independent composition review completed, affected tests passed 392/392, and the exact full make test passed 17,860 with zero failures.
---
author: oompah
created: 2026-08-08 03:58
---
Integrated and validated on epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
---
<!-- COMMENTS:END -->
