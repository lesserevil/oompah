---
id: OOMPAH-650
type: bug
status: Open
priority: 1
title: Keep scoped task handoff credentials valid for the full worker lifetime
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:09.832838Z'
updated_at: '2026-07-31T08:59:30.865768Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-650
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e12d210e52775bddb4e0f0261ddd708b8c2890ef3db6daf9b0043d22fd2907f9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e23ad513-2e50-49f9-9ba6-20435a5a2055
  claim_owner: 106d2bf0-ef5a-4435-81e3-efd3fb3705e0
  claimed_at: '2026-07-31T08:59:21.698913+00:00'
  claim_expires_at: '2026-07-31T09:29:21.698913+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 29d8eb02-0f3e-42aa-992e-f9ecf2be00a8
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-650
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-650
  base_branch: epic-OOMPAH-619
  base_sha: 0dc7d0f7caeea06a6eceb55ea2e58cf16554f0a4
  updated_at: '2026-07-31T08:59:28.483865+00:00'
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
<!-- COMMENTS:END -->
