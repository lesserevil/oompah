---
id: OOMPAH-355
type: task
status: In Progress
priority: 0
title: Rebase epic-OOMPAH-325 onto epic-OOMPAH-318
parent: OOMPAH-325
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T01:21:49.952576Z'
updated_at: '2026-07-22T01:26:35.642559Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 31cfb33c-0a06-4fd1-824f-c0eefb8b6f5c
---
## Summary

The epic branch `epic-OOMPAH-325` is stale: it has fallen behind `epic-OOMPAH-318`. Rebase the branch onto `origin/epic-OOMPAH-318`, resolve any conflicts, and force-push with `git push --force-with-lease`.

This task was auto-filed because epic OOMPAH-325 was detected as stale. Do NOT create a new branch or PR — work directly on `epic-OOMPAH-325`.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:25
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 01:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 01:25
---
Understanding: This task requests rebasing the epic branch epic-OOMPAH-325 onto origin/epic-OOMPAH-318 and force-pushing. As a Duplicate Investigator, my first step is to check whether a similar rebase task has already been filed and/or completed for these same branches before taking any action.
---
author: oompah
created: 2026-07-22 01:26
---
Duplicate screening result: NO DUPLICATE found.

Searches performed:
- rg for 'epic-OOMPAH-325', 'rebase.*325', '325.*rebase' across all .oompah/tasks/ subdirectories, docs/, plans/, README.md, WORKFLOW.md — zero matches
- Reviewed OOMPAH-353 (In Progress, child of OOMPAH-318): 'Rebase epic-OOMPAH-318 onto main' — covers a different source branch (epic-OOMPAH-318) and a different target (main), not epic-OOMPAH-325 onto epic-OOMPAH-318. Not a duplicate.
- Reviewed OOMPAH-267 (Needs Rebase): concurrent git commit race condition — completely unrelated.
- OOMPAH-325 (Open): the feature epic itself (GitLab hook lifecycle); OOMPAH-318 (In Progress): the parent forge-parity epic.

OOMPAH-355 is the only task targeting the epic-OOMPAH-325 stale-branch rebase onto epic-OOMPAH-318. It is original and should be implemented.

Focus handoff: duplicate_detector

1. Outcome: No duplicate. OOMPAH-355 is unique — no prior task covers rebasing epic-OOMPAH-325 onto origin/epic-OOMPAH-318.
2. Evidence: rg search across all task directories and docs returned zero matches for epic-OOMPAH-325 rebase. OOMPAH-353 is the closest task (same pattern: epic rebase) but covers different branches entirely.
3. Remaining work: Fetch origin/epic-OOMPAH-318, check out epic-OOMPAH-325, rebase it onto origin/epic-OOMPAH-318, resolve any conflicts, run make test, and force-push with --force-with-lease. Note that OOMPAH-353 (rebase epic-OOMPAH-318 onto main) is still In Progress — it may be worth confirming epic-OOMPAH-318 is up to date before rebasing epic-OOMPAH-325 onto it, to avoid a double rebase later.
4. Recommended next focus: devops/chore — the work is a git rebase + conflict resolution on epic-OOMPAH-325.
---
<!-- COMMENTS:END -->
