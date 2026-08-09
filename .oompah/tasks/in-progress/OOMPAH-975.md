---
id: OOMPAH-975
type: bug
status: In Progress
priority: 1
title: Carry trusted composed landing heads into rollup terminal transitions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T21:14:31.760374Z'
updated_at: '2026-08-09T21:20:52.847789Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-940

Live all-enforce rollout regression found after OOMPAH-940 child delivery on 2026-08-09. Done children OOMPAH-787, OOMPAH-794, OOMPAH-797, and OOMPAH-798 have canonical durable landing facts (landing_source=<task>, landing_target=epic-OOMPAH-767/771, landing_revision=33f85955b3c1285987253c2ff17b31f574c6d12f), but no standalone work_branch/task_head because their owner-completed commits were composed into the epic. The workflow decision correctly emits terminal.immediate_target_landing_proven and parent_rollup_review requesting Merged, yet the handler builds TransitionIntent.exact_head=null; TaskTransitionService rejects transition.head_required and the jobs exhaust as current policy failures. Implementation scope: thread the canonical trusted landing revision through parent_rollup_review revalidation/effect/transition intent whenever immediate-target landing is proven; require the landing source/target and task evidence generation to remain current; supersede/retry historical exhausted null-head jobs after the fixed decision generation; preserve exact-head fail-closed behavior when landing proof is absent, stale, wrong-source, wrong-target, or mutable. Relevant code: universal workflow facts/decisions, epic parent rollup review handler, transition-intent construction, durable job recovery/current exhaustion. Required tests: composed Done child with no task branch but exact durable epic landing reaches Merged; all four live shapes; stale/mismatched/no landing remains head_required without exhausting an administratively recoverable job; restart/replay is idempotent; independent standalone tasks still require their exact accepted head. Acceptance: these four historical jobs are naturally superseded or retired, current exhausted returns to zero, no broad status/database edits are used, focused workflow/transition/restart suites and full gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 21:17
---
The live affected set expanded deterministically from four to six as the generation-852 queue drained: OOMPAH-889 and OOMPAH-894 have the same terminal.immediate_target_landing_proven shape, exact landing revision 33f85955b3c1285987253c2ff17b31f574c6d12f into epic-OOMPAH-763, empty task branch/head, and null-head transition rejection. They were also retained through terminal-provenance authority; implementation remains terminal. Regression coverage and natural supersession must include all six rows.
---
<!-- COMMENTS:END -->
