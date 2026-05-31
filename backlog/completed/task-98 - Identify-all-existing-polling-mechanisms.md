---
id: TASK-98
title: Identify all existing polling mechanisms
status: Done
assignee: []
created_date: 2026-03-08 20:10
updated_date: 2026-03-08 20:35
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-8r5
  state: closed
  parent_id: oompah-ky3
  dependencies: []
  branch_name: oompah-8r5
  target_branch: null
  url: null
  created_at: '2026-03-08T20:10:05Z'
  updated_at: '2026-03-08T20:35:02Z'
  closed_at: '2026-03-08T20:35:02Z'
parent: TASK-71
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Find and list all the places where polling is currently used
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 565f8024-a849-4c39-b7fd-1ebe29c8404a
author: oompah
created: 2026-03-08T20:23:41Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bff3cb0f-841d-4354-8863-a007b1205dd8
author: oompah
created: 2026-03-08T20:23:41Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 17e3d717-7263-4011-9706-518543578b14
author: oompah
created: 2026-03-08T20:24:01Z

I understand the issue: Find and list all places where polling is currently used in the codebase. This is a subtask of the larger epic (oompah-ky3) to replace all polling with event-driven mechanisms. My plan is to: 1) Search the codebase for common polling patterns (while loops, sleep, time.sleep, asyncio.sleep, setInterval, etc.), 2) Document each polling location with file, line, and description, 3) Create a structured summary and potentially create child issues for each polling mechanism that needs to be replaced.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b42e82f8-3a42-4528-a3ca-c9ea60a7b2ca
author: oompah
created: 2026-03-08T20:24:42Z

Found all polling mechanisms in the codebase. Summary:

1. **Orchestrator main poll loop** (oompah/orchestrator.py:316-328): The core  method uses  with  on a  event, timing out at  (default 30s). This drives issue fetch, dispatch, and reconciliation.

2. **Graceful restart drain loop** (oompah/orchestrator.py:194):  — polls until agents drain or timeout.

3. **LogFileWatcher poll loop** (oompah/error_watcher.py:289-297):  — polls log files every 2 seconds (configurable) for new error lines.

4. **Agent CLI worker turn loop** (oompah/agent.py:109 / orchestrator.py CLi worker):  with continuous turn streaming — not strictly polling but a sequential loop.

5. **CLI main restart loop** (oompah/__main__.py:66):  outer loop in  that restarts the process via  on graceful restart.

6. **AgentSession stream_turn loop** (oompah/agent.py:262):  inner loop reading stdout lines during a turn — event-driven via readline but structured as a poll loop.

7. **Config setting**:  (default 30000ms) in  and  configures the main orchestrator poll interval.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a952903c-7ad4-4b42-a7d8-25f18f34991b
author: oompah
created: 2026-03-08T20:29:35Z

Agent failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -1287005, Model saturation: 70.7%'}","type":"None","param":"None","code":"429"}}. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 03b6eea2-0126-4890-ae91-3e981b2b9ba2
author: oompah
created: 2026-03-08T20:29:45Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3d109062-62ec-4851-a8a3-d0954a8b636d
author: oompah
created: 2026-03-08T20:29:46Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6c8b0c55-a743-4636-9c17-164c5fbce2b2
author: oompah
created: 2026-03-08T20:29:48Z

Agent failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -1911665, Model saturation: 73.7%'}","type":"None","param":"None","code":"429"}}. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 22c87565-849d-49c1-aae6-37a8de74b580
author: oompah
created: 2026-03-08T20:32:09Z

Retrying (attempt #4, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 08c81266-f3f0-4014-926b-120f32c267bf
author: oompah
created: 2026-03-08T20:32:10Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 38c0c598-f711-462b-a1eb-9d90396f6d28
author: oompah
created: 2026-03-08T20:34:45Z

Implementation: Created docs/polling-mechanisms.md with a full inventory of all 6 polling locations found. Each entry includes file path, line numbers, code snippet, interval, and what it does. The two highest-priority items for event-driven replacement are: (1) orchestrator.py run() — the 30s main poll loop, and (3) error_watcher.py LogFileWatcher.start() — the 2s file-polling loop.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 71b1273f-bb63-46c3-90a3-c1b03231fdf0
author: oompah
created: 2026-03-08T20:34:52Z

Verification: Existing test suite runs (12 pre-existing failures unrelated to this change, 606 pass). No code was modified — only docs/polling-mechanisms.md added. PR: https://github.com/lesserevil/oompah/pull/33
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dd4106b8-552d-4cb4-b292-e2a9111ba4e9
author: oompah
created: 2026-03-08T20:34:57Z

Completion: Delivered docs/polling-mechanisms.md documenting all 6 polling mechanisms in the codebase. High-priority items for oompah-ky3 (event-driven epic): (1) Orchestrator main poll loop in orchestrator.py run() — 30s interval, core scheduling; (3) LogFileWatcher poll loop in error_watcher.py — 2s interval, continuous file polling. PR: https://github.com/lesserevil/oompah/pull/33
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1e3f03dc-4d61-4ab5-9918-8bac9da3032c
author: oompah
created: 2026-03-08T20:35:02Z

Agent completed successfully in 173s (434593 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
