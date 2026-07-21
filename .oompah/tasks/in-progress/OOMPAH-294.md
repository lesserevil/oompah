---
id: OOMPAH-294
type: task
status: In Progress
priority: 1
title: Define repository-map artifact and state-branch lifecycle
parent: OOMPAH-293
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:13:47.496504Z'
updated_at: '2026-07-21T16:10:45.133224Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 05d53f75-0d26-4b05-8325-cf56da480d7c
oompah.task_costs:
  total_input_tokens: 468330
  total_output_tokens: 7258
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 468330
      output_tokens: 7258
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 275556
    output_tokens: 1584
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:46:09.606215+00:00'
  - profile: standard
    model: unknown
    input_tokens: 17
    output_tokens: 4062
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:48:16.321858+00:00'
  - profile: standard
    model: unknown
    input_tokens: 192757
    output_tokens: 1612
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:49:11.558166+00:00'
---
## Summary

Write the implementation design and add the core model/types for a repository-map artifact. Define a versioned, deterministic JSON schema containing: repository identity, analyzed commit SHA, generator version, indexed files, symbol tags, relationship edges, generation timestamp, and rendering metadata. Define the exact state-branch path, atomic-write procedure, freshness rule (map SHA must equal checkout SHA), retention/pruning policy, and behavior for unavailable or unsupported repositories.\n\nDo not add parsing or prompt injection in this task. The artifact must be data only; it must never be executed or interpreted as instructions.\n\nTests:\n- Unit-test schema serialization/deserialization and schema-version rejection.\n- Unit-test deterministic output for identical input and invalidation when the commit SHA changes.\n- Unit-test all path construction and state-branch writes remain within the project state namespace.\n\nAcceptance criteria:\n- A documented schema and lifecycle exist in plans/.\n- Code exposes a typed artifact contract for later tasks.\n- Artifacts are keyed by repository identity and commit SHA and are safe to read only when fresh.\n- Tests pass through the project Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed successfully in 47s (277140 tokens)
---
author: oompah
created: 2026-07-21 15:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 275.6K in / 1.6K out [277.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-294__20260721T154528Z.jsonl
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-293`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 15:46
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 15:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:48
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate found. Searched all .oompah/tasks/ directories (archived, done, merged, backlog, needs-ci-fix, needs-rebase) and the plans/ directory for: repository-map, repo-map, repomap, repo_map, symbol tags, indexed files, commit SHA artifact, relationship edges. Zero matches.

2. **Closest reviewed tasks/evidence**:
   - \`plans/state-branch-design.md\` (related to epic OOMPAH-253): About isolating oompah *task* state onto a git state branch. Completely different from a code-repository-map artifact (indexed files, symbol tags, edges).
   - OOMPAH-282 (backlog): Bug report about state branch migration UnicodeEncodeError. Unrelated.
   - No merged task in the 166-280 range describes anything resembling a versioned repo-map JSON schema for code analysis.

3. **Remaining work**: Full implementation required — the schema design, typed Python model, state-branch path definitions, atomic-write logic, freshness rules, retention policy, and unit tests are all absent from the codebase.

4. **Recommended next focus**: feature — this is net-new implementation work (plan doc in plans/, typed artifact model in oompah/, unit tests in tests/).
---
author: oompah
created: 2026-07-21 15:48
---
Agent completed successfully in 105s (4079 tokens)
---
author: oompah
created: 2026-07-21 15:48
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 34, Tool calls: 24
- Tokens: 17 in / 4.1K out [4.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 45s
- Log: OOMPAH-294__20260721T154634Z.jsonl
---
author: oompah
created: 2026-07-21 15:48
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 15:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 15:48
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 15:49
---
Agent completed successfully in 45s (194369 tokens)
---
author: oompah
created: 2026-07-21 15:49
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 192.8K in / 1.6K out [194.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 45s
- Log: OOMPAH-294__20260721T154828Z.jsonl
---
author: oompah
created: 2026-07-21 15:49
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-293`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 15:49
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 15:49
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 15:50
---
Understanding: As Test Engineer, I will write unit tests for the repository-map artifact module (oompah/repo_map.py) and plan doc (plans/repo-map-artifact.md). Previous agents attempted but landed no commits. I will implement all three: (1) the plan doc, (2) the typed Python artifact contract, and (3) comprehensive unit tests covering schema serialization/deserialization, schema-version rejection, deterministic output, SHA-based invalidation, and path/namespace constraints. Tests will use the make test target.
---
author: oompah
created: 2026-07-21 15:51
---
Discovery: No prior repo_map code exists. Following patterns from oompah/release_pick_schema.py (typed dataclasses, from_raw/to_raw, enum-based states) and oompah/intake_schema.py. State-branch path pattern from plans/state-branch-design.md uses .oompah/ namespace. Will create: plans/repo-map-artifact.md (design doc), oompah/repo_map.py (typed schema + atomic write/read + freshness/prune), tests/test_repo_map.py (full unit test suite).
---
author: oompah
created: 2026-07-21 16:10
---
Implementation complete. Created: (1) plans/repo-map-artifact.md — full design doc covering schema, state-branch path, atomic-write, freshness rule, retention, and unsupported-repo behavior; (2) oompah/repo_map.py — typed Python artifact contract (IndexedFile, SymbolTag, RelationshipEdge, RenderingMetadata, RepoMap dataclasses plus SchemaVersionError, repo_map_slug, repo_map_path, is_within_namespace, is_fresh, write_repo_map, read_repo_map, prune_repo_maps); (3) tests/test_repo_map.py — 106 unit tests.
---
author: oompah
created: 2026-07-21 16:10
---
Verification: make test passed — 10028 passed, 36 skipped, 11 warnings. All 106 new tests in tests/test_repo_map.py pass. Coverage: schema serialization/deserialization, schema-version rejection (wrong version, None, future, string, missing key), deterministic output, SHA-based invalidation, path construction (all within .oompah/ namespace), atomic write, freshness/staleness, pruning, and unsupported/unavailable repository behavior.
---
<!-- COMMENTS:END -->
