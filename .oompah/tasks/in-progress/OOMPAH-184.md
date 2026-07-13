---
id: OOMPAH-184
type: task
status: In Progress
priority: 2
title: Document release-addendum workflow and operator migration
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-183
labels: []
assignee: null
created_at: '2026-07-13T02:37:55.470386Z'
updated_at: '2026-07-13T06:39:00.486209Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Read the full plans/release-branch-addendums.md. Update user-facing docs, operator/configuration documentation, project-definition help, API reference, and generated agent guidance to describe the main-first release-addendum workflow: supported release lines, selecting release targets, immediate queueing, per-branch lifecycle, task/epic snapshots, branch inspection, retries, and legacy migration. Remove active instructions that tell users to create or work child backport tasks; retain historical references only when clearly labelled. Use Mermaid for any diagrams. Update documentation tests or add targeted assertions for generated guidance. Acceptance: a junior operator can configure supported lines, approve a merged task for two branches, inspect outcomes, and understand migration without consulting source code.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

