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
updated_at: '2026-07-27T21:07:50.294169Z'
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
<!-- COMMENTS:END -->
