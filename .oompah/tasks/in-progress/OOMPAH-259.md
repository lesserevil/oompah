---
id: OOMPAH-259
type: task
status: In Progress
priority: null
title: Implement resumable migration of existing projects to Git state branches
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-256
- OOMPAH-257
labels: []
assignee: null
created_at: '2026-07-20T16:30:00.848090Z'
updated_at: '2026-07-20T20:35:41.359651Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 50413210-d1de-417b-9ec6-76897ff71c4f
oompah.task_costs:
  total_input_tokens: 90816
  total_output_tokens: 6377
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 90816
      output_tokens: 6377
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 17
    output_tokens: 5769
    cost_usd: 0.0
    recorded_at: '2026-07-20T20:34:00.929515+00:00'
  - profile: default
    model: unknown
    input_tokens: 90799
    output_tokens: 608
    cost_usd: 0.0
    recorded_at: '2026-07-20T20:35:38.287580+00:00'
---
## Summary

Scope

Provide an explicit operator-driven migration path for existing native Markdown managed projects whose .oompah task tree currently lives on main. Migration must preserve task files and history, avoid interfering with code branches, and be safe to resume or roll back.

Implementation requirements

- Add a supported migration command or UI action that performs preflight validation, creates or validates the target state branch, copies the canonical .oompah task tree, commits/pushes it, verifies the remote result, and only then enables the project state-branch configuration.
- Never delete .oompah history from main automatically. The initial migration must retain main history for rollback and auditability; document optional later cleanup as a separate, explicit operator decision.
- Make migration idempotent and resumable after interruption. Record enough Git-backed migration metadata to detect completed steps without a separate database.
- Provide a rollback command or documented operation that restores legacy configuration when state-branch validation fails, without overwriting either branch.
- Block or clearly serialize concurrent tracker writes during the cutover and surface progress/errors to the operator.

Tests

- End-to-end fixture migrates a project with task files, comments, dependencies, merged tasks, and active code branches; verify all tracker data remains readable after cutover.
- Interrupted migration tests at each stage prove retry is safe and does not duplicate or lose tasks.
- Rollback test proves legacy main-based tracker access is restored and state-branch data is retained.
- Concurrent-write test proves cutover cannot silently lose a mutation.

Acceptance criteria

- An operator can migrate an existing project without manually editing task files.
- After migration, routine task updates no longer modify main.
- Migration is recoverable, auditable, and documented.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 20:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 20:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 20:31
---
Understanding: I am the Duplicate Investigator agent for OOMPAH-259. My role is to determine whether this issue (resumable migration of existing projects to Git state branches) is a duplicate of any existing task before any implementation begins. I will search for similar tasks covering: migration to state branches, git state branch setup, project migration commands, and related topics.
---
author: oompah
created: 2026-07-20 20:33
---
Duplicate screening complete: OOMPAH-259 is NOT a duplicate.

Searched across all .oompah/tasks/ directories (open, in-progress, done, merged, archived) using keywords: migration, migrate, state-branch, state_branch, resumable, cutover, rollback, preflight, migrate-state-branch.

Closest reviewed tasks (none overlap):
- OOMPAH-254 (Done): Created design docs (plans/state-branch-design.md, docs/state-branch-migration.md) with migration stages A/B/C and rollback protocol — design only, not implementation.
- OOMPAH-255 (Done): Added per-project state-branch configuration fields — config schema, not migration command.
- OOMPAH-256 (Done): Made native tracker read/write the configured state branch — runtime plumbing, not migration command.
- OOMPAH-257 (Done): Coalesced mutations into checkpoints — checkpoint coalescing, not migration command.
- OOMPAH-258 (In Progress): Configuring project-bootstrap and operator docs — new-project setup, not existing-project migration.
- OOMPAH-260 (Open): End-to-end validation and readiness guide — explicitly BLOCKED on OOMPAH-259.

OOMPAH-259 is the implementation of the operator-driven `oompah admin migrate-state-branch <project-id>` command specified in plans/state-branch-design.md §6 and §7. The blockers OOMPAH-256 and OOMPAH-257 are both Done, so this task is unblocked and ready for implementation.

Key design inputs: plans/state-branch-design.md (stages A/B/C, rollback protocol, CLI spec, API spec POST /api/v1/projects/{id}/state-branch/migrate), docs/state-branch-migration.md (operator guide).
---
author: oompah
created: 2026-07-20 20:34
---
Agent completed successfully in 174s (5786 tokens)
---
author: oompah
created: 2026-07-20 20:34
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 35, Tool calls: 25
- Tokens: 17 in / 5.8K out [5.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 54s
- Log: OOMPAH-259__20260720T203114Z.jsonl
---
author: oompah
created: 2026-07-20 20:34
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-20 20:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 20:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 20:35
---
Agent completed successfully in 27s (91407 tokens)
---
<!-- COMMENTS:END -->
