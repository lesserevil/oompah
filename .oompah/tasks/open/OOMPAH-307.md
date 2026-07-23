---
id: OOMPAH-307
type: bug
status: Open
priority: 1
title: Keep shared-epic child work and merge state on the epic branch
parent: null
children:
- OOMPAH-308
- OOMPAH-309
- OOMPAH-310
- OOMPAH-311
- OOMPAH-312
- OOMPAH-313
blocked_by: []
labels:
- focus-complete:duplicate_detector
- focus-complete:epic_planner
- epic:stale
assignee: null
created_at: '2026-07-21T16:27:57.025790Z'
updated_at: '2026-07-23T00:14:01.219891Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 33020a3a-c101-471d-b89e-29be042ac8f7
oompah.task_costs:
  total_input_tokens: 255527
  total_output_tokens: 9635
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 255527
      output_tokens: 9635
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 255429
    output_tokens: 2216
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:41:14.036695+00:00'
  - profile: deep
    model: unknown
    input_tokens: 19
    output_tokens: 4651
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:47:49.344114+00:00'
  - profile: default
    model: unknown
    input_tokens: 79
    output_tokens: 2768
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:55:37.496646+00:00'
---
## Summary

Fix native Markdown task dispatch so child tasks in a shared epic execute on the epic work branch and are not independently merged to main.\n\nObserved reproduction: OOMPAH-286 is a child of epic OOMPAH-285 but was assigned work_branch=OOMPAH-286, target_branch=main, and PR #466. Its status became Merged even though the parent epic branch remains the intended integration branch. Under the shared-only epic model, this child should contribute to OOMPAH-285’s branch and remain non-terminal until the epic is merged.\n\nImplementation requirements:\n- Identify shared epic membership before creating a worktree, branch, PR, or terminal-state transition.\n- Route child commits and tests to the parent epic worktree/work branch; never create a child-to-main PR for a shared child.\n- Record child completion as integrated-on-epic-branch (or equivalent non-terminal state) and show the parent epic/branch in dashboard, detail, CLI/API, and release association views.\n- Promote child tasks to Merged only when the parent epic merge to its target branch is confirmed.\n- Reconcile existing affected children safely: detect independently created child PRs/branches, preserve history, and surface an operator remediation path without rewriting or losing commits.\n\nTests:\n- Shared-epic child dispatch uses parent worktree/branch and creates no child PR to main.\n- Child completion before epic merge is not terminal; after confirmed epic merge it becomes Merged.\n- Regression fixture for OOMPAH-285/OOMPAH-286 routing prevents a child branch/PR #466-style outcome.\n- Existing independently merged child data is diagnosed and does not corrupt the epic branch.\n\nAcceptance criteria:\n- Shared-epic children never bypass the epic branch.\n- UI status explains whether a child is complete on the epic branch versus merged to target.\n- No child is falsely labeled Merged before its epic delivery is merged.\n- Relevant Makefile tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:40
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:41
---
Agent completed successfully in 62s (257645 tokens)
---
author: oompah
created: 2026-07-21 16:41
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 255.4K in / 2.2K out [257.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 2s
- Log: OOMPAH-307__20260721T164019Z.jsonl
---
author: oompah
created: 2026-07-21 16:41
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-307`. No stronger profile is configured; retrying with 'deep' in 10s (1/3).
---
author: oompah
created: 2026-07-21 16:45
---
Retrying (attempt #3, agent: deep)
---
author: oompah
created: 2026-07-21 16:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:47
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-307 is a unique bug covering shared-epic child dispatch routing to the parent epic branch, prevention of child-to-main PRs, and child status promotion gating on epic merge. No existing task addresses this behavior.

2. Evidence:
   - Searched .oompah/tasks/ (archived, backlog, done, merged, needs-ci-fix, needs-rebase), plans/, docs/, README.md, WORKFLOW.md for: shared epic, epic branch, child dispatch, work_branch, target_branch, child PR.
   - Zero matches across all directories.
   - Closest reviewed tasks:
     - OOMPAH-285 (In Progress): parent epic for prompt injection defense — not about branch routing
     - OOMPAH-286 (Merged): exact reproduction case — child given own branch (OOMPAH-286) and PR #466 merged to main; this is the bug OOMPAH-307 wants to prevent
     - OOMPAH-282 (Backlog): unrelated state-branch migration encoding error
     - plans/multi-branch-support.md: covers per-task target_branch and project default_branch but no epic branch child routing concept
   - No existing task or design doc describes the fix.

3. Remaining work and risks:
   - Implementation: Identify shared epic membership before worktree/branch/PR creation (projects.py, orchestrator.py).
   - Route child commits and tests to parent epic worktree/branch; prevent child-to-main PR.
   - Record child completion as integrated-on-epic-branch (non-terminal state); promote to Merged only when parent epic merges.
   - Reconcile OOMPAH-286/PR #466 existing data safely.
   - Key files: oompah/orchestrator.py (_create_workspace_for_issue, _ensure_review_exists, _open_epic_main_prs), oompah/projects.py (create_worktree, create_epic_worktree), oompah/models.py (Issue, epic fields).
   - Tests: regression fixture for OOMPAH-285/286 routing, shared-epic dispatch test, status-promotion lifecycle test.

4. Recommended next focus: feature (implement shared-epic child routing and status lifecycle).
---
author: oompah
created: 2026-07-21 16:47
---
Agent completed successfully in 123s (4670 tokens)
---
author: oompah
created: 2026-07-21 16:47
---
Run #4 [attempt=4, profile=deep, role=deep -> Claude/default]
- Turns: 38, Tool calls: 28
- Tokens: 19 in / 4.7K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 3s
- Log: OOMPAH-307__20260721T164550Z.jsonl
---
author: oompah
created: 2026-07-21 16:47
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:48
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:48
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-21 16:52
---
Epic Planner: Understanding and decomposition plan

OOMPAH-307 addresses a real regression path for native (oompah_md) shared-epic children. Code investigation confirms:

Key files:
- oompah/orchestrator.py: _create_workspace_for_issue, _resolve_parent_epic, _epic_rollup_child_strategy, _ensure_review_exists, Done→Merged promotion paths (~lines 4651-4810, 8280-8330, 8595-8625)
- oompah/statuses.py: epic_rollup_state, status lifecycle
- oompah/projects.py: create_worktree, create_epic_worktree (lines 1464-1615, 1740+)
- tests/test_epic_strategy.py: existing shared-epic routing tests

Current state of fixes: Some protections exist (_create_workspace_for_issue routes to epic worktree, _ensure_review_exists skips per-child PR when parent_epic is not None, YOLO closes stale child PRs). But these fail under the following conditions:

Gap A: When a native child has stale work_branch/branch_name in its frontmatter metadata (e.g., work_branch=OOMPAH-286), _branch_for_issue returns the stale per-task branch even after routing to the epic worktree. This stale branch is used in Done→Merged promotion and can trigger false Merged status.

Gap B: When _resolve_parent_epic fails (tracker error, parent not found), the shared protection is entirely bypassed. The child falls through to per-task worktree, gets its own branch, and may receive a per-child PR to main.

Gap C: No code path updates the native child's work_branch metadata to the epic branch name after routing. The child's frontmatter still says work_branch=OOMPAH-286 even when dispatched correctly on the epic branch.

Gap D: Child completion status is non-trivially Done, but the epic-merge-triggered Merged promotion path needs verification. The _epic_rollup_child_strategy check at line 8282 guards one path but there's another at line 8607 that also depends on rollup_strategy being 'shared'.

Gap E: No diagnostic or remediation path for existing affected children (OOMPAH-286/PR #466 already independently merged).

Gap F: No regression fixture for the specific OOMPAH-285/286 scenario.

Decomposing into 5 focused child tasks.
---
author: oompah
created: 2026-07-21 16:55
---
Focus handoff: epic_planner

1. Outcome: Epic decomposed into 6 actionable child tasks (OOMPAH-308 through OOMPAH-313). Each task has a detailed description with implementation scope, relevant files, required tests, and acceptance criteria. Epic status set to Backlog.

2. Evidence / decisions:
   - Investigated orchestrator.py, projects.py, models.py, statuses.py, oompah_md_tracker.py, and all test_epic_strategy.py / test_shared_epic_display_status.py tests
   - Key files: oompah/orchestrator.py (_create_workspace_for_issue ~4719, _resolve_parent_epic ~4651, _epic_rollup_child_strategy ~4700, _ensure_review_exists ~7803, Done→Merged promotion ~8280-8330/8595-8625)
   - Confirmed partial protections already exist but with three critical gaps for native (oompah_md) tasks

3. Child tasks created:
   - OOMPAH-308 (P1): Fix stale work_branch metadata when child routes to shared epic worktree
   - OOMPAH-309 (P1): Harden shared-epic protection when _resolve_parent_epic fails with parent_id set
   - OOMPAH-310 (P2): Verify/harden epic-merge-triggered Merged promotion for shared children [depends on 308, 309]
   - OOMPAH-311 (P2): Diagnose and surface remediation for existing independently-merged children (OOMPAH-286/PR #466 pattern)
   - OOMPAH-312 (P3): UI/dashboard: show Done-on-epic-branch vs Merged-to-target status [depends on 310]
   - OOMPAH-313 (P1): Regression tests: OOMPAH-285/286 fixture + native child lifecycle [depends on 308, 309]

4. Remaining work and risks:
   - OOMPAH-308 and OOMPAH-309 are the critical path — start here. They address the root cause gaps.
   - OOMPAH-313 (regression tests) should be written alongside or after 308/309.
   - OOMPAH-311 is independent and can be done in parallel.
   - OOMPAH-310 and OOMPAH-312 follow after the core routing fixes land.
   - Risk: oompah/orchestrator.py is very large (~17000 lines); agents should use grep/search to navigate, not read the whole file.

5. Recommended next focus: feature (implement OOMPAH-308 and OOMPAH-309 — the root routing/hardening fixes)
---
author: oompah
created: 2026-07-21 16:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 59
- Tokens: 79 in / 2.8K out [2.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 36s
- Log: OOMPAH-307__20260721T164803Z.jsonl
---
<!-- COMMENTS:END -->
