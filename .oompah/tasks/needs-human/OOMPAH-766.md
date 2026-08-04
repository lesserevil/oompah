---
id: OOMPAH-766
type: epic
status: Needs Human
priority: 1
title: Implement durable leased workflow jobs and restart-safe sagas
parent: OOMPAH-763
children:
- OOMPAH-780
- OOMPAH-783
- OOMPAH-785
blocked_by: []
start_blocked_by: &id001
- OOMPAH-769
- OOMPAH-765
labels: []
assignee: null
created_at: '2026-08-04T13:55:56.148047Z'
updated_at: '2026-08-04T16:54:25.171429Z'
work_branch: epic-OOMPAH-766
target_branch: epic-OOMPAH-763
review_url: https://github.com/lesserevil/oompah/pull/713
review_number: '713'
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.review_url: https://github.com/lesserevil/oompah/pull/713
oompah.review_number: '713'
oompah.work_branch: epic-OOMPAH-766
oompah.target_branch: epic-OOMPAH-763
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    infrastructure-exhausted-audit-cad15f0c8539-3: '2026-08-04T16:54:15.433774+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-766
    target_state: Done
    evidence_fingerprint: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    audit_ids:
    - audit-cad15f0c8539
    kind: result
    applied: true
    retired_at: '2026-08-04T16:54:15.433786+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-766
    audit_id: audit-cad15f0c8539
    attempt_id: infrastructure-exhausted-audit-cad15f0c8539-3
    target_state: Done
    evidence_fingerprint: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    status: Needs Human
    audit_ids:
    - audit-cad15f0c8539
    applied: true
    created_at: '2026-08-04T16:54:15.433805+00:00'
    applied_at: '2026-08-04T16:54:22.525932+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cad15f0c8539
    project_id: proj-14849f1b
    task_id: OOMPAH-766
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    attempts:
    - version: 1
      attempt_id: attempt-7de0b06f8d3c
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
      created_at: '2026-08-04T16:51:20.064565+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:51:20.064565+00:00'
      branch_key: epic-OOMPAH-766
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T16:51:36.040638+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766)'
      next_retry_at: '2026-08-04T16:51:46.040608+00:00'
    - version: 1
      attempt_id: attempt-dd1943326e29
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
      created_at: '2026-08-04T16:52:23.001825+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T16:52:23.001825+00:00'
      branch_key: epic-OOMPAH-766
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T16:52:31.764329+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766)'
      next_retry_at: '2026-08-04T16:52:51.764310+00:00'
    - version: 1
      attempt_id: attempt-a9484b21d76f
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
      created_at: '2026-08-04T16:53:12.285147+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T16:53:12.285147+00:00'
      branch_key: epic-OOMPAH-766
      candidate_rotation_count: 2
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T16:53:27.735228+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766)'
      next_retry_at: '2026-08-04T16:54:07.735195+00:00'
    - version: 1
      attempt_id: infrastructure-exhausted-audit-cad15f0c8539-3
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
      verdict: needs_human
      failure_classification: infrastructure_error
      created_at: '2026-08-04T16:54:15.433648+00:00'
      completed_at: '2026-08-04T16:54:15.433648+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T16:50:31.930408+00:00'
    updated_at: '2026-08-04T16:54:15.433648+00:00'
  - version: 1
    audit_id: audit-48e0b754331c
    project_id: proj-14849f1b
    task_id: OOMPAH-766
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T16:50:31.930408+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7de0b06f8d3c
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    created_at: '2026-08-04T16:51:20.064565+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:51:20.064565+00:00'
    branch_key: epic-OOMPAH-766
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T16:51:36.040638+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766)'
    next_retry_at: '2026-08-04T16:51:46.040608+00:00'
  - version: 1
    attempt_id: attempt-dd1943326e29
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    created_at: '2026-08-04T16:52:23.001825+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T16:52:23.001825+00:00'
    branch_key: epic-OOMPAH-766
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T16:52:31.764329+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766)'
    next_retry_at: '2026-08-04T16:52:51.764310+00:00'
  - version: 1
    attempt_id: attempt-a9484b21d76f
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa4c63e4c5e02fff4a69bc9b90425b9374715cca81060b65e6f682799a55e88a
    created_at: '2026-08-04T16:53:12.285147+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T16:53:12.285147+00:00'
    branch_key: epic-OOMPAH-766
    candidate_rotation_count: 2
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T16:53:27.735228+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766)'
    next_retry_at: '2026-08-04T16:54:07.735195+00:00'
---
## Summary

Add a durable workflow-job ledger for execution ownership and recovery. Each job records stable ID/idempotency key, project/task/generation, action/phase, expected evidence/head, queued/leased/running/retry-wait/completed/superseded/action-required state, lease owner/expiry, attempt budget, next retry, timestamps, checkpoint, and categorized failure. Implement a resumable saga: persist intent, lease, revalidate preconditions, perform external effect, verify, checkpoint, request transition, complete. Every step must be idempotent and safe across process death because tracker/Git/forge/SQLite cannot share one transaction. Build a durable consumer, expired-lease recovery, bounded backoff, explicit exhaustion, and observability. Replace process-local lifecycle authority/future ownership only as each domain migrates. Required tests: concurrent claimers, exact-generation fencing, kill/restart injection after every persistence boundary, external effect succeeds before crash, tracker write succeeds before acknowledgment, lease expiry/reclaim, retry exhaustion, and cross-project isolation. Acceptance: no workflow action relies solely on a process-local map/future/timestamp; every unfinished job resumes, supersedes, or explicitly escalates after restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 16:47
---
Branch quality gate passed for `fd480f6bd8aeab2763b927bee841ffae52a345e1` using `make test` in 616.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-04 16:50
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 16:50
---
YOLO: merged PR #713.
---
author: oompah
created: 2026-08-04 16:51
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:51
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
---
author: oompah
created: 2026-08-04 16:51
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 16:52
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 16:52
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4s
---
author: oompah
created: 2026-08-04 16:52
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 16:53
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 16:53
---
Run #3 [attempt=3, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 10s
---
author: oompah
created: 2026-08-04 16:53
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-766 (tried: origin/epic-OOMPAH-766, origin/OOMPAH-766). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 16:54
---
Needs Human — Done audit requires operator input.

Independent auditor launches exhausted their retry budget because the audit workspace or transport failed before review began. Restore the audit infrastructure, then have a project owner rearm this terminal audit; do not reopen implementation work.
---
<!-- COMMENTS:END -->
