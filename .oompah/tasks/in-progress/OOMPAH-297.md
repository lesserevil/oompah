---
id: OOMPAH-297
type: task
status: In Progress
priority: 1
title: Generate and maintain repository maps on Git-backed state branches
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-294
- OOMPAH-296
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:14:07.528667Z'
updated_at: '2026-07-21T22:15:21.812813Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a9b49eac-b66e-4f2f-b7d5-c7e6d0d01e7d
oompah.task_costs:
  total_input_tokens: 425949
  total_output_tokens: 8423
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 425949
      output_tokens: 8423
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 21
    output_tokens: 5691
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:13:56.160912+00:00'
  - profile: standard
    model: unknown
    input_tokens: 425928
    output_tokens: 2732
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:15:18.905813+00:00'
---
## Summary

Connect repository-map generation to Oompah project synchronization. For a managed project checkout, reuse a fresh artifact for the exact target commit or generate one from the Tree-sitter extractor and ranked renderer. Write it atomically to the configured project state branch using the lifecycle from OOMPAH-294; never write generated map files to the managed repository main or release branches. Coalesce duplicate requests for the same project/SHA and retain only the configured bounded history.\n\nGeneration must run as a bounded background operation. A failed, stale, or partial index must be reported and must not block normal task dispatch.\n\nTests:\n- Integration tests with a temporary Git remote prove maps land only on the state branch.\n- Verify same-SHA requests reuse the artifact and changed-SHA requests regenerate it.\n- Verify concurrent requests coalesce and atomic writes never expose partial JSON.\n- Verify failures/timeouts leave task dispatch usable and emit a diagnostic state.\n\nAcceptance criteria:\n- One fresh artifact is available per successfully indexed project commit.\n- No repository code branch receives index-only commits.\n- Storage retention and failure behavior match the design document.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:13
---
Duplicate screening complete: no duplicate found.

Searched all .oompah/tasks/ directories (archived ~200+ tasks, done, merged ~50+ tasks, backlog, needs-ci-fix, needs-rebase) and plans/ for: repository-map, repo-map, repomap, repo_map, state-branch, coalesce, bounded background, background generation, SHA reuse, project synchronization, atomic write + map, tree-sitter. Zero matches for any of these terms in an overlapping scope.

Closest reviewed tasks and evidence:
- OOMPAH-294 (Done): Defines the artifact schema and state-branch lifecycle — this is the upstream foundation that OOMPAH-297 builds on, not a duplicate.
- OOMPAH-295 (Done): Adds Tree-sitter extraction (input layer) — out of scope for generation/maintenance orchestration.
- OOMPAH-296 (Merged): Implements ranking and bounded rendering (output layer) — out of scope for the integration/orchestration tier.
- OOMPAH-298/299/300 (Open): Downstream consumers (prompt injection, config/docs, observability) — distinct from generation/maintenance.
- plans/repo-map-artifact.md: Design doc (OOMPAH-294 output) covers schema/lifecycle only, not the generation orchestrator.
- No archived or merged task covers: project-sync integration, duplicate-request coalescing, background-bounded generation, per-SHA cache reuse, state-branch integration tests, or concurrent-write atomicity.

OOMPAH-297 is net-new implementation work: the orchestration/integration layer that connects Tree-sitter extraction + ranking to the state-branch persistence lifecycle.
---
author: oompah
created: 2026-07-21 22:13
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate confirmed. OOMPAH-297 is net-new implementation work — the orchestration/integration layer of the OOMPAH-293 epic.

2. **Relevant files, commands, and evidence**:
   - `oompah/repo_map.py` — typed artifact contract (RepoMap, IndexedFile, SymbolTag, RelationshipEdge, RenderingMetadata), atomic write/read helpers (write_repo_map, read_repo_map, prune_repo_maps), freshness check (is_fresh), path construction (repo_map_path, repo_map_slug). Implemented by OOMPAH-294.
   - `oompah/repo_indexer.py` — Tree-sitter symbol and reference extraction. Implemented by OOMPAH-295.
   - `oompah/repo_map_ranker.py` — rank_symbols() and render_repo_map() for Aider-style ranking. Implemented by OOMPAH-296.
   - `tests/test_repo_map.py` — 106 unit tests for schema/lifecycle.
   - `plans/repo-map-artifact.md` — design doc for schema, atomic write, freshness, pruning, state-branch paths.
   - `plans/state-branch-design.md` — state-branch namespace and lifecycle.
   - `make test` — test target (runs uv run pytest tests/).

3. **Remaining work (all of it)**:
   - Create the generation/maintenance orchestrator (e.g., `oompah/repo_map_generator.py`) that:
     a) Checks the state branch for a fresh map for the current project/SHA; returns it if available.
     b) Otherwise, triggers Tree-sitter extraction (repo_indexer) + ranking (repo_map_ranker) to generate a new RepoMap.
     c) Writes the artifact atomically via write_repo_map() and commits to the configured state branch (never to main/release).
     d) Coalesces duplicate requests for the same project+SHA (in-flight dedup).
     e) Runs as a bounded background operation with a configurable timeout.
     f) Reports failures/timeouts as diagnostic state without blocking task dispatch.
     g) Retains only bounded history (prune_repo_maps after each commit).
   - Integration tests with a temporary Git remote verifying: maps land only on the state branch; same-SHA requests reuse the artifact; changed-SHA requests regenerate; concurrent requests coalesce; atomic writes never expose partial JSON; failures leave task dispatch usable; timeouts emit diagnostic state.
   - Verify all tests pass via `make test`.

4. **Risks**:
   - The state branch commit logic needs to integrate with the existing state-branch write infrastructure (see `plans/state-branch-design.md`). Verify whether a helper for state-branch commits already exists or needs to be created.
   - Concurrency primitives (asyncio.Lock or threading.Lock) must match the event loop model used in the rest of the codebase — check `oompah/projects.py` and related files for patterns.
   - The blocking dependencies (OOMPAH-294, OOMPAH-296) are Done/Merged, so implementation can proceed.

5. **Recommended next focus**: feature
---
author: oompah
created: 2026-07-21 22:13
---
Agent completed successfully in 323s (5712 tokens)
---
author: oompah
created: 2026-07-21 22:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 43, Tool calls: 28
- Tokens: 21 in / 5.7K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 23s
- Log: OOMPAH-297__20260721T220835Z.jsonl
---
author: oompah
created: 2026-07-21 22:13
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 22:14
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 22:14
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 22:15
---
Agent completed successfully in 73s (428660 tokens)
---
author: oompah
created: 2026-07-21 22:15
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 425.9K in / 2.7K out [428.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 13s
- Log: OOMPAH-297__20260721T221410Z.jsonl
---
author: oompah
created: 2026-07-21 22:15
---
Agent completed without closing this issue (73s (428660 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
