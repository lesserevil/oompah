---
id: OOMPAH-601
type: bug
status: Open
priority: 1
title: Aggregate branch-ownership cleanup skips without warning floods
parent: OOMPAH-588
children: []
blocked_by:
- OOMPAH-600
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:16:00.331568Z'
updated_at: '2026-07-30T15:55:28.687192Z'
work_branch: epic-OOMPAH-588--task-OOMPAH-601
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6d55bd19aff045e8d8aaf70e895e49bee62e7e4102e9a264dc04f07b2f713310
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: inconclusive\n\
    \nMatches: none\n\nEvidence: The only nonterminal task records available locally\
    \ (OOMPAH-281, OOMPAH-282) are unrelated. Closest historical tasks OOMPAH-165\
    \ and OOMPAH-168 concern shared-epic merge strategy, but are Archived. Server-backed\
    \ records for OOMPAH-600\u2013603 could not be read because the oompah server\
    \ is unavailable."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-07-30T15:56:24.029414+00:00'
oompah.agent_run_id: 6c40be69-e4ba-4f26-b0bc-02ef12244dd3
oompah.work_branch: epic-OOMPAH-588--task-OOMPAH-601
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-588--task-OOMPAH-601
  base_branch: epic-OOMPAH-588
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:52:56.452956+00:00'
oompah.task_costs:
  total_input_tokens: 605906
  total_output_tokens: 3306
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 605906
      output_tokens: 3306
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 605906
    output_tokens: 3306
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:55:24.028592+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-601__20260730T155258Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-588--task-OOMPAH-601
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:55:24.037091+00:00'
---
## Summary

Implementation scope

Correct and consolidate aggressive cleanup handling for terminal child tasks that legitimately share an epic-owned branch. Resolve ownership through canonical task/epic aliases before deciding, preserve ambiguous/shared branches, and emit one structured summary per run with categorized counts instead of one warning per child every tick. Keep actionable corruption/unsafe-path cases as warnings or alerts. Measure and avoid the observed multi-second reconciliation slowdown. Relevant files include oompah/projects.py cleanup/ownership helpers, orchestrator maintenance status, and logs/state APIs.

Tests

Cover shared epic branches, task-style repair branches, aliases, missing project_id, cross-project same identifiers, dirty/unmerged branches, large batches, warning aggregation, and latency-safe bounded scans. Run focused cleanup tests and make test.

Acceptance criteria

Normal shared-branch ownership produces no warning flood, cleanup remains safe, categorized skip evidence is visible, and the maintenance tick stays within its configured healthy budget for representative inventory.

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
created: 2026-07-30 15:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:55
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 605.9K in / 3.3K out [609.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 30s
- Log: OOMPAH-601__20260730T155258Z.jsonl
---
<!-- COMMENTS:END -->
