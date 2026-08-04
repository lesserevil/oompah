---
id: OOMPAH-777
type: feature
status: Done
priority: 1
title: Implement the pure total WorkDecision evaluator
parent: OOMPAH-765
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-786
labels: []
assignee: null
created_at: '2026-08-04T13:58:52.177276Z'
updated_at: '2026-08-04T17:02:13.845155Z'
work_branch: epic-OOMPAH-765--task-OOMPAH-777
target_branch: epic-OOMPAH-765
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-765
oompah.work_branch: epic-OOMPAH-765--task-OOMPAH-777
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-765--task-OOMPAH-777
  base_branch: epic-OOMPAH-765
  head_sha: 96b878f747949df1956de1d11e6f9bc6db32d279
  submitted_at: '2026-08-04T15:28:18.364467+00:00'
  updated_at: '2026-08-04T15:28:18.364467+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-40009111e70b
    project_id: proj-14849f1b
    task_id: OOMPAH-777
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7a0d62337d276c70afd99a556a6dfcb63eabd18937a196b52010b68fe42d296b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner exact-head integration: commit 96b878f747949df1956de1d11e6f9bc6db32d279
      was proven a descendant and fast-forwarded to epic-OOMPAH-765. Verification:
      195 workflow/delivery tests, ruff check/format, terminal mutation scan, secret
      scan, and diff check passed.'
    created_at: '2026-08-04T15:28:48.450992+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-777
    target_state: Done
    evidence_fingerprint: 7a0d62337d276c70afd99a556a6dfcb63eabd18937a196b52010b68fe42d296b
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T15:28:56.714051+00:00'
  oompah.terminal_audit_result_intents: []
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-899458e0afdc
    project_id: proj-14849f1b
    task_id: OOMPAH-777
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7a0d62337d276c70afd99a556a6dfcb63eabd18937a196b52010b68fe42d296b
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: Done
    created_at: '2026-08-04T17:02:08.533793+00:00'
  - version: 1
    audit_id: audit-e3387608a901
    project_id: proj-14849f1b
    task_id: OOMPAH-777
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7a0d62337d276c70afd99a556a6dfcb63eabd18937a196b52010b68fe42d296b
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: Done
    created_at: '2026-08-04T17:02:08.533793+00:00'
  attempt_history: []
---
## Summary

Implement evaluate_task(task, facts) -> WorkDecision using the workflow contract. Return disposition, reason code, owner type, prerequisites, evidence revision, next reassessment, permitted actions, action_required, and severity. Centralize dependency satisfaction, queue eligibility, target/landing resolution, retry/exhaustion, audit/review/implementation ownership, and epic readiness without I/O. Required table/property tests across every status and error fact, cross-epic dependencies, mixed queue heads, nested epics, retries, authority changes, and terminal states. Acceptance: evaluator is deterministic and total; no nonterminal input returns unknown without an explicit bounded recovery decision; consumers need no independent lifecycle heuristics.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 15:27
---
Implemented the pure, deterministic WorkDecision evaluator with stable reason codes, owner/disposition/action output, dependency semantics, lease/retry recovery, audit/integration/rollup/landing decisions, and structural alert-severity invariants. Added 40 focused tests plus incident-contract coverage. Verification: 195 focused/adjacent tests passed; ruff check and format-check passed; make terminal-audit-scan passed; staged secret scan and git diff --check passed.
---
author: oompah
created: 2026-08-04 15:28
---
Implemented and verified the pure WorkDecision evaluator; exact commit 96b878f747949df1956de1d11e6f9bc6db32d279 is ready to land on epic-OOMPAH-765.
---
author: oompah
created: 2026-08-04 15:28
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner exact-head integration: commit 96b878f747949df1956de1d11e6f9bc6db32d279 was proven a descendant and fast-forwarded to epic-OOMPAH-765. Verification: 195 workflow/delivery tests, ruff check/format, terminal mutation scan, secret scan, and diff check passed.
---
author: oompah
created: 2026-08-04 17:02
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
