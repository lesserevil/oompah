---
id: OOMPAH-553
type: feature
status: Merged
priority: 0
title: Deliver coordination messages into live ACP sessions
parent: OOMPAH-550
children: []
blocked_by:
- OOMPAH-552
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:16.695169Z'
updated_at: '2026-08-02T18:34:05.129291Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f62b9576f2ac
    project_id: proj-14849f1b
    task_id: OOMPAH-553
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 912600fcabc9006cb1d03c568adeeb622d2092ef502180800c1ecc78d64af739
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:33:58.358336+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-553
    target_state: Merged
    evidence_fingerprint: 912600fcabc9006cb1d03c568adeeb622d2092ef502180800c1ecc78d64af739
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-02T18:34:03.604189+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Standardize backend message injection through AcpAgentSession. Preserve Claude queue delivery and add safe follow-up-turn draining for Codex subscription/API sessions; support OpenCode when its protocol permits and retain inbox fallback otherwise. A worker must drain queued messages before the session reports success. Delivery is FIFO, idempotent, bounded, observable, and never injected into an already failing or interrupted session.

Tests must cover messages arriving before, during, and after a turn; multiple messages; stop/error races; Codex and Claude follow-up turns; unsupported-backend fallback; and exactly-once delivery across restart boundaries.

Acceptance criteria: supported live agents receive peer messages before exit, unsupported backends lose no messages, and focused tests plus make test pass.

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
