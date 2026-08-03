---
id: OOMPAH-727
type: task
status: Open
priority: null
title: Prune safe auxiliary worktrees left by direct epic maintenance tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:39:38.824262Z'
updated_at: '2026-08-03T16:03:14.190132Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e1c5de9a-1999-4382-9104-86aa9c17ea3d
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T16:03:04.167596+00:00'
  claim_expires_at: '2026-08-03T16:33:04.167596+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5257ddba-948a-413b-aeb6-7f8ffab96c33
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
<!-- COMMENTS:END -->
