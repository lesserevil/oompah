---
id: OOMPAH-581
type: task
status: In Review
priority: null
title: Prune merged epic repair workspaces with task-style branch paths
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T04:35:07.041991Z'
updated_at: '2026-07-31T02:35:28.293569Z'
work_branch: OOMPAH-581
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/600
review_number: '600'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a338ea5975a877aefdcedab72f7a1b0b63004ce67dfebb4118df198b424a58e0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T04:37:29.793932+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search for related tasks, I've investigated\
    \ whether OOMPAH-581 is a duplicate of any existing issue. Here's my analysis:\n\
    \n## Search Findings\n\nI searched the complete `.oompah/tasks` directory across\
    \ all states:\n- **Open tasks**: Only OOMPAH-281 (self-hosted GitHub Actions runner\
    \ setup) \u2014 completely unrelated\n- **Merged tasks**: 7 tasks (OOMPAH-271,\
    \ 272, 275, 277, 278, 279, 280) \u2014 none related to epic repair/cleanup\n-\
    \ **Archived tasks**: 200+ historical tasks \u2014 no epic repair/worktree pruning\
    \ tasks found\n- **Backlog**: Only OOMPAH-282 (UnicodeEncodeError in state_branch_migration)\
    \ \u2014 unrelated\n\n### Keyword searches performed\n- `epic|cleanup|worktree`\
    \ \u2014 no matches in open/merged\n- `terminal|branch.*prune|worktree.*prune|maintenance|cleanup`\
    \ \u2014 no matches\n- `epic|state.*branch|orchestrator` \u2014 no matches\n-\
    \ `459` (GitHub reference from task description) \u2014 found OOMPAH-282, which\
    \ is an unrelated state_branch_migration error\n\n### Related GitHub issue\nOOMPAH-282\
    \ references GitHub issue `lesserevil/oompah#459`, but that issue is about a UnicodeEncodeError\
    \ in state_branch_migration, not epic workspace cleanup. The comments in OOMPAH-581\
    \ note that issue #459 **exposed** the problem that OOMPAH-581 aims to automate,\
    \ but they are addressing different concerns.\n\n## Conclusion\n\n**OOMPAH-581\
    \ is a unique task** with no active duplicate:\n- No existing task covers automating\
    \ the pruning of merged epic repair workspaces with task-style branch paths\n\
    - The manual cleanup already performed (mentioned in comments) is a one-off that\
    \ this task aims to make automatic for future occurrences\n- All related maintenance/cleanup\
    \ tasks are in terminal states or address different problems\n\n---\n\nFocus handoff:\
    \ duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\nMatches:\
    \ none\n\nEvidence: Comprehensive search of `.oompah/tasks` (300+ task files across\
    \ open/merged/archived/backlog) revealed no active tasks addressing epic repair\
    \ workspace cleanup or terminal epic mainten"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 6a4de8a6-701b-4c8a-b916-6798acc68b91
oompah.task_costs:
  total_input_tokens: 46127
  total_output_tokens: 7383
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46037
      output_tokens: 5042
      cost_usd: 0.0
    sonnet:
      input_tokens: 90
      output_tokens: 2341
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 122
    output_tokens: 4044
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:37:29.792877+00:00'
  - profile: default
    model: haiku
    input_tokens: 45915
    output_tokens: 998
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:38:26.022994+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 90
    output_tokens: 2341
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:47:55.550438+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-581__20260730T043610Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-581
    source_sha: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
    completed_at: '2026-07-30T04:37:29.807776+00:00'
  - run_id: OOMPAH-581__20260730T043750Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: refactor
    source_branch: OOMPAH-581
    source_sha: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
    completed_at: '2026-07-30T04:38:26.026202+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-581
  head_sha: 741a7d88b2ad409575a0b3577564b98f57733f87
  submitted_at: '2026-07-30T04:47:42.763165+00:00'
  updated_at: '2026-07-30T04:47:42.763165+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/600
oompah.review_number: '600'
oompah.work_branch: OOMPAH-581
oompah.target_branch: main
---
## Summary

Live cleanup after OOMPAH-459 exposed one remaining owned legacy shape: a terminal epic records work_branch=epic-<id>, but an epic repair/planner run may leave a clean task-style managed worktree at <worktree_root>/<id> on branch <id>. Implementation scope: extend terminal maintenance cleanup in oompah/projects.py/orchestrator cleanup routing to recognize this exact same-identifier repair workspace only for terminal epic records, require the managed registered path and owned exact branch, and delete its worktree plus local/remote ref only when clean and merged/ancestor-safe. Never infer arbitrary paths, shared branches, dirty worktrees, or unmerged heads. Tests: real bare-remote scenario for a terminal epic with canonical epic work_branch plus auxiliary <id> repair worktree/branch; prove cleanup removes the auxiliary workspace and refs, while dirty, unmerged, shared, and different-identifier branches remain preserved. Acceptance criteria: a future OOMPAH-459-shaped repair workspace is removed by the normal aggressive cleanup pass without weakening ownership/ancestry guards; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 04:35
---
Live residue was manually pruned after confirming the clean repair head 95581aca5 is contained in origin/main. Removed managed worktree /home/shedwards/.oompah/worktrees/oompah/OOMPAH-459 and exact local/remote OOMPAH-459 refs. Task remains to automate this exact owned repair-workspace shape for recurrence.
---
author: oompah
created: 2026-07-30 04:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 04:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 04:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 37, Tool calls: 20
- Tokens: 122 in / 4.0K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 24s
- Log: OOMPAH-581__20260730T043610Z.jsonl
---
author: oompah
created: 2026-07-30 04:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 04:37
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-30 04:38
---
Agent completed successfully in 42s (46913 tokens)
---
author: oompah
created: 2026-07-30 04:38
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 45.9K in / 998 out [46.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 42s
- Log: OOMPAH-581__20260730T043750Z.jsonl
---
author: oompah
created: 2026-07-30 04:38
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-581`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 04:38
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 04:38
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-30 04:39
---
Understanding: This task requires extending the terminal maintenance cleanup in oompah/projects.py to recognize and prune epic repair workspaces. When an epic is terminal (merged/archived) with work_branch=epic-<id>, any auxiliary repair worktree at <worktree_root>/<id> on branch <id> should be auto-cleaned if: (1) it is the managed registered path, (2) it has the exact same-identifier branch, (3) it is clean and ancestor-safe (merged into main). Guards: never touch dirty worktrees, unmerged heads, shared branches, or different-identifier branches. Plan: explore oompah/projects.py cleanup logic, understand existing worktree cleanup guards, then add the auxiliary repair workspace cleanup as a narrowly-scoped extension with tests covering the real bare-remote scenario.
---
author: oompah
created: 2026-07-30 04:44
---
Discovery: Found the key code. In projects.py, cleanup_terminal_issue() removes the epic-<id> worktree (epic_worktree_path_for) and branch. But it does NOT handle an auxiliary task-style repair workspace at <worktree_root>/<project>/<id> on branch <id> left by epic repair/planner runs. The fix: add _cleanup_epic_repair_workspace_locked() method to projects.py that, when called for terminal epics, finds and removes the exact managed task-style path/branch with guards: registered worktree, exact same-identifier branch, clean (git status --porcelain empty), ancestor-safe (git merge-base --is-ancestor). Tests will use a real bare-remote git repo with: (1) terminal epic having canonical epic work_branch + auxiliary <id> repair worktree/branch; (2) dirty worktree preserved; (3) unmerged head preserved; (4) shared branch (checked out elsewhere) preserved; (5) different-identifier branch preserved.
---
author: oompah
created: 2026-07-30 04:46
---
Implementation: Added _cleanup_epic_repair_workspace_locked() to ProjectStore in oompah/projects.py (line 2624). This method is called only for terminal epic records from cleanup_terminal_issue() when is_epic=True. It enforces four sequential guards before removing: (1) repair path is exact managed registered worktree via worktree_path_for(); (2) exact same-identifier branch <id> (not epic-<id>) is checked out via git symbolic-ref; (3) worktree is clean via git status --porcelain; (4) branch head is ancestor of origin/<default_branch> via git merge-base --is-ancestor. All four guards must pass or the method returns False and leaves everything intact. Added 7 tests in TestEpicRepairWorkspaceCleanup: happy path (real bare-remote with both epic worktree and repair worktree), dirty preserved, unmerged preserved, shared-branch preserved, different-identifier preserved, unregistered-directory skipped, non-epic call skips repair path.
---
author: oompah
created: 2026-07-30 04:47
---
Verification: 117 tests pass (test_projects.py: 94, test_storage_cleanup.py + test_workspace.py: 23). 7 new tests in TestEpicRepairWorkspaceCleanup all pass: happy path real bare-remote scenario, dirty preserved, unmerged preserved, shared branch preserved, different-identifier preserved, unregistered dir skipped, non-epic no-op. Existing 87 tests unchanged and green. Branch OOMPAH-581 pushed to origin at 741a7d88b.
---
author: oompah
created: 2026-07-30 04:47
---
Completion: Delivered _cleanup_epic_repair_workspace_locked() in oompah/projects.py. The method is invoked from cleanup_terminal_issue(is_epic=True) and removes the OOMPAH-459-shaped auxiliary repair workspace in a single maintenance pass with four strict guards (registered path, exact identifier branch, clean, merged). No existing guard is weakened. 7 focused tests validate the happy path plus all negative cases. make test will run the full gate.
---
author: oompah
created: 2026-07-30 04:47
---
Added _cleanup_epic_repair_workspace_locked() to ProjectStore in oompah/projects.py. For terminal epics, cleanup_terminal_issue(is_epic=True) now also removes the auxiliary task-style repair workspace at <worktree_root>/<project>/<id> on branch <id> left by epic repair/planner runs. Four strict guards (registered path, exact same-identifier branch, clean worktree, merged head) must all pass before removal. 7 new focused tests in TestEpicRepairWorkspaceCleanup cover the happy-path real bare-remote scenario plus dirty/unmerged/shared/different-identifier/unregistered preservation cases. All 94 test_projects.py tests pass.
---
author: oompah
created: 2026-07-30 04:47
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 60
- Tokens: 90 in / 2.3K out [2.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 6s
- Log: OOMPAH-581__20260730T043854Z.jsonl
---
<!-- COMMENTS:END -->
