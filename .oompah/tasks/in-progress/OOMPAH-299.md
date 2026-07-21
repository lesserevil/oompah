---
id: OOMPAH-299
type: task
status: In Progress
priority: 2
title: Add repository-map configuration, bootstrap defaults, and operator documentation
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-297
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:14:09.575764Z'
updated_at: '2026-07-21T23:38:55.087576Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 04f0d172-18ca-4447-a9ce-b3d11ec9deca
oompah.task_costs:
  total_input_tokens: 29
  total_output_tokens: 7251
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 29
      output_tokens: 7251
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 29
    output_tokens: 7251
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:03:15.084019+00:00'
---
## Summary

Add environment-backed configuration for repository maps: enable flag, token budget, supported-language policy, maximum file size, generation timeout, and retained-artifact count. Add safe defaults and document every setting in .env.example. Update project-bootstrap so new managed projects receive the required state-branch capability/configuration without changing application source branches. Write user/operator documentation covering activation, freshness, diagnostics, privacy/trust boundaries, and how to disable or rebuild a map.\n\nDo not add configuration values to WORKFLOW.md.\n\nTests:\n- Configuration parsing tests cover defaults, valid overrides, invalid values, and disabled mode.\n- Bootstrap tests verify generated project configuration enables the feature only under the documented conditions.\n- Documentation checks or fixtures verify every exposed environment setting is represented in .env.example.\n\nAcceptance criteria:\n- Operators can enable, tune, disable, and diagnose the feature solely through documented configuration.\n- Newly bootstrapped projects work with the Git-backed state model.\n- No new daemon, database, or externally hosted service is required.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:02
---
Duplicate screening complete: no duplicate found.

Searched all .oompah/tasks/ directories (archived ~223 tasks, merged ~50 tasks, done/backlog) and plans/ for: repository-map, repo-map, repomap, repo_map, token-budget, max-file-size, generation-timeout, retained-artifact, language-policy, OOMPAH_REPO_MAP, env.example + repo-map, operator + repo-map, bootstrap + repo-map.

Closest reviewed tasks (all confirmed distinct):
- OOMPAH-258 (Merged): 'Configure Git state branches in project-bootstrap and operator documentation' — superficially similar (bootstrap + operator docs) but covers the state-branch feature, not repository maps. Distinct scope.
- OOMPAH-297 (Done): 'Generate and maintain repository maps on Git-backed state branches' — implements the generation/maintenance orchestrator. Does not add env-backed config, bootstrap defaults, or operator documentation.
- OOMPAH-294 (Done): Defines artifact schema and lifecycle. Covers storage paths and freshness, not operator configuration or bootstrap.
- OOMPAH-295 (Done): Tree-sitter extraction (indexing layer only).
- OOMPAH-296 (Merged): Ranking and bounded rendering (output layer only).
- OOMPAH-298 (Open): Prompt injection (downstream consumer, distinct from config/docs).
- OOMPAH-300 (Open): End-to-end observability (distinct observability layer).

No existing task covers: OOMPAH_REPO_MAP_* environment variable definitions, env.example repo-map section, bootstrap defaults for repo-map capability, or operator documentation for activation, freshness, diagnostics, privacy/trust boundaries, and rebuild procedures.

OOMPAH-299 is net-new work.
---
author: oompah
created: 2026-07-21 23:03
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate confirmed. OOMPAH-299 is net-new work — the configuration, bootstrap-defaults, and operator-documentation layer for the repository-map feature (OOMPAH-293 epic).

2. **Relevant files, commands, and evidence**:
   - `oompah/repo_map.py` — artifact schema, write/read helpers, freshness check, pruning. Implemented by OOMPAH-294.
   - `oompah/repo_indexer.py` — Tree-sitter extraction. Implemented by OOMPAH-295.
   - `oompah/repo_map_ranker.py` — rank_symbols(), render_repo_map(), token budget enforced at render time. Implemented by OOMPAH-296.
   - `oompah/repo_map_generator.py` — generation/maintenance orchestrator, bounded background thread pool, coalescing, state-branch commit+push, pruning. Implemented by OOMPAH-297.
   - `oompah/project_bootstrap/__init__.py` — has initialize_state_branch() from OOMPAH-258; does NOT yet have repo-map bootstrap defaults.
   - `.env.example` — check whether OOMPAH_REPO_MAP_* variables exist yet (expected: they do not).
   - `plans/repo-map-artifact.md` — schema and lifecycle design doc; does not define env-var configuration.
   - `plans/state-branch-design.md` — state-branch namespace; useful for repo-map state-branch paths.
   - `docs/project-bootstrap.md` — updated by OOMPAH-258 with state-branch section; no repo-map section yet.
   - `make test` — runs uv run pytest tests/

3. **Remaining work**:
   - Add `OOMPAH_REPO_MAP_ENABLED`, `OOMPAH_REPO_MAP_TOKEN_BUDGET`, `OOMPAH_REPO_MAP_LANGUAGES`, `OOMPAH_REPO_MAP_MAX_FILE_SIZE`, `OOMPAH_REPO_MAP_GENERATION_TIMEOUT`, `OOMPAH_REPO_MAP_RETAINED_ARTIFACTS` environment variables and safe defaults in oompah config module.
   - Document all settings with examples and valid ranges in `.env.example`.
   - Update project-bootstrap so new managed projects have repo-map capability configured (state-branch already exists from OOMPAH-258; add repo-map enable flag and defaults to bootstrap output).
   - Write user/operator documentation in `docs/` covering: activation, freshness behavior, diagnostics, privacy/trust boundaries (untrusted data constraint), and how to disable or rebuild a map.
   - Tests: config parsing (defaults, valid overrides, invalid values, disabled mode), bootstrap tests (verify generated project config enables the feature only under documented conditions), documentation fixture test (every env var in code appears in .env.example).
   - All tests pass via `make test`.

4. **Risks**:
   - The token budget is currently enforced inside `render_repo_map()` in `oompah/repo_map_ranker.py` — the new config system should feed into this function's `max_tokens` parameter.
   - Language policy should map cleanly to the `supported_extensions` / Tree-sitter language detection in `oompah/repo_indexer.py`.
   - Bootstrap changes must be idempotent (consistent with OOMPAH-258 pattern).
   - The description explicitly says: do NOT add config values to WORKFLOW.md — use `.env` / `.env.example` only.

5. **Recommended next focus**: feature
---
author: oompah
created: 2026-07-21 23:03
---
Agent completed successfully in 155s (7280 tokens)
---
author: oompah
created: 2026-07-21 23:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 56, Tool calls: 45
- Tokens: 29 in / 7.3K out [7.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 35s
- Log: OOMPAH-299__20260721T230043Z.jsonl
---
author: oompah
created: 2026-07-21 23:03
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 23:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:38
---
Focus: Test Engineer
---
<!-- COMMENTS:END -->
