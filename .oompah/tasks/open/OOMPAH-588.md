---
id: OOMPAH-588
type: epic
status: Open
priority: 1
title: Finish safe repository hygiene and maintenance correctness
parent: OOMPAH-584
children:
- OOMPAH-600
- OOMPAH-601
- OOMPAH-602
- OOMPAH-603
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:46.482910Z'
updated_at: '2026-07-31T05:02:07.611055Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Finish aggressive but safe worktree/branch pruning and remove maintenance errors/noise that obscure real faults. Reuse OOMPAH-581, preserve dirty or unmerged work, repair project-scoped merged-label maintenance, and make cleanup outcomes measurable.

Relevant context

The managed oompah repository retained 20 registered worktrees, 117 local branches, and 67 remote branches. Cleanup itself reported no fatal error, but emitted repeated terminal-branch ownership warnings and a slow tick; merged_labels rejected OOMPAH-476 for missing project_id. OOMPAH-581 is already implemented and Ready to Integrate.

Acceptance criteria

Safe terminal artifacts are pruned on schedule; dirty/unmerged/shared-owner work is preserved; ownership skips are aggregated instead of warning-flooded; cleanup latency and categorized skip counts are visible; merged-label maintenance always resolves project scope without unsafe legacy fallback; focused and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:20
---
Children are accepted and open; activate the hygiene recovery epic.
---
author: oompah
created: 2026-07-31 01:00
---
Operator recovery for the live nested-epic queue deadlock: rebased origin/epic-OOMPAH-588 from 89dfc1881 onto current parent origin/epic-OOMPAH-584 d62dd4cff and force-pushed with an exact lease at b4959703e. The three OOMPAH-602 commits replayed cleanly; adjusted one maintenance-scope test mock for the newer authoritative landing-ref refresh. Focused merged-label scope and rollup verification: 33 passed; terminal mutation scan passed.
---
<!-- COMMENTS:END -->
