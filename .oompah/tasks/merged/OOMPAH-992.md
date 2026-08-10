---
id: OOMPAH-992
type: bug
status: Merged
priority: 1
title: Bound task creation when quality-gate reconciliation owns project mutation
parent: null
children:
- OOMPAH-993
- OOMPAH-994
- OOMPAH-995
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:32:43.695792Z'
updated_at: '2026-08-10T15:39:33.748115Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-b5d84536823a
    project_id: proj-14849f1b
    task_id: OOMPAH-992
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3abf08bb74d4f83f352d2c57c809737198d7052f31851035f33ada7611ae373c
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #798 merged as 2ab880be5 and contains all reviewed OOMPAH-992 child
      patches plus combined authority hardening e09ad2e26 and 2c26f79aa; this owner
      disposition establishes the parent landing authority required to terminalize
      its contained child tasks.'
    created_at: '2026-08-10T15:39:20.151549+00:00'
    selected_ref: origin/main
    selected_sha: 2ab880be5c25d7b5c70000845698d39d5d53d3c8
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-992
    target_state: Merged
    evidence_fingerprint: 3abf08bb74d4f83f352d2c57c809737198d7052f31851035f33ada7611ae373c
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T15:39:31.945936+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-991

While filing OOMPAH-991 immediately after OOMPAH-989's submitted branch quality gate failed, two authenticated oompah task create requests remained blocked for more than three minutes. The HTTP control plane and health endpoint stayed responsive, but three server request threads remained on the same futex-backed synchronization point; cancelling both clients did not cancel the accepted server work, and an identity-checked emergency restart was required. After restart, the same create completed in 5.35 seconds. Diagnose project task-mutation serialization across quality-gate result reconciliation, issue snapshot refresh, durable workflow effects, and client disconnect/cancellation. Add deterministic barriers that hold the gate-result/status path while one or more task creates arrive, prove bounded completion or retryable failure, ensure cancelled duplicate clients cannot create duplicate tasks later, and ensure no lock is held across tracker/SCM/network callbacks. Acceptance: task creation cannot wait indefinitely behind gate reconciliation; accepted work has idempotent identity and observable completion; restart recovery converges without duplicates; focused concurrency/restart tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 15:39
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: PR #798 merged as 2ab880be5 and contains all reviewed OOMPAH-992 child patches plus combined authority hardening e09ad2e26 and 2c26f79aa; this owner disposition establishes the parent landing authority required to terminalize its contained child tasks.
---
<!-- COMMENTS:END -->
