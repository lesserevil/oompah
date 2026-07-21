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
- needs:feature
assignee: null
created_at: '2026-07-21T15:13:47.496504Z'
updated_at: '2026-07-21T15:48:11.112577Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f0066eb5-c34a-4619-8f70-73b6c36f3405
oompah.task_costs:
  total_input_tokens: 275556
  total_output_tokens: 1584
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 275556
      output_tokens: 1584
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 275556
    output_tokens: 1584
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:46:09.606215+00:00'
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
<!-- COMMENTS:END -->
