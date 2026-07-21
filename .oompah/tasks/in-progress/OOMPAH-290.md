---
id: OOMPAH-290
type: task
status: In Progress
priority: 1
title: Enforce server-side authority boundaries for agent actions influenced by external
  intake
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-287
labels: []
assignee: null
created_at: '2026-07-21T14:51:56.727670Z'
updated_at: '2026-07-21T22:38:57.532989Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2798d0fc-83d1-46e0-833a-89b40fb242fd
---
## Summary

Audit tool and API paths reachable by agents working on externally sourced tasks. Add centralized checks requiring trusted server-side state for status transitions, task creation/decomposition, source changes, provider/project configuration, credential access, Git pushes, GitHub comments/labels, and release delivery actions. Never authorize an action solely because external issue text requests it. Emit an auditable denial reason while preserving normal approved workflows.

Dependency: Add provenance metadata for external content entering Oompah.

Tests: integration tests using externally sourced tasks that request protected actions; assert denial without trusted approval and success through the approved path.

Acceptance criteria: external prompt injection cannot grant capabilities or bypass transition or authorization gates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:38
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
