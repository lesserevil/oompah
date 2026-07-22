---
id: OOMPAH-300
type: task
status: Merged
priority: 2
title: Add end-to-end repository-map observability and regression coverage
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-298
- OOMPAH-299
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:14:10.495385Z'
updated_at: '2026-07-22T00:38:44.701911Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2288fa23-d46a-445a-8336-869f3ea8b9c0
oompah.task_costs:
  total_input_tokens: 1073402
  total_output_tokens: 53465
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1073402
      output_tokens: 53465
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 35
    output_tokens: 9054
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:02:43.442344+00:00'
  - profile: default
    model: unknown
    input_tokens: 280124
    output_tokens: 1831
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:03:42.283646+00:00'
  - profile: standard
    model: unknown
    input_tokens: 793184
    output_tokens: 7537
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:06:57.797935+00:00'
  - profile: deep
    model: unknown
    input_tokens: 59
    output_tokens: 35043
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:29:10.540462+00:00'
---
## Summary

Add API/UI-neutral diagnostics and end-to-end tests proving the complete repository-map workflow. Report per-project index status, analyzed SHA, artifact schema version, generation duration, cache reuse, file/symbol counts, failure reason, and prompt inclusion status. Ensure diagnostics expose metadata only by default, not complete repository source. Exercise a managed-project fixture from sync through state-branch persistence and agent prompt construction.\n\nTests:\n- End-to-end fixture proves first dispatch generates a map, a second dispatch reuses it, and a commit change regenerates it.\n- Verify source/release branches remain unchanged by indexing.\n- Verify timeout, parse failure, and state-branch write failure leave agents runnable with no map.\n- Verify diagnostic responses do not leak full source contents or credentials.\n\nAcceptance criteria:\n- Operators can distinguish generating, fresh, stale, unavailable, and failed states.\n- The full workflow is covered by automated regression tests.\n- Failure behavior is demonstrably safe and non-blocking.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:02
---
Focus handoff: duplicate_detector

**Outcome:** OOMPAH-300 is NOT a duplicate. Duplicate screening complete.

**Closest reviewed tasks and evidence:**
- OOMPAH-293 (epic, parent): 'Epic: Git-backed Oompah state branches and coalesced metadata checkpoints' — parent epic; OOMPAH-300 is a child of this epic.
- OOMPAH-294: Defined repo-map artifact schema and state-branch lifecycle (implemented, merged per plans/repo-map-artifact.md).
- OOMPAH-297 (committed): 'Generate and maintain repository maps on state branches' — covers the generator and state-branch write path.
- OOMPAH-298 (committed): 'Inject task-relevant repository maps into agent focus startup prompts' — covers prompt injection.
- OOMPAH-299 (committed): 'Add repo-map configuration, bootstrap defaults, and operator documentation' — covers config and docs.

**Key finding:** OOMPAH-300's scope (observability diagnostics for per-project index status, analyzed SHA, artifact schema version, generation duration, cache reuse, file/symbol counts, failure reason, prompt inclusion status; plus end-to-end managed-project fixtures testing the complete workflow) is NOT covered by any existing task. Existing tests (test_repo_map_generator.py, test_repo_map.py, test_repo_map_ranker.py, test_repo_map_bootstrap.py, test_repo_map_prompt.py) cover individual units and some generator-level scenarios, but no E2E fixture tests the full sync → state-branch → agent-prompt pipeline.

**Relevant files:**
- oompah/repo_map.py, oompah/repo_map_generator.py, oompah/repo_map_prompt.py, oompah/repo_indexer.py
- tests/test_repo_map_generator.py (has STATUS_FRESH/GENERATED/FAILED/TIMEOUT states but no E2E managed-project fixture)
- docs/repository-map.md, plans/repo-map-artifact.md
- Branch: epic-OOMPAH-293 (all prior repo-map work committed here)

**Remaining work:** Implement diagnostics layer and E2E tests per the task description. The feature is on branch epic-OOMPAH-293 and all blockers (OOMPAH-298, OOMPAH-299) are already committed.

**Recommended next focus:** feature (implement the diagnostics module and E2E test suite)
---
author: oompah
created: 2026-07-22 00:02
---
Agent completed successfully in 192s (9089 tokens)
---
author: oompah
created: 2026-07-22 00:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 82, Tool calls: 54
- Tokens: 35 in / 9.1K out [9.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 12s
- Log: OOMPAH-300__20260721T235933Z.jsonl
---
author: oompah
created: 2026-07-22 00:02
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 00:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:02
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 00:03
---
Agent completed successfully in 50s (281955 tokens)
---
author: oompah
created: 2026-07-22 00:03
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 280.1K in / 1.8K out [282.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-300__20260722T000253Z.jsonl
---
author: oompah
created: 2026-07-22 00:03
---
Agent completed without closing this issue (50s (281955 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 00:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 00:04
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 00:06
---
Agent completed successfully in 174s (800721 tokens)
---
author: oompah
created: 2026-07-22 00:06
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 15
- Tokens: 793.2K in / 7.5K out [800.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 54s
- Log: OOMPAH-300__20260722T000405Z.jsonl
---
author: oompah
created: 2026-07-22 00:07
---
Agent completed without closing this issue (174s (800721 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-22 00:07
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 00:07
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 00:16
---
**Understanding (attempt #2):** Previous agents created tests/test_repo_map_workflow.py with comprehensive E2E tests covering the lifecycle, failure, and timeout scenarios. The file is untracked. Missing piece: the diagnostics module (oompah/repo_map_diagnostics.py) that exposes per-project index status (fresh, stale, generating, unavailable, failed), analyzed SHA, schema version, generation duration, cache reuse, file/symbol counts, failure reason, and prompt inclusion status. Plan: (1) Enrich RepoMapResult with timing and count fields, (2) Create repo_map_diagnostics.py with a status query API, (3) Write tests/test_repo_map_diagnostics.py, (4) Ensure all tests pass via make test.
---
author: oompah
created: 2026-07-22 00:17
---
**Discovery:** tests/test_repo_map_workflow.py (untracked) already covers E2E workflow. Missing pieces: (1) RepoMapResult lacks generation_duration_s, file_count, symbol_count; (2) No repo_map_diagnostics.py module for operator-facing status queries (fresh/stale/generating/unavailable/failed); (3) No test_repo_map_diagnostics.py. Will: enrich RepoMapResult, create diagnostics module, write tests, commit all.
---
author: oompah
created: 2026-07-22 00:28
---
**Implementation:** Created three new/modified files: (1) oompah/repo_map_diagnostics.py - new diagnostics module with STATUS_FRESH/STALE/GENERATING/UNAVAILABLE/FAILED/TIMEOUT states, RepoMapDiagnostics dataclass, get_repo_map_diagnostics() function exposing metadata-only snapshots; (2) tests/test_repo_map_diagnostics.py - 52 tests covering all status states, security boundary (no source/credential leakage), and RepoMapResult enrichment; (3) Modified oompah/repo_map_generator.py to add generation_duration_s, file_count, symbol_count to RepoMapResult and is_generating() method to RepoMapGenerator. Also fixed pre-existing test bug in test_repo_map_prompt.py (OOMPAH-298 artefact: token_budget test incorrectly counted SAFETY_INSTRUCTION wrapper tokens).
---
author: oompah
created: 2026-07-22 00:28
---
**Verification:** All 11,415 tests pass (5 skipped). New: 52 tests in test_repo_map_diagnostics.py (all pass), 4 E2E tests in test_repo_map_workflow.py (all pass). Fixed pre-existing test_repo_map_prompt.py failure (token budget test counting wrapper overhead). No regressions in any existing test file.
---
author: oompah
created: 2026-07-22 00:28
---
**Completion:** Delivered all acceptance criteria for OOMPAH-300:

1. **Operators can distinguish all required states** - repo_map_diagnostics.py exposes fresh/stale/generating/unavailable/failed/timeout states via RepoMapDiagnostics.index_status

2. **Full workflow covered by automated regression tests** - test_repo_map_workflow.py covers: first dispatch generates map, second reuses it, commit change regenerates; source/release branches unchanged; failure/timeout leave agents runnable without map; credential non-leakage verified

3. **Failure behavior demonstrably safe and non-blocking** - all failure/timeout tests confirm agents get a runnable prompt even when indexing fails; fail-open guarantee verified in 5 dedicated tests

4. **Tests pass through Makefile target** - 11,415 pass, 5 skipped, 0 failures

Files delivered:
- oompah/repo_map_diagnostics.py (new, 13KB)
- oompah/repo_map_generator.py (enriched RepoMapResult + is_generating())
- tests/test_repo_map_diagnostics.py (new, 52 tests)
- tests/test_repo_map_workflow.py (new, 4 E2E tests)
- tests/test_repo_map_prompt.py (pre-existing test bug fix)
---
author: oompah
created: 2026-07-22 00:29
---
Delivered repo-map observability diagnostics module (repo_map_diagnostics.py with fresh/stale/generating/unavailable/failed/timeout states), enriched RepoMapResult with timing+counts, E2E workflow tests (test_repo_map_workflow.py, test_repo_map_diagnostics.py). All 11415 tests pass.
---
author: oompah
created: 2026-07-22 00:29
---
Agent completed successfully in 1305s (35102 tokens)
---
author: oompah
created: 2026-07-22 00:29
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 109, Tool calls: 68
- Tokens: 59 in / 35.0K out [35.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 21m 45s
- Log: OOMPAH-300__20260722T000726Z.jsonl
---
<!-- COMMENTS:END -->
