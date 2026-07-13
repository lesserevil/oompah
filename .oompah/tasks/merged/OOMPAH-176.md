---
id: OOMPAH-176
type: task
status: Merged
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
updated_at: '2026-07-13T07:14:33.449173Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6bd62640-feb0-4271-9801-64f6f2190908
oompah.task_costs:
  total_input_tokens: 133
  total_output_tokens: 4289
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 133
      output_tokens: 4289
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 133
    output_tokens: 4289
    cost_usd: 0.0
    recorded_at: '2026-07-13T04:17:11.339434+00:00'
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
author: oompah
created: 2026-07-13 03:59
---
Discovery: OOMPAH-176 is not a duplicate. Prior tasks OOMPAH-173 (AddendumRepository, schema) and OOMPAH-175 (ReleaseBranchCatalog, GET catalog endpoint) are both Done and provide the building blocks. No existing code implements POST /api/v1/issues/{identifier}/release-addendums. Key files: oompah/events.py (need RELEASE_ADDENDUM_READY), oompah/release_addendum_schema.py (AddendumRepository), oompah/release_branch_catalog.py (ReleaseBranchCatalog), oompah/release_pick_commit_resolver.py (_resolve_via_scm/_resolve_via_git). Implementation plan: (1) add EventType.RELEASE_ADDENDUM_READY; (2) create oompah/release_addendum_approval.py with per-source asyncio.Lock, commit resolution, and atomic write; (3) add POST endpoint to server.py; (4) create tests/test_server_release_addendums.py covering all required scenarios.
---
author: oompah
created: 2026-07-13 04:06
---
Implementation: Created oompah/release_addendum_approval.py and POST /api/v1/issues/{identifier}/release-addendums in server.py. Key changes: (1) EventType.RELEASE_ADDENDUM_READY added to oompah/events.py; (2) new module oompah/release_addendum_approval.py with per-source asyncio.Lock via _get_source_lock(), resolve_addendum_commits() using SCM PR lookup then git rev-list, validate_target_branches() enforcing deduplication/availability/stale-rejection/default-branch rejection, and approve_release_addendums() that atomically creates missing open rows, writes via AddendumRepository, then publishes release_addendum_ready events per new row (event failure leaves row open, returns queued=False); (3) server.py endpoint validates project/issue/Merged-state/catalog/commits all-or-nothing before lock; (4) 41 new tests in tests/test_server_release_addendums.py covering all required scenarios.
---
author: oompah
created: 2026-07-13 04:06
---
Verification: make test — 7606 passed, 28 skipped, 13 warnings (0 failures). 41 new tests added: two-target approval; duplicate request idempotency; concurrent approval (single row via asyncio.Lock); invalid/non-merged source (409); unavailable/default/unsupported/stale targets (400); unresolved commits (409); atomic all-or-nothing validation (no partial writes when one branch invalid); event failure recovery (row persisted open, queued=false, no rollback, event_failures in response); event emission per new row; no tracker child task created.
---
author: oompah
created: 2026-07-13 04:06
---
Completion: Delivered POST /api/v1/issues/{identifier}/release-addendums (section 6 of plans/release-branch-addendums.md). Not a duplicate of any existing task. Blockers OOMPAH-173 (schema) and OOMPAH-175 (catalog) were both Done and provided all building blocks. Implementation: EventType.RELEASE_ADDENDUM_READY; oompah/release_addendum_approval.py (per-source asyncio lock, commit resolution via SCM+git, catalog validation, atomic write, event publication with failure recovery); server.py endpoint (all-or-nothing validation: Merged check, catalog/stale/default/unsupported branch rejection, commit resolution, under-lock create+write, invalidate caches, return full addendum list). 41 tests cover all acceptance criteria. Approval immediately leaves durable open queue items attached to the source and creates no tracker child task.
---
author: oompah
created: 2026-07-13 04:07
---
Implemented POST /api/v1/issues/{identifier}/release-addendums with per-source lock, commit snapshot, event publication and recovery. 41 tests, 7606 total passed.
---
author: oompah
created: 2026-07-13 04:17
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 95
- Tokens: 133 in / 4.3K out [4.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 36m 11s
- Log: OOMPAH-176__20260713T034104Z.jsonl
---
<!-- COMMENTS:END -->
