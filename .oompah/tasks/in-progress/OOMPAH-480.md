---
id: OOMPAH-480
type: feature
status: In Progress
priority: 1
title: Route release-delivery and release-pick terminal updates through audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:28.235708Z'
updated_at: '2026-07-29T18:29:11.114382Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-480
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a8ace4f99c51df6d0fb98d310ca6955aba9e017c72f118fb7c241f837cf7cf3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:44:58.777050+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: No active release-delivery/release-pick task exists\
    \ in the checked-out native tracker; the only active records are OOMPAH-281 and\
    \ OOMPAH-282, both unrelated. Closest reviewed tasks\u2014OOMPAH-195 (ledger executor/poller),\
    \ OOMPAH-196 (task/epic ledger compatibility), and OOMPAH-214 (conflict dispatch)\u2014\
    are all Archived and do not gate canonical Done/Merged transitions through target-specific\
    \ audits."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 84a2164f-5f0f-4709-a974-3fe468782345
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-480
oompah.task_costs:
  total_input_tokens: 224708
  total_output_tokens: 1742
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 224708
      output_tokens: 1742
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 224708
    output_tokens: 1742
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:44:58.776601+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-459--task-OOMPAH-480
  base_branch: epic-OOMPAH-459
  base_sha: 65c8e4725fe931bf0fa9c3357d153ba003ad03c4
  updated_at: '2026-07-29T18:29:09.032645+00:00'
---
## Summary

Implementation scope

Find every task/epic Done or Merged update in release_pick_reconciler, release-delivery completion/polling, cherry-pick helpers, and release addendum reconciliation. Stage the appropriate Done/Merged audit with the release target branch, selected commit set, review identity, and target SHA. Preserve release ledger/addendum status semantics; this task gates canonical task/epic terminal state, not delivery-record state. Wrong release target or partial cherry-pick must fail landing evidence and route to the existing repair state.

Tests

Cover successful cherry-pick PR, partial selected commits, wrong release branch, failed CI, conflict, duplicate poll, deleted branch, already-landed commit, task and epic release items, and delivery records remaining independent. Run release-focused tests and make test.

Acceptance criteria

Release automation cannot mark canonical work Done/Merged without target-specific audit, and delivery bookkeeping continues to work unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:44
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 01:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:44
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 4
- Tokens: 224.7K in / 1.7K out [226.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 55s
- Log: OOMPAH-480__20260729T014409Z.jsonl
---
author: oompah
created: 2026-07-29 18:29
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 18:29
---
Focus: CI Failure Fixer
---
<!-- COMMENTS:END -->
