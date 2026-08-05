---
id: OOMPAH-818
type: bug
status: Open
priority: 1
title: Fence stalled-task reopen against exact failing gate evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T01:23:30.171988Z'
updated_at: '2026-08-05T01:25:09.490191Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3d162b1f16d8f609ede69a559947440f139e2416a65c3e1c6e0ceb213d8558b0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T01:24:52.464266+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: No active peer in the authoritative corpus covers the stalled-task watchdog
    race against exact-head gate and integration evidence. Closest tasks OOMPAH-210,
    OOMPAH-216, and OOMPAH-217 address CI-access fallback, release-delivery reconciliation,
    and duplicate-screening handoff respectively; all are Archived and describe distinct
    root causes.

    Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none


    Evidence: No active peer in the authoritative corpus covers the stalled-task watchdog
    race against exact-head gate and integration evidence. Closest tasks OOMPAH-210,
    OOMPAH-216, and OOMPAH-217 address CI-access fallback, release-delivery reconciliation,
    and duplicate-screening handoff respectively; all are Archived and describe distinct
    root causes.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8e226ac5-fe4e-4515-9192-785136e5d367
oompah.task_costs:
  total_input_tokens: 48349
  total_output_tokens: 328
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 48349
      output_tokens: 328
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 48349
    output_tokens: 328
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:24:52.458610+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-818__20260805T012419Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: OOMPAH-818
    source_sha: e1b0f4846054bacac48e667295e2c00733d86d8c
    completed_at: '2026-08-05T01:24:52.489993+00:00'
---
## Summary

Triggered by: OOMPAH-814

Live regression on 2026-08-05: OOMPAH-814 exact accepted head 254b131c713bece56500a72408f796c46bfee8d0 completed its authoritative combined-tree gate with 2 failures and moved to Needs CI Fix. Seconds later stalled-task watchdog run #22 classified the task actionable with evidence 'current CI evidence is passing', moved Needs CI Fix to Open, and caused the integration row to be cancelled as tracker state Open. No repair worker was assigned, stranding the dependency chain. Implementation scope: make stalled-task CI classification consume the latest authoritative exact-head gate result and integration record atomically; a newer failing result must dominate older focused/passing evidence; require exact accepted head and branch identity before automatic reopen; fence classification/action with a compare-and-set generation so a gate completion or integration-row transition cannot race the watchdog; never cancel the only current exact-head integration record based on stale evidence; expose the evidence head/result/generation in the watchdog comment and structured event. Required tests: deterministic interleavings for gate failure immediately before and during watchdog classification/action, older pass plus newer fail, pass/fail on different heads, duplicate watchdog runs, and restart reconciliation; assert task remains Needs CI Fix with its failing exact-head row recoverable and dependents held. Acceptance: the OOMPAH-814 sequence cannot report passing or reopen after the latest exact-head gate failed, and no nonterminal task is left Open without a repair/validation owner because of watchdog action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 01:24
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-05 01:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 01:24
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 48.3K in / 328 out [48.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 52s
- Log: OOMPAH-818__20260805T012419Z.jsonl
---
<!-- COMMENTS:END -->
