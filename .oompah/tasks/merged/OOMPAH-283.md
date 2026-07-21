---
id: OOMPAH-283
type: task
status: Merged
priority: null
title: Expose active state-branch identity and checkpoint health in project APIs
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T22:54:50.695408Z'
updated_at: '2026-07-21T04:04:48.247241Z'
work_branch: OOMPAH-283
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/461
review_number: '461'
merged_at: null
oompah.agent_run_id: ae956562-0967-4190-9762-22eca0ea7d39
oompah.task_costs:
  total_input_tokens: 85573
  total_output_tokens: 13086
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 85573
      output_tokens: 13086
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 85427
    output_tokens: 683
    cost_usd: 0.0
    recorded_at: '2026-07-20T23:09:41.004707+00:00'
  - profile: default
    model: unknown
    input_tokens: 31
    output_tokens: 9421
    cost_usd: 0.0
    recorded_at: '2026-07-20T23:23:48.887655+00:00'
  - profile: standard
    model: unknown
    input_tokens: 115
    output_tokens: 2982
    cost_usd: 0.0
    recorded_at: '2026-07-20T23:40:59.423926+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/461
oompah.review_number: '461'
oompah.work_branch: OOMPAH-283
oompah.target_branch: main
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
author: oompah
created: 2026-07-20 23:23
---
Agent completed successfully in 568s (9452 tokens)
---
author: oompah
created: 2026-07-20 23:23
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 61, Tool calls: 44
- Tokens: 31 in / 9.4K out [9.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 28s
- Log: OOMPAH-283__20260720T231422Z.jsonl
---
author: oompah
created: 2026-07-20 23:23
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 23:23
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 23:23
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-20 23:31
---
Understanding: I am the Test Engineer for OOMPAH-283. The feature agent did not land commits. I will implement both the feature fix and the tests.

Root cause confirmed:
1. models.py to_dict() emits state_branch_shadow_write only when True and state_branch_migration_stage only when non-empty — so Stage B (shadow_write=False, enabled=True) returns null for both in GET /api/v1/projects
2. state_branch_name property is never emitted by to_dict() at all
3. CheckpointQueue._last_push_at is only set by flush() — bootstrap commits via subprocess are invisible, causing 'Last push: never'

Plan:
A. models.py: when state_branch_enabled=True, always emit state_branch_name, state_branch_shadow_write, state_branch_migration_stage
B. oompah_md_tracker.py: get_checkpoint_observability() falls back to git log -1 --format=%aI when _last_push_at is None
C. Tests: Stage B serialization assertions (to_dict + HTTP GET), observability bootstrap-fallback test
---
author: oompah
created: 2026-07-20 23:37
---
Implementation complete. Changes pushed to branch OOMPAH-283.

**Feature fixes:**

1. oompah/models.py (to_dict): When state_branch_enabled=True, always emit state_branch_name (computed), state_branch_shadow_write (boolean, even False), and state_branch_migration_stage (string, even empty). Legacy projects (enabled=False) retain compact/omit behavior for backward compatibility.

2. oompah/oompah_md_tracker.py (get_checkpoint_observability + new _get_state_branch_last_commit_at): When CheckpointQueue._last_push_at is None (e.g. right after bootstrap before any flush), falls back to 'git log -1 --format=%aI <state_branch>' to report the actual bootstrap commit time.

**Tests added:**

tests/test_state_branch_project_config.py — TestStageBApiContract (16 tests):
- to_dict/to_safe_dict: Stage B returns state_branch_name='oompah/state/proj-stageb', shadow_write=False, migration_stage='B'
- Stage A: shadow_write=True, migration_stage='A', state_branch_name present
- Legacy: state_branch_name, shadow_write, migration_stage all absent
- HTTP GET /api/v1/projects/{id}: Stage B returns non-null branch name and explicit false shadow_write
- HTTP GET /api/v1/projects: list includes state_branch_name for Stage B

tests/test_checkpoint_coalescing.py — TestCheckpointObservability (+3 tests, 1 updated):
- Updated existing test: last_push_at now reflects bootstrap commit (not None)
- New: last_push_at is None when branch has no commits (edge case)
- New: bootstrap-commit fallback exactly reproduces and verifies the 'Last push: never' fix

All 9790 tests pass.
---
author: oompah
created: 2026-07-20 23:40
---
Implemented OOMPAH-253 API contract: to_dict() now always emits state_branch_name, shadow_write (even False), migration_stage for state-branch-enabled projects; get_checkpoint_observability() falls back to git log for last_push_at after bootstrap. Added 19 new tests covering Stage B API contract and checkpoint bootstrap-commit fallback. All 9790 tests pass.
---
author: oompah
created: 2026-07-20 23:41
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 77
- Tokens: 115 in / 3.0K out [3.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 2s
- Log: OOMPAH-283__20260720T232359Z.jsonl
---
<!-- COMMENTS:END -->
