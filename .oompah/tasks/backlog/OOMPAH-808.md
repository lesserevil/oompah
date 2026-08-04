---
id: OOMPAH-808
type: task
status: Backlog
priority: null
title: Fence nested-epic dispatch until prerequisite code is reachable
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T21:45:34.568898Z'
updated_at: '2026-08-04T21:45:34.568898Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live OOMPAH-796 reproduction on 2026-08-04: OOMPAH-770 and its private task branch were created at old main a681ec2fc. Hard-start prerequisite OOMPAH-785 was terminal and the server dispatched OOMPAH-796, but the required WorkDecision/job contracts existed only on the authoritative parent lineage epic-OOMPAH-763 at f1e7925b7. The worker therefore concluded the contract did not exist and was about to reinvent it. Operator workaround revoked the empty run and fast-forwarded epic-OOMPAH-770 plus the task branch to f1e7925b7. Implementation scope: before any nested-epic child workspace/claim/provider launch, resolve the immediate parent target and required hard-start landing heads; prove every required code head is reachable from the nested epic base and new private task base. If not, atomically suppress dispatch, publish a reason-coded waiting state, and schedule exactly one authorized parent-to-child epic topology repair using the OOMPAH-633/754 policy; never fall back to main or launch on a stale base. Fence repair versus dispatch/status/head changes with a generation CAS, recreate/advance the private task branch only after the repaired epic head is published, and resume naturally after restart. Relevant code: workspace creation/private branch base selection, duplicate-to-implementation handoff, hard-start prerequisite reachability, nested epic target resolution, integration staleness repair, task/health projections. Required tests: exact OOMPAH-770/796 old-main base with terminal prerequisite reachable only from epic-OOMPAH-763; zero worker/provider launch before repair; one correct fast-forward/rebase to immediate parent then one dispatch on the repaired SHA; concurrent dependency completion and dispatch; restart mid-repair; wrong/unresolved parent fails closed; standalone/top-level tasks unaffected. Acceptance: a terminal hard-start prerequisite cannot authorize implementation until its code is reachable from the actual dispatch base, and no nested worker can inspect or mutate a stale lineage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

