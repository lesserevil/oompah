---
id: OOMPAH-477
type: feature
status: In Progress
priority: 1
title: Replace the post-worker completion verifier with Done audit staging
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:25.383734Z'
updated_at: '2026-07-29T18:05:46.258472Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c05645ee2c2ac1f81cb7a09756e16a3ff56e6291b5d1474b0c161bbe06ba4871
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:30:44.798730+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active OOMPAH-475, 476, 478, 479, 480, 481, and 488\
    \ cover auditor dispatch, API/rollup/merge/release/archive routing, and lifecycle\
    \ testing\u2014not worker-exit Done staging. Terminal OOMPAH-468 and OOMPAH-492\
    \ are historical and distinct."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a4cf5471-8a4e-496b-b703-00f107494405
oompah.work_branch: epic-OOMPAH-459
oompah.task_costs:
  total_input_tokens: 1308655
  total_output_tokens: 5074
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1308655
      output_tokens: 5074
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1308655
    output_tokens: 5074
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:30:44.798106+00:00'
---
## Summary

Implementation scope

In the normal worker-exit path, preserve the existing close gate and unpushed gate as deterministic prechecks. When the agent requests a terminal state, capture contributor provenance and call the terminal coordinator instead of _run_completion_verifier or directly honoring close. Remove retry ceilings that eventually fail open. Reuse useful deterministic acceptance-reference extraction only as Done evidence. Ensure review creation happens at the same lifecycle point after a passed Done audit, not immediately after staging. Deprecate the old verifier call path without deleting reusable helpers in this task.

Tests

Update worker-exit, close-gate, unpushed-gate, dispatch-close-race, GitHub lifecycle, retry, and review-handoff tests. Add a full normal exit asserting In Validation first, independent audit pass to Done, then review creation. Test failed audit redispatch and no fail-open after repeated rejects. Run focused tests and make test.

Acceptance criteria

A worker cannot self-certify Done; all existing deterministic landing safeguards remain; review handoff and retry behavior occur only after the independent Done result.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 17
- Tokens: 1.3M in / 5.1K out [1.3M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 2s
- Log: OOMPAH-477__20260729T012849Z.jsonl
---
author: oompah
created: 2026-07-29 18:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:05
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
