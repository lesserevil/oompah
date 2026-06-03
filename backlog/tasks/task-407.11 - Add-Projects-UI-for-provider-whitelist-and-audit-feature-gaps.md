---
id: TASK-407.11
title: Add Projects UI for provider whitelist and audit feature gaps
status: Open
assignee: []
created_date: '2026-06-03 04:53'
labels:
  - bug
  - frontend
  - provider
dependencies:
  - TASK-407.10
parent_task_id: TASK-407
priority: high
ordinal: 65000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-407.10 implemented the project provider whitelist backend/API/orchestrator behavior, but the Projects page does not currently expose any UI for viewing or editing provider_whitelist. Add the missing UI and audit the feature end to end so operators can configure project-level provider restrictions without using curl.

Context to inspect first:
- TASK-407.10 and tests/test_project_provider_whitelist.py describe the intended behavior.
- oompah/models.py Project.provider_whitelist stores provider names, not provider IDs.
- oompah/server.py PATCH /api/v1/projects/{id} accepts provider_whitelist as a list of strings or null.
- oompah/templates/projects.html renders /projects-manage and currently has no provider whitelist control.
- oompah/templates/providers.html and /api/v1/providers show how provider names are represented.

Implementation guidance for a junior developer:
1. Load provider records on /projects-manage in addition to projects, using /api/v1/providers. Handle fetch failures gracefully like the page already does for projects.
2. On each project card, show a Provider Whitelist row. If the list is empty, show something like All providers. If non-empty, show the whitelisted provider names.
3. In the edit form for each project, add a compact multi-select control for provider names. Checkboxes are acceptable and easiest to reason about. The control must use provider names as values because dispatch filtering matches names.
4. Include all currently configured providers as options. Preserve unknown whitelist names that are already stored on the project, so old config values do not silently disappear just because the provider is temporarily missing from the provider store.
5. Save provider_whitelist in the existing PATCH body from saveProject(). Empty selection must send [] so the whitelist is cleared and all providers are allowed.
6. Consider whether the Add Project form should also allow setting an initial whitelist. If not implemented, document why edit-after-create is acceptable and make sure the API still behaves correctly.
7. Audit the feature for other misses: project list display, edit form, save payload, GET/PATCH API behavior, dispatch filtering, all-filtered warning, and tests. File a separate follow-up task for any miss that is too large to fix inside this task.
8. Add tests for the Projects UI template/JavaScript so this gap cannot recur. Existing template tests use source inspection; follow nearby patterns. At minimum test that provider_whitelist is displayed, edit controls exist, saveProject reads selected provider names, and the PATCH body includes provider_whitelist.
9. Run make test before closing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Projects page shows each project provider whitelist, using All providers when the whitelist is empty.
- [ ] #2 The project edit form lets an operator choose zero, one, or many provider names for provider_whitelist.
- [ ] #3 Saving a project sends provider_whitelist in the PATCH request as a list of provider names; an empty selection sends [] to clear the whitelist.
- [ ] #4 Existing unknown whitelist names are preserved and visible instead of being silently dropped when providers are loaded.
- [ ] #5 The implementation audits the rest of the feature and either fixes or files follow-up tasks for any remaining provider-whitelist misses.
- [ ] #6 Tests cover display, edit controls, save payload, empty whitelist clearing, and unknown-name preservation.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No backend whitelist semantics change unless required by the audit.
- [ ] #2 make test passes.
<!-- DOD:END -->
