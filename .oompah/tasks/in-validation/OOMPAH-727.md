---
id: OOMPAH-727
type: task
status: In Validation
priority: null
title: Prune safe auxiliary worktrees left by direct epic maintenance tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:39:38.824262Z'
updated_at: '2026-08-03T17:47:29.963165Z'
work_branch: OOMPAH-727
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/685
review_number: '685'
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
oompah.agent_run_id: 9b687c0c-b9b6-4297-8d8c-2295928cf311
oompah.task_costs:
  total_input_tokens: 71
  total_output_tokens: 16241
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1769
      cost_usd: 0.0
    sonnet:
      input_tokens: 28
      output_tokens: 8224
      cost_usd: 0.0
    unknown:
      input_tokens: 33
      output_tokens: 6248
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1769
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:04:19.450411+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 28
    output_tokens: 8224
    cost_usd: 0.0
    recorded_at: '2026-08-03T17:09:53.612920+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 6248
    cost_usd: 0.0
    recorded_at: '2026-08-03T17:47:27.260584+00:00'
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
  - run_id: OOMPAH-727__20260803T165450Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: refactor
    source_branch: OOMPAH-727
    source_sha: ab69c0eb8ae7721493ae99334bd5fc3e7564bec1
    completed_at: '2026-08-03T17:09:53.617554+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-727
  base_branch: main
  base_sha: eb4a649ba8d316327f2435e23e98604c8a3384d9
  head_sha: ab69c0eb8ae7721493ae99334bd5fc3e7564bec1
  submitted_at: '2026-08-03T17:07:49.533798+00:00'
  updated_at: '2026-08-03T17:10:02.797188+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/685
oompah.review_number: '685'
oompah.work_branch: OOMPAH-727
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-45e3fdc15aae: '2026-08-03T17:46:28.350280+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-727
    target_state: Done
    evidence_fingerprint: 946ea77753dfb857220dd0a476bd127a912163a95f293b1569e9e707901a8086
    audit_ids:
    - audit-89399af60cd4
    kind: result
    applied: true
    retired_at: '2026-08-03T17:46:28.350293+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-727
    audit_id: audit-89399af60cd4
    attempt_id: attempt-45e3fdc15aae
    target_state: Done
    evidence_fingerprint: 946ea77753dfb857220dd0a476bd127a912163a95f293b1569e9e707901a8086
    status: In Validation
    audit_ids:
    - audit-89399af60cd4
    applied: true
    created_at: '2026-08-03T17:46:28.350310+00:00'
    applied_at: '2026-08-03T17:46:33.610159+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-89399af60cd4
    project_id: proj-14849f1b
    task_id: OOMPAH-727
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 946ea77753dfb857220dd0a476bd127a912163a95f293b1569e9e707901a8086
    attempts:
    - version: 1
      attempt_id: attempt-45e3fdc15aae
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 946ea77753dfb857220dd0a476bd127a912163a95f293b1569e9e707901a8086
      created_at: '2026-08-03T17:37:08.434579+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T17:37:08.434579+00:00'
      branch_key: OOMPAH-727
      verdict: pass
      completed_at: '2026-08-03T17:46:28.350082+00:00'
      ended_at: '2026-08-03T17:46:28.350082+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T17:36:12.143444+00:00'
    updated_at: '2026-08-03T17:46:28.350082+00:00'
  - version: 1
    audit_id: audit-91aee5a5411d
    project_id: proj-14849f1b
    task_id: OOMPAH-727
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 946ea77753dfb857220dd0a476bd127a912163a95f293b1569e9e707901a8086
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T17:36:12.143444+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-45e3fdc15aae
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 946ea77753dfb857220dd0a476bd127a912163a95f293b1569e9e707901a8086
    created_at: '2026-08-03T17:37:08.434579+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T17:37:08.434579+00:00'
    branch_key: OOMPAH-727
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
author: oompah
created: 2026-08-03 16:19
---
Implementation: added a conservative ProjectStore direct-epic auxiliary cleanup path. It recognizes only a registered issue worktree on the exact scheduler-derived epic child branch, rejects shared checkouts, active operations, stable recovery refs, dirty state, ref identity changes, protected refs, and missing durable evidence, and compare-and-deletes only the exact local derived ref after worktree removal. Reachability accepts the default/authoritative epic remote or a same-epic private task remote; no remote ref is deleted. Added integration coverage for EXOCOMP-240 shape, staged/unstaged/untracked changes, recovery, paused rebase, unpublished unique heads, wrong suffix, shared checkout, cross-project/unregistered paths, authoritative/remote preservation, and repeated cleanup.
---
author: oompah
created: 2026-08-03 16:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 62
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 18s
- Log: OOMPAH-727__20260803T160606Z.jsonl
---
author: oompah
created: 2026-08-03 16:54
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 16:54
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-03 16:58
---
Continuation run #1: reviewing recovered state from prior agent run. Recovery checkpoint (22674acb) contains 341-line addition to oompah/projects.py (new _cleanup_direct_epic_auxiliary_workspace_locked + _registered_worktree_branch_paths helpers, integration into cleanup_terminal_issue) and 392-line addition to tests/test_projects.py (TestDirectEpicAuxiliaryCleanup with 8 test scenarios). Running focused tests now to verify correctness before creating a proper commit.
---
author: oompah
created: 2026-08-03 17:07
---
Verification: all focused tests pass on commit ab69c0eb8.
- TestDirectEpicAuxiliaryCleanup: 10/10 new tests pass (EXOCOMP-240 happy path, dirty/recovery/rebase/unpublished/mismatch/shared/cross-project preservation, idempotent second pass)
- TestEpicRepairWorkspaceCleanup (OOMPAH-581 compatibility): 7/7 pass
- TestRemoveWorktreeCleanup (terminal lifecycle): 17/17 pass
- TestGitWorktreeAddWithRecovery: 3/3 pass
- test_terminal_audit.py + test_terminal_audit_workspace_recovery.py: 31 pass
- test_repo_hygiene.py + test_orchestrator_repo_hygiene.py: 19 pass
- test_terminal_audit_scanner.py + test_terminal_audit_enforcement.py: 27 pass
- test_workspace.py + test_epic_rebase_state.py: 32 pass
- Full test_projects.py: 113/113 pass (including all new tests)
Branch pushed as origin/OOMPAH-727 at ab69c0eb8.
---
author: oompah
created: 2026-08-03 17:07
---
Added conservative auxiliary-workspace cleanup for direct epic maintenance tasks. New _cleanup_direct_epic_auxiliary_workspace_locked() in oompah/projects.py recognises the EXOCOMP-240/OOMPAH-721 shape (registered issue worktree on exact scheduler-derived epic child branch for a task whose recorded work_branch is the parent epic branch), enforces 8 safety guards (identity, registration, shared-checkout, active-operation, recovery-ref, dirty-state, ref-identity, remote-reachability) before removing only the auxiliary worktree and exact local derived ref. No remote ref deleted, no epic worktree touched, idempotent. 10 new integration tests in TestDirectEpicAuxiliaryCleanup covering all required scenarios; 113/113 tests pass in test_projects.py.
---
author: oompah
created: 2026-08-03 17:09
---
Agent completed successfully in 911s (8252 tokens)
---
author: oompah
created: 2026-08-03 17:09
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 51, Tool calls: 30
- Tokens: 28 in / 8.2K out [8.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 11s
- Log: OOMPAH-727__20260803T165450Z.jsonl
---
author: oompah
created: 2026-08-03 17:26
---
Branch quality gate passed for `ab69c0eb8ae7721493ae99334bd5fc3e7564bec1` using `make test` in 406.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 17:36
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 17:36
---
YOLO: merged PR #685.
---
author: oompah
created: 2026-08-03 17:37
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 17:37
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 17:46
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_commit: ab69c0eb8ae7721493ae99334bd5fc3e7564bec1
- commit_on_main: true
- implementation_file: oompah/projects.py
- cleanup_function_line: 4306
- helper_function_line: 3022
- integration_call_site: 4652
- test_class: tests/test_projects.py::TestDirectEpicAuxiliaryCleanup at line 2353
- test_count_new: 10
- test_projects_total: 113 passed
- terminal_audit_suites: 58 passed
- scanner_workspace_epic_suites: 103 passed
- focused_direct_epic_result: 10 passed in 1.31s
- focused_epic_repair_and_remove_worktree_result: 24 passed in 1.20s
- branch_gate_status: make test passed at ab69c0eb8 (independently verified per prior comment)
---
author: oompah
created: 2026-08-03 17:47
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 36, Tool calls: 27
- Tokens: 33 in / 6.2K out [6.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 8s
- Log: OOMPAH-727__20260803T173725Z.jsonl
---
<!-- COMMENTS:END -->
