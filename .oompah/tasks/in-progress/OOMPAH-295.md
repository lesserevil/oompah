---
id: OOMPAH-295
type: task
status: In Progress
priority: 1
title: Add Tree-sitter repository symbol and reference extraction
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-294
labels: []
assignee: null
created_at: '2026-07-21T15:13:48.374539Z'
updated_at: '2026-07-21T16:14:04.229957Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1c95c3bc-a69d-47e0-b141-7b921955d054
oompah.task_costs:
  total_input_tokens: 112011
  total_output_tokens: 5332
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 112011
      output_tokens: 5332
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 22
    output_tokens: 4535
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:13:21.861895+00:00'
  - profile: default
    model: unknown
    input_tokens: 111989
    output_tokens: 797
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:14:01.225354+00:00'
---
## Summary

Implement a standalone repository indexer that walks a checked-out repository, respects existing ignore rules, and uses Tree-sitter Python bindings plus packaged grammars to extract file-level symbols and references. Start with the languages used by Oompah-managed projects: Python, Rust, TypeScript/JavaScript, YAML, and Markdown where useful. Record normalized relative paths, symbol name, kind, line span, and reference names using the artifact contract from OOMPAH-294. Handle parse errors and unsupported file types without failing the repository scan.\n\nDo not rank results, persist artifacts, or change prompts in this task. Do not execute project code.\n\nTests:\n- Fixture repositories for each supported language verify expected extracted symbols and references.\n- Verify ignored, binary, oversized, and unsupported files are skipped with recorded diagnostics.\n- Verify malformed source yields partial results and no crash.\n\nAcceptance criteria:\n- The indexer runs solely on checked-out file content and requires no project build.\n- Supported-language output conforms to the repository-map artifact types.\n- Unsupported or invalid input degrades safely and is observable.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:13
---
Duplicate screening complete: no duplicate found.

Searched all .oompah/tasks/ directories (archived, done, merged, backlog, needs-ci-fix, needs-rebase) for: tree-sitter, tree_sitter, treesitter, symbol extraction, reference extraction, code indexer, grammar, parse file, walk repo. Zero matches across all task files.

Closest reviewed tasks/evidence:
- OOMPAH-293 (In Progress): Parent epic 'Build Git-backed repository maps'. Contains 'Tree-sitter' in description, but is the parent epic — not a duplicate of this child task.
- OOMPAH-294 (Done): 'Define repository-map artifact and state-branch lifecycle'. This is the upstream dependency (defines types/schema). It explicitly states 'parsing heuristics' and 'how the map is generated' are 'specified in later tasks' (i.e., OOMPAH-295 is that later task).
- OOMPAH-296-300 (Open): Sibling tasks covering ranking (296), persistence/state-branch maintenance (297), prompt injection (298), docs/config (299), and observability (300). All distinct from symbol extraction.
- plans/repo-map-artifact.md: Confirms the indexer/parser is out of scope for OOMPAH-294.

No prior task covers Tree-sitter-based file walking, symbol extraction, or reference extraction. OOMPAH-295 is net-new implementation work.
---
author: oompah
created: 2026-07-21 16:13
---
Agent completed successfully in 104s (4557 tokens)
---
author: oompah
created: 2026-07-21 16:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 48, Tool calls: 32
- Tokens: 22 in / 4.5K out [4.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 44s
- Log: OOMPAH-295__20260721T161142Z.jsonl
---
author: oompah
created: 2026-07-21 16:13
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-21 16:13
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:14
---
Agent completed successfully in 26s (112786 tokens)
---
author: oompah
created: 2026-07-21 16:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 112.0K in / 797 out [112.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 26s
- Log: OOMPAH-295__20260721T161337Z.jsonl
---
author: oompah
created: 2026-07-21 16:14
---
Agent completed without closing this issue (26s (112786 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
