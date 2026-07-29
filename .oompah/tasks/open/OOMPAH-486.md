---
id: OOMPAH-486
type: feature
status: Open
priority: 1
title: Add terminal-audit metrics, maintenance health, and actionable alerts
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-483
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:25.195304Z'
updated_at: '2026-07-29T02:08:02.038395Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4e7f3870005234da335ab42730b57e4a6e6cd1432e2297b0d9226918d8bae59f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:08:00.115630+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active OOMPAH-475, OOMPAH-483, and sibling\
    \ tasks OOMPAH-484/485/487/488/489. They cover auditor dispatch, bypass detection,\
    \ APIs, UI, documentation, and lifecycle tests\u2014not metrics/maintenance health/alerting.\
    \ Historical OOMPAH-257 and OOMPAH-272 are terminal and were excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f17c37b1-df78-4eb3-9af1-1ac083d11e9d
oompah.work_branch: epic-OOMPAH-460
oompah.task_costs:
  total_input_tokens: 2610630
  total_output_tokens: 8447
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2610630
      output_tokens: 8447
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 2610630
    output_tokens: 8447
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:08:00.114490+00:00'
---
## Summary

Implementation scope

Track counters/gauges for queued, running, passed, failed, retried, stale-discarded, overridden, grandfathered, and no-independent-candidate audits, plus oldest queue age and last successful audit time. Surface them in the existing snapshot/maintenance status shapes. Add dashboard alerts only when no independent candidate exists, an audit exceeds the configured attempt/age threshold, queue recovery fails, or persistence is corrupt. Deduplicate by project/task/audit and clear alerts on recovery. Normal queued/running/passed audits must not alert.

Tests

Use deterministic clocks to cover metric increments, restart restoration, per-project isolation, oldest age, alert threshold/dedup/clear, no-candidate instructions, corrupt persistence, and absence of normal-operation alerts. Run observability tests and make test.

Acceptance criteria

Operators can distinguish healthy validation throughput from an actionable audit stall without receiving routine operating-procedure noise.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:08
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 29
- Tokens: 2.6M in / 8.4K out [2.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 42s
- Log: OOMPAH-486__20260729T020423Z.jsonl
---
<!-- COMMENTS:END -->
