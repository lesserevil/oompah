---
id: OOMPAH-40
type: task
status: In Progress
priority: 1
title: Fix draft-release findings and sync them back to main
parent: OOMPAH-37
children: []
blocked_by:
- OOMPAH-39
labels: []
assignee: null
created_at: '2026-06-22T01:17:39.633849Z'
updated_at: '2026-06-22T16:00:07.742596Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 393afc6c-caa7-4856-b37a-40ed78da4789
oompah.task_costs:
  total_input_tokens: 95
  total_output_tokens: 2894
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 95
      output_tokens: 2894
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 80
    output_tokens: 2822
    cost_usd: 0.0
    recorded_at: '2026-06-22T15:48:16.703367+00:00'
  - profile: standard
    model: unknown
    input_tokens: 15
    output_tokens: 72
    cost_usd: 0.0
    recorded_at: '2026-06-22T15:49:17.177403+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#release-execution-and-verification

WHAT TO DO
Fix any issues found during draft release verification on release/1.0 and merge or cherry-pick the fixes back to main as appropriate.

HOW TO VERIFY
Draft findings are either fixed and verified or explicitly documented as non-blocking before final release.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 15:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 15:32
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 15:33
---
UNDERSTANDING: Not a duplicate. OOMPAH-40 is step E3 in the 1.0 release plan (plans/oompah-1.0-release.md#release-execution-and-verification). OOMPAH-39 (E2) is now Done. All other tasks are distinct: OOMPAH-38=E1, OOMPAH-41=E4, OOMPAH-42=E5. Proceeding with E3 work: identify what changes were applied to release/1.0 during OOMPAH-39 that need to be synced back to main, and check for any remaining draft-verification findings.
---
author: oompah
created: 2026-06-22 15:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 54
- Tokens: 80 in / 2.8K out [2.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 16s
- Log: OOMPAH-40__20260622T153205Z.jsonl
---
author: oompah
created: 2026-06-22 15:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-06-22 15:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 15:49
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 6
- Tokens: 15 in / 72 out [87 total]
- Cost: $0.0000
- Exit: terminated, Duration: 43s
- Log: OOMPAH-40__20260622T154840Z.jsonl
---
author: oompah
created: 2026-06-22 15:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 15:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 15:52
---
UNDERSTANDING: E3 task confirmed not a duplicate. OOMPAH-39 (E2) applied Epic A workstream changes to release/1.0 as commit 21033827 (scripts/render_cli_release_notes.py draft tag support, updated test suite, docs/cli-api-surface.md new file, updated docs/cli-release.md, docs/cli-install.md, plans/oompah-1.0-release.md). These changes do NOT exist on main. Plan: cherry-pick commit 21033827 from release/1.0 onto main via this branch, run tests, push. Current worktree is on epic-OOMPAH-37 (behind origin/main by 27 commits). Will pull to update then cherry-pick.
---
author: oompah
created: 2026-06-22 16:00
---
DISCOVERY: Two issues found after cherry-picking commit 21033827 onto main.\n\n1. test_pyproject_version_is_1_0_0 FAILS: main still has version 0.1.0; need to also cherry-pick the version bump commit (d6faeace).\n\n2. test_orchestrator_webhook_health.py::TestFetchAllReviewsSkipsHealthy (2 failures): Pre-existing bug on both main and release/1.0. _fetch_all_reviews() only skips healthy projects when they have warm cache entries. Tests expect healthy projects to ALWAYS be skipped (never call provider), returning [] if no cache. Fix: change condition from 'is_webhook_healthy AND warm_cache' to 'is_webhook_healthy' only.
---
<!-- COMMENTS:END -->
