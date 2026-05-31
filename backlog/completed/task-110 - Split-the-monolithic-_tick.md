---
id: TASK-110
title: Split the monolithic _tick()
status: Done
assignee: []
created_date: 2026-03-08 21:18
updated_date: 2026-03-08 22:05
labels:
- archive:yes
- draft
- merge-conflict
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-k3d.2
  state: closed
  parent_id: oompah-k3d
  dependencies: []
  branch_name: oompah-k3d.2
  target_branch: null
  url: null
  created_at: '2026-03-08T21:18:42Z'
  updated_at: '2026-03-08T22:05:26Z'
  closed_at: '2026-03-08T22:05:26Z'
parent: TASK-108
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split the current _tick() into targeted handlers
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: c13eb0da-d0ec-409e-b05d-12598f8cb542
author: oompah
created: 2026-03-08T21:19:04Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fac26716-df05-4cd7-9d0a-6f653831c9e3
author: oompah
created: 2026-03-08T21:19:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 67b40467-6a7f-4f5f-b41c-8d41f4e0a2a0
author: oompah
created: 2026-03-08T21:19:31Z

I understand the issue: The monolithic _tick() method does 8 different things in one cycle (reconcile, fetch candidates, fetch reviews, fetch merged branches, pre-resolve blockers, sort/dispatch, yolo/archive/merged-label, auto-update). The goal is to split this into targeted handlers: _handle_dispatch_needed(), _handle_review_check(), _handle_reconcile(), _handle_yolo_review(), and _handle_auto_update(). My plan is to refactor _tick() by extracting these 5 focused handler methods that can be called independently, while keeping _tick() as the coordinator that calls them in the right order. The handlers will be independently testable. I'll write unit tests for each new handler.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4a18cc39-2232-4a43-bd27-ed45c7557cb2
author: oompah
created: 2026-03-08T21:21:23Z

Found the relevant code: The monolithic _tick() in oompah/orchestrator.py runs ~8 steps sequentially - reconcile, config validation, fetch reviews/candidates/merged branches in parallel, pre-resolve blockers, sort+dispatch, epic planning, reset orphaned in_progress, yolo/archive/merged-label in parallel, and auto-update. The refactoring plan is: (1) Extract _handle_reconcile() for reconciliation, (2) Extract _handle_review_check() for fetching reviews+merged branches, (3) Extract _handle_dispatch_needed() for candidates fetch+blocker resolution+sort+dispatch+epic planning+reset orphaned, (4) Extract _handle_yolo_review() for YOLO actions+archive+merged-labeling, (5) Extract _handle_auto_update() for git auto-update when idle. _tick() becomes a thin coordinator calling these in order. Each handler will be independently testable.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 371fef52-2a00-476c-8305-fc8c58a899aa
author: oompah
created: 2026-03-08T21:26:52Z

Implemented the split. Changed _tick() in oompah/orchestrator.py to delegate to 5 targeted handlers: (1) _handle_reconcile() — wraps existing _reconcile(), (2) _handle_review_check() — fetches forge state (reviews + merged branches), populates caches, (3) _handle_dispatch_needed() — fetches candidates, resolves blockers, dispatches issues + epics, resets orphaned issues, (4) _handle_yolo_review() — runs YOLO/archive/merged-label in parallel, returns timing tuple, (5) _handle_auto_update() — triggers git pull/restart when idle. _tick() is now a thin coordinator with clear comments on what each handler does. Added 42 tests in tests/test_orchestrator_handlers.py covering each handler's behavior independently and _tick()'s delegation order.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2efae95b-bdb5-473e-9455-cdbd3e71c4d5
author: oompah
created: 2026-03-08T21:28:19Z

Verification: All 770 tests pass (including the 42 new handler tests). No regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b8a31a7f-1dfb-4d13-b8c1-0e5dfec293d8
author: oompah
created: 2026-03-08T21:29:42Z

YOLO: Merge conflict detected on review #42. Rebase onto main and resolve conflicts.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 80b4d9f0-778d-43a1-b2d5-874f7258d252
author: oompah
created: 2026-03-08T21:29:49Z

Merge conflict detected: review #42 cannot be automatically rebased onto main.

Please resolve the conflicts on this branch (oompah-k3d.2):
1. Run: git fetch origin && git rebase origin/main
2. Resolve all conflicts, keeping the intent of both sides
3. Run tests to verify nothing is broken
4. Force-push: git push --force-with-lease
5. Verify the review is clean and CI passes
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f1bd0402-171f-4514-bcaf-909a81eaeca3
author: oompah
created: 2026-03-08T21:30:52Z

Merge conflict detected: review #42 cannot be automatically rebased onto main.

Please resolve the conflicts on this branch (oompah-k3d.2):
1. Run: git fetch origin && git rebase origin/main
2. Resolve all conflicts, keeping the intent of both sides
3. Run tests to verify nothing is broken
4. Force-push: git push --force-with-lease
5. Verify the review is clean and CI passes
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4050d867-4c29-4dc1-b1cf-f82b4131c2c8
author: oompah
created: 2026-03-08T21:39:52Z

Merge conflict detected: review #42 cannot be automatically rebased onto main.

Please resolve the conflicts on this branch (oompah-k3d.2):
1. Run: git fetch origin && git rebase origin/main
2. Resolve all conflicts, keeping the intent of both sides
3. Run tests to verify nothing is broken
4. Force-push: git push --force-with-lease
5. Verify the review is clean and CI passes
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 48514fca-e50f-464f-97af-4a6ccc8bc441
author: oompah
created: 2026-03-08T21:45:29Z

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f78695fb-c84d-40bc-8828-b4bfd6b8e406
author: oompah
created: 2026-03-08T21:45:29Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2003ecbf-01e3-45cf-b134-b3d703a1baf2
author: oompah
created: 2026-03-08T21:45:47Z

I understand the issue: This branch has a merge conflict that needs to be resolved by rebasing onto main. The branch contains a commit that splits the monolithic _tick() into targeted handlers. Main has 2 new commits since the branch diverged: 'Make codebase VCS-provider agnostic, auto-create reviews on push' and 'Let merge-conflict and ci-fix issues bypass open-review dispatch gate'. I need to rebase oompah-k3d.2 onto origin/main, resolve any conflicts, run tests, and force-push.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2f46119d-3c28-4a9d-96a7-e0a1b0e81942
author: oompah
created: 2026-03-08T21:52:55Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d17ac9f1-aa40-4ba0-8e57-4a3453e497f2
author: oompah
created: 2026-03-08T21:52:56Z

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4fa9ac04-fc14-46e4-a5f9-477ba1592955
author: oompah
created: 2026-03-08T21:53:41Z

I understand the issue: The branch oompah-k3d.2 has the _tick() split commit and needs to be rebased onto origin/main. The local branch currently sits on top of commit a2a37c8, but origin/main has one additional commit: '8985225 Exclude YOLO projects from reviews-needing-attention count'. I need to rebase onto origin/main, resolve any conflicts, run tests, and force-push.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 67a50304-7b4b-4e13-a6b9-02edbde865e5
author: oompah
created: 2026-03-08T22:04:15Z

Found the conflict: The branch's test file used the old name '_unmerged_pr_branches' but the main branch renamed it to '_unmerged_review_branches' in commit b94db08 (VCS-provider agnostic changes). Rebase applied cleanly, then I updated the test names in test_orchestrator_handlers.py and fixed the docstring in orchestrator.py to match the renamed attribute. The 5 pre-existing failures in test_orchestrator_merged.py::TestBlockerHasUnmergedPr are from origin/main and unrelated to this branch.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14863c9e-e695-4a03-a0e0-7d167c8359ac
author: oompah
created: 2026-03-08T22:04:53Z

Verification: 882 tests pass. The 5 failures in test_orchestrator_merged.py::TestBlockerHasUnmergedPr are pre-existing on origin/main (unrelated to this branch). All 42 new handler tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 54660ba3-4d77-4a6b-bdd5-92111c3a0fe5
author: oompah
created: 2026-03-08T22:05:21Z

Completion: Successfully rebased oompah-k3d.2 onto origin/main. The rebase itself was clean (no merge conflicts). The only conflict resolution needed was updating test_orchestrator_handlers.py to use '_unmerged_review_branches' instead of the old '_unmerged_pr_branches' name (renamed in b94db08). Also fixed the docstring in _handle_review_check(). Force-pushed with --force-with-lease. Branch is now clean and up to date with origin.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b2270faf-37bf-44ad-8faf-533303b1fc5e
author: oompah
created: 2026-03-08T22:05:26Z

Agent completed successfully in 751s (948051 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
