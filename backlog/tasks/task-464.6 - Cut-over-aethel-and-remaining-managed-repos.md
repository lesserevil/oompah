---
id: TASK-464.6
title: Cut over aethel and remaining managed repos
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 16:23'
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

author: oompah
created: 2026-06-10 16:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 16:05
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 16:07
---
Stopped the 2026-06-10 16:05 UTC run because the new project tools are still too narrow for TASK-464.6: get_project/update_project only operate on the current oompah project, while this task needs to inspect and update other managed projects such as aethel. Do not redispatch until the ACP project tools support listing managed projects and selecting a target project_id without HTTP self-calls or direct .oompah/projects.json access.
---

author: oompah
created: 2026-06-10 16:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 17
- Tokens: 35 in / 813 out [848 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 51s
- Log: TASK-464.6__20260610T160534Z.jsonl
---

author: oompah
created: 2026-06-10 16:16
---
Unblocked after 824104a landed on main and the service was restarted on 2026-06-10 16:18 UTC. ACP agents now have mcp__oompah__list_projects plus mcp__oompah__get_project_by_id/mcp__oompah__update_project_by_id, so this task can discover and update aethel/remaining managed projects through ProjectStore without HTTP self-calls or direct .oompah/projects.json access.
---

author: oompah
created: 2026-06-10 16:17
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 16:20
---
UNDERSTANDING: This task is NOT a duplicate — it uniquely covers cutting over the remaining managed repos to GitHub Issues after TASK-464.5 completed trickle. Key findings: (1) Only 2 managed projects exist: oompah (proj-14849f1b, tracker_kind=null) and trickle (proj-3e4e9214, already cut over). (2) 'aethel' is referenced in the migration plan as an example repo but does NOT exist as a managed project — no cutover needed. (3) The main work is to cut over the oompah project (proj-14849f1b) to github_issues with tracker_owner=lesserevil, tracker_repo=oompah, legacy_backlog_enabled=true (keeps existing Backlog tasks visible), legacy_backlog_dispatch=false. (4) Trickle's settings look correct: tracker_kind=github_issues, legacy_backlog_enabled=true, legacy_backlog_dispatch=false. Plan: (a) update oompah project via mcp__oompah__update_project, (b) verify both projects satisfy the acceptance criteria, (c) close.
---

author: oompah
created: 2026-06-10 16:22
---
DISCOVERY: Confirmed not a duplicate. Key findings: (1) Only 2 managed projects: oompah (proj-14849f1b, tracker_kind=null) and trickle (proj-3e4e9214, already cut over). 'aethel' is not a managed project — it appears in the migration plan as a planning example only. (2) The dispatch gate in orchestrator.py lines 5331-5339 only applies when _is_github_backed() returns True (i.e., tracker_kind=github_issues). Currently oompah has tracker_kind=null so all Backlog tasks dispatch freely. (3) trickle is fully cut over and correct. (4) Work needed: set oompah (proj-14849f1b) to tracker_kind=github_issues, tracker_owner=lesserevil, tracker_repo=oompah, legacy_backlog_enabled=true (existing tasks visible), legacy_backlog_dispatch=true (TASK-464.7 and active Backlog tasks can still run to completion). (5) No code changes needed — all guardrails (Backlog file creation guard TASK-460.4, dispatch gate TASK-464.2) already implemented. This is a pure ProjectStore configuration update.
---

author: oompah
created: 2026-06-10 16:23
---
IMPLEMENTATION: Cut over oompah project (proj-14849f1b) to GitHub Issues via mcp__oompah__update_project. Final state: tracker_kind=github_issues, tracker_owner=lesserevil, tracker_repo=oompah, tracker_cutover_at=2026-06-10T16:23:00+00:00, legacy_backlog_enabled=true (existing Backlog tasks remain visible), legacy_backlog_dispatch=true (TASK-464.7 and other active Backlog tasks can still run to completion). 'aethel' is not a managed project — only a planning example in the migration plan. Trickle was already cut over by TASK-464.5. All guardrails verified: (1) completion_verifier.py rejects GitHub-backed tasks that add backlog/ files, (2) orchestrator.py dispatch gate blocks Backlog tasks for github-backed projects without legacy_backlog_dispatch, (3) projects.py source sync skips Backlog compat checks for github-backed projects, (4) PR reconciliation via _is_github_backed() paths. No code changes needed — this was a pure ProjectStore configuration update.
---
<!-- COMMENTS:END -->
