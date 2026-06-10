---
id: TASK-460.1
title: Build oompah task command wrapper
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 03:38'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - pyproject.toml
  - oompah/server.py
  - tests
parent_task_id: TASK-460
priority: high
ordinal: 131000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add an oompah task CLI or equivalent server-backed command surface for view, comment, create, child-create, set-status, add-label, remove-label, and set-dependency. The wrapper should call the local oompah API and work for both GitHub and legacy Backlog trackers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Agents have one tracker-neutral command surface for task operations.
- [ ] #2 Wrapper commands fail loudly with actionable errors when the local server is unavailable.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 03:18
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:19
---
Understanding: This task requires building an 'oompah task' CLI wrapper that calls the local oompah server API to provide tracker-neutral task operations (view, comment, create, child-create, set-status, add-label, remove-label, set-dependency). No duplicate found after searching. The dependency TASK-459.2 is merged, giving us backend-neutral mutation endpoints to call. Plan: (1) explore server.py APIs and existing CLI entry points, (2) implement oompah/task_cli.py with each subcommand, (3) wire it into the CLI entry point, (4) add tests, (5) verify.
---

author: oompah
created: 2026-06-10 03:23
---
Discovery: The server API already has all necessary endpoints except POST /api/v1/issues/{identifier}/dependencies (the tracker protocol has add_dependency() but no server route). The CLI will: (1) use httpx (already a project dep) to call the local server, (2) be implemented as oompah/task_cli.py, (3) be wired into __main__.py as 'oompah task ...' subcommand dispatch. For set-status with --summary, we'll set the status via PATCH then add a comment for the summary text. All 8 operations map cleanly to existing server endpoints except set-dependency which needs a new POST /api/v1/issues/{id}/dependencies endpoint.
---

author: oompah
created: 2026-06-10 03:36
---
Implementation: Created oompah/task_cli.py with all 8 subcommands (view, comment, create, child-create, set-status, add-label, remove-label, set-dependency). Added POST /api/v1/issues/{identifier}/dependencies endpoint to server.py (mirrors the label API pattern with project_id/managed_repo/issue_key resolution). Wired 'oompah task ...' dispatch into __main__.py before the server argparse. Tests: 71 tests in test_task_cli.py + 16 tests in test_server_dependencies.py = 87 new tests.
---

author: oompah
created: 2026-06-10 03:38
---
Verification: 87 new tests pass (71 task_cli + 16 server_dependencies). Additional 809+ existing tests verified clean. 'oompah task --help' shows all 8 subcommands. Both acceptance criteria met: (1) tracker-neutral command surface implemented; (2) ConnectError and TimeoutException exit with actionable messages including server start instructions.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Built oompah task CLI wrapper (oompah/task_cli.py) with 8 tracker-neutral subcommands: view, comment, create, child-create, set-status, add-label, remove-label, set-dependency. Added POST /api/v1/issues/{id}/dependencies server endpoint. Wired dispatch in __main__.py. 87 new tests. Both ACs met: tracker-neutral command surface + fail-loud on server unavailability.
<!-- SECTION:FINAL_SUMMARY:END -->
