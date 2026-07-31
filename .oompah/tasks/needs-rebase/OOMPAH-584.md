---
id: OOMPAH-584
type: epic
status: Needs Rebase
priority: 0
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
- merge-conflict
- epic:rebasing
assignee: null
created_at: '2026-07-30T14:13:01.872040Z'
updated_at: '2026-07-31T05:34:00.348340Z'
work_branch: epic-OOMPAH-584
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/603
review_number: '603'
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
  total_input_tokens: 477716
  total_output_tokens: 4362
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 33
      output_tokens: 988
      cost_usd: 0.0
    opus:
      input_tokens: 477683
      output_tokens: 3374
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 988
    cost_usd: 0.0
    recorded_at: '2026-07-31T05:14:14.677987+00:00'
  - profile: deep
    model: opus
    input_tokens: 477683
    output_tokens: 3374
    cost_usd: 0.0
    recorded_at: '2026-07-31T05:16:23.357022+00:00'
oompah.agent_run_id: 75d2b45c-3d2c-4777-9bd9-578d0e0c0cb9
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-584__20260731T051445Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: epic_planner
    source_branch: OOMPAH-584
    source_sha: 24bd5d6c166af7f8c839e9d5c9e4f3f17d17508e
    completed_at: '2026-07-31T05:16:23.361221+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/603
oompah.review_number: '603'
oompah.work_branch: epic-OOMPAH-584
oompah.target_branch: main
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
author: oompah
created: 2026-07-31 05:16
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 9
- Tokens: 477.7K in / 3.4K out [481.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 45s
- Log: OOMPAH-584__20260731T051445Z.jsonl
---
author: oompah
created: 2026-07-31 05:16
---
Task handoff failed after the worker ran: the server-owned, task-scoped tracker capability could not update this task. The task is held in Needs Human and will not be redispatched automatically; verify the handoff service and reconcile the worker's branch before resuming it.
---
author: oompah
created: 2026-07-31 05:33
---
Branch quality gate passed for `cf2fd7cfc6f556f51a9f11c6a950f00e6ba2d220` using `make test` in 262.5s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 05:33
---
YOLO: Merge conflict detected on MR #603. Rebase `epic-OOMPAH-584` onto main and resolve conflicts.
---
<!-- COMMENTS:END -->
