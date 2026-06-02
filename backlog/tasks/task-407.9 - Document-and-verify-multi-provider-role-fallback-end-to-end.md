---
id: TASK-407.9
title: Document and verify multi-provider role fallback end to end
status: In Progress
assignee: []
created_date: '2026-06-01 21:45'
updated_date: '2026-06-02 18:20'
labels:
  - feature
dependencies:
  - TASK-407.6
  - TASK-407.7
  - TASK-407.8
modified_files:
  - docs
  - plans
parent_task_id: TASK-407
priority: medium
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Finish the multi-provider role assignment feature with documentation, migration notes, and end-to-end verification.

Current state to inspect first:
- User-facing docs belong in docs/.
- Internal design and implementation notes belong in plans/.
- The feature changes operator-facing configuration on the Providers page and internal dispatch behavior.

Required behavior:
- Operators can understand how to configure priority and round-robin role assignments.
- Developers can understand the new role candidate schema and selector state at a high level.
- The implementation is verified with automated tests and a short manual scenario using harmless mocked or configured providers.
- The feature does not regress existing single-candidate projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 User-facing documentation explains how to configure priority and round-robin role assignments.
- [ ] #2 Documentation explains what provider failures cause fallback to the next candidate.
- [ ] #3 Documentation explains that the provider Test button does not create tasks or update round-robin usage.
- [ ] #4 Migration from old single-candidate roles is verified.
- [ ] #5 make test passes before this task is marked Done.
- [ ] #6 Any discovered follow-up work is filed as Backlog tasks under TASK-407.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add or update user-facing docs explaining role candidates, priority strategy, round-robin strategy, failover cases, and the provider Test button.
2. Add or update an internal plan/design note only if the implementation introduces non-obvious selector state or dispatch behavior that maintainers need to understand.
3. Verify migration from old one-provider roles.json to the new candidate schema.
4. Run focused tests while developing and make test before closing.
5. Manually check the Providers page on port 8090: load roles, add candidates, reorder candidates, save, reload, use Test button, and confirm layout remains usable.
6. Capture any follow-up bugs as Backlog tasks with parent TASK-407 if they are discovered.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: This task requires user-facing docs in docs/ for operators on how to configure multi-candidate roles with priority/round-robin, what causes provider failover, and the Test button behavior. Also requires internal design notes in plans/ for developers, end-to-end test coverage verifying migration from legacy single-candidate roles.json and non-regression of single-candidate projects, and make test passing.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Docs or plans are updated in the correct directory.
- [ ] #2 Automated tests and manual verification results are recorded in the final summary.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 17:28

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 17:29

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 17:34

Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 47s
- Log: TASK-407.9__20260602T172915Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-02 17:35

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-02 17:35

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-02 17:42

Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 55s
- Log: TASK-407.9__20260602T173541Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-02 17:42

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-02 17:42

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-02 17:49

Run #3 [attempt=3, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 42s
- Log: TASK-407.9__20260602T174257Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-02 17:49

Retrying (attempt #3, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-02 17:50

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12
author: oompah
created: 2026-06-02 17:56

Run #4 [attempt=4, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 36s
- Log: TASK-407.9__20260602T175021Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 13
author: oompah
created: 2026-06-02 17:57

Retrying (attempt #4, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14
author: oompah
created: 2026-06-02 17:58

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 15
author: oompah
created: 2026-06-02 18:03

Run #5 [attempt=5, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 49s
- Log: TASK-407.9__20260602T175819Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16
author: oompah
created: 2026-06-02 18:06

Retrying (attempt #5, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 17
author: oompah
created: 2026-06-02 18:06

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18
author: oompah
created: 2026-06-02 18:13

Run #6 [attempt=6, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 45s
- Log: TASK-407.9__20260602T180650Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 19
author: oompah
created: 2026-06-02 18:18

Retrying (attempt #6, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
