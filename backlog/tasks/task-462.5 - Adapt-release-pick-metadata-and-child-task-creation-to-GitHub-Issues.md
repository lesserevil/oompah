---
id: TASK-462.5
title: Adapt release-pick metadata and child task creation to GitHub Issues
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 04:30'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.3
  - TASK-454
  - TASK-455
  - TASK-456
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - oompah/templates/dashboard.html
parent_task_id: TASK-462
priority: high
ordinal: 149000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Integrate the release-pick workstream with GitHub issue fields/body metadata. Source tasks should track backport targets, child GitHub tasks, target branches, cherry-pick status, PR links, conflicts, and merged outcomes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Release-pick children are GitHub Issues for GitHub-backed projects.
- [ ] #2 Conflict states preserve worktrees and surface actionable comments.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 04:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 04:05
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 04:11
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 65
- Tokens: 107 in / 3.1K out [3.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 18s
- Log: TASK-462.5__20260610T040535Z.jsonl
---

author: oompah
created: 2026-06-10 04:13
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 04:13
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 04:23
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 62
- Tokens: 102 in / 3.5K out [3.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 56s
- Log: TASK-462.5__20260610T041322Z.jsonl
---

author: oompah
created: 2026-06-10 04:25
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-10 04:26
---
Understanding: This is NOT a duplicate. TASK-455.3 (Done) created child Backlog tasks for release-picks; TASK-454.4 (Open) defined the metadata schema. TASK-462.5 is distinct: it adapts the release-pick child-task creation to produce GitHub Issues (instead of Backlog tasks) when the project uses GitHub as its tracker, and ensures conflict states preserve worktrees and surface actionable comments. Dependencies TASK-462.3 (Done), TASK-454, TASK-455, TASK-456 are blockers listed but TASK-462.3 is Done — the other epics are Backlog but unblocking. Plan: (1) Find release_pick_reconciler.py and _create_backport_child(); (2) Detect whether the project uses GitHub tracker; (3) Create GitHub Issue instead of Backlog task for GitHub-backed projects; (4) Write backport metadata (target_branch, backport_of, backports, work_branch, etc.) to GitHub Issue body; (5) Handle conflict state: preserve worktree and add actionable comment; (6) Write tests.
---

author: oompah
created: 2026-06-10 04:30
---
Discovery: Not a duplicate. The previous agent runs produced the necessary code changes in the working tree but did not commit or close the task. Key changes found: (1) oompah/release_pick_reconciler.py — type hints changed from BacklogMdTracker to TrackerProtocol making the reconciler backend-agnostic; _post_conflict_source_comment() helper added to surface actionable conflict notices on source GitHub Issues; call to _post_conflict_source_comment added in _reconcile_entries when CONFLICT status is detected; (2) oompah/cherry_pick_pr_creator.py — same BacklogMdTracker→TrackerProtocol type annotation change; (3) tests/test_release_pick_github.py — 32 comprehensive tests covering GitHub Issue child creation, metadata round-trips, conflict comment surfacing, and full reconcile pass end-to-end. All 289 release-pick tests pass. AC#1 satisfied: _create_backport_child uses tracker.create_issue() polymorphically — GitHub tracker creates GitHub Issues; AC#2 satisfied: _post_conflict_source_comment posts actionable worktree-preservation message on source task. Need to commit and push.
---
<!-- COMMENTS:END -->
