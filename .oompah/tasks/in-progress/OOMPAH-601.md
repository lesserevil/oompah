---
id: OOMPAH-601
type: bug
status: In Progress
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
updated_at: '2026-07-30T16:23:28.393099Z'
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
oompah.agent_run_id: fb8a4b0c-63ba-495d-ab14-f9ef02a9a941
oompah.work_branch: epic-OOMPAH-588--task-OOMPAH-601
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-588--task-OOMPAH-601
  base_branch: epic-OOMPAH-588
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T16:03:15.971571+00:00'
oompah.task_costs:
  total_input_tokens: 776439
  total_output_tokens: 8578
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 719600
      output_tokens: 8075
      cost_usd: 0.0
    opus:
      input_tokens: 56839
      output_tokens: 503
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
  - profile: default
    model: haiku
    input_tokens: 113588
    output_tokens: 1252
    cost_usd: 0.0
    recorded_at: '2026-07-30T16:02:09.514675+00:00'
  - profile: deep
    model: opus
    input_tokens: 56839
    output_tokens: 503
    cost_usd: 0.0
    recorded_at: '2026-07-30T16:03:02.118393+00:00'
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
  - run_id: OOMPAH-601__20260730T160131Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: auth_http
    source_branch: epic-OOMPAH-588--task-OOMPAH-601
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T16:02:09.519969+00:00'
  - run_id: OOMPAH-601__20260730T160242Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: auth_http
    source_branch: epic-OOMPAH-588--task-OOMPAH-601
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T16:03:02.122251+00:00'
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
author: oompah
created: 2026-07-30 16:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 16:01
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 16:02
---
Agent completed successfully in 56s (114840 tokens)
---
author: oompah
created: 2026-07-30 16:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 113.6K in / 1.3K out [114.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 56s
- Log: OOMPAH-601__20260730T160131Z.jsonl
---
author: oompah
created: 2026-07-30 16:02
---
Agent completed without closing this issue (56s (114840 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 16:02
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 16:02
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 16:03
---
Agent completed successfully in 27s (57342 tokens)
---
author: oompah
created: 2026-07-30 16:03
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 1
- Tokens: 56.8K in / 503 out [57.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 27s
- Log: OOMPAH-601__20260730T160242Z.jsonl
---
author: oompah
created: 2026-07-30 16:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 16:03
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 16:04
---
**Understanding & Plan:**

Issue: Branch-ownership cleanup is emitting one warning per child task on every maintenance tick (warning flood), instead of aggregating skips into a single structured summary. This happens when terminal child tasks legitimately share an epic-owned branch.

Goal: 
1. Resolve branch ownership through canonical task/epic aliases before deciding to skip
2. Preserve ambiguous/shared branches (don't warn about normal shared ownership)
3. Emit one structured categorized summary per run instead of per-tick warnings
4. Keep actionable corruption/unsafe-path cases as real warnings
5. Avoid multi-second reconciliation slowdown (measure latency)

Approach:
1. Find where the warning flood is happening (likely in orchestrator.py or projects.py cleanup logic)
2. Implement aggregation logic to collect skip reasons by category
3. Add tests for shared epic branches, aliases, missing project_id, cross-project identifiers, dirty branches, large batches
4. Verify latency stays within configured budget

Starting codebase exploration...
---
author: oompah
created: 2026-07-30 16:12
---
**Discovery:**

Found the warning flood source in oompah/projects.py:

The _delete_owned_issue_branch_locked() function (line 1895+) emits warnings for every child task with a shared epic branch:
- 'Skipping terminal branch not owned by issue' (line 1920-1925)
- 'Skipping protected terminal branch' (line 1929-1935)
- 'Skipping terminal branch still checked out in a worktree' (line 1945-1951)

When multiple child tasks share an epic branch (e.g., epic-OOMPAH-588), each child cleanup on each maintenance tick triggers these warnings, creating a flood.

Also confirmed by test test_terminal_child_cleanup_preserves_shared_epic_branch which shows that child tasks with epic branch names should be silently skipped without warnings.

Fix approach:
1. Distinguish between shared epic branches (silent skip) vs problematic cases (keep as warnings)
2. Aggregate skip reasons instead of per-issue warnings
3. Emit one structured summary per cleanup run with categorized counts
4. Enhance cleanup logic to detect parent epic relationship
---
author: oompah
created: 2026-07-30 16:23
---
**Implementation Progress:**

Completed core fix for warning flood issue:

1. **Modified _delete_owned_issue_branch_locked** (projects.py):
   - Changed return type from bool to (bool, skip_reason) tuple
   - Silently skips branches starting with 'epic-' (shared epic branches) without warning
   - Returns categorized skip_reason: 'shared_epic_branch', 'protected_branch', 'checked_out_in_worktree', 'not_owned'

2. **Updated cleanup_terminal_issue** (projects.py):
   - Now returns (changed, skip_reason) tuple
   - Passes skip reason up for orchestrator aggregation

3. **Enhanced _cleanup_terminal_worktrees** (orchestrator.py):
   - Tracks categorized skip_reasons dictionary
   - Aggregates skip counts across all terminal issues in cleanup run
   - Emits one structured summary log message instead of per-issue warnings
   - Includes 'skipped_branches' categorized counts in maintenance_status

4. **Updated tests**:
   - All 87 existing tests in test_projects.py pass
   - Tests handle new tuple return types
   - test_terminal_child_cleanup_preserves_shared_epic_branch verifies skip_reason='shared_epic_branch'

Next: Add orchestrator-level integration tests, verify latency budget
---
<!-- COMMENTS:END -->
