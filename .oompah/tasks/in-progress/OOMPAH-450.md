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
updated_at: '2026-07-27T21:06:12.659946Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Update docs/project-bootstrap.md to make CLI installation an explicit prerequisite and link to docs/cli-install.md before any project-bootstrap commands. Include installation/verification context sufficient to prevent agents on fresh machines from attempting bootstrap without the oompah executable. Add a regression test that verifies the bootstrap guide retains the install-guide link and prerequisite ordering. Acceptance criteria: the guide links to cli-install.md near the Local CLI instructions, clearly states bootstrap does not install the CLI, and the focused documentation test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

