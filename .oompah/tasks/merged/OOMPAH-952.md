---
id: OOMPAH-952
type: bug
status: Merged
priority: 1
title: Retire obsolete landed reviews and exact capacity reservations
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:48:29.754525Z'
updated_at: '2026-08-09T16:33:23.394074Z'
work_branch: OOMPAH-952
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-952
  head_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
  submitted_at: '2026-08-09T11:17:06.915915+00:00'
  updated_at: '2026-08-09T11:17:06.915915+00:00'
oompah.work_branch: OOMPAH-952
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-e95502a95243
    project_id: proj-14849f1b
    task_id: OOMPAH-952
    digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
  - version: 1
    audit_id: audit-347c8b8a5247
    project_id: proj-14849f1b
    task_id: OOMPAH-952
    digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6f2f9abe0440
    project_id: proj-14849f1b
    task_id: OOMPAH-952
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner override after accepted task head 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
      was proven contained in exact composed PR #765 head 64afe17c03741659c9b6d3ee8d47bb84f033e45e;
      PR #765 merged as 91bf64c57c26baf2dfaaf355c33bb53f28230061 with hosted Python
      3.11/3.12/3.13 checks successful.'
    created_at: '2026-08-09T16:33:16.929663+00:00'
    selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e95502a95243
    project_id: proj-14849f1b
    task_id: OOMPAH-952
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
    attempts:
    - version: 1
      attempt_id: attempt-7322d1353a82
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
      created_at: '2026-08-09T14:18:45.044497+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:18:45.044497+00:00'
      branch_key: OOMPAH-952
      selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
      selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
      failure_classification: scheduler_pause
      ended_at: '2026-08-09T15:51:42.887992+00:00'
      failure_reason: graceful restart interrupted auditor before verdict
    - version: 1
      attempt_id: attempt-1e8587fac5f4
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
      created_at: '2026-08-09T15:58:36.211448+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T15:58:36.211448+00:00'
      branch_key: OOMPAH-952
      selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
      selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
      candidate_rotation_count: 1
      failure_classification: scheduler_pause
      ended_at: '2026-08-09T16:23:42.600390+00:00'
      failure_reason: operator pause interrupted auditor before verdict
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T13:31:33.721362+00:00'
    selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    updated_at: '2026-08-09T16:23:42.600390+00:00'
  - version: 1
    audit_id: audit-347c8b8a5247
    project_id: proj-14849f1b
    task_id: OOMPAH-952
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T13:31:33.721362+00:00'
    selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
  attempt_history:
  - version: 1
    attempt_id: attempt-7322d1353a82
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
    created_at: '2026-08-09T14:18:45.044497+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:18:45.044497+00:00'
    branch_key: OOMPAH-952
    selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    failure_classification: scheduler_pause
    ended_at: '2026-08-09T15:51:42.887992+00:00'
    failure_reason: graceful restart interrupted auditor before verdict
  - version: 1
    attempt_id: attempt-1e8587fac5f4
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e660776e62cdcdd6173a2f5b5cec83a4051fbc25199331a3c513c188b4d8703c
    created_at: '2026-08-09T15:58:36.211448+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T15:58:36.211448+00:00'
    branch_key: OOMPAH-952
    selected_ref: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    selected_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
    candidate_rotation_count: 1
    failure_classification: scheduler_pause
    ended_at: '2026-08-09T16:23:42.600390+00:00'
    failure_reason: operator pause interrupted auditor before verdict
oompah.task_costs:
  total_input_tokens: 396
  total_output_tokens: 96
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 396
      output_tokens: 96
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 62
    output_tokens: 11
    cost_usd: 0.0
    recorded_at: '2026-08-09T15:51:40.335386+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 334
    output_tokens: 85
    cost_usd: 0.0
    recorded_at: '2026-08-09T16:23:46.935296+00:00'
---
## Summary

Triggered by: OOMPAH-764

Triggered by OOMPAH-764 / GitHub PR #748 on 2026-08-09. A Done nested epic whose three accepted source commits were all patch-equivalent in its authoritative immediate target retained a conflicting open review and committed review-capacity reservation for more than a day. With max_in_flight_prs=1, that obsolete row blocked otherwise eligible OOMPAH-946 and OOMPAH-949. Existing OOMPAH-782/837 contracts require capacity release and restart convergence, but no open task covers this live regression.

Implementation scope: in the durable review/epic reconciliation path, bind an open review and its reservation to exact project, task, source branch, submitted head, target branch, task authority generation, and current landing fact. When authoritative exact ancestry or complete patch-equivalence proves that accepted work is already landed and the task is terminal/landing-eligible, retire the obsolete open review and release only its matching committed reservation. Preserve legitimate Done-but-unlanded reviews, wrong-target reviews, partial/ambiguous patch equivalence, advanced source heads, nonterminal revisions, forge uncertainty, and stale workflow generations. Make close/release idempotent and restart-safe, and prevent a later stale cache publication from re-adopting the retired review.

Relevant code: oompah/review_workflow.py, oompah/review_workflow_adapter.py, oompah/epic_workflow.py, oompah/epic_workflow_adapter.py, oompah/review_capacity.py, orchestrator live-review reconciliation/standalone or epic cleanup. Tests: reproduce OOMPAH-764 with a conflicted open review plus exact complete patch-equivalent landing and capacity=1; assert exact review close and reservation release unblock the next delivery. Add ancestry, restart/idempotence, stale-cache race, wrong target, partial/conflicting proof, advanced head, nonterminal and forge-failure fail-closed cases. Acceptance: an obsolete exact review cannot hold project capacity after authoritative landing is proven; valid in-flight reviews are never retired; the next eligible Ready task naturally acquires the released slot.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 11:16
---
Implemented durable epic auto-close retirement: revalidate exact landed source/target/head, authoritatively inspect open reviews, bind and retire only matching review capacity under issue/project locks, persist exact epic review reservation authority/head, and fail closed on source drift, wrong targets, conflicting capacity routes, or unavailable forge state. Verification: 503 related workflow/review/capacity tests passed; focused epic workflow suite 88 passed; terminal mutation scan and secret scan passed.
---
author: oompah
created: 2026-08-09 11:17
---
Implemented exact landed epic review retirement before auto-close, with durable authority/head capacity binding, restart-safe release, fail-closed route/head checks, and regression coverage. Commit 8e1ac57e2.
---
author: oompah
created: 2026-08-09 11:30
---
Implemented exact landed epic review retirement before auto-close, with durable authority/head capacity binding, restart-safe release, fail-closed route/head checks, and regression coverage. Commit 8e1ac57e2ec2e8503fd380e75c05639badcc5fba is pushed; 503 related tests and focused validation passed.
---
author: oompah
created: 2026-08-09 12:47
---
Worked around the deployed pre-OOMPAH-953 remote-head polling deadlock by creating exact-head PR #765 and arming squash auto-merge. GitHub hosted checks are the exact review-head gate.
---
author: oompah
created: 2026-08-09 13:00
---
All three PR #765 matrices reproduced the OOMPAH-954 production-stack contract failure. Composed the already-reviewed two-commit OOMPAH-954 fix into exact head d7cc48949; hosted checks are rerunning.
---
author: oompah
created: 2026-08-09 13:23
---
Composed the complete current-main OOMPAH-957 stabilization into PR #765 at exact head 64afe17c0. The two repaired effect/liveness contract tests plus all three known hosted timing regressions pass together; hosted matrix is rerunning this final composition.
---
author: oompah
created: 2026-08-09 13:31
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:18
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:18
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 15:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 7, Tool calls: 3
- Tokens: 62 in / 11 out [73 total]
- Cost: $0.0000
- Exit: scheduler_pause, Duration: 1h 32m 52s
- Log: OOMPAH-952__20260809T141858Z.jsonl
---
author: oompah
created: 2026-08-09 15:52
---
Auditor attempt ended: graceful restart interrupted auditor before verdict. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-09 15:58
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 15:58
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 16:23
---
Auditor transport/finalization ended before a verdict; the bounded audit retry will preserve candidate capacity.
---
author: oompah
created: 2026-08-09 16:23
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 16
- Tokens: 334 in / 85 out [419 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 8s
- Log: OOMPAH-952__20260809T155852Z.jsonl
---
<!-- COMMENTS:END -->
