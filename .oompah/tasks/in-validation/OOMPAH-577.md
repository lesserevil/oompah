---
id: OOMPAH-577
type: task
status: In Validation
priority: null
title: Allow a changed integrated head to retry a failed completed terminal audit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:07:59.102017Z'
updated_at: '2026-08-07T06:08:56.525620Z'
work_branch: OOMPAH-577
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/588
review_number: '588'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/588
oompah.review_number: '588'
oompah.work_branch: OOMPAH-577
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-98c92344aec1
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: 'Restore proven merged state from PR #588 merge commit 70fa1de48 and recorded
      green CI/live evidence.'
    created_at: '2026-07-31T06:06:55.508737+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c1eee8ef1fc2
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    attempts:
    - version: 1
      attempt_id: attempt-2d156054d52d
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
      created_at: '2026-07-31T06:06:20.213169+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T06:06:20.213169+00:00'
      branch_key: OOMPAH-577
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: In Review
    created_at: '2026-07-31T06:06:13.348111+00:00'
    updated_at: '2026-07-31T06:06:20.213169+00:00'
  - version: 1
    audit_id: audit-534d62772883
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    attempts: []
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: In Review
    created_at: '2026-07-31T06:06:13.348111+00:00'
  - version: 1
    audit_id: audit-ddd74e1c9e1e
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 80e2c5927e01fa8dd501f592e9e8062ec6229b01926107d735232bfc4bf86daf
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-07T06:08:51.515138+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-2d156054d52d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    created_at: '2026-07-31T06:06:20.213169+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T06:06:20.213169+00:00'
    branch_key: OOMPAH-577
oompah.task_costs:
  total_input_tokens: 22
  total_output_tokens: 549
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 22
      output_tokens: 549
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 22
    output_tokens: 549
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:07:17.755570+00:00'
---
## Summary

Triggered by: OOMPAH-483\n\nImplementation scope: update TerminalTransitionCoordinator request handling so a completed audit record only rejects an identical stale request. When the same target is requested with a different evidence fingerprint after a failed audit and new pushed/integrated work, preserve the old record as Superseded and enqueue a fresh Pending record. Do not allow duplicate same-fingerprint requests and do not weaken successful terminal-state idempotency. Ensure the integration completion sweep can move a Ready-to-Integrate task back to In Validation after its earlier audit failed and the integrated SHA changed. Relevant files: oompah/terminal_transition_coordinator.py, tests/test_terminal_transition_coordinator.py, and integration transition tests in tests/test_orchestrator_handlers.py. Tests: same-fingerprint completed rejection, changed-fingerprint completed supersession, preserved history/audit IDs, fresh pending record, and repeated sweep coalescing. Acceptance criteria: OOMPAH-483 at integrated SHA 11ea824f7 can enter a new independent Done audit instead of logging 'already completed'; identical completed evidence stays idempotently rejected; focused and full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 03:33
---
Implemented changed-completed-evidence retry at 7fc9aa8ae and merged PR #588 to main as 70fa1de48 after required Python 3.11/3.12/3.13 CI passed. Focused coordinator/integration tests: 115 passed. Complete Makefile gate: 13,617 passed, 7 skipped. Live verification: OOMPAH-483 superseded its earlier failed completed audit, entered a fresh audit at integrated SHA 11ea824f7, received an independent PASS after 209 focused auditor tests, and reached Done. Service restarted gracefully and is healthy.
---
author: oompah
created: 2026-07-31 06:06
---
Post-restart reconciliation: PR #588 merged this task to main as 70fa1de48 after all matrix checks and live verification. The current In Review display is stale; restoring Merged.
---
author: oompah
created: 2026-07-31 06:06
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 06:06
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 06:06
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 06:07
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: Restore proven merged state from PR #588 merge commit 70fa1de48 and recorded green CI/live evidence.
---
author: oompah
created: 2026-07-31 06:07
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 12, Tool calls: 10
- Tokens: 22 in / 549 out [571 total]
- Cost: $0.0000
- Exit: terminated, Duration: 56s
- Log: OOMPAH-577__20260731T060623Z.jsonl
---
<!-- COMMENTS:END -->
