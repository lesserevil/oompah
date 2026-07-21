---
id: OOMPAH-291
type: task
status: Backlog
priority: 1
title: Add prompt-injection regression suite, observability, and operator guidance
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-288
- OOMPAH-289
labels: []
assignee: null
created_at: '2026-07-21T14:51:57.738049Z'
updated_at: '2026-07-21T14:52:07.632164Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Build end-to-end adversarial fixtures that flow GitHub issue bodies/comments and other inventoried sources through import, approval, prompt rendering, focus selection, agent dispatch, and protected-action checks. Add structured audit events for untrusted-content rendering and denied actions without logging secrets. Document the security model, safe intake configuration, and incident response.

Dependencies: Render untrusted content in explicit prompt data boundaries; Harden focus triage and other model-only decisions against external instructions; Enforce server-side authority boundaries for agent actions influenced by external intake.

Tests: end-to-end suite plus documentation tests; run make test.

Acceptance criteria: a malicious GitHub issue cannot override agent instructions or cause protected side effects, and operators can investigate attempted injection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

