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
updated_at: '2026-08-09T21:43:40.541298Z'
work_branch: OOMPAH-975
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-975
  head_sha: 2fd04d272f03f9ea670243978878dd8e9c88ff2f
  submitted_at: '2026-08-09T21:43:23.517825+00:00'
  updated_at: '2026-08-09T21:43:23.517825+00:00'
oompah.work_branch: OOMPAH-975
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
author: oompah
created: 2026-08-09 21:22
---
Implementation started in isolated worktree /home/shedwards/src/oompah-975 on branch OOMPAH-975 at base 312c18ae3. Confirmed six current exhausted parent_rollup_review jobs (OOMPAH-787, -794, -797, -798, -889, -894) all lose trusted composed landing revision 33f85955... before TransitionIntent. Fix will fence source/target/evidence at revalidation, carry the exact landing SHA through transition and terminal-audit binding, preserve standalone exact-head requirements, and cover natural current-exhaustion retirement/restart replay.
---
author: oompah
created: 2026-08-09 21:42
---
Implementation complete on branch OOMPAH-975. The parent-rollup authority now carries a canonical exact composed landing SHA through revalidation, effect receipt, verification, transition intent, and terminal-audit binding; source/target/project/revision/durability remain fail-closed at the final mutation guard. Regression coverage includes all six live shapes (OOMPAH-787/-794/-797/-798/-889/-894), absent/stale/wrong/mutable landing rejection, actual TaskTransitionService staging, restart journal replay, audit coalescing, standalone no-head rejection, and owner-driven exhaustion retirement without automatic rearm. Focused workflow/transition/runtime gate: 630 passed; terminal mutation scan passed. Preparing exact-head commit/push for the configured full branch gate.
---
author: oompah
created: 2026-08-09 21:43
---
Committed and pushed 2fd04d272 on OOMPAH-975. Trusted composed parent landing heads now remain exact through rollup revalidation/effect/verification/transition and bind the terminal audit; all authority fields are rechecked at final mutation. Added six-shape, fail-closed, actual transition, restart/replay, coalescing, runtime-guard, and standalone-head regressions. Focused relevant suites: 630 passed; task mutation scan passed. Existing owner-projection retirement remains responsible for superseding old exhausted generations without unsafe rearm.
---
<!-- COMMENTS:END -->
