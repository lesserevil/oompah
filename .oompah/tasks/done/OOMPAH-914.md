---
id: OOMPAH-914
type: task
status: Done
priority: null
title: Recover expired task-transition claims without operator deadlock
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T14:25:47.766180Z'
updated_at: '2026-08-09T21:42:54.844701Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f4ad63fbd302
    project_id: proj-14849f1b
    task_id: OOMPAH-914
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 642ab4831eb57aa71929e77de2d87f1f2e96cdae6ec70a5289d6aaadb418ccc6
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:25:07.289741+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-914
    target_state: Done
    evidence_fingerprint: 642ab4831eb57aa71929e77de2d87f1f2e96cdae6ec70a5289d6aaadb418ccc6
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:25:22.761362+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:42:53.321470+00:00'
    updated_at: '2026-08-09T21:42:53.321470+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:42:53.321470+00:00'
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

A live Backlog to Open request for OOMPAH-912 was interrupted while its durable transition was in applying. After the 300-second claim expired and the service restarted, every new operator request was rejected with transition.recovery_required because TransitionJournal.begin only permits the exact old idempotency key to reclaim an expired foreign transition, while the ordinary status API generates a new key and exposes no recovery path. The task is therefore permanently stuck without direct database surgery or replaying an inaccessible internal key.\n\nImplementation scope:\n- Add a durable restart/runtime recovery lane for expired task-transition claims that inspects the original immutable intent and current tracker state, resumes or safely finalizes that exact transition, and releases the claim.\n- Keep per-task fencing and fail closed for live leases, ambiguous tracker evidence, changed task authority, and conflicting newer intents.\n- Make API/operator requests report bounded recovery progress and retry successfully after recovery rather than deadlocking forever on transition.recovery_required.\n- Add health/diagnostic visibility for outstanding expired claims.\n- Relevant code: oompah/task_transition_service.py TransitionJournal.begin and TaskTransitionService.execute, orchestrator startup/recovery wiring, server status-transition error mapping.\n\nRequired tests:\n- Simulate process death after APPLYING, advance beyond lease TTL, restart, and prove the original intent is recovered or safely finalized and a later operator transition can proceed.\n- Cover effect-already-applied, effect-not-applied, stale status/version, live foreign lease, and concurrent recovery claimant cases.\n- Prove recovery never deletes append-only journal history and never permits a conflicting writer while a lease is live.\n\nAcceptance criteria:\n- No task can remain permanently blocked solely because an inaccessible prior status-transition idempotency key owns an expired claim.\n- OOMPAH-912 can be promoted through the normal API after recovery without manual SQLite edits.\n- Focused transition-service, orchestrator restart, and server API tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner implementation is in progress on the systemic composition branch. Recovery is being made durable: an expired foreign claim will reclaim and execute the exact immutable prior intent under CAS before retrying the waiting operator request; live leases and concurrent recovery remain fenced. Status remains Backlog only because this bug currently prevents normal promotion.
---
author: oompah
created: 2026-08-08 16:25
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
