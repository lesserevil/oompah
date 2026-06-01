---
id: TASK-407.7
title: Update Providers page role matrix to edit candidate lists
status: To Do
assignee: []
created_date: '2026-06-01 21:44'
labels:
  - feature
  - 'needs:frontend'
  - 'needs:test'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Frontend tests or server template tests cover the new save/load shape.
- [ ] #2 Manual browser check confirms no overlapping text or broken controls on desktop width.
<!-- DOD:END -->
