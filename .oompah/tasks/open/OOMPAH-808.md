---
id: OOMPAH-808
type: task
status: Open
priority: null
title: Fence nested-epic dispatch until prerequisite code is reachable
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T21:45:34.568898Z'
updated_at: '2026-08-04T21:53:33.392621Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-808
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d7bddd80d28d0965f56d075e5545a112d35734356e7266b832f38aadfa7e69e0
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 64b7728e-79b2-43da-bb30-8cb28a85af72
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T21:52:47.770161+00:00'
  claim_expires_at: '2026-08-04T22:22:47.770161+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: af142af5-069d-42b4-b385-53b2fa37352b
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-808
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-808
  base_branch: epic-OOMPAH-763
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T21:53:26.873053+00:00'
---
## Summary

Live OOMPAH-796 reproduction on 2026-08-04: OOMPAH-770 and its private task branch were created at old main a681ec2fc. Hard-start prerequisite OOMPAH-785 was terminal and the server dispatched OOMPAH-796, but the required WorkDecision/job contracts existed only on the authoritative parent lineage epic-OOMPAH-763 at f1e7925b7. The worker therefore concluded the contract did not exist and was about to reinvent it. Operator workaround revoked the empty run and fast-forwarded epic-OOMPAH-770 plus the task branch to f1e7925b7. Implementation scope: before any nested-epic child workspace/claim/provider launch, resolve the immediate parent target and required hard-start landing heads; prove every required code head is reachable from the nested epic base and new private task base. If not, atomically suppress dispatch, publish a reason-coded waiting state, and schedule exactly one authorized parent-to-child epic topology repair using the OOMPAH-633/754 policy; never fall back to main or launch on a stale base. Fence repair versus dispatch/status/head changes with a generation CAS, recreate/advance the private task branch only after the repaired epic head is published, and resume naturally after restart. Relevant code: workspace creation/private branch base selection, duplicate-to-implementation handoff, hard-start prerequisite reachability, nested epic target resolution, integration staleness repair, task/health projections. Required tests: exact OOMPAH-770/796 old-main base with terminal prerequisite reachable only from epic-OOMPAH-763; zero worker/provider launch before repair; one correct fast-forward/rebase to immediate parent then one dispatch on the repaired SHA; concurrent dependency completion and dispatch; restart mid-repair; wrong/unresolved parent fails closed; standalone/top-level tasks unaffected. Acceptance: a terminal hard-start prerequisite cannot authorize implementation until its code is reachable from the actual dispatch base, and no nested worker can inspect or mutate a stale lineage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:53
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
