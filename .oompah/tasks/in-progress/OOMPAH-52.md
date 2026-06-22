---
id: OOMPAH-52
type: task
status: In Progress
priority: null
title: Update oompah uv-tool install to include project-bootstrap support
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T14:20:20.212899Z'
updated_at: '2026-06-22T14:47:41.074956Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e966e93c-13b9-410c-bf38-578f33b8cda0
---
## Summary

Validation in OOMPAH-31 found that the oompah binary installed via 'uv tool install git+https://github.com/lesserevil/oompah' (/home/shedwards/.local/bin/oompah) is an older version that lacks project_bootstrap/ and project_bootstrap_cli.py. Running 'oompah project-bootstrap status .' fails with 'unrecognized arguments: status .' because the installed __main__.py does not have the project-bootstrap dispatch block.\n\nThe development version (python3 -m oompah) works correctly.\n\nAny operator who installed oompah before the project-bootstrap feature was added needs to reinstall:\n  uv tool upgrade oompah\n  # or\n  uv tool install --reinstall git+https://github.com/lesserevil/oompah\n\nThis should be called out in the release notes and operator runbook so operators know to reinstall after 1.0 ships.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 14:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 14:30
---
Understanding: This issue reports that operators who installed oompah via 'uv tool install' before the project-bootstrap feature was added will have a stale binary that lacks the project_bootstrap/ module and project-bootstrap CLI dispatch. The fix is for operators to reinstall, and we need to document this in release notes and the operator runbook. My role is Duplicate Investigator — I'll first search for existing tasks covering the same ground before doing any implementation.
---
author: oompah
created: 2026-06-22 14:36
---
Discovery: OOMPAH-52 is NOT a duplicate — it was explicitly filed by the OOMPAH-31 agent as a follow-up after discovering the stale binary issue during validation. No other task covers documenting the reinstall requirement for operators. The work is: (1) add an 'Upgrading from pre-1.0 installs' section to docs/cli-install.md covering the project-bootstrap reinstall requirement, and (2) add a note to the release notes section of docs/cli-release.md. There is no operator runbook doc yet (D2 from oompah-1.0-release.md), so I'll focus on the install/release docs where an upgrade notice belongs.
---
author: oompah
created: 2026-06-22 14:47
---
Implementation plan: (1) Add 'Upgrading an existing install' section to docs/cli-install.md — explains that pre-project-bootstrap installs need 'uv tool upgrade oompah' or '--reinstall'. (2) Add upgrade notice to scripts/render_cli_release_notes.py so the 1.0 release notes include the reinstall call-out. (3) Add note in docs/cli-release.md that release notes should call out reinstall requirements for major feature additions. (4) Add test in test_cli_release_packaging.py that verifies the upgrade section appears in generated release notes.
---
<!-- COMMENTS:END -->
