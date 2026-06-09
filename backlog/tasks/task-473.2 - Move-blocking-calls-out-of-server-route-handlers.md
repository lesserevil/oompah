---
id: TASK-473.2
title: Move blocking calls out of server route handlers
status: In Progress
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 18:25'
labels:
  - performance
dependencies: []
parent_task_id: TASK-473
priority: high
ordinal: 200000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Audit the ~11 subprocess/run_in_executor/sync-I/O sites in oompah/server.py route handlers and ensure blocking work runs off the event loop (threadpool/async), so it cannot stall the shared loop the orchestrator and WebSocket broadcasts depend on.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No synchronous blocking call runs inline on the event loop in hot route handlers
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 14:33
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 14:33
---
Focus: Queue Api Oompah Specialist
---

author: oompah
created: 2026-06-09 14:46
---
Agent stalled 1 time(s) (760s (462057 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 14:46
---
Run #1 [attempt=1, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 461.1K in / 948 out [462.1K total]
- Cost: $0.0000
- Exit: stalled, Duration: 12m 40s
- Log: TASK-473.2__20260609T143409Z.jsonl
---

author: oompah
created: 2026-06-09 15:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:45
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 16:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 136
- Tokens: 204 in / 7.2K out [7.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 56m 25s
- Log: TASK-473.2__20260609T154607Z.jsonl
---

author: oompah
created: 2026-06-09 18:18
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 18:19
---
Understanding: No duplicate confirmed. TASK-473.3 (Done) fixed the favicon-specific sync read. TASK-473.2 is the broader audit task to move ALL ~11 blocking subprocess/run_in_executor/sync-I/O sites out of the event loop. TASK-473.1 already documented the sites: 3 urllib.urlopen calls, 4 sync open() calls, 2+ run_in_executor sites. Proceeding with implementation: audit oompah/server.py for all remaining blocking calls and wrap them in asyncio.to_thread() or replace with async equivalents.
---

author: oompah
created: 2026-06-09 18:25
---
Discovery: Found uncommitted changes from a previous agent run (136 tool calls, terminated). The working tree already has all the blocking-call fixes implemented but not committed. Fixes include: (1) api_create_issue: _run_issue_enhancement wrapped in asyncio.to_thread; (2) api_issue_quality_source: has_quality_source + load_quality_source refactored into _check_quality_source() thread helper; (3) api_list_foci: load_foci wrapped in to_thread; (4) api_create_focus: refactored into _save_focus() helper via to_thread; (5) api_delete_focus: refactored into _delete_focus() helper via to_thread; (6) api_update_focus: refactored into _load_update_save() helper via to_thread; (7) api_list_focus_suggestions: load_suggestions via to_thread; (8) api_update_focus_suggestion: update_suggestion_status via to_thread; (9) api_upload_attachment: all file write+store+commit refactored into _upload_sync() via to_thread; (10) api_serve_attachment: file read refactored into _read_attachment() via to_thread. Test file tests/test_server_blocking_off_loop.py also present (16 tests). All 16 tests pass. Proceeding to commit.
---
<!-- COMMENTS:END -->
