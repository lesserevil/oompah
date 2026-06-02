---
id: TASK-402.14
title: Recognize Backlog task closure from agent worktrees
status: Done
assignee:
  - oompah
created_date: '2026-06-02 15:23'
updated_date: '2026-06-02 15:31'
labels:
  - bug
dependencies: []
parent_task_id: TASK-402
priority: high
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug discovered while investigating TASK-407.2 on 2026-06-02.

Observed behavior:
- The agent worktree `/home/shedwards/.oompah/worktrees/oompah/TASK-407.2` had `TASK-407.2` marked `Done` and pushed to `origin/TASK-407.2`.
- PR #197 was merged into `main` and the `TASK-407.2` worktree passed `make test`: 3779 passed, 4 skipped.
- The managed service checkout `/home/shedwards/.oompah/repos/oompah` still had `TASK-407.2` in `Needs Human` because `Orchestrator._on_worker_exit` checked `tracker.fetch_issue_detail(entry.identifier)` against the project tracker cwd, which reads the managed main checkout, not the worker worktree branch.
- As a result, oompah treated a valid branch-local Backlog closure as `completed_without_closing`, retried Duplicate Investigator agents, and eventually marked the task `Needs Human`.

Expected behavior:
- When an agent exits normally, oompah should detect terminal Backlog status written in the worker worktree/branch before incrementing `completed_without_closing`.
- If the worktree task is terminal, the normal close gate, unpushed gate, completion verifier, review creation, and parent-epic handling should run using that terminal task detail.
- Oompah must not escalate, retry, or mark `Needs Human` solely because the managed checkout has not yet received the worktree task-file status.

Implementation guidance for a junior developer:
1. Read `Orchestrator._on_worker_exit` in `oompah/orchestrator.py`, especially the `reason == normal` path around `tracker.fetch_issue_detail` and the `completed_without_closing` retry block.
2. Read `BacklogMdTracker.fetch_issue_detail` in `oompah/tracker.py` and `ProjectStore.create_worktree` / `sync_task_file_to_worktree` in `oompah/projects.py` to understand which checkout each tracker reads.
3. Add a helper that resolves the worker worktree path for `entry.identifier`, reads the Backlog task detail from that worktree using `BacklogMdTracker(cwd=worktree_path)`, and returns it only when it is the same task and has a terminal status.
4. In `_on_worker_exit`, before treating `current` as non-terminal, consult that worktree task detail. If the worktree detail is terminal, treat it as the current closed issue and continue through the existing close-gate / unpushed-gate / completion-verifier flow.
5. Preserve fail-open behavior: if the worktree path is missing, the Backlog task file is absent, or parsing fails, log at debug/warning as appropriate and keep the existing managed-tracker behavior.
6. Add regression tests that simulate managed tracker state `In Progress` but worktree Backlog state `Done`, then assert `_on_worker_exit` does not increment `reopen_counts`, does not schedule a `completed_without_closing` retry, and does not mark `Needs Human`.
7. Add a negative test where the worktree task is not terminal, confirming the existing `completed_without_closing` behavior still applies.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Tests cover both recognized worktree closure and non-terminal worktree fallback.
- [x] #2 Branch-local Backlog task closure is recognized on normal agent exit.
- [x] #3 TASK-407.2-style branch-local closure does not produce Duplicate Investigator retries or Needs Human escalation.
- [x] #4 Existing close gate, unpushed gate, completion verifier, review creation, and parent-epic behavior still run for recognized worktree closures.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test passes.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 15:27

Claiming this to fix the Backlog worktree closure detection bug found with TASK-407.2.
<!-- COMMENT:END -->

<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 15:31

Implemented the worktree Backlog closure fix. RunningEntry now records the worker workspace path, worker setup populates it for API/ACP/CLI agents, and _on_worker_exit reads a terminal Backlog task from that workspace before treating a normal exit as completed_without_closing. Added regression coverage for terminal worktree closure and non-terminal fallback. Verification: targeted TestNeedsHumanTransitions passed, make test passed with 3896 passed and 17 warnings, and make check-secrets passed.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the TASK-407.2 closure-detection bug by teaching _on_worker_exit to honor terminal Backlog task state written in the agent worktree. The running entry now records the exact workspace path used by API, ACP, and CLI workers. On normal worker exit, oompah checks that workspace for the same task in a terminal status and routes it through the existing close gate, unpushed gate, completion verifier, review creation, and parent epic handling instead of escalating completed_without_closing. Added regression tests for recognized worktree closure and non-terminal fallback. Verification: make test passed with 3896 passed and 17 warnings; make check-secrets passed.
<!-- SECTION:FINAL_SUMMARY:END -->
