---
id: OOMPAH-31
type: task
status: In Progress
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
updated_at: '2026-06-22T14:09:20.400957Z'
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
<!-- COMMENTS:END -->
