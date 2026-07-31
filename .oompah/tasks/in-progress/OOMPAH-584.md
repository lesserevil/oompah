---
id: OOMPAH-584
type: epic
status: In Progress
priority: 1
title: Return the oompah delivery control plane to green
parent: null
children:
- OOMPAH-585
- OOMPAH-586
- OOMPAH-587
- OOMPAH-588
- OOMPAH-630
- OOMPAH-631
- OOMPAH-632
- OOMPAH-633
blocked_by: []
start_blocked_by: []
labels:
- epic:stale
assignee: null
created_at: '2026-07-30T14:13:01.872040Z'
updated_at: '2026-07-31T05:14:41.792934Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6a47727db55b
    project_id: proj-14849f1b
    task_id: OOMPAH-584
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c4a0fd600972ec3a5d8ffdd99f0986dabfc9e170eb09eccbf6944bf2066d1d9f
    attempts:
    - version: 1
      attempt_id: attempt-4132c39c1619
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c4a0fd600972ec3a5d8ffdd99f0986dabfc9e170eb09eccbf6944bf2066d1d9f
      created_at: '2026-07-31T05:12:43.491182+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T05:12:43.491182+00:00'
      branch_key: OOMPAH-584
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-07-31T05:12:30.587245+00:00'
    updated_at: '2026-07-31T05:12:43.491182+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4132c39c1619
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c4a0fd600972ec3a5d8ffdd99f0986dabfc9e170eb09eccbf6944bf2066d1d9f
    created_at: '2026-07-31T05:12:43.491182+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T05:12:43.491182+00:00'
    branch_key: OOMPAH-584
oompah.task_costs:
  total_input_tokens: 33
  total_output_tokens: 988
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 33
      output_tokens: 988
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 988
    cost_usd: 0.0
    recorded_at: '2026-07-31T05:14:14.677987+00:00'
oompah.agent_run_id: 75d2b45c-3d2c-4777-9bd9-578d0e0c0cb9
---
## Summary

Goal

Restore the oompah project to an objectively green state across service health, terminal auditing, task access, integration delivery, and repository hygiene. This epic coordinates four focused child epics; implementation belongs in their actionable children rather than in this umbrella branch.

Scope and acceptance

- The service is healthy, unpaused, restartable through documented Makefile targets, and operator/task-worker authentication succeeds with least privilege.
- Terminal audits dispatch successfully, pending/stale transitions recover, and alerts accurately represent failures and clear after recovery.
- No task is stranded in Ready to Integrate or In Validation; the OOMPAH-460 chain drains in dependency order and main remains clean.
- Worktree/branch cleanup runs without errors or warning floods, preserves dirty/unmerged work, and removes safe terminal artifacts.
- The merged-label maintenance lane is project-scoped and error-free.
- Focused tests cover every fix and the configured complete Makefile gate passes on each review-ready head.

Live evidence at creation

The service had 54 pending terminal audits; OOMPAH-580 and OOMPAH-582 were stale In Validation after auditor launch failures; OOMPAH-484 and OOMPAH-487 had real rebase conflicts; downstream OOMPAH-485/488/489 were waiting; OOMPAH-574/575/576/581 were Ready to Integrate without open PRs; managed cleanup retained 20 worktrees, 117 local branches, and 67 remote branches; merged_labels rejected legacy OOMPAH-476 because project_id was absent.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:27
---
Recovery graph created and accepted: child epics OOMPAH-585 through OOMPAH-588; implementation children OOMPAH-589 through OOMPAH-603. Finish-order and true hard-start edges are recorded. The live scheduler claimed OOMPAH-589 and OOMPAH-590 first; direct operator implementation is deferred while service workers are making progress. If the current broken terminal-audit runtime prevents the audit-fix epic from delivering, bootstrap those exact reviewed heads to main through the normal PR/full-gate path, then resume scheduler ownership.
---
author: oompah
created: 2026-07-31 05:12
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 05:12
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 05:12
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 05:13
---
Operator race fence: outer validation started while required child epic OOMPAH-588 is Done but not Merged. Returning the outer epic to Open until OOMPAH-588 is rebased onto current parent 145b6b67e, passes exact-head verification, and merges. This prevents a stale audit from authorizing an incomplete outer review.
---
author: oompah
created: 2026-07-31 05:14
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 18
- Tokens: 33 in / 988 out [1.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 29s
- Log: OOMPAH-584__20260731T051250Z.jsonl
---
author: oompah
created: 2026-07-31 05:14
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 05:14
---
Focus: Epic Planner
---
<!-- COMMENTS:END -->
