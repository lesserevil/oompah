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
assignee: null
created_at: '2026-07-21T15:13:49.289592Z'
updated_at: '2026-07-21T16:42:11.126060Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b16ebc8d-6147-48b9-a226-04ab4b10ca54
oompah.task_costs:
  total_input_tokens: 17
  total_output_tokens: 4204
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 17
      output_tokens: 4204
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 17
    output_tokens: 4204
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:42:00.024090+00:00'
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
<!-- COMMENTS:END -->
