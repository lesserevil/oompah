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
updated_at: '2026-07-30T15:59:03.639422Z'
work_branch: epic-OOMPAH-588--task-OOMPAH-601
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6d55bd19aff045e8d8aaf70e895e49bee62e7e4102e9a264dc04f07b2f713310
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:58:58.952891+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation of the task repository, I need to\
    \ document my findings:\n\n## Search Results\n\nI conducted comprehensive searches\
    \ for duplicate tasks using multiple keyword patterns:\n\n1. **Direct cleanup/ownership\
    \ searches**: `branch-ownership|branch ownership|cleanup.*warning|warning.*cleanup`\
    \ \u2192 No matches\n2. **Terminal/child/epic searches**: `terminal.*child|child.*task|shared.*branch|epic-owned`\
    \ \u2192 No matches  \n3. **Broad cleanup/reconciliation**: `cleanup|reconciliation|warning\
    \ flood` \u2192 No matches\n4. **Code references**: `projects\\.py|cleanup|reconciliation`\
    \ \u2192 No matches\n5. **Task-related**: `epic|terminal|child` \u2192 No matches\n\
    6. **Sibling/parent references**: Searched for OOMPAH-588, 600, 602, 603 \u2192\
    \ No files found\n\nI also reviewed:\n- All files in `.oompah/tasks/open/` (1\
    \ task: OOMPAH-281, unrelated to GitHub Actions runner setup)\n- All archived\
    \ and merged tasks (270 files total) \u2014 none match this topic\n- Documentation\
    \ in `docs/` and `plans/` directories \u2014 no existing issue about this topic\n\
    \n## Analysis\n\nOOMPAH-601 addresses a specific bug:\n- **Problem**: Aggressive\
    \ branch cleanup for terminal child tasks produces warning floods when branches\
    \ are legitimately shared with epics\n- **Solution**: Resolve ownership through\
    \ canonical aliases, preserve shared branches, and emit one structured summary\
    \ per run instead of one warning per child per tick\n- **Scope**: oompah/projects.py\
    \ cleanup/ownership helpers, orchestrator maintenance, logs/state APIs\n\nThe\
    \ referenced related tasks (OOMPAH-588 epic-parent, OOMPAH-600/602/603 siblings)\
    \ do not have files in the tracked task system and are likely in server state\
    \ only.\n\n## Conclusion\n\nNo active task in the `.oompah/tasks` directory covers\
    \ the same branch-ownership cleanup warning-flood problem that OOMPAH-601 describes.\
    \ This is a unique issue.\n\n---\n\n**Focus handoff: duplicate_detector**\n\n\
    **Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search of .oompah/tasks (open/mer"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 81b77a4b-be9a-498f-a33e-7bfe877361d0
oompah.work_branch: epic-OOMPAH-588--task-OOMPAH-601
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-588--task-OOMPAH-601
  base_branch: epic-OOMPAH-588
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:57:17.259986+00:00'
oompah.task_costs:
  total_input_tokens: 606012
  total_output_tokens: 6823
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 606012
      output_tokens: 6823
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 605906
    output_tokens: 3306
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:55:24.028592+00:00'
  - profile: default
    model: haiku
    input_tokens: 106
    output_tokens: 3517
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:58:58.952150+00:00'
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
  - run_id: OOMPAH-601__20260730T155721Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-588--task-OOMPAH-601
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:58:58.956101+00:00'
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
author: oompah
created: 2026-07-30 15:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 31, Tool calls: 16
- Tokens: 106 in / 3.5K out [3.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 50s
- Log: OOMPAH-601__20260730T155721Z.jsonl
---
<!-- COMMENTS:END -->
