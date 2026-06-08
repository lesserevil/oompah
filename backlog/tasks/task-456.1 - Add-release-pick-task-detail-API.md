---
id: TASK-456.1
title: Add release-pick task detail API
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 21:19'
labels:
  - task
dependencies:
  - TASK-454.4
parent_task_id: TASK-456
priority: high
ordinal: 103000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create API helpers/endpoints to read and update release-pick metadata for a task, validate target branches, and return normalized target status, child task IDs, PR IDs, and URLs.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:41
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:41
---
Focus: Queue Api Oompah Specialist
---

author: oompah
created: 2026-06-08 20:52
---
Agent completed successfully in 665s (980744 tokens)
---

author: oompah
created: 2026-06-08 20:52
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/Nemotron-3-Nano-30B-A3B]
- Turns: 23, Tool calls: 22
- Tokens: 962.1K in / 18.7K out [980.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 5s
- Log: TASK-456.1__20260608T204151Z.jsonl
---

author: oompah
created: 2026-06-08 20:52
---
Agent completed without landing — no commits found on origin for branch `epic-TASK-456`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-08 20:55
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:55
---
Focus: Queue Api Oompah Specialist
---

author: oompah
created: 2026-06-08 21:02
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 296.1K in / 641 out [296.7K total]
- Cost: $0.0000
- Exit: stalled, Duration: 7m 7s
- Log: TASK-456.1__20260608T205611Z.jsonl
---

author: oompah
created: 2026-06-08 21:02
---
Agent stalled 1 time(s) (427s (296695 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-08 21:03
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-08 21:03
---
Focus: Queue Api Oompah Specialist
---

author: oompah
created: 2026-06-08 21:04
---
Agent completed successfully in 65s (15608 tokens)
---

author: oompah
created: 2026-06-08 21:04
---
Run #3 [attempt=3, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 2, Tool calls: 1
- Tokens: 15.4K in / 171 out [15.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 5s
- Log: TASK-456.1__20260608T210402Z.jsonl
---

author: oompah
created: 2026-06-08 21:05
---
Agent completed without landing — no commits found on origin for branch `epic-TASK-456`. No stronger profile is configured; retrying with 'deep' in 20s (2/3).
---

author: oompah
created: 2026-06-08 21:07
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-08 21:10
---
Understanding (Duplicate Investigator + Implementation): This is NOT a duplicate. TASK-454.x tasks (Done/In Progress) built the underlying schema (release_pick_schema.py) and validation (release_pick_validation.py). TASK-456.1 is a distinct task: it creates the HTTP API layer (GET + PATCH /api/v1/issues/{identifier}/release-picks) and an oompah/release_pick_api.py helper module. The endpoints will read normalized release-pick metadata (backports list with status/task_id/pr_url per entry, plus backport_of for child tasks) and allow updates with branch validation. Plan: create release_pick_api.py with read/update helpers, add two endpoints to server.py, add tests.
---

author: oompah
created: 2026-06-08 21:19
---
Implementation: Created oompah/release_pick_api.py with get_release_pick_detail(), update_release_pick_entry(), and update_release_picks_bulk() helpers. Added GET /api/v1/issues/{identifier}/release-picks and PATCH /api/v1/issues/{identifier}/release-picks endpoints to server.py. GET returns normalized backports list (branch, status, task_id, pr_url, pr_id derived from URL, is_valid, validation_error) and backport_of dict. PATCH supports single-entry and bulk update modes; validates all target branches before writing. Body validation (project_id, JSON parse) happens before orchestrator lookup so errors return 400 not 503.
---

author: oompah
created: 2026-06-08 21:19
---
Verification: 278 tests pass across test_release_pick_api.py (44), test_server_release_picks.py (18), test_release_pick_schema.py (97), test_release_pick_validation.py (44), test_server_issue_detail.py/api.py (33), test_backlog_tracker.py (50), test_server_label_api.py, test_server_create_issue.py. Zero regressions.
---

author: oompah
created: 2026-06-08 21:19
---
Completion: Delivered oompah/release_pick_api.py (helpers: get_release_pick_detail, update_release_pick_entry, update_release_picks_bulk) and two HTTP endpoints (GET + PATCH /api/v1/issues/{identifier}/release-picks) in server.py. GET returns normalized backports list with status, task_id, pr_url, pr_id, is_valid, validation_error and backport_of dict. PATCH supports single-entry and bulk update modes with pre-write branch validation. 62 new tests (44 unit + 18 integration), 278 total passing. Pushed to origin/epic-TASK-456.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Created oompah/release_pick_api.py with get_release_pick_detail(), update_release_pick_entry(), and update_release_picks_bulk() API helpers. Added GET and PATCH /api/v1/issues/{identifier}/release-picks endpoints to server.py. GET returns normalized backports list (branch, status, task_id, pr_url, pr_id derived from URL, is_valid, validation_error) and backport_of. PATCH supports single-entry and bulk update modes with pre-write branch validation via release_pick_validation.py. 62 new tests (44 unit + 18 server integration), 278 total passing. Not a duplicate.
<!-- SECTION:FINAL_SUMMARY:END -->
