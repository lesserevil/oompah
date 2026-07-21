---
id: OOMPAH-299
type: task
status: In Progress
priority: 2
title: Add repository-map configuration, bootstrap defaults, and operator documentation
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-297
labels: []
assignee: null
created_at: '2026-07-21T15:14:09.575764Z'
updated_at: '2026-07-21T23:00:42.916160Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 02f9bb7f-9a10-4200-8027-c995cdfc72ba
---
## Summary

Add environment-backed configuration for repository maps: enable flag, token budget, supported-language policy, maximum file size, generation timeout, and retained-artifact count. Add safe defaults and document every setting in .env.example. Update project-bootstrap so new managed projects receive the required state-branch capability/configuration without changing application source branches. Write user/operator documentation covering activation, freshness, diagnostics, privacy/trust boundaries, and how to disable or rebuild a map.\n\nDo not add configuration values to WORKFLOW.md.\n\nTests:\n- Configuration parsing tests cover defaults, valid overrides, invalid values, and disabled mode.\n- Bootstrap tests verify generated project configuration enables the feature only under the documented conditions.\n- Documentation checks or fixtures verify every exposed environment setting is represented in .env.example.\n\nAcceptance criteria:\n- Operators can enable, tune, disable, and diagnose the feature solely through documented configuration.\n- Newly bootstrapped projects work with the Git-backed state model.\n- No new daemon, database, or externally hosted service is required.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:00
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
