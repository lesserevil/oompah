---
id: OOMPAH-771
type: epic
status: Done
priority: 1
title: Retire legacy reconcilers and modularize the orchestrator
parent: OOMPAH-763
children:
- OOMPAH-787
- OOMPAH-794
- OOMPAH-798
blocked_by: []
start_blocked_by: &id001
- OOMPAH-768
- OOMPAH-770
- OOMPAH-767
- OOMPAH-769
- OOMPAH-806
labels: []
assignee: null
created_at: '2026-08-04T13:56:05.119669Z'
updated_at: '2026-08-10T01:10:50.758313Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-dd69dc0f3d7a
    project_id: proj-14849f1b
    task_id: OOMPAH-771
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 373e7fb99b691009473fed06eeaca69e7d9b02697dfd9e61f630bfa6bd427b75
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope and every prerequisite wave are contained in that validated
      head; owner override closes the composed work without fabricating a separate
      integration generation.
    created_at: '2026-08-08T16:31:58.799764+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-771
    target_state: Done
    evidence_fingerprint: 373e7fb99b691009473fed06eeaca69e7d9b02697dfd9e61f630bfa6bd427b75
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:32:12.773549+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done work is complete, but current parent-landing evidence
      cannot be reconstructed safely enough to promote it to Merged; retain immutable
      terminal provenance and retire reassessment.
    marked_at: '2026-08-10T01:10:49.343618+00:00'
    updated_at: '2026-08-10T01:10:49.343618+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done work is complete, but current parent-landing
        evidence cannot be reconstructed safely enough to promote it to Merged; retain
        immutable terminal provenance and retire reassessment.
      recorded_at: '2026-08-10T01:10:49.343618+00:00'
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

Complete the migration by deleting superseded workflow code and documenting the supported architecture. Remove duplicate eligibility summaries, direct status writers, read-time repair side effects, status-specific watchdog recovery now covered by liveness, obsolete process-local authority maps, and fire-and-forget lifecycle futures. Reduce _tick to event intake, fact refresh, decision evaluation, and durable job scheduling. Split the 37k-line orchestrator into cohesive workflow modules without changing public behavior; keep project/tracker/Git adapters separate from pure rules. Remove shadow flags only after production canary evidence, update user/operator docs, publish recovery and rollout guidance, and enforce architectural import/write boundaries. Required tests: full make test, architectural dependency tests, API compatibility, clean restart/upgrade from pre-migration state, rollback before final flag removal, and production-like soak. Acceptance: legacy paths are deleted rather than retained; production workflow LOC and branch complexity materially decline; one transition writer/decision engine/job ledger/liveness controller remain; repository and docs contain no contradictory workflow implementation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 16:32
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope and every prerequisite wave are contained in that validated head; owner override closes the composed work without fabricating a separate integration generation.
---
<!-- COMMENTS:END -->
