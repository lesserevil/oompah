---
id: OOMPAH-557
type: feature
status: Merged
priority: 0
title: Implement durable topological epic integration queues
parent: OOMPAH-555
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-547
- OOMPAH-556
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:22.859407Z'
updated_at: '2026-08-02T18:34:45.813354Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-144313a1fedf
    project_id: proj-14849f1b
    task_id: OOMPAH-557
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9ef72b9c6ef242d4f5dd05d5d017a570069d95687832582e254d2bcae6cd083c
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:34:39.074960+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-557
    target_state: Merged
    evidence_fingerprint: 9ef72b9c6ef242d4f5dd05d5d017a570069d95687832582e254d2bcae6cd083c
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-02T18:34:44.737033+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Implement a restart-safe per-epic queue with leases and deterministic selection. Ready submissions whose finish dependencies are satisfied are ordered by dependency topology, priority, and submission time. Same-epic prerequisites require terminal status plus integrated ancestry; parent epic finish edges are inherited. Cross-epic work may run but all dependent-epic integration waits until upstream code is reachable from the target branch. Recover expired leases without duplicate integration.

Tests must cover out-of-order submission, independent tasks, inherited constraints, cross-epic holds, missing/changed dependency evidence, cycles, lease expiry, restart, concurrent ticks, and deterministic ordering.

Acceptance criteria: coding can run in parallel while integration and completion obey the graph exactly once, and focused tests plus make test pass.

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
