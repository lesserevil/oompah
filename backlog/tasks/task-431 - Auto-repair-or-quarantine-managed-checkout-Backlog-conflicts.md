---
id: TASK-431
title: Auto-repair or quarantine managed checkout Backlog conflicts
status: In Progress
assignee: []
created_date: 2026-06-03 06:16
updated_date: 2026-06-03 07:15
labels:
- bug
- backlog
- orchestrator
dependencies: []
priority: high
ordinal: 67000
oompah.task_costs:
  total_input_tokens: 902528
  total_output_tokens: 2185
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 902528
      output_tokens: 2185
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 784668
    output_tokens: 1391
    cost_usd: 0.0
    recorded_at: '2026-06-03T06:56:09.759640+00:00'
  - profile: deep
    model: unknown
    input_tokens: 117860
    output_tokens: 794
    cost_usd: 0.0
    recorded_at: '2026-06-03T07:14:01.620368+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Managed project checkouts can accumulate unresolved Git conflicts in backlog task files when oompah and remote updates both edit task metadata. We saw this in Aethel TASK-3.1/TASK-8.3 and in the managed oompah checkout TASK-407.11/TASK-427/TASK-428. When a Backlog task file contains conflict markers or otherwise invalid YAML/frontmatter, BacklogMdTracker skips the task and the dashboard becomes inconsistent with reality.

Implement startup and project-sync handling so oompah never silently runs with a managed checkout that has unresolved Backlog conflicts. The handler should inspect each managed repo for unmerged paths and Backlog parse failures before scheduling. For conflicts limited to backlog task files, attempt a deterministic structured repair that preserves both sides where possible: canonical lifecycle status, comments, final summary, oompah.task_costs, dependencies, labels, parent_task_id, and the newest meaningful updated_date. After repair, validate with BacklogMdTracker/backlog CLI parsing before allowing the project to schedule.

If repair cannot be proven safe, quarantine or pause that project, surface a dashboard alert with the project name and conflicted paths, and avoid dispatching tasks from that project until the checkout is repaired. Do not leave tasks invisible or schedulable from partially parsed state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Startup checks every managed checkout for unmerged Git paths and invalid Backlog task frontmatter before dispatch.
- [ ] #2 Backlog-only conflicts get an automatic structured merge that preserves comments, final summary, oompah.task_costs, dependencies, labels, parent_task_id, and valid lifecycle status.
- [ ] #3 Automatic repair validates the resulting task files through the same parser used by BacklogMdTracker before the project can schedule.
- [ ] #4 Unrepairable conflicts pause or quarantine only the affected project and show a dashboard alert naming the project and conflicted files.
- [ ] #5 Regression tests cover auto-repair, unrepairable quarantine/alert behavior, and prevention of task scheduling from an invalid managed checkout.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Use the Backlog CLI or BacklogMdTracker parser for validation instead of ad hoc string checks.
- [ ] #2 make test passes.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 06:17

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 06:18

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 06:56

Agent stalled 1 time(s) (2305s (786059 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 06:56

Run #1 [attempt=1, profile=default, role=fast -> Godspeed/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4]
- Turns: 19, Tool calls: 19
- Tokens: 784.7K in / 1.4K out [786.1K total]
- Cost: $0.0000
- Exit: stalled, Duration: 38m 25s
- Log: TASK-431__20260603T061807Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 06:56

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 06:56

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 07:14

Run #2 [attempt=2, profile=deep, role=deep -> Godspeed/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4]
- Turns: 12, Tool calls: 12
- Tokens: 117.9K in / 794 out [118.7K total]
- Cost: $0.0000
- Exit: stalled, Duration: 17m 28s
- Log: TASK-431__20260603T065638Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 07:14

Issue has failed 2 time(s). Attempting auto-decomposition into smaller tasks.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-03 07:14

Auto-decomposition failed: No provider configured for decomposition. Falling back to normal retry.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-03 07:14

Retrying (attempt #2, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-03 07:14

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12
author: oompah
created: 2026-06-03 07:14

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 13
author: oompah
created: 2026-06-03 07:14

Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 5s
- Log: TASK-431__20260603T071431Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14
author: oompah
created: 2026-06-03 07:15

Retrying (attempt #3, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 15
author: oompah
created: 2026-06-03 07:30

UNDERSTANDING: Not a duplicate — TASK-418 was a manual one-off fix; TASK-431 implements a systematic auto-repair/quarantine mechanism. Plan: (1) New oompah/backlog_conflict.py with conflict detection and structured repair logic; (2) Add backlog_conflict_paths field to Project model to persist quarantine state; (3) Update sync_project_sources() to detect/attempt repair/quarantine; (4) Update orchestrator startup_cleanup() to surface dashboard alerts for paused+conflicted projects; (5) Tests covering auto-repair, quarantine, alert surfacing, and dispatch prevention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16
author: oompah
created: 2026-06-03 07:45

IMPLEMENTATION: Created oompah/backlog_conflict.py with has_conflict_markers(), repair_backlog_task_file(), inspect_repo_backlog_conflicts(), and repair_repo_backlog_conflicts(). The structured merge preserves: most-advanced lifecycle status, union of labels/dependencies, newest updated_date, non-empty final_summary/parent, merged oompah.task_costs. Updated Project model with backlog_conflict_paths field. Updated sync_project_sources() to detect conflicts, attempt repair, quarantine (pause=True + store paths) if unrepairable. Added _refresh_backlog_conflict_alerts() to orchestrator that surfaces error-level dashboard alerts with project name and conflicted file paths. Called from startup_cleanup() and after each webhook sync. 60 new tests, updated 4 existing tests.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
