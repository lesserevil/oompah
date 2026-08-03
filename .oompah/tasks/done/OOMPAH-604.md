---
id: OOMPAH-604
type: bug
status: Done
priority: 1
title: Allow owner overrides after terminal-audit evidence supersession
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T17:07:44.032640Z'
updated_at: '2026-08-03T20:03:55.326343Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-604
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cf2935cf7b70e1c92538f418b7aaa9f96386384356b7e7edf3a943797cfea103
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T17:14:34.914773+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-585, OOMPAH-589, OOMPAH-577, OOMPAH-591, OOMPAH-484/485/487/489,
    and OOMPAH-460. They cover related audit dispatch, supersession, recovery, UI,
    documentation, or E2E behavior, but none duplicates the current owner-override
    fingerprint-selection bug.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: f5298e77-99d4-4298-8f50-76eb05df55f4
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-604
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-604
  base_branch: epic-OOMPAH-585
  base_sha: 4cd5ddfae7384bbb7022d2562149468f0127a35e
  updated_at: '2026-07-30T18:18:28.458615+00:00'
oompah.task_costs:
  total_input_tokens: 4048502
  total_output_tokens: 14121
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1840201
      output_tokens: 12108
      cost_usd: 0.0
    unknown:
      input_tokens: 2208301
      output_tokens: 2013
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 194
    output_tokens: 6400
    cost_usd: 0.0
    recorded_at: '2026-07-30T17:10:44.856110+00:00'
  - profile: default
    model: haiku
    input_tokens: 1839409
    output_tokens: 5556
    cost_usd: 0.0
    recorded_at: '2026-07-30T17:14:34.913452+00:00'
  - profile: default
    model: haiku
    input_tokens: 598
    output_tokens: 152
    cost_usd: 0.0
    recorded_at: '2026-07-30T17:19:10.743451+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 2208301
    output_tokens: 2013
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:27:05.631790+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-604__20260730T170845Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-604
    source_sha: b252293d3fc950f79a342c74b51d3285f62ecf4c
    completed_at: '2026-07-30T17:10:44.866445+00:00'
  - run_id: OOMPAH-604__20260730T171158Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-604
    source_sha: b252293d3fc950f79a342c74b51d3285f62ecf4c
    completed_at: '2026-07-30T17:14:34.922459+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    no-auditor-audit-c55cdf449369-1: '2026-07-30T18:13:33.817963+00:00'
    attempt-4abb7df16260: '2026-07-30T18:26:01.660530+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-55b734b4f72a
    project_id: proj-14849f1b
    task_id: OOMPAH-604
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34f58520a2b73227f592ca447a9e5b66be178fb90218ca3efdd0d057f3a2c9dd
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:26:54.871497+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-604
    target_state: Merged
    evidence_fingerprint: 34f58520a2b73227f592ca447a9e5b66be178fb90218ca3efdd0d057f3a2c9dd
    audit_ids:
    - audit-c55cdf449369
    - audit-8f5172bb44b8
    kind: override
    applied: true
    retired_at: '2026-08-02T18:27:00.242548+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c55cdf449369
    project_id: proj-14849f1b
    task_id: OOMPAH-604
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0f613657d486fa940f53b02ce2189b529f124964715d216756a0e0ddb4956f35
    attempts:
    - version: 1
      attempt_id: attempt-1c2185a9153a
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0f613657d486fa940f53b02ce2189b529f124964715d216756a0e0ddb4956f35
      created_at: '2026-07-30T17:23:59.222018+00:00'
      provider_id: prov-3c712bff
      model: nvidia/nvidia/nemotron-3-ultra
      started_at: '2026-07-30T17:23:59.222018+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-604
      ended_at: '2026-07-30T17:24:09.062897+00:00'
      failure_reason: 'unknown url type: ''/chat/completions'''
      next_retry_at: '2026-07-30T17:24:19.062867+00:00'
    - version: 1
      attempt_id: no-auditor-audit-c55cdf449369-1
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0f613657d486fa940f53b02ce2189b529f124964715d216756a0e0ddb4956f35
      verdict: fail
      failure_classification: no_auditor
      created_at: '2026-07-30T18:13:33.817886+00:00'
      completed_at: '2026-07-30T18:13:33.817886+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T17:23:37.458459+00:00'
    updated_at: '2026-07-30T18:13:33.817886+00:00'
  - version: 1
    audit_id: audit-8f5172bb44b8
    project_id: proj-14849f1b
    task_id: OOMPAH-604
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: faf6a681bc9c0fa7e1674b644c0b7db1e10324e0b7abe3468e1945ca485e75bd
    attempts:
    - version: 1
      attempt_id: attempt-4abb7df16260
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: faf6a681bc9c0fa7e1674b644c0b7db1e10324e0b7abe3468e1945ca485e75bd
      created_at: '2026-07-30T18:18:18.535304+00:00'
      provider_id: prov-3c712bff
      model: nvidia/nvidia/nemotron-3-ultra
      started_at: '2026-07-30T18:18:18.535304+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-604
      verdict: pass
      completed_at: '2026-07-30T18:26:01.660419+00:00'
      ended_at: '2026-07-30T18:26:01.660419+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: api
    previous_state: Needs Human
    created_at: '2026-07-30T18:16:28.150022+00:00'
    updated_at: '2026-07-30T18:26:01.660419+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1c2185a9153a
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0f613657d486fa940f53b02ce2189b529f124964715d216756a0e0ddb4956f35
    created_at: '2026-07-30T17:23:59.222018+00:00'
    provider_id: prov-3c712bff
    model: nvidia/nvidia/nemotron-3-ultra
    started_at: '2026-07-30T17:23:59.222018+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-604
    ended_at: '2026-07-30T17:24:09.062897+00:00'
    failure_reason: 'unknown url type: ''/chat/completions'''
    next_retry_at: '2026-07-30T17:24:19.062867+00:00'
  - version: 1
    attempt_id: attempt-4abb7df16260
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: faf6a681bc9c0fa7e1674b644c0b7db1e10324e0b7abe3468e1945ca485e75bd
    created_at: '2026-07-30T18:18:18.535304+00:00'
    provider_id: prov-3c712bff
    model: nvidia/nvidia/nemotron-3-ultra
    started_at: '2026-07-30T18:18:18.535304+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-604
---
## Summary

Implementation scope

Repair TerminalTransitionCoordinator._override_transition_locked so an authorized owner override evaluates the current active audit request for the requested target instead of rejecting whenever any superseded historical pending-chain record has a different EvidenceFingerprint. Preserve authorization, quarantine handling, atomic metadata persistence, redaction, and fail-closed behavior for a genuinely stale current request. Relevant files: oompah/terminal_transition_coordinator.py, API/CLI terminal status routing, and terminal override tests. Reproduce using OOMPAH-589, which has multiple Done audit records after reintegration and currently returns HTTP 409 for every valid owner override. Do not hand-edit task metadata as the workaround.

Tests

Add regressions with multiple same-target audit records carrying different fingerprints: a current matching record plus superseded older records must allow the override; a mismatch against the active/current record must still reject; authorization, comment ordering, metadata quarantine, secret redaction, and concurrent update behavior must remain covered. Run focused terminal override/coordinator/interface/CLI tests and make test.

Acceptance criteria

A project owner can apply an auditable override to the current OOMPAH-589-style terminal request even when historical records use older fingerprints. Truly stale overrides remain rejected, the selected active-record rule is deterministic and documented in code, no terminal metadata is edited manually, and all override records/comments remain durable and redacted.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 17:08
---
Project-owner-approved follow-up to repair the terminal owner-override fingerprint deadlock discovered while bootstrapping OOMPAH-589.
---
author: oompah
created: 2026-07-30 17:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 17:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 17:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 68, Tool calls: 27
- Tokens: 194 in / 6.4K out [6.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 6s
- Log: OOMPAH-604__20260730T170845Z.jsonl
---
author: oompah
created: 2026-07-30 17:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 17:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 17:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 20
- Tokens: 1.8M in / 5.6K out [1.8M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 44s
- Log: OOMPAH-604__20260730T171158Z.jsonl
---
author: oompah
created: 2026-07-30 17:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 17:14
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 17:15
---
UNDERSTANDING: The issue is that TerminalTransitionCoordinator._override_transition_locked currently rejects owner overrides whenever ANY historical pending-chain record has a different EvidenceFingerprint, even if the CURRENT active record matches. The fix should evaluate only the current active audit record's fingerprint. This blocks OOMPAH-589 (which has multiple Done audit records after reintegration) from accepting valid overrides. I need to: (1) locate and understand the buggy code, (2) identify how to select the current/active record, (3) change the fingerprint check to use only that record, (4) add regression tests, and (5) verify all existing tests still pass.
---
author: oompah
created: 2026-07-30 17:16
---
DISCOVERY: Found the bug in _override_transition_locked (line 1255-1263). Currently checks ALL records in pending_chain for the requested target and rejects if ANY has a different fingerprint. The fix: only check the CURRENT/ACTIVE record (non-superseded one). When fingerprints change, old records are marked SUPERSEDED and new ones created, so we must check only the last non-superseded record for that target. Will now implement the fix and add regression tests.
---
author: oompah
created: 2026-07-30 17:18
---
IMPLEMENTATION: Fixed the fingerprint-mismatch check in _override_transition_locked. Changed from checking all records in pending_chain to only checking the current (non-SUPERSEDED) record for the requested target. When evidence fingerprints change, older records are marked SUPERSEDED and new ones created; the override must evaluate only the current active record. This allows valid overrides on tasks like OOMPAH-589 with multiple Done records.
---
author: oompah
created: 2026-07-30 17:18
---
VERIFICATION: All tests pass. Terminal override tests (27 tests): all pass. Terminal coordinator tests (103 tests): all pass. Terminal audit tests (37 tests): all pass. New regression tests validate: (1) override succeeds when current record matches despite superseded records with different fingerprints, (2) override rejected when current record fingerprint mismatches, (3) override allowed when no pending record exists, (4) correct handling of multiple targets in the chain. Authorization, metadata quarantine, atomic persistence, redaction, and concurrent behavior all covered.
---
author: oompah
created: 2026-07-30 17:18
---
Fixed TerminalTransitionCoordinator._override_transition_locked to check only the current active (non-superseded) audit record's fingerprint, allowing owner overrides after evidence fingerprint updates. Added 4 regression tests. All existing tests pass.
---
author: oompah
created: 2026-07-30 17:18
---
COMPLETION: Fixed the terminal-audit evidence supersession bug (OOMPAH-604). A project owner can now apply an auditable override to a terminal request even when historical superseded records use older fingerprints, provided the current active record matches. The fix preserves all safety guarantees: authorization is re-checked at the owner layer, metadata is atomically persisted before status changes, secrets are redacted, and stale overrides (where the current record doesn't match) are still rejected. Task is ready for integration.
---
author: oompah
created: 2026-07-30 17:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 36
- Tokens: 598 in / 152 out [750 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 17s
- Log: OOMPAH-604__20260730T171500Z.jsonl
---
author: oompah
created: 2026-07-30 17:23
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 17:24
---
Auditor dispatched (attempt #1, candidate: prov-3c712bff/nvidia/nvidia/nemotron-3-ultra)
---
author: oompah
created: 2026-07-30 17:24
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 17:24
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
- Log: OOMPAH-604__20260730T172407Z.jsonl
---
author: oompah
created: 2026-07-30 17:24
---
Auditor attempt ended: unknown url type: '/chat/completions'. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-07-30 18:13
---
Needs Human — Done audit requires operator input.

No independent auditor candidate is available for this audit (All eligible auditor candidates were already attempted for this audit.). Configure the `auditor` role with at least one healthy provider/model that is independent of the task contributors, then move the task back to Open to retry.
---
author: oompah
created: 2026-07-30 18:18
---
Auditor dispatched (attempt #1, candidate: prov-3c712bff/nvidia/nvidia/nemotron-3-ultra)
---
author: oompah
created: 2026-07-30 18:18
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 18:26
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- test_results: 13724 passed, 7 skipped
- fix_location: oompah/terminal_transition_coordinator.py:_override_transition_locked
- regression_tests: tests/test_terminal_override.py (4 new tests)
---
author: oompah
created: 2026-07-30 18:27
---
Run #1 [attempt=1, profile=auditor, role=auditor -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 8, Tool calls: 8
- Tokens: 2.2M in / 2.0K out [2.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 41s
- Log: OOMPAH-604__20260730T181834Z.jsonl
---
author: oompah
created: 2026-08-02 18:26
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
