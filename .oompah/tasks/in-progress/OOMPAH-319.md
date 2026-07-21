---
id: OOMPAH-319
type: task
status: In Progress
priority: 1
title: Add explicit forge configuration and backward-compatible project migration
parent: OOMPAH-318
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T20:33:31.453522Z'
updated_at: '2026-07-21T22:17:26.526252Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ec8495fb-1a43-4caf-839f-394a24ea5830
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Core architecture and interfaces.

Implement explicit project forge configuration. Add forge_kind (github|gitlab) and forge_base_url; infer GitHub defaults for every existing persisted project. Validate forge URL, repo URL, tracker kind, and self-managed GitLab host combinations before save. Generalize behavior around tracker namespace/project while retaining serialized tracker_owner/tracker_repo and accepting existing GitHub-only API fields as aliases.

Do not implement GitLab REST calls, tracker behavior, or UI controls in this task.

Tests:
- Existing project JSON deserializes with unchanged GitHub behavior.
- GitLab.com and nested self-managed GitLab paths validate and normalize correctly.
- Invalid/mismatched forge, URL, and tracker combinations fail with actionable errors.
- Create/update API serialization preserves old clients and emits new fields.

Acceptance criteria:
- All project consumers can determine forge kind and canonical base URL without substring detection.
- Existing GitHub project files and API clients require no migration.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:17
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
