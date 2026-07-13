---
id: OOMPAH-174
type: task
status: In Progress
priority: 1
title: Add supported release lines to project configuration
parent: OOMPAH-172
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:35:40.880021Z'
updated_at: '2026-07-13T03:08:53.047573Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9f743cae-ff50-464e-965f-66d0bfd90b87
---
## Summary

Read section 5 of plans/release-branch-addendums.md. Add ordered supported_release_branches to Project, persistence, project create/update APIs, and the project-definition UI. It is a list of exact branch names, separate from Project.branches. Validate nonempty names, uniqueness after normalization, exclusion of default_branch, and matching against Project.branches. Removing a supported line must not delete historic addendums. Tests: legacy project records default to an empty list; create/update/serialization; invalid values return validation errors; project UI renders and saves the ordered list. Acceptance: operators can configure supported release lines without any release-addendum feature being enabled.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 03:08
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
