---
id: OOMPAH-602
type: bug
status: Open
priority: 1
title: Repair project scope propagation in merged-label maintenance
parent: OOMPAH-588
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:01.749200Z'
updated_at: '2026-07-30T16:09:08.810618Z'
work_branch: epic-OOMPAH-588--task-OOMPAH-602
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: aa914b1d0b87f4e5d642c7dcc794fb62222894a887640d54d1539e6646239a7b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 155f356d-81b4-4c45-9a63-9562ec337aa1
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T16:08:54.706577+00:00'
  claim_expires_at: '2026-07-30T16:38:54.706577+00:00'
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 9d8eeacf-bc88-4884-bd3a-7e88bbf12f3d
oompah.work_branch: epic-OOMPAH-588--task-OOMPAH-602
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-588--task-OOMPAH-602
  base_branch: epic-OOMPAH-588
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T16:09:06.859350+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-602__20260730T160131Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-588--task-OOMPAH-602
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T16:04:28.646848+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1030
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1030
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1030
    cost_usd: 0.0
    recorded_at: '2026-07-30T16:04:28.642099+00:00'
---
## Summary

Implementation scope

Fix merged-label maintenance so every managed issue operation uses the owning project/tracker scope, including legacy records such as OOMPAH-476 whose issue object lacks project_id. Resolve scope from the managed project iteration or canonical ownership index; never fall back to an unscoped legacy tracker. Persist/backfill safe scope metadata only through supported tracker APIs where necessary, and expose a clear conflict if ownership is ambiguous. Relevant files include merged-label reconciliation, project/tracker routing, issue normalization, and maintenance status.

Tests

Cover missing project_id with known project iteration, ambiguous identifiers across projects, explicit project mismatch, GitHub/native tracker routing, restart, idempotent labels, and no unscoped calls. Run focused maintenance tests and make test.

Acceptance criteria

The merged_labels maintenance lane completes with last_error null; OOMPAH-476 is handled in proj-14849f1b; no task in another project can be mutated through identifier collision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:19
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 16:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 16:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 16:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 67, Tool calls: 40
- Tokens: 10 in / 1.0K out [1.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 8s
- Log: OOMPAH-602__20260730T160131Z.jsonl
---
author: oompah
created: 2026-07-30 16:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 16:09
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
