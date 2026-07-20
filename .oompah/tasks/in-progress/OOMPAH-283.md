---
id: OOMPAH-283
type: task
status: In Progress
priority: null
title: Expose active state-branch identity and checkpoint health in project APIs
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-20T22:54:50.695408Z'
updated_at: '2026-07-20T23:23:42.449830Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ecd1a707-a567-4da8-865b-14fd53bb4e7e
oompah.task_costs:
  total_input_tokens: 85427
  total_output_tokens: 683
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 85427
      output_tokens: 683
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 85427
    output_tokens: 683
    cost_usd: 0.0
    recorded_at: '2026-07-20T23:09:41.004707+00:00'
---
## Summary

Problem: after a successful Stage B migration, GET /api/v1/projects reports state_branch: null and state_branch_shadow_write: null, while the state-branch status command correctly finds oompah/state/<project-id>. The status command also reports Last push: never immediately after bootstrap despite the branch being pushed.\n\nImplement the OOMPAH-253 API/health contract completely. For state-branch-enabled projects, return the computed branch name, a boolean shadow-write value, migration stage, and accurate last successful push/checkpoint information in project and state endpoints.\n\nTests: add API tests for a Stage B project asserting a non-null branch name and false shadow-write value; add health/status test asserting a pushed bootstrap commit is reflected as the last state commit/push.\n\nAcceptance criteria: dashboard and API consumers can identify the active state branch and its latest checkpoint without deriving branch names themselves; existing legacy projects retain null/disabled behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 23:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 23:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:09
---
Agent completed successfully in 27s (86110 tokens)
---
author: oompah
created: 2026-07-20 23:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 85.4K in / 683 out [86.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 27s
- Log: OOMPAH-283__20260720T230915Z.jsonl
---
author: oompah
created: 2026-07-20 23:09
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-283`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 23:10
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 23:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 23:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 23:23
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-283 is NOT a duplicate of any existing task.

**Evidence reviewed:**
- Searched all .oompah/tasks/ directories (all statuses) for: state_branch, ln_name, state_branch_name, shadow_write, last push, API contract, expose state, branch identity
- Read OOMPAH-253 epic (parent), OOMPAH-255 (model fields), OOMPAH-257 (checkpoint health in /api/v1/state), OOMPAH-259 (migration engine + shadow_write/migration_stage fields), OOMPAH-260 (E2E validation)
- Confirmed current server.py behavior: GET /api/v1/projects and GET /api/v1/projects/{id} both call project.to_safe_dict() → to_dict()

**Root cause confirmed (not covered by any existing task):**
1. state_branch_name is a @property on Project but is NOT emitted by to_dict() — it is absent from GET /api/v1/projects and GET /api/v1/projects/{id} responses
2. state_branch_shadow_write is conditionally serialized (only when True) so at Stage B (shadow_write=False) it's absent from the response, not False
3. state_branch_migration_stage is conditionally serialized (only when non-empty) so at Stage A/B it may not appear
4. Last push 'never' bug: checkpoint observability (get_checkpoint_observability()) apparently doesn't read the bootstrap commit timestamp from git log for the initial state branch push

**Closest reviewed tasks (all distinct):**
- OOMPAH-255 (Merged): Added state_branch model fields — does not expose computed state_branch_name in to_dict()
- OOMPAH-257 (Merged): Checkpoint health in GET /api/v1/state (service-level) — NOT the per-project GET /api/v1/projects endpoint
- OOMPAH-259 (Merged): Migration engine, adds shadow_write/migration_stage fields — serializes shadow_write conditionally only when True

**Key files for implementing agent:**
- oompah/models.py lines 470-592 (state_branch_name property + to_dict())
- oompah/server.py lines 9900-9904 (GET /api/v1/projects) and 10056-10072 (GET /api/v1/projects/{id})
- oompah/checkpoint_queue.py (get_checkpoint_observability / last_push_at tracking)
- tests/test_ln_project_config.py, tests/test_state_branch_migration.py (existing test patterns)

**Remaining work:**
1. Emit state_branch_name in to_dict() always when state_branch_enabled=True (or always with null for disabled)
2. Always emit state_branch_shadow_write (even when False) and state_branch_migration_stage (even when empty)
3. Fix checkpoint last_push_at to reflect the bootstrap commit timestamp on first push
4. Add API tests asserting Stage B project returns non-null branch name and false shadow_write
5. Add health/status test asserting bootstrap commit is reflected as last push

**Recommended next focus:** feature
---
<!-- COMMENTS:END -->
