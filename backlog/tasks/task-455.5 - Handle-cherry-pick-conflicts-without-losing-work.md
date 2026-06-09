---
id: TASK-455.5
title: Handle cherry-pick conflicts without losing work
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-09 01:12'
labels:
  - task
dependencies:
  - TASK-455.4
parent_task_id: TASK-455
priority: high
ordinal: 100000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When a cherry-pick conflicts, leave the worktree intact, mark the child task Needs Rebase or Needs Human with a diagnostic comment, update source metadata to conflict, and ensure later ticks do not overwrite the conflicted workspace.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 23:58
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 23:58
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 23:59
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 23:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 33s
- Log: TASK-455.5__20260608T235853Z.jsonl
---

author: oompah
created: 2026-06-09 00:00
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 00:00
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:00
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 00:13
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:13
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:14
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 00:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 44s
- Log: TASK-455.5__20260609T001403Z.jsonl
---

author: oompah
created: 2026-06-09 00:15
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 00:16
---
Focus: Maintenance Engineer
---

author: oompah
created: 2026-06-09 00:30
---
Agent stalled 1 time(s) (892s (187282 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 00:31
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 186.0K in / 1.3K out [187.3K total]
- Cost: $0.0000
- Exit: stalled, Duration: 14m 52s
- Log: TASK-455.5__20260609T001635Z.jsonl
---

author: oompah
created: 2026-06-09 00:32
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-09 00:32
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:33
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 00:33
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 52s
- Log: TASK-455.5__20260609T003309Z.jsonl
---

author: oompah
created: 2026-06-09 00:35
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-09 00:39
---
Understanding & Plan: This task is NOT a duplicate - it's a follow-on to TASK-455.4. TASK-455.4 implemented the cherry-pick+push+PR flow but took a shortcut on conflict handling: it calls git cherry-pick --abort (cleaning the worktree) and only updates metadata. TASK-455.5 requires: (1) Leave the worktree intact with conflict markers in place instead of aborting; (2) Detect if a cherry-pick is already in progress to skip on later ticks; (3) Mark the child task as 'Needs Rebase' (the correct status for merge conflicts) with a diagnostic comment; (4) Update source metadata to 'conflict'. Plan: modify cherry_pick_pr_creator.py to (a) add _has_cherry_pick_in_progress() helper, (b) skip --abort on conflict, (c) mark child task Needs Rebase + add diagnostic comment on conflict. Add tests.
---

author: oompah
created: 2026-06-09 01:12
---
Discovery: The previous TASK-455.4 implementation in cherry_pick_pr_creator.py was calling git cherry-pick --abort on conflict (leaving the worktree clean) and only updating metadata without changing the child task status. Three gaps found: (1) No in-progress cherry-pick detection — CHERRY_PICK_HEAD check missing; (2) Worktree was being cleaned (abort called) instead of left intact; (3) Child task status not updated to Needs Rebase and no diagnostic comment added. The reconciler correctly skips CONFLICT entries (no case handles them) but lacked the in-progress detection guard.
---

author: oompah
created: 2026-06-09 01:12
---
Implementation: Modified oompah/cherry_pick_pr_creator.py: (1) Added _has_cherry_pick_in_progress(wt_path) helper that checks for CHERRY_PICK_HEAD via 'git rev-parse --git-dir'; (2) apply_cherry_pick() now checks for in-progress cherry-pick at start and raises CherryPickConflictError immediately (prevents later ticks overwriting existing conflict state); (3) On conflict, cherry-pick --abort is NO LONGER called — worktree left intact with conflict markers; (4) cherry_pick_push_and_open_pr() now: marks child task Needs Rebase via tracker.update_issue(), adds diagnostic comment with commit list + worktree path + conflict details via tracker.add_comment(), both non-fatal. Non-conflict failures still call --abort for worktree hygiene. Added 11 new tests: 5 for _has_cherry_pick_in_progress, 4 for apply_cherry_pick conflict changes, 4 for cherry_pick_push_and_open_pr conflict marking. Total: 53 tests all passing.
---
<!-- COMMENTS:END -->
