---
id: OOMPAH-986
type: bug
status: Ready to Integrate
priority: 1
title: Prevent terminal-audit churn from starving unrelated workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T04:41:10.778919Z'
updated_at: '2026-08-10T05:12:56.602685Z'
work_branch: OOMPAH-986
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-986
  head_sha: 4c1b1fb3f52345048207f11bc2389db54f9da96b
  submitted_at: '2026-08-10T05:12:42.829013+00:00'
  updated_at: '2026-08-10T05:12:42.829013+00:00'
oompah.work_branch: OOMPAH-986
---
## Summary

Triggered by: OOMPAH-981

Live regression on 2026-08-10 after OOMPAH-979: OOMPAH-981 PR #793 reached green protected CI with mergeStateStatus=CLEAN, but project proj-14849f1b repeatedly logged durable workflow publication superseded at 04:26:08, 04:36:54, and 04:39:50 UTC because OOMPAH-983's long-running terminal-audit disposition changed during each corpus-wide collection. OOMPAH-979 bounded the project publication lock and correctly added project-wide revision fences, but legitimate activity in the terminal-audit lane can now invalidate every full-project cut indefinitely and starve unrelated review/integration decisions. Implement task- or lane-scoped publication authority (or an equivalent convergent partial/retry mechanism) so a terminal-audit disposition mutation supersedes decisions that depend on that task/audit while unrelated exact review/merge decisions can publish. Preserve fail-closed same-task terminal authority, OOMPAH-968 absent-to-retained provenance fencing, tracker/workflow owner authority fencing, atomic durable snapshot/job publication, restart idempotence, and cross-project isolation. Relevant code: oompah/workflow_runtime.py, workflow fact/publication authority composition, terminal-audit metadata/lane proof sources, and tests/test_workflow_runtime.py. Required tests: deterministically hold a 200-task publication while one In Validation audit advances through repeated disposition/heartbeat changes and one unrelated In Review PR becomes green; prove the audit-dependent projection supersedes or is refreshed while the unrelated review_merge effect publishes exactly once without waiting for audit completion; prove a same-task audit/provenance race cannot publish stale authority; prove a project pause/owner mutation still fences all affected dispatch; prove restart/replay and repeated churn converge without duplicate effects. Acceptance: continuous terminal-audit progress cannot starve an unrelated review/integration lane; exact authority remains atomic at the affected task/lane boundary; focused workflow/runtime, audit, review, persistence, and scaling tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 04:52
---
Direct-owner implementation is committed and pushed at exact head 54c318df1856316862ae8e398f98bbfa3611848a on branch OOMPAH-986 in /home/shedwards/src/oompah-986. The runtime now journals terminal-authority mutations by exact task. If a racing change is scoped only to active audit tasks and each existing durable audit lane still proves under the publication lock, those stale task projections are preserved as explicitly incomplete while unrelated review/integration decisions publish. Unscoped changes, tracker generation changes, provenance changes, failed same-task lane proofs, workflow owner changes, and pause changes retain fail-closed supersession. A deterministic 200-task regression performs two consecutive audit-revision races and proves the unrelated green review materializes exactly one review_merge job with no stale audit projection. Verification: 325 focused workflow runtime/controller/job-store/project-lock/terminal-metadata tests passed; make check-secrets and git diff --check passed. Branch is clean and up to date; task is intentionally not submitted pending independent review/full exact gate.
---
author: oompah
created: 2026-08-10 05:04
---
Supersedes prior head 54c318df1/c1e82283f after independent review exposed two production-shape blockers. Corrected exact head 4c1b1fb3f52345048207f11bc2389db54f9da96b is pushed. First, excluded active-audit identities are removed from runtime projections and omitted/masked incomplete in the canonical cut rather than retaining prior stale decisions. Second, paired NativeTracker state-branch generation changes are now proved through a bounded shared mutation journal plus exact Git task-file diff; only post-write oompah.terminal_audit mutations carry task scope. Pre-write uncached reads clear only local cache and no-op metadata writes no longer create phantom tracker authority. Runtime requires the tracker changed-task set to exactly match the ProjectStore terminal changed-task set and an active durable lane proof. Unrelated/unscoped tracker writes, provenance changes, failed lane proofs, and owner/pause changes remain fail-closed. Verification: 497 focused workflow runtime/controller/job-store/native tracker/state-branch/project-lock/terminal-metadata tests passed; make check-secrets and git diff --check passed. Branch/worktree are clean and up to date; not submitted pending final independent review/full exact gate.
---
author: oompah
created: 2026-08-10 05:12
---
Prevent terminal-audit churn from starving unrelated workflow publication; exact paired tracker/terminal authority proof, stale audit projection exclusion, and fail-closed unrelated mutation fences implemented and independently approved.
---
<!-- COMMENTS:END -->
