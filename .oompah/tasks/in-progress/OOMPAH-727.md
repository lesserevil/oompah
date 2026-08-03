---
id: OOMPAH-727
type: task
status: In Progress
priority: null
title: Prune safe auxiliary worktrees left by direct epic maintenance tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:39:38.824262Z'
updated_at: '2026-08-03T16:10:11.371564Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9df53674c40ac7d9e4a9fec361c81045ed448d33abdbbb44363c8bbb33ec5ae8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T16:04:19.451867+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 175 tasks in the authoritative project corpus.\
    \ No active task addresses worktree pruning for auxiliary managed issue workspaces\
    \ created during epic maintenance dispatch. Tasks OOMPAH-581, OOMPAH-721, and\
    \ OOMPAH-726 are cited as compatibility references but do not appear in the corpus.\
    \ Terminal-state tasks are excluded per duplicate detection policy. OOMPAH-727\
    \ is the only active task focused on formalizing the worktree cleanup behavior\
    \ triggered by the EXOCOMP-240 failed dispatch scenario.\nI need to conduct a\
    \ duplicate investigation for OOMPAH-727 by comparing it against the authoritative\
    \ project task corpus.\n\n## Analysis of OOMPAH-727\n\n**Task Summary:** Prune\
    \ safe auxiliary worktrees left by direct epic maintenance tasks (triggered by\
    \ EXOCOMP-240 failed dispatch scenario)\n\n**Key Characteristics:**\n- Involves\
    \ worktree cleanup for auxiliary managed issue workspaces created during epic\
    \ maintenance/rebase tasks\n- References in-flight emergency cleanup already completed\n\
    - Requires formalizing cleanup logic with tests and guards\n- Mentions compatibility\
    \ with OOMPAH-581 (epic repair) and OOMPAH-726 (nested-target evidence)\n\n##\
    \ Review of Corpus\n\nI searched the provided authoritative task corpus for any\
    \ existing active (non-terminal) tasks that address:\n1. Worktree pruning or removal\n\
    2. Auxiliary worktree cleanup\n3. Epic maintenance workspace handling\n4. Failed\
    \ dispatch recovery\n\n**Findings:**\n- No active (Open/In Progress) tasks in\
    \ the corpus cover worktree pruning or cleanup\n- Tasks OOMPAH-581, OOMPAH-721,\
    \ and OOMPAH-726 are referenced in OOMPAH-727's description but are NOT included\
    \ in the authoritative corpus provided\n- All tasks related to workspace, tracker,\
    \ and epic management in the corpus are in terminal states (ARCHIVED)\n- The remaining\
    \ corpus tasks focus on tracker integration, intake validation, dashboard features,\
    \ and epic strategy standardization\u2014none address worktree lifecycle management\n\
    \n## Conclusion\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict:\
    \ no_duplicate\n\nMatches: none\n\nEvidence: Reviewed all 175 tasks in the authoritative\
    \ project corpus. No active task addresses worktree pruning for auxiliary managed\
    \ issue workspaces created during epic maintenance dispatch. Tasks OOMPAH-581,\
    \ OOMPAH-721, and OOMPAH-726 are cited as compatibility references but do not\
    \ appear in the corpus. Terminal-state tasks are excluded per duplicate detection\
    \ policy. OOMPAH-727 is the only active task focused on formalizing the worktree\
    \ cleanup beha"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5ec5420f-65f5-44e1-bebd-d3f2708d2a77
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1769
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1769
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1769
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:04:19.450411+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-727__20260803T160322Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-727
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T16:04:19.467265+00:00'
---
## Summary

Triggered by EXOCOMP-240 after the OOMPAH-721 duplicate-focus incident. EXOCOMP-240 is an auto-filed rebase task whose authoritative work branch is the shared container epic-EXOCOMP-130. The incorrect preflight/ordinary dispatch nevertheless created managed issue workspace /home/shedwards/.oompah/worktrees/exocomp/EXOCOMP-240 on derived branch epic-EXOCOMP-130--task-EXOCOMP-240. The clean workspace contains no EXOCOMP-240 implementation; its exact head b0d047ea97d00deb5c9b83054ddfb6de1491f0a9 is still published as the pre-rebase EXOCOMP-145 private branch. Terminal cleanup repeatedly refused it because the checked-out derived branch differs from the tasks recorded direct epic branch.

Implementation scope:
- Teach terminal/hygiene cleanup to recognize an auxiliary managed issue workspace created for a direct shared-epic maintenance/rebase task when its checked-out branch is the scheduler-derived private task branch rather than the recorded epic branch.
- Remove only the auxiliary worktree and exact local derived ref after proving the task is terminal/audited, the workspace is registered and clean, no Git operation or recovery state is active, and the head has durable pushed/merged/recovery reachability.
- Never delete the authoritative shared epic worktree or another tasks remote branch/ref used as reachability evidence.
- Preserve unique, dirty, unpublished, active-operation, mismatched-identity, and cross-project workspaces with actionable diagnostics.
- Keep cleanup idempotent and compatible with OOMPAH-581 epic repair workspace handling and OOMPAH-726 nested-target evidence.

Required tests:
- Reproduce EXOCOMP-240: direct epic work_branch plus an auxiliary issue path on epic-parent--task-id at a clean head also reachable from a trusted remote private branch; prune only the auxiliary worktree/local ref.
- Cover unique unpublished commit, staged/unstaged/untracked changes, recovery ref, paused rebase, wrong issue suffix, shared checkout, missing remote evidence, and repeated cleanup.
- Prove the authoritative epic worktree, remote epic branch, and any other tasks remote branch remain untouched.
- Run focused project cleanup, repo hygiene, maintenance/rebase, recovery, and terminal lifecycle suites plus make test.

Acceptance criteria:
- OOMPAH-721-style failed maintenance dispatches cannot leave permanent clean auxiliary worktrees solely because recorded and derived branch names differ.
- No unique or recoverable work is deleted.
- Cleanup emits one success record and no recurring warning after removal.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 15:40
---
In-flight cleanup completed with exact guards. EXOCOMP-240 auxiliary workspace was clean on exact derived branch epic-EXOCOMP-130--task-EXOCOMP-240 at b0d047ea97d00deb5c9b83054ddfb6de1491f0a9. That head remains published as origin/epic-EXOCOMP-130--task-EXOCOMP-145; authoritative epic workspace and origin/epic-EXOCOMP-130 both remain exact at 72ade5184d8c3ce5ac1ea112fdf3d514994cc7cc. Removed only the EXOCOMP-240 managed workspace and compare-and-deleted its exact local derived ref; no remote ref was removed.
---
author: oompah
created: 2026-08-03 16:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 16:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 6s
- Log: OOMPAH-727__20260803T160322Z.jsonl
---
author: oompah
created: 2026-08-03 16:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:05
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-03 16:07
---
Understanding: terminal/hygiene cleanup must identify clean auxiliary direct-epic maintenance workspaces on scheduler-derived task branches, prove terminal/audited durable reachability and inactive Git state, and prune only the auxiliary worktree plus exact local derived ref. I will trace existing epic repair and nested-target guards, add conservative branch-identity evidence, cover the requested safety matrix, then run focused tests and the project gate.
---
author: oompah
created: 2026-08-03 16:10
---
Discovery: cleanup is centered in oompah/projects.py. cleanup_terminal_issue passes a task's recorded work_branch into _assert_terminal_worktree_safe_locked, so a direct-epic maintenance task whose managed issue path is actually on epic-<parent>--task-<id> raises on branch mismatch. Existing _cleanup_epic_repair_workspace_locked safely handles OOMPAH-581's epic-path/<id>-branch residue, while epic_child_branch_name defines the exact private branch shape needed here. I’ll extend the non-epic terminal path with narrow parent-epic/derived-branch evidence and preserve all existing guards.
---
<!-- COMMENTS:END -->
