---
id: OOMPAH-258
type: task
status: In Progress
priority: null
title: Configure Git state branches in project-bootstrap and operator documentation
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-256
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:29:48.958577Z'
updated_at: '2026-07-20T20:16:47.086788Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5e1f7dca-7ddf-4a2b-abdc-0626cd792ce7
oompah.task_costs:
  total_input_tokens: 104999
  total_output_tokens: 4969
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 104999
      output_tokens: 4969
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 104981
    output_tokens: 576
    cost_usd: 0.0
    recorded_at: '2026-07-20T20:13:54.345108+00:00'
  - profile: standard
    model: unknown
    input_tokens: 18
    output_tokens: 4393
    cost_usd: 0.0
    recorded_at: '2026-07-20T20:16:43.995811+00:00'
---
## Summary

Scope

Update project-bootstrap so every newly bootstrapped native-tracker project receives a dedicated Oompah state branch and corresponding project configuration. Update user-facing documentation for setup, permissions, verification, troubleshooting, and recovery.

Implementation requirements

- Extend project-bootstrap templates/scripts to create or initialize the configured state branch with the canonical task-tree layout and set the project state-branch configuration.
- Bootstrap must be idempotent: rerunning it recognizes a valid existing state branch and never overwrites task data.
- Document required repository permissions, branch protection considerations, how to verify state-branch tracking, checkpoint timing configuration in .env, and how to troubleshoot failed state pushes.
- Document the distinction between code branches and the Oompah state branch, including why state commits do not appear in code or release histories.
- Do not add an external service or database dependency.

Tests

- End-to-end bootstrap fixture starts with an empty remote repository and verifies the state branch, project configuration, and initial task layout are created.
- Idempotency test reruns bootstrap with existing state data and proves no data is lost or duplicated.
- Template/documentation test verifies the generated configuration contains the state-branch setting.

Acceptance criteria

- A newly bootstrapped managed project is state-branch enabled by default.
- Bootstrap is safe to rerun.
- docs/ contains complete operator setup and recovery instructions.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 20:13
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 20:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 20:13
---
Agent completed successfully in 32s (105557 tokens)
---
author: oompah
created: 2026-07-20 20:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 105.0K in / 576 out [105.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 32s
- Log: OOMPAH-258__20260720T201329Z.jsonl
---
author: oompah
created: 2026-07-20 20:14
---
Agent completed without closing this issue (32s (105557 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 20:14
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 20:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 20:16
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-258 is a unique, non-duplicated task.

**Evidence reviewed:**
- Searched .oompah/tasks/ (all states: open, in-progress, done, archived) for keywords: bootstrap, project-bootstrap, state branch, state_branch, idempotent, operator documentation
- Reviewed the full OOMPAH-253 epic family: OOMPAH-254 (design doc), OOMPAH-255 (project model fields), OOMPAH-256 (tracker read/write routing), OOMPAH-257 (checkpoint coalescing), OOMPAH-259 (existing project migration), OOMPAH-260 (E2E validation)
- Checked archived bootstrap tasks: OOMPAH-24 (release smoke tests), OOMPAH-31 (bootstrap flow validation) — both archived, neither covers state-branch initialization

**Closest reviewed tasks (all confirmed distinct):**
- OOMPAH-256 (Done): tracker read/write routing — distinct: only the tracker, not the bootstrap templates
- OOMPAH-259 (Open): migration for EXISTING projects — distinct: migration path, not bootstrap for NEW projects
- OOMPAH-254 (Done): design document — distinct: plans/ design doc, not implementation
- OOMPAH-260 (Open, blocked by 258): E2E validation — depends on this task being completed first

**Remaining work:** Implementation of:
1. Extend project-bootstrap templates/scripts to create/initialize the state branch with canonical task-tree layout and set state-branch configuration
2. Idempotency guard (rerun recognizes valid existing state branch, never overwrites task data)
3. docs/ operator guide: permissions, branch protection, verification, checkpoint tuning (.env), troubleshooting failed state pushes, code branch vs state branch distinction
4. Tests: E2E bootstrap fixture (empty remote → state branch + config + task layout), idempotency test, template/config verification test

**Recommended next focus:** feature (backend + docs implementation)
---
author: oompah
created: 2026-07-20 20:16
---
Agent completed successfully in 137s (4411 tokens)
---
<!-- COMMENTS:END -->
