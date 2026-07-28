---
id: OOMPAH-464
type: feature
status: In Progress
priority: 1
title: Persist the upgrade grandfather baseline and recover pending audits
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-463
labels: []
assignee: null
created_at: '2026-07-28T13:05:06.169316Z'
updated_at: '2026-07-28T18:56:51.113112Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 99d03501-b86e-42c7-859c-50348f9eb437
oompah.work_branch: epic-OOMPAH-457
---
## Summary

Implementation scope

Extend service_state.json with a versioned terminal-audit enforcement record. On the first upgraded startup, snapshot each existing terminal task as a grandfather tuple of project, task, terminal state, and current evidence fingerprint. Reuse that baseline across restart. A task that leaves and later re-enters terminal state, or whose evidence fingerprint changes, is no longer grandfathered. Also scan In Validation metadata on startup and rebuild pending audit queue entries without duplicating attempts. Keep legacy/corrupt entries fail-closed and observable.

Tests

Use temporary service-state and fake trackers to cover first startup, second startup, unchanged grandfathered records, changed evidence, terminal-to-nonterminal-to-terminal, pending queue recovery, duplicate suppression, corrupt state, and multiple projects with overlapping task IDs. Run focused tests and make test.

Acceptance criteria

Deployment does not retroactively audit existing terminal records, restart does not forget enforcement or pending work, and any post-upgrade terminal/evidence change requires a fresh audit.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:56
---
Understanding: Investigating OOMPAH-464 as Duplicate Investigator. The task requires extending service_state.json with a versioned terminal-audit enforcement record, snapshotting existing terminal tasks on first upgrade, and recovering pending audit queue entries on restart. Before implementing, I am searching for existing tasks that cover the same ground: grandfather baselining, terminal state audit enforcement, upgrade persistence, or audit queue recovery.
---
author: oompah
created: 2026-07-28 18:56
---
Discovery: Completed duplicate screening. Searched 280+ archived/merged/backlog tasks, git log history, code files, and design plans. No existing task addresses grandfather baseline snapshotting, upgrade persistence to service_state.json, or pending audit queue recovery. OOMPAH-462 and OOMPAH-463 (the two blocking dependencies) are already committed in epic-OOMPAH-457; they provide terminal-audit domain records and metadata persistence. OOMPAH-464 is a new, non-duplicate task that builds on them.
---
<!-- COMMENTS:END -->
