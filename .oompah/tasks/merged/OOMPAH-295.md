---
id: OOMPAH-295
type: task
status: Merged
priority: 1
title: Add Tree-sitter repository symbol and reference extraction
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-294
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:13:48.374539Z'
updated_at: '2026-07-22T00:37:52.972986Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: bd1c33b7-1890-465a-a08f-fd41ef79dc3a
oompah.task_costs:
  total_input_tokens: 209313
  total_output_tokens: 10159
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 209313
      output_tokens: 10159
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
  - profile: standard
    model: unknown
    input_tokens: 97163
    output_tokens: 666
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:14:45.998564+00:00'
  - profile: default
    model: unknown
    input_tokens: 100
    output_tokens: 3041
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:40:05.120662+00:00'
  - profile: default
    model: unknown
    input_tokens: 39
    output_tokens: 1120
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:36:54.672564+00:00'
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
author: oompah
created: 2026-07-21 16:14
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 16:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:14
---
Focus handoff: duplicate_detector

1. Outcome: no duplicate confirmed.
2. Evidence: searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for Tree-sitter/indexing/symbol/reference/repository-map terms. OOMPAH-293 is the parent epic; OOMPAH-294 supplies the typed artifact contract and explicitly excludes parsing. Neither duplicates this extraction task.
3. Remaining work: implement the standalone Tree-sitter repository walker and extraction tests against oompah/repo_map.py artifact types.
4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-21 16:14
---
Agent completed successfully in 28s (97829 tokens)
---
author: oompah
created: 2026-07-21 16:14
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 2
- Tokens: 97.2K in / 666 out [97.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-295__20260721T161419Z.jsonl
---
author: oompah
created: 2026-07-21 16:14
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:14
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 16:17
---
Understanding + Discovery: No indexer implementation exists yet. The artifact contract (OOMPAH-294) is in oompah/repo_map.py. tree-sitter and grammar packages (tree-sitter-python, tree-sitter-rust, tree-sitter-javascript, tree-sitter-typescript, tree-sitter-yaml) are available on PyPI and resolvable by uv. Plan: (1) add tree-sitter dependencies to pyproject.toml, (2) implement oompah/repo_indexer.py with file-walker, language detector, binary/size filters, gitignore respect, and Tree-sitter-based symbol/reference extractor for Python/Rust/TypeScript/JavaScript/YAML/Markdown, (3) write comprehensive tests covering happy paths per language, skipped files (binary/oversized/ignored/unsupported), malformed source, and no-crash invariants. Tests will use pytest.importorskip for tree-sitter, and inline fixture repos created in tmp_path.
---
author: oompah
created: 2026-07-21 16:35
---
Implementation + Verification: Implemented oompah/repo_indexer.py (standalone Tree-sitter indexer) and tests/test_repo_indexer.py (166 tests). make test passes: 10,194 total tests, 0 failures. Key coverage: detect_language (all 6 supported languages + unsupported), is_binary_content (null-byte heuristic), _GitignoreSpec (patterns, anchored, negation, node_modules, negation order), extract_symbols_and_edges per language (Python/Rust/JS/TS/YAML/Markdown), index_repository (file walking, .gitignore, binary/oversized/unsupported skipping, always-skip dirs, lexicographic sorting, content hash, schema conformance, error cases), mixed-fixture integration test.
---
author: oompah
created: 2026-07-21 16:39
---
Completion: Delivered oompah/repo_indexer.py (standalone Tree-sitter indexer) and tests/test_repo_indexer.py (166 tests). All 10,194 tests pass via 'make test'. The indexer walks a checked-out repository, respects .gitignore rules, skips binary/oversized/unsupported files with diagnostics, and uses Tree-sitter grammars to extract symbols and references for Python, Rust, TypeScript, JavaScript, YAML, and Markdown. Returns a RepoMap conforming to the OOMPAH-294 artifact contract. tree-sitter grammar packages added to pyproject.toml [server] and [dev] extras. Committed to branch epic-OOMPAH-293 (the parent epic's feature branch, consistent with OOMPAH-294) and pushed.
---
author: oompah
created: 2026-07-21 16:39
---
Implemented Tree-sitter repository indexer (oompah/repo_indexer.py) with symbol and reference extraction for Python, Rust, TypeScript, JavaScript, YAML, and Markdown. Added 166 comprehensive tests in tests/test_repo_indexer.py. All 10,194 tests pass via make test. tree-sitter grammar packages added to pyproject.toml.
---
author: oompah
created: 2026-07-21 16:40
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 65
- Tokens: 100 in / 3.0K out [3.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 10s
- Log: OOMPAH-295__20260721T161456Z.jsonl
---
author: oompah
created: 2026-07-22 00:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:32
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 00:36
---
Agent failed: Exception: Command failed with exit code 143 (exit code: 143)
Error output: Check stderr output for details. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-22 00:36
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 31, Tool calls: 20
- Tokens: 39 in / 1.1K out [1.2K total]
- Cost: $0.0000
- Exit: error, Duration: 4m 43s
- Log: OOMPAH-295__20260722T003213Z.jsonl
---
author: oompah
created: 2026-07-22 00:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 00:37
---
Focus: Test Engineer
---
<!-- COMMENTS:END -->
