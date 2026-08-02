---
id: OOMPAH-559
type: feature
status: Merged
priority: 0
title: Recover integration failures and clean private workspaces safely
parent: OOMPAH-555
children: []
blocked_by:
- OOMPAH-554
- OOMPAH-558
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:27.458733Z'
updated_at: '2026-08-02T18:35:24.739205Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8c7e2c752137
    project_id: proj-14849f1b
    task_id: OOMPAH-559
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6721ac667d8a9a544dc7f608f5ab5bc092b2af51911e55c3915f07ac3e561c27
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:35:19.307573+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Route rebase conflicts to Needs Rebase and combined-tree failures to Needs CI Fix with actionable task comments and the correct private branch. Re-dispatch repair agents with dependency and coordination context. Recover integrating tasks after service restart, invalidate stale integration evidence when upstream code changes, clean private worktrees after integration, and delete remote task branches only after epic landing. Extend stale cleanup without touching active or recoverable work.

Tests must cover each recovery state, exact final human instructions when escalation is unavoidable, watchdog interaction, stale evidence, branch cleanup timing, active-work protection, and interrupted service restarts.

Acceptance criteria: failures never lose commits or silently stall, repair work resumes on the correct branch, storage is reclaimed safely, and focused tests plus make test pass.

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
created: 2026-08-02 18:35
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: the human-owned parallel coordination/integration implementation was delivered by merged PR #579 at 31f8938b8, with full-gate and live-deployment evidence recorded on the task family. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
