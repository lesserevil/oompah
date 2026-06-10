---
id: TASK-464.8
title: Add non-HTTP project management path for agent-driven cutovers
status: Done
assignee: []
created_date: '2026-06-10 14:51'
updated_date: '2026-06-10 15:15'
labels:
  - bug
  - github-issues
  - agent-tools
dependencies: []
parent_task_id: TASK-464
priority: high
ordinal: 237000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Agents running through oompah MCP can deadlock or starve the service when they call back into http://127.0.0.1:8090 via curl or the oompah task CLI, because the same oompah process is servicing the MCP tool call. TASK-464.5 hit this while trying to PATCH /api/v1/projects/proj-3e4e9214 and then considered directly editing /home/shedwards/src/oompah/.oompah/projects.json. Add an MCP/project-management tool or other non-HTTP path for ProjectStore reads and updates needed by cutover tasks, and update agent instructions to forbid direct projects.json edits for production cutovers.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 14:52
---
Acceptance details: (1) agents have a non-HTTP way to read and update ProjectStore tracker fields for managed-project cutovers; (2) agent instructions/tools make local oompah HTTP self-calls unnecessary from MCP run_command; (3) production cutover prompts explicitly forbid direct edits to .oompah/projects.json; (4) TASK-464.5 can be moved back to Open and complete trickle cutover without local API curl timeouts or manual config-file edits.
---
author: oompah
created: 2026-06-10 14:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-10 14:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-10 15:14
---
Agent completed successfully in 1293s (41282 tokens)
---
author: oompah
created: 2026-06-10 15:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 163, Tool calls: 109
- Tokens: 84 in / 41.2K out [41.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 21m 33s
- Log: TASK-464.8__20260610T145258Z.jsonl
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented non-HTTP project management ACP/MCP tools on epic-TASK-464 and pushed commits 8a098a7, c0cc4e9, and f9af940. Verification passed: 458 targeted ACP/project tests and 423 broader tests. Live server still needs the epic branch merged/restarted before downstream cutover agents can use these tools.
<!-- SECTION:FINAL_SUMMARY:END -->
