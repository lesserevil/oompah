---
id: TASK-467.1
title: Add per-project locks for tracker writes and git mutations
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 20:08'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
  - oompah/projects.py
modified_files:
  - oompah/orchestrator.py
  - oompah/projects.py
  - tests/test_submit_queue_concurrency.py
parent_task_id: TASK-467
ordinal: 11
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce explicit per-project and, where needed, per-epic locks for operations that mutate Backlog task files, GitHub tracker state, git worktrees, branches, or review metadata. Use the locks from dispatch, maintenance, YOLO, epic rollup, self-heal, and worker-exit paths so background parallelism cannot corrupt shared state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tracker writes for the same project are serialized through a single lock.
- [ ] #2 Git worktree and branch mutations for the same project cannot overlap unsafely.
- [ ] #3 Tests cover concurrent maintenance plus dispatch attempts on the same project.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:51
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 19:55
---
UNDERSTANDING: As Test Engineer, I need to implement per-project locking for tracker writes and git mutations, then write comprehensive tests. The implementation involves: (1) adding a per-project lock registry to ProjectStore so tracker writes and git worktree mutations for the same project are serialized, (2) using those locks from dispatch, maintenance, YOLO, self-heal, and worker-exit paths. The TASK-465.2 dispatch lane lock is already on the epic-TASK-465 branch but not yet in main; I'll work with the current codebase. Plan: add ProjectLockRegistry to projects.py, expose a project_lock() context manager, apply it at key tracker/git mutation sites in orchestrator.py, then write unit tests that verify serialization and cross-project independence.
---

author: oompah
created: 2026-06-08 20:03
---
DISCOVERY: Per-project locks implemented in oompah/projects.py: added threading.RLock per project_id to ProjectStore, exposed via project_write_lock(). Worktree mutation methods (create_worktree, remove_worktree, create_epic_worktree, remove_epic_worktree) now acquire the lock internally via the thin wrapper + locked helper pattern. In orchestrator.py, _reset_orphaned_in_progress uses the lock around tracker.update_issue() calls. RLock chosen to allow callers holding the lock to re-enter worktree methods without deadlock. Now writing comprehensive tests.
---

author: oompah
created: 2026-06-08 20:08
---
IMPLEMENTATION: Added per-project write locks to oompah/projects.py (ProjectStore._project_locks: dict[str, RLock], project_write_lock() method) and wired them into worktree mutation methods. Changes: (1) ProjectStore.create_worktree/remove_worktree/create_epic_worktree/remove_epic_worktree each acquire the per-project RLock before delegating to _*_locked() helpers. (2) orchestrator._reset_orphaned_in_progress wraps tracker.update_issue() with the project lock. (3) contextlib imported in orchestrator for nullcontext(). New test file tests/test_project_locks.py with 26 tests covering: lock API (creation, identity, independence, reentrancy, thread safety), serialization of concurrent worktree ops for same project, independence of different projects, epic worktree locking, orchestrator integration, thread-pool concurrency, and lock release on error.
---
<!-- COMMENTS:END -->
