---
id: OOMPAH-31
type: task
status: Done
priority: 1
title: Validate project bootstrap flows across managed projects
parent: OOMPAH-27
children: []
blocked_by:
- OOMPAH-26
- OOMPAH-30
labels: []
assignee: null
created_at: '2026-06-22T01:17:08.467848Z'
updated_at: '2026-06-22T14:20:36.809164Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 575ffd89-e5d6-486d-b2f1-b3ebe123b185
---
## Summary

Plan: plans/oompah-1.0-release.md#managed-project-workflow-readiness

WHAT TO DO
Validate project-bootstrap status, preview, and apply flows against current managed projects and make sure generated instructions match the 1.0 native tracker workflow.

HOW TO VERIFY
At least one representative managed project has status and preview checked, and any drift is either fixed or filed as follow-up work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 14:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 14:09
---
UNDERSTANDING: Not a duplicate. Searched all tasks for overlap: OOMPAH-42 covers post-release bootstrap smoke checks after v1.0.0 ships; OOMPAH-24/25/47 covered release packaging smoke tests; OOMPAH-26 documented the 1.0 CLI surface (now Merged); OOMPAH-30 validated decomposition boundaries (In Review). None covers pre-release validation of the bootstrap status/preview/apply flows against managed projects. Blockers OOMPAH-26 (Merged) and OOMPAH-30 (In Review, work complete) are resolved. Plan: (1) run 'oompah project-bootstrap status/preview .' on the current repo to validate the CLI works end-to-end, (2) inspect the generated AGENTS.md template to confirm it uses the 1.0 native oompah task workflow (OOMPAH_TASK_AGENT_INSTRUCTIONS), (3) check the bootstrap apply --dry-run path, (4) file follow-up tasks for any drift.
---
author: oompah
created: 2026-06-22 14:12
---
DISCOVERY: Validated bootstrap flows against the oompah managed project (the only locally accessible managed project; trickle and ova are external GitHub repos). Findings: (1) STATUS flow works correctly via 'python3 -m oompah project-bootstrap status .' — reports 3 missing files (docs/README.md, plans/README.md, scripts/githooks/pre-commit), 2 project-owned protected files (Makefile, .gitignore), and AGENTS.md as current. (2) PREVIEW flow works correctly — shows unified diffs for the 3 missing files. (3) APPLY --dry-run flow works correctly — lists files that would be written. (4) AGENTS.md template uses OOMPAH_TASK_AGENT_INSTRUCTIONS (v:2), which is the correct 1.0 native tracker workflow. AGENTS.md in this repo is already current. (5) KEY ISSUE: The installed 'oompah' binary (/home/shedwards/.local/bin/oompah, via 'uv tool install') is an older version that lacks project_bootstrap/ and project_bootstrap_cli.py modules. 'oompah project-bootstrap status .' fails. Only 'python3 -m oompah project-bootstrap' (using the development worktree) works. This means any operator who installed oompah before the project-bootstrap feature was added cannot use the CLI. Plan: (a) apply bootstrap to oompah repo to fix the 3-file drift, (b) file follow-up for the stale installed binary issue.
---
author: oompah
created: 2026-06-22 14:16
---
IMPLEMENTATION: Bootstrap apply completed for oompah project - applied 3 missing files (docs/README.md, plans/README.md, scripts/githooks/pre-commit). Bootstrap is now all-current. AGENTS.md template confirmed to use OOMPAH_TASK_AGENT_INSTRUCTIONS (v:2) - the 1.0 native tracker workflow. Now adding: (1) test for AGENTS.md template content validation (v:2 marker, 1.0 native workflow content), (2) oompah project-bootstrap --help smoke test to test_installed_cli_smoke.py.
---
author: oompah
created: 2026-06-22 14:19
---
VERIFICATION: All 7118 tests pass (make test). New tests added: (1) test_agents_md_template_uses_1_0_native_tracker_workflow - validates AGENTS.md template uses BEGIN OOMPAH TASK INTEGRATION v:2 marker and 1.0 native workflow content, does not use GitHub Issues tracker; (2) test_apply_agents_md_template_is_current_after_apply - validates end-to-end apply produces 1.0-compliant AGENTS.md and bootstrap status reports it as current; (3) test_oompah_project_bootstrap_help_exits_zero - installed CLI smoke test for project-bootstrap --help showing status/preview/apply subcommands; (4) test_oompah_project_bootstrap_help_does_not_import_server_dependencies - validates CLI-only install works without server extras. All HOW TO VERIFY criteria met: oompah project (representative managed project) has status and preview checked, drift (3 missing files) is fixed, generated AGENTS.md matches 1.0 native tracker workflow.
---
author: oompah
created: 2026-06-22 14:20
---
COMPLETION: Bootstrap flows validated for the oompah managed project (representative project). Delivered: (1) Applied 3 missing bootstrap files: docs/README.md, plans/README.md, scripts/githooks/pre-commit - oompah project now bootstrap-current. (2) Confirmed AGENTS.md uses 1.0 native tracker workflow (OOMPAH TASK INTEGRATION v:2). (3) Added 4 new tests: template content validation, end-to-end apply validation, installed CLI smoke test for project-bootstrap --help, and server-dependency isolation test. (4) Filed OOMPAH-52 for follow-up: installed oompah binary (uv tool install) doesn't include project-bootstrap support and needs reinstall. All 7118 tests pass. HOW TO VERIFY criteria met: oompah managed project has status/preview checked, drift fixed, generated instructions match 1.0 native tracker workflow. Not a duplicate.
---
<!-- COMMENTS:END -->
