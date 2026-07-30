---
id: OOMPAH-604
type: bug
status: Open
priority: 1
title: Allow owner overrides after terminal-audit evidence supersession
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T17:07:44.032640Z'
updated_at: '2026-07-30T17:14:39.852310Z'
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
oompah.agent_run_id: 81684a6e-a795-4548-ae01-0db3e31727f5
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-604
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-604
  base_branch: epic-OOMPAH-585
  base_sha: b252293d3fc950f79a342c74b51d3285f62ecf4c
  updated_at: '2026-07-30T17:11:54.364649+00:00'
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
<!-- COMMENTS:END -->
