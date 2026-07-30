---
id: OOMPAH-581
type: task
status: In Progress
priority: null
title: Prune merged epic repair workspaces with task-style branch paths
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T04:35:07.041991Z'
updated_at: '2026-07-30T04:37:47.833659Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a338ea5975a877aefdcedab72f7a1b0b63004ce67dfebb4118df198b424a58e0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T04:37:29.793932+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search for related tasks, I've investigated\
    \ whether OOMPAH-581 is a duplicate of any existing issue. Here's my analysis:\n\
    \n## Search Findings\n\nI searched the complete `.oompah/tasks` directory across\
    \ all states:\n- **Open tasks**: Only OOMPAH-281 (self-hosted GitHub Actions runner\
    \ setup) \u2014 completely unrelated\n- **Merged tasks**: 7 tasks (OOMPAH-271,\
    \ 272, 275, 277, 278, 279, 280) \u2014 none related to epic repair/cleanup\n-\
    \ **Archived tasks**: 200+ historical tasks \u2014 no epic repair/worktree pruning\
    \ tasks found\n- **Backlog**: Only OOMPAH-282 (UnicodeEncodeError in state_branch_migration)\
    \ \u2014 unrelated\n\n### Keyword searches performed\n- `epic|cleanup|worktree`\
    \ \u2014 no matches in open/merged\n- `terminal|branch.*prune|worktree.*prune|maintenance|cleanup`\
    \ \u2014 no matches\n- `epic|state.*branch|orchestrator` \u2014 no matches\n-\
    \ `459` (GitHub reference from task description) \u2014 found OOMPAH-282, which\
    \ is an unrelated state_branch_migration error\n\n### Related GitHub issue\nOOMPAH-282\
    \ references GitHub issue `lesserevil/oompah#459`, but that issue is about a UnicodeEncodeError\
    \ in state_branch_migration, not epic workspace cleanup. The comments in OOMPAH-581\
    \ note that issue #459 **exposed** the problem that OOMPAH-581 aims to automate,\
    \ but they are addressing different concerns.\n\n## Conclusion\n\n**OOMPAH-581\
    \ is a unique task** with no active duplicate:\n- No existing task covers automating\
    \ the pruning of merged epic repair workspaces with task-style branch paths\n\
    - The manual cleanup already performed (mentioned in comments) is a one-off that\
    \ this task aims to make automatic for future occurrences\n- All related maintenance/cleanup\
    \ tasks are in terminal states or address different problems\n\n---\n\nFocus handoff:\
    \ duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\nMatches:\
    \ none\n\nEvidence: Comprehensive search of `.oompah/tasks` (300+ task files across\
    \ open/merged/archived/backlog) revealed no active tasks addressing epic repair\
    \ workspace cleanup or terminal epic mainten"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 94cb7506-1d98-421c-b561-a7afe82762f7
oompah.task_costs:
  total_input_tokens: 122
  total_output_tokens: 4044
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 122
      output_tokens: 4044
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 122
    output_tokens: 4044
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:37:29.792877+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-581__20260730T043610Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-581
    source_sha: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
    completed_at: '2026-07-30T04:37:29.807776+00:00'
---
## Summary

Live cleanup after OOMPAH-459 exposed one remaining owned legacy shape: a terminal epic records work_branch=epic-<id>, but an epic repair/planner run may leave a clean task-style managed worktree at <worktree_root>/<id> on branch <id>. Implementation scope: extend terminal maintenance cleanup in oompah/projects.py/orchestrator cleanup routing to recognize this exact same-identifier repair workspace only for terminal epic records, require the managed registered path and owned exact branch, and delete its worktree plus local/remote ref only when clean and merged/ancestor-safe. Never infer arbitrary paths, shared branches, dirty worktrees, or unmerged heads. Tests: real bare-remote scenario for a terminal epic with canonical epic work_branch plus auxiliary <id> repair worktree/branch; prove cleanup removes the auxiliary workspace and refs, while dirty, unmerged, shared, and different-identifier branches remain preserved. Acceptance criteria: a future OOMPAH-459-shaped repair workspace is removed by the normal aggressive cleanup pass without weakening ownership/ancestry guards; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 04:35
---
Live residue was manually pruned after confirming the clean repair head 95581aca5 is contained in origin/main. Removed managed worktree /home/shedwards/.oompah/worktrees/oompah/OOMPAH-459 and exact local/remote OOMPAH-459 refs. Task remains to automate this exact owned repair-workspace shape for recurrence.
---
author: oompah
created: 2026-07-30 04:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 04:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 04:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 37, Tool calls: 20
- Tokens: 122 in / 4.0K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 24s
- Log: OOMPAH-581__20260730T043610Z.jsonl
---
author: oompah
created: 2026-07-30 04:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 04:37
---
Focus: Refactoring Specialist
---
<!-- COMMENTS:END -->
