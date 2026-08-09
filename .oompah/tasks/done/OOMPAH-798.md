---
id: OOMPAH-798
type: task
status: Done
priority: 1
title: Split the monolithic orchestrator into cohesive workflow modules
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-794
labels: []
assignee: null
created_at: '2026-08-04T13:59:30.266221Z'
updated_at: '2026-08-09T21:15:07.697125Z'
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
    override_id: override-8274c9c81f3b
    project_id: proj-14849f1b
    task_id: OOMPAH-798
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6573695d97c270f5f806613c34b7ac591ccaa8e42f3ecf6be941e9ed5b1d1fd6
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope and every prerequisite wave are contained in that validated
      head; owner override closes the composed work without fabricating a separate
      integration generation.
    created_at: '2026-08-08T16:31:30.961430+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-798
    target_state: Done
    evidence_fingerprint: 6573695d97c270f5f806613c34b7ac591ccaa8e42f3ecf6be941e9ed5b1d1fd6
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:31:40.502069+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: 'Retain authoritative terminal provenance while OOMPAH-975 repairs null-head
      rollup transitions: this Done child was owner-accepted in the delivered systemic
      composition, and the current workflow job itself records exact immediate-target
      landing revision 33f85955b3c1285987253c2ff17b31f574c6d12f from this task into
      its canonical epic target. Do not rearm implementation.'
    marked_at: '2026-08-09T21:15:06.170332+00:00'
    updated_at: '2026-08-09T21:15:06.170332+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: 'Retain authoritative terminal provenance while OOMPAH-975 repairs null-head
        rollup transitions: this Done child was owner-accepted in the delivered systemic
        composition, and the current workflow job itself records exact immediate-target
        landing revision 33f85955b3c1285987253c2ff17b31f574c6d12f from this task into
        its canonical epic target. Do not rearm implementation.'
      recorded_at: '2026-08-09T21:15:06.170332+00:00'
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

Refactor the remaining orchestrator after legacy deletion into explicit adapters/coordinators: event intake/fact refresh, decision scheduling, durable jobs, transitions, integration, audit, review, implementation ownership, epics, liveness, and housekeeping. Keep pure models/evaluators independent of I/O and enforce import boundaries. Preserve public API/orchestrator compatibility during extraction. Required tests: architectural dependency rules, no import cycles, focused module tests, startup/shutdown/reload, concurrency and full make test. Acceptance: orchestrator.py becomes a thin composition root; workflow modules have clear single ownership and substantially lower per-file branch complexity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 09:45
---
Direct implementation handoff complete on exact systemic base 689db5160549caa1d126e5de5bf58c0164457c9b. Commit f018dc1fd5b1d86ddf72b63d893e1e52474b433e on branch direct/OOMPAH-798-on-systemic in /home/shedwards/.oompah/worktrees/oompah/OOMPAH-798-direct.LmdyEJ. Extracted authoritative WorkDecision publication/projection, thread-safe event intake/coalescing, and pure immutable fact models from I/O collectors; redirected controllers/evaluators/domain modules to explicit pure boundaries; added ownership design and import-cycle/I/O/complexity/re-export architecture tests. Complexity: root publication 337 LOC/53 branches -> 33/0; coordinator publish 102/10; workflow_facts 1390 LOC -> 856-line collector and 564-line pure model; orchestrator reduced 64283 -> 63795 LOC. Dedicated broker: 146 passed decision/event; 169 passed model/controller/architecture; 98 passed runtime/startup/shutdown/reload/concurrency. Make terminal scan 9/9 and full-tree secret scan passed; diff check and clean worktree passed. Repository-wide broker was queued then cleanly cancelled at integrator request because consolidated exact gate will run once after composition. No push or task-status mutation performed.
---
author: oompah
created: 2026-08-08 09:45
---
Correction: the exact committed head is f018dc1fd36e9801e3e004a37c9123e09a916a02 (the preceding handoff comment's abbreviated-prefix expansion was inaccurate). Branch/worktree and all validation results in that handoff are unchanged.
---
author: oompah
created: 2026-08-08 16:31
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope and every prerequisite wave are contained in that validated head; owner override closes the composed work without fabricating a separate integration generation.
---
<!-- COMMENTS:END -->
