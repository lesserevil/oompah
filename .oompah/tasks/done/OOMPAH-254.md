---
id: OOMPAH-254
type: task
status: Done
priority: null
title: Define state-branch format, configuration contract, and migration design
parent: OOMPAH-253
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:29:10.225678Z'
updated_at: '2026-07-20T16:47:12.892242Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 37ce215b-6481-41ed-9fb0-db4d4c283e9f
oompah.task_costs:
  total_input_tokens: 93581
  total_output_tokens: 4141
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 93581
      output_tokens: 4141
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 93564
    output_tokens: 612
    cost_usd: 0.0
    recorded_at: '2026-07-20T16:32:05.456922+00:00'
  - profile: standard
    model: unknown
    input_tokens: 17
    output_tokens: 3529
    cost_usd: 0.0
    recorded_at: '2026-07-20T16:34:12.080015+00:00'
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
author: oompah
created: 2026-07-20 16:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 93.6K in / 612 out [94.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 27s
- Log: OOMPAH-254__20260720T163145Z.jsonl
---
author: oompah
created: 2026-07-20 16:32
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-253`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 16:32
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 16:32
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:33
---
Focus handoff: duplicate_detector

Outcome: No duplicate found. OOMPAH-254 is a unique design task and is not covered by any existing or archived task.

Evidence reviewed:
- Searched .oompah/tasks/, plans/, docs/ for: state-branch, checkpoint, coalesce, migration, configuration-contract, git-backed state
- plans/multi-branch-support.md tracks multiple *code* branches; does not address a dedicated oompah/state metadata branch
- OOMPAH-203 (auto-update after tracker writes) and OOMPAH-235 (concurrent write recovery) are implementation bug-fixes, not the design work described here
- All OOMPAH-228 through OOMPAH-232 (archived) are duplicate-task-ID bugs, unrelated
- OOMPAH-254 is child task 1 of epic OOMPAH-253 (Git-backed Oompah state branches); no prior design exists

Remaining work: Full design document as specified in the task description:
- plans/state-branch-design.md: state branch contract, durable vs ephemeral classification, checkpoint coalescing policy, migration/rollback protocol, affected APIs/CLI/test layers
- docs/state-branch-migration.md: operator migration steps
- Design-validation tests for any machine-readable schemas introduced

Recommended next focus: docs (design writer, to produce the plans/ and docs/ content required by the acceptance criteria)
---
author: oompah
created: 2026-07-20 16:34
---
Agent completed successfully in 98s (3546 tokens)
---
author: oompah
created: 2026-07-20 16:34
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 31, Tool calls: 21
- Tokens: 17 in / 3.5K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 38s
- Log: OOMPAH-254__20260720T163239Z.jsonl
---
author: oompah
created: 2026-07-20 16:34
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 16:35
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 16:35
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-20 16:36
---
Understanding: This task requires writing two key documents: (1) plans/state-branch-design.md — the internal architecture spec for Git-backed per-project state branches, covering naming conventions, layout, durable vs ephemeral data classification, checkpoint coalescing, migration/rollback, and affected APIs/test layers; (2) docs/state-branch-migration.md — operator-facing migration guide.

After reviewing the codebase, I understand the current state: task data lives on the project's default branch under .oompah/tasks/, written by OompahMarkdownTracker with synchronous commit+push on every write. The 'state branch' design would move this write path to a dedicated oompah/state/<project-id> branch to avoid contaminating main with task metadata commits, enabling cleaner merge queues and reducing write conflicts on busy projects.

Beginning document authoring now.
---
author: oompah
created: 2026-07-20 16:36
---
Discovery: Completed codebase review. Key findings:

1. Task data today is written to .oompah/tasks/ on the project's default branch by OompahMarkdownTracker._commit_and_push() — one git commit per write operation (create, update, comment, metadata change). This contaminates the default branch with high-frequency service metadata commits.

2. Every write goes through _prepare_default_branch_for_write() which rejects writes on any non-default branch, then pulls with ff-only + rebase fallback. This is a single-writer assumption baked into the current design.

3. The submit-queue plan (plans/submit-queue.md, Step 2) explicitly notes that keeping task writes server-side and away from worker branches is needed for parallel PR safety.

4. No existing design addresses a dedicated oompah/state/* branch — this is net-new design work.

5. The design must be backward-compatible: the write path only changes when a project opts in via a new state_branch configuration field.

Writing plans/state-branch-design.md and docs/state-branch-migration.md now.
---
author: oompah
created: 2026-07-20 16:46
---
Implementation: Created three new files:

1. plans/state-branch-design.md (35KB) — full internal design covering:
   - State branch naming convention (oompah/state/<project-id>) and orphan branch rationale
   - Complete directory layout (.oompah/tasks/ only, no source code)
   - Bootstrap, remote tracking, and branch protection setup
   - Relationship to code main and release branches (Mermaid diagram)
   - New Project model fields (state_branch_enabled, checkpoint tunables)
   - All .env variables with defaults (OOMPAH_STATE_BRANCH_CHECKPOINT_DEBOUNCE_MS=5000, etc.)
   - Durable vs ephemeral data classification (all fields explicitly listed)
   - Checkpoint coalescing policy: debounce (5s), max delay (30s), mandatory flush events
   - Single-writer ordering and push/retry behavior
   - Crash recovery protocol
   - Observability (structured logs, GET /api/v1/state state_branch block)
   - 3-stage migration (A: shadow write, B: exclusive state-branch, C: optional cleanup)
   - Rollback protocol for each stage
   - Affected APIs, CLI, tracker implementation guide, test layers
   - All open design questions resolved (9 decisions recorded)

2. docs/state-branch-migration.md (12KB) — operator-facing migration guide covering:
   - Why to migrate (benefit explanation without implementation jargon)
   - Prerequisites
   - Step-by-step migration (validate, branch protection, Stage A, Stage B, monitor, Stage C)
   - Troubleshooting table (push_failures, alerts, corrupt files, duplicates)
   - Rollback from each stage
   - New-project setup
   - Checkpoint interval tuning

3. tests/test_state_branch_design.py (22KB) — design-validation tests:
   - Env variable naming convention (all OOMPAH_STATE_BRANCH_ prefixed)
   - Default value constraints (enabled=false, debounce < max_delay)
   - Project model backward compatibility (xfail until fields added)
   - Checkpoint interval correction formula
   - Historical task data fixture (git repo with main + release/1.0 + task files)
   - Orphan branch property validation
   - State branch contains only .oompah/ content (no source code)
   - State branch naming parametrized tests

make test: 9430 passed, 36 skipped, 2 xfailed (new xfails document not-yet-implemented Project fields)
---
author: oompah
created: 2026-07-20 16:47
---
Completion: All deliverables for OOMPAH-254 are committed and pushed to epic-OOMPAH-253 (commit 0095b1ef).

Delivered:
- plans/state-branch-design.md: Implementable design with no unresolved choices. Covers naming, layout, bootstrap, durable/ephemeral classification, checkpoint coalescing with all tunable values in .env, migration stages A/B/C, rollback for each stage, and all affected APIs/CLI/test layers. All 9 design decisions are explicitly resolved with rationale.
- docs/state-branch-migration.md: Operator guide clearly separated from internal design. Written for operators who don't read the plans/ doc. Covers prerequisites, GitHub branch protection setup, step-by-step migration commands, monitoring, rollback, and tuning.
- tests/test_state_branch_design.py: Design-validation tests using a git fixture with historical .oompah task data on main and active release/1.0 branch. Validates env var naming, defaults, checkpoint constraint formula, orphan branch property, directory layout contract, YAML integrity, and no-duplicate pre-migration check. make test: 9430 passed, 2 xfailed (xfails document not-yet-implemented Project fields).

Acceptance criteria met:
- plans/ contains an implementable design with no unresolved choices
- docs/ clearly distinguishes operator migration steps from internal design
- The design includes concrete compatibility, migration, rollback, and checkpoint semantics
- make test passes
---
author: oompah
created: 2026-07-20 16:47
---
Wrote plans/state-branch-design.md (internal design), docs/state-branch-migration.md (operator guide), and tests/test_state_branch_design.py (design-validation tests). All make test passes (9430 passed, 2 xfailed for not-yet-implemented Project fields). Pushed to epic-OOMPAH-253.
---
<!-- COMMENTS:END -->
