---
id: OOMPAH-513
type: bug
status: In Progress
priority: 1
title: Fail closed on task writes from a managed code checkout
parent: OOMPAH-511
children: []
blocked_by:
- OOMPAH-512
labels: []
assignee: null
created_at: '2026-07-28T15:16:43.939778Z'
updated_at: '2026-07-28T15:45:12.164293Z'
work_branch: epic-OOMPAH-511
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7d1f7dd7-46fa-4ae9-ad9b-95a4e3c24178
oompah.work_branch: epic-OOMPAH-511
---
## Summary

Implementation scope

Add a defensive write policy at the native Markdown tracker boundary so a tracker representing a managed state-branch project cannot commit task mutations on the repository's default/code branch. The check must run before any task file or Git index mutation and must cover create, update, comment, label, archive, and maintenance-driven writes through the common persistence path. Prefer an explicit policy/configuration supplied by the project-aware factory over heuristics. Keep reads available where safe. Preserve legacy standalone operation when no state branch is configured, and preserve the dedicated state-branch worktree/checkpoint path.

Relevant files

oompah/oompah_md_tracker.py, oompah/orchestrator.py/project tracker factory code, state-branch tracker tests, and any tracker protocol/type definitions needed for an explicit read-only or expected-write-branch policy.

Required tests

Using disposable repositories only, reproduce an unscoped/default-branch mutation attempt and assert it fails before the task tree, Git index, HEAD, or remote changes. Cover the configured state-branch success path, every public mutation family through the shared guard, legacy standalone success, and an actionable diagnostic. Run focused native tracker/state-branch tests and make test.

Acceptance criteria

A misrouted managed-project task write cannot create or modify .oompah/tasks, cannot create a commit, and cannot push the default branch; correct state-branch writes still checkpoint; standalone behavior remains compatible; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:37
---
Claimed in the OOMPAH-511 isolated worktree. Implemented a tracker-level fail-closed guard covering all public native task mutation families while preserving explicit standalone/legacy writes and non-task release ledgers.
---
author: oompah
created: 2026-07-28 15:41
---
Completed in commit 6533e235e. The native tracker now rejects unscoped managed task writes before filesystem or Git mutation across create, update, archive, comment, label, parent, dependency, attachment, metadata, raw-body, and external-import operations. Correct state-branch and standalone paths remain covered.
---
author: oompah
created: 2026-07-28 15:41
---
Added a fail-closed native tracker write policy with complete public-mutation regression coverage.
---
author: oompah
created: 2026-07-28 15:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:43
---
Understanding: Screening OOMPAH-513 for an existing task covering the same managed-checkout write-guard bug. I will search task records by state-branch/write-policy terminology, inspect full candidate task histories, and either archive this as a confirmed duplicate or hand off with evidence if no duplicate exists. No implementation will be attempted in this focus.
---
author: oompah
created: 2026-07-28 15:45
---
Discovery: Duplicate screening found no confirmed duplicate. OOMPAH-256 covers correct configured state-branch routing, while OOMPAH-512 removes projectless managed-runtime tracker selection; neither supplies OOMPAH-513's separate tracker-boundary rejection of an already-misrouted write. OOMPAH-511 explicitly decomposes these as distinct child scopes. Read-only inspection also confirms pushed commit 6533e235e already contains allow_default_branch_task_writes, the pre-mutation guard, public-mutation coverage, and disposable-repository isolation tests.
---
<!-- COMMENTS:END -->
