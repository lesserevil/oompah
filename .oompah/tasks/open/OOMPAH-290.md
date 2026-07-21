---
id: OOMPAH-290
type: task
status: Open
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
updated_at: '2026-07-21T15:45:08.689442Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Audit tool and API paths reachable by agents working on externally sourced tasks. Add centralized checks requiring trusted server-side state for status transitions, task creation/decomposition, source changes, provider/project configuration, credential access, Git pushes, GitHub comments/labels, and release delivery actions. Never authorize an action solely because external issue text requests it. Emit an auditable denial reason while preserving normal approved workflows.

Dependency: Add provenance metadata for external content entering Oompah.

Tests: integration tests using externally sourced tasks that request protected actions; assert denial without trusted approval and success through the approved path.

Acceptance criteria: external prompt injection cannot grant capabilities or bypass transition or authorization gates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

