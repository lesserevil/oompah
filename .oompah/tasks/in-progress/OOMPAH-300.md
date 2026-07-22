---
id: OOMPAH-300
type: task
status: In Progress
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
updated_at: '2026-07-22T00:03:49.039480Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3bcad6b2-86b5-4e2a-b0d5-54352f1cc682
oompah.task_costs:
  total_input_tokens: 280159
  total_output_tokens: 10885
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 280159
      output_tokens: 10885
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
<!-- COMMENTS:END -->
