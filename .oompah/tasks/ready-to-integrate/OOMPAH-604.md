---
id: OOMPAH-604
type: bug
status: Ready to Integrate
priority: 1
title: Allow owner overrides after terminal-audit evidence supersession
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T17:07:44.032640Z'
updated_at: '2026-07-30T17:18:49.655039Z'
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
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-604
  head_sha: 4cd5ddfae7384bbb7022d2562149468f0127a35e
  submitted_at: '2026-07-30T17:18:47.380173+00:00'
  updated_at: '2026-07-30T17:18:47.380173+00:00'
oompah.task_costs:
  total_input_tokens: 1839603
  total_output_tokens: 11956
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1839603
      output_tokens: 11956
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
<!-- COMMENTS:END -->
