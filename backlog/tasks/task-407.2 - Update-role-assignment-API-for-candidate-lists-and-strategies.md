---
id: TASK-407.2
title: Update role assignment API for candidate lists and strategies
status: In Progress
assignee: []
created_date: 2026-06-01 21:43
updated_date: 2026-06-02 14:57
labels:
- feature
dependencies:
- TASK-407.1
modified_files:
- oompah/server.py
- tests/test_providers_role_matrix.py
parent_task_id: TASK-407
priority: high
ordinal: 32000
oompah.task_costs:
  total_input_tokens: 51
  total_output_tokens: 33118
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 51
      output_tokens: 33118
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 51
    output_tokens: 33118
    cost_usd: 0.0
    recorded_at: '2026-06-02T14:52:09.173948+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Change the /api/v1/roles API from one provider/model per role to one strategy plus an ordered candidate list per role.

Current state to inspect first:
- oompah/server.py uses ROLE_MATRIX_KEYS for fast, standard, deep, and default.
- GET /api/v1/roles serializes provider_id and model for each role.
- PUT /api/v1/roles expects provider_id and model for each role and updates all roles atomically.

Required behavior:
- GET returns each role with strategy and candidates.
- PUT accepts strategy and candidates for every role.
- The update must stay atomic: either all roles are valid and saved, or none are changed.
- Keep enough compatibility for existing UI/tests during the transition, such as provider_id/model fields mirroring the first candidate if needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /api/v1/roles returns strategy and candidates for fast, standard, deep, and default.
- [x] #2 PUT /api/v1/roles accepts multi-candidate role bodies and persists them.
- [x] #3 PUT rejects an invalid candidate and leaves all existing roles unchanged.
- [x] #4 PUT rejects an invalid strategy.
- [x] #5 Provider and model status information is available for each candidate so the UI can show whether a candidate is usable.
- [x] #6 Existing single-candidate behavior is either supported temporarily or explicitly updated in tests and UI in the same implementation series.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read the current role API serializer and tests before editing.
2. Extend the role row serializer to include strategy, candidates, and per-candidate provider/model status details.
3. Update PUT validation to require valid strategy and at least one candidate for each role.
4. Reuse RoleStore validation instead of duplicating model/provider rules in server.py.
5. Preserve rollback behavior by snapshotting RoleStore before applying updates.
6. Add tests for valid multi-candidate updates, invalid candidate rollback, old single-candidate request compatibility if retained, and safe GET output.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 API tests cover success, validation failure, and rollback behavior.
- [x] #2 No direct edits to backlog task files are needed for this implementation.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 14:41

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 14:41

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 14:52

Agent completed successfully in 665s (33169 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-02 14:52

Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 89, Tool calls: 54
- Tokens: 51 in / 33.1K out [33.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 5s
- Log: TASK-407.2__20260602T144113Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-02 14:57

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-02 14:57

UNDERSTANDING (Duplicate Investigator): Searched for similar tasks using 'roles API', 'candidate', 'strategy' keywords. TASK-407.2 is NOT a duplicate — it is a unique subtask in the TASK-407 epic covering the API layer (server.py), distinct from TASK-407.1 (data model/roles.py). The previous Test Engineer run (Run #1) already implemented all required changes: extended _serialize_role_row with strategy/candidates, updated api_put_roles for both old/new format, added full atomicity via snapshot/restore. 51 tests added in tests/test_roles_api.py covering all acceptance criteria. No duplicate found; proceeding to verify completion.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-02 14:57

DISCOVERY: Run #1 commit a73af97 implemented all required changes in oompah/server.py and tests/test_roles_api.py. Key changes: _resolve_candidate_status helper, _serialize_role_row extended with strategy/candidates/per-candidate status, api_put_roles updated for both legacy (provider_id/model) and new (strategy/candidates) formats, VALID_STRATEGIES constant, full atomicity via snapshot/restore. All 51 new API tests pass, 46 existing role matrix tests pass, 177 total tests across 3 test files pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-02 14:57

VERIFICATION: python -m pytest tests/test_roles_api.py tests/test_providers_role_matrix.py tests/test_role_store.py - 177 passed in 0.62s. All 6 acceptance criteria met: GET returns strategy+candidates for all 4 roles, PUT accepts multi-candidate bodies and persists, PUT atomically rejects bad candidates/strategies, per-candidate status in GET response, legacy format backward-compat maintained. Branch pushed to origin/TASK-407.2.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-02 14:57

COMPLETION: TASK-407.2 is complete. The /api/v1/roles GET and PUT endpoints now support strategy and ordered candidate lists per role. The implementation in oompah/server.py provides: (1) GET returns strategy, candidates with per-candidate status, and backward-compat provider_id/model fields mirroring first candidate; (2) PUT accepts both legacy format (provider_id/model promoted to single-candidate priority) and new format (strategy + candidates list); (3) atomic rollback if any role validation fails; (4) 51 comprehensive API tests. Not a duplicate — unique sibling task in the TASK-407 epic.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
