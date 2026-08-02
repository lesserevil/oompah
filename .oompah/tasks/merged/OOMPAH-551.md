---
id: OOMPAH-551
type: feature
status: Merged
priority: 0
title: Persist coordination messages and derive peer suggestions
parent: OOMPAH-550
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:14.047092Z'
updated_at: '2026-08-02T18:33:45.191472Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-cf9d5d93cd6d
    project_id: proj-14849f1b
    task_id: OOMPAH-551
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c44fe329b6e407a67d9d8f897c1f75f870085b8e2fa7025a0aed19963074d645
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:33:41.640278+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Implement a versioned SQLite CoordinationStore under Oompah service state with message IDs, project/task/run identities, kind, text, changed paths, commit SHA, timestamps, and delivered/read state. Derive peer suggestions from direct dependency neighbors, inherited epic relationships, active siblings, and live changed-path overlap. Bound message size and retention and make all writes idempotent and restart-safe.

Tests must cover schema migration, concurrent writers, restart recovery, ordering, idempotency, retention, graph derivation, inherited relationships, overlap detection, and empty/terminal projects.

Acceptance criteria: coordination history is durable and queryable, peer results are deterministic and project-scoped, and focused tests plus make test pass.

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
created: 2026-08-02 18:33
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: the human-owned parallel coordination/integration implementation was delivered by merged PR #579 at 31f8938b8, with full-gate and live-deployment evidence recorded on the task family. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
