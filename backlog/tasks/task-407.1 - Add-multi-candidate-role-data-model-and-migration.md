---
id: TASK-407.1
title: Add multi-candidate role data model and migration
status: Backlog
assignee: []
created_date: '2026-06-01 21:43'
updated_date: '2026-06-02 01:07'
labels:
  - feature
  - 'needs:backend'
  - 'needs:test'
dependencies: []
modified_files:
  - oompah/roles.py
  - tests/test_role_store.py
parent_task_id: TASK-407
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the current one provider/model role assignment shape with a role assignment that can hold multiple provider/model candidates and a selection strategy.

Current state to inspect first:
- oompah/roles.py has Role(name, provider_id, model, updated_at).
- RoleStore.set(name, provider_id, model) validates exactly one provider/model.
- .oompah/roles.json may already exist in the old single-candidate shape.

Required behavior:
- A role has strategy, candidates, and updated_at.
- strategy must be either priority or round_robin.
- candidates is an ordered list of provider/model pairs.
- Existing old roles.json files with provider_id and model must load successfully and become one-candidate priority roles.
- Saving roles should write the new schema.
- Do not remove support for reading old data in this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Old roles.json data with provider_id/model loads as one priority candidate.
- [ ] #2 New roles serialize with strategy and candidates.
- [ ] #3 A role with no candidates is rejected.
- [ ] #4 A role with an unknown strategy is rejected.
- [ ] #5 A role candidate with an unknown provider is rejected.
- [ ] #6 A role candidate with an invalid model is rejected, while ACP providers with SDK-managed empty model continue to work.
- [ ] #7 Duplicate provider/model candidates in the same role are rejected.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a RoleCandidate dataclass with provider_id and model fields.
2. Change Role so it stores strategy and candidates instead of only provider_id/model.
3. Keep read compatibility in Role.from_dict for old dictionaries that contain provider_id/model.
4. Update Role.to_dict to write strategy and candidates. Include deprecated provider_id/model only if needed by current API compatibility tests; document that they mirror the first candidate.
5. Replace or overload RoleStore.set so callers can save a full candidate list and strategy.
6. Add validation helpers that check provider existence, model validity, empty ACP-model behavior, non-empty candidate lists, valid strategies, and duplicate candidates.
7. Update tests/test_role_store.py for new and migrated formats.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Discovery: oompah/roles.py has Role(name, provider_id, model, updated_at) and RoleStore.set(name, provider_id, model). server.py accesses role.provider_id and role.model directly in _resolve_role_status and _serialize_role_row, so those need to remain accessible as backward-compat properties. test_providers_role_matrix.py also instantiates Role() directly (bypassing validation) for two tests - those needed updating too. Implementation: Added Candidate dataclass with provider_id+model+to_dict/from_dict. Updated Role to use strategy+candidates+updated_at with provider_id/model as compat properties returning first candidate. from_dict handles both old (provider_id/model at top level) and new (strategy+candidates) formats. set() now delegates to set_candidates(). Added set_candidates(name, strategy, candidates) for multi-candidate. Added _validate_multi() checking strategy, empty candidates, and duplicates. All 3605 tests pass.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 RoleStore unit tests cover old schema migration and new schema validation.
- [ ] #2 No beads or bd task tracking is introduced.
<!-- DOD:END -->
