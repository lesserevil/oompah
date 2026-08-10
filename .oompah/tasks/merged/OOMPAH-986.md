---
id: OOMPAH-986
type: bug
status: Merged
priority: 1
title: Prevent terminal-audit churn from starving unrelated workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T04:41:10.778919Z'
updated_at: '2026-08-10T06:17:18.014986Z'
work_branch: OOMPAH-986
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/794
review_number: '794'
review_head: 4c1b1fb3f52345048207f11bc2389db54f9da96b
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
oompah.review_url: https://github.com/lesserevil/oompah/pull/794
oompah.review_number: '794'
oompah.target_branch: main
oompah.review_head: 4c1b1fb3f52345048207f11bc2389db54f9da96b
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7cf4a03baeb5
    project_id: proj-14849f1b
    task_id: OOMPAH-986
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c4548ef77b3df343589114481820057562c904b85a649d578e136ff20fa6461e
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner reconciliation of already-landed exact delivery. Branch
      head 4c1b1fb3f52345048207f11bc2389db54f9da96b passed the exact full Makefile
      gate with 19,295 passed, 7 skipped, and 2 expected failures; protected PR #794
      Python 3.11, 3.12, and 3.13 checks all succeeded; GitHub merged that exact head
      to main as e7fa85dbe952917f1a293ac641104d4db5d5a3f2. The merged build is now
      the healthy running service revision. This records verified delivery without
      launching a redundant post-merge corpus gate.'
    created_at: '2026-08-10T06:17:08.308819+00:00'
    selected_ref: 4c1b1fb3f52345048207f11bc2389db54f9da96b
    selected_sha: 4c1b1fb3f52345048207f11bc2389db54f9da96b
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-986
    target_state: Merged
    evidence_fingerprint: c4548ef77b3df343589114481820057562c904b85a649d578e136ff20fa6461e
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T06:17:16.376195+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-10 06:00
---
Branch quality gate passed for `4c1b1fb3f52345048207f11bc2389db54f9da96b` using `make test` in 171.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 06:00
---
Exact full branch gate passed at pushed head 4c1b1fb3f52345048207f11bc2389db54f9da96b: make test completed with 19,295 passed, 7 skipped, 2 xfailed, 49 warnings in 1,267.73s. Worktree is clean and origin/OOMPAH-986 resolves to the same exact head. Proceeding to protected PR CI.
---
author: oompah
created: 2026-08-10 06:17
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner reconciliation of already-landed exact delivery. Branch head 4c1b1fb3f52345048207f11bc2389db54f9da96b passed the exact full Makefile gate with 19,295 passed, 7 skipped, and 2 expected failures; protected PR #794 Python 3.11, 3.12, and 3.13 checks all succeeded; GitHub merged that exact head to main as e7fa85dbe952917f1a293ac641104d4db5d5a3f2. The merged build is now the healthy running service revision. This records verified delivery without launching a redundant post-merge corpus gate.
---
<!-- COMMENTS:END -->
