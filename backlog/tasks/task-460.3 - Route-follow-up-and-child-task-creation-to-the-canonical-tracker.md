---
id: TASK-460.3
title: Route follow-up and child task creation to the canonical tracker
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 05:24'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - WORKFLOW.md
  - oompah/orchestrator.py
  - oompah/error_watcher.py
parent_task_id: TASK-460
priority: high
ordinal: 133000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure agent-created follow-ups, child tasks, missing-capability tasks, watcher tasks, and handoff tasks go through the oompah task wrapper or tracker protocol. For legacy Backlog tasks, new follow-ups should still be GitHub Issues unless explicitly configured otherwise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No GitHub-backed workflow instructs agents to create Backlog task files.
- [ ] #2 Follow-up task parent/source metadata is preserved across tracker backends.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 03:50
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:50
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 04:11
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 99
- Tokens: 157 in / 5.3K out [5.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 21m 27s
- Log: TASK-460.3__20260610T035011Z.jsonl
---

author: oompah
created: 2026-06-10 04:12
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
- Turns: 0, Tool calls: 76
- Tokens: 114 in / 3.7K out [3.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 59s
- Log: TASK-460.3__20260610T041317Z.jsonl
---

author: oompah
created: 2026-06-10 04:25
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-10 04:25
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 04:39
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 04:39
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 05:20
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 05:21
---
Understanding: No duplicate found. TASK-461.6 is a downstream dependent task (phase 5), not a duplicate. This task (TASK-460.3, phase 4) needs to: (1) Update WORKFLOW.md agent instructions to use 'oompah task' wrapper instead of direct backlog CLI for task creation; (2) Update orchestrator.py and error_watcher.py to route auto-filed tasks through the tracker protocol. The dependency TASK-460.1 is Done (oompah task CLI wrapper exists). Plan: explore modified files listed in task metadata, then update agent prompt instructions and auto-filing code paths.
---

author: oompah
created: 2026-06-10 05:24
---
Discovery: Confirmed not a duplicate. Found that prior partial runs had already implemented all required changes in the working tree: (1) WORKFLOW.md: github_issues template now passes --source {{issue.identifier}} for follow-up task creation; legacy Backlog template embeds 'Follow-up from {{issue.identifier}}' in description. (2) oompah/task_cli.py: added --source flag, sends source_task_id to server. (3) oompah/server.py: handles source_task_id by prepending 'Triggered by: <id>' to description across all tracker backends. (4) Tests in test_server_create_issue.py (5 tests), test_task_cli.py (4 tests), test_prompt.py (3 tests). The orchestrator.py and error_watcher.py already use tracker.create_issue() (tracker-neutral), no changes needed there.
---

author: oompah
created: 2026-06-10 05:24
---
Implementation: Committed and pushed to epic-TASK-460. Changes: (1) WORKFLOW.md adds --source to github_issues follow-up template and embeds 'Follow-up from' in legacy Backlog description. (2) oompah/task_cli.py adds --source flag for source_task_id. (3) oompah/server.py prepends 'Triggered by: <id>' in description when source_task_id given. (4) 12 new tests across 3 test files. All 149 tests pass. Acceptance criteria met: AC#1 - GitHub-backed workflow uses oompah task create (not backlog task create); AC#2 - source metadata preserved via 'Triggered by:' in description across tracker backends.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Routed follow-up and child task creation to canonical tracker. (1) WORKFLOW.md: github_issues branch now uses 'oompah task create --source {{issue.identifier}}' for follow-ups (no backlog commands); legacy Backlog branch embeds 'Follow-up from {{issue.identifier}}' in description for traceability. (2) oompah/task_cli.py: --source flag added to oompah task create. (3) oompah/server.py: source_task_id prepends 'Triggered by: <id>' to description across all tracker backends. (4) orchestrator.py and error_watcher.py already use tracker.create_issue() (tracker-neutral). 12 new tests, 149 pass. Both ACs satisfied.
<!-- SECTION:FINAL_SUMMARY:END -->
