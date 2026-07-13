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
updated_at: '2026-07-13T03:21:38.707532Z'
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
author: oompah
created: 2026-07-13 03:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:09
---
Understanding: Investigated for duplicates — OOMPAH-174 is unique. No other task covers adding supported_release_branches to the Project model, persistence, create/update APIs, and project-definition UI. OOMPAH-173 (schema) and OOMPAH-175 (catalog API) are sibling tasks with distinct scopes.

Plan: (1) Find the Project model and add supported_release_branches: list[str] with validation (nonempty names, unique after normalization, not equal to default_branch, matched by project.branches). (2) Update persistence/serialization with legacy default of []. (3) Update project create/update API endpoints. (4) Update the project-definition UI template to render and save the ordered list. (5) Write tests for all of the above.
---
author: oompah
created: 2026-07-13 03:12
---
Discovery: Found all relevant code.

Key files:
- oompah/models.py: Project dataclass (line 234), to_dict() (line ~415), from_dict() (line ~536), return cls() (line ~584)
- oompah/projects.py: ProjectStore.create() (line 725), UPDATABLE_FIELDS (line 925), ProjectStore.update() (line 956)
- oompah/server.py: api_create_project() (line 6310), api_update_project() (line 6455)
- oompah/templates/projects.html: read-only display (~line 286), edit form (~line 398), saveProject() (~line 644)

Validation pattern to follow: provider_whitelist (list[str], unique-normalized, null=[], from_dict defaults empty) and status_label_authorized_logins (unique by lowercase key).

Plan:
1. models.py: add supported_release_branches: list[str] = [], update to_dict/from_dict
2. projects.py: add _validate_supported_release_branches helper, add to UPDATABLE_FIELDS, validate in update() with cross-field check against effective branches/default_branch
3. server.py: parse from create/update request bodies, validate in PATCH handler
4. templates/projects.html: display row, edit textarea, saveProject() inclusion
5. tests/test_project_supported_release_branches.py: full test coverage
---
author: oompah
created: 2026-07-13 03:21
---
Implementation: Added supported_release_branches to Project model, persistence, APIs, and project-definition UI.

Changes:
1. oompah/models.py: Added supported_release_branches: list[str] = [] field to Project dataclass; updated to_dict() (always emits the field), from_dict() (legacy records default to []); updated cls() constructor call.
2. oompah/projects.py: Added _validate_supported_release_branches() helper enforcing nonempty, unique-after-normalisation, exclusion of default_branch, and fnmatch against branches patterns; added 'supported_release_branches' to UPDATABLE_FIELDS; added validation in update() using effective branches/default_branch (cross-field); added field to create() signature with delegation to helper.
3. oompah/server.py: Parsed supported_release_branches from PATCH body (type-check, delegates validation to ProjectStore); parsed in POST body (type-check, passes to create()).
4. oompah/templates/projects.html: Added read-only display row; added edit form input with help text explaining removing does not cancel addendums; read in saveProject() and included in PATCH body.
5. tests/test_project_supported_release_branches.py: Full coverage across model (round-trip, from_dict legacy compat), validator helper (all validation rules), ProjectStore.update() (cross-field validation, persistence), server API (GET/PATCH valid+invalid), template presence.
6. tests/test_projects_crud.py: Added 'supported_release_branches' to test_updatable_fields_are_correct.
---
author: oompah
created: 2026-07-13 03:21
---
Verification: make test — 7523 passed, 28 skipped, 12 warnings (0 failures). All new and existing tests pass.
---
<!-- COMMENTS:END -->
