---
id: OOMPAH-995
type: bug
status: Done
priority: 1
title: Move gate and workflow publication I/O outside project locks
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:35.641259Z'
updated_at: '2026-08-10T15:41:00.263394Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3b4cff748c2c
    project_id: proj-14849f1b
    task_id: OOMPAH-995
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ddd78a1176e804f72ad080fa150040718b71142804e515fd552a271ed0404008
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #798 merged as 2ab880be5; parent OOMPAH-992 is authoritatively terminal;
      contained 6e3d69765 and 277b833cc are aggregate-patch-identical to reviewed
      OOMPAH-995 branch through c57295dce. Recording shared-child completion as Done
      because no separate parent review record exists.'
    created_at: '2026-08-10T15:40:46.903841+00:00'
    selected_ref: origin/OOMPAH-995
    selected_sha: c57295dce36f0d0a529aef5b6c9f904ec343af6d
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-995
    target_state: Done
    evidence_fingerprint: ddd78a1176e804f72ad080fa150040718b71142804e515fd552a271ed0404008
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T15:40:58.515798+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Refactor quality-gate result and workflow publication so tracker reads, Git head/dependency checks, state-branch generation, and diff work occur outside project and delivery-authority locks. Use external preflight followed by a constant-time in-memory generation/CAS finalization that rejects superseded results while preserving terminal-first, result-first, head-change, and dependency-change behavior. Add barrier-based concurrency tests proving publication I/O is lock-free and unrelated task creation and health/control requests remain responsive.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 11:13
---
Implemented and pushed exact branch head 853fa473ec258e9171a12d550891789b20906242. Quality-gate publication now performs tracker/task/dependency/project/Git-head preflight without project or standalone-delivery locks, then finalizes under project + authority fences using project-scoped managed-tracker and workflow revisions. Durable workflow state-branch generation and scoped Git-diff proof now run before publication locks; final publication compares the in-memory tracker epoch, terminal/workflow revisions, and SQLite lane authority. Liveness observation authority is released around external preflight and its policy epoch is revalidated so health/control requests remain responsive. Managed native and external tracker writes now advance an atomic project-scoped publication epoch. Barrier regressions prove terminal revocation and external task creation proceed during stalled quality tracker reads, and project control + health reads proceed during stalled workflow Git-diff preflight. Focused verification: 349 quality/workflow tests passed; 125 provenance/project/terminal-metadata tests passed; 203 native tracker/state-branch/protocol tests passed; py_compile and git diff --check passed; make terminal-audit-scan passed; make check-secrets and commit hooks passed. No full suite run, per assignment.
---
author: oompah
created: 2026-08-10 11:13
---
Submission attempted after push but the server rejected it with: submission Git authority rejected: origin/epic-OOMPAH-992 is not published. Implementation is complete and branch OOMPAH-995 is clean/up to date at 853fa473ec258e9171a12d550891789b20906242; parent integration must publish/restore the expected epic-OOMPAH-992 authority before resubmitting.
---
author: oompah
created: 2026-08-10 11:18
---
Exact-head integration review blocker fixed and pushed at replacement head c57295dce36f0d0a529aef5b6c9f904ec343af6d. Managed generic tracker mutations now use short ProjectStore admission/finalization tokens: admission marks the project mutation active and advances the revision under the project lock, external tracker/SCM/network work runs with no project lock, and finalization retires the token and advances the revision under the lock even when the callback raises. Publication requires a quiescent exact revision, so any active, completed, failed, or overlapping mutation supersedes stale evidence. Added barrier coverage proving a blocked external create does not own the project lock and quality publication fails closed without reading the tracker; success, exception cleanup, overlapping-active mutation, and MagicMock/legacy compatibility paths are covered. Replacement focused verification: 350 quality/workflow tests passed; 73 provenance/project-lock tests passed; py_compile, git diff --check, terminal-audit scan, and commit secret hooks passed. Per integration instruction, task submission was not retried.
---
author: oompah
created: 2026-08-10 11:21
---
Replacement head c57295dce36f0d0a529aef5b6c9f904ec343af6d was independently reviewed and integrated into the shared OOMPAH-989 branch as commits 6e3d69765 and 277b833cc. Five focused cross-lock/publication barrier tests pass on the integrated head. The clean pushed child worktree has been pruned; the child remains In Progress pending the shared PR landing.
---
author: oompah
created: 2026-08-10 15:40
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: PR #798 merged as 2ab880be5; parent OOMPAH-992 is authoritatively terminal; contained 6e3d69765 and 277b833cc are aggregate-patch-identical to reviewed OOMPAH-995 branch through c57295dce. Recording shared-child completion as Done because no separate parent review record exists.
---
<!-- COMMENTS:END -->
