---
id: OOMPAH-966
type: bug
status: Done
priority: 1
title: Fence completed workflow effects until completion callbacks settle
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- workflow-runtime
- ci-fix
assignee: null
created_at: '2026-08-09T16:29:54.272144Z'
updated_at: '2026-08-10T01:24:19.307101Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c46ac0732a9f
    project_id: proj-14849f1b
    task_id: OOMPAH-966
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48dbc93627f96806b0b07a90c339ddfd2c0f891c4761cd132cd6ae68994bc7ec
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Regression child delivered in the exact reviewed OOMPAH-962 merge.
    created_at: '2026-08-09T17:38:18.021642+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-966
    target_state: Done
    evidence_fingerprint: 48dbc93627f96806b0b07a90c339ddfd2c0f891c4761cd132cd6ae68994bc7ec
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T17:38:31.740121+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done record lacks safe exact current landing proof;
      retain immutable terminal provenance and retire recurring reassessment without
      creating new work.
    marked_at: '2026-08-10T01:24:17.815474+00:00'
    updated_at: '2026-08-10T01:24:17.815474+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done record lacks safe exact current landing proof;
        retain immutable terminal provenance and retire recurring reassessment without
        creating new work.
      recorded_at: '2026-08-10T01:24:17.815474+00:00'
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

Triggered by: OOMPAH-962

Hosted PR #770 run 31323480242 failed Python 3.12 in test_fast_admission_requests_one_world_scan_after_queue_drains while 3.11/3.13 passed. The runtime retains detached effect tasks in _effect_tasks until the done callback pops them and appends the result to _effect_results, but health_snapshot()['worker']['retained'] and pending_operation_count count only tasks whose task.done() is false. There is therefore an event-loop gap where the task is done but its completion callback has not settled: health reports idle, a fast-admission caller can drain zero completions, and close/drain accounting can omit callback-pending work. Scope: make runtime retained/pending accounting include completed tasks until _effect_finished settles their result and publishes the replenishment edge; preserve worker active counts, quarantine accounting, bounded drains, no double completion, and no busy loop. Add deterministic regression coverage that pauses the done callback gap and proves health/pending remain nonzero, continue/close cannot observe false idle, the result is consumed once after settlement, and the empty published queue requests exactly one world scan. Update the existing fast-admission test to synchronize on the true completion boundary instead of scheduler timing. Required checks: repeated focused test, workflow runtime module, integration workflow and OOMPAH-962 composed affected suite, hosted Python 3.11/3.12/3.13. Acceptance: the exact hosted failure shape is deterministic and fixed without sleeps, false-idle telemetry is impossible, and PR #770 can qualify.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 16:30
---
Project owner promotes the exact hosted false-idle race for direct repair on the active OOMPAH-962 integration branch.
---
author: oompah
created: 2026-08-09 16:41
---
Implemented directly on the active OOMPAH-962 integration branch at exact head bb0cc60f6440809184d7f50c4149fae11b4da604. Callback-pending tasks remain retained/pending through atomic one-shot settlement; close and drain stay fenced; the fast-admission test now synchronizes on the actual completion observer. Deterministic callback-gap regression and focused pair passed 30 repetitions; 821 composed tests plus safety/static scans pass. PR #770 hosted run 31324369226 is qualifying the exact head, and independent review is running.
---
author: oompah
created: 2026-08-09 16:51
---
Independent review found that _run_due still filtered task.done callback-pending entries from lane activity, allowing a same-loop continuation to report false idle before result publication. Corrected and pushed exact OOMPAH-962 head c8f359c88: every retained entry now occupies its lane until _effect_finished atomically publishes/removes it. Added deterministic same-loop ordering regression proving the gap reports active=1, then exactly one settled result requests the world scan. Runtime/integration 199 tests and 616 broader composed tests plus scans/lint/diff pass. Fresh hosted matrix is running; final independent re-review remains required.
---
author: oompah
created: 2026-08-09 17:07
---
Final callback-settlement correction pushed at 42a1926aa on PR #770. A quick same-pass final completion is retained for the callback-driven admission turn, producing exactly one published_queue_drained world reconcile; callback-gap snapshots atomically report the effect as active or completed and never false-idle. Validation: 201 runtime/integration tests, 618 broad workflow tests, terminal-audit mutation scan, secret scan, critical Ruff, and diff checks pass; exact-head independent re-review and hosted matrix are pending.
---
author: oompah
created: 2026-08-09 17:14
---
Regression proof strengthened at final exact OOMPAH-962 head 2fc11a864. The test now structurally blocks the post-schedule no-job claim until the completion callback has settled, proving the first report is scheduled=1/completed=0/active=0 with one deferred result, the second is the sole published_queue_drained reconcile, and the third is empty. 100 focused repetitions and 293 composed tests pass; no further production change was required.
---
author: oompah
created: 2026-08-09 17:38
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Regression child delivered in the exact reviewed OOMPAH-962 merge.
---
author: oompah
created: 2026-08-09 17:38
---
Delivered by PR #770 at c503e7e586a18445b0671c765bce2b998cc277be. Deterministic callback-settlement proof passed 100 repetitions; final combined exact head dd2e18fc passed independent review and hosted Python 3.11/3.12/3.13 CI.
---
<!-- COMMENTS:END -->
