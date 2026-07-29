---
id: OOMPAH-567
type: task
status: In Progress
priority: null
title: Install complete test dependencies in fresh Makefile worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T22:48:39.126282Z'
updated_at: '2026-07-29T22:52:42.312991Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 74a23c6d090c22ea61528ddfcf61a260aa0aac54abbcc720f6217632de107b58
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T22:51:59.901868+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: No active task covers fresh-worktree test dependency setup. Reviewed
    active OOMPAH-281 (self-hosted runner) and archived OOMPAH-25/31 (packaging/bootstrap),
    which are distinct. No files or tracker state were modified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0f6e797a-df52-41e5-aa88-1fe927890b1d
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-567__20260729T225056Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-567
    source_sha: 9fab41077abdd6d02c19624c9713a144f8c84b9e
    completed_at: '2026-07-29T22:51:59.906486+00:00'
oompah.task_costs:
  total_input_tokens: 429814
  total_output_tokens: 2360
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 429814
      output_tokens: 2360
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 429814
    output_tokens: 2360
    cost_usd: 0.0
    recorded_at: '2026-07-29T22:51:59.900737+00:00'
---
## Summary

Fresh integration worktrees run the configured quality gate via make test. The Makefile test target currently depends on setup, which installs only .[server]; uv then adds only the dependency-group pytest packages, leaving the claude, codex, and granian test dependencies absent. Live reproduction on OOMPAH-564 and OOMPAH-565: both exact combined-tree gates produced 112 failures and 4 errors, including SDK install guards and authority/terminal interface tests, while the same heads pass CI where .[dev] is installed. Scope: give make test/test-serial an idempotent test-specific setup marker that installs .[dev] without changing production start/setup behavior; ensure the marker is invalidated by pyproject.toml; document target behavior if needed. Add Makefile/packaging regression tests that prove test targets depend on the complete dev extra and server startup remains server-only. Acceptance criteria: a clean worktree with no preexisting .venv can run make test with both agent SDKs and granian importable; focused tests pass; the full Makefile gate passes; committed work is pushed and submitted through oompah.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 22:49
---
Implementing the fresh-worktree Makefile test dependency fix directly from the primary checkout.
---
author: oompah
created: 2026-07-29 22:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 22:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 22:52
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 429.8K in / 2.4K out [432.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 15s
- Log: OOMPAH-567__20260729T225056Z.jsonl
---
author: oompah
created: 2026-07-29 22:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 22:52
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-29 22:52
---
Understanding: Fresh worktrees fail make test because test targets depend only on setup which installs .[server], leaving claude/codex/granian test deps absent. Need to: (1) Add idempotent test-specific setup marker installing .[dev] without changing prod start/setup; (2) Ensure marker invalidated by pyproject.toml; (3) Add regression tests proving test depends on dev extra + server startup remains server-only. Approach: Examine Makefile test targets and pyproject.toml structure, then implement cached marker pattern.
---
<!-- COMMENTS:END -->
