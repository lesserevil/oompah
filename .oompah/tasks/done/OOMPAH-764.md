---
id: OOMPAH-764
type: epic
status: Done
priority: 1
title: Define the authoritative workflow contract and liveness invariants
parent: OOMPAH-763
children:
- OOMPAH-772
- OOMPAH-773
- OOMPAH-774
- OOMPAH-799
- OOMPAH-800
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:55:51.305029Z'
updated_at: '2026-08-04T14:44:23.317695Z'
work_branch: epic-OOMPAH-764
target_branch: epic-OOMPAH-763
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f6b2d320f767
    project_id: proj-14849f1b
    task_id: OOMPAH-764
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c048d70c3966e70e9a1d4a96a2a9740b821ab38d23f760587ec42d5eedcbd950
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Project-owner nested-epic landing recovery. Exact work branch epic-OOMPAH-764
      at 73f5aeb26fc91f62a0bd9ac5ba544582b761f811 is contained by immediate parent
      target epic-OOMPAH-763 at the same revision. All canonical children are Done
      and 482 focused and adjacent tests passed.
    created_at: '2026-08-04T14:44:06.820415+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-764
    target_state: Done
    evidence_fingerprint: c048d70c3966e70e9a1d4a96a2a9740b821ab38d23f760587ec42d5eedcbd950
    audit_ids:
    - audit-a70c8beeb684
    - audit-017862c7aec9
    kind: override
    applied: true
    retired_at: '2026-08-04T14:44:20.219011+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a70c8beeb684
    project_id: proj-14849f1b
    task_id: OOMPAH-764
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
    attempts:
    - version: 1
      attempt_id: attempt-cbaa8c66e9b3
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
      created_at: '2026-08-04T14:41:52.684347+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T14:41:52.684347+00:00'
      branch_key: OOMPAH-764
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T14:42:05.339740+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-764 (tried: origin/OOMPAH-764)'
      next_retry_at: '2026-08-04T14:42:15.339705+00:00'
    - version: 1
      attempt_id: attempt-799768e2e86a
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
      created_at: '2026-08-04T14:42:47.116394+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T14:42:47.116394+00:00'
      branch_key: epic-OOMPAH-764
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-08-04T14:41:10.958074+00:00'
    updated_at: '2026-08-04T14:42:47.116394+00:00'
  - version: 1
    audit_id: audit-017862c7aec9
    project_id: proj-14849f1b
    task_id: OOMPAH-764
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c048d70c3966e70e9a1d4a96a2a9740b821ab38d23f760587ec42d5eedcbd950
    attempts: []
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Open
    created_at: '2026-08-04T14:43:55.858596+00:00'
    updated_at: '2026-08-04T14:44:20.218984+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-cbaa8c66e9b3
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
    created_at: '2026-08-04T14:41:52.684347+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T14:41:52.684347+00:00'
    branch_key: OOMPAH-764
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T14:42:05.339740+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-764 (tried: origin/OOMPAH-764)'
    next_retry_at: '2026-08-04T14:42:15.339705+00:00'
  - version: 1
    attempt_id: attempt-799768e2e86a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
    created_at: '2026-08-04T14:42:47.116394+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T14:42:47.116394+00:00'
    branch_key: epic-OOMPAH-764
    candidate_rotation_count: 1
oompah.target_branch: epic-OOMPAH-763
oompah.work_branch: epic-OOMPAH-764
---
## Summary

Establish the executable specification that all later workflow-engine work must implement. Scope: split user-visible business status from execution phase and durable disposition; define stable reason codes, permitted transition graph, ownership/lease/retry semantics, parent-child containment rules, dependency rules, landing evidence, safety properties, liveness properties, and measurable reassessment SLOs. Build a permanent incident corpus for OOMPAH-562, OOMPAH-731, OOMPAH-732, OOMPAH-739, OOMPAH-748, OOMPAH-749, and OOMPAH-751 using existing code/tests/log evidence. Relevant code: oompah/statuses.py, docs/task-epic-workflow.md, terminal_transition_coordinator.py, release_addendum_schema.py, orchestrator lifecycle helpers, and tests. Required tests: transition-table structural invariants, total status-to-disposition mapping, graph validation, and incident fixture validation. Acceptance: every canonical status has an unambiguous disposition/owner/reassessment contract; safety and eventual-progress invariants are machine-readable; nested landing facts do not depend cyclically on parent status; downstream epics can consume the contract without duplicating rules.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:41
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 14:42
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 14:42
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3s
---
author: oompah
created: 2026-08-04 14:42
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-764 (tried: origin/OOMPAH-764). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 14:42
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 14:43
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 14:44
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner nested-epic landing recovery. Exact work branch epic-OOMPAH-764 at 73f5aeb26fc91f62a0bd9ac5ba544582b761f811 is contained by immediate parent target epic-OOMPAH-763 at the same revision. All canonical children are Done and 482 focused and adjacent tests passed.
---
<!-- COMMENTS:END -->
