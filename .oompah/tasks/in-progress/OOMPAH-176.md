---
id: OOMPAH-176
type: task
status: In Progress
priority: 1
title: Approve release addendums and snapshot main commits
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-173
- OOMPAH-175
labels: []
assignee: null
created_at: '2026-07-13T02:35:47.109837Z'
updated_at: '2026-07-13T03:45:00.999527Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6bd62640-feb0-4271-9801-64f6f2190908
---
## Summary

Read sections 4.1 and 6 of plans/release-branch-addendums.md. Implement POST /api/v1/issues/{identifier}/release-addendums. Require a task or epic that is Merged on the project default branch; accept only distinct, currently available supported release branches; resolve and persist the ordered full-SHA commit snapshot before creating each open addendum. Use a per-source lock and idempotency key so retries/concurrent requests create at most one active row per branch. Publish one release_addendum_ready event per newly created row after persistence; recover safely if event publication fails. Tests: two-target approval; duplicate request; concurrent approval; invalid/non-merged source; unavailable/default/unsupported target; unresolved commits; atomic all-or-nothing validation; and event failure recovery. Acceptance: approval immediately leaves durable open queue items attached to the source and creates no tracker child task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 03:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 03:41
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:45
---
Understanding: OOMPAH-176 is not a duplicate — no other task implements POST /api/v1/issues/{identifier}/release-addendums. OOMPAH-173 (Done) provided the schema/repository, OOMPAH-175 (Done) provided ReleaseBranchCatalog. This task implements the approval API endpoint, commit snapshot resolution, per-source locking, idempotency, and release_addendum_ready event publication. Plan: implement the endpoint in server.py using AddendumRepository and ReleaseBranchCatalog from prior tasks, resolve commits via existing SCM helpers, use a per-source asyncio.Lock for concurrency safety, publish events, and add all required tests.
---
<!-- COMMENTS:END -->
