---
id: OOMPAH-430
type: task
status: In Progress
priority: null
title: Provide focus agents a supported tracker-handoff mutation path
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T22:26:45.549947Z'
updated_at: '2026-07-23T22:35:24.947841Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 07e1562f-a79b-4a1f-b5fd-6c5bbec9d3ee
---
## Summary

Focus handlers must record completion labels and a handoff comment before the scheduler chooses the next focus. EXOCOMP-55 showed that the agent environment lacked task-mutation MCP tools while project instructions prohibited loopback CLI use; duplicate screening therefore completed but could not persist its handoff and was retried repeatedly. Provide an approved mutation interface or change the focus protocol so agents can reliably add completion labels and comments. Add regression coverage for a no-commit focus completion advancing to the requested implementation focus. Acceptance: duplicate detection that finds no duplicate records its completion and handoff exactly once, and the next run begins feature work rather than another duplicate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 22:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 22:35
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
