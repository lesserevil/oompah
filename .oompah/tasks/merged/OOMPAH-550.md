---
id: OOMPAH-550
type: epic
status: Merged
priority: 0
title: Broker durable coordination between concurrent agents
parent: null
children:
- OOMPAH-551
- OOMPAH-552
- OOMPAH-553
- OOMPAH-554
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:13.053468Z'
updated_at: '2026-08-02T18:35:50.099990Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7bef3d3581bb
    project_id: proj-14849f1b
    task_id: OOMPAH-550
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: be164359a18ef0714d9c0fd4368cd3f19e04cd1e4e802a69dfc20d7401921208
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: the human-owned parallel coordination/integration
      implementation was delivered by merged PR #579 at 31f8938b8, with full-gate
      and live-deployment evidence recorded on the task family. OOMPAH-699 tracks
      automatic convergence.'
    created_at: '2026-08-02T18:35:45.195644+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Goal

Allow concurrently running agents to exchange durable, auditable coordination messages without relying on tracker comments or a specific model provider.

Implementation scope

Create a restart-safe coordination timeline and derived peer suggestion graph from dependencies, epic ancestry, active siblings, and changed-path overlap. Add worker-scoped API/CLI/tools for peers, inbox, send, and checkpoint. Deliver messages at safe live turn boundaries for supported ACP backends with durable fallback for every backend. Generate automatic peer, change, conflict-risk, submission, and integration notices. Add observability, bounded retention, authorization, and loop prevention.

Acceptance criteria

Agents can communicate while running, messages survive restarts, only authorized suggested peers can exchange messages, unavailable live injection falls back without loss, communication never becomes a completion deadlock, conflict-risk peers are notified automatically, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-08-02 18:35
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: the human-owned parallel coordination/integration implementation was delivered by merged PR #579 at 31f8938b8, with full-gate and live-deployment evidence recorded on the task family. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
