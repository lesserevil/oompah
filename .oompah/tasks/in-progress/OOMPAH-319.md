---
id: OOMPAH-319
type: task
status: In Progress
priority: 1
title: Add explicit forge configuration and backward-compatible project migration
parent: OOMPAH-318
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-21T20:33:31.453522Z'
updated_at: '2026-07-21T22:18:22.049160Z'
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
author: oompah
created: 2026-07-21 22:17
---
Understanding: I am performing the required duplicate screening only. I will compare this explicit forge configuration/migration scope against existing forge and GitLab tasks, read any candidate task details and comments, then either archive this task as a confirmed duplicate or leave a duplicate-detector handoff for implementation.
---
author: oompah
created: 2026-07-21 22:18
---
Discovery: Duplicate screening found no confirmed duplicate. OOMPAH-318 is the parent epic; OOMPAH-327 covers later UI/API/ACP exposure and health controls, OOMPAH-329 covers final cross-forge acceptance, and OOMPAH-320 covers provider contracts. None implements this task's model/persistence validation and compatibility migration scope. Git history contains only the parity plan, not an implementation of forge_kind/forge_base_url.
---
author: oompah
created: 2026-07-21 22:18
---
Focus handoff: duplicate_detector\n\n1. Outcome: no duplicate confirmed; OOMPAH-319 remains the distinct foundation child for explicit forge configuration and persisted-project migration.\n2. Evidence: searched , docs, plans, README.md, and WORKFLOW.md for forge/GitLab terms; reviewed OOMPAH-318, OOMPAH-320, OOMPAH-327, and OOMPAH-329 with ; inspected all git history messages matching forge/GitLab.\n3. Remaining work/risks: implement and test ProjectStore/model/API compatibility, including validation and canonical normalization; coordinate the serialization boundary so OOMPAH-327 can layer UI controls without duplicating model work.\n4. Recommended next focus: feature (backend configuration/model implementation).
---
<!-- COMMENTS:END -->
