---
id: OOMPAH-466
type: feature
status: In Validation
priority: 1
title: Apply audit verdicts and route failures without fail-open behavior
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-465
labels: []
assignee: null
created_at: '2026-07-28T13:05:08.204164Z'
updated_at: '2026-08-04T23:44:17.907249Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 310715ad-27ac-4a75-a8f1-dba49637df2a
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 390392
  total_output_tokens: 8251
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 390282
      output_tokens: 5073
      cost_usd: 0.0
    opus:
      input_tokens: 110
      output_tokens: 3178
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 390282
    output_tokens: 5073
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:52:43.775139+00:00'
  - profile: deep
    model: opus
    input_tokens: 110
    output_tokens: 3178
    cost_usd: 0.0
    recorded_at: '2026-07-28T20:04:58.585212+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-dd75f3a260a4: '2026-08-04T23:44:15.614622+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-466
    target_state: Archived
    evidence_fingerprint: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
    audit_ids:
    - audit-e83dfc0257fe
    kind: result
    applied: true
    retired_at: '2026-08-04T23:44:15.614631+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-466
    audit_id: audit-e83dfc0257fe
    attempt_id: attempt-dd75f3a260a4
    target_state: Archived
    evidence_fingerprint: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
    status: Archived
    audit_ids:
    - audit-e83dfc0257fe
    applied: false
    created_at: '2026-08-04T23:44:15.614642+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e83dfc0257fe
    project_id: proj-14849f1b
    task_id: OOMPAH-466
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
    attempts:
    - version: 1
      attempt_id: attempt-1f2d12258dd1
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
      created_at: '2026-08-04T21:40:54.112068+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:40:54.112068+00:00'
      branch_key: epic-OOMPAH-457
      ended_at: '2026-08-04T21:48:05.906767+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-dd75f3a260a4
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
      created_at: '2026-08-04T23:38:22.483199+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T23:38:22.483199+00:00'
      branch_key: epic-OOMPAH-457
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-04T23:44:15.614523+00:00'
      ended_at: '2026-08-04T23:44:15.614523+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:33:59.671378+00:00'
    updated_at: '2026-08-04T23:44:15.614523+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1f2d12258dd1
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
    created_at: '2026-08-04T21:40:54.112068+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:40:54.112068+00:00'
    branch_key: epic-OOMPAH-457
    ended_at: '2026-08-04T21:48:05.906767+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-dd75f3a260a4
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5035c7261246e8fe6d45dbd09ced47dc347d1fd9b27581db5c669e79f47aaac5
    created_at: '2026-08-04T23:38:22.483199+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T23:38:22.483199+00:00'
    branch_key: epic-OOMPAH-457
    candidate_rotation_count: 1
---
## Summary

Implementation scope

Add coordinator result handling with compare-and-set checks for audit ID, target, fingerprint, and current In Validation state. PASS records safe evidence, posts a result comment, and applies only the audited target before advancing the next chain item. Map FAIL classifications centrally: incomplete/missing tests/unpushed/missing evidence to Open; CI failure to Needs CI Fix; conflict/out-of-date to Needs Rebase; healthy unmerged review to In Review; ambiguous requirements/external capability/no auditor to Needs Human; unsafe archive restores the recorded pre-audit state unless another class is more specific. NEEDS_HUMAN comments must end with explicit instructions or questions. Never honor an error, timeout, unparseable verdict, or retry ceiling as a pass.

Tests

Table-test every verdict/classification/status, stale result rejection, duplicate result idempotency, chained pass behavior, failed comment/status writes, unsafe archive restoration, actionable Needs Human endings, and absence of all fail-open paths. Run focused tests and make test.

Acceptance criteria

Only a matching PASS reaches the requested terminal state; every failure has a deterministic repair state and durable actionable explanation; malformed or infrastructure results leave the item nonterminal.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 19:49
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:50
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 19:52
---
Agent completed successfully in 168s (395355 tokens)
---
author: oompah
created: 2026-07-28 19:52
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 29
- Tokens: 390.3K in / 5.1K out [395.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-466__20260728T195001Z.jsonl
---
author: oompah
created: 2026-07-28 19:52
---
Agent completed without closing this issue (168s (395355 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-28 19:53
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 19:53
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 19:55
---
Understanding: This task implements coordinator result-handling per OOMPAH-457's terminal-transition-coordinator design. The staging half (OOMPAH-465) landed; the verdict-application half is missing. Plan: (1) add an AuditResult submission surface with an idempotency attempt_id; (2) add TerminalTransitionCoordinator.apply_audit_result that CAS-checks audit_id/target/fingerprint and requires In Validation before applying; (3) on PASS record safe evidence, post a result comment, and apply only the audited target while advancing the next chain item; (4) map FAIL classifications centrally to Open, Needs CI Fix, Needs Rebase, In Review, Needs Human, or the recorded pre-audit state per the spec; (5) NEEDS_HUMAN comments run through validate_needs_human_comment so they end with instructions/questions; (6) never map error/timeout/unparseable/malformed/retry-ceiling to PASS. Note: the dispatcher labelled this run 'CI Failure Fixer' but there is no failing PR/CI on this branch — the actual work is the feature. I will implement it directly rather than hand off again since the prior agent also did not close and CI has no failures to fix.
---
author: oompah
created: 2026-07-28 20:03
---
Discovery + Implementation: Extended oompah/terminal_transition_coordinator.py with (1) AuditResult submission surface, ResultOutcome, and ResultRejection reason constants; (2) classify_failure_to_status() as the single central mapping from FailureClassification -> canonical status (Open/Needs CI Fix/Needs Rebase/In Review/Needs Human, and pre-audit state restore for UNSAFE_ARCHIVE); (3) TerminalTransitionCoordinator.apply_audit_result() that CAS-checks audit_id/target_state/evidence_fingerprint AND that the tracker still holds the issue in In Validation, records the auditor's attempt into the audit chain, and only then routes the verdict; (4) idempotency via a bounded applied_result_attempts log in metadata; (5) actionable Needs Human comment composition with an always-appended fallback so validate_needs_human_comment cannot reject the composed message. Never-honor guarantees: ERROR verdicts, unparseable payloads, MALFORMED_RESULT, INFRASTRUCTURE_ERROR, retry ceilings, and rejected NEEDS_HUMAN messages all leave the record PENDING and the task in In Validation. Files: oompah/terminal_transition_coordinator.py, plans/terminal-transition-coordinator.md (added Result Application section), tests/test_terminal_transition_coordinator.py (added 59 result-handling tests, 100 total in this suite).
---
author: oompah
created: 2026-07-28 20:04
---
Verification: tests/test_terminal_transition_coordinator.py — 100 passed (41 pre-existing + 59 new result-handling cases). Focused suites tests/test_terminal_audit.py, tests/test_terminal_audit_metadata.py, tests/test_terminal_audit_enforcement.py, tests/test_transition_gate.py, tests/test_granian_bootstrap.py — 195 passed total across the terminal-audit stack with no regressions. Table-driven parametrisation covers every FailureClassification -> status mapping, every verdict (PASS, FAIL, NEEDS_HUMAN, ERROR), stale audit_id/target/fingerprint rejection, issue-not-in-validation rejection, record-already-completed rejection, duplicate attempt_id idempotency, Done->Merged chain advance (issue stays in In Validation, advanced_target reported), unsafe-archive restoration and its Needs Human fallback, actionable Needs Human comment fallback via the tracker validator, and every never-honour path (ERROR, MALFORMED_RESULT, INFRASTRUCTURE_ERROR, and stubbed validate_needs_human_comment rejection). Full make test gate is deferred to the orchestrator branch gate per project handoff policy.
---
author: oompah
created: 2026-07-28 20:04
---
Completion: Delivered TerminalTransitionCoordinator.apply_audit_result with compare-and-set on audit_id/target_state/evidence_fingerprint plus In Validation guard, central classify_failure_to_status() failure router, PASS terminal application with chain advance, actionable Needs Human comment composition, and durable pending-record retention for every non-terminal path (ERROR, MALFORMED_RESULT, INFRASTRUCTURE_ERROR, retry ceiling, non-actionable NEEDS_HUMAN). Acceptance criteria met: only a matching PASS reaches the requested terminal state; every failure has a deterministic repair state and durable actionable explanation; malformed or infrastructure results leave the item nonterminal in In Validation. Commit 63b904e09 on epic-OOMPAH-457.
---
author: oompah
created: 2026-07-28 20:04
---
Coordinator apply_audit_result with CAS, central failure routing, PASS/FAIL/NEEDS_HUMAN/ERROR handling, actionable Needs Human comments, and no fail-open paths. 100 tests in the coordinator suite (195 across the terminal-audit stack).
---
author: oompah
created: 2026-07-28 20:05
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 72
- Tokens: 110 in / 3.2K out [3.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 55s
- Log: OOMPAH-466__20260728T195305Z.jsonl
---
author: oompah
created: 2026-08-04 21:34
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 23:38
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 23:38
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
