---
id: OOMPAH-552
type: feature
status: Merged
priority: 0
title: Add worker-scoped coordination API, CLI, and tools
parent: OOMPAH-550
children: []
blocked_by:
- OOMPAH-551
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:15.200331Z'
updated_at: '2026-08-02T18:33:54.036817Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7ff391102871
    project_id: proj-14849f1b
    task_id: OOMPAH-552
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1e99166470f00144ab01ac2179a514fb1869b2aad98b74e9cf966d50a209859d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:33:50.832320+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Add authenticated endpoints and CLI commands for oompah coordinate peers, inbox, send, and checkpoint. Extend task handoff capabilities without exposing operator credentials. A worker may read its own inbox and message only server-suggested peers in the same managed project; system automation may publish validated notices. Surface messages in a separate Oompah coordination timeline rather than external tracker comments.

Tests must cover capability scope, expiry, cross-project and non-peer rejection, message validation, pagination, idempotency, CLI request construction, direct ACP tool routing, and OpenAPI/MCP exposure policy.

Acceptance criteria: every spawned worker can safely use the coordination surface, unauthorized routing is rejected without secret leakage, and focused tests plus make test pass.

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
