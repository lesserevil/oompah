---
id: OOMPAH-556
type: feature
status: Merged
priority: 0
title: Allocate isolated private branches for epic children
parent: OOMPAH-555
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-548
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:21.738821Z'
updated_at: '2026-08-02T18:34:24.515784Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-040a39b52354
    project_id: proj-14849f1b
    task_id: OOMPAH-556
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fbc7b0c4610a01420abd0dba2ecb7db5f7b13d8058e37582d16f398b6a938502
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:34:17.721851+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-556
    target_state: Merged
    evidence_fingerprint: fbc7b0c4610a01420abd0dba2ecb7db5f7b13d8058e37582d16f398b6a938502
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-02T18:34:23.368363+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Replace shared child workspace allocation under parallel mode with one worktree and branch per child, named without Git ref namespace collisions and based on the latest epic integration head. Persist private branch identity separately from the epic delivery branch. Keep epic repair agents on the epic branch. Add drain-time migration rules for existing Open, In Progress, Ready, and Done children and reject unsafe mixed shared/private dispatch.

Tests must cover concurrent workspace creation, branch naming, latest-main/epic bases, nested epics, tracker persistence, existing shared worktree migration, dirty worktrees, crash recovery, and no cross-worktree writes.

Acceptance criteria: concurrent children never share a worktree or checked-out branch, existing work is preserved, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:24
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:28
---
Implemented in PR #579 and merged to main at 31f8938b8f669a316a830690aaedcc1e0d3834bf. Full GitHub CI passed on Python 3.11, 3.12, and 3.13; the deployed server exposes the new coordination and submission surfaces.
---
author: oompah
created: 2026-08-02 18:34
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: the human-owned parallel coordination/integration implementation was delivered by merged PR #579 at 31f8938b8, with full-gate and live-deployment evidence recorded on the task family. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
