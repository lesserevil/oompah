---
id: OOMPAH-479
type: feature
status: Open
priority: 1
title: Route webhook, YOLO, and merged-branch reconciliation through Merged audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-477
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:27.240594Z'
updated_at: '2026-07-29T01:35:13.965844Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e2aaf43115f65ce1c0ec00b596ffebbaaccb8cad3c31286f5487466d56a644d3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:35:11.353364+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: Active OOMPAH-281 and backlog OOMPAH-282 are\
    \ unrelated. Closest tasks OOMPAH-162, OOMPAH-165, OOMPAH-195, and OOMPAH-216\
    \ were fully reviewed but are Archived; OOMPAH-279 is Merged. None covers this\
    \ exact cross-source Merged-audit requirement."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4883e3c5-e408-42ae-b116-94c9484f55a4
oompah.work_branch: epic-OOMPAH-459
oompah.task_costs:
  total_input_tokens: 457305
  total_output_tokens: 3044
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 457305
      output_tokens: 3044
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 457305
    output_tokens: 3044
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:35:11.352925+00:00'
---
## Summary

Implementation scope

Inventory and replace Merged writes driven by GitHub/GitLab merge webhooks, YOLO direct/queued merge outcomes, merged-label maintenance, deferred Done review reconciliation, stale In Review reconciliation, and branch-containment sweeps. Each authoritative merge signal requests Merged with review/source/target evidence. If no current Done audit exists, the coordinator chains Done then Merged. Physical merges may already have occurred, but tracker state remains In Validation until both contracts pass. Preserve CI/rebase recovery and wrong-target checks.

Tests

Add provider-neutral webhook/YOLO/reconciliation cases for correct merge, direct Merged without Done, duplicate webhook/poll events, wrong target, failed/pending CI, deleted source branch, source advanced after merge, shared epic branch, and no matching task. Assert no direct terminal tracker call. Run focused tests and make test.

Acceptance criteria

Every forge- or Git-observed landing is independently validated before the task/epic says Merged, while duplicate observations remain idempotent.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 11
- Tokens: 457.3K in / 3.0K out [460.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-479__20260729T013353Z.jsonl
---
<!-- COMMENTS:END -->
