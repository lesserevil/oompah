---
id: OOMPAH-32
type: epic
status: In Review
priority: 0
title: Finish 1.0 operator and project docs
parent: OOMPAH-16
children:
- OOMPAH-33
- OOMPAH-34
- OOMPAH-35
- OOMPAH-36
- OOMPAH-45
blocked_by: []
labels:
- merge-conflict
- epic:rebasing
assignee: null
created_at: '2026-06-22T01:17:10.735548Z'
updated_at: '2026-06-22T15:05:28.641982Z'
work_branch: epic-OOMPAH-32
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/350
review_number: null
merged_at: null
oompah.work_branch: epic-OOMPAH-32
oompah.target_branch: main
oompah.agent_run_id: da39e503-7103-4261-b2f9-0e9494bea8a5
oompah.review_url: https://github.com/lesserevil/oompah/pull/350
---
## Summary

Plan: plans/oompah-1.0-release.md#epic-d-finish-10-operator-and-project-docs

WHAT TO DO
Finish the operator and managed-project documentation needed for a 1.0 release.

DONE WHEN
Docs describe the current native tracker, GitHub-only release, service operation, and managed-project onboarding paths without stale Backlog.md or beads instructions.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:57
---
Review reconciliation reopened this task because it was marked In Review but no open review artifact exists.

No PR/MR for this branch was found.
Branch: `epic-OOMPAH-32`
Target branch: `main`
Unmerged commits: 265 commits
  45e07c5c OOMPAH-36: Mark stale beads/bd references as historical in .gitignore and .gitattributes
  89473ee0 Comment on oompah task OOMPAH-36
  a858a72d Comment on oompah task OOMPAH-27
  96176e29 Comment on oompah task OOMPAH-52
  efda52ac Comment on oompah task OOMPAH-52
  7c40d817 Comment on oompah task OOMPAH-52
  fce91d6d Update metadata for oompah task OOMPAH-52
  fe047c6b Update oompah task OOMPAH-52
  887152a6 Update oompah task OOMPAH-52
  9d38ae79 Update oompah task OOMPAH-27

Required: restore or recreate the PR/MR for this branch, then move the task back to In Review after the review exists.
---
author: oompah
created: 2026-06-22 14:58
---
Review reconciliation reopened this task because it was marked In Review but no open review artifact exists.

No PR/MR for this branch was found.
Branch: `epic-OOMPAH-32`
Target branch: `main`
Unmerged commits: 265 commits
  45e07c5c OOMPAH-36: Mark stale beads/bd references as historical in .gitignore and .gitattributes
  89473ee0 Comment on oompah task OOMPAH-36
  a858a72d Comment on oompah task OOMPAH-27
  96176e29 Comment on oompah task OOMPAH-52
  efda52ac Comment on oompah task OOMPAH-52
  7c40d817 Comment on oompah task OOMPAH-52
  fce91d6d Update metadata for oompah task OOMPAH-52
  fe047c6b Update oompah task OOMPAH-52
  887152a6 Update oompah task OOMPAH-52
  9d38ae79 Update oompah task OOMPAH-27

Required: restore or recreate the PR/MR for this branch, then move the task back to In Review after the review exists.
---
author: oompah
created: 2026-06-22 14:59
---
The epic branch `epic-OOMPAH-32` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.
---
author: oompah
created: 2026-06-22 14:59
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-22 14:59
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-06-22 15:01
---
Understanding: This branch (epic-OOMPAH-32) is stale and has fallen behind origin/main. My role as Merge Conflict Resolver is to fetch origin, rebase this branch onto origin/main, resolve any conflicts, run tests, and force-push. No new code changes — conflict resolution only.
---
author: oompah
created: 2026-06-22 15:01
---
Discovery: Branch has 265 commits on top of a merge base that is 359 commits behind origin/main. Key file changes: docs/cli-install.md, docs/cli-release.md, docs/managed-project-onboarding.md, docs/operator-runbook.md (the documentation work), plus .gitattributes/.gitignore, oompah/orchestrator.py, and .oompah/tasks/ metadata. Starting rebase now.
---
author: oompah
created: 2026-06-22 15:04
---
Implementation: Rebased epic-OOMPAH-32 onto origin/main. The branch had 265 commits, but 261 were task metadata commits already present in main — they were skipped. Only 4 real code commits were replayed: OOMPAH-34 (operator runbook), OOMPAH-33 (install/release docs refresh), OOMPAH-35 (managed-project onboarding checklist), OOMPAH-36 (.gitignore/.gitattributes beads cleanup). No conflicts arose during the rebase.
---
author: oompah
created: 2026-06-22 15:04
---
Verification: All 7120 tests pass (28 skipped, 14 warnings — pre-existing). Force-push succeeded: 45e07c5c -> b5685c4b. Branch is now 4 commits ahead of origin/main, 0 behind.
---
<!-- COMMENTS:END -->
