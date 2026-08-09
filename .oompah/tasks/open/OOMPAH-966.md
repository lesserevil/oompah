---
id: OOMPAH-966
type: bug
status: Open
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
updated_at: '2026-08-09T16:41:20.247083Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
