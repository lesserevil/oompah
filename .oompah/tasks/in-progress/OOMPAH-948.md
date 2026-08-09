---
id: OOMPAH-948
type: bug
status: In Progress
priority: 1
title: Bound terminal branch cleanup as durable fair maintenance
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:56:00.569098Z'
updated_at: '2026-08-09T10:43:26.525703Z'
work_branch: OOMPAH-948
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
  task_branch: OOMPAH-948
  head_sha: 08701a1925d1a6f2a3daf872f22ddda46357540e
  submitted_at: '2026-08-09T10:43:15.307424+00:00'
  updated_at: '2026-08-09T10:43:15.307424+00:00'
oompah.work_branch: OOMPAH-948
---
## Summary

Triggered by: OOMPAH-947

Live regression observed during the 2026-08-09 OOMPAH-939 rollout: after the orchestrator quiesced at 09:46:21, an already-started maintenance tick walked terminal branch cleanup across the full multi-project historical corpus until at least 09:54:46, logging dozens of nested-parent deferrals and a final 178-branch skip aggregate. This independently holds the event loop and graceful drain for minutes even when audit scanning is bounded. Scope: replace the monolithic terminal branch cleanup sweep with a durable project/task cursor and explicit scheduler-scale operation/time slice; keep exact ownership, accepted-target, shared-epic, nested-topology, and deletion safety fences; persist progress across restart; coalesce an immediate continuation only while eligible cleanup remains; separate bounded actionable work from complete historical observability. Relevant code: orchestrator terminal branch cleanup/maintenance scheduling, project cleanup helpers, workflow maintenance cursors and tick telemetry. Required tests: thousands of terminal/shared/nested rows keep one invocation below the configured deterministic budget; a Ready integration claim progresses between slices; cursor survives restart and visits every project/task fairly; quiesce/drain stops after the current bounded unit; no duplicate or unsafe deletion; partial health remains truthful; existing cleanup safety tests remain green. Acceptance: terminal cleanup cannot monopolize an event-loop tick or graceful restart for minutes, live telemetry shows bounded fair convergence, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:02
---
Additional live evidence: cleanup completed full historical scans at 09:54:46, 09:56:49, and 09:59:29 even though graceful drain quiesced new dispatch at 09:46:21. The configured batch limit counts successful deletions rather than examined rows, so 178 safe skips consume no budget and the cursor resets, causing repeated full scans. Temporary rollout mitigation staged in .env: OOMPAH_WORKTREE_CLEANUP_BATCH_SIZE=0 until this task lands; automated cleanup will be re-enabled immediately after the bounded examined-row cursor is deployed.
---
author: oompah
created: 2026-08-09 10:43
---
Implemented and pushed exact head 08701a192. Cleanup now uses bounded native state pages and durable per-project round-robin cursors across terminal tasks, stale directories, and stale branches; every safe skip/error consumes the operation slice; a 15s cooperative deadline and drain fences yield between exact candidates; partial/error/disabled health is truthful; only budget/deadline deferrals coalesce; cursor saves are checked and serialized; storage cleanup no longer bypasses the worktree lane. Verification: 510 scheduler/config tests and 300 tracker/project/storage tests passed; cold-cache 1,000-task regression parses only the page limit; terminal mutation, secret, diff, and fatal/static scans passed.
---
author: oompah
created: 2026-08-09 10:43
---
Bound worktree cleanup as durable fair maintenance at 08701a192
---
<!-- COMMENTS:END -->
