---
id: OOMPAH-764
type: epic
status: In Validation
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
updated_at: '2026-08-04T14:41:53.811187Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a70c8beeb684
    project_id: proj-14849f1b
    task_id: OOMPAH-764
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
    attempts:
    - version: 1
      attempt_id: attempt-cbaa8c66e9b3
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
      created_at: '2026-08-04T14:41:52.684347+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T14:41:52.684347+00:00'
      branch_key: OOMPAH-764
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-08-04T14:41:10.958074+00:00'
    updated_at: '2026-08-04T14:41:52.684347+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-cbaa8c66e9b3
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a896dca59b0518a9920ae5a6fbd185fa921267513316f4cea0b18c3840f78d8b
    created_at: '2026-08-04T14:41:52.684347+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T14:41:52.684347+00:00'
    branch_key: OOMPAH-764
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
<!-- COMMENTS:END -->
