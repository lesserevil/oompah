---
id: OOMPAH-254
type: task
status: In Progress
priority: null
title: Define state-branch format, configuration contract, and migration design
parent: OOMPAH-253
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T16:29:10.225678Z'
updated_at: '2026-07-20T16:32:06.136722Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2221343f-cd90-4149-8607-cfa8c808bff0
---
## Summary

Scope

Write the implementation design for Git-backed per-project Oompah state branches before changing runtime behavior. Specify the canonical state branch naming, layout, project configuration fields, backward-compatible defaults, checkpoint rules, recovery, concurrency, migration stages, and rollback. Place internal design material in plans/ and user/operator guidance in docs/ as appropriate.

Required detail

- Define the state branch contract: required task-tree paths, initial commit/bootstrap behavior, remote tracking, branch protection assumptions, and how it relates to code main and release branches.
- Define durable versus ephemeral task data. Explicitly classify status, dependencies, human comments, focus handoffs, descriptions, agent telemetry, retry counters, timestamps, and caches.
- Define checkpoint coalescing policy: debounce interval, maximum delay, mandatory flush events, single-writer ordering, push/retry behavior, crash recovery, and observability. All tunable values belong in .env.
- Define an idempotent migration and rollback protocol for existing projects, including validation and failure handling.
- Identify all affected APIs, CLI behavior, project-bootstrap templates, docs, and test layers.

Tests

- Add design-validation tests only where the design introduces machine-readable defaults or configuration schemas.
- Review the design against a fixture representing a project with historical .oompah task data on main and active release branches.

Acceptance criteria

- plans/ contains an implementable design with no unresolved choices that would block a junior developer.
- docs/ clearly distinguishes operator migration steps from internal design.
- The design includes concrete compatibility, migration, rollback, and checkpoint semantics.
- make test passes if code/schema changes are made.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:32
---
Agent completed successfully in 27s (94176 tokens)
---
<!-- COMMENTS:END -->
