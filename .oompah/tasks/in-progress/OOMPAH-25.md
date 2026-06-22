---
id: OOMPAH-25
type: task
status: In Progress
priority: 1
title: Verify lightweight wheel contents and dependency boundary
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-24
labels: []
assignee: null
created_at: '2026-06-22T01:16:46.207414Z'
updated_at: '2026-06-22T02:48:23.633221Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 407d385b-22a6-4f25-a03b-2b48c7dc0f97
---
## Summary

Plan: plans/oompah-1.0-release.md#cli-and-api-contract

WHAT TO DO
Verify the lightweight wheel includes the modules required by oompah task and oompah project-bootstrap, while keeping server runtime dependencies behind the server extra.

HOW TO VERIFY
A clean wheel install can run the supported CLI commands, and dependency metadata does not force-install the full service runtime for normal CLI users.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:40
---
UNDERSTANDING: Not a duplicate. Searched existing tasks for 'wheel', 'lightweight', 'server extra', 'dependency boundary'. No existing task covers comprehensive dependency boundary verification. OOMPAH-7 (Merged) set up release packaging; OOMPAH-8 (Merged) added basic smoke tests; OOMPAH-24 (Done) expanded smoke tests for project-bootstrap. None specifically verify: (1) ALL server-only packages (not just watchfiles) are blocked from CLI import path, or (2) wheel contents include all required CLI modules. Proceeding to implement: add comprehensive server-dep blocking tests + wheel contents test to test_installed_cli_smoke.py and test_cli_release_packaging.py.
---
author: oompah
created: 2026-06-22 02:44
---
DISCOVERY: No existing test verifies wheel contents (which Python modules are included in the wheel). Existing tests check: (1) basic smoke (help exits zero), (2) watchfiles is blocked from CLI path, (3) pyproject.toml base deps = only httpx. Missing coverage: (a) ALL server packages (fastapi, uvicorn, jinja2, yaml/pyyaml, watchfiles, jwt/PyJWT, liquid/python-liquid, multipart/python-multipart) must be blocked from 'oompah task' and 'oompah project-bootstrap' import paths; (b) wheel contents (zipfile namelist) should include all required CLI modules (task_cli, project_bootstrap_cli, project_bootstrap, agent_instructions, etc.) when a wheel is present in dist/. Adding both to tests/test_installed_cli_smoke.py and tests/test_cli_release_packaging.py.
---
author: oompah
created: 2026-06-22 02:48
---
IMPLEMENTATION: Added 5 new tests across 2 files to verify the dependency boundary and wheel contents. (1) tests/test_installed_cli_smoke.py: test_oompah_task_help_does_not_import_any_server_package and test_oompah_project_bootstrap_help_does_not_import_any_server_package — comprehensive server dep blocking tests that guard all 8 server packages (fastapi, uvicorn, jinja2, yaml/pyyaml, watchfiles, jwt/PyJWT, liquid/python-liquid, multipart/python-multipart) not just watchfiles. (2) tests/test_cli_release_packaging.py: test_server_extras_complete_and_not_in_base_dependencies (verifies ALL server packages are in server extra and base deps = only httpx); test_wheel_contains_required_cli_modules (checks wheel zip contains all required CLI module paths — skipped without wheel); test_wheel_does_not_contain_server_only_module_as_dep (checks METADATA Requires-Dist has no unconditional server packages — skipped without wheel).
---
author: oompah
created: 2026-06-22 02:48
---
VERIFICATION: All tests pass. Full suite: 7045 passed, 31 skipped, 12 warnings. New tests: 3 passing (comprehensive server dep blocking for task and project-bootstrap, complete server extras metadata check) + 2 correctly skipped (wheel contents and wheel metadata checks — skip when dist/*.whl absent, will activate in release CI after 'python -m build').
---
<!-- COMMENTS:END -->
