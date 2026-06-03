---
id: TASK-407.10
title: Add per-project provider whitelist
status: Done
assignee: []
created_date: '2026-06-03 00:15'
updated_date: '2026-06-03 04:26'
labels:
  - feature
  - provider
dependencies:
  - TASK-407.1
  - TASK-407.2
  - TASK-407.4
  - TASK-407.5
parent_task_id: TASK-407
priority: medium
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a project-level provider whitelist so operators can restrict which providers oompah may use for a specific managed project. By default, projects have no whitelist and can use any provider that is otherwise allowed by the role assignment settings. When a project whitelist is configured, oompah must only consider role candidates whose provider name is in that whitelist. Example: if project foo whitelists provider bar, then a role assignment candidate using provider bar is eligible for foo, while candidates using claude, codex, or any other provider are not. Multiple provider names may be whitelisted for one project. This is provider-level filtering only; model-level role rules and provider health/failover still apply after the whitelist filter.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Project records support an optional provider whitelist field, persisted through project create/update/load/save round trips.
- [ ] #2 When the whitelist is empty or unset, behavior is unchanged: every provider allowed by role settings remains available to the project.
- [ ] #3 When the whitelist contains one or more provider names, dispatch filters role candidates to only those providers before applying priority or round-robin selection.
- [ ] #4 If all candidates for a required role are filtered out by the project whitelist, oompah does not start an agent and surfaces a clear warning explaining that the project provider whitelist excludes the available role providers.
- [ ] #5 Provider filtering is applied consistently in dispatch, preflight availability checks, and any UI/API surfaces that show role/provider availability for a project.
- [ ] #6 The Projects UI/API allow viewing and editing the whitelist as a list of provider names; more than one provider can be selected.
- [ ] #7 Tests cover default-unset behavior, single-provider whitelist behavior, multi-provider whitelist behavior, all-candidates-filtered behavior, and persistence/API/UI behavior.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented per-project provider whitelist. Added provider_whitelist field to Project model (oompah/models.py) with to_dict/from_dict/round-trip support. Added UPDATABLE_FIELDS entry and validation in ProjectStore (oompah/projects.py). Added _apply_project_provider_whitelist() method to Orchestrator that filters dispatch targets by project whitelist before the preflight loop; all-filtered case surfaces clear error message, does not fall through to CLI. Server PATCH /api/v1/projects/{id} accepts/validates/returns provider_whitelist. 44 new tests in tests/test_project_provider_whitelist.py covering all AC (default-unset, single-provider, multi-provider, all-filtered, persistence, API). Updated UPDATABLE_FIELDS test in test_projects_crud.py. All 738 existing tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No change to global role settings semantics except applying the project whitelist as an additional project-specific filter.
- [ ] #2 Existing projects without a whitelist continue to behave as before after restart and config reload.
- [ ] #3 Run make test before closing the task.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 04:06

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 04:07

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 04:08

UNDERSTANDING: Confirmed NOT a duplicate. Searched for 'provider whitelist', 'project provider', 'provider filter', 'restrict provider project', and 'whitelist' — no other task covers per-project provider whitelisting. TASK-407.10 is a unique subtask of the TASK-407 multi-provider epic. Implementation plan: (1) Add provider_whitelist field to Project model with to_dict/from_dict support, (2) Add to UPDATABLE_FIELDS in ProjectStore and validate in update(), (3) Filter _resolve_dispatch_targets results by whitelist in _run_worker before the candidate loop, (4) Surface clear warning when all targets filtered, (5) Expose field in PATCH /api/v1/projects/{id} API, (6) Tests covering all AC.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 04:15

DISCOVERY: Key code locations confirmed. (1) Project model in oompah/models.py. (2) ProjectStore.UPDATABLE_FIELDS in oompah/projects.py. (3) Orchestrator._run_worker in oompah/orchestrator.py — dispatch targets flow through _resolve_dispatch_targets then new _apply_project_provider_whitelist. (4) Server API PATCH /api/v1/projects/{id} in oompah/server.py. All dependency tasks (407.1/2/4/5) provide DispatchTarget, CandidateSelector, and failover loop that this feature integrates with cleanly.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 04:20

IMPLEMENTATION: Changes made: (1) oompah/models.py — provider_whitelist: list[str] field on Project, in to_dict() and from_dict() with strip/blank-entry handling. (2) oompah/projects.py — 'provider_whitelist' added to UPDATABLE_FIELDS; validation in update(). (3) oompah/orchestrator.py — new _apply_project_provider_whitelist() returns (filtered_targets, was_applied); called in _run_worker after _resolve_dispatch_targets; all-filtered case calls _on_worker_exit with clear error, does NOT fall through to CLI. (4) oompah/server.py — provider_whitelist handled in PATCH /api/v1/projects/{id}. (5) tests/test_project_provider_whitelist.py — 44 new tests covering all ACs. (6) tests/test_projects_crud.py — updated UPDATABLE_FIELDS assertion.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 04:25

VERIFICATION: All 44 new tests pass. Broader test suite (738 tests) passes. No regressions in test_candidate_preflight, test_multi_provider_e2e, test_projects_crud, test_orchestrator_handlers, test_project_pause, or any other related tests.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
