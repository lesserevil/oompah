---
id: OOMPAH-219
type: task
status: In Progress
priority: null
title: Detect shared-worktree commits that absorb another task's changes
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-17T18:24:58.199363Z'
updated_at: '2026-07-17T18:39:12.849320Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2e94895f-cdec-4e17-a20d-f0c745671c95
oompah.task_costs:
  total_input_tokens: 28
  total_output_tokens: 6465
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 28
      output_tokens: 6465
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 28
    output_tokens: 6465
    cost_usd: 0.0
    recorded_at: '2026-07-17T18:38:56.624796+00:00'
---
## Summary

Implement persistent reconciliation for shared-epic worktree commit races.

Problem: TRICKLE-45 edited documentation in the shared epic worktree, but could not commit. A later TRICKLE-44 commit on the same shared branch absorbed those edits. TRICKLE-45 then exhausted its incomplete-session limit and moved to Needs Human even though its acceptance work had landed.

Required behavior:
1. When a shared-epic child exits with uncommitted changes or fails the landing gate, persist evidence on the task: shared branch name, observed base SHA, and changed file paths.
2. During normal reconciliation (including after a service restart), inspect commits added to that shared branch after the recorded base SHA.
3. When a later commit touches the recorded paths, add a task comment naming the absorbing commit(s), clear the stale incomplete-session state, and return the task to Open for a fresh verification/closure run. Do not automatically mark the task Done merely from path overlap.
4. Remove or supersede the evidence once the task reaches a terminal state or the verification run completes.
5. Keep non-shared task behavior unchanged and fail open on Git errors.

Tests required:
- Capture records branch, SHA, and paths for a dirty shared worktree.
- Reconciliation after a later matching shared-branch commit reopens the task and writes attribution.
- Unrelated commits do not reopen the task.
- Evidence survives service restart/persistence boundary.
- Terminal tasks and non-shared tasks are ignored.
- Git errors fail open without changing task state.

Acceptance criteria:
- A reproduction equivalent to TRICKLE-45/TRICKLE-44 does not leave the absorbed task in Needs Human.
- Operator-visible task history identifies the absorbing commit and asks a fresh agent to verify/close the task.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-17 18:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 18:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 18:36
---
Understanding: Investigating OOMPAH-219 as Duplicate Investigator. The issue describes a race condition in shared-epic worktrees where one task's uncommitted changes get absorbed by another task's commit (TRICKLE-44/TRICKLE-45 scenario). Searching for duplicate or closely related tasks before any implementation work.
---
author: oompah
created: 2026-07-17 18:38
---
Focus handoff: duplicate_detector

Outcome: No duplicate found. OOMPAH-219 describes a novel feature — persistent reconciliation for shared-epic worktree commit races — that is not covered by any existing task.

Search scope:
- All .oompah/tasks/{archived,merged,done,in-progress} files (150+ tasks)
- oompah/ source, plans/, docs/ for keywords: shared-worktree, absorb, TRICKLE-44/45, base_sha, changed_paths, uncommitted, evidence+persist, commit race, landing gate

Closest reviewed candidates (NOT duplicates):
1. OOMPAH-218 (Merged): Count incomplete-agent safety limit per focus — covers the incomplete-session counter per focus, but does NOT cover the case where another task's commit absorbs uncommitted changes and the stale state persists.
2. OOMPAH-168 (Merged): Orchestration cleanup for shared-only epic workflow — consolidates strategy to shared-only, but does NOT implement evidence persistence for unabsorbed dirty worktree changes.
3. OOMPAH-165 (Merged): Epic rollup status bug for nested epics — different class of shared-epic bug (premature Merged state), not the commit-absorption race.

Relevant code locations for the implementation agent:
- oompah/orchestrator.py: _on_worker_exit / incomplete-session tracking (lines 16282-16330), _shared_epic_child_done, shared-epic landing gate block (lines 16315-16430)
- oompah/landing_gate.py: check_landing_gate, shared-epic branch resolution (lines 89-263)
- oompah/orchestrator.py: _epic_rebase_states pattern (lines 850-1177) — good precedent for persistence structure (service_state.json)
- tests/ directory for existing patterns

Remaining work: Full feature implementation per the task description (5 behavior requirements, 6 test requirements, 2 acceptance criteria). No blockers found.

Recommended next focus: feature
---
author: oompah
created: 2026-07-17 18:38
---
Agent completed successfully in 181s (6493 tokens)
---
author: oompah
created: 2026-07-17 18:39
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 57, Tool calls: 46
- Tokens: 28 in / 6.5K out [6.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 1s
- Log: OOMPAH-219__20260717T183600Z.jsonl
---
<!-- COMMENTS:END -->
