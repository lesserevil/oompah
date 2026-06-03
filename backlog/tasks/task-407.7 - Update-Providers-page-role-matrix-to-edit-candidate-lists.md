---
id: TASK-407.7
title: Update Providers page role matrix to edit candidate lists
status: Done
assignee: []
created_date: '2026-06-01 21:44'
updated_date: '2026-06-03 02:33'
labels:
  - feature
dependencies:
  - TASK-407.2
modified_files:
  - oompah/templates/providers.html
  - tests/test_providers_role_matrix.py
parent_task_id: TASK-407
priority: high
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update the Providers page role matrix so each role can be configured with multiple provider/model candidates and a strategy.

Current state to inspect first:
- oompah/templates/providers.html has ROLE_MATRIX_ROLES and roleMatrixState.
- Each role row currently renders one provider select and one model select.
- saveRoleMatrix sends provider_id and model for each role.

Required behavior:
- Each role row shows a strategy control with Priority and Round-robin options.
- Each role row shows an ordered list of candidate rows.
- Each candidate row has provider select, model select, status/billing details, and remove control.
- Users can add a candidate to a role.
- Users can move candidates up and down so priority order is clear.
- Saving sends strategy plus candidates to /api/v1/roles.
- Loading reads strategy plus candidates from /api/v1/roles.
- Keep the UI compact and consistent with the existing Providers page rather than turning it into a marketing-style layout.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Providers page can display more than one candidate for a role.
- [ ] #2 The user can switch a role between Priority and Round-robin.
- [ ] #3 The user can add, remove, and reorder candidates.
- [ ] #4 Saving sends strategy and ordered candidates for every role.
- [ ] #5 Loading existing one-candidate roles still renders a usable single candidate row.
- [ ] #6 Candidate status and billing information is shown per candidate.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read the current providers.html role matrix code before editing.
2. Update roleMatrixState so each role has strategy and candidates.
3. Render a small segmented strategy control for each role.
4. Render candidate rows with provider/model selectors, status text, billing text, up/down buttons, and remove buttons.
5. Add an Add candidate button per role.
6. Update change handlers so selecting a provider clears or validates the model for only that candidate row.
7. Update saveRoleMatrix to send the new API shape.
8. Update dirty-state handling and reload behavior.
9. Update any frontend-oriented tests or HTML assertions that currently assume one provider/model select per role.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Discovery: Found key sections in providers.html. Current role matrix is a simple 6-column table. API (TASK-407.2) already returns strategy+candidates. Implementing: CSS for new layout, updated state structure, new rendering with role-header-rows and candidate-rows, helper functions, updated save format, updated tests.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Rebase complete. The feature commit (providers.html role matrix with multi-candidate support) was already cherry-picked into main via PR #201. Git auto-detected this during rebase and skipped the duplicate commit. The only branch-specific commit remaining is the backlog status update. Force-pushed after clean rebase. All 89 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Frontend tests or server template tests cover the new save/load shape.
- [ ] #2 Manual browser check confirms no overlapping text or broken controls on desktop width.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 15:50

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 15:50

Focus: Frontend Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 16:14

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 02:22

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 02:22

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 02:22

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 02:22

Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
- Log: TASK-407.7__20260603T022219Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 02:22

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-03 02:22

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-03 02:22

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-03 02:23

Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
- Log: TASK-407.7__20260603T022257Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12
author: oompah
created: 2026-06-03 02:23

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
