---
id: OOMPAH-450
type: task
status: In Progress
priority: null
title: Link project bootstrap guide to CLI installation instructions
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-27T21:06:07.569431Z'
updated_at: '2026-07-27T21:09:24.043926Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e5e9183e-a914-44f0-b240-510ee775d2d0
---
## Summary

Update docs/project-bootstrap.md to make CLI installation an explicit prerequisite and link to docs/cli-install.md before any project-bootstrap commands. Include installation/verification context sufficient to prevent agents on fresh machines from attempting bootstrap without the oompah executable. Add a regression test that verifies the bootstrap guide retains the install-guide link and prerequisite ordering. Acceptance criteria: the guide links to cli-install.md near the Local CLI instructions, clearly states bootstrap does not install the CLI, and the focused documentation test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-27 21:06
---
Starting implementation. Confirmed docs/project-bootstrap.md currently assumes the oompah executable exists and does not link to docs/cli-install.md. I will add an explicit prerequisite/link before the Local CLI commands and a regression assertion in the existing CLI documentation test suite.
---
author: oompah
created: 2026-07-27 21:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-27 21:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-27 21:08
---
Understanding: I am performing the required duplicate-investigator phase only. I will search existing task records and documentation for prior work covering the project-bootstrap CLI prerequisite/link, inspect plausible task candidates in full, and either archive this task if it is a confirmed duplicate or hand it off without implementation if no duplicate is established.
---
author: oompah
created: 2026-07-27 21:09
---
Discovery: Duplicate screening found no confirmed duplicate. Reviewed OOMPAH-9 (generated managed-project guidance and CLI fallbacks), OOMPAH-31 (bootstrap flow validation), OOMPAH-52 (stale-install upgrade guidance in cli-install/release docs), and OOMPAH-35 (broad onboarding checklist), including their full descriptions and comments. None changes docs/project-bootstrap.md to link cli-install.md as a prerequisite before commands or adds the requested ordering regression. Current evidence: the Local CLI section says the GitHub install includes the bootstrap CLI but has no cli-install.md link and does not explicitly say bootstrap itself does not install the executable.
---
<!-- COMMENTS:END -->
