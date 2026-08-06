---
id: OOMPAH-868
type: bug
status: In Progress
priority: 1
title: Broker self-hosted CI validation and bound log amplification
parent: null
children: []
blocked_by:
- OOMPAH-846
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T23:27:55.534862Z'
updated_at: '2026-08-06T23:29:26.524037Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 42efe2295fd180771895fffa53944c16b080d2c47cc84d5a38c627cd07c9e428
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T23:29:06.810890+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-846 is the closest active task, but it covers\
    \ server-spawned worker command paths. OOMPAH-868 specifically addresses dedicated\
    \ GitHub Actions workflow lease integration and bounded CI logging, so the scopes\
    \ are complementary rather than duplicates.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ OOMPAH-846 is the closest active task, but it covers server-spawned worker command\
    \ paths. OOMPAH-868 specifically addresses dedicated GitHub Actions workflow lease\
    \ integration and bounded CI logging, so the scopes are complementary rather than\
    \ duplicates."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1196b283-a90e-4dfc-bd55-42c7100b0e35
oompah.task_costs:
  total_input_tokens: 46810
  total_output_tokens: 354
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46810
      output_tokens: 354
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46810
    output_tokens: 354
    cost_usd: 0.0
    recorded_at: '2026-08-06T23:29:06.809459+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-868__20260806T232846Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-868
    source_sha: f2b319c1182cd654112db622a0498171e508dead
    completed_at: '2026-08-06T23:29:06.990841+00:00'
---
## Summary

Triggered by: OOMPAH-768

Live reproduction on 2026-08-06: dedicated GitHub Actions run 31129704050 launched a full pytest process on the same host while the Oompah validation-resource database reported no owner or waiter. The run therefore bypasses the capacity-1 broker used by exact gates and managed workers. Its pytest -v command emits more than 16,000 per-test records; the process repeatedly entered jbd2_log_wait_commit and delayed both CI and local focused repair validation. Implementation scope: route every dedicated self-hosted CI full gate through the shared durable validation-resource lease before pytest starts, using a stable project/task/run authority identity and releasing on completion, cancellation, runner death, or timeout; prevent overlap with server exact gates and managed worker or auditor validation; replace per-test verbose console amplification with bounded console output while preserving complete failure diagnostics through a durable artifact or equivalent. Relevant files include .github/workflows/ci-dedicated.yml, validation lease integration scripts, and tests for runner lifecycle and command classification. Required tests: a simulated dedicated run waits while capacity=1 is owned, begins immediately after release, cancellation and owner death free capacity, concurrent runs cannot exceed capacity, and success/failure diagnostics remain available without verbose per-test streaming. Acceptance: process-table evidence proves at most one heavyweight validation tree on this host across dedicated CI and Oompah-managed paths, GitHub check conclusions remain correct, and a full clean run no longer causes sustained filesystem journal wait from console amplification.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 23:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 23:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 23:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.8K in / 354 out [47.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-868__20260806T232846Z.jsonl
---
<!-- COMMENTS:END -->
