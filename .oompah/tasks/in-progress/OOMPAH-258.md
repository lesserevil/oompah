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
labels: []
assignee: null
created_at: '2026-07-20T16:29:48.958577Z'
updated_at: '2026-07-20T20:14:25.409027Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5e1f7dca-7ddf-4a2b-abdc-0626cd792ce7
oompah.task_costs:
  total_input_tokens: 104981
  total_output_tokens: 576
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 104981
      output_tokens: 576
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 104981
    output_tokens: 576
    cost_usd: 0.0
    recorded_at: '2026-07-20T20:13:54.345108+00:00'
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
<!-- COMMENTS:END -->
