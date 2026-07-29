---
id: OOMPAH-478
type: feature
status: Open
priority: 1
title: Route epic rollup, child Done, and epic close transitions through audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:26.329329Z'
updated_at: '2026-07-29T01:33:41.628543Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ab86b60bea92b12dbe85f111788a91ca686b0760b5299075160d7f27c6439cc4
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate-screening worker exited with reason normal.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-07-29T01:34:39.044365+00:00'
oompah.agent_run_id: 131815d1-b006-4f0b-b2bb-fd7953537d60
oompah.work_branch: epic-OOMPAH-459
oompah.task_costs:
  total_input_tokens: 162
  total_output_tokens: 4648
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 162
      output_tokens: 4648
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 4648
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:33:39.043297+00:00'
---
## Summary

Implementation scope

Replace terminal writes in epic rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests. In Validation children count as nonterminal and block rollup landing. A parent cannot enter Done until every required child has a current passed Done audit. A parent Merged request must chain its own Done audit when missing and then run target landing audit. Preserve nested/shared epic branch and landing-evidence gates. Do not let rollup reconciliation overwrite In Validation or audit:repair-needed.

Tests

Cover standalone epic, shared children, stale In Review child to Done, nested epics, child In Validation blocking parent, missing child audit, parent Done/Merged audit chains, independently merged child, existing review-repair states, and idempotent repeated ticks. Run epic strategy/rollup tests and make test.

Acceptance criteria

No epic or child is terminalized by rollup alone; each terminal meaning has the correct current audit and existing branch containment safeguards still apply.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 49, Tool calls: 19
- Tokens: 162 in / 4.6K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-478__20260729T013057Z.jsonl
---
<!-- COMMENTS:END -->
