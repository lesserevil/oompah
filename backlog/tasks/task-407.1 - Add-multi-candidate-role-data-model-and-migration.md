---
id: TASK-407.1
title: Add multi-candidate role data model and migration
status: Done
assignee: []
created_date: '2026-06-01 21:43'
updated_date: '2026-06-02 03:35'
labels:
  - feature
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
- [x] #1 Old roles.json data with provider_id/model loads as one priority candidate.
- [x] #2 New roles serialize with strategy and candidates.
- [x] #3 A role with no candidates is rejected.
- [x] #4 A role with an unknown strategy is rejected.
- [x] #5 A role candidate with an unknown provider is rejected.
- [x] #6 A role candidate with an invalid model is rejected, while ACP providers with SDK-managed empty model continue to work.
- [x] #7 Duplicate provider/model candidates in the same role are rejected.
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
Understanding: Replaced single provider/model Role shape with multi-candidate model. Discovery: oompah/roles.py and tests/test_role_store.py were already fully implemented on this branch with Candidate dataclass, Role with strategy+candidates, backward-compat from_dict, set_candidates, and validation. Implementation: All 7 acceptance criteria met. Verification: 80/80 role store tests pass; 3605 total tests pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented multi-candidate role data model in oompah/roles.py: added Candidate dataclass (provider_id, model), updated Role to store strategy (priority|round_robin) and a list of Candidates, added backward-compat in Role.from_dict for old single-candidate JSON format, updated RoleStore with set_candidates() for the full multi-candidate API and _validate_multi() for duplicate/strategy/provider checks. All 7 acceptance criteria verified: 80 role store tests and 3605 total tests pass. Old roles.json with provider_id/model fields load cleanly as 1-candidate priority roles; saves always write the new schema.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 RoleStore unit tests cover old schema migration and new schema validation.
- [x] #2 No beads or bd task tracking is introduced.
<!-- DOD:END -->
