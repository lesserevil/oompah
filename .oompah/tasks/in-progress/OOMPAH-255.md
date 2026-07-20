---
id: OOMPAH-255
type: task
status: In Progress
priority: null
title: Add per-project state-branch configuration and validation
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-254
labels: []
assignee: null
created_at: '2026-07-20T16:29:19.457116Z'
updated_at: '2026-07-20T16:54:15.347976Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8bdbd08c-1a30-4ab3-9ef8-e5f4e68c33cd
---
## Summary

Scope

Implement the project model, persistence, API, CLI, and UI support for configuring an optional native-tracker state branch. The default must remain backward compatible for existing projects until migration sets the field. New projects will be configured by the separate bootstrap task.

Implementation requirements

- Add a project-level state branch setting with validation for a safe branch name and a documented default convention of oompah/state.
- Expose it consistently in project create/read/update APIs, the project-definition UI, serialization, and any relevant CLI output or flags.
- Maintain legacy behavior when the setting is absent: native task data continues to be read from the current default branch.
- Reject invalid configuration with actionable errors. Never infer a state branch merely because an arbitrary remote branch exists.
- Invalidate relevant tracker and repository caches when this setting changes.

Tests

- Model/serialization tests for absent, valid, and invalid state-branch values.
- API and UI tests for displaying and updating the setting.
- Backward-compatibility test proving an existing project without the field still resolves its tracker from main.
- Cache-invalidation regression test after changing the configured branch.

Acceptance criteria

- Operators can explicitly configure a state branch per managed project.
- Existing projects are behaviorally unchanged until migrated.
- Invalid settings cannot be saved.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:54
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
