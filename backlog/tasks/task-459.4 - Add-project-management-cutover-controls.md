---
id: TASK-459.4
title: Add project management cutover controls
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 05:35'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.3
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/templates/projects.html
  - tests
parent_task_id: TASK-459
priority: medium
ordinal: 126000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update the projects management UI to show tracker backend, central task hub, legacy Backlog visibility/dispatch flags, and a guarded cutover action that warns existing Backlog tasks will not be migrated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Operators can see and edit tracker settings for each managed project.
- [ ] #2 Cutover copy explicitly states existing Backlog.md tasks are not migrated.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 04:52
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 04:52
---
Focus: Frontend Developer
---

author: oompah
created: 2026-06-09 05:13
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 0, Tool calls: 9
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 21m 1s
- Log: TASK-459.4__20260609T045257Z.jsonl
---

author: oompah
created: 2026-06-09 05:14
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 05:15
---
Focus: Frontend Developer
---

author: oompah
created: 2026-06-09 05:27
---
Agent stalled 1 time(s) (765s (173204 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 05:27
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 172.5K in / 735 out [173.2K total]
- Cost: $0.0000
- Exit: stalled, Duration: 12m 45s
- Log: TASK-459.4__20260609T051524Z.jsonl
---

author: oompah
created: 2026-06-09 05:29
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-09 05:30
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 05:30
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 05:31
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 6s
- Log: TASK-459.4__20260609T053030Z.jsonl
---

author: oompah
created: 2026-06-09 05:32
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-09 05:33
---
Understanding: This is NOT a duplicate. TASK-464.3 (phase 8) covers the backend cutover workflow; TASK-459.4 (phase 3) covers the UI changes to projects.html. Plan: (1) Add tracker settings section to each project in projects.html showing tracker_kind, tracker_owner, tracker_repo, github_project_node_id, legacy_backlog_enabled, legacy_backlog_dispatch; (2) Add editable controls for these fields; (3) Add a guarded cutover action button that shows a warning modal stating existing Backlog.md tasks will not be migrated; (4) Add tests.
---

author: oompah
created: 2026-06-09 05:35
---
Discovery: TASK-459.3 (Done) already added all 7 tracker fields to the Project model and API. projects.html needs: (1) display rows in project cards for tracker_kind, tracker_owner/repo (task hub), github_project_node_id, legacy_backlog_enabled/dispatch flags; (2) edit form inputs for these fields; (3) saveProject() to include them in PATCH body; (4) a cutover modal with warning that Backlog.md tasks won't be migrated; (5) tests in tests/test_projects_tracker_ui.py.
---
<!-- COMMENTS:END -->
