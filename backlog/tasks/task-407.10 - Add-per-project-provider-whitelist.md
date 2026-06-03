---
id: TASK-407.10
title: Add per-project provider whitelist
status: Backlog
assignee: []
created_date: '2026-06-03 00:15'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No change to global role settings semantics except applying the project whitelist as an additional project-specific filter.
- [ ] #2 Existing projects without a whitelist continue to behave as before after restart and config reload.
- [ ] #3 Run make test before closing the task.
<!-- DOD:END -->
