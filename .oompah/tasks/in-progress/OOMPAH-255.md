---
id: OOMPAH-255
type: task
status: In Progress
priority: null
title: Add per-project state-branch configuration and validation
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-254
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:29:19.457116Z'
updated_at: '2026-07-20T17:06:02.663027Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 42596652-eb76-46d2-83ec-d159c6e1b1d2
oompah.task_costs:
  total_input_tokens: 19
  total_output_tokens: 4656
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 19
      output_tokens: 4656
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 19
    output_tokens: 4656
    cost_usd: 0.0
    recorded_at: '2026-07-20T16:57:54.567782+00:00'
---
## Summary

Scope

Implement the project model, persistence, API, CLI, and UI support for configuring an optional native-tracker state branch. The default must remain backward compatible for existing projects until migration sets the field. New projects will be configured by the separate bootstrap task.

Implementation requirements

- Add a project-level state branch setting with validation for a safe branch name and a documented default convention of oompah/state.
- Expose it consistently in project create/read/update APIs, the project-definition UI, serialization, and any relevant CLI output or flags.
- Maintain legacy behavior when the setting is absent: native task data continues to be read from the current default branch.
- Reject invalid configuration with actionable errors. Never infer a state branch merely because an arbitrary remote branch exists.
- Invalidate relevant tracker and repository caches when this setting changes.

Tests

- Model/serialization tests for absent, valid, and invalid state-branch values.
- API and UI tests for displaying and updating the setting.
- Backward-compatibility test proving an existing project without the field still resolves its tracker from main.
- Cache-invalidation regression test after changing the configured branch.

Acceptance criteria

- Operators can explicitly configure a state branch per managed project.
- Existing projects are behaviorally unchanged until migrated.
- Invalid settings cannot be saved.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:57
---
Focus handoff: duplicate_detector

Outcome: No duplicate found. OOMPAH-255 is a unique subtask within the OOMPAH-253 epic and is not covered by any existing or archived task.

Evidence reviewed:
- Searched .oompah/tasks/ (open, in-progress, done, archived) for: state-branch, state_branch, per-project branch, project model state, branch configuration, branch validation
- All sibling tasks (OOMPAH-256 through OOMPAH-260) are distinct: OOMPAH-256 covers tracker read/write implementation (blocked by 255), OOMPAH-257 covers checkpointing, OOMPAH-258 covers bootstrap, OOMPAH-259 covers migration, OOMPAH-260 covers E2E validation
- OOMPAH-254 (In Progress): is the design/spec task; OOMPAH-255 is the implementation of the project model/API/CLI/UI layer from that spec
- Archived tasks OOMPAH-175, OOMPAH-180, OOMPAH-203, OOMPAH-235, OOMPAH-266 are unrelated (release branches, tracker write recovery, restart suppression)
- plans/state-branch-design.md and docs/state-branch-migration.md were created by OOMPAH-254's agent and are the design inputs for OOMPAH-255
- No prior archived task covers project model field addition, API/UI exposure, or branch-name validation for the state branch

Remaining work (for next focus):
- Add state_branch field to the Project model with validation (safe branch name regex, documented default oompah/state)
- Expose field in project create/read/update APIs (REST + UI)
- Add CLI flag/output for the setting
- Maintain legacy behavior (None → read from default branch)
- Invalidate tracker and repository caches on change
- Tests: model/serialization, API, UI, backward-compat, cache-invalidation
- make test must pass

Recommended next focus: feature (backend implementation of project model field, API, validation, cache invalidation, and tests)
---
author: oompah
created: 2026-07-20 16:57
---
Agent completed successfully in 232s (4675 tokens)
---
author: oompah
created: 2026-07-20 16:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 39, Tool calls: 27
- Tokens: 19 in / 4.7K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 52s
- Log: OOMPAH-255__20260720T165418Z.jsonl
---
author: oompah
created: 2026-07-20 16:58
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 17:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 17:05
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-20 17:06
---
Understanding: As Test Engineer, my role is to write comprehensive tests for the per-project state-branch configuration feature. I'll start by exploring what implementation exists on the branch, then write tests covering: (1) model/serialization tests for absent, valid, and invalid state-branch values; (2) API tests for create/read/update; (3) UI tests; (4) backward-compat test proving existing projects without the field read from main; (5) cache-invalidation regression tests. Starting with codebase exploration.
---
<!-- COMMENTS:END -->
