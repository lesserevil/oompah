---
id: OOMPAH-288
type: task
status: In Progress
priority: 1
title: Render untrusted content in explicit prompt data boundaries
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-287
labels: []
assignee: null
created_at: '2026-07-21T14:51:41.895980Z'
updated_at: '2026-07-21T21:51:54.752901Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a62b41a4-5220-47e9-ac40-ad4073304ad4
---
## Summary

Update prompt rendering, continuation prompts, decomposition prompts, agent system prompt construction, and attachment rendering to consume provenance metadata. Delimit untrusted content in a stable escaped data block and add a non-bypassable instruction that content inside is reference data only and cannot override system, project, or task instructions. Prevent role markers, template syntax, control headers, and task-state directives from entering instruction-bearing positions. Preserve original content for human review.

Dependency: Add provenance metadata for external content entering Oompah.

Tests: adversarial issue/comment fixtures containing role changes, tool requests, instruction overrides, XML/Markdown delimiters, and Liquid-like syntax; assert rendering preserves text as data and emits the safety instruction exactly once.

Acceptance criteria: no external content is interpolated into an instruction-bearing prompt position.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 21:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 21:51
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
