---
id: OOMPAH-296
type: task
status: In Progress
priority: 2
title: Implement Aider-style repository-map ranking and bounded rendering
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-295
labels:
- focus-complete:duplicate_detector
- focus-complete:frontend
assignee: null
created_at: '2026-07-21T15:13:49.289592Z'
updated_at: '2026-07-21T16:55:00.511888Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 30ceb0ca-c179-4a85-9d7b-20c6b16f6421
oompah.task_costs:
  total_input_tokens: 630953
  total_output_tokens: 14201
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 630953
      output_tokens: 14201
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 17
    output_tokens: 4204
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:42:00.024090+00:00'
  - profile: standard
    model: unknown
    input_tokens: 13
    output_tokens: 3017
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:46:42.469689+00:00'
  - profile: standard
    model: unknown
    input_tokens: 238916
    output_tokens: 4236
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:49:03.099630+00:00'
  - profile: deep
    model: unknown
    input_tokens: 392007
    output_tokens: 2744
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:51:01.594874+00:00'
---
## Summary

Build the ranking and rendering layer over extracted Tree-sitter tags. Following Aider RepoMap principles, form a directed relationship graph from definitions and references, rank important symbols/files, and render a stable, compact textual map within a caller-provided token budget. Prefer task-mentioned identifiers and seed files when supplied; include useful definitions rather than raw source bodies. Ensure ties sort deterministically.\n\nDo not persist maps or alter agent prompts in this task.\n\nTests:\n- Synthetic graph fixtures verify referenced symbols outrank isolated symbols.\n- Verify task-mentioned names and seed files receive the documented boost.\n- Verify output never exceeds the requested token budget, remains deterministic, and remains readable when no edges exist.\n- Verify paths and source excerpts are escaped/marked as untrusted data.\n\nAcceptance criteria:\n- Callers can request a bounded text map from an extracted artifact.\n- Results prioritize structurally relevant and task-relevant code.\n- Rendering has no network dependency and does not expose files outside the repository.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:41
---
Duplicate screening complete: no duplicate found.

Searched all .oompah/tasks/ directories (archived, done, merged, backlog, needs-ci-fix, needs-rebase) for: repo-map, repomap, aider, ranking, tree-sitter, pagerank, token budget, bounded render, directed graph, symbol rank, seed file, task-mentioned. Zero matches across all task files for these terms in the context of ranking or rendering.

Closest reviewed tasks/evidence:
- OOMPAH-293 (In Progress): Parent epic 'Build Git-backed repository maps'. Contains 'Aider-style definition/reference ranking algorithm' in description but is the parent epic, not a duplicate of this child task.
- OOMPAH-295 (Done): 'Add Tree-sitter repository symbol and reference extraction'. This is the upstream dependency (produces extraction artifacts). It explicitly excludes ranking — 'Do not rank results' is in its description. OOMPAH-296 builds the ranking/rendering layer over those artifacts.
- OOMPAH-294 (Done): Defines the artifact schema/lifecycle. Out of scope for ranking.
- OOMPAH-297–300 (Open): Sibling tasks covering persistence/state-branch maintenance (297), prompt injection (298), docs/config (299), and observability (300). All distinct from ranking and bounded rendering.
- plans/ and docs/: No plans or docs covering Aider-style ranking or token-bounded map rendering found.

No prior task covers directed relationship graph formation, PageRank-style symbol scoring, task-relevance boosting, or token-budget-bounded rendering. OOMPAH-296 is net-new implementation work.
---
author: oompah
created: 2026-07-21 16:41
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-296 is net-new implementation work.
2. Evidence: Searched all .oompah/tasks/ subdirectories (archived ~200+ tasks, done, merged ~50+ tasks, backlog, needs-ci-fix, needs-rebase) for: repo-map, aider, ranking, tree-sitter, pagerank, token budget, bounded render, directed graph, symbol rank, seed file. Zero matches for ranking/rendering context. OOMPAH-293 is the parent epic; OOMPAH-295 (Done) is the upstream extractor (explicitly excludes ranking). OOMPAH-297–300 are distinct sibling tasks.
3. Remaining work: Implement the Aider-style ranking and bounded rendering layer: (a) build directed relationship graph from OOMPAH-295 extraction artifacts (defs/refs), (b) apply PageRank-style scoring with boosts for task-mentioned identifiers and seed files, (c) render token-budget-bounded text map with deterministic tie-breaking, (d) escape/mark paths and source excerpts as untrusted, (e) write tests per acceptance criteria (synthetic graph fixtures, boost verification, budget enforcement, determinism, no-edge readability, path escaping), (f) verify 'make test' passes. Key dependency: oompah/repo_indexer.py and oompah/repo_map.py (OOMPAH-295 artifacts).
4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-21 16:42
---
Agent completed successfully in 104s (4221 tokens)
---
author: oompah
created: 2026-07-21 16:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 37, Tool calls: 24
- Tokens: 17 in / 4.2K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 44s
- Log: OOMPAH-296__20260721T164019Z.jsonl
---
author: oompah
created: 2026-07-21 16:42
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:42
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 16:42
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 16:46
---
Understanding (as Frontend Developer): OOMPAH-296 requires implementing Aider-style ranking and bounded rendering over Tree-sitter extraction artifacts (OOMPAH-295). This involves: (1) building a directed relationship graph from RepoMap.symbol_tags and RepoMap.relationship_edges, (2) PageRank-style symbol/file scoring with task-mention and seed-file boosts, (3) token-budget-bounded text map rendering with deterministic tie-breaking, (4) path/excerpt escaping as untrusted data, and (5) comprehensive tests per acceptance criteria.

This is a purely Python backend feature (graph algorithms, text rendering) with no UI, accessibility, or frontend component. My 'Frontend Developer' focus is not applicable here. Handing off to 'feature' specialist.
---
author: oompah
created: 2026-07-21 16:46
---
Focus handoff: frontend

1. Outcome: This task has no frontend/UI component. It is a pure Python backend feature implementing Aider-style ranking and rendering over the Tree-sitter extraction artifacts from OOMPAH-295. The Frontend Developer focus is inapplicable — no handoff work was done; no code was changed.

2. Relevant files and evidence:
   - oompah/repo_map.py — defines RepoMap, SymbolTag, RelationshipEdge, IndexedFile, RenderingMetadata dataclasses (schema/serialization, DONE per OOMPAH-294/295). No ranking or rendering code exists here.
   - oompah/repo_indexer.py — Tree-sitter extraction of symbols and edges (DONE per OOMPAH-295). No ranking.
   - tests/test_repo_map.py — comprehensive schema/lifecycle tests.
   - tests/test_repo_indexer.py — extraction tests.
   - NO oompah/repo_map_ranker.py or similar ranking/rendering module exists yet.
   - make test → uv run pytest tests/ -v

3. Remaining work (ALL of it, none started):
   - Create oompah/repo_map_ranker.py (or similar) with:
     a) build_relationship_graph(repo_map: RepoMap) → directed symbol/file graph from relationship_edges and symbol_tags
     b) rank_symbols(graph, task_mentions=None, seed_files=None) → scores with PageRank-style algorithm; boost task-mentioned names and seed files
     c) render_repo_map(repo_map, token_budget, task_mentions=None, seed_files=None) → str: token-budget-bounded text, deterministic tie-breaking, paths/excerpts escaped as untrusted data, no network calls, no filesystem access outside repo
   - Create tests/test_repo_map_ranker.py with:
     a) Synthetic graph fixtures: referenced symbols outrank isolated symbols
     b) Boost verification: task-mentioned names and seed files get documented score boost
     c) Budget enforcement: output never exceeds token_budget
     d) Determinism: same inputs → identical output
     e) No-edge readability: graceful output when graph has no edges
     f) Path/excerpt escaping: paths and source excerpts marked/escaped as untrusted
   - Verify make test passes

4. Recommended next focus: feature
---
author: oompah
created: 2026-07-21 16:46
---
Agent completed successfully in 273s (3030 tokens)
---
author: oompah
created: 2026-07-21 16:46
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 26, Tool calls: 15
- Tokens: 13 in / 3.0K out [3.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 33s
- Log: OOMPAH-296__20260721T164211Z.jsonl
---
author: oompah
created: 2026-07-21 16:46
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:47
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 16:47
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 16:49
---
Agent completed successfully in 105s (243152 tokens)
---
author: oompah
created: 2026-07-21 16:49
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 238.9K in / 4.2K out [243.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 45s
- Log: OOMPAH-296__20260721T164719Z.jsonl
---
author: oompah
created: 2026-07-21 16:49
---
Agent completed without closing this issue (105s (243152 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 16:49
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:49
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 16:51
---
Agent completed successfully in 99s (394751 tokens)
---
author: oompah
created: 2026-07-21 16:51
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 8
- Tokens: 392.0K in / 2.7K out [394.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 39s
- Log: OOMPAH-296__20260721T164924Z.jsonl
---
author: oompah
created: 2026-07-21 16:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:51
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 16:55
---
Understanding (Test Engineer): The test file tests/test_repo_map_ranker.py already exists with comprehensive tests for rank_symbols() and render_repo_map(). The implementation file oompah/repo_map_ranker.py is missing — causing a ModuleNotFoundError. My job is to create the implementation to make all tests pass. Tests cover: (1) referenced symbols outranking isolated ones, (2) task-mention and seed-file boosts, (3) deterministic tie-breaking by path+line, (4) token-budget enforcement, (5) ValueError on non-positive budget, (6) readable output without edges, (7) HTML-escaping of untrusted paths/names with UNTRUSTED label. Implementing now.
---
<!-- COMMENTS:END -->
