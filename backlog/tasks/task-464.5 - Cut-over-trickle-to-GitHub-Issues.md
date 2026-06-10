---
id: TASK-464.5
title: Cut over trickle to GitHub Issues
status: Needs Human
assignee: []
created_date: 2026-06-08 17:58
updated_date: 2026-06-10 15:26
labels:
- task
- github-issues
- tracker-migration
dependencies:
- TASK-464.4
- TASK-464.8
references:
- plans/github-issues-tracker-migration.md
parent_task_id: TASK-464
priority: high
ordinal: 162000
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 48
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 48
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 10
    output_tokens: 48
    cost_usd: 0.0
    recorded_at: '2026-06-10T15:25:49.791467+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the managed-project cutover workflow to trickle after the low-risk repo has run cleanly. Verify task creation, dispatch, PR links, review reconciliation, release-pick metadata, and no new Backlog task files after cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New trickle tasks are GitHub Issues in the central task hub.
- [ ] #2 trickle legacy Backlog tasks are visible/dispatchable only according to configured flags.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 14:21
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 14:21
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 14:26
---
Operator hint: the managed project named trickle is repo https://github.com/NVIDIA-Omniverse/trickle, project_id proj-3e4e9214, local mirror /home/shedwards/.oompah/repos/trickle. lesserevil/trickle returning 404 is expected and should not be used. The live project API is GET http://127.0.0.1:8090/api/v1/projects; the isolated agent worktree does not contain .oompah/projects.json. GitHub Issues are enabled on NVIDIA-Omniverse/trickle and the available token has repo admin/maintain/push permissions. Current live project state is not yet cut over: tracker_kind=null, tracker_owner=null, tracker_repo=null, cutover_at=null, legacy_backlog_enabled=false, legacy_backlog_dispatch=false.
---

author: oompah
created: 2026-06-10 14:29
---
Operator intervention: pausing this run because epic-TASK-464 is stale relative to main and does not include the already-merged TASK-461 per-project tracker routing. Continuing on the stale branch would reason from obsolete code. Next step is to rebase epic-TASK-464 onto origin/main, preserve the task comments/status updates, then resume TASK-464.5 from the rebased branch.
---

author: oompah
created: 2026-06-10 14:30
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 59
- Tokens: 90 in / 3.0K out [3.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 59s
- Log: TASK-464.5__20260610T142128Z.jsonl
---

author: oompah
created: 2026-06-10 14:33
---
Operator correction after rebase: earlier discovery saying lesserevil/oompah should serve as the trickle task hub was based on stale branch context and is incorrect for the real trickle smoke. Use the managed project facts from the operator hint: project_id proj-3e4e9214, repo https://github.com/NVIDIA-Omniverse/trickle, local mirror /home/shedwards/.oompah/repos/trickle. The branch has been rebased onto current origin/main so TASK-461 per-project tracker routing is available.
---

author: oompah
created: 2026-06-10 14:41
---
Operator correction: use the current project field name tracker_cutover_at, not cutover_at. Cutover configuration is done with PATCH /api/v1/projects/<project-id> using tracker_kind, tracker_owner, tracker_repo, tracker_cutover_at, legacy_backlog_enabled, legacy_backlog_dispatch, and paused as needed; there are no /cutover or /rollback project endpoints on current main.
---

author: oompah
created: 2026-06-10 14:41
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 14:41
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 14:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 31
- Tokens: 55 in / 1.5K out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 32s
- Log: TASK-464.5__20260610T144145Z.jsonl
---

author: oompah
created: 2026-06-10 14:50
---
Operator intervention: stopped the TASK-464.5 agent before it fell back to directly editing /home/shedwards/src/oompah/.oompah/projects.json. The root cause is an oompah self-call deadlock/starvation pattern: an agent command executed through oompah MCP called back into http://127.0.0.1:8090/api/v1/projects, which timed out because the same service was busy servicing the agent tool call. Do not direct-edit projects.json for cutover. A future run needs either an operator-side PATCH call or an oompah MCP/project-management tool that updates the ProjectStore without HTTP self-calls.
---

author: oompah
created: 2026-06-10 14:51
---
Moved to Needs Human from the dashboard/API. Human action required: inspect TASK-464.5 (Cut over trickle to GitHub Issues), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---

author: oompah
created: 2026-06-10 15:15
---
Operator note: TASK-464.8 implementation has been pushed on epic-TASK-464, but keep this task in Needs Human in the managed repo until that branch lands and the running oompah service has restarted onto code that includes the new mcp__oompah__get_project and mcp__oompah__update_project tools. Reopening before then would dispatch another agent on the old tool catalog and risk the same local HTTP self-call failure.
---
author: user
created: 2026-06-10 15:23
---
I approve this action. Please cut over trickle to github issues.
---
author: oompah
created: 2026-06-10 15:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-10 15:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-10 15:25
---
Moved to Needs Human from the dashboard/API. Human action required: inspect TASK-464.5 (Cut over trickle to GitHub Issues), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-06-10 15:25
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 3
- Tokens: 10 in / 48 out [58 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 27s
- Log: TASK-464.5__20260610T152430Z.jsonl
---
author: oompah
created: 2026-06-10 15:26
---
Operator intervention: stopped the 2026-06-10 15:24 UTC run even though the cutover is approved, because the live ACP/MCP tool catalog for the run still only exposed generic read/write/search/run tools and did not include mcp__oompah__get_project or mcp__oompah__update_project. Re-dispatching before the running service is restarted onto the TASK-464.8 code risks repeating the local HTTP self-call/direct projects.json fallback failure. Keep this in Needs Human until either the service is restarted on code with those tools or an operator performs the ProjectStore cutover externally and records the result.
---
<!-- COMMENTS:END -->
