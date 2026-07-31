---
id: OOMPAH-650
type: bug
status: Open
priority: 1
title: Keep scoped task handoff credentials valid for the full worker lifetime
parent: OOMPAH-619
children: []
blocked_by:
- OOMPAH-652
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:09.832838Z'
updated_at: '2026-07-31T09:08:07.312287Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-650
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a045feb3c4e136514e5067edcf8e10cd8e6ddf01b44eef220fd15192a76e1c6b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6f904d6a-089c-451b-9ff9-d90334569d83
  claim_owner: 432b475d-ac6b-4689-b481-380c0818b1e9
  claimed_at: '2026-07-31T09:07:14.709464+00:00'
  claim_expires_at: '2026-07-31T09:37:14.709464+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 9edc9ae9-678c-4ade-8b4c-8bfcb475e367
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-650
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-650
  base_branch: epic-OOMPAH-619
  base_sha: 0dc7d0f7caeea06a6eceb55ea2e58cf16554f0a4
  updated_at: '2026-07-31T09:07:21.802007+00:00'
---
## Summary

Live reproduction on 2026-07-31: an active OOMPAH-646 worker inherited OOMPAH_TASK_HANDOFF_TOKEN, but the capability expired while that worker was still running. Every permitted oompah task view then selected the expired scoped capability and returned 401; unsetting the token exposed reusable operator Basic credentials and worked, but spawned workers must never need or inherit that fallback. Implementation scope: bind task-handoff grant lifetime to the owning live worker/session rather than a shorter wall-clock lease, renew or rotate grants safely across long tool calls and graceful service restarts, revoke them exactly when ownership ends, and return an explicit expired/revoked diagnostic that distinguishes auth transport failure from task failure. Keep the capability task/project/action scoped and do not weaken the prohibition on reusable operator credentials in worker environments. Relevant files: oompah/task_handoff.py, orchestrator worker launch/termination/restart recovery, task_cli.py, ACP backend environment injection, and auth-health reporting. Required tests: a worker outliving the current grant TTL can view/comment/submit; long tool activity keeps the grant usable; restart recovery preserves or atomically replaces the grant; termination/retry revokes the old grant; cross-task/project/action use remains denied; no Basic-auth fallback. Acceptance: a live worker never receives 401 solely because its task-scoped credential aged out, stale workers remain unable to mutate tasks, focused auth/handoff tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 08:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 08:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:08
---
Additional live evidence: OOMPAH-645 completed focused verification on clean pushed head 6686290d5, but its post-worker task handoff failed at 08:58. After operator reconciliation and a server restart, a fresh standard worker repeated the same post-run handoff failure at 09:04 and the task returned to Needs Human again. The task is now intentionally held with finish-order dependencies on OOMPAH-650/OOMPAH-652 to stop redispatch churn. Cover both TTL expiry and restart/revocation/reissue paths; a newly launched post-restart worker must receive a valid server-owned capability through its final submit.
---
<!-- COMMENTS:END -->
