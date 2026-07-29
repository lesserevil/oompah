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
updated_at: '2026-07-29T01:35:25.541501Z'
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
  evidence: ''
  claim_id: d2bdb2cd-a337-4884-a38a-7136715b8162
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:35:20.920388+00:00'
  claim_expires_at: '2026-07-29T02:05:20.920388+00:00'
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 281b5440-05d8-4d8d-abc8-a793de37295e
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
author: oompah
created: 2026-07-29 01:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:35
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
