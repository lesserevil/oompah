---
id: OOMPAH-1342
type: epic
status: In Progress
priority: 1
title: Recover production service throughput and workflow progress
parent: null
children:
- OOMPAH-1343
- OOMPAH-1344
- OOMPAH-1345
- OOMPAH-1346
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-26T18:42:41.866488Z'
updated_at: '2026-08-27T04:03:03.004317Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-epic
  request_fingerprint: 070158bda33ab0d0629239fafe161aeb566b706e18982b59d6073e52830bd282
oompah.lifecycle_revision: 2
---
## Summary

Implement the accepted recovery plan in plans/service-throughput-recovery.md. This epic coordinates four independently deliverable children: deployment stabilization, bounded reconciliation/forge observations, snapshot-backed reviews API, and bounded storage retention. Preserve fail-closed lifecycle, exact-head, project-scope, and audit guarantees. Require focused tests for every child and the complete Makefile gate plus workflow rollout check before resuming production projects. Acceptance: the children are complete in rollout order, production reconciliation stays inside its configured budget, APIs remain responsive, storage growth is bounded, exhausted decisions have explicit dispositions, and projects resume without unexplained liveness divergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 22:50
---
Recovery implementation is pushed on epic-OOMPAH-1342 and PR #951. Full make test passes: 20,449 passed, 7 skipped, 2 xfailed. Production remains globally paused; storage reclaimed from 93% to 79% used, and /api/v1/reviews dropped from >20s timeout to ~0.08s on the deployed candidate.
---
author: oompah
created: 2026-08-26 23:36
---
Progress update: PR #951 merged to main at 13718ac1c after GitHub CI passed. Focused suites pass (756) and the full local gate passes (20,449 passed, 7 skipped, 2 xfailed). Production is deployed on that revision and remains globally paused. Disk pressure was relieved from 93% to 79%; the reviews endpoint returns from memory in under 0.1s. Remaining controlled work is production re-enable/canary and explicit disposition of historical exhausted jobs.
---
author: oompah
created: 2026-08-27 03:16
---
Progress: deployed PR #959 at 08f21678e. Oompah-only complete reconciliation improved to 129.545s (implementation 3.146s, review 11.399s, integration 106.101s, epic 7.941s) with complete recovery, zero current divergence, zero source errors, and zero action-required decisions. This remains 9.545s above the 120s convergence budget, so global and all project pauses were restored. Continuing to remove remaining per-revision forge I/O under direct human control.
---
author: oompah
created: 2026-08-27 04:03
---
Queue hygiene cleanup completed under global/project pause. Closed all 8 stale conflicting Oompah PRs (#939, #947-950, #954-955, #960), archived their 11 superseded tasks with owner override, and deleted their remote branches. Archived another 44 duplicate auto-filed contributor-evidence/worker-dispatch tasks that were still Ready to Integrate despite the root fixes already being on main. Closed 8 stale blocked Trickle draft MRs (!3, !10-13, !16-18), archived their tasks with explicit fresh-revision requirements, and deleted their remote branches. Review inventory fell from 21 to 6 and conflict count from 11 to 0; Ready to Integrate fell from 77 to 32 (Oompah 49 to 5). Remaining six Trickle MRs are non-draft and conflict-free; their CI/blocker disposition remains to be handled separately.
---
<!-- COMMENTS:END -->
