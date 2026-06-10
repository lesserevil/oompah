---
id: TASK-464.6
title: Cut over aethel and remaining managed repos
status: Open
assignee: []
created_date: 2026-06-08 17:58
updated_date: 2026-06-10 16:04
labels:
- task
- github-issues
- tracker-migration
dependencies:
- TASK-464.5
references:
- plans/github-issues-tracker-migration.md
parent_task_id: TASK-464
priority: high
ordinal: 163000
oompah.task_costs:
  total_input_tokens: 25
  total_output_tokens: 382
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 25
      output_tokens: 382
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 25
    output_tokens: 382
    cost_usd: 0.0
    recorded_at: '2026-06-10T15:59:05.977303+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the cutover workflow to aethel and the rest of the managed repositories. Verify each repo has GitHub task creation, dispatch, PR reconciliation, webhook refresh, and Backlog file creation guardrails enabled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every managed repo creates new work as GitHub Issues.
- [ ] #2 No managed repo depends on Backlog.md for new task creation.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 15:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-10 15:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-10 15:59
---
Stopped the 2026-06-10 15:58 UTC run before it could perform managed-project cutovers from stale context. The worktree copy of TASK-464.5 still showed In Progress even though main/managed repo show Done, and the ACP tool catalog still only exposes generic file/search/run tools rather than safe project-management tools. Do not redispatch this task until the worktree/task sync issue is fixed or an operator performs the remaining cutovers externally and records the result.
---
author: oompah
created: 2026-06-10 15:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 10
- Tokens: 25 in / 382 out [407 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 2s
- Log: TASK-464.6__20260610T155810Z.jsonl
---
author: oompah
created: 2026-06-10 16:04
---
Unblocked after 70b1f39 landed on main and the service was restarted on 2026-06-10 16:04 UTC. The ACP tool catalog now exposes non-HTTP get_project/update_project tools, and TASK-464.5/TASK-464.6 were refreshed in the epic worktree so agents see TASK-464.5 as Done. Safe to redispatch; use the project tools instead of local HTTP calls or direct .oompah/projects.json edits.
---
<!-- COMMENTS:END -->
