---
id: OOMPAH-560
type: task
status: Merged
priority: 0
title: Expose, document, and pilot parallel epic integration
parent: OOMPAH-555
children: []
blocked_by:
- OOMPAH-559
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:29.405626Z'
updated_at: '2026-08-02T18:35:42.703349Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-b44242a1f70a
    project_id: proj-14849f1b
    task_id: OOMPAH-560
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fe2edcbd2bca3c63f27e4c94bb0c6da5f377d3606e297e1718305bf8e07be9ca
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:35:32.721454+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-560
    target_state: Merged
    evidence_fingerprint: fe2edcbd2bca3c63f27e4c94bb0c6da5f377d3606e297e1718305bf8e07be9ca
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-02T18:35:41.379196+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Add integration queue and peer activity to state/task/activity APIs and the dashboard. Document configuration, submission, dependency semantics, recovery, rollback, and operator verification. Add OOMPAH_PARALLEL_EPIC_CHILDREN_ENABLED in .env/.env.example with a drain-first activation check. Build end-to-end tests for two parallel siblings, out-of-order dependent submission, overlap communication, ordered integration, terminal audit, and a single epic PR. Pilot on one owned epic before enabling globally.

Acceptance criteria: operators can see why every Ready task is waiting, rollout and rollback are documented and safe, the full end-to-end scenario passes, make test passes, and live production verification confirms parallel child agents without shared-worktree races.

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
