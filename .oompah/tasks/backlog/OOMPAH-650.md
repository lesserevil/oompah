---
id: OOMPAH-650
type: bug
status: Backlog
priority: 1
title: Keep scoped task handoff credentials valid for the full worker lifetime
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:09.832838Z'
updated_at: '2026-07-31T08:57:09.832838Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction on 2026-07-31: an active OOMPAH-646 worker inherited OOMPAH_TASK_HANDOFF_TOKEN, but the capability expired while that worker was still running. Every permitted oompah task view then selected the expired scoped capability and returned 401; unsetting the token exposed reusable operator Basic credentials and worked, but spawned workers must never need or inherit that fallback. Implementation scope: bind task-handoff grant lifetime to the owning live worker/session rather than a shorter wall-clock lease, renew or rotate grants safely across long tool calls and graceful service restarts, revoke them exactly when ownership ends, and return an explicit expired/revoked diagnostic that distinguishes auth transport failure from task failure. Keep the capability task/project/action scoped and do not weaken the prohibition on reusable operator credentials in worker environments. Relevant files: oompah/task_handoff.py, orchestrator worker launch/termination/restart recovery, task_cli.py, ACP backend environment injection, and auth-health reporting. Required tests: a worker outliving the current grant TTL can view/comment/submit; long tool activity keeps the grant usable; restart recovery preserves or atomically replaces the grant; termination/retry revokes the old grant; cross-task/project/action use remains denied; no Basic-auth fallback. Acceptance: a live worker never receives 401 solely because its task-scoped credential aged out, stale workers remain unable to mutate tasks, focused auth/handoff tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

